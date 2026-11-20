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
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

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
# Shown under it after ten seconds: the wait is the server loading its libraries, longest from
# a cold disk (measured 9 s warm, 21 s right after a restart, on the laptop Voxa is built on).
HINT = {
    "en": "The first start after turning the computer on takes the longest: Voxa loads its "
          "libraries.",
    "az": "Kompüter açılandan sonrakı ilk başlanğıc ən uzun çəkir: Voxa kitabxanalarını yükləyir.",
    "tr": "Bilgisayar açıldıktan sonraki ilk başlangıç en uzun sürer: Voxa kitaplıklarını "
          "yüklüyor.",
}
FAILED = {
    "en": "Voxa's server didn't start. What it printed is in {log}",
    "az": "Voxa-nın serveri başlamadı. Yazdıqları buradadır: {log}",
    "tr": "Voxa'nın sunucusu başlamadı. Yazdıkları şurada: {log}",
}
OPEN_LOGS = {"en": "Open the log folder", "az": "Loq qovluğunu aç", "tr": "Günlük klasörünü aç"}
WEBVIEW2_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"
NO_WEBVIEW2 = {
    "en": "Voxa Studio shows its window with Microsoft Edge WebView2, which this computer doesn't "
          "have (or its .NET Framework is older than 4.6.2). The console opens in your browser "
          "instead.\n\nWebView2 can be installed from:\n{url}",
    "az": "Voxa Studio pəncərəsini Microsoft Edge WebView2 ilə göstərir, bu kompüterdə isə o "
          "yoxdur (və ya .NET Framework 4.6.2-dən köhnədir). Konsol bunun əvəzinə brauzerdə "
          "açılır.\n\n"
          "WebView2-ni buradan qura bilərsiniz:\n{url}",
    "tr": "Voxa Studio penceresini Microsoft Edge WebView2 ile gösterir; bu bilgisayarda o yok "
          "(ya da .NET Framework 4.6.2'den eski). Konsol bunun yerine tarayıcıda açılıyor.\n\n"
          "WebView2'yi şuradan kurabilirsiniz:\n{url}",
}

# The console's own colors (web/app/globals.css), for what the window draws before and around
# it: background, text, heading, brand.
PAGE_COLORS = {
    "dark": ("#0A0A0B", "#A1A1AA", "#FAFAFA", "#38BDF8"),
    "light": ("#FFFFFF", "#52525B", "#0A0A0B", "#0369A1"),
}
# The title bar: caption, its text, the window's border. surface-0, foreground and border.
CHROME = {
    "dark": ("#0D0D0F", "#FAFAFA", "#26262B"),
    "light": ("#F6F6F7", "#0A0A0B", "#E4E4E7"),
}


def page(text: str, theme: str = "dark", hint: str = "", button: str = "") -> str:
    """The window's own page while the server starts, or when it couldn't: Voxa's waveform,
    what is happening, `hint` faded in after ten seconds of waiting, and `button`, which opens
    the log folder. In the theme the console was last in, so nothing flashes."""
    from html import escape
    bg, fg, heading, brand = PAGE_COLORS.get(theme, PAGE_COLORS["dark"])
    bars = "".join(f'<i style="height:{h}px;animation-delay:{i * 120}ms"></i>'
                   for i, h in enumerate((12, 22, 32, 18, 28, 14, 24)))
    hint_html = f'<p class="hint">{escape(hint)}</p>' if hint else ""
    button_html = (f'<button onclick="window.pywebview&&window.pywebview.api.open_logs()">'
                   f'{escape(button)}</button>' if button else "")
    scheme = "light" if theme == "light" else "dark"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box}}
html,body{{height:100%;margin:0;overflow:hidden;color-scheme:{scheme}}}
body{{display:grid;place-items:center;background:{bg};color:{fg};
font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;text-align:center;padding:24px}}
h1{{color:{heading};font-size:20px;font-weight:600;margin:16px 0 6px}}
p{{margin:0;max-width:440px}}
.wave{{display:flex;gap:4px;align-items:center;justify-content:center;height:36px}}
.wave i{{display:block;width:4px;border-radius:2px;background:{brand};
animation:w 1.2s ease-in-out infinite;transform:scaleY(.4)}}
@keyframes w{{50%{{transform:scaleY(1)}}}}
.hint{{margin-top:18px;font-size:13px;opacity:0;animation:show .3s 10s forwards}}
@keyframes show{{to{{opacity:1}}}}
button{{margin-top:20px;font:inherit;font-weight:500;color:{bg};background:{brand};border:0;
border-radius:6px;padding:8px 14px;cursor:pointer}}
button:focus-visible{{outline:2px solid {brand};outline-offset:2px}}
@media (prefers-reduced-motion:reduce){{.wave i{{animation:none;transform:scaleY(.7)}}}}
</style></head><body><div><div class="wave" aria-hidden="true">{bars}</div>
<h1>{TITLE}</h1><p>{escape(text)}</p>{hint_html}{button_html}</div></body></html>"""


# ── where the window was, and in which theme ─────────────
WINDOW_FILE = "window.json"
DEFAULT_SIZE = (1280, 840)
MIN_SIZE = (960, 640)


def read_place(workspace: Path) -> dict:
    """What the last window left in window.json: its size, place, whether it was maximized,
    and the console's theme."""
    try:
        data = json.loads((workspace / WINDOW_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _number(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def window_place(saved: dict, screens) -> dict:
    """create_window's size and place: the last window's size, at least the minimum; its
    place only if a screen is still there (a monitor may have been unplugged since), else
    centred; and maximized if it was."""
    place = {"width": DEFAULT_SIZE[0], "height": DEFAULT_SIZE[1]}
    if _number(saved.get("width")) and _number(saved.get("height")):
        place["width"] = max(saved["width"], MIN_SIZE[0])
        place["height"] = max(saved["height"], MIN_SIZE[1])
    x, y = saved.get("x"), saved.get("y")
    # Its title bar, a little in from the corner, has to be on a screen to be dragged back.
    if _number(x) and _number(y) and any(
            s.x <= x + 40 < s.x + s.width and s.y <= y + 10 < s.y + s.height for s in screens):
        place["x"], place["y"] = x, y
    if saved.get("maximized") is True:
        place["maximized"] = True
    return place


def _write_place(workspace: Path, data: dict) -> None:
    path = workspace / WINDOW_FILE
    try:
        workspace.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(".json.part")
        part.write_text(json.dumps(data), encoding="utf-8")
        part.replace(path)
    except OSError:
        pass                                # not kept: the next window opens at the default


def remember_place(workspace: Path, x: int, y: int, width: int, height: int, state: str) -> None:
    """Keep the window's place for the next launch. A maximized window keeps the size it had
    before, to go back to; a minimized one keeps nothing (Windows parks it off every screen)."""
    data = read_place(workspace)
    if state == "normal":
        data.update(x=x, y=y, width=width, height=height, maximized=False)
    elif state == "maximized":
        data["maximized"] = True
    else:
        return
    _write_place(workspace, data)


# ── the title bar in Voxa's colors (Windows 11) ──────────
def _colorref(hex_color: str) -> int:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return r | (g << 8) | (b << 16)


def paint_title_bar(hwnd: int, theme: str, dwm=None) -> bool:
    """Draw the native title bar in the console's colors, so the window reads as one piece.
    The frame stays Windows' own: Snap Layouts, resizing by the edges and DPI keep working,
    which a frameless window drawn by the page loses in pywebview (VOXA_DESIGN_PLAN.md §7.1).
    Dark mode for the caption buttons from Windows 10 1809; the colors from Windows 11, which
    10 refuses, leaving its own. True when the colors took."""
    if os.name != "nt":
        return False
    import ctypes
    if dwm is None:
        dwm = ctypes.WinDLL("dwmapi")
        dwm.DwmSetWindowAttribute.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p,
                                              ctypes.c_uint)
        dwm.DwmSetWindowAttribute.restype = ctypes.c_long

    def attribute(name: int, value: int) -> bool:
        data = ctypes.c_uint(value)
        return dwm.DwmSetWindowAttribute(hwnd, name, ctypes.byref(data), 4) == 0

    caption, text, border = CHROME.get(theme, CHROME["dark"])
    attribute(20, 1 if theme == "dark" else 0)       # DWMWA_USE_IMMERSIVE_DARK_MODE
    attribute(38, 1)                                  # DWMWA_SYSTEMBACKDROP_TYPE: none, not Mica
    return all([attribute(35, _colorref(caption)),   # DWMWA_CAPTION_COLOR
                attribute(36, _colorref(text)),      # DWMWA_TEXT_COLOR
                attribute(34, _colorref(border))])   # DWMWA_BORDER_COLOR


def paint_window(window, theme: str) -> bool:
    try:
        hwnd = int(window.native.Handle.ToInt64())     # the WinForms form pywebview made
    except Exception:
        return False
    return paint_title_bar(hwnd, theme)


# ── The taskbar button: a dub's progress, and a call back when one needs you ─
# The window watches the dubs the server lists (VOXA_DESIGN_PLAN.md §7.5), so the console's
# page takes no part and a browser is untouched.

TASKBAR_EVERY = 2.0                     # seconds between two looks at the dubs
_PROGRESS = {"none": 0, "indeterminate": 1, "normal": 2, "error": 4, "paused": 8}
GOING = ("queued", "running")


def fetch_jobs(url: str) -> Optional[List[dict]]:
    try:
        with urllib.request.urlopen(f"{url}/api/jobs", timeout=2) as response:
            return json.load(response)["jobs"]
    except (OSError, ValueError, KeyError):
        return None


def taskbar_state(jobs: List[dict]) -> Tuple[str, float]:
    """What the button shows: the running dub's step out of seven (the oldest, when several
    run); something moving while dubs only wait in the queue; nothing otherwise."""
    running = [job for job in jobs if job.get("status") == "running"]
    if running:
        step = min(max(int(running[0].get("step") or 1), 1), 7)
        return "normal", step / 7
    if any(job.get("status") == "queued" for job in jobs):
        return "indeterminate", 0.0
    return "none", 0.0


def calls_back(before: Dict[str, str], jobs: List[dict]) -> List[str]:
    """The dubs that, since the last look, finished, failed, or stopped to have their lines
    checked: each a reason to call the user back. One the user stopped isn't."""
    out = []
    for job in jobs:
        if before.get(job.get("id")) not in GOING:
            continue
        status = job.get("status")
        if status in ("done", "review") or (status == "failed" and not job.get("cancelled")):
            out.append(job["id"])
    return out


class Taskbar:
    """The window's taskbar button, on Windows: its progress (ITaskbarList3, through COM) and
    a flash until the window is brought forward (FlashWindowEx). Made and used on one thread,
    which COM is started on. Anywhere else, or if Windows refuses, each call does nothing."""

    CLSID = "{56FDF344-FD6D-11d0-958A-006097C9A090}"        # TaskbarList
    IID = "{EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF}"          # ITaskbarList3

    def __init__(self, hwnd: int) -> None:
        self.hwnd = hwnd
        self._list = None
        self._shown: Optional[Tuple[str, float]] = None
        if os.name != "nt" or not hwnd:
            return
        import ctypes
        from ctypes import wintypes
        self._ctypes = ctypes
        self._user32 = ctypes.WinDLL("user32")
        ole32 = ctypes.WinDLL("ole32")
        try:
            ole32.CoInitializeEx(None, 0x2)                 # COINIT_APARTMENTTHREADED

            class GUID(ctypes.Structure):
                _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD),
                            ("d", ctypes.c_ubyte * 8)]

            def guid(text: str) -> GUID:
                g = GUID()
                ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(g))
                return g

            pointer = ctypes.c_void_p()
            if ole32.CoCreateInstance(ctypes.byref(guid(self.CLSID)), None, 0x1,  # INPROC
                                      ctypes.byref(guid(self.IID)), ctypes.byref(pointer)):
                return
            table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
            hresult = ctypes.c_long
            self._init = ctypes.WINFUNCTYPE(hresult, ctypes.c_void_p)(table[3])
            self._value = ctypes.WINFUNCTYPE(hresult, ctypes.c_void_p, wintypes.HWND,
                                             ctypes.c_ulonglong, ctypes.c_ulonglong)(table[9])
            self._state = ctypes.WINFUNCTYPE(hresult, ctypes.c_void_p, wintypes.HWND,
                                             ctypes.c_int)(table[10])
            if self._init(pointer) == 0:                    # HrInit
                self._list = pointer
        except Exception:
            self._list = None

    def progress(self, state: str, value: float = 0.0) -> bool:
        """The button's bar: "normal" filled to value (0-1), "indeterminate", "none"…
        Asked again with what it shows already, it does nothing."""
        if self._list is None or self._shown == (state, value):
            return False
        hwnd = self._ctypes.c_void_p(self.hwnd)
        ok = self._state(self._list, hwnd, _PROGRESS[state]) == 0
        if state in ("normal", "paused", "error"):
            ok = self._value(self._list, hwnd, int(value * 1000), 1000) == 0 and ok
        self._shown = (state, value)
        return ok

    def in_front(self) -> bool:
        if os.name != "nt" or not self.hwnd:
            return True
        return int(self._user32.GetForegroundWindow() or 0) == self.hwnd

    def flash(self) -> bool:
        """Flash the button until the window is brought forward."""
        if os.name != "nt" or not self.hwnd:
            return False
        ctypes = self._ctypes
        from ctypes import wintypes

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND),
                        ("dwFlags", wintypes.DWORD), ("uCount", wintypes.UINT),
                        ("dwTimeout", wintypes.DWORD)]

        info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), self.hwnd, 0x2 | 0xC, 0, 0)  # TRAY|TIMERNOFG
        self._user32.FlashWindowEx(ctypes.byref(info))
        return True


def watch_jobs(url: str, hwnd: int, stop: threading.Event,
               taskbar: Callable[[int], "Taskbar"] = Taskbar,
               fetch: Callable[[str], Optional[List[dict]]] = fetch_jobs,
               every: float = TASKBAR_EVERY) -> None:
    """Until stop is set: the running dub's progress on the button, and a flash when a dub
    finishes, fails or waits for review while the window is behind others."""
    button = taskbar(hwnd)
    before: Optional[Dict[str, str]] = None
    while not stop.wait(every):
        jobs = fetch(url)
        if jobs is None:                    # the server isn't up yet, or is busy
            continue
        button.progress(*taskbar_state(jobs))
        if before is not None and calls_back(before, jobs) and not button.in_front():
            button.flash()
        before = {job.get("id"): job.get("status") for job in jobs}
    button.progress("none")


def follow_system_theme(repaint: Callable[[], None]) -> None:
    """pywebview paints the title bar for Windows' theme again whenever that changes; paint it
    for the console's after it (handlers run in the order they were added)."""
    if os.name != "nt":
        return
    try:
        # pythonnet, which pywebview's WinForms backend has loaded
        from Microsoft.Win32 import SystemEvents
        SystemEvents.UserPreferenceChanged += lambda sender, args: repaint()
    except Exception:
        pass


LOCAL_ORIGINS = ("http://127.0.0.1:", "http://localhost:")


def clipboard_rule(read_kind, allow) -> Callable:
    """WebView2's PermissionRequested handler: the console's own right-click Paste reads the
    clipboard, which WebView2 would ask the user about ("127.0.0.1 wants to see text and
    images copied to the clipboard"). Voxa's local server may read it; anything else asks."""
    def requested(sender, args) -> None:
        if args.PermissionKind == read_kind and str(args.Uri).startswith(LOCAL_ORIGINS):
            args.State = allow
    return requested


def allow_clipboard_read(window) -> bool:
    """Add clipboard_rule to the window's WebView2, on its UI thread (WebView2 refuses others)."""
    if os.name != "nt":
        return False
    try:
        from Microsoft.Web.WebView2.Core import (
            CoreWebView2PermissionKind,
            CoreWebView2PermissionState,
        )
        from System import Action
        rule = clipboard_rule(CoreWebView2PermissionKind.ClipboardRead,
                              CoreWebView2PermissionState.Allow)

        def add() -> None:
            window.native.webview.CoreWebView2.PermissionRequested += rule

        window.native.Invoke(Action(add))
        return True
    except Exception:
        return False


def open_folder(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(path))                 # noqa: S606 (our own folder, no arguments)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True
    except OSError:
        return False


def _shell_version() -> Optional[str]:
    try:
        from importlib.metadata import version
        return version("voxa-dub")
    except Exception:
        return None


def let_explorer_front() -> bool:
    """Pass on the right to come to the front, which Windows gives the app in front, to File
    Explorer's own process (the desktop's shell): its window shows a dub's file. The same as
    voxa_server.let_explorer_front, which this process doesn't import."""
    if sys.platform != "win32":
        return False
    import ctypes
    user32 = ctypes.windll.user32
    pid = ctypes.c_ulong()
    shell = user32.GetShellWindow()
    if not shell or not user32.GetWindowThreadProcessId(shell, ctypes.byref(pid)):
        return False
    return bool(user32.AllowSetForegroundWindow(pid.value))


class StudioApi:
    """What the console may ask of the window it is in, as window.pywebview.api.*: paint the
    title bar for its theme, open the log folder, say what it runs on, let Explorer's window
    come to the front. None of it takes a path
    or a command, so no page can make it open anything else. pywebview hands the page public
    methods only, so the state is kept in private attributes."""

    def __init__(self, workspace: Path, theme: str = "dark") -> None:
        self._workspace = workspace
        self._theme = theme
        self._window = None
        self._renderer: Optional[str] = None

    def _from_voxa(self) -> bool:
        """The window shows Voxa's own page or its local server, never anything else."""
        try:
            url = self._window.get_current_url() if self._window is not None else None
        except Exception:
            return False
        return (not url or url.startswith(("http://127.0.0.1:", "http://localhost:", "data:"))
                or url == "about:blank")

    def set_chrome(self, theme: str) -> bool:
        if theme not in CHROME:
            return False
        self._theme = theme
        data = read_place(self._workspace)
        if data.get("theme") != theme:
            data["theme"] = theme
            _write_place(self._workspace, data)
        return paint_window(self._window, theme) if self._window is not None else False

    def open_logs(self) -> bool:
        return self._from_voxa() and open_folder(self._workspace)

    def app_info(self) -> dict:
        import platform
        return {"shell": _shell_version(), "renderer": self._renderer, "os": platform.platform()}

    def let_explorer_front(self) -> bool:
        """Asked just before the server shows a dub's file: this window, in front because its
        button was clicked, lets File Explorer's window come to the front over it. Opens
        nothing itself."""
        return self._from_voxa() and let_explorer_front()


def say_no_webview2(language: str) -> None:
    text = NO_WEBVIEW2.get(language, NO_WEBVIEW2["en"]).format(url=WEBVIEW2_URL)
    if os.name == "nt":
        import ctypes
        user32 = ctypes.WinDLL("user32")
        user32.MessageBoxW.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                                       ctypes.c_uint)
        # INFORMATION, SETFOREGROUND, TOPMOST: there's no window yet to own it
        user32.MessageBoxW(None, text, TITLE, 0x40 | 0x10000 | 0x40000)
    print(f"⚠️  {text}", file=sys.stderr)


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
                waiting: str = "", jobs_url: Optional[str] = None) -> bool:
    """Show a window and return once it is closed: on `url`, or on a page saying `waiting`
    while `when_shown` (run in a thread of its own once the window is up) gets it there.
    False when no window could be opened, so the caller falls back to the browser."""
    try:
        import webview
    except Exception:                       # not installed, or no GUI backend to import
        return False
    workspace = storage.parent
    language = system_language()
    saved = read_place(workspace)
    theme = saved.get("theme") if saved.get("theme") in CHROME else "dark"
    api = StudioApi(workspace, theme)
    try:
        try:
            screens = list(webview.screens)
        except Exception:
            screens = []
        place = window_place(saved, screens)
        state = {"now": "maximized" if place.get("maximized") else "normal"}
        webview.settings["ALLOW_DOWNLOADS"] = True      # a Save dialog, starting in Downloads
        window = webview.create_window(
            TITLE, f"{url}/" if url else None,
            html=None if url else page(waiting, theme, HINT[language]),
            js_api=api, min_size=MIN_SIZE, background_color=PAGE_COLORS[theme][0],
            text_select=True, **place)
        api._window = window

        def initialized(renderer: str) -> bool:
            # Without WebView2 (or with a .NET older than 4.6.2) pywebview falls back to
            # Internet Explorer's engine, which shows the console as a blank page: no window
            # then, and the browser instead.
            api._renderer = renderer
            return renderer != "mshtml"

        watching = threading.Event()

        def shown() -> None:
            paint_window(window, api._theme)
            follow_system_theme(lambda: paint_window(window, api._theme))
            if jobs_url and os.name == "nt":
                try:
                    hwnd = int(window.native.Handle.ToInt64())
                except Exception:
                    return
                threading.Thread(target=watch_jobs, args=(jobs_url, hwnd, watching),
                                 name="voxa-taskbar", daemon=True).start()

        def loaded() -> None:
            # WebView2 is ready once a page has loaded (the splash, first).
            if not state.get("clipboard"):
                state["clipboard"] = allow_clipboard_read(window)

        def closing() -> bool:
            if not may_close_now(window):
                return False
            try:
                remember_place(workspace, window.x, window.y, window.width, window.height,
                               state["now"])
            except Exception:
                pass
            watching.set()
            return True

        window.events.initialized += initialized
        window.events.shown += shown
        window.events.loaded += loaded
        window.events.closing += closing
        window.events.maximized += lambda: state.update(now="maximized")
        window.events.minimized += lambda: state.update(now="minimized")
        window.events.restored += lambda: state.update(now="normal")
        # Not private: the console keeps its language, theme and settings between launches,
        # here in the Voxa folder rather than pywebview's.
        webview.start(when_shown, (window,) if when_shown else None,
                      private_mode=False, storage_path=str(storage), icon=window_icon())
    except Exception as e:                  # e.g. Linux without GTK or Qt
        print(f"⚠️  Couldn't open a window ({e}); opening the browser instead", file=sys.stderr)
        return False
    if api._renderer == "mshtml":
        say_no_webview2(language)
        return False
    return True


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
            theme = read_place(workspace).get("theme")
            window.load_html(page(FAILED[language].format(log=log if hidden else "the terminal"),
                                  theme if theme in CHROME else "dark",
                                  button=OPEN_LOGS[language]))

    def may_close_now(window) -> bool:
        if server is None or not outcome["ready"]:   # not ours, or nothing running yet
            return True
        return may_close(dubs_running(url), lambda question: ask(window, question), language)

    try:
        shown = not args.browser and open_window(
            None if server else url, workspace / "webview", may_close_now,
            when_shown if server else None, STARTING[language], jobs_url=url)
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
