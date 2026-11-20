"""A dub can be stopped, taken off the list, and tells when it started and ended (S3)."""
import asyncio
import json
import os
import subprocess
import sys
import time

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
    monkeypatch.setattr(srv, "_JOB_SLOTS", None)
    monkeypatch.setattr(srv, "_WORKDIR_LOCKS", {})
    monkeypatch.setattr(srv, "_running_jobs", 0)
    monkeypatch.setattr(srv, "read_settings", lambda: {"advanced": {"maxConcurrentJobs": 1}})
    return workspace


def _job(ws, job_id="j1", status="queued", created=100.0, work="0123456789abcdef", lang="de"):
    folder = ws / "jobs" / work
    folder.mkdir(parents=True, exist_ok=True)
    config = srv.JobConfigModel(targetLang=lang, translator="google", tts="edge")
    job = srv.Job(id=job_id, file_name="talk.mp4", config=config, work_dir=folder,
                  status=status, created_at=created)
    srv.JOBS[job_id] = job
    return job


def _alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        k32 = ctypes.WinDLL("kernel32")
        k32.OpenProcess.restype = ctypes.c_void_p
        handle = k32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        k32.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))
        k32.CloseHandle(ctypes.c_void_p(handle))
        return code.value == 259
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A zombie still answers kill(0); ps knows it's gone.
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True,
                           text=True).stdout.strip()
    return bool(state) and not state.startswith("Z")


class Voxa:
    """Stands in for a voxa run that keeps going: a real process with a child of its own (as
    voxa has ffmpeg), printing a step, then nothing until it is stopped."""

    def __init__(self):
        self.real = subprocess.Popen(
            [sys.executable, "-c",
             "import subprocess, sys, time\n"
             "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
             "print(c.pid, flush=True)\n"
             "time.sleep(120)"],
            stdout=subprocess.PIPE, text=True)
        self.pid = self.real.pid
        self.grandchild = int(self.real.stdout.readline())
        self.returncode = None
        self.stdout = self._lines()

    async def _lines(self):
        yield b"[3/7] Transcribing with Whisper\n"
        while self.real.poll() is None:
            await asyncio.sleep(0.05)

    async def wait(self):
        self.returncode = await asyncio.to_thread(self.real.wait)
        return self.returncode


@pytest.fixture
def voxa(monkeypatch):
    started = []

    async def launch(*cmd, **kwargs):
        started.append(Voxa())
        return started[-1]

    monkeypatch.setattr(srv.asyncio, "create_subprocess_exec", launch)
    yield started
    for run in started:                                  # nothing outlives a failed test
        if run.real.poll() is None:
            srv.kill_tree(run.pid)


async def _until(predicate, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        await asyncio.sleep(0.05)
    return False


# ── stopping ─────────────────────────────────────────────
def test_stopping_a_running_dub_ends_voxa_and_what_it_started(ws, voxa):
    job = _job(ws)

    async def main():
        srv._start_job(job)
        assert await _until(lambda: job.status == "running" and voxa and job.step == 3)
        summary = await srv.cancel_job(job.id)
        return summary

    summary = asyncio.run(main())
    run = voxa[0]
    assert summary["status"] == "failed" and summary["cancelled"] is True
    assert summary["error"] == srv.CANCELLED and summary["finishedAt"] >= summary["startedAt"]
    assert not _alive(run.pid) and not _alive(run.grandchild)
    assert job.events[-1] == {"type": "status", "status": "failed", "error": srv.CANCELLED}
    record = json.loads((srv._history_dir() / "j1.json").read_text(encoding="utf-8"))
    assert record["cancelled"] is True and record["status"] == "failed"


def test_stopping_a_queued_dub_takes_it_out_of_the_queue(ws, voxa):
    first, second = _job(ws, "first", created=1.0, work="aaaa"), _job(ws, "second", created=2.0,
                                                                         work="bbbb")

    async def main():
        srv._start_job(first)
        srv._start_job(second)
        assert await _until(lambda: first.status == "running" and voxa)
        assert second.status == "queued" and second.summary()["queuePosition"] == 1
        stopped = await srv.cancel_job("second")
        assert first.status == "running" and len(voxa) == 1       # the other one goes on
        await srv.cancel_job("first")
        return stopped

    stopped = asyncio.run(main())
    assert stopped["cancelled"] and stopped["startedAt"] is None     # it never ran
    assert len(voxa) == 1 and not _alive(voxa[0].pid)


def test_only_a_dub_going_can_be_stopped(ws):
    _job(ws, status="done")
    response = TestClient(srv.app).post("/api/jobs/j1/cancel")
    assert response.status_code == 409 and "nothing to stop" in response.json()["detail"]
    assert TestClient(srv.app).post("/api/jobs/nope/cancel").status_code == 404


def test_the_server_shutting_down_isnt_taken_for_a_stop(ws, voxa):
    job = _job(ws)

    async def main():
        srv._start_job(job)
        assert await _until(lambda: job.status == "running" and voxa)
        job.task.cancel()                        # what the server's shutdown does
        with pytest.raises(asyncio.CancelledError):
            await job.task

    asyncio.run(main())
    assert job.status == "running" and not job.cancelled   # next start: "interrupted"


def test_voicing_a_stopped_dub_again_starts_it_afresh(ws, monkeypatch):
    job = _job(ws, status="failed")
    job.cancelled, job.started_at, job.finished_at = True, 1.0, 2.0
    job.translation_file = job.work_dir / "translations" / "j1.json"
    job.translation_file.parent.mkdir(parents=True)
    job.translation_file.write_text('[{"start": 0, "end": 1, "text": "Hallo"}]', encoding="utf-8")
    monkeypatch.setattr(srv, "_start_job", lambda j: None)
    summary = TestClient(srv.app).post("/api/jobs/j1/voice").json()
    assert summary["status"] == "queued" and summary["cancelled"] is False
    assert summary["startedAt"] is None and summary["finishedAt"] is None


# ── when, and where in the queue ─────────────────────────
def test_a_run_says_when_it_started_and_ended(ws, monkeypatch):
    job = _job(ws)

    class Done:
        pid, returncode = None, None

        async def _lines(self):
            yield b"[7/7] Assembling final video\n"
            (job.work_dir / "talk_dubbed_de.mp4").write_bytes(b"video")

        def __init__(self):
            self.stdout = self._lines()

        async def wait(self):
            return 0

    async def launch(*cmd, **kwargs):
        return Done()

    monkeypatch.setattr(srv.asyncio, "create_subprocess_exec", launch)
    before = time.time()
    asyncio.run(srv._run_job(job))
    summary = job.summary()
    assert summary["status"] == "done" and summary["createdAt"] == 100.0
    assert before <= summary["startedAt"] <= summary["finishedAt"] <= time.time()
    assert summary["queuePosition"] is None and summary["cancelled"] is False


def test_the_queue_is_numbered_in_the_order_the_dubs_were_made(ws):
    _job(ws, "running", status="running", created=1.0)
    for job_id, created in (("c", 4.0), ("a", 2.0), ("b", 3.0)):
        _job(ws, job_id, created=created)
    jobs = TestClient(srv.app).get("/api/jobs").json()["jobs"]
    listed = {j["id"]: j["queuePosition"] for j in jobs}
    assert listed == {"running": None, "a": 1, "b": 2, "c": 3}


def test_the_times_and_the_stop_outlive_a_restart(ws):
    job = _job(ws, status="failed")
    job.started_at, job.finished_at, job.cancelled = 10.0, 20.0, True
    srv.save_job(job)
    srv.JOBS.clear()
    srv.load_history()
    back = srv.JOBS["j1"].summary()
    assert (back["startedAt"], back["finishedAt"], back["cancelled"]) == (10.0, 20.0, True)


# ── taking a dub off the list ────────────────────────────
def _finished(ws, job_id="j1", lang="de", work="0123456789abcdef"):
    job = _job(ws, job_id, status="done", work=work, lang=lang)
    job.result_video = job.work_dir / f"talk_dubbed_{lang}.mp4"
    job.result_video.write_bytes(b"video")
    job.result_srt = job.work_dir / "talk_work" / f"captions_{lang}.srt"
    job.result_srt.parent.mkdir(exist_ok=True)
    job.result_srt.write_text("1", encoding="utf-8")
    job.translation_file = job.work_dir / "translations" / f"{job_id}.json"
    job.translation_file.parent.mkdir(exist_ok=True)
    job.translation_file.write_text("[]", encoding="utf-8")
    srv.save_job(job)
    return job


def test_removing_a_dub_keeps_its_files_unless_asked(ws):
    job = _finished(ws)
    reply = TestClient(srv.app).delete("/api/jobs/j1").json()
    assert reply == {"deleted": "j1", "removedFiles": []}
    assert "j1" not in srv.JOBS and not (srv._history_dir() / "j1.json").exists()
    assert not job.translation_file.exists()                          # the job's own lines go
    assert job.result_video.exists() and job.result_srt.exists()      # the dub stays


def test_removing_a_dub_with_its_files(ws):
    job = _finished(ws)
    reply = TestClient(srv.app).delete("/api/jobs/j1?files=true").json()
    assert sorted(reply["removedFiles"]) == ["captions_de.srt", "talk_dubbed_de.mp4"]
    assert not job.result_video.exists() and not job.result_srt.exists()
    assert job.work_dir.exists()                         # other dubs of the video reuse it


def test_files_another_dub_made_too_are_kept(ws):
    job = _finished(ws, "j1")
    again = _finished(ws, "j2")                          # the same video, same language, again
    assert again.result_video == job.result_video
    reply = TestClient(srv.app).delete("/api/jobs/j1?files=true").json()
    assert reply["removedFiles"] == [] and job.result_video.exists()


def test_a_dub_going_cant_be_removed(ws):
    _job(ws, status="running")
    response = TestClient(srv.app).delete("/api/jobs/j1")
    assert response.status_code == 409 and "j1" in srv.JOBS


# ── the log reads as a terminal shows it ─────────────────
@pytest.mark.parametrize("raw, shown", [
    ("Downloading:   0%|     | 0/139M\r  50%|###  | 70M/139M\r 100%|#####| 139M/139M",
     " 100%|#####| 139M/139M"),
    ("\x1b[32m[3/7] ✓ Transcription already completed\x1b[0m",
     "[3/7] ✓ Transcription already completed"),
    ("[5/7] Translating to de", "[5/7] Translating to de"),
    ("\r\r", ""),
])
def test_a_progress_bar_leaves_its_last_state(raw, shown):
    assert srv.terminal_line(raw) == shown


def test_the_log_gets_one_line_per_progress_bar(ws, monkeypatch):
    job = _job(ws)

    class Bar:
        pid, returncode = None, None

        async def _lines(self):
            yield b"  0%|     | 0/9\r 44%|##   | 4/9\r100%|#####| 9/9\n"
            yield b"\r\n"

        def __init__(self):
            self.stdout = self._lines()

        async def wait(self):
            return 1

    async def launch(*cmd, **kwargs):
        return Bar()

    monkeypatch.setattr(srv.asyncio, "create_subprocess_exec", launch)
    asyncio.run(srv._run_job(job))
    logs = [e["line"] for e in job.events if e["type"] == "log"]
    assert logs == ["100%|#####| 9/9"]


# ── BE-8: run a failed or stopped dub again ──

def test_a_failed_or_stopped_dub_runs_again_in_place(ws, monkeypatch):
    started = []
    monkeypatch.setattr(srv, "_start_job", started.append)
    job = _job(ws, "j1", status="failed")
    (job.work_dir / job.file_name).write_bytes(b"video")
    job.error, job.step, job.cancelled = srv.CANCELLED, 4, True
    job.started_at, job.finished_at = 10.0, 20.0
    client = TestClient(srv.app)
    body = client.post("/api/jobs/j1/retry").json()
    assert body["status"] == "queued" and body["error"] is None and body["step"] == 0
    assert body["cancelled"] is False and body["startedAt"] is None
    assert started == [job] and list(srv.JOBS) == ["j1"]          # the same dub, not a new one
    saved = json.loads((ws / "history" / "j1.json").read_text(encoding="utf-8"))
    assert saved["status"] == "queued"


def test_only_a_failed_dub_with_its_video_runs_again(ws, monkeypatch):
    monkeypatch.setattr(srv, "_start_job", lambda job: None)
    client = TestClient(srv.app)
    _job(ws, "done1", status="done")
    assert client.post("/api/jobs/done1/retry").status_code == 409
    gone = _job(ws, "gone1", status="failed", work="fedcba9876543210")
    assert not (gone.work_dir / gone.file_name).exists()
    r = client.post("/api/jobs/gone1/retry")
    assert r.status_code == 409 and "isn't in its folder" in r.json()["detail"]
    assert client.post("/api/jobs/nope/retry").status_code == 404
