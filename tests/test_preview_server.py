"""The console's side of a preview: a job that dubs the first seconds (voxa --preview), whose
results are its own even beside the whole video's in the same work dir, and the job that then
dubs the whole video.

voxa itself is replaced by a stand-in that leaves in the work dir what a run would;
tests/test_preview.py runs the real pipeline.

Run:  pytest -q tests/test_preview_server.py
"""
import asyncio
import json
import os
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
    monkeypatch.setattr(srv, "_JOB_SLOTS", None)
    monkeypatch.setattr(srv, "_WORKDIR_LOCKS", {})
    monkeypatch.setattr(srv, "_running_jobs", 0)
    monkeypatch.setattr(srv, "read_settings", lambda: {})
    return workspace


@pytest.fixture
def voxa_runs(monkeypatch):
    """Stands in for voxa: records each command and leaves a preview's files (talk.preview<N>s…)
    or the whole video's (talk…), each newer than whatever was there."""
    runs = []

    async def launch(*cmd, cwd, **kwargs):
        runs.append(list(cmd))
        stem = f"talk.preview{cmd[cmd.index('--preview') + 1]}s" if "--preview" in cmd else "talk"
        work = Path(cwd) / f"{stem}_work"
        work.mkdir(exist_ok=True)
        lines = [{"text": f"{stem} line", "start": 0.5, "end": 1.5}]
        (work / "translated.json").write_text(json.dumps(lines), encoding="utf-8")
        (work / "subtitles_az.srt").write_text("1", encoding="utf-8")
        (Path(cwd) / f"{stem}_dubbed_az.mp4").write_bytes(stem.encode())
        later = 1000.0 + len(runs)
        for path in (work / "translated.json", work / "subtitles_az.srt",
                     Path(cwd) / f"{stem}_dubbed_az.mp4"):
            os.utime(path, (later, later))

        class Proc:
            async def _lines(self):
                yield b"[7/7] Assembling\n"

            def __init__(self):
                self.stdout = self._lines()

            async def wait(self):
                return 0

        return Proc()

    monkeypatch.setattr(srv.asyncio, "create_subprocess_exec", launch)
    return runs


def _job(ws, preview=20, job_id="p1"):
    work = ws / "jobs" / "0123456789abcdef"
    work.mkdir(parents=True, exist_ok=True)
    (work / "talk.mp4").write_bytes(b"video")
    config = srv.JobConfigModel(targetLang="az", translator="google", tts="edge",
                                preview=preview)
    job = srv.Job(id=job_id, file_name="talk.mp4", config=config, work_dir=work)
    srv.JOBS[job_id] = job
    return job


def test_each_run_finds_its_own_files_beside_the_others(ws, voxa_runs):
    preview = _job(ws)
    asyncio.run(srv._run_job(preview))
    assert voxa_runs[0][-2:] == ["--preview", "20"]
    assert preview.result_video.name == "talk.preview20s_dubbed_az.mp4"
    assert preview.result_srt.parent.name == "talk.preview20s_work"
    assert json.loads(preview.translation_file.read_text("utf-8"))[0]["text"] == \
        "talk.preview20s line"

    whole = _job(ws, preview=None, job_id="w1")
    asyncio.run(srv._run_job(whole))
    assert "--preview" not in voxa_runs[1]
    assert whole.result_video.name == "talk_dubbed_az.mp4"
    assert json.loads(whole.translation_file.read_text("utf-8"))[0]["text"] == "talk line"

    # The preview, run again after the whole video, still finds only its own.
    asyncio.run(srv._run_job(preview))
    assert preview.result_video.name == "talk.preview20s_dubbed_az.mp4"
    # ...and the whole video, after another preview, only its own.
    asyncio.run(srv._run_job(whole))
    assert whole.result_video.name == "talk_dubbed_az.mp4"
    assert whole.result_srt.parent.name == "talk_work"


def test_a_preview_leads_to_the_whole_video(ws, voxa_runs, monkeypatch):
    preview = _job(ws)
    asyncio.run(srv._run_job(preview))
    started = []

    async def queue(job):
        started.append(job)

    monkeypatch.setattr(srv, "_run_job", queue)
    client = TestClient(srv.app)
    whole_id = client.post("/api/jobs/p1/full").json()["jobId"]
    (whole,) = started
    assert whole.id == whole_id and whole.config.preview is None
    assert whole.file_name == "talk.mp4" and whole.work_dir == preview.work_dir
    assert whole.config.model_dump(exclude={"preview"}) == \
        preview.config.model_dump(exclude={"preview"})
    assert client.get(f"/api/jobs/{whole_id}").json()["config"]["preview"] is None
    # The whole video's job has no "whole video" to go on to.
    assert client.post(f"/api/jobs/{whole_id}/full").status_code == 409


def test_the_whole_video_needs_the_video(ws):
    job = _job(ws)
    (job.work_dir / "talk.mp4").unlink()
    assert TestClient(srv.app).post("/api/jobs/p1/full").status_code == 404


@pytest.mark.parametrize("seconds", [2, 121])
def test_a_preview_has_a_sensible_length(ws, monkeypatch, seconds):
    monkeypatch.setattr(srv, "UPLOADS", {})
    r = TestClient(srv.app).post("/api/jobs", json={"fileId": "x", "config": {
        "targetLang": "az", "translator": "google", "tts": "edge", "preview": seconds}})
    assert r.status_code == 422 and "5 to 120 seconds" in r.json()["detail"]
