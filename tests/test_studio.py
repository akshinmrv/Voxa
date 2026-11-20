"""Voxa Studio: the console in a window of its own, falling back to the browser."""
import http.server
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import voxa_studio as studio


# ── closing ──────────────────────────────────────────────
def test_with_nothing_running_it_closes_without_asking():
    asked = []
    assert studio.may_close(0, asked.append, "en") is True and asked == []


@pytest.mark.parametrize("language, word", [("en", "Close anyway?"), ("az", "bağlansın"),
                                            ("tr", "kapatılsın")])
def test_with_dubs_running_it_asks_first(language, word):
    asked = []
    assert studio.may_close(2, lambda q: asked.append(q) or False, language) is False
    assert "2" in asked[0] and word in asked[0]
    assert studio.may_close(1, lambda q: True, language) is True


@pytest.mark.skipif(os.name == "nt", reason="Windows reads the language from the user's locale")
@pytest.mark.parametrize("lang, expected", [("tr_TR.UTF-8", "tr"), ("az_AZ.UTF-8", "az"),
                                            ("de_DE.UTF-8", "en"), ("", "en")])
def test_the_question_follows_the_locale(monkeypatch, lang, expected):
    for name in ("LC_ALL", "LC_MESSAGES"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANG", lang)
    assert studio.system_language() == expected


# ── the server ───────────────────────────────────────────
def test_a_taken_port_gives_way_to_a_free_one():
    import socket
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        busy = taken.getsockname()[1]
        assert studio.pick_port(busy) != busy


def test_the_launcher_gives_the_server_a_console_of_its_own(monkeypatch, tmp_path):
    # pythonw.exe has no console; python.exe beside it gets one, hidden, which the dubs share.
    (tmp_path / "python.exe").write_bytes(b"")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "pythonw.exe"))
    cmd = studio.server_command(8123, ["--env-file", "x.env"])
    assert cmd[0] == str(tmp_path / "python.exe")
    assert cmd[3:] == ["serve", "--port", "8123", "--env-file", "x.env"]
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python3"))
    assert studio.server_command(1, [])[0] == str(tmp_path / "python3")


@pytest.fixture
def fake_voxa():
    """A local server answering /api/health and /api/jobs as voxa serve would."""
    state = {"jobs": []}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = ({"status": "ok", "version": "9.9.9"} if self.path == "/api/health"
                    else {"jobs": state["jobs"]})
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{server.server_address[1]}"
    yield state
    server.shutdown()


def test_a_second_launch_finds_the_studio_already_running(tmp_path, fake_voxa):
    workspace = tmp_path / ".voxa_serve"
    assert studio.running_studio(workspace) is None                   # nothing yet
    workspace.mkdir()
    (workspace / "studio.json").write_text(json.dumps({"url": fake_voxa["url"]}))
    assert studio.running_studio(workspace) == fake_voxa["url"]
    (workspace / "studio.json").write_text(json.dumps({"url": "http://127.0.0.1:9"}))
    assert studio.running_studio(workspace) is None                   # stale: nobody answers


def test_it_counts_the_dubs_still_going(fake_voxa):
    fake_voxa["jobs"] = [{"status": "done"}, {"status": "running"}, {"status": "queued"},
                         {"status": "failed"}]
    assert studio.dubs_running(fake_voxa["url"]) == 2
    assert studio.dubs_running("http://127.0.0.1:9") == 0


# ── the window, or the browser ───────────────────────────
def test_without_pywebview_there_is_no_window(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "webview", None)              # import fails
    assert studio.open_window("http://127.0.0.1:1", tmp_path, lambda w: True) is False


class FakeServer:
    instances = []

    def __init__(self, workspace, port, extra, hidden):
        self.url = f"http://127.0.0.1:{port}"
        self.stopped = False
        self.process = type("P", (), {"wait": lambda self: 0})()
        FakeServer.instances.append(self)

    def wait_ready(self):
        return True

    def stop(self):
        self.stopped = True


@pytest.fixture
def launch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(studio, "Server", FakeServer)
    monkeypatch.setattr(studio, "pick_port", lambda: 8123)
    opened = []
    monkeypatch.setattr(studio.webbrowser, "open", opened.append)
    FakeServer.instances = []
    return tmp_path / ".voxa_serve", opened


class FakeWindow:
    def __init__(self):
        self.loaded = []

    def load_url(self, url):
        self.loaded.append(("url", url))

    def load_html(self, html):
        self.loaded.append(("html", html))


def test_the_window_shows_at_once_and_moves_to_the_console_when_ready(launch, monkeypatch):
    workspace, browser = launch
    seen = {}

    def window(url, storage, may_close_now, when_shown, waiting, jobs_url=None):
        seen.update(url=url, storage=storage, waiting=waiting, jobs_url=jobs_url)
        win = FakeWindow()
        when_shown(win)                                       # pywebview runs it once shown
        seen["loaded"] = win.loaded
        seen["marker"] = json.loads((workspace / "studio.json").read_text())["url"]
        return True

    monkeypatch.setattr(studio, "open_window", window)
    monkeypatch.setattr(studio, "system_language", lambda: "az")
    assert studio.run([]) == 0
    assert seen["url"] is None and seen["waiting"] == "Başlayır…"     # its own page first
    assert seen["loaded"] == [("url", "http://127.0.0.1:8123/")]
    assert seen["storage"] == workspace / "webview" and seen["marker"] == "http://127.0.0.1:8123"
    assert seen["jobs_url"] == "http://127.0.0.1:8123"       # the taskbar watches its dubs
    assert FakeServer.instances[0].stopped and browser == []
    assert not (workspace / "studio.json").exists()


def test_without_a_window_the_browser_opens(launch, monkeypatch):
    workspace, browser = launch
    monkeypatch.setattr(studio, "open_window", lambda *a, **k: False)
    assert studio.run([]) == 0
    assert browser == ["http://127.0.0.1:8123/"] and FakeServer.instances[0].stopped


def test_browser_asks_for_no_window(launch, monkeypatch):
    workspace, browser = launch
    monkeypatch.setattr(studio, "open_window", lambda *a, **k: pytest.fail("no window asked for"))
    assert studio.run(["--browser"]) == 0 and browser == ["http://127.0.0.1:8123/"]


def test_a_second_launch_opens_a_window_on_the_first_ones_server(launch, monkeypatch):
    workspace, browser = launch
    monkeypatch.setattr(studio, "running_studio", lambda ws: "http://127.0.0.1:8000")
    calls = []
    monkeypatch.setattr(studio, "open_window",
                        lambda url, storage, may, when_shown, waiting, jobs_url=None:
                        calls.append((url, when_shown)) or True)
    assert studio.run([]) == 0
    assert calls == [("http://127.0.0.1:8000", None)] and FakeServer.instances == []


class Broken(FakeServer):
    def wait_ready(self):
        return False


def test_a_server_that_wont_start_says_so_in_the_window(launch, monkeypatch):
    workspace, browser = launch
    monkeypatch.setattr(studio, "Server", Broken)
    monkeypatch.setattr(studio, "system_language", lambda: "en")
    pages = []

    def window(url, storage, may_close_now, when_shown, waiting, jobs_url=None):
        win = FakeWindow()
        when_shown(win)
        pages.extend(win.loaded)
        return True

    monkeypatch.setattr(studio, "open_window", window)
    assert studio.run([], hidden=True) == 1
    kind, html = pages[0]
    assert kind == "html" and "didn&#x27;t start" in html and "studio.log" in html
    assert FakeServer.instances[0].stopped


def test_a_server_that_wont_start_is_reported_without_a_window(launch, monkeypatch, capsys):
    monkeypatch.setattr(studio, "Server", Broken)
    monkeypatch.setattr(studio, "open_window", lambda *a, **k: False)
    assert studio.run([]) == 1
    assert "didn't start" in capsys.readouterr().err and FakeServer.instances[0].stopped


# ── Windows: the server and what it starts end together ──
def _alive(pid: int) -> bool:
    import ctypes
    k32 = ctypes.WinDLL("kernel32")
    k32.OpenProcess.restype = ctypes.c_void_p
    handle = k32.OpenProcess(0x1000, False, pid)            # QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    code = ctypes.c_ulong()
    k32.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))
    k32.CloseHandle(ctypes.c_void_p(handle))
    return code.value == 259                                 # STILL_ACTIVE


@pytest.mark.skipif(os.name != "nt", reason="job objects are Windows'")
def test_closing_ends_the_server_and_the_dubs_it_started():
    child = subprocess.Popen(
        [sys.executable, "-c",
         "import subprocess, sys, time\n"
         "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
         "print(p.pid, flush=True)\n"
         "time.sleep(120)"],
        stdout=subprocess.PIPE, text=True)
    together = studio._KillTogether(child.pid)
    grandchild = int(child.stdout.readline())
    assert _alive(child.pid) and _alive(grandchild)
    together.close()
    child.wait(timeout=10)
    assert not _alive(grandchild)


def test_the_launcher_writes_to_a_log_not_to_a_missing_console(tmp_path, monkeypatch):
    # pythonw.exe gives no stdout or stderr, and a library writing to them stops the window.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(studio, "run", lambda argv, hidden: print("hello") or 0)
    with pytest.raises(SystemExit):
        studio.main()
    log = Path(tmp_path / ".voxa_serve" / "studio-window.log")
    sys.stdout.flush()
    assert log.read_text(encoding="utf-8") == "hello\n"


# ── Voxa's icon ──────────────────────────────────────────
def test_the_package_carries_voxas_icon():
    import struct

    import voxa_ui
    ico = voxa_ui.icon_path("ico").read_bytes()
    reserved, kind, count = struct.unpack("<HHH", ico[:6])
    sizes = sorted((ico[6 + 16 * i] or 256) for i in range(count))
    assert (reserved, kind) == (0, 1) and sizes == [16, 20, 24, 32, 40, 48, 64, 256]
    assert voxa_ui.icon_path("png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize("windows, suffix", [(True, ".ico"), (False, ".png")])
def test_each_system_gets_the_icon_it_reads(windows, suffix):
    icon = studio.window_icon(windows)
    assert icon.endswith("voxa" + suffix) and Path(icon).is_file()


class _Event:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self


class _Window:
    """pywebview's window, as far as open_window uses it."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.events = type("E", (), {})()
        for name in ("initialized", "shown", "loaded", "closing", "maximized", "minimized",
                     "restored"):
            setattr(self.events, name, _Event())
        self.x, self.y, self.width, self.height = 120, 80, 1500, 900


def _fake_webview(monkeypatch, start=None, screens=()):
    made = {}
    fake = type(sys)("webview")
    fake.settings = {}
    fake.screens = list(screens)

    def create_window(*args, **kwargs):
        made["window"] = _Window(**kwargs)
        return made["window"]

    fake.create_window = create_window
    fake.start = start or (lambda *a, **kw: made.update(started=kw))
    monkeypatch.setitem(sys.modules, "webview", fake)
    return made


def test_the_window_gets_voxas_icon(monkeypatch, tmp_path):
    made = _fake_webview(monkeypatch)
    assert studio.open_window("http://127.0.0.1:1", tmp_path, lambda w: True) is True
    started = made["started"]
    assert started["icon"] == studio.window_icon() and Path(started["icon"]).is_file()
    assert started["private_mode"] is False


# ── the window's place, theme and title bar ──────────────
class _Screen:
    def __init__(self, x, y, width, height):
        self.x, self.y, self.width, self.height = x, y, width, height


def test_the_first_window_opens_at_the_default_size():
    assert studio.window_place({}, [_Screen(0, 0, 1920, 1080)]) == {"width": 1280, "height": 840}


def test_the_window_opens_where_it_was_left():
    saved = {"x": 2000, "y": 40, "width": 1500, "height": 900, "maximized": True}
    screens = [_Screen(0, 0, 1920, 1080), _Screen(1920, 0, 2560, 1440)]
    assert studio.window_place(saved, screens) == {
        "width": 1500, "height": 900, "x": 2000, "y": 40, "maximized": True}


def test_a_window_left_on_an_unplugged_monitor_comes_back_centred():
    saved = {"x": 2000, "y": 40, "width": 1500, "height": 900}
    assert studio.window_place(saved, [_Screen(0, 0, 1920, 1080)]) == {
        "width": 1500, "height": 900}


def test_a_window_is_never_restored_smaller_than_the_minimum():
    place = studio.window_place({"width": 300, "height": True, "x": "a"}, [])
    assert place == {"width": 1280, "height": 840}            # a bool isn't a size
    assert studio.window_place({"width": 300, "height": 200}, []) == {"width": 960, "height": 640}


def test_closing_remembers_the_place_but_not_a_minimized_one(tmp_path):
    studio.remember_place(tmp_path, 10, 20, 1300, 850, "normal")
    assert studio.read_place(tmp_path) == {"x": 10, "y": 20, "width": 1300, "height": 850,
                                           "maximized": False}
    studio.remember_place(tmp_path, 0, 0, 2560, 1400, "maximized")   # keeps the size to go back to
    kept = studio.read_place(tmp_path)
    assert kept["width"] == 1300 and kept["maximized"] is True
    studio.remember_place(tmp_path, -32000, -32000, 160, 28, "minimized")
    assert studio.read_place(tmp_path)["x"] == 10


def test_open_window_restores_the_place_and_saves_it_on_close(monkeypatch, tmp_path):
    workspace = tmp_path / ".voxa_serve"
    studio._write_place(workspace, {"x": 50, "y": 60, "width": 1400, "height": 860,
                                    "theme": "light"})
    made = _fake_webview(monkeypatch, screens=[_Screen(0, 0, 1920, 1080)])
    assert studio.open_window(None, workspace / "webview", lambda w: True, None, "…") is True
    window = made["window"]
    kw = window.kwargs
    assert (kw["x"], kw["y"], kw["width"], kw["height"]) == (50, 60, 1400, 860)
    assert kw["background_color"] == "#FFFFFF" and "#FFFFFF" in kw["html"]  # last theme, no flash
    assert isinstance(kw["js_api"], studio.StudioApi) and kw["min_size"] == (960, 640)
    (closing,) = window.events.closing.handlers
    assert closing() is True
    kept = studio.read_place(workspace)
    assert kept["width"] == 1500 and kept["theme"] == "light"


def test_a_cancelled_close_saves_nothing(monkeypatch, tmp_path):
    made = _fake_webview(monkeypatch)
    studio.open_window(None, tmp_path / "webview", lambda w: False, None, "…")
    (closing,) = made["window"].events.closing.handlers
    assert closing() is False and studio.read_place(tmp_path) == {}


def test_without_webview2_the_browser_opens_and_says_why(monkeypatch, tmp_path):
    def start(*args, **kwargs):
        # pywebview aborts the window when an `initialized` handler answers False.
        (handler,) = made["window"].events.initialized.handlers
        assert handler("mshtml") is False

    made = _fake_webview(monkeypatch, start=lambda *a, **kw: start())
    said = []
    monkeypatch.setattr(studio, "say_no_webview2", said.append)
    monkeypatch.setattr(studio, "system_language", lambda: "tr")
    assert studio.open_window("http://127.0.0.1:1", tmp_path, lambda w: True) is False
    assert said == ["tr"]
    assert "WebView2" in studio.NO_WEBVIEW2["az"] and studio.WEBVIEW2_URL.startswith("https://")


def test_webview2_opens_the_window(monkeypatch, tmp_path):
    made = _fake_webview(monkeypatch, start=lambda *a, **kw: (
        made["window"].events.initialized.handlers[0]("edgechromium")))
    monkeypatch.setattr(studio, "say_no_webview2", lambda lang: pytest.fail("not asked"))
    assert studio.open_window("http://127.0.0.1:1", tmp_path, lambda w: True) is True


class _Dwm:
    def __init__(self, refuse=()):
        self.set, self.refuse = {}, refuse

    def DwmSetWindowAttribute(self, hwnd, name, data, size):        # noqa: N802 (Win32's name)
        self.set[name] = data._obj.value
        return -2147024809 if name in self.refuse else 0             # E_INVALIDARG


@pytest.mark.skipif(os.name != "nt", reason="the title bar is painted on Windows")
@pytest.mark.parametrize("theme, dark, caption, text", [
    ("dark", 1, 0x0F0D0D, 0xFAFAFA), ("light", 0, 0xF7F6F6, 0x0B0A0A)])
def test_the_title_bar_takes_the_consoles_colors(theme, dark, caption, text):
    dwm = _Dwm()
    assert studio.paint_title_bar(1234, theme, dwm) is True
    # dark mode, no Mica, then caption / text / border as COLORREF (0x00BBGGRR)
    assert dwm.set[20] == dark and dwm.set[38] == 1
    assert dwm.set[35] == caption and dwm.set[36] == text


@pytest.mark.skipif(os.name != "nt", reason="the title bar is painted on Windows")
def test_windows_10_keeps_its_own_title_bar_colors():
    dwm = _Dwm(refuse={34, 35, 36})
    assert studio.paint_title_bar(1234, "dark", dwm) is False and dwm.set[20] == 1


def test_the_console_asks_for_a_theme_and_it_is_kept(tmp_path):
    api = studio.StudioApi(tmp_path)
    assert api.set_chrome("purple") is False and studio.read_place(tmp_path) == {}
    api.set_chrome("light")
    assert studio.read_place(tmp_path) == {"theme": "light"} and api._theme == "light"


def test_the_bridge_opens_only_voxas_own_folder(monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(studio, "open_folder", lambda path: opened.append(path) or True)
    api = studio.StudioApi(tmp_path)
    api._window = type("W", (), {"get_current_url": lambda self: "http://127.0.0.1:8000/en/app/"})()
    assert api.open_logs() is True and opened == [tmp_path]
    api._window = type("W", (), {"get_current_url": lambda self: "https://example.com/"})()
    assert api.open_logs() is False and opened == [tmp_path]
    # pywebview hands the page public methods only: what it keeps stays out of reach.
    public = {n for n in dir(api) if not n.startswith("_")}
    assert public == {"set_chrome", "open_logs", "app_info", "let_explorer_front"}
    assert set(api.app_info()) == {"shell", "renderer", "os"}


def test_only_voxas_page_lets_explorer_to_the_front(monkeypatch, tmp_path):
    asked = []
    monkeypatch.setattr(studio, "let_explorer_front", lambda: asked.append(1) or True)
    api = studio.StudioApi(tmp_path)
    api._window = type("W", (), {"get_current_url": lambda self: "https://example.com/"})()
    assert api.let_explorer_front() is False and asked == []
    api._window = type("W", (), {"get_current_url": lambda self: "http://127.0.0.1:8000/en/app/"})()
    assert api.let_explorer_front() is True and asked == [1]


def test_letting_explorer_forward_is_windows_only_and_never_raises(monkeypatch):
    # From a process that isn't in front (as here), Windows refuses it: False, no error.
    assert studio.let_explorer_front() in (True, False)
    monkeypatch.setattr(studio.sys, "platform", "linux")
    assert studio.let_explorer_front() is False


def test_the_starting_page_explains_a_long_wait_and_stays_still_if_asked():
    html = studio.page("Başlayır…", "dark", studio.HINT["az"])
    assert "kitabxanalarını" in html and "10s forwards" in html
    assert "prefers-reduced-motion" in html and "#0A0A0B" in html
    assert "<button" not in html
    # Fills the window exactly: no scrollbar on a page that has nothing to scroll.
    assert "box-sizing:border-box" in html and "overflow:hidden" in html
    assert "color-scheme:dark" in html and "color-scheme:light" in studio.page("x", "light")


def test_the_failure_page_offers_the_log_folder(launch, monkeypatch):
    workspace, browser = launch
    studio._write_place(workspace, {"theme": "light"})
    monkeypatch.setattr(studio, "Server", Broken)
    monkeypatch.setattr(studio, "system_language", lambda: "az")
    pages = []

    def window(url, storage, may_close_now, when_shown, waiting, jobs_url=None):
        win = FakeWindow()
        when_shown(win)
        pages.extend(win.loaded)
        return True

    monkeypatch.setattr(studio, "open_window", window)
    studio.run([], hidden=True)
    html = pages[0][1]
    assert "Loq qovluğunu aç" in html and "pywebview.api.open_logs()" in html
    assert "#FFFFFF" in html                                   # in the theme it was left in


def test_only_voxas_own_server_may_read_the_clipboard():
    # WebView2 would ask the user each time the console's right-click Paste reads it.
    rule = studio.clipboard_rule("ClipboardRead", "Allow")

    def asked(kind, uri):
        args = type("A", (), {"PermissionKind": kind, "Uri": uri, "State": "Default"})()
        rule(None, args)
        return args.State

    assert asked("ClipboardRead", "http://127.0.0.1:8000/en/app/settings/") == "Allow"
    assert asked("ClipboardRead", "https://example.com/") == "Default"        # still asks
    assert asked("Microphone", "http://127.0.0.1:8000/") == "Default"         # only the clipboard


def test_without_webview2s_assembly_the_clipboard_rule_is_skipped():
    assert studio.allow_clipboard_read(object()) is False


# ── The taskbar button (S7) ──

def test_the_button_shows_the_running_dubs_step():
    assert studio.taskbar_state([{"status": "running", "step": 3}]) == ("normal", 3 / 7)
    # Several running: the oldest, which the server lists first. A step not yet said: 1.
    assert studio.taskbar_state([{"status": "done"}, {"status": "running", "step": 0},
                                 {"status": "running", "step": 6}]) == ("normal", 1 / 7)
    assert studio.taskbar_state([{"status": "queued"}, {"status": "done"}]) == \
        ("indeterminate", 0.0)
    assert studio.taskbar_state([{"status": "done"}, {"status": "review"}]) == ("none", 0.0)


def test_who_calls_the_user_back():
    before = {"a": "running", "b": "running", "c": "queued", "d": "running", "e": "done"}
    jobs = [{"id": "a", "status": "done"}, {"id": "b", "status": "review"},
            {"id": "c", "status": "failed"}, {"id": "d", "status": "failed", "cancelled": True},
            {"id": "e", "status": "done"}, {"id": "f", "status": "done"}]
    # Finished, waiting for review, failed: yes. Stopped by the user, done before, new: no.
    assert studio.calls_back(before, jobs) == ["a", "b", "c"]


class _Button:
    def __init__(self, hwnd, front=False):
        self.hwnd, self.front, self.shown, self.flashes = hwnd, front, [], 0

    def progress(self, state, value=0.0):
        self.shown.append((state, round(value, 3)))

    def in_front(self):
        return self.front

    def flash(self):
        self.flashes += 1


def _watch(answers, front=False):
    """Run watch_jobs over a list of answers from the server, one per look."""
    import threading
    stop, made = threading.Event(), []
    answers = list(answers)

    def fetch(url):
        if not answers:
            stop.set()
            return None
        return answers.pop(0)

    def taskbar(hwnd):
        made.append(_Button(hwnd, front))
        return made[-1]

    studio.watch_jobs("http://127.0.0.1:1", 42, stop, taskbar, fetch, every=0.001)
    return made[0]


def test_watching_the_dubs_moves_the_bar_and_flashes_once_done():
    button = _watch([
        [{"id": "a", "status": "queued", "step": 0}],
        None,                                           # the server busy: nothing changes
        [{"id": "a", "status": "running", "step": 3}],
        [{"id": "a", "status": "done", "step": 7}],
        [{"id": "a", "status": "done", "step": 7}],
    ])
    assert button.hwnd == 42
    assert button.shown == [("indeterminate", 0.0), ("normal", 0.429), ("none", 0.0),
                            ("none", 0.0), ("none", 0.0)]
    assert button.flashes == 1                          # once, when it finished


def test_no_flash_while_the_window_is_in_front():
    button = _watch([[{"id": "a", "status": "running", "step": 5}],
                     [{"id": "a", "status": "failed", "step": 5}]], front=True)
    assert button.flashes == 0


@pytest.mark.skipif(os.name != "nt", reason="the taskbar is Windows'")
def test_windows_gives_the_taskbar_list():
    import ctypes
    button = studio.Taskbar(ctypes.windll.user32.GetDesktopWindow())
    assert button._list is not None                     # ITaskbarList3, HrInit S_OK
    assert studio.Taskbar(0)._list is None              # no window: nothing to do
