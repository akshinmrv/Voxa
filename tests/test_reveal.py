"""Show in folder (S5, BE-6): the server shows a dub's file in its own file manager, only for
a console on the same machine with a desktop, and only files in the dub's own folder."""
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import voxa_server as srv  # noqa: E402


@pytest.fixture
def ws(tmp_path, monkeypatch):
    workspace = tmp_path / ".voxa_serve"
    monkeypatch.setattr(srv, "WORKSPACE", workspace)
    monkeypatch.setattr(srv, "JOBS_DIR", workspace / "jobs")
    monkeypatch.setattr(srv, "JOBS", {})
    return workspace


@pytest.fixture
def launched(monkeypatch):
    """What the server would have started, instead of starting it."""
    calls = []
    monkeypatch.setattr(srv, "_launch", calls.append)
    return calls


def _local(monkeypatch, desktop="/usr/bin/xdg-open"):
    # TestClient's caller is "testclient": count it as this machine, with this desktop.
    monkeypatch.setattr(srv, "_LOCAL_HOSTS", {"testclient"})
    monkeypatch.setattr(srv, "_desktop_opener", lambda: desktop)


def _done_job(ws, job_id="j1"):
    folder = ws / "jobs" / "0123456789abcdef"
    (folder / "talk_work").mkdir(parents=True)
    video = folder / "talk_dubbed_de.mp4"
    video.write_bytes(b"\0" * 64)
    srt = folder / "talk_work" / "captions_de.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHallo\n", encoding="utf-8")
    config = srv.JobConfigModel(targetLang="de", translator="google", tts="edge")
    job = srv.Job(id=job_id, file_name="talk.mp4", config=config, work_dir=folder,
                  status="done", result_video=video, result_srt=srt)
    srv.JOBS[job_id] = job
    return job


def test_health_says_whether_it_can_show_files(ws, monkeypatch):
    client = TestClient(srv.app)
    _local(monkeypatch)
    assert client.get("/api/health").json()["canReveal"] is True
    monkeypatch.setattr(srv, "_desktop_opener", lambda: None)       # a container, no display
    assert client.get("/api/health").json()["canReveal"] is False
    _local(monkeypatch)
    monkeypatch.setattr(srv, "_LOCAL_HOSTS", {"127.0.0.1"})         # a caller elsewhere
    assert client.get("/api/health").json()["canReveal"] is False


def test_shows_the_video_the_subtitles_or_the_folder(ws, monkeypatch, launched):
    job = _done_job(ws)
    _local(monkeypatch)
    client = TestClient(srv.app)
    for kind, name in (("video", "talk_dubbed_de.mp4"), ("srt", "captions_de.srt"),
                       ("folder", "0123456789abcdef")):
        r = client.post(f"/api/jobs/j1/reveal?file={kind}")
        assert r.status_code == 200, r.text
        assert r.json() == {"shown": name}
    # The paths the server knows, each as this platform shows it (forms checked below).
    assert launched == [srv.reveal_command("/usr/bin/xdg-open", p)
                        for p in (job.result_video, job.result_srt, job.work_dir)]


def test_refused_in_a_container_or_from_elsewhere(ws, monkeypatch, launched):
    _done_job(ws)
    client = TestClient(srv.app)
    _local(monkeypatch, desktop=None)
    assert client.post("/api/jobs/j1/reveal").status_code == 409
    _local(monkeypatch)
    monkeypatch.setattr(srv, "_LOCAL_HOSTS", {"127.0.0.1"})
    assert client.post("/api/jobs/j1/reveal").status_code == 409
    assert launched == []


def test_a_missing_file_or_one_outside_the_dub_isnt_shown(ws, monkeypatch, launched, tmp_path):
    job = _done_job(ws)
    _local(monkeypatch)
    client = TestClient(srv.app)
    job.result_srt.unlink()
    assert client.post("/api/jobs/j1/reveal?file=srt").status_code == 404
    # A record pointing somewhere else (edited by hand) shows nothing.
    elsewhere = tmp_path / "elsewhere.mp4"
    elsewhere.write_bytes(b"\0")
    job.result_video = elsewhere
    assert client.post("/api/jobs/j1/reveal?file=video").status_code == 404
    assert client.post("/api/jobs/j1/reveal?file=../../x").status_code == 422
    assert client.post("/api/jobs/nope/reveal").status_code == 404
    assert launched == []


def test_explorer_selects_a_file_and_opens_a_folder(tmp_path):
    folder = tmp_path / "a folder"
    folder.mkdir()
    video = folder / "my talk_dubbed_de.mp4"
    video.write_bytes(b"\0")
    explorer = r"C:\Windows\explorer.exe"
    # One /select,"<path>" piece: explorer's own parsing, spaces in the path kept.
    assert srv.reveal_command(explorer, video, "win32") == f'"{explorer}" /select,"{video}"'
    assert srv.reveal_command(explorer, folder, "win32") == f'"{explorer}" "{folder}"'
    assert srv.reveal_command("/usr/bin/open", video, "darwin") == ["/usr/bin/open", "-R",
                                                                      str(video)]
    assert srv.reveal_command("/usr/bin/open", folder, "darwin") == ["/usr/bin/open",
                                                                       str(folder)]
    assert srv.reveal_command("/usr/bin/xdg-open", video, "linux") == ["/usr/bin/xdg-open",
                                                                         str(folder)]


def test_no_desktop_in_a_container_or_without_a_display(monkeypatch):
    monkeypatch.setattr(srv.voxa, "_in_container", lambda: True)
    assert srv._desktop_opener() is None
    monkeypatch.setattr(srv.voxa, "_in_container", lambda: False)
    if srv.sys.platform == "win32":
        assert Path(srv._desktop_opener()).name.lower() == "explorer.exe"
    elif srv.sys.platform != "darwin":
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert srv._desktop_opener() is None


def test_launch_starts_and_reaps(monkeypatch):
    """The real _launch: a short program started, nothing waited for on the request."""
    import sys
    import time
    started = []
    real = srv.subprocess.Popen

    def spy(*args, **kwargs):
        proc = real(*args, **kwargs)
        started.append(proc)
        return proc

    monkeypatch.setattr(srv.subprocess, "Popen", spy)
    srv._launch([sys.executable, "-c", "pass"])
    deadline = time.time() + 20
    while started[0].poll() is None and time.time() < deadline:
        time.sleep(0.05)
    assert started[0].returncode == 0


def test_launch_first_lets_explorer_come_forward(monkeypatch):
    """Windows brings Explorer's window in front only if allowed: _launch asks first."""
    import types
    order = []
    monkeypatch.setattr(srv, "let_explorer_front", lambda: order.append("allow") or False)
    monkeypatch.setattr(srv.subprocess, "Popen",
                        lambda *a, **k: order.append("start") or types.SimpleNamespace(
                            wait=lambda: 0))
    srv._launch(["explorer"])
    assert order == ["allow", "start"]


def test_letting_explorer_forward_never_raises(monkeypatch):
    assert srv.let_explorer_front() in (True, False)
    monkeypatch.setattr(srv.sys, "platform", "darwin")
    assert srv.let_explorer_front() is False


def test_a_slow_options_call_holds_up_nothing_else(monkeypatch):
    """The first /api/options imports pyannote (~10 s): it used to keep every other request,
    the health check that shows Show in folder among them, waiting until it was done."""
    import asyncio
    import time

    import httpx

    def slow():
        time.sleep(1.0)
        return {"languages": []}

    monkeypatch.setattr(srv, "build_options", slow)

    async def both():
        transport = httpx.ASGITransport(app=srv.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            started = time.perf_counter()
            took = {}

            async def get(path):
                r = await client.get(path)
                took[path] = time.perf_counter() - started
                return r.status_code

            codes = await asyncio.gather(get("/api/options"), get("/api/health"))
            return codes, took

    codes, took = asyncio.run(both())
    assert codes == [200, 200]
    assert took["/api/health"] < 0.5 <= took["/api/options"], took
