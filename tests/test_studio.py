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

    def window(url, storage, may_close_now, when_shown, waiting):
        seen.update(url=url, storage=storage, waiting=waiting)
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
    assert FakeServer.instances[0].stopped and browser == []
    assert not (workspace / "studio.json").exists()


def test_without_a_window_the_browser_opens(launch, monkeypatch):
    workspace, browser = launch
    monkeypatch.setattr(studio, "open_window", lambda *a: False)
    assert studio.run([]) == 0
    assert browser == ["http://127.0.0.1:8123/"] and FakeServer.instances[0].stopped


def test_browser_asks_for_no_window(launch, monkeypatch):
    workspace, browser = launch
    monkeypatch.setattr(studio, "open_window", lambda *a: pytest.fail("no window asked for"))
    assert studio.run(["--browser"]) == 0 and browser == ["http://127.0.0.1:8123/"]


def test_a_second_launch_opens_a_window_on_the_first_ones_server(launch, monkeypatch):
    workspace, browser = launch
    monkeypatch.setattr(studio, "running_studio", lambda ws: "http://127.0.0.1:8000")
    calls = []
    monkeypatch.setattr(studio, "open_window",
                        lambda url, storage, may, when_shown, waiting:
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

    def window(url, storage, may_close_now, when_shown, waiting):
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
    monkeypatch.setattr(studio, "open_window", lambda *a: False)
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
