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
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from fastapi import FastAPI, File, HTTPException, UploadFile
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
        translators.append({"id": pid, **meta})

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
