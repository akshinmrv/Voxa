"""The console's job list outlives the server: each job is also a file in the workspace."""
import asyncio
import json
import shutil

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import voxa_server as srv  # noqa: E402


@pytest.fixture
def ws(tmp_path, monkeypatch):
    workspace = tmp_path / "home" / ".voxa_serve"
    monkeypatch.setattr(srv, "WORKSPACE", workspace)
    monkeypatch.setattr(srv, "JOBS_DIR", workspace / "jobs")
    monkeypatch.setattr(srv, "JOBS", {})
    # Fresh primitives: each asyncio.run() is a new event loop.
    monkeypatch.setattr(srv, "_JOB_SLOTS", None)
    monkeypatch.setattr(srv, "_WORKDIR_LOCKS", {})
    monkeypatch.setattr(srv, "_running_jobs", 0)
    monkeypatch.setattr(srv, "read_settings", lambda: {})
    return workspace


def _job(ws, job_id="a1", status="done", created=100.0):
    work = ws / "jobs" / "0123456789abcdef"
    work.mkdir(parents=True, exist_ok=True)
    config = srv.JobConfigModel(targetLang="de", translator="google", tts="edge")
    return srv.Job(id=job_id, file_name="talk.mp4", config=config, work_dir=work,
                   status=status, created_at=created)


def _restart():
    srv.JOBS.clear()
    return srv.load_history()


def test_a_finished_dub_comes_back_after_a_restart(ws):
    job = _job(ws)
    job.result_video = job.work_dir / "talk_dubbed_de.mp4"
    job.result_video.write_bytes(b"video")
    job.result_srt = job.work_dir / "talk_work" / "subtitles_de.srt"
    job.result_srt.parent.mkdir()
    job.result_srt.write_text("1", encoding="utf-8")
    job.step = 7
    job.events = [{"type": "log", "line": "[7/7] Assembling"}, {"type": "status", "status": "done"}]
    srv.save_job(job)
    before = job.summary()

    assert _restart() == 1
    assert srv.JOBS["a1"].summary() == before
    assert srv.JOBS["a1"].events == job.events                 # its page still shows the log
    assert TestClient(srv.app).get("/api/jobs/a1/result/video").content == b"video"


@pytest.mark.parametrize("status", ["queued", "running"])
def test_a_dub_cut_short_says_what_to_do(ws, status):
    srv.save_job(_job(ws, status=status))
    _restart()
    job = srv.JOBS["a1"]
    assert job.status == "failed" and "Dub the same video again" in job.error
    notice = {"type": "status", "status": "failed", "error": job.error}
    assert job.events[-1] == notice
    _restart()                                                 # and only once
    assert srv.JOBS["a1"].events.count(notice) == 1


def test_the_list_keeps_the_order_the_dubs_were_made_in(ws):
    for job_id, created in (("late", 300.0), ("early", 100.0), ("middle", 200.0)):
        srv.save_job(_job(ws, job_id=job_id, created=created))
    _restart()
    listed = TestClient(srv.app).get("/api/jobs").json()["jobs"]
    assert [j["id"] for j in listed] == ["early", "middle", "late"]


def test_a_record_it_cant_read_is_skipped(ws):
    srv.save_job(_job(ws))
    (srv._history_dir() / "broken.json").write_text("{not json", encoding="utf-8")
    (srv._history_dir() / "partial.json").write_text(json.dumps({"id": "x"}), encoding="utf-8")
    assert _restart() == 1 and list(srv.JOBS) == ["a1"]


def test_the_folder_can_move_with_its_jobs(ws, tmp_path, monkeypatch):
    job = _job(ws)
    job.result_video = job.work_dir / "talk_dubbed_de.mp4"
    job.result_video.write_bytes(b"video")
    srv.save_job(job)
    record = json.loads((srv._history_dir() / "a1.json").read_text(encoding="utf-8"))
    assert record["workDir"] == "jobs/0123456789abcdef"
    assert record["resultVideo"] == "jobs/0123456789abcdef/talk_dubbed_de.mp4"

    moved = tmp_path / "elsewhere" / ".voxa_serve"
    moved.parent.mkdir()
    shutil.move(str(ws), str(moved))
    monkeypatch.setattr(srv, "WORKSPACE", moved)
    _restart()
    assert srv.JOBS["a1"].summary()["hasVideo"]


def test_a_long_log_keeps_its_end(ws):
    job = _job(ws)
    job.events = [{"type": "log", "line": str(i)} for i in range(srv.HISTORY_EVENTS + 500)]
    srv.save_job(job)
    _restart()
    events = srv.JOBS["a1"].events
    assert len(events) == srv.HISTORY_EVENTS
    assert events[-1]["line"] == str(srv.HISTORY_EVENTS + 499)


def test_a_run_writes_its_record_as_it_goes(ws, monkeypatch):
    job = _job(ws, status="queued")
    seen = []
    save = srv.save_job
    monkeypatch.setattr(srv, "save_job", lambda j: (seen.append(j.status), save(j)))

    class Voxa:
        async def _lines(self):
            for line in (b"[6/7] Synthesizing speech\n", b"[7/7] Assembling final video\n"):
                yield line
            (job.work_dir / "talk_dubbed_de.mp4").write_bytes(b"video")

        def __init__(self):
            self.stdout = self._lines()

        async def wait(self):
            return 0

    async def launch(*cmd, **kwargs):
        return Voxa()

    monkeypatch.setattr(srv.asyncio, "create_subprocess_exec", launch)
    asyncio.run(srv._run_job(job))
    assert seen == ["running", "done"]
    record = json.loads((srv._history_dir() / "a1.json").read_text(encoding="utf-8"))
    assert record["status"] == "done" and record["step"] == 7
    assert record["resultVideo"].endswith("talk_dubbed_de.mp4")


def test_a_new_job_is_on_disk_before_it_runs(ws, monkeypatch):
    async def launch(*cmd, **kwargs):
        raise OSError("not launched in a test")

    monkeypatch.setattr(srv.asyncio, "create_subprocess_exec", launch)
    monkeypatch.setattr(srv, "UPLOAD_DIR", ws / "uploads")
    monkeypatch.setattr(srv, "UPLOADS", {})
    monkeypatch.setattr(srv, "UPLOAD_HASHES", {})
    client = TestClient(srv.app)
    file_id = client.post("/api/upload", files={"file": ("talk.mp4", b"0" * 64)}).json()["fileId"]
    job_id = client.post("/api/jobs", json={"fileId": file_id, "config": {
        "targetLang": "de", "translator": "google", "tts": "edge"}}).json()["jobId"]
    assert (srv._history_dir() / f"{job_id}.json").exists()


def test_a_disk_error_doesnt_fail_the_dub(ws, monkeypatch, capsys):
    def refuse(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(srv.os, "replace", refuse)
    srv.save_job(_job(ws))                                     # no exception
    assert "Couldn't save job a1" in capsys.readouterr().err
