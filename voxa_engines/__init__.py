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
import re
import shutil
import subprocess
import sys
import threading
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

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
    "voxcpm": Engine(
        id="voxcpm",
        label="VoxCPM2",
        kind="tts",
        description="Clones each speaker's voice from the original video, in 30 languages; "
                    "made for an NVIDIA GPU.",
        licence="Apache-2.0",
        commercial="yes",
        languages=("ar", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "id", "it",
                   "ja", "km", "ko", "lo", "ms", "my", "nl", "no", "pl", "pt", "ru", "sv",
                   "sw", "th", "tl", "tr", "vi", "zh"),
        cloning=True,
        python="3.11",
        packages=("voxcpm==2.0.3",),
        worker="voxcpm_worker.py",
        download_gb=6.4,
        homepage="https://github.com/OpenBMB/VoxCPM",
        notice="Without an NVIDIA GPU it is slow: on a laptop CPU each line took 18 to 31 "
               "times as long as its speech, so a ten-minute video takes hours, and loading "
               "it used 9.5 GB of memory. Its model card forbids using it to impersonate "
               "anyone, and asks that what it makes be labelled as AI-generated.",
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
            marker = json.loads(_marker(engine_id).read_text("utf-8"))
        except (OSError, ValueError):
            marker = {}
        info["installedAt"] = marker.get("installed")
        # Where it computes, when the install found out: "gpu" (on info["gpu"]) or "cpu".
        info["runsOn"], info["gpu"] = marker.get("runsOn"), marker.get("gpu")
    return info


def catalogue() -> List[dict]:
    return [status(engine_id) for engine_id in sorted(ENGINES)]


# ── Installing and removing ──────────────────────────────

def find_uv() -> Optional[str]:
    """uv: VoxaSetup.exe's own (beside its uninstaller; not on PATH), on PATH, from the `uv`
    package on PyPI, or where its installer puts it."""
    setup = Path(sys.prefix).parent.parent
    if (setup / "Uninstall Voxa.exe").is_file() and (setup / "uv.exe").is_file():
        return str(setup / "uv.exe")
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


# What uv's exit codes mean, to say after its own words. Measured with uv 0.13.8: packages that
# can't be installed together end it with 1, a download that fails (an index it can't reach,
# a connection that drops) with 2.
_UV_EXIT = {
    1: "These packages can't be installed together here.",
    2: "A download failed: check the connection, and that pypi.org and download.pytorch.org "
       "can be reached from this network, then install again.",
}
_ERROR_LINE = ("error", "caused by", "cause:", "×", "╰─▶", "help:")


def _failure(cmd: List[str], code: int, tail: List[str]) -> str:
    """Why an install step failed, in one message that stands on its own: the console shows it
    where the step's output may not be on screen. uv's own error lines, then what its exit
    code means. Pure."""
    said = [line.strip() for line in tail if line.strip().lower().startswith(_ERROR_LINE)]
    said = said or [line.strip() for line in tail if line.strip()][-3:]
    step = f"`{Path(cmd[0]).name} {' '.join(cmd[1:3])}` failed (exit code {code})"
    meaning = _UV_EXIT.get(code) if Path(cmd[0]).stem.lower() == "uv" else None
    return " ".join([step + (":" if said else "."), *said[-6:]] +
                    ([meaning] if meaning else []))[:900]


def _run(cmd: List[str], log: Callable[[str], None]) -> None:
    """Run one install step, passing its output to `log` line by line."""
    log("$ " + " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    assert proc.stdout is not None
    tail: deque = deque(maxlen=40)
    for line in proc.stdout:
        log(line.rstrip())
        tail.append(line.rstrip())
    if proc.wait() != 0:
        raise EngineError(_failure(cmd, proc.returncode, list(tail)))


# ── Which PyTorch an engine gets ─────────────────────────
# uv's --torch-backend auto takes the newest CUDA build the GPU's driver runs. An engine whose
# packages pin PyTorch may have no such build: chatterbox-tts 0.1.7 pins torch 2.6.0, which
# exists for CUDA 12.6 at most, and voxcpm 2.0.3 resolves for CUDA 12.6 and 13.0 only (both
# measured with uv 0.13.8), so on a driver newer than that the install failed. And a build can
# leave the GPU out: PyTorch's CUDA 13 builds start at Turing, RTX 50 cards need CUDA 12.8 and
# PyTorch 2.7. So the build is chosen here, from the GPU, its driver and what the packages
# resolve to, and checked on the GPU once installed.
CUDA_BUILDS: Tuple[Tuple[str, Tuple[int, int]], ...] = (
    ("cu130", (13, 0)), ("cu129", (12, 9)), ("cu128", (12, 8)), ("cu126", (12, 6)),
    ("cu124", (12, 4)), ("cu121", (12, 1)), ("cu118", (11, 8)))


class Gpu(NamedTuple):
    name: str
    capability: Optional[Tuple[int, int]]   # its compute capability, 8.9 for an RTX 4090
    cuda: Optional[Tuple[int, int]]         # the newest CUDA its driver runs


def parse_nvidia_smi(query: str, summary: str) -> Optional[Gpu]:
    """The first GPU nvidia-smi lists, from `--query-gpu=name,compute_cap --format=csv,noheader`
    and from its summary table, which says the newest CUDA the driver runs. Pure."""
    line = next((ln.strip() for ln in query.splitlines() if ln.strip()), "")
    if not line or "not a valid field" in line.lower() or "failed" in line.lower():
        return None
    name, _, cap = line.rpartition(",")
    if not name:
        name, cap = line, ""
    found = re.match(r"\s*(\d+)\.(\d+)", cap)
    cuda = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", summary)
    return Gpu(name.strip(),
               (int(found[1]), int(found[2])) if found else None,
               (int(cuda[1]), int(cuda[2])) if cuda else None)


def nvidia_gpu() -> Optional[Gpu]:
    """This computer's NVIDIA GPU, as nvidia-smi (installed with the driver) describes it, or
    None without one."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        query = subprocess.run([exe, "--query-gpu=name,compute_cap", "--format=csv,noheader"],
                               capture_output=True, text=True, timeout=20)
        if query.returncode != 0:              # a driver older than the compute_cap field
            query = subprocess.run([exe, "--query-gpu=name", "--format=csv,noheader"],
                                   capture_output=True, text=True, timeout=20)
        summary = subprocess.run([exe], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_nvidia_smi(query.stdout if query.returncode == 0 else "", summary.stdout)


def _version(text: str) -> Tuple[int, int]:
    found = re.match(r"(\d+)\.(\d+)", text or "")
    return (int(found[1]), int(found[2])) if found else (0, 0)


def torch_runs_on(build: str, torch_version: str,
                  capability: Optional[Tuple[int, int]]) -> bool:
    """Whether PyTorch `torch_version`'s `build` has the kernels for a GPU of `capability`, by
    what PyTorch has published: Blackwell (10.0 and up) needs CUDA 12.8 and PyTorch 2.7; CUDA
    13 builds start at Turing (7.5); CUDA 12.8 and 12.9 builds left out Maxwell and Pascal from
    2.8, and Volta from 2.11; older builds run from Maxwell (5.0) on. An unknown capability
    is taken to be fine: the GPU check after the install has the last word. Pure."""
    cuda = dict(CUDA_BUILDS).get(build)
    if cuda is None:
        return False
    if capability is None:
        return True
    torch = _version(torch_version)
    if capability >= (10, 0):
        return cuda >= (12, 8) and torch >= (2, 7)
    if cuda >= (13, 0):
        return capability >= (7, 5)
    if cuda >= (12, 8) and torch >= (2, 11):
        return capability >= (7, 5)
    if cuda >= (12, 8) and torch >= (2, 8):
        return capability >= (7, 0)
    return capability >= (5, 0)


def _cap(capability: Optional[Tuple[int, int]]) -> str:
    return f"{capability[0]}.{capability[1]}" if capability else "?"


def choose_torch(gpu: Optional[Gpu],
                 resolve: Callable[[str], Tuple[int, Optional[str], List[str]]],
                 log: Callable[[str], None]) -> Tuple[str, str]:
    """The --torch-backend to install an engine with, and in a sentence why. `resolve(backend)`
    is uv's dry run: (its exit code, the torch it would install, its output's last lines).
    With an NVIDIA GPU, the newest CUDA build its driver runs that the packages resolve to and
    whose PyTorch has the GPU's kernels; none, and the CPU. Without one, uv's own choice, or
    the CPU if the packages don't resolve to it. A download that fails stops the install."""
    def attempt(backend: str) -> Tuple[int, Optional[str]]:
        code, torch, tail = resolve(backend)
        if code == 2:
            raise EngineError(_failure(["uv", "pip", "install"], code, tail))
        return code, torch

    if gpu is None or gpu.cuda is None:
        if attempt("auto")[0] == 0:
            return "auto", ""
        return "cpu", "no PyTorch build these packages accept was found for this computer, " \
                      "so it gets the CPU build"
    for build, cuda in CUDA_BUILDS:
        if cuda > gpu.cuda:
            continue
        code, torch = attempt(build)
        if code != 0 or not torch:
            log(f"PyTorch for CUDA {cuda[0]}.{cuda[1]} ({build}): these packages don't "
                f"install with it")
            continue
        if not torch_runs_on(build, torch, gpu.capability):
            log(f"PyTorch for CUDA {cuda[0]}.{cuda[1]} ({build}): {torch} has no kernels for "
                f"{gpu.name} (compute {_cap(gpu.capability)})")
            continue
        return build, f"PyTorch {torch} for {gpu.name} (compute {_cap(gpu.capability)})"
    newer = gpu.cuda < CUDA_BUILDS[0][1]
    return "cpu", (f"no PyTorch these packages accept runs on {gpu.name} (compute "
                   f"{_cap(gpu.capability)}, driver for CUDA {gpu.cuda[0]}.{gpu.cuda[1]}), so "
                   f"it runs on the CPU" +
                   ("; a newer NVIDIA driver may let it use the GPU" if newer else ""))


def _resolve(uv: str, python: str, packages: Tuple[str, ...],
             backend: str) -> Tuple[int, Optional[str], List[str]]:
    """uv's dry run of an install with `backend`: what it would do, nothing downloaded but
    the packages' metadata."""
    proc = subprocess.run([uv, "pip", "install", "--python", python, "--dry-run",
                           "--torch-backend", backend, *packages],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=900)
    said = (proc.stdout or "") + (proc.stderr or "")
    torch = re.search(r"^\s*\+\s*torch==(\S+)", said, re.MULTILINE)
    return proc.returncode, (torch[1] if torch else None), said.splitlines()[-40:]


# Runs in the engine's environment: whether its PyTorch can work on the GPU, by working on it.
_GPU_CHECK = (
    "import json, torch\n"
    "r = {'torch': torch.__version__, 'cuda': torch.cuda.is_available()}\n"
    "if r['cuda']:\n"
    "    try:\n"
    "        r['works'] = float((torch.ones(64, device='cuda') * 2).sum()) == 128.0\n"
    "    except Exception as e:\n"
    "        r['works'], r['error'] = False, str(e).splitlines()[0][:200]\n"
    "print(json.dumps(r))\n")


def gpu_works(python: str) -> Tuple[bool, str]:
    """Whether the PyTorch in an engine's environment computes on the GPU, and if not, why."""
    try:
        proc = subprocess.run([python, "-c", _GPU_CHECK], capture_output=True, text=True,
                              timeout=300)
        seen = json.loads(proc.stdout.strip().splitlines()[-1])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return False, "PyTorch couldn't be started to check the GPU"
    if not seen.get("cuda"):
        return False, f"PyTorch {seen.get('torch')} doesn't see a CUDA GPU"
    if not seen.get("works"):
        return False, f"PyTorch {seen.get('torch')} can't compute on it ({seen.get('error')})"
    return True, ""


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
    runs: dict = {}
    if uv:
        _run([uv, "venv", "--python", engine.python, str(env)], log)
        gpu = nvidia_gpu()
        if gpu:
            cuda = f"{gpu.cuda[0]}.{gpu.cuda[1]}" if gpu.cuda else "?"
            log(f"GPU: {gpu.name}, compute {_cap(gpu.capability)}, its driver runs CUDA {cuda}")
        backend, why = choose_torch(
            gpu, lambda b: _resolve(uv, python, engine.packages, b), log)
        if why:
            log(f"PyTorch: {why}")
        _run([uv, "pip", "install", "--python", python, "--torch-backend", backend,
              *engine.packages], log)
        runs = {"torch": backend, "gpu": gpu.name if gpu else None,
                "runsOn": ("cpu" if backend == "cpu" else None) if gpu else None}
        if gpu and backend != "cpu":
            works, why_not = gpu_works(python)
            if works:
                runs["runsOn"] = "gpu"
                log(f"{engine.label} computes on {gpu.name}")
            else:
                # The table in torch_runs_on can be behind PyTorch: the GPU has the last word.
                log(f"{gpu.name}: {why_not}. Installing the CPU build of PyTorch instead, "
                    f"which is slower but runs")
                _run([uv, "pip", "install", "--python", python, "--torch-backend", "cpu",
                      "--reinstall", *engine.packages], log)
                runs.update(torch="cpu", runsOn="cpu")
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
        "installed": datetime.now(timezone.utc).isoformat(timespec="seconds"), **runs,
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
