"""Voxa Studio: the console in a window of its own.

`voxa studio`, and the `voxa-studio` launcher that opens no terminal, run `voxa serve` as a child
process and show the console in a native window: pywebview, from the [studio] extra, with Edge
WebView2 on Windows and WebKit on macOS. Closing the window stops the server and any dub it is
running, after asking if one is. With no window to open (no pywebview, or Linux without GTK or
Qt) the console opens in the browser instead, as `voxa studio` always did.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Callable, List, Optional

TITLE = "Voxa Studio"
LOG_LIMIT = 5 * 1024 * 1024          # studio.log is started afresh past this

CLOSE_QUESTION = {
    "en": "Dubs still running: {n}. Closing Voxa Studio stops them, and dubbing the same video "
          "again later reuses the steps they finished. Close anyway?",
    "az": "Hələ gedən dublyaj: {n}. Voxa Studio-nu bağlamaq onları dayandırır; eyni videonu sonra "
          "yenidən dublyaj etsəniz, bitmiş addımlar yenidən istifadə olunur. Yenə də bağlansın?",
    "tr": "Hâlâ süren dublaj: {n}. Voxa Studio'yu kapatmak onları durdurur; aynı videoyu sonra "
          "yeniden dublajlarsanız biten adımlar yeniden kullanılır. Yine de kapatılsın mı?",
}


def system_language() -> str:
    """az, tr or en, from the user's locale (for the one native question the window asks)."""
    tag = ""
    if os.name == "nt":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(85)
            if ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85):
                tag = buf.value
        except (AttributeError, OSError):
            pass
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        tag = tag or os.environ.get(name, "")
    primary = tag.replace("_", "-").split("-")[0].lower()
    return primary if primary in CLOSE_QUESTION else "en"


def pick_port(preferred: int = 8000) -> int:
    """The preferred port if it is free on loopback, else any free one."""
    for port in (preferred, 0):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return sock.getsockname()[1]
    raise OSError("no free port on 127.0.0.1")


def server_command(port: int, extra: List[str]) -> List[str]:
    """`voxa serve` on the same Python. The launcher runs on pythonw.exe, which has no console;
    the server gets python.exe and a console of its own, hidden, which the dubs and their
    ffmpeg calls then share instead of each flashing a window up."""
    python = Path(sys.executable)
    if python.name.lower() == "pythonw.exe" and python.with_name("python.exe").exists():
        python = python.with_name("python.exe")
    return [str(python), "-c", "import voxa; voxa.cli()", "serve", "--port", str(port), *extra]


def _answers(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/api/health", timeout=2) as response:
            return "version" in json.load(response)
    except (OSError, ValueError):
        return False


def running_studio(workspace: Path) -> Optional[str]:
    """The address of a Voxa Studio already serving this folder, so a second launch opens a
    window on it instead of a second server."""
    try:
        url = json.loads((workspace / "studio.json").read_text(encoding="utf-8"))["url"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return url if _answers(url) else None


def dubs_running(url: str) -> int:
    try:
        with urllib.request.urlopen(f"{url}/api/jobs", timeout=2) as response:
            jobs = json.load(response)["jobs"]
    except (OSError, ValueError, KeyError):
        return 0
    return sum(job.get("status") in ("queued", "running") for job in jobs)


def ask(window, question: str) -> bool:
    """OK or Cancel from the user. On Windows a Win32 message box: pywebview's own is a WinForms
    one, shown from the thread its closing handler runs on, which isn't an STA thread, so it
    never appeared and Cancel was taken, and the window couldn't be closed during a dub. It has
    no owner, since the window's thread waits on this handler: it stays on top instead, with
    Cancel as the default."""
    if os.name == "nt":
        import ctypes
        user32 = ctypes.WinDLL("user32")
        user32.MessageBoxW.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                                       ctypes.c_uint)
        flags = 0x1 | 0x30 | 0x100 | 0x10000 | 0x40000   # OKCANCEL, WARNING, DEFBUTTON2,
        return user32.MessageBoxW(None, question, TITLE, flags) == 1   # SETFOREGROUND, TOPMOST
    return bool(window.create_confirmation_dialog(TITLE, question))


def may_close(running: int, ask: Callable[[str], bool], language: str) -> bool:
    """Whether the window may close: yes with nothing running, else what the user answers."""
    return running == 0 or ask(CLOSE_QUESTION[language].format(n=running))


class _KillTogether:
    """Windows: a job object holding the server, so it and every process it starts (the dubs,
    their ffmpeg, engine workers) end when this one closes it, or when this process ends in any
    way, a crash included."""

    def __init__(self, pid: int) -> None:
        import ctypes
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class Io(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", Io),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
        k32.SetInformationJobObject.restype = wintypes.BOOL
        k32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                                                wintypes.DWORD)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k32.AssignProcessToJobObject.restype = wintypes.BOOL
        k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        self._k32 = k32

        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x2000          # KILL_ON_JOB_CLOSE
        self.handle = k32.CreateJobObjectW(None, None)
        process = k32.OpenProcess(0x0100 | 0x0001, False, pid)  # SET_QUOTA | TERMINATE
        ok = (self.handle and process
              and k32.SetInformationJobObject(self.handle, 9, ctypes.byref(info),
                                              ctypes.sizeof(info))
              and k32.AssignProcessToJobObject(self.handle, process))
        if process:
            k32.CloseHandle(process)
        if not ok:
            self.close()
            raise OSError(ctypes.get_last_error(), "couldn't put the server in a job object")

    def close(self) -> None:
        if self.handle:
            self._k32.CloseHandle(self.handle)
            self.handle = None


class Server:
    """`voxa serve` as a child process, stopped together with everything it started."""

    def __init__(self, workspace: Path, port: int, extra: List[str], hidden: bool) -> None:
        self.url = f"http://127.0.0.1:{port}"
        env = {**os.environ, "VOXA_STUDIO_PARENT": str(os.getpid())}
        kwargs: dict = {"cwd": str(workspace.parent), "env": env}
        if hidden:
            # No console to write to: the server's output goes to a log the user can send.
            log = workspace / "studio.log"
            workspace.mkdir(parents=True, exist_ok=True)
            if log.exists() and log.stat().st_size > LOG_LIMIT:
                log.replace(log.with_suffix(".log.1"))
            kwargs["stdout"] = open(log, "ab")
            kwargs["stderr"] = subprocess.STDOUT
        if os.name == "nt":
            if hidden:
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            kwargs["start_new_session"] = True      # its own group, stopped as one
        self.process = subprocess.Popen(server_command(port, extra), **kwargs)
        self._together: Optional[_KillTogether] = None
        if os.name == "nt":
            try:
                self._together = _KillTogether(self.process.pid)
            except OSError as e:
                print(f"⚠️  {e}; closing Voxa Studio may leave a dub running", file=sys.stderr)

    def wait_ready(self, timeout: float = 120.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.process.poll() is not None:
                return False
            if _answers(self.url):
                return True
            time.sleep(0.25)
        return False

    def stop(self) -> None:
        if self.process.poll() is None:
            if self._together is not None:
                self._together.close()
            elif os.name != "nt":
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except OSError:
                    pass
            else:
                self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                if os.name != "nt":
                    try:
                        os.killpg(self.process.pid, signal.SIGKILL)
                    except OSError:
                        pass
                self.process.kill()
        if self._together is not None:
            self._together.close()


STARTING = {"en": "Starting…", "az": "Başlayır…", "tr": "Başlatılıyor…"}
FAILED = {
    "en": "Voxa's server didn't start. What it printed is in {log}",
    "az": "Voxa-nın serveri başlamadı. Yazdıqları buradadır: {log}",
    "tr": "Voxa'nın sunucusu başlamadı. Yazdıkları şurada: {log}",
}


def page(text: str) -> str:
    """The window's own page while the server starts, or when it couldn't."""
    from html import escape
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{height:100%;margin:0}}
body{{display:grid;place-items:center;background:#0a0a0b;color:#a1a1aa;
font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;text-align:center;padding:24px}}
h1{{color:#e7e7ea;font-size:20px;margin:0 0 8px}}
</style></head><body><div><h1>{TITLE}</h1><p>{escape(text)}</p></div></body></html>"""


def window_icon(windows: Optional[bool] = None) -> Optional[str]:
    """Voxa's icon for the window and its taskbar button: .ico on Windows (pywebview's WinForms
    window takes it there too, whatever its docs say), .png for GTK and Qt."""
    try:
        from voxa_ui import icon_path
    except ImportError:
        return None
    windows = os.name == "nt" if windows is None else windows
    path = icon_path("ico" if windows else "png")
    return str(path) if path.is_file() else None


def open_window(url: Optional[str], storage: Path, may_close_now: Callable[["object"], bool],
                when_shown: Optional[Callable[["object"], None]] = None,
                waiting: str = "") -> bool:
    """Show a window and return once it is closed: on `url`, or on a page saying `waiting`
    while `when_shown` (run in a thread of its own once the window is up) gets it there.
    False when no window could be opened, so the caller falls back to the browser."""
    try:
        import webview
    except Exception:                       # not installed, or no GUI backend to import
        return False
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True      # a Save dialog, starting in Downloads
        window = webview.create_window(TITLE, f"{url}/" if url else None,
                                       html=None if url else page(waiting),
                                       width=1280, height=840, min_size=(960, 640),
                                       background_color="#0A0A0B", text_select=True)

        def closing() -> bool:
            return may_close_now(window)

        window.events.closing += closing
        # Not private: the console keeps its language, theme and settings between launches,
        # here in the Voxa folder rather than pywebview's.
        webview.start(when_shown, (window,) if when_shown else None,
                      private_mode=False, storage_path=str(storage), icon=window_icon())
        return True
    except Exception as e:                  # e.g. Linux without GTK or Qt
        print(f"⚠️  Couldn't open a window ({e}); opening the browser instead", file=sys.stderr)
        return False


def run(argv: Optional[List[str]] = None, hidden: bool = False) -> int:
    parser = argparse.ArgumentParser(
        prog="voxa studio",
        description="Open the Voxa console in a window of its own (in the browser without one).")
    parser.add_argument("--port", type=int, default=0,
                        help="Port for its server (default: 8000 when free, else any)")
    parser.add_argument("--browser", action="store_true",
                        help="Open the console in the browser instead of a window")
    args, extra = parser.parse_known_args(argv)

    home = Path.cwd()
    workspace = home / ".voxa_serve"
    language = system_language()
    log = workspace / "studio.log"

    url = None if args.browser else running_studio(workspace)
    server = None
    if url is None:
        server = Server(workspace, args.port or pick_port(), extra, hidden)
        url = server.url
    outcome = {"ready": server is None}

    def ready() -> bool:
        """Wait for the server (once), and say where this folder's Studio is."""
        if not outcome["ready"]:
            outcome["ready"] = server.wait_ready()
            if outcome["ready"]:
                try:
                    workspace.mkdir(parents=True, exist_ok=True)
                    (workspace / "studio.json").write_text(
                        json.dumps({"url": url, "pid": os.getpid()}), encoding="utf-8")
                except OSError:
                    pass
        return outcome["ready"]

    def when_shown(window) -> None:
        if ready():
            window.load_url(f"{url}/")
        else:
            window.load_html(page(FAILED[language].format(log=log if hidden else "the terminal")))

    def may_close_now(window) -> bool:
        if server is None or not outcome["ready"]:   # not ours, or nothing running yet
            return True
        return may_close(dubs_running(url), lambda question: ask(window, question), language)

    try:
        shown = not args.browser and open_window(
            None if server else url, workspace / "webview", may_close_now,
            when_shown if server else None, STARTING[language])
        if not shown:
            if not ready():
                print("❌ Voxa's server didn't start" + (f"; see {log}" if hidden else ""),
                      file=sys.stderr)
                return 1
            webbrowser.open(f"{url}/")
            if server is not None:
                print(f"🖥️  Voxa Studio → {url}/   (Ctrl+C stops it)")
                try:
                    server.process.wait()
                except KeyboardInterrupt:
                    pass
        return 0 if outcome["ready"] else 1
    finally:
        if server is not None:
            server.stop()
            marker = workspace / "studio.json"
            try:
                if json.loads(marker.read_text(encoding="utf-8"))["url"] == url:
                    marker.unlink()
            except (OSError, ValueError, KeyError):
                pass


def main() -> None:
    """The `voxa-studio` launcher: no console, so everything printed goes to a log."""
    workspace = Path.cwd() / ".voxa_serve"
    try:
        workspace.mkdir(parents=True, exist_ok=True)
        log = open(workspace / "studio-window.log", "a", encoding="utf-8", buffering=1)
    except OSError:
        log = open(os.devnull, "w", encoding="utf-8")
    # pythonw.exe leaves both as None, and a library writing to them stops the window opening.
    sys.stdout = sys.stderr = log
    sys.exit(run(sys.argv[1:], hidden=True))
