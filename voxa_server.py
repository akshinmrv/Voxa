"""Voxa operator server — the backend behind ``voxa serve``.

A small FastAPI app so a browser UI can upload a video, pick engines, watch the
seven-step pipeline live (Server-Sent Events), and download the result. Each job
shells out to the very same ``voxa`` CLI in an isolated working directory, so the
core dubbing code is never imported into the request path and stays untouched.

Install the extra dependencies with::

    pip install "voxa[serve]"

Then run::

    voxa serve            # http://127.0.0.1:8000
    voxa serve --port 9000
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

# The registries come straight from the tool, so the UI always reflects what this
# install actually supports.
import voxa

# --------------------------------------------------------------------------- #
# Registry → options
# --------------------------------------------------------------------------- #

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large", "turbo"]

# OpenAI TTS model/voice choices offered when the OpenAI engine is selected.
OPENAI_TTS_MODELS = ["gpt-4o-mini-tts", "tts-1", "tts-1-hd"]
OPENAI_VOICES = [
    "alloy", "ash", "ballad", "coral", "echo", "fable",
    "nova", "onyx", "sage", "shimmer", "verse",
]

# A curated shortlist for the dropdown; the CLI itself accepts any language code.
COMMON_LANGUAGES = [
    ("ru", "Russian"), ("tr", "Turkish"), ("az", "Azerbaijani"), ("en", "English"),
    ("de", "German"), ("fr", "French"), ("es", "Spanish"), ("it", "Italian"),
    ("pt", "Portuguese"), ("ar", "Arabic"), ("zh", "Chinese"), ("ja", "Japanese"),
]

_TRANSLATOR_META = {
    "google": {"label": "Google", "description": "Free, fast, no key required"},
    "ollama": {"label": "Ollama", "description": "Local LLM, fully offline", "offline": True},
    "openai": {"label": "OpenAI", "description": "Context-aware, needs API key"},
    "anthropic": {"label": "Anthropic", "description": "Context-aware, needs API key"},
}

_TTS_META = {
    "edge": {"label": "Edge", "description": "Cloud, many natural voices"},
    "openai": {"label": "OpenAI", "description": "Cloud or self-hosted endpoint"},
    "piper": {"label": "Piper", "description": "Fully offline neural TTS", "offline": True},
    "xtts": {"label": "XTTS", "description": "Voice cloning from a sample",
             "requiresVoiceSample": True},
}


def build_options() -> dict:
    """Assemble the /api/options payload from the tool's live registries."""
    translators = [{"id": "google", **_TRANSLATOR_META["google"]},
                   {"id": "ollama", **_TRANSLATOR_META["ollama"]}]
    for pid in sorted(voxa.LLM_PROVIDERS):
        meta = _TRANSLATOR_META.get(pid, {"label": pid.capitalize(),
                                          "description": "Context-aware LLM, needs API key"})
        # defaultModel lets the settings UI show the engine's built-in model as a placeholder.
        translators.append({"id": pid, **meta,
                            "defaultModel": voxa.LLM_PROVIDERS[pid]["default_model"]})

    tts_engines = []
    for tid in sorted(voxa.TTS_PROVIDERS):
        meta = _TTS_META.get(tid, {"label": tid.capitalize(), "description": ""})
        tts_engines.append({"id": tid, **meta})

    return {
        "languages": [{"code": c, "name": n} for c, n in COMMON_LANGUAGES],
        "translators": translators,
        "ttsEngines": tts_engines,
        "whisperModels": [{"id": m, "label": m} for m in WHISPER_MODELS],
        "openaiTtsModels": [{"id": m, "label": m} for m in OPENAI_TTS_MODELS],
        "openaiVoices": [{"id": v, "label": v} for v in OPENAI_VOICES],
    }


# --------------------------------------------------------------------------- #
# Jobs
# --------------------------------------------------------------------------- #

STEP_RE = re.compile(r"\[(\d)/7\]")
TOTAL_STEPS = 7

WORKSPACE = Path.cwd() / ".voxa_serve"
UPLOAD_DIR = WORKSPACE / "uploads"
JOBS_DIR = WORKSPACE / "jobs"

# Dubbing is heavy (a Whisper model + ffmpeg); run one job at a time so a second
# request queues instead of thrashing the machine.
_JOB_LOCK = asyncio.Lock()

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_name(name: str) -> str:
    cleaned = _SAFE.sub("_", Path(name).name).strip("._") or "video"
    return cleaned


class JobConfigModel(BaseModel):
    targetLang: str
    translator: str
    tts: str
    whisperModel: str = "base"
    voiceSample: Optional[str] = None
    openaiTtsModel: Optional[str] = None
    openaiVoice: Optional[str] = None


class CreateJobModel(BaseModel):
    fileId: str
    config: JobConfigModel


@dataclass
class Job:
    id: str
    file_name: str
    config: JobConfigModel
    work_dir: Path
    status: str = "queued"  # queued | running | done | failed
    step: int = 0
    events: List[dict] = field(default_factory=list)
    subscribers: Set["asyncio.Queue[dict]"] = field(default_factory=set)
    result_video: Optional[Path] = None
    result_srt: Optional[Path] = None
    error: Optional[str] = None

    def summary(self) -> dict:
        return {
            "id": self.id,
            "fileName": self.file_name,
            "config": self.config.model_dump(),
            "status": self.status,
            "step": self.step,
            "totalSteps": TOTAL_STEPS,
            "hasVideo": bool(self.result_video and self.result_video.exists()),
            "hasSrt": bool(self.result_srt and self.result_srt.exists()),
            "error": self.error,
        }


UPLOADS: Dict[str, Path] = {}
JOBS: Dict[str, Job] = {}


async def _emit(job: Job, event: dict) -> None:
    job.events.append(event)
    for q in list(job.subscribers):
        q.put_nowait(event)


async def _run_job(job: Job) -> None:
    """Run one dubbing job as a subprocess and stream its [N/7] progress."""
    async with _JOB_LOCK:
        job.status = "running"
        await _emit(job, {"type": "status", "status": "running"})

        cfg = job.config
        cmd = [
            sys.executable, voxa.__file__, job.file_name,
            "--target_lang", cfg.targetLang,
            "--translator", cfg.translator,
            "--tts", cfg.tts,
            "--whisper_model", cfg.whisperModel,
            "--output-dir", str(job.work_dir),
        ]
        # Apply the operator's saved per-provider model (P1) and translation style (P2).
        current_settings = read_settings()
        cmd += provider_model_args(cfg.translator, current_settings)
        cmd += translation_prompt_args(cfg.translator, current_settings)
        if cfg.tts == "xtts" and cfg.voiceSample:
            cmd += ["--voice-sample", cfg.voiceSample]
        if cfg.tts == "openai":
            if cfg.openaiTtsModel:
                cmd += ["--openai-tts-model", cfg.openaiTtsModel]
            if cfg.openaiVoice:
                cmd += ["--openai-voice", cfg.openaiVoice]

        # Force UTF-8 in the child so its emoji log lines encode to the pipe on any
        # console codepage (Windows defaults to a legacy ANSI codepage otherwise).
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(job.work_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
        except OSError as exc:
            job.status = "failed"
            job.error = f"Failed to launch voxa: {exc}"
            await _emit(job, {"type": "status", "status": "failed", "error": job.error})
            return

        assert proc.stdout is not None
        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if not line:
                continue
            await _emit(job, {"type": "log", "line": line})
            match = STEP_RE.search(line)
            if match:
                n = int(match.group(1))
                done = ("✓" in line) or ("already completed" in line)
                job.step = n
                await _emit(job, {"type": "step", "step": n,
                                  "status": "done" if done else "running"})

        code = await proc.wait()
        if code == 0:
            stem = Path(job.file_name).stem
            video = job.work_dir / f"{stem}_dubbed_{cfg.targetLang}.mp4"
            srt = job.work_dir / f"{stem}_work" / f"subtitles_{cfg.targetLang}.srt"
            job.result_video = video if video.exists() else None
            job.result_srt = srt if srt.exists() else None
            job.status = "done"
            await _emit(job, {"type": "status", "status": "done"})
        else:
            job.status = "failed"
            job.error = f"voxa exited with code {code}"
            await _emit(job, {"type": "status", "status": "failed", "error": job.error})


# --------------------------------------------------------------------------- #
# Settings & API keys (P0 — Foundation)
#
# The operator UI persists two kinds of config, deliberately kept apart:
#   • non-secret settings  → .voxa_serve/settings.json  (safe to keep/version)
#   • API keys (secrets)   → the .env file              (git-ignored, never echoed)
#
# The core `voxa.py` engine is untouched: it already reads keys from the
# environment and defaults from a --config JSON, so this layer only writes the
# files it already knows how to read. See AI_PROVIDER_AND_SPEECH_CONTROL_STRATEGY_AZ.md.
# --------------------------------------------------------------------------- #

SETTINGS_FILE = WORKSPACE / "settings.json"
SETTINGS_VERSION = 1

# .env path the settings layer reads/writes; set from --env-file at startup.
ENV_FILE = ".env"

# Only requests from the loopback interface may read or change settings/keys.
_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def default_settings() -> dict:
    """The out-of-the-box settings object. Nested groups (translation/speech/advanced)
    are placeholders that later phases (P2/P3/P4) populate; None means "use the engine's
    built-in default"."""
    return {
        "version": SETTINGS_VERSION,
        "defaultTranslator": "google",
        "defaultTts": "edge",
        # Per-LLM-provider default translation model (None = the engine's built-in default).
        "providers": {pid: {"model": None} for pid in voxa.LLM_PROVIDERS},
        "translation": {"prompt": None},
        "speech": {"instructions": None, "presets": []},
        "advanced": {"speechRate": None},
    }


def _merge_settings(base: dict, patch: dict) -> dict:
    """Shallow merge with one level of nesting for the known group objects. A None value
    in the patch is ignored (partial update), so callers only send what changed."""
    out = dict(base)
    for key, value in patch.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            nested = dict(out[key])
            nested.update(value)
            out[key] = nested
        else:
            out[key] = value
    return out


def read_settings() -> dict:
    """Current settings, always shaped like default_settings() (missing keys are filled,
    so an older on-disk file stays forward-compatible). Invalid/missing file → defaults."""
    base = default_settings()
    try:
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                base = _merge_settings(base, data)
    except Exception:
        pass
    base["version"] = SETTINGS_VERSION
    return base


def write_settings(patch: dict) -> dict:
    """Merge a partial patch into the current settings and persist atomically."""
    updated = _merge_settings(read_settings(), patch)
    updated["version"] = SETTINGS_VERSION
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_FILE.with_name(SETTINGS_FILE.name + ".tmp")
    tmp.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SETTINGS_FILE)
    return updated


def reset_settings() -> dict:
    """Delete the settings file so defaults take over again (Danger Zone → Reset)."""
    try:
        SETTINGS_FILE.unlink()
    except FileNotFoundError:
        pass
    return read_settings()


def valid_translators() -> Set[str]:
    return {"google", "ollama"} | set(voxa.LLM_PROVIDERS)


# ── API-key storage in .env (secrets never leave the machine) ────────────────

def _mask(value: str) -> str:
    """Show only the last 4 chars; the full key is never returned to the browser."""
    v = (value or "").strip()
    return ("••••" + v[-4:]) if len(v) > 4 else "••••"


def _key_lines_without(env_key: str) -> List[str]:
    path = Path(ENV_FILE)
    if not path.exists():
        return []
    return [ln for ln in path.read_text(encoding="utf-8").splitlines()
            if not ln.strip().replace(" ", "").startswith(f"{env_key}=")]


def set_env_key(env_key: str, value: str) -> None:
    """Upsert KEY=value in the .env file (preserving other lines) and the live process
    environment, so already-inherited job subprocesses and new ones both see it."""
    value = (value or "").strip()
    lines = _key_lines_without(env_key)
    lines.append(f"{env_key}={value}")
    Path(ENV_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[env_key] = value


def delete_env_key(env_key: str) -> None:
    """Remove KEY=... from the .env file and the live environment."""
    lines = _key_lines_without(env_key)
    path = Path(ENV_FILE)
    path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
    os.environ.pop(env_key, None)


def read_key_status() -> List[dict]:
    """Masked status for every provider that needs a key. 'hasKey' reflects the live
    environment (what a job would actually use), never the raw value."""
    out = []
    for pid, info in voxa.LLM_PROVIDERS.items():
        env_key = info["env_key"]
        value = os.environ.get(env_key, "")
        out.append({
            "provider": pid,
            "envKey": env_key,
            "hasKey": bool(value),
            "masked": _mask(value) if value else None,
        })
    return out


def require_local(request: Request) -> None:
    """Reject any non-loopback caller. Defense in depth: the server binds 127.0.0.1 by
    default, but this still holds if it is ever started with --host 0.0.0.0."""
    host = request.client.host if request.client else ""
    if host not in _LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="Settings are available on localhost only.")


class SettingsPatch(BaseModel):
    defaultTranslator: Optional[str] = None
    defaultTts: Optional[str] = None
    providers: Optional[dict] = None
    translation: Optional[dict] = None
    speech: Optional[dict] = None
    advanced: Optional[dict] = None


class KeyBody(BaseModel):
    value: str


def provider_model_args(translator: str, settings: dict) -> List[str]:
    """Extra CLI args pinning the translation model for an LLM provider, from settings.
    Returns [] for non-LLM translators (google/ollama) or when no model is configured."""
    if translator not in voxa.LLM_PROVIDERS:
        return []
    model = ((settings.get("providers") or {}).get(translator) or {}).get("model")
    return [f"--{translator}_model", str(model)] if model else []


def translation_prompt_args(translator: str, settings: dict) -> List[str]:
    """CLI args passing the operator's saved translation style guidance (P2) to an LLM job.
    Non-LLM translators (google/ollama) ignore prompts, so returns [] for them."""
    if translator not in voxa.LLM_PROVIDERS:
        return []
    prompt = ((settings.get("translation") or {}).get("prompt") or "").strip()
    return ["--translation-prompt", prompt] if prompt else []


def test_provider(pid: str) -> dict:
    """Connection test for one LLM provider: a cheap, no-token models.list() call that
    only checks the key is valid and the endpoint is reachable. Never raises."""
    info = voxa.LLM_PROVIDERS.get(pid)
    if not info:
        return {"ok": False, "error": f"Unknown provider: {pid}"}
    if not os.environ.get(info["env_key"]):
        return {"ok": False, "error": "No API key set."}
    try:
        key = os.environ[info["env_key"]]
        client = (voxa.get_anthropic_client(key) if pid == "anthropic"
                  else voxa.get_openai_client(key))
        if client is None:
            return {"ok": False, "error": "Client unavailable (provider package missing?)."}
        started = time.perf_counter()
        client.models.list()
        return {"ok": True, "latencyMs": int((time.perf_counter() - started) * 1000)}
    except Exception as exc:  # noqa: BLE001 — surface any auth/network error to the UI
        return {"ok": False, "error": str(exc)[:300]}


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #

app = FastAPI(title="Voxa operator server", version=voxa.__dict__.get("__version__", "1.0.0"))

# The operator UI is served separately (Next.js dev on :3000, or a static build);
# allow it to call this local API.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.get("/api/options")
async def options() -> dict:
    return build_options()


@app.get("/api/settings")
async def get_settings() -> dict:
    return read_settings()


@app.put("/api/settings")
async def put_settings(patch: SettingsPatch, _: None = Depends(require_local)) -> dict:
    data = patch.model_dump(exclude_none=True)
    if "defaultTranslator" in data and data["defaultTranslator"] not in valid_translators():
        raise HTTPException(status_code=422,
                            detail=f"Unknown translator: {data['defaultTranslator']}")
    if "defaultTts" in data and data["defaultTts"] not in set(voxa.TTS_PROVIDERS):
        raise HTTPException(status_code=422, detail=f"Unknown TTS engine: {data['defaultTts']}")
    if "providers" in data:
        for pid in data["providers"]:
            if pid not in voxa.LLM_PROVIDERS:
                raise HTTPException(status_code=422, detail=f"Unknown provider: {pid}")
    if "translation" in data:
        prompt = (data["translation"] or {}).get("prompt")
        if prompt is not None and len(str(prompt)) > 4000:
            raise HTTPException(status_code=422,
                                detail="Translation style guidance is too long (max 4000 chars).")
    return write_settings(data)


@app.post("/api/settings/reset")
async def post_settings_reset(_: None = Depends(require_local)) -> dict:
    return reset_settings()


@app.get("/api/keys")
async def get_keys(_: None = Depends(require_local)) -> dict:
    return {"keys": read_key_status()}


@app.put("/api/keys/{provider}")
async def put_key(provider: str, body: KeyBody, _: None = Depends(require_local)) -> dict:
    info = voxa.LLM_PROVIDERS.get(provider)
    if not info:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    if not body.value.strip():
        raise HTTPException(status_code=422, detail="Key value is empty.")
    set_env_key(info["env_key"], body.value)
    return {"keys": read_key_status()}


@app.delete("/api/keys/{provider}")
async def delete_key(provider: str, _: None = Depends(require_local)) -> dict:
    info = voxa.LLM_PROVIDERS.get(provider)
    if not info:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    delete_env_key(info["env_key"])
    return {"keys": read_key_status()}


@app.post("/api/providers/{provider}/test")
async def post_provider_test(provider: str, _: None = Depends(require_local)) -> dict:
    return test_provider(provider)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex
    dest = UPLOAD_DIR / f"{file_id}_{_safe_name(file.filename or 'video.mp4')}"
    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            out.write(chunk)
    UPLOADS[file_id] = dest
    return {"fileId": file_id, "fileName": file.filename, "size": size}


@app.post("/api/jobs")
async def create_job(body: CreateJobModel) -> dict:
    src = UPLOADS.get(body.fileId)
    if not src or not src.exists():
        raise HTTPException(status_code=404, detail="Uploaded file not found")

    job_id = uuid.uuid4().hex[:12]
    work_dir = JOBS_DIR / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    file_name = _safe_name(Path(src.name).name.split("_", 1)[-1])
    shutil.copy2(src, work_dir / file_name)

    job = Job(id=job_id, file_name=file_name, config=body.config, work_dir=work_dir)
    JOBS[job_id] = job
    asyncio.create_task(_run_job(job))
    return {"jobId": job_id}


@app.get("/api/jobs")
async def list_jobs() -> dict:
    return {"jobs": [j.summary() for j in JOBS.values()]}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.summary()


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def stream():
        queue: "asyncio.Queue[dict]" = asyncio.Queue()
        job.subscribers.add(queue)
        try:
            # Replay history so a late subscriber catches up, then stream live.
            for event in list(job.events):
                yield f"data: {json.dumps(event)}\n\n"
            if job.status in ("done", "failed"):
                return
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "status" and event.get("status") in ("done", "failed"):
                    return
        finally:
            job.subscribers.discard(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _result(job_id: str, kind: str) -> FileResponse:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    path = job.result_video if kind == "video" else job.result_srt
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Result not ready")
    return FileResponse(str(path), filename=path.name)


@app.get("/api/jobs/{job_id}/result/video")
async def result_video(job_id: str) -> FileResponse:
    return _result(job_id, "video")


@app.get("/api/jobs/{job_id}/result/srt")
async def result_srt(job_id: str) -> FileResponse:
    return _result(job_id, "srt")


# --------------------------------------------------------------------------- #
# CLI entry (called by `voxa serve` in voxa.cli)
# --------------------------------------------------------------------------- #

def run_from_cli(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="voxa serve",
        description="Run the Voxa operator web server (upload, dub, download).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--env-file", default=".env",
                        help="Load API keys from this .env file (default: .env)")
    args = parser.parse_args(argv)

    # The settings layer reads/writes keys in this same .env file.
    global ENV_FILE
    ENV_FILE = args.env_file

    # Emoji in our banners/logs must survive a legacy console codepage (e.g. cp1254).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    # Load API keys into the environment so each job subprocess inherits them —
    # jobs run in an isolated cwd (.voxa_serve/jobs/...) where a relative .env
    # would not be found.
    try:
        from dotenv import load_dotenv
        load_dotenv(args.env_file)
    except ImportError:
        pass

    try:
        import uvicorn
    except ImportError:
        print("❌ `voxa serve` needs extra dependencies.\n"
              "   Install them with:  pip install \"voxa[serve]\"")
        return 1

    WORKSPACE.mkdir(parents=True, exist_ok=True)
    detected = [k for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY") if os.environ.get(k)]
    print(f"🌐 Voxa operator server → http://{args.host}:{args.port}")
    print(f"🔑 API keys detected: {', '.join(detected) if detected else 'none'}")
    print("   Open the web UI (see web/) and point it at this address.")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0
