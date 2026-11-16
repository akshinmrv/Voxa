"""Voxa operator server — the backend behind ``voxa serve``.

A small FastAPI app so a browser UI can upload a video, pick engines, watch the
seven-step pipeline live (Server-Sent Events), and download the result. Each job
shells out to the very same ``voxa`` CLI in an isolated working directory, so the
core dubbing code is never imported into the request path and stays untouched.

Install the extra dependencies with::

    pip install "voxa-dub[serve]"

Then run::

    voxa studio           # serve, and open the console in the browser
    voxa serve            # http://127.0.0.1:8000
    voxa serve --port 9000

A released package carries the console as a static build (the voxa_ui package) and serves
it from "/"; a source checkout has it only after ``npm run build:console`` in web/.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
import webbrowser
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Set, Tuple

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# The registries come straight from the tool, so the UI always reflects what this
# install actually supports.
import voxa
import voxa_engines

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
    "openrouter": {"label": "OpenRouter", "description": "Many vendors via one key"},
}

# Composable speech-style presets for OpenAI TTS (P3). Each compiles to a short phrase;
# they are style only — voxa itself appends the locked timing guard, so no preset here can
# affect pacing, duration or dub sync.
SPEECH_STYLE_PRESETS = {
    "warm": "warm and reassuring",
    "confident": "confident and assured",
    "calm": "calm and composed",
    "excited": "excited and upbeat",
    "documentary": "measured, authoritative documentary-narrator tone",
    "professional": "polished and professional",
    "energetic": "energetic and lively",
    "sad": "subdued and sombre",
    "friendly": "friendly and approachable",
    "natural": "natural and conversational",
    "narration": "clear narration voice",
}

_TTS_META = {
    "chatterbox": {"label": "Chatterbox", "description": "Voice cloning in 23 languages",
                   "requiresVoiceSample": True},
    "edge": {"label": "Edge", "description": "Cloud, many natural voices"},
    "openai": {"label": "OpenAI", "description": "Cloud or self-hosted endpoint"},
    "piper": {"label": "Piper", "description": "Fully offline neural TTS", "offline": True},
    "voxcpm": {"label": "VoxCPM2", "description": "Voice cloning in 30 languages, made for a GPU",
               "requiresVoiceSample": True},
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
        # An engine Voxa installs separately can be picked only once it is installed.
        available = tid not in voxa_engines.ENGINES or voxa_engines.is_installed(tid)
        tts_engines.append({"id": tid, **meta, "available": available})

    return {
        "languages": [{"code": c, "name": n} for c, n in COMMON_LANGUAGES],
        "translators": translators,
        "ttsEngines": tts_engines,
        "whisperModels": [{"id": m, "label": m} for m in WHISPER_MODELS],
        "openaiTtsModels": [{"id": m, "label": m} for m in OPENAI_TTS_MODELS],
        "openaiVoices": [{"id": v, "label": v} for v in OPENAI_VOICES],
        "speechPresets": [{"id": k, "label": k.capitalize()}
                          for k in SPEECH_STYLE_PRESETS],
        # So the job form can offer diarization only when the optional extra is installed.
        "diarizeAvailable": voxa._pyannote_available(),
        # So the job form can offer a URL source only when the yt-dlp extra is installed.
        "urlAvailable": voxa._ytdlp_available(),
        # So the job form can offer keeping the background only once Demucs is installed.
        "separateAvailable": voxa_engines.is_installed("demucs"),
        # So Settings can offer the GPUs this machine has: CUDA, or Apple's (MPS).
        "gpu": {"cuda": bool(voxa.torch is not None and voxa.torch.cuda.is_available()),
                "mps": voxa.mps_usable()},
    }


# --------------------------------------------------------------------------- #
# Jobs
# --------------------------------------------------------------------------- #

STEP_RE = re.compile(r"\[(\d)/7\]")
TOTAL_STEPS = 7

WORKSPACE = Path.cwd() / ".voxa_serve"
UPLOAD_DIR = WORKSPACE / "uploads"
JOBS_DIR = WORKSPACE / "jobs"

# Dubbing is heavy (each job is a separate process with its own Whisper model), so the number
# of dubs running at once is bounded. The default is one — the machine isn't thrashed unless
# the operator opts in — and the ceiling is deliberately low, since raising it trades memory
# and CPU for throughput. The limit is read when a job starts, so a change in Settings applies
# to the next job without restarting the server.
CONCURRENT_JOBS_MIN = 1
CONCURRENT_JOBS_MAX = 4
CONCURRENT_JOBS_DEFAULT = 1

_JOB_SLOTS: Optional[asyncio.Condition] = None
_running_jobs = 0

# Jobs on the same source share a content-keyed work dir and its resume state, so two of them
# must never run at the same time — even when the concurrency limit would allow it.
_WORKDIR_LOCKS: Dict[str, asyncio.Lock] = {}

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
    diarize: bool = False
    numSpeakers: Optional[int] = None
    maxSpeakers: Optional[int] = None
    # Keep the original's music and effects, its speech taken out (Demucs).
    separate: bool = False
    # Stop once the lines are translated, so they can be checked and changed before any is
    # voiced (status "review"); POST /api/jobs/{id}/voice then voices them.
    review: bool = False
    # Dub only the first this many seconds (voxa --preview), to hear it before dubbing it all;
    # POST /api/jobs/{id}/full then dubs the whole video.
    preview: Optional[int] = None
    # The Edge voice to speak with (voxa --edge-voice); None lets Voxa pick one.
    edgeVoice: Optional[str] = None
    # A voice per speaker of a diarized job (voxa --speaker-voices): an engine voice, or for a
    # cloning engine a clip of the voice library. Set once the speakers are known.
    speakerVoices: Optional[Dict[str, str]] = None
    # Subtitles, no speech (voxa --subtitles-only).
    subtitlesOnly: bool = False
    # The subtitles in the video: a track players can turn on ("soft"), or drawn onto the
    # picture ("hard"); in the dub, or with subtitlesOnly in the original.
    subtitlesInVideo: Optional[Literal["soft", "hard"]] = None


class CreateJobModel(BaseModel):
    # Exactly one source: an uploaded file, or a URL to download (yt-dlp extra).
    fileId: Optional[str] = None
    sourceUrl: Optional[str] = None
    config: JobConfigModel


@dataclass
class Job:
    id: str
    file_name: str
    config: JobConfigModel
    work_dir: Path
    # Set for a URL job: passed to voxa as the positional input, which downloads it
    # (via yt-dlp) into work_dir. None for an uploaded-file job.
    source_url: Optional[str] = None
    status: str = "queued"  # queued | running | review | done | failed
    step: int = 0
    events: List[dict] = field(default_factory=list)
    subscribers: Set["asyncio.Queue[dict]"] = field(default_factory=set)
    result_video: Optional[Path] = None
    result_srt: Optional[Path] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    # The lines this job translated (or was given), kept with the job: see keep_translation.
    translation_file: Optional[Path] = None
    # When its last run started and ended (epoch seconds; None until it does).
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    # Stopped from the console (POST /cancel), not failed on its own.
    cancelled: bool = False
    # The run going on now, to stop it: its task and its voxa process. Never saved.
    task: Optional[asyncio.Task] = field(default=None, repr=False, compare=False)
    process: Optional[object] = field(default=None, repr=False, compare=False)

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
            "hasTranslation": bool(self.translation_file and self.translation_file.exists()),
            "error": self.error,
            "createdAt": self.created_at,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "queuePosition": queue_position(self),
            "cancelled": self.cancelled,
        }


def queue_position(job: "Job") -> Optional[int]:
    """Where a queued job stands: 1 is next. Jobs leave the queue about in the order they were
    made (a second dub of the same video also waits for the first), so this is the order the
    console shows; None for a job that isn't queued."""
    if job.status != "queued":
        return None
    return 1 + sum(1 for other in JOBS.values()
                   if other.status == "queued" and other.created_at < job.created_at)


UPLOADS: Dict[str, Path] = {}
# fileId → sha256 of the uploaded bytes, so a re-upload of the same video maps to the same
# work dir and its cached transcription is reused instead of being redone.
UPLOAD_HASHES: Dict[str, str] = {}
JOBS: Dict[str, Job] = {}

# --------------------------------------------------------------------------- #
# Job history: each job is also a file, so the list outlives the server
# --------------------------------------------------------------------------- #

# A job's record keeps the end of its log, enough for its page to show what happened.
HISTORY_EVENTS = 2000
INTERRUPTED = ("Voxa Studio stopped before this dub finished. Dub the same video again with "
               "the same settings: the steps it had finished are reused.")


def _history_dir() -> Path:
    # A function, not a constant, so it follows WORKSPACE when that is moved (as in tests).
    return WORKSPACE / "history"


def _stored_path(path: Optional[Path]) -> Optional[str]:
    """Relative to the workspace when inside it, so the folder can be moved with its jobs."""
    if path is None:
        return None
    try:
        return Path(path).resolve().relative_to(WORKSPACE.resolve()).as_posix()
    except ValueError:
        return str(path)


def _loaded_path(value: Optional[str]) -> Optional[Path]:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else WORKSPACE / path


def save_job(job: Job) -> None:
    """Write the job's record (written whole, then swapped in, so a crash leaves the old
    one). A disk error is logged, never raised: it mustn't fail the dub itself."""
    record = {
        "version": 1,
        "id": job.id,
        "fileName": job.file_name,
        "sourceUrl": job.source_url,
        "config": job.config.model_dump(),
        "workDir": _stored_path(job.work_dir),
        "status": job.status,
        "step": job.step,
        "error": job.error,
        "resultVideo": _stored_path(job.result_video),
        "resultSrt": _stored_path(job.result_srt),
        "translationFile": _stored_path(job.translation_file),
        "createdAt": job.created_at,
        "startedAt": job.started_at,
        "finishedAt": job.finished_at,
        "cancelled": job.cancelled,
        "events": job.events[-HISTORY_EVENTS:],
    }
    folder = _history_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        temp = folder / f"{job.id}.json.tmp"
        temp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, folder / f"{job.id}.json")
    except OSError as e:
        print(f"⚠️  Couldn't save job {job.id} to the history: {e}", file=sys.stderr)


def load_history() -> int:
    """Put the jobs of earlier runs back in JOBS, oldest first, as the console lists them.
    One that was queued or running when the server stopped shows as interrupted. A record
    that can't be read is skipped. Returns how many came back."""
    folder = _history_dir()
    if not folder.is_dir():
        return 0
    records = []
    for path in folder.glob("*.json"):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    loaded = 0
    for rec in sorted(records, key=lambda r: r.get("createdAt") or 0):
        try:
            job = Job(id=rec["id"], file_name=rec["fileName"],
                      config=JobConfigModel(**rec["config"]),
                      work_dir=_loaded_path(rec["workDir"]), source_url=rec.get("sourceUrl"),
                      status=rec["status"], step=rec.get("step", 0),
                      events=list(rec.get("events") or []),
                      result_video=_loaded_path(rec.get("resultVideo")),
                      result_srt=_loaded_path(rec.get("resultSrt")),
                      error=rec.get("error"), created_at=rec.get("createdAt") or 0,
                      translation_file=_loaded_path(rec.get("translationFile")),
                      started_at=rec.get("startedAt"), finished_at=rec.get("finishedAt"),
                      cancelled=bool(rec.get("cancelled")))
        except (KeyError, TypeError, ValueError):
            continue
        if job.id in JOBS:
            continue
        if job.status in ("queued", "running"):
            job.status, job.error = "failed", INTERRUPTED
            job.events.append({"type": "status", "status": "failed", "error": INTERRUPTED})
            save_job(job)
        JOBS[job.id] = job
        loaded += 1
    return loaded


_PREVIEW_FILE = re.compile(r"\.preview\d+s_")


def _of_run(paths, preview: Optional[int]) -> list:
    """The files of one kind of run, in a work dir that can hold both: a preview's (voxa
    --preview) carry .preview<N>s in their name or their work dir's, the whole video's don't."""
    if preview:
        tag = f".preview{preview}s_"
        return [p for p in paths if tag in Path(p).as_posix()]
    return [p for p in paths if not _PREVIEW_FILE.search(Path(p).as_posix())]


def _translation_path(job: Job) -> Path:
    return job.work_dir / "translations" / f"{job.id}.json"


def keep_translation(job: Job) -> Optional[Path]:
    """Copy the lines the job's run translated (or was given) out of the video's work dir and
    keep them with the job, each with the source line it came from. Every dub of the same video
    shares that work dir and its translated.json, so a dub to another language replaces it;
    the job's own copy is what it is reviewed, changed and voiced from. Returns its path, or
    None when the run left no translation."""
    found = sorted(_of_run(job.work_dir.glob("*_work/translated.json"), job.config.preview),
                   key=lambda p: p.stat().st_mtime)
    lines = voxa._read_json_list(found[-1]) if found else None
    if not lines:
        return None
    merged = voxa._read_json_list(found[-1].with_name("merged_sentences.json")) or []
    source = {}
    for seg in merged:
        try:
            source[(round(float(seg["start"]), 3), round(float(seg["end"]), 3))] = \
                " ".join(str(seg.get("text", "")).split())
        except (KeyError, TypeError, ValueError):
            continue
    kept = []
    for line in lines:
        try:
            start, end = float(line["start"]), float(line["end"])
        except (KeyError, TypeError, ValueError):
            continue
        entry = {"start": start, "end": end, "text": str(line.get("text") or ""),
                 "source": source.get((round(start, 3), round(end, 3)), "")}
        if line.get("speaker") is not None:
            entry["speaker"] = line["speaker"]
        kept.append(entry)
    path = _translation_path(job)
    _write_lines(path, kept)
    job.translation_file = path
    return path


def _write_lines(path: Path, lines: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(lines, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temp, path)


def _video_work_dir(content_key: Optional[str]) -> Path:
    """Work dir for a source video, keyed by CONTENT. Re-dubbing the same video (to a new
    language or model) then reuses the cached audio/transcription via the engine's resume
    logic — the language-independent stages skip, only translation/synthesis rerun. Falls
    back to a random dir when the content hash is unknown (e.g. after a server restart)."""
    return JOBS_DIR / (content_key or uuid.uuid4().hex)[:16]


def error_from_log_line(line: str) -> Optional[str]:
    """The human-readable reason from a voxa log line, or None if it isn't an error. Used to
    report WHY a job failed instead of a bare exit code the operator must dig logs to explain."""
    if " - ERROR - " in line:
        return line.split(" - ERROR - ")[-1].strip() or None
    if line.lstrip().startswith("❌"):
        return line.strip() or None
    return None


async def _emit(job: Job, event: dict) -> None:
    job.events.append(event)
    for q in list(job.subscribers):
        q.put_nowait(event)


def max_concurrent_jobs(settings: Optional[dict] = None) -> int:
    """How many dubs may run at once (Settings → Advanced), clamped to a safe range.
    Each concurrent job is a separate process loading its own Whisper model, so the ceiling is
    low on purpose: concurrency pays off when the engines wait on the network (cloud
    translation and speech) and costs memory when they don't (local Whisper, Piper, XTTS)."""
    src = settings if settings is not None else read_settings()
    raw = (src.get("advanced") or {}).get("maxConcurrentJobs")
    if raw is None:
        return CONCURRENT_JOBS_DEFAULT
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        return CONCURRENT_JOBS_DEFAULT
    return max(CONCURRENT_JOBS_MIN, min(CONCURRENT_JOBS_MAX, limit))


def _workdir_lock(work_dir: Path) -> asyncio.Lock:
    """One lock per work dir, created on first use. Safe without a guard: the event loop is
    single-threaded and there is no await between the lookup and the insert."""
    key = str(work_dir)
    lock = _WORKDIR_LOCKS.get(key)
    if lock is None:
        lock = _WORKDIR_LOCKS[key] = asyncio.Lock()
    return lock


def _job_slots() -> asyncio.Condition:
    """Created on first use, inside the loop that runs the jobs. An asyncio primitive belongs to
    the first loop that uses it, and a queued job waiting on it from another loop fails with "is
    bound to a different event loop" — which is why the tests reset it for each loop they run."""
    global _JOB_SLOTS
    if _JOB_SLOTS is None:
        _JOB_SLOTS = asyncio.Condition()
    return _JOB_SLOTS


@asynccontextmanager
async def _job_gate(job: Job):
    """Admit a job to run. Its work dir must be free first — a second dub of the same video
    waits rather than racing on the shared resume state — and only then does it take one of
    the concurrency slots. Taking the work-dir lock first means a queued same-source job
    doesn't hold a slot that an unrelated video could be using."""
    global _running_jobs
    slots = _job_slots()
    async with _workdir_lock(job.work_dir):
        async with slots:
            await slots.wait_for(lambda: _running_jobs < max_concurrent_jobs())
            _running_jobs += 1
        try:
            yield
        finally:
            async with slots:
                _running_jobs -= 1
                slots.notify_all()


CANCELLED = "Stopped before it finished."
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def terminal_line(text: str) -> str:
    """A log line as a terminal would have left it. A progress bar (tqdm: Whisper's model
    download, Demucs) redraws itself on one line with carriage returns, so the pipe carries
    every state of it run together; only the last one means anything. Colour and cursor codes
    go too."""
    text = _ANSI.sub("", text)
    if "\r" not in text:
        return text
    states = [part for part in text.split("\r") if part.strip()]
    return states[-1] if states else ""


def kill_tree(pid: int, wait: float = 5.0) -> None:
    """End a process and every process under it: voxa, its ffmpeg, an engine's worker. On
    Windows taskkill does the whole tree; elsewhere the tree is read from ps (Linux and macOS
    both have it), and the processes are asked to end, then made to."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True,
                       timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return
    try:
        listing = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True,
                                 text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        listing = ""
    children: Dict[int, List[int]] = {}
    for row in listing.splitlines():
        parts = row.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            children.setdefault(int(parts[1]), []).append(int(parts[0]))
    tree, todo = [], [pid]
    while todo:
        current = todo.pop()
        tree.append(current)
        todo.extend(children.get(current, []))
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for each in tree:
            try:
                os.kill(each, sig)
            except (ProcessLookupError, PermissionError):
                pass
        deadline = time.time() + wait
        while sig == signal.SIGTERM and time.time() < deadline:
            if not any(_alive(each) for each in tree):
                return
            time.sleep(0.1)


def _alive(pid: int) -> bool:
    # Not waitpid: the voxa process is asyncio's child, and reaping it here would take its
    # exit status from asyncio. An ended child not reaped yet counts as alive a moment longer.
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _start_job(job: Job) -> None:
    """Run the job in the background, keeping its task so it can be stopped."""
    job.task = asyncio.create_task(_run_job(job))


async def _run_job(job: Job) -> None:
    """Run one dubbing job, as _run_steps says. Stopped from the console (POST /cancel), its
    voxa process and everything under it are ended and it is marked stopped; cancelled any
    other way (the server shutting down) the cancellation goes on, and the next start shows
    the dub interrupted."""
    try:
        await _run_steps(job)
    except asyncio.CancelledError:
        if not job.cancelled:
            raise
        proc = job.process
        if proc is not None and getattr(proc, "returncode", None) is None and \
                getattr(proc, "pid", None):
            await asyncio.to_thread(kill_tree, proc.pid)
            try:
                await asyncio.wait_for(proc.wait(), timeout=15)
            except (asyncio.TimeoutError, Exception):
                pass
        job.status, job.error, job.finished_at = "failed", CANCELLED, time.time()
        await _emit(job, {"type": "status", "status": "failed", "error": CANCELLED})
        save_job(job)
    finally:
        job.task = job.process = None


async def _run_steps(job: Job) -> None:
    """Run one dubbing job as a subprocess and stream its [N/7] progress."""
    async with _job_gate(job):
        job.status = "running"
        job.started_at, job.finished_at = time.time(), None
        await _emit(job, {"type": "status", "status": "running"})
        save_job(job)

        cfg = job.config
        # A URL is passed straight through: voxa downloads it into the run's cwd
        # (the work dir) before the pipeline. An uploaded file is a local name in work_dir.
        source_arg = job.source_url or job.file_name
        cmd = [
            sys.executable, voxa.__file__, source_arg,
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
        cmd += speech_style_args(cfg.tts, current_settings)
        cmd += translation_fallback_args(current_settings)
        cmd += advanced_timing_args(current_settings)
        if cfg.tts in voxa.CLONING_TTS and cfg.voiceSample:
            cmd += ["--voice-sample", _voice_path(cfg.voiceSample)]
        if cfg.tts == "edge" and cfg.edgeVoice:
            cmd += ["--edge-voice", cfg.edgeVoice]
        if cfg.tts == "openai":
            if cfg.openaiTtsModel:
                cmd += ["--openai-tts-model", cfg.openaiTtsModel]
            if cfg.openaiVoice:
                cmd += ["--openai-voice", cfg.openaiVoice]
        cmd += diarize_args(cfg)
        if cfg.diarize and cfg.speakerVoices:
            cloning = cfg.tts in voxa.CLONING_TTS
            cmd += ["--speaker-voices", ",".join(
                f"{speaker}={_voice_path(voice) if cloning else voice}"
                for speaker, voice in sorted(cfg.speakerVoices.items()))]
        if cfg.separate:
            cmd += ["--separate"]
        if cfg.preview:
            cmd += ["--preview", str(cfg.preview)]
        if cfg.subtitlesOnly:
            cmd += ["--subtitles-only"]
        if cfg.subtitlesInVideo:
            cmd += ["--subtitles-in-video", cfg.subtitlesInVideo]
        # Lines the job kept (reviewed, changed, or from an earlier run) are voiced as they
        # are; a job asked to be reviewed stops after translating the first time.
        given = job.translation_file if job.translation_file and \
            job.translation_file.exists() else None
        reviewing = cfg.review and given is None
        if given:
            cmd += ["--translation", str(given)]
        elif reviewing:
            cmd += ["--review"]

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
            job.finished_at = time.time()
            await _emit(job, {"type": "status", "status": "failed", "error": job.error})
            save_job(job)
            return
        job.process = proc

        assert proc.stdout is not None
        last_error = ""
        async for raw in proc.stdout:
            line = terminal_line(raw.decode("utf-8", errors="replace").rstrip())
            if not line.strip():
                continue
            # Remember the most recent error so a failed job can show WHY.
            reason = error_from_log_line(line)
            if reason:
                last_error = reason
            await _emit(job, {"type": "log", "line": line})
            match = STEP_RE.search(line)
            if match:
                n = int(match.group(1))
                done = ("✓" in line) or ("already completed" in line)
                job.step = n
                await _emit(job, {"type": "step", "step": n,
                                  "status": "done" if done else "running"})

        code = await proc.wait()
        if code == 0 and reviewing:
            if keep_translation(job):
                job.status = "review"
                await _emit(job, {"type": "status", "status": "review"})
            else:
                job.status = "failed"
                job.error = "The translation finished, but it left no lines to review."
                await _emit(job, {"type": "status", "status": "failed", "error": job.error})
        elif code == 0:
            # Kept, so the lines can be changed and voiced again after the dub is done.
            keep_translation(job)
            # Locate outputs by glob, not by name: a URL download lands under a
            # yt-dlp-chosen filename the server can't predict. The content-keyed work dir
            # holds one source video and outputs are language-suffixed, so each pattern
            # matches exactly one file for this target language.
            lang = cfg.targetLang
            made = "subtitled" if cfg.subtitlesOnly else "dubbed"
            videos = sorted(_of_run(job.work_dir.glob(f"*_{made}_{lang}.mp4"), cfg.preview),
                            key=lambda p: p.stat().st_mtime)
            # The captions, cut to read on screen; an older run left only one cue per line.
            srts = sorted(_of_run([*job.work_dir.glob(f"*_work/captions_{lang}.srt")]
                                  or job.work_dir.glob(f"*_work/subtitles_{lang}.srt"),
                                  cfg.preview),
                          key=lambda p: p.stat().st_mtime)
            job.result_video = videos[-1] if videos else None
            job.result_srt = srts[-1] if srts else None
            job.status = "done"
            await _emit(job, {"type": "status", "status": "done"})
        else:
            job.status = "failed"
            job.error = last_error or f"voxa exited with code {code}"
            await _emit(job, {"type": "status", "status": "failed", "error": job.error})
        job.finished_at = time.time()
        save_job(job)


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
        "translation": {"prompt": None, "fallback": None},
        "speech": {"instructions": None, "presets": []},
        "advanced": {"speechRate": None, "qualityGate": False, "ttsWorkers": None,
                     "maxConcurrentJobs": None, "autoDownload": False,
                     # Ask PyPI once a day whether a newer Voxa is out (voxa.latest_version).
                     "checkUpdates": True,
                     # Where the local models run (voxa --device); None is "auto".
                     "device": None},
    }


# Guardrail for the exposed speaking-rate knob (chars/sec). The engine default is 15; outside
# this band, dub timing degrades (too low over-condenses, too high rushes delivery).
SPEECH_RATE_MIN = 8.0
SPEECH_RATE_MAX = 30.0
TTS_WORKERS_MIN = 1
TTS_WORKERS_MAX = 16


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


# --------------------------------------------------------------------------- #
# Access: whom the server answers
# --------------------------------------------------------------------------- #

# The names a browser on this machine reaches the server by.
_LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1"}
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
TOKEN_COOKIE_DAYS = 30


@dataclass
class Access:
    """How the running server admits a request. Without a token it answers only requests
    addressed to this machine by name — a page that points its own domain at 127.0.0.1 (DNS
    rebinding) still sends that domain — and refuses changes another site sends. With one,
    every request but /api/health must carry it: as the cookie the ?token= link leaves, or
    as `Authorization: Bearer <token>`."""
    token: Optional[str] = None
    cookie: str = "voxa_token"


# Set by run_from_cli. None, as when tests import the app, checks nothing.
ACCESS: Optional[Access] = None


def _hostname(netloc: str) -> str:
    """The host of a Host header or an origin's netloc: lower-case, without port or brackets."""
    return urllib.parse.urlsplit("//" + netloc).hostname or ""


def is_loopback_bind(host: str) -> bool:
    return host in ("localhost", "::1") or host.startswith("127.")


def server_token(host: str, given: Optional[str], env: Optional[str]) -> Tuple[Optional[str], bool]:
    """The token the server asks for, and whether it was made up just now: the one given
    (--token, else VOXA_TOKEN); else, when it listens beyond loopback — where anyone who
    reaches the port could otherwise dub with your keys and download your dubs — a new one;
    else none."""
    if given or env:
        return given or env, False
    if is_loopback_bind(host):
        return None, False
    return secrets.token_urlsafe(24), True


def _same_token(offered: str, token: str) -> bool:
    return secrets.compare_digest(offered.encode(), token.encode())


def _carries_token(request: Request, access: Access) -> bool:
    offered = [request.cookies.get(access.cookie, "")]
    scheme, _, credentials = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer":
        offered.append(credentials.strip())
    return any(value and _same_token(value, access.token) for value in offered)


_GATE_TEXT = {
    "en": ("Voxa asks for its access token",
           "This server can be reached from beyond the computer it runs on, so it opens only "
           "for the token in the link <code>voxa serve</code> printed when it started, or the "
           "one you set with <code>VOXA_TOKEN</code>.",
           "Access token", "Open", "That isn't this server's token."),
    "az": ("Voxa giriş tokenini istəyir",
           "Bu serverə işlədiyi kompüterdən kənardan da çatmaq olur, ona görə yalnız "
           "<code>voxa serve</code> başlayanda yazdığı linkdəki tokenlə, ya da "
           "<code>VOXA_TOKEN</code> ilə özünüz təyin etdiyiniz tokenlə açılır.",
           "Giriş tokeni", "Aç", "Bu, bu serverin tokeni deyil."),
    "tr": ("Voxa erişim belirtecini istiyor",
           "Bu sunucuya çalıştığı bilgisayarın dışından da ulaşılabiliyor, bu yüzden yalnızca "
           "<code>voxa serve</code> başlarken yazdırdığı bağlantıdaki belirteçle ya da "
           "<code>VOXA_TOKEN</code> ile kendiniz belirlediğinizle açılıyor.",
           "Erişim belirteci", "Aç", "Bu, bu sunucunun belirteci değil."),
}


def gate_page(request: Request, wrong: bool) -> HTMLResponse:
    """The page a visitor without the token gets instead of the console: a field for it."""
    locale = console_locale(request.cookies.get("NEXT_LOCALE", ""),
                            request.headers.get("accept-language", ""))
    title, body, label, button, mismatch = _GATE_TEXT[locale]
    error = f'<p class="error">{mismatch}</p>' if wrong else ""
    page = f"""<!doctype html>
<html lang="{locale}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#0a0a0b;color:#e7e7ea;
font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;padding:16px;box-sizing:border-box}}
main{{max-width:28rem}} h1{{font-size:1.25rem;margin:0 0 .5rem}} p{{color:#a1a1aa;margin:0 0 1rem}}
code{{color:#e7e7ea}} label{{display:block;font-size:.875rem;margin-bottom:.25rem}}
input{{width:100%;box-sizing:border-box;padding:.6rem .75rem;border-radius:.5rem;
border:1px solid #3f3f46;background:#18181b;color:inherit;font:inherit}}
button{{margin-top:.75rem;padding:.55rem 1.1rem;border:0;border-radius:.5rem;background:#e7e7ea;
color:#0a0a0b;font:inherit;font-weight:600;cursor:pointer}} .error{{color:#f87171}}
</style></head>
<body><main><h1>{title}</h1><p>{body}</p>{error}
<form method="get"><label for="token">{label}</label>
<input id="token" name="token" type="password" autocomplete="off" required autofocus>
<button type="submit">{button}</button></form></main></body></html>"""
    return HTMLResponse(page, status_code=401)


def _is_https(request: Request) -> bool:
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return request.url.scheme == "https" or forwarded == "https"


def admission(request: Request, access: Access) -> Optional[Response]:
    """None to let the request through, else the response that turns it away."""
    host = request.headers.get("host", "")
    path = request.url.path
    if access.token is None:
        if _hostname(host) not in _LOOPBACK_NAMES:
            return JSONResponse(status_code=403, content={"detail": (
                "Voxa answers only to localhost and 127.0.0.1. To open it from another "
                "machine, or through a proxy, start it with --host 0.0.0.0 or --token, and it "
                "will ask for an access token.")})
        origin = request.headers.get("origin")
        if request.method in _UNSAFE_METHODS and origin is not None:
            netloc = urllib.parse.urlsplit(origin).netloc
            if netloc.lower() != host.lower() and _hostname(netloc) not in _LOOPBACK_NAMES:
                return JSONResponse(status_code=403, content={
                    "detail": "Voxa doesn't take changes another site sends."})
        return None
    # With a token, another site's request carries neither the SameSite=Strict cookie nor
    # (without passing CORS) the header, so the token alone settles it — and the Host can be
    # whatever a proxy in front says.
    if path == "/api/health":
        return None
    offered = request.query_params.get("token")
    if offered is not None and not path.startswith("/api/"):
        if not _same_token(offered, access.token):
            return gate_page(request, wrong=True)
        # Keep the token in a cookie the console's own calls carry, and out of the address.
        rest = [(k, v) for k, v in request.query_params.multi_items() if k != "token"]
        target = "/" + path.lstrip("/") + (f"?{urllib.parse.urlencode(rest)}" if rest else "")
        response = RedirectResponse(target, status_code=303)
        response.set_cookie(access.cookie, access.token, max_age=TOKEN_COOKIE_DAYS * 86400,
                            httponly=True, samesite="strict", secure=_is_https(request))
        return response
    if _carries_token(request, access):
        return None
    if path.startswith("/api/"):
        return JSONResponse(status_code=401, headers={"WWW-Authenticate": "Bearer"}, content={
            "detail": "This Voxa server asks for its access token: open the link voxa serve "
                      "printed when it started (it ends in ?token=…), or send "
                      "Authorization: Bearer <token>."})
    return gate_page(request, wrong=False)


_TOKEN_IN_QUERY = re.compile(r"([?&]token=)[^&\s]*")


class HideToken(logging.Filter):
    """uvicorn's access log writes each request's address, so opening the ?token= link would
    put the token in the log (and in `docker logs`); it gets [hidden] instead."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(_TOKEN_IN_QUERY.sub(r"\1[hidden]", arg) if isinstance(arg, str)
                                else arg for arg in record.args)
        return True


class AccessGuard:
    """ASGI middleware that puts every HTTP request through admission() first."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http" and ACCESS is not None:
            refusal = admission(Request(scope), ACCESS)
            if refusal is not None:
                await refusal(scope, receive, send)
                return
        await self.app(scope, receive, send)


def require_local(request: Request) -> None:
    """Reject any non-loopback caller. Defense in depth: the server binds 127.0.0.1 by
    default, but this still holds if it is ever started with --host 0.0.0.0. With a token,
    its holder — whom the access check alone lets this far — may change them from anywhere,
    as in a container, where no caller is loopback."""
    if ACCESS is not None and ACCESS.token is not None:
        return
    host = request.client.host if request.client else ""
    if host not in _LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail=(
            "Settings, keys and engines can be changed only from the machine Voxa runs on, "
            "or with the access token Voxa asks for when started with --host 0.0.0.0."))


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


def compile_speech_style(settings: dict) -> str:
    """Flatten the saved speech style (preset ids + free text) into one style phrase.
    Style only: voxa appends the locked timing guard, which this can never remove."""
    speech = settings.get("speech") or {}
    parts = [SPEECH_STYLE_PRESETS[p] for p in (speech.get("presets") or [])
             if p in SPEECH_STYLE_PRESETS]
    free = (speech.get("instructions") or "").strip()
    if free:
        parts.append(free)
    return "; ".join(parts).strip()


def speech_style_args(tts: str, settings: dict) -> List[str]:
    """CLI args carrying the operator's speech style (P3) to an OpenAI TTS job. Other
    engines don't take instructions, so returns [] for them."""
    if tts != "openai":
        return []
    style = compile_speech_style(settings)
    return ["--openai-tts-instructions", style] if style else []


def translation_fallback_args(settings: dict) -> List[str]:
    """CLI args carrying the operator's fallback translator (P4). The engine only uses it
    when the primary LLM translator substantially fails, so it's safe to always pass."""
    fb = (settings.get("translation") or {}).get("fallback")
    return ["--fallback-translator", fb] if fb else []


def diarize_args(cfg: JobConfigModel) -> List[str]:
    """CLI flags for a job's diarization choice (empty when off). An exact speaker count wins;
    otherwise an optional upper bound curbs over-splitting. The HF token flows to the child
    through the inherited environment, exactly like the OpenAI key does."""
    if not cfg.diarize:
        return []
    args = ["--diarize"]
    if cfg.numSpeakers:
        args += ["--num-speakers", str(cfg.numSpeakers)]
    elif cfg.maxSpeakers:
        args += ["--max-speakers", str(cfg.maxSpeakers)]
    return args


def advanced_timing_args(settings: dict) -> List[str]:
    """CLI args for the exposed advanced knobs (P4): the speaking rate (clamped to the
    guardrail band) and the quality gate, which also enables the neutral-retry of bad takes."""
    adv = settings.get("advanced") or {}
    args: List[str] = []
    rate = adv.get("speechRate")
    if rate is not None:
        clamped = max(SPEECH_RATE_MIN, min(SPEECH_RATE_MAX, float(rate)))
        args += ["--speech-rate", str(clamped)]
    if adv.get("qualityGate"):
        args += ["--quality-gate"]
    workers = adv.get("ttsWorkers")
    if workers is not None:
        clamped = max(TTS_WORKERS_MIN, min(TTS_WORKERS_MAX, int(workers)))
        args += ["--tts-workers", str(clamped)]
    if adv.get("device") in voxa.DEVICES and adv.get("device") != "auto":
        args += ["--device", adv["device"]]
    return args


def test_provider(pid: str) -> dict:
    """Connection test for one LLM provider: a cheap, no-token call that only checks the
    key is valid and the endpoint is reachable — models.list(), or for OpenRouter, whose
    model list is public, its key endpoint. The key goes to its own provider's host only.
    Never raises."""
    info = voxa.LLM_PROVIDERS.get(pid)
    if not info:
        return {"ok": False, "error": f"Unknown provider: {pid}"}
    if not os.environ.get(info["env_key"]):
        return {"ok": False, "error": "No API key set."}
    try:
        key = os.environ[info["env_key"]]
        client = (voxa.get_anthropic_client(key) if pid == "anthropic"
                  else voxa.get_openai_client(key, info.get("base_url")))
        if client is None:
            return {"ok": False, "error": "Client unavailable (provider package missing?)."}
        started = time.perf_counter()
        if pid == "openrouter":
            client.get("/key", cast_to=object)
        else:
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
# Added last, so it runs first: nothing reaches a route, or the console, before admission().
app.add_middleware(AccessGuard)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "version": app.version}


def checks_updates() -> bool:
    """Settings → Check for updates; VOXA_NO_UPDATE_CHECK turns it off as well."""
    advanced = read_settings().get("advanced")
    return not isinstance(advanced, dict) or advanced.get("checkUpdates", True) is not False


@app.get("/api/update")
async def update() -> dict:
    """Is a newer Voxa out, and how does this install get it. PyPI is asked at most once a
    day, in a worker thread, so a slow network never holds up the console."""
    return await asyncio.to_thread(voxa.update_status, checks_updates())


def _say_if_newer() -> None:
    status = voxa.update_status(checks_updates())
    if status["newer"]:
        print(f"⬆️  Voxa {status['latest']} is out (this is {status['current']}): "
              f"{status['command'] or status['download']}", flush=True)


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
        tr = data["translation"] or {}
        prompt = tr.get("prompt")
        if prompt is not None and len(str(prompt)) > 4000:
            raise HTTPException(status_code=422,
                                detail="Translation style guidance is too long (max 4000 chars).")
        fb = tr.get("fallback")
        if fb is not None and fb not in valid_translators():
            raise HTTPException(status_code=422, detail=f"Unknown fallback translator: {fb}")
    if "advanced" in data:
        if not isinstance((data["advanced"] or {}).get("checkUpdates", True), bool):
            raise HTTPException(status_code=422, detail="checkUpdates must be true or false.")
        if (data["advanced"] or {}).get("device") not in (None, *voxa.DEVICES):
            raise HTTPException(status_code=422,
                                detail=f"device must be one of {', '.join(voxa.DEVICES)}.")
        rate = (data["advanced"] or {}).get("speechRate")
        if rate is not None:
            try:
                rate = float(rate)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail="speechRate must be a number.")
            if not (SPEECH_RATE_MIN <= rate <= SPEECH_RATE_MAX):
                raise HTTPException(
                    status_code=422,
                    detail=f"speechRate must be between {SPEECH_RATE_MIN} and {SPEECH_RATE_MAX}.")
        workers = (data["advanced"] or {}).get("ttsWorkers")
        if workers is not None:
            try:
                workers = int(workers)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail="ttsWorkers must be an integer.")
            if not (TTS_WORKERS_MIN <= workers <= TTS_WORKERS_MAX):
                raise HTTPException(
                    status_code=422,
                    detail=f"ttsWorkers must be between {TTS_WORKERS_MIN} and {TTS_WORKERS_MAX}.")
        concurrent = (data["advanced"] or {}).get("maxConcurrentJobs")
        if concurrent is not None:
            try:
                concurrent = int(concurrent)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422,
                                    detail="maxConcurrentJobs must be an integer.")
            if not (CONCURRENT_JOBS_MIN <= concurrent <= CONCURRENT_JOBS_MAX):
                raise HTTPException(
                    status_code=422,
                    detail=(f"maxConcurrentJobs must be between {CONCURRENT_JOBS_MIN} "
                            f"and {CONCURRENT_JOBS_MAX}."))
    if "speech" in data:
        speech = data["speech"] or {}
        presets = speech.get("presets")
        if presets is not None:
            if not isinstance(presets, list):
                raise HTTPException(status_code=422, detail="speech.presets must be a list.")
            for pid in presets:
                if pid not in SPEECH_STYLE_PRESETS:
                    raise HTTPException(status_code=422,
                                        detail=f"Unknown speech preset: {pid}")
        instr = speech.get("instructions")
        if instr is not None and len(str(instr)) > 2000:
            raise HTTPException(status_code=422,
                                detail="Speech style text is too long (max 2000 chars).")
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
    hasher = hashlib.sha256()
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            out.write(chunk)
            hasher.update(chunk)
    UPLOADS[file_id] = dest
    UPLOAD_HASHES[file_id] = hasher.hexdigest()
    return {"fileId": file_id, "fileName": file.filename, "size": size}


def _job_engines(cfg) -> List[str]:
    """The engines Voxa installs separately that a job runs with."""
    if getattr(cfg, "subtitlesOnly", False):
        return []                       # no speech, and nothing to separate it from
    engines = [cfg.tts] if cfg.tts in voxa_engines.ENGINES else []
    return engines + (["demucs"] if getattr(cfg, "separate", False) else [])


def engine_problem(cfg: JobConfigModel) -> Optional[str]:
    """Why a job can't run yet: it needs an engine Voxa installs separately that isn't."""
    for engine_id in _job_engines(cfg):
        if not voxa_engines.is_installed(engine_id):
            label = voxa_engines.get(engine_id).label
            return (f"{label} isn't installed. Install it under Models, or run: "
                    f"voxa engines install {engine_id}")
    return None


# --------------------------------------------------------------------------- #
# Voices: what each engine offers, and the library of clips voices are cloned from
# --------------------------------------------------------------------------- #

VOICE_CLIP_SECONDS = (3.0, 30.0)     # shorter can't be cloned well; longer is cut
_LIBRARY_ID = re.compile(r"[0-9a-f]{12}")


def _voices_dir() -> Path:
    # A function, not a constant, so it follows WORKSPACE when that is moved (as in tests).
    return WORKSPACE / "voices"


def voice_library() -> list:
    """The clips kept to clone voices from, newest first."""
    entries = voxa._read_json_list(_voices_dir() / "library.json") or []
    return sorted((e for e in entries if isinstance(e, dict) and _library_clip(e.get("id"))),
                  key=lambda e: e.get("createdAt") or 0, reverse=True)


def _save_library(entries: list) -> None:
    _voices_dir().mkdir(parents=True, exist_ok=True)
    temp = _voices_dir() / "library.json.tmp"
    temp.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temp, _voices_dir() / "library.json")


def _library_clip(voice_id) -> Optional[Path]:
    if not isinstance(voice_id, str) or not _LIBRARY_ID.fullmatch(voice_id):
        return None
    clip = _voices_dir() / f"{voice_id}.wav"
    return clip if clip.exists() else None


def _voice_path(value: Optional[str]) -> Optional[str]:
    """A voice a job names for a cloning engine: a clip of the library, by its id, becomes its
    file; anything else (a path, as the console took before the library) passes as it is."""
    clip = _library_clip(value)
    return str(clip) if clip else value


@app.get("/api/voices")
async def list_voices(engine: str, lang: str = "en") -> dict:
    """The voices to choose from for one engine and language, and whether they can be heard
    first (POST /api/voices/listen)."""
    if engine == "openai":
        return {"voices": [{"id": v, "label": v} for v in OPENAI_VOICES], "listen": False}
    if engine in voxa.CLONING_TTS:
        return {"voices": [{"id": e["id"], "label": e["name"], "seconds": e.get("seconds")}
                           for e in voice_library()], "listen": False, "library": True}
    try:
        found = await voxa.voice_catalogue(engine, lang)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Couldn't get {engine}'s voices: {e}")
    return {"voices": found, "listen": engine in ("edge", "piper")}


@app.get("/api/voices/library")
async def get_voice_library() -> dict:
    return {"voices": voice_library()}


@app.post("/api/voices/library")
async def add_voice(file: UploadFile = File(...), name: str = Form("")) -> dict:
    """Keep a clip to clone a voice from: any audio or video, made mono 24 kHz WAV and cut to
    its first 30 seconds."""
    voice_id = uuid.uuid4().hex[:12]
    folder = _voices_dir()
    folder.mkdir(parents=True, exist_ok=True)
    upload, clip = folder / f"{voice_id}.upload", folder / f"{voice_id}.wav"
    with upload.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)
    low, high = VOICE_CLIP_SECONDS
    try:
        made = await asyncio.to_thread(
            subprocess.run, ["ffmpeg", "-y", "-i", str(upload), "-t", str(high), "-vn",
                             "-ac", "1", "-ar", "24000", str(clip)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        upload.unlink(missing_ok=True)
    seconds = voxa.probe_duration(clip) if made.returncode == 0 and clip.exists() else None
    if not seconds or seconds < low:
        clip.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=(
            f"A voice to clone needs at least {low:g} seconds of speech." if seconds
            else "That file has no audio Voxa can read."))
    entry = {"id": voice_id,
             "name": " ".join(name.split())[:60] or Path(file.filename or "voice").stem[:60],
             "seconds": round(seconds, 1), "createdAt": time.time()}
    _save_library(voice_library() + [entry])
    return entry


@app.delete("/api/voices/library/{voice_id}")
async def delete_voice(voice_id: str) -> dict:
    clip = _library_clip(voice_id)
    if not clip:
        raise HTTPException(status_code=404, detail="No such voice.")
    _save_library([e for e in voice_library() if e.get("id") != voice_id])
    clip.unlink(missing_ok=True)
    return {"voices": voice_library()}


@app.get("/api/voices/library/{voice_id}/audio")
async def voice_audio(voice_id: str) -> FileResponse:
    clip = _library_clip(voice_id)
    if not clip:
        raise HTTPException(status_code=404, detail="No such voice.")
    return FileResponse(str(clip), media_type="audio/wav")


class ListenBody(BaseModel):
    engine: str
    voice: str
    lang: str = "en"
    # What to say: a line of the dub, say; a short greeting in the language otherwise.
    text: Optional[str] = None


@app.post("/api/voices/listen")
async def listen(body: ListenBody) -> FileResponse:
    """One voice saying a short line, to hear it before choosing it (Edge and Piper). Kept,
    so hearing it again is instant."""
    if body.engine not in ("edge", "piper"):
        raise HTTPException(status_code=422,
                            detail=f"{body.engine} voices can't be heard before a dub.")
    line = body.text or voxa.SAMPLE_LINES.get(body.lang[:2].lower(), voxa.SAMPLE_LINES["en"])
    text = " ".join(line.split())[:300]
    if not text:
        raise HTTPException(status_code=422, detail="Nothing to say.")
    key = hashlib.sha256(f"{body.engine}|{body.voice}|{text}".encode("utf-8")).hexdigest()[:24]
    out = _voices_dir() / "samples" / f"{key}{'.mp3' if body.engine == 'edge' else '.wav'}"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            await voxa.speak_sample(body.engine, body.voice, text, out)
        except Exception as e:
            out.unlink(missing_ok=True)
            raise HTTPException(status_code=502, detail=f"{body.voice} couldn't be heard: {e}")
    return FileResponse(str(out), media_type="audio/mpeg" if out.suffix == ".mp3"
                        else "audio/wav")


def _check_preview(config: JobConfigModel) -> None:
    low, high = voxa.PREVIEW_RANGE
    if config.preview is not None and not low <= config.preview <= high:
        raise HTTPException(status_code=422,
                            detail=f"A preview is {low} to {high} seconds long.")


@app.post("/api/jobs")
async def create_job(body: CreateJobModel) -> dict:
    problem = engine_problem(body.config)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    _check_preview(body.config)
    job_id = uuid.uuid4().hex[:12]
    # Content-keyed work dir: a second dub of the same source reuses its cached transcription.
    # The single job lock serialises runs and outputs are language-suffixed, so jobs sharing
    # a dir never collide.
    if body.sourceUrl:
        url = body.sourceUrl.strip()
        if not voxa._looks_like_url(url):
            raise HTTPException(status_code=400, detail="sourceUrl must be an http(s) URL")
        if not voxa._ytdlp_available():
            raise HTTPException(status_code=400, detail=voxa._YTDLP_HINT)
        # Key the work dir by the URL so re-dubbing it reuses the download + transcription.
        content_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        work_dir = _video_work_dir(content_key)
        work_dir.mkdir(parents=True, exist_ok=True)
        job = Job(id=job_id, file_name=url, config=body.config,
                  work_dir=work_dir, source_url=url)
    elif body.fileId:
        src = UPLOADS.get(body.fileId)
        if not src or not src.exists():
            raise HTTPException(status_code=404, detail="Uploaded file not found")
        work_dir = _video_work_dir(UPLOAD_HASHES.get(body.fileId))
        work_dir.mkdir(parents=True, exist_ok=True)
        file_name = _safe_name(Path(src.name).name.split("_", 1)[-1])
        dest_video = work_dir / file_name
        if not dest_video.exists() or dest_video.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dest_video)
        job = Job(id=job_id, file_name=file_name, config=body.config, work_dir=work_dir)
    else:
        raise HTTPException(status_code=400, detail="Provide either fileId or sourceUrl")

    JOBS[job_id] = job
    save_job(job)
    _start_job(job)
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
            # Replay history so a late subscriber catches up, then stream live. A job voiced
            # again starts a new run with "queued": only that run is replayed, or the end of
            # the last one would close the stream before the new one is heard.
            events = list(job.events)
            starts = [i for i, e in enumerate(events)
                      if e.get("type") == "status" and e.get("status") == "queued"]
            for event in events[starts[-1] if starts else 0:]:
                yield f"data: {json.dumps(event)}\n\n"
            if job.status in JOB_AT_REST:
                return
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "status" and event.get("status") in JOB_AT_REST:
                    return
        finally:
            job.subscribers.discard(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# A job in one of these isn't running: its lines can be read, changed and voiced again.
JOB_AT_REST = ("review", "done", "failed")
LINE_MAX_CHARS = 2000


class TranslationEdit(BaseModel):
    # One text per line, in order; only the words change, never the timing.
    texts: List[str]


def _job_or_404(job_id: str) -> Job:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _kept_lines(job: Job) -> list:
    lines = voxa._read_json_list(job.translation_file) if job.translation_file else None
    if not lines:
        raise HTTPException(status_code=404, detail="This job has no translated lines yet.")
    return lines


def _translation_view(job: Job, lines: list) -> dict:
    """The lines with the length each can take: about what the speaking rate fits into its
    time (Settings → Advanced). A longer line is sped up, then trimmed, to fit."""
    rate = (read_settings().get("advanced") or {}).get("speechRate") or \
        voxa.DEFAULT_SPEECH_RATE_CPS
    return {
        "editable": job.status in JOB_AT_REST,
        "lines": [{"start": line["start"], "end": line["end"], "text": line.get("text", ""),
                   "source": line.get("source", ""), "speaker": line.get("speaker"),
                   "maxChars": voxa._duration_to_max_chars(
                       max(0.0, float(line["end"]) - float(line["start"])), float(rate))}
                  for line in lines],
    }


@app.get("/api/jobs/{job_id}/translation")
async def get_translation(job_id: str) -> dict:
    job = _job_or_404(job_id)
    return _translation_view(job, _kept_lines(job))


@app.put("/api/jobs/{job_id}/translation")
async def put_translation(job_id: str, body: TranslationEdit) -> dict:
    job = _job_or_404(job_id)
    if job.status not in JOB_AT_REST:
        raise HTTPException(status_code=409,
                            detail="The lines can be changed once this run of the job ends.")
    lines = _kept_lines(job)
    if len(body.texts) != len(lines):
        raise HTTPException(status_code=422,
                            detail=f"Send one text for each of the {len(lines)} lines.")
    if any(len(text) > LINE_MAX_CHARS for text in body.texts):
        raise HTTPException(status_code=422,
                            detail=f"A line can hold at most {LINE_MAX_CHARS} characters.")
    texts = [" ".join(text.split()) for text in body.texts]
    if not any(texts):
        raise HTTPException(status_code=422, detail="At least one line needs something to say.")
    for line, text in zip(lines, texts):
        line["text"] = text
    _write_lines(job.translation_file, lines)
    return _translation_view(job, lines)


class JobVoices(BaseModel):
    # The job's own voice for its engine: an Edge or OpenAI voice, or a library clip for a
    # cloning engine; None lets Voxa choose (or cut one from the video).
    voice: Optional[str] = None
    # A voice per speaker, for a diarized job.
    speakers: Dict[str, str] = {}


@app.put("/api/jobs/{job_id}/voices")
async def put_job_voices(job_id: str, body: JobVoices) -> dict:
    """Choose the voices a job speaks with, before it is voiced (after a review) or to voice it
    again: its lines are kept, so only the speech is made again."""
    job = _job_or_404(job_id)
    if job.status not in JOB_AT_REST:
        raise HTTPException(status_code=409,
                            detail="The voices can be changed once this run of the job ends.")
    voice = (body.voice or "").strip() or None
    speakers = {k.strip(): v.strip() for k, v in body.speakers.items() if k.strip() and v.strip()}
    named = [voice or ""] + list(speakers) + list(speakers.values())
    if any(len(x) > 300 or "," in x or "=" in x for x in named):
        raise HTTPException(status_code=422, detail="A voice's name can't hold , or =.")
    field = {"edge": "edgeVoice", "openai": "openaiVoice"}.get(
        job.config.tts, "voiceSample" if job.config.tts in voxa.CLONING_TTS else None)
    update = {"speakerVoices": speakers or None}
    if field:
        update[field] = voice
    job.config = job.config.model_copy(update=update)
    save_job(job)
    return job.summary()


@app.post("/api/jobs/{job_id}/full")
async def dub_whole_video(job_id: str) -> dict:
    """A new job that dubs the whole video a preview was cut from, with the preview's
    settings. Its own transcription runs on the whole video; the preview's files stay."""
    job = _job_or_404(job_id)
    if not job.config.preview:
        raise HTTPException(status_code=409, detail="This job already dubs the whole video.")
    if not job.source_url and not (job.work_dir / job.file_name).exists():
        raise HTTPException(status_code=404, detail="The video isn't in its folder any more.")
    config = job.config.model_copy(update={"preview": None})
    problem = engine_problem(config)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    whole = Job(id=uuid.uuid4().hex[:12], file_name=job.file_name, config=config,
                work_dir=job.work_dir, source_url=job.source_url)
    JOBS[whole.id] = whole
    save_job(whole)
    _start_job(whole)
    return {"jobId": whole.id}


@app.post("/api/jobs/{job_id}/voice")
async def voice_job(job_id: str) -> dict:
    """Voice the job's lines as they are now: after a review, or again after changing some
    (only the changed lines are voiced again)."""
    job = _job_or_404(job_id)
    if job.status not in JOB_AT_REST:
        raise HTTPException(status_code=409, detail="This job is already running.")
    _kept_lines(job)
    job.status, job.error, job.step = "queued", None, 0
    job.started_at = job.finished_at = None
    job.cancelled = False
    await _emit(job, {"type": "status", "status": "queued"})
    save_job(job)
    _start_job(job)
    return job.summary()


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict:
    """Stop a dub that is queued or running. Its voxa process ends with everything it started
    (ffmpeg, an engine's worker), and the dub shows as stopped. What it finished stays in the
    video's work dir, so dubbing the same video again picks up from there."""
    job = _job_or_404(job_id)
    if job.status not in ("queued", "running"):
        raise HTTPException(status_code=409,
                            detail="This dub isn't going, so there's nothing to stop.")
    job.cancelled = True
    task = job.task
    if task is not None and not task.done():
        task.cancel()
        await asyncio.wait({task}, timeout=60)
    else:                       # a job without a run in this server: just say it's stopped
        job.status, job.error, job.finished_at = "failed", CANCELLED, time.time()
        await _emit(job, {"type": "status", "status": "failed", "error": CANCELLED})
        save_job(job)
    return job.summary()


def _same_file(a: Optional[Path], b: Optional[Path]) -> bool:
    try:
        return bool(a and b and a.resolve() == b.resolve())
    except OSError:
        return False


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str, files: bool = False) -> dict:
    """Take a dub off the list: its record and the lines it kept go. With files=true its video
    and subtitles go too, unless another dub on the list made the same files (the same video
    into the same language again). The video's work dir stays: other dubs of it reuse what it
    holds, its transcription first."""
    job = _job_or_404(job_id)
    if job.status in ("queued", "running"):
        raise HTTPException(status_code=409, detail="Stop the dub before removing it.")
    removed = []
    if files:
        others = [j for j in JOBS.values() if j is not job]
        for path in (job.result_video, job.result_srt):
            if not path or not path.exists() or any(
                    _same_file(path, o.result_video) or _same_file(path, o.result_srt)
                    for o in others):
                continue
            try:
                path.unlink()
                removed.append(path.name)
            except OSError:
                pass
    for path in (job.translation_file, _history_dir() / f"{job.id}.json"):
        try:
            if path:
                path.unlink(missing_ok=True)
        except OSError:
            pass
    JOBS.pop(job_id, None)
    return {"deleted": job_id, "removedFiles": removed}


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


@app.get("/api/jobs/{job_id}/result/vtt")
async def result_vtt(job_id: str) -> Response:
    """The subtitles as WebVTT, which a browser's video player shows (it doesn't read SRT)."""
    job = _job_or_404(job_id)
    if not job.result_srt or not job.result_srt.exists():
        raise HTTPException(status_code=404, detail="Result not ready")
    srt = job.result_srt.read_text(encoding="utf-8-sig")
    vtt = re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", srt.replace("\r\n", "\n"))
    return Response("WEBVTT\n\n" + vtt, media_type="text/vtt; charset=utf-8")


# --------------------------------------------------------------------------- #
# Engines installed into environments of their own (see voxa_engines)
# --------------------------------------------------------------------------- #

# Installs started from the console: engine id -> {"status", "log", "error"}. An install
# runs in a thread, since it downloads for minutes; the console polls the engine's status.
ENGINE_INSTALLS: Dict[str, dict] = {}


def _install_state(engine_id: str) -> dict:
    state = ENGINE_INSTALLS.get(engine_id)
    if state is None:
        return {"status": "idle", "log": [], "error": None}
    return {"status": state["status"], "log": list(state["log"])[-40:], "error": state["error"]}


def _engine_status(engine_id: str) -> dict:
    try:
        return {**voxa_engines.status(engine_id), "install": _install_state(engine_id)}
    except voxa_engines.EngineError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/engines")
async def list_engines() -> dict:
    return {"engines": [_engine_status(e) for e in sorted(voxa_engines.ENGINES)],
            "dir": str(voxa_engines.engines_dir())}


@app.get("/api/engines/{engine_id}")
async def get_engine(engine_id: str) -> dict:
    return _engine_status(engine_id)


@app.post("/api/engines/{engine_id}/install")
async def install_engine(engine_id: str, _: None = Depends(require_local)) -> dict:
    _engine_status(engine_id)                        # 404 for an unknown engine
    if ENGINE_INSTALLS.get(engine_id, {}).get("status") == "installing":
        raise HTTPException(status_code=409, detail="It is already being installed.")
    state = {"status": "installing", "log": deque(maxlen=400), "error": None}
    ENGINE_INSTALLS[engine_id] = state

    def _install() -> None:
        try:
            voxa_engines.install(engine_id, log=state["log"].append)
            state["status"] = "done"
        except Exception as e:                       # shown in the console, not lost
            state["status"], state["error"] = "failed", str(e)

    threading.Thread(target=_install, daemon=True).start()
    return _engine_status(engine_id)


@app.delete("/api/engines/{engine_id}")
async def remove_engine(engine_id: str, _: None = Depends(require_local)) -> dict:
    _engine_status(engine_id)
    if ENGINE_INSTALLS.get(engine_id, {}).get("status") == "installing":
        raise HTTPException(status_code=409, detail="Wait for the install to finish first.")
    if any(engine_id in _job_engines(job.config) and job.status in ("queued", "running")
           for job in JOBS.values()):
        raise HTTPException(status_code=409, detail="A dub is using it; remove it afterwards.")
    try:
        voxa_engines.remove(engine_id)
    except voxa_engines.EngineError as e:
        raise HTTPException(status_code=409, detail=str(e))
    ENGINE_INSTALLS.pop(engine_id, None)
    return _engine_status(engine_id)


# --------------------------------------------------------------------------- #
# Console (the operator UI, bundled into the package)
# --------------------------------------------------------------------------- #

CONSOLE_LOCALES = ("en", "az", "tr")


def console_locale(cookie: str, accept_language: str) -> str:
    """The console language for a visitor: the one they picked before (next-intl's
    NEXT_LOCALE cookie), else the first of their browser's languages the console has,
    else English."""
    if cookie in CONSOLE_LOCALES:
        return cookie
    for tag in accept_language.split(","):
        primary = tag.split(";")[0].strip().split("-")[0].lower()
        if primary in CONSOLE_LOCALES:
            return primary
    return CONSOLE_LOCALES[0]


# Next's static build writes a page's prefetch payloads as nested files
# (`__next.$d$locale/app/jobs.txt`), while the browser asks for them with the segments
# joined by dots (`__next.$d$locale.app.jobs.txt`); Next's own server maps one to the other.
_SEGMENT_PAYLOAD = re.compile(r"__next\.([^/\\]+)\.txt")


def segment_payload_path(path: str) -> Optional[str]:
    """The nested file a dot-joined prefetch payload request refers to, or None when `path`
    isn't one (a single segment, like `__next._tree.txt`, is a file of that name)."""
    head, name = os.path.split(path)
    match = _SEGMENT_PAYLOAD.fullmatch(name)
    if not match or "." not in match.group(1):
        return None
    first, *rest = match.group(1).split(".")
    return os.path.join(head, f"__next.{first}", *rest[:-1], f"{rest[-1]}.txt")


class ConsoleFiles(StaticFiles):
    """Serves the bundled console. The static build has no page at the bare root, so "/"
    redirects to the console in the visitor's language."""

    async def get_response(self, path: str, scope) -> Response:
        if path in ("", "."):
            request = Request(scope)
            locale = console_locale(request.cookies.get("NEXT_LOCALE", ""),
                                    request.headers.get("accept-language", ""))
            return RedirectResponse(f"/{locale}/app/")
        nested = segment_payload_path(path)
        if nested is not None and self.lookup_path(nested)[1] is not None:
            path = nested
        return await super().get_response(path, scope)


def mount_console(target: FastAPI, directory: Optional[Path]) -> bool:
    """Serve the console from `directory` under "/". Mounted after the API routes, so
    /api/... still reaches them. False, with nothing mounted, when there is no build."""
    if directory is None:
        return False
    target.mount("/", ConsoleFiles(directory=directory, html=True), name="console")
    return True


try:
    from voxa_ui import static_dir as _console_dir
except ImportError:                      # installed without the console package
    def _console_dir() -> Optional[Path]:
        return None

CONSOLE_BUNDLED = mount_console(app, _console_dir())


def _exit_with_studio() -> None:
    """Started by Voxa Studio on macOS or Linux, end when its window's process does, even if
    that one crashes: the server leads a process group of its own there, so the dubs it
    started end too. (On Windows a job object does this.)"""
    parent = os.environ.get("VOXA_STUDIO_PARENT", "")
    if os.name == "nt" or not parent.isdigit():
        return

    def _watch() -> None:
        while os.getppid() == int(parent):
            time.sleep(2)
        if os.getpgrp() == os.getpid():
            os.killpg(os.getpgrp(), signal.SIGTERM)
        else:
            os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=_watch, daemon=True).start()


def _open_when_ready(url: str, token: Optional[str] = None, timeout: float = 30.0) -> None:
    """Open the console in the browser once the server answers, from a background thread
    so it doesn't hold up the server start."""
    entry = f"{url}/?token={urllib.parse.quote(token)}" if token else f"{url}/"

    def _wait_then_open() -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"{url}/api/health", timeout=2)
                webbrowser.open(entry)
                return
            except OSError:
                time.sleep(0.3)
    threading.Thread(target=_wait_then_open, daemon=True).start()


# --------------------------------------------------------------------------- #
# CLI entry (called by `voxa serve` and `voxa studio` in voxa.cli)
# --------------------------------------------------------------------------- #

def run_from_cli(argv: List[str], prog: str = "voxa serve") -> int:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Run the Voxa operator web server (upload, dub, download).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--env-file", default=".env",
                        help="Load API keys from this .env file (default: .env)")
    parser.add_argument("--token", default=None,
                        help="The access token the console and API ask for (default: "
                             "VOXA_TOKEN; with neither, a new one whenever --host isn't "
                             "loopback, printed in the link to open)")
    parser.add_argument("--open", action="store_true",
                        help="Open the console in the browser once the server is up "
                             "(`voxa studio` does this)")
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
              "   Install them with:  pip install \"voxa-dub[serve]\"")
        return 1

    # After the .env load, so a VOXA_TOKEN kept there counts. Cookies don't tell ports apart,
    # so each port gets its own, and two servers on one machine don't trade tokens.
    global ACCESS
    token, made_up = server_token(args.host, args.token, os.environ.get("VOXA_TOKEN"))
    ACCESS = Access(token=token, cookie=f"voxa_token_{args.port}")

    WORKSPACE.mkdir(parents=True, exist_ok=True)
    earlier = load_history()
    _exit_with_studio()
    detected = [k for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY") if os.environ.get(k)]
    # A wildcard bind is reachable on loopback; the browser can't open 0.0.0.0 itself.
    local = "127.0.0.1" if args.host in ("0.0.0.0", "::", "") else args.host
    url = f"http://{local}:{args.port}"
    print(f"🌐 Voxa operator server → http://{args.host}:{args.port}")
    print(f"🔑 API keys detected: {', '.join(detected) if detected else 'none'}")
    if earlier:
        print(f"📜 {earlier} earlier dub{'s' if earlier != 1 else ''} in {_history_dir()}")
    threading.Thread(target=_say_if_newer, name="voxa-update-check", daemon=True).start()
    if made_up:
        print("🔐 It listens beyond this machine, so the console and the API ask for this "
              f"access token (set your own with --token or VOXA_TOKEN):\n   {token}")
    elif token:
        print("🔐 The console and the API ask for the access token you set.")
    if CONSOLE_BUNDLED:
        entry = f"{url}/?token={urllib.parse.quote(token)}" if made_up else f"{url}/"
        print(f"🖥️  Console → {entry}")
        if args.open:
            _open_when_ready(url, token)
    else:
        print("   This install has no built console. Run it from web/ (npm run dev) and point it\n"
              "   at this address, or build it into the package with: npm run build:console")
    # uvicorn's logging setup keeps a logger's filters, so this one outlasts it.
    logging.getLogger("uvicorn.access").addFilter(HideToken())
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0
