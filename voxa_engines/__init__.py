"""Engines Voxa installs into environments of their own.

Some engines pin their dependencies hard — Chatterbox wants torch 2.6 and
transformers 5.2, XTTS an older transformers — so they can't share an environment with
each other or with Voxa. Each engine listed in ENGINES gets its own virtual environment
under ~/.voxa/engines/<id>/ (VOXA_ENGINES_DIR moves it), made with uv when it's available,
which also fetches the Python version the engine needs, and with venv and pip otherwise.

Voxa talks to an engine through a worker script (workers/) that runs in that environment
and answers one JSON request per line on stdin/stdout, so the model loads once per run and
nothing of the engine is imported into Voxa. Removing an engine deletes its folder.

This module imports nothing heavy, so `voxa engines` and the console can list and install
engines without loading torch.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

WORKERS_DIR = Path(__file__).parent / "workers"


class EngineError(RuntimeError):
    """An engine can't be installed, found or run; the message says what to do."""


@dataclass(frozen=True)
class Engine:
    id: str
    label: str
    kind: str                       # what it does in the pipeline: "tts" or "separation"
    description: str
    licence: str                    # the model weights' licence, as the model card gives it
    # What that licence allows commercially, in the terms of voxa.PIPER_LICENCE_USE:
    # "yes", "credit" (with attribution), "no" or "unknown".
    commercial: str
    languages: Tuple[str, ...]      # ISO 639-1 codes it speaks; () when any will do
    cloning: bool                   # clones a voice from a reference recording
    python: str                     # the Python version its environment is made with
    packages: Tuple[str, ...]       # what goes into that environment
    # Its script in workers/. Not named after the engine's package: Python puts the
    # script's folder first on sys.path, so a chatterbox.py would import itself.
    worker: str
    download_gb: float              # roughly what an install downloads: packages, then weights
    homepage: str
    notice: str = ""                # what else to know before using it


ENGINES: Dict[str, Engine] = {
    "chatterbox": Engine(
        id="chatterbox",
        label="Chatterbox Multilingual",
        kind="tts",
        description="Clones each speaker's voice from the original video, in 23 languages.",
        licence="MIT",
        commercial="yes",
        languages=("ar", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "it", "ja",
                   "ko", "ms", "nl", "no", "pl", "pt", "ru", "sv", "sw", "tr", "zh"),
        cloning=True,
        python="3.11",
        # Its watermarker (resemble-perth) imports pkg_resources, which a uv environment
        # doesn't have and setuptools 80 stopped shipping; without it Chatterbox won't load.
        packages=("chatterbox-tts==0.1.7", "setuptools<80"),
        worker="chatterbox_worker.py",
        download_gb=4.5,
        homepage="https://github.com/resemble-ai/chatterbox",
        notice="Every clip it makes carries Resemble AI's inaudible PerTh watermark.",
    ),
    "demucs": Engine(
        id="demucs",
        label="Demucs",
        kind="separation",
        description="Takes the speech out of the original, so the dub keeps its music and "
                    "effects at full volume.",
        licence="code MIT, weights unlicensed",
        commercial="unknown",
        languages=(),
        cloning=False,
        python="3.11",
        # Demucs converts its tensors with numpy but doesn't list it, so name it here.
        packages=("demucs==4.1.0", "numpy"),
        worker="demucs_worker.py",
        download_gb=0.7,
        homepage="https://github.com/adefossez/demucs",
        notice="Its author says the weights' licence isn't clear: part of their training "
               "data (MUSDB) was released for research only. Check that before using it "
               "commercially.",
    ),
}


# ── Where an engine lives ─────────────────────────────────

def engines_dir() -> Path:
    return Path(os.environ.get("VOXA_ENGINES_DIR") or Path.home() / ".voxa" / "engines")


def engine_dir(engine_id: str) -> Path:
    return engines_dir() / engine_id


def env_python(engine_id: str) -> Path:
    env = engine_dir(engine_id) / "env"
    return env / "Scripts" / "python.exe" if os.name == "nt" else env / "bin" / "python"


def _marker(engine_id: str) -> Path:
    return engine_dir(engine_id) / "installed.json"


def get(engine_id: str) -> Engine:
    try:
        return ENGINES[engine_id]
    except KeyError:
        raise EngineError(f"No engine called '{engine_id}'. "
                          f"Available: {', '.join(sorted(ENGINES))}") from None


def is_installed(engine_id: str) -> bool:
    """Installed completely: the marker is written last, so a failed install never counts."""
    return _marker(engine_id).is_file() and env_python(engine_id).is_file()


def status(engine_id: str) -> dict:
    """The catalogue entry plus whether, when and where it's installed."""
    engine = get(engine_id)
    info = {**asdict(engine), "installed": is_installed(engine_id),
            "path": str(engine_dir(engine_id))}
    if info["installed"]:
        try:
            info["installedAt"] = json.loads(_marker(engine_id).read_text("utf-8")).get(
                "installed")
        except (OSError, ValueError):
            pass
    return info


def catalogue() -> List[dict]:
    return [status(engine_id) for engine_id in sorted(ENGINES)]


# ── Installing and removing ──────────────────────────────

def find_uv() -> Optional[str]:
    """uv: on PATH, from the `uv` package on PyPI, or where its installer puts it."""
    found = shutil.which("uv")
    if found:
        return found
    try:
        from uv import find_uv_bin
        return find_uv_bin()
    except Exception:
        pass
    local = Path.home() / ".local" / "bin" / ("uv.exe" if os.name == "nt" else "uv")
    return str(local) if local.is_file() else None


def _run(cmd: List[str], log: Callable[[str], None]) -> None:
    """Run one install step, passing its output to `log` line by line."""
    log("$ " + " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    assert proc.stdout is not None
    for line in proc.stdout:
        log(line.rstrip())
    if proc.wait() != 0:
        raise EngineError(f"`{Path(cmd[0]).name} {' '.join(cmd[1:3])}` failed "
                          f"(exit code {proc.returncode}); the lines above say why")


def install(engine_id: str, log: Callable[[str], None] = print) -> None:
    """Create the engine's environment from scratch and install it there. Re-running it
    reinstalls; a failed run leaves the engine uninstalled rather than half there."""
    engine = get(engine_id)
    root = engine_dir(engine_id)
    if root.exists():
        remove(engine_id)
    env = root / "env"
    python = str(env_python(engine_id))
    uv = find_uv()
    if uv:
        _run([uv, "venv", "--python", engine.python, str(env)], log)
        # --torch-backend auto picks the CPU build of PyTorch on a machine without a
        # supported GPU, instead of the far larger CUDA build PyPI serves on Linux.
        _run([uv, "pip", "install", "--python", python, "--torch-backend", "auto",
              *engine.packages], log)
    else:
        wanted = tuple(int(p) for p in engine.python.split(".")[:2])
        if sys.version_info[:2] < wanted:
            raise EngineError(f"{engine.label} needs Python {engine.python} or newer, and "
                              f"this is {sys.version_info[0]}.{sys.version_info[1]}. Install uv "
                              f"(https://docs.astral.sh/uv/) and Voxa will fetch the right one.")
        _run([sys.executable, "-m", "venv", str(env)], log)
        _run([python, "-m", "pip", "install", *engine.packages], log)
    _marker(engine_id).write_text(json.dumps({
        "engine": engine_id, "packages": list(engine.packages),
        "installed": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, indent=2), encoding="utf-8")
    log(f"{engine.label} is installed in {root}")


def remove(engine_id: str) -> None:
    get(engine_id)
    root = engine_dir(engine_id)
    try:
        shutil.rmtree(root)
    except FileNotFoundError:
        pass
    except OSError as e:
        raise EngineError(f"Couldn't remove {root} ({e}). If a dub is using the engine, "
                          f"wait for it to finish and try again.") from e


# ── Talking to an installed engine ───────────────────────

class Worker:
    """An engine's worker process. The model loads once, on start(); each request() is one
    JSON line out and one back. Its stderr (library logs, progress bars) goes to log_path."""

    def __init__(self, engine_id: str, log_path: Optional[Path] = None):
        if not is_installed(engine_id):
            raise EngineError(f"{get(engine_id).label} isn't installed. Install it with: "
                              f"voxa engines install {engine_id}")
        self.engine = get(engine_id)
        self.log_path = log_path
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def start(self, **options) -> dict:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        stderr = open(self.log_path, "a", encoding="utf-8") if self.log_path else subprocess.DEVNULL
        self._proc = subprocess.Popen(
            [str(env_python(self.engine.id)), str(WORKERS_DIR / self.engine.worker)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
            text=True, encoding="utf-8", env=env)
        return self.request(cmd="load", **options)

    def request(self, on_progress: Optional[Callable[[float], None]] = None,
                **payload) -> dict:
        """Send one request and wait for its answer. A long request may say how far it has
        got first, in {"progress": 0.4} lines, which go to on_progress. Raises EngineError
        if the worker reports a failure or has gone away."""
        if self._proc is None or self._proc.poll() is not None:
            raise EngineError(f"The {self.engine.label} worker isn't running"
                              f"{self._log_tail()}")
        with self._lock:
            assert self._proc.stdin is not None and self._proc.stdout is not None
            try:
                self._proc.stdin.write(json.dumps(payload) + "\n")
                self._proc.stdin.flush()
                while True:
                    line = self._proc.stdout.readline()
                    if not line:
                        raise EngineError(f"The {self.engine.label} worker exited"
                                          f"{self._log_tail()}")
                    reply = json.loads(line)
                    if "progress" not in reply:
                        break
                    if on_progress:
                        on_progress(reply["progress"])
            except OSError as e:
                raise EngineError(f"The {self.engine.label} worker stopped ({e})"
                                  f"{self._log_tail()}") from e
        if not reply.get("ok"):
            raise EngineError(f"{self.engine.label}: {reply.get('error', 'failed')}")
        return reply

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.poll() is None:
                self.request(cmd="quit")
            self._proc.wait(timeout=30)
        except Exception:
            self._proc.kill()
        finally:
            self._proc = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _log_tail(self, lines: int = 8) -> str:
        if not self.log_path or not Path(self.log_path).is_file():
            return ""
        tail = Path(self.log_path).read_text("utf-8", errors="replace").splitlines()[-lines:]
        return ":\n    " + "\n    ".join(tail) if tail else ""
