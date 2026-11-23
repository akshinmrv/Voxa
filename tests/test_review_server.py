"""The console's side of reviewing a translation: a job that stops at "review", its lines read
and changed through the API, and voiced (again) from the job's own copy of them.

voxa itself is replaced by a stand-in process that writes what a run would leave in the work
dir; tests/test_review.py runs the real pipeline.

Run:  pytest -q tests/test_review_server.py
"""
import asyncio
import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import voxa_server as srv  # noqa: E402

TRANSLATED = [{"text": "Sabahınız xeyir.", "start": 0.5, "end": 1.5},
              {"text": "Sabah görüşərik.", "start": 2.0, "end": 5.0, "speaker": "SPEAKER_01"}]
MERGED = [{"text": " Good morning.", "start": 0.5, "end": 1.5},
          {"text": "See you  tomorrow.", "start": 2.0, "end": 5.0}]


@pytest.fixture
def ws(tmp_path, monkeypatch):
    workspace = tmp_path / ".voxa_serve"
    monkeypatch.setattr(srv, "WORKSPACE", workspace)
    monkeypatch.setattr(srv, "JOBS_DIR", workspace / "jobs")
    monkeypatch.setattr(srv, "JOBS", {})
    monkeypatch.setattr(srv, "_JOB_SLOTS", None)
    monkeypatch.setattr(srv, "_WORKDIR_LOCKS", {})
    monkeypatch.setattr(srv, "_running_jobs", 0)
    monkeypatch.setattr(srv, "read_settings", lambda: {"advanced": {"speechRate": 10}})
    return workspace


@pytest.fixture
def voxa_runs(monkeypatch):
    """Stands in for the voxa process: records each command, and leaves in the work dir what
    the run would (the translation, and the video unless it stopped for review)."""
    runs = []

    async def launch(*cmd, cwd, **kwargs):
        from pathlib import Path
        runs.append(list(cmd))
        work = Path(cwd) / "talk_work"
        work.mkdir(exist_ok=True)
        if "--translation" in cmd:
            given = json.loads(Path(cmd[cmd.index("--translation") + 1]).read_text("utf-8"))
            lines = [{k: v for k, v in line.items() if k != "source"} for line in given]
        else:
            lines = TRANSLATED
        (work / "translated.json").write_text(json.dumps(lines), encoding="utf-8")
        (work / "merged_sentences.json").write_text(json.dumps(MERGED), encoding="utf-8")
        if "--review" not in cmd:
            (Path(cwd) / "talk_dubbed_az.mp4").write_bytes(b"video")

        class Proc:
            async def _lines(self):
                yield b"[5/7] Translating\n"

            def __init__(self):
                self.stdout = self._lines()

            async def wait(self):
                return 0

        return Proc()

    monkeypatch.setattr(srv.asyncio, "create_subprocess_exec", launch)
    return runs


def _job(ws, review=True, job_id="j1"):
    work = ws / "jobs" / "0123456789abcdef"
    work.mkdir(parents=True, exist_ok=True)
    config = srv.JobConfigModel(targetLang="az", translator="google", tts="edge", review=review)
    job = srv.Job(id=job_id, file_name="talk.mp4", config=config, work_dir=work)
    srv.JOBS[job_id] = job
    return job


def test_a_review_job_stops_with_its_lines_kept(ws, voxa_runs):
    job = _job(ws)
    asyncio.run(srv._run_job(job))
    assert "--review" in voxa_runs[0] and "--translation" not in voxa_runs[0]
    assert job.status == "review" and job.summary()["hasTranslation"]
    assert job.events[-1] == {"type": "status", "status": "review"}
    assert not (job.work_dir / "talk_dubbed_az.mp4").exists()

    view = TestClient(srv.app).get("/api/jobs/j1/translation").json()
    assert view["editable"] is True
    assert view["lines"] == [
        # 10 characters a second for the 1.35 s up to the next line (its gap kept)
        {"start": 0.5, "end": 1.5, "text": "Sabahınız xeyir.", "source": "Good morning.",
         "speaker": None, "maxChars": 13},
        {"start": 2.0, "end": 5.0, "text": "Sabah görüşərik.", "source": "See you tomorrow.",
         "speaker": "SPEAKER_01", "maxChars": 30}]




def test_the_lines_are_changed_and_voiced_from_the_jobs_copy(ws, voxa_runs, monkeypatch):
    job = _job(ws)
    asyncio.run(srv._run_job(job))
    client = TestClient(srv.app)
    r = client.put("/api/jobs/j1/translation", json={"texts": ["Günaydın.", " Sabaha\n qədər. "]})
    assert r.status_code == 200
    assert [line["text"] for line in r.json()["lines"]] == ["Günaydın.", "Sabaha qədər."]
    # Another dub of the same video replaces the work dir's translated.json; this job's lines
    # stay its own.
    (job.work_dir / "talk_work" / "translated.json").write_text("[]", encoding="utf-8")

    run_job, started = srv._run_job, []

    async def queue(j):
        started.append(j.id)

    monkeypatch.setattr(srv, "_run_job", queue)
    summary = client.post("/api/jobs/j1/voice").json()
    assert summary["status"] == "queued" and started == ["j1"]
    assert job.events[-1] == {"type": "status", "status": "queued"}

    asyncio.run(run_job(job))
    cmd = voxa_runs[-1]
    assert "--review" not in cmd
    given = json.loads(open(cmd[cmd.index("--translation") + 1], encoding="utf-8").read())
    assert [line["text"] for line in given] == ["Günaydın.", "Sabaha qədər."]
    assert job.status == "done" and job.summary()["hasVideo"]
    # Its lines are still there to change, and to voice again.
    assert [line["text"] for line in client.get("/api/jobs/j1/translation").json()["lines"]] \
        == ["Günaydın.", "Sabaha qədər."]


def test_a_dub_without_review_keeps_its_lines_too(ws, voxa_runs):
    job = _job(ws, review=False)
    asyncio.run(srv._run_job(job))
    assert "--review" not in voxa_runs[0] and "--translation" not in voxa_runs[0]
    assert job.status == "done" and job.summary()["hasTranslation"]
    asyncio.run(srv._run_job(job))                      # voiced again: from its own lines
    assert "--translation" in voxa_runs[1]


@pytest.mark.parametrize("texts, status, says", [
    (["one"], 422, "one text for each of the 2 lines"),
    (["", " "], 422, "At least one line needs something to say"),
    (["x" * 2001, "y"], 422, "at most 2000 characters"),
])
def test_changes_that_dont_fit_are_refused(ws, voxa_runs, texts, status, says):
    asyncio.run(srv._run_job(_job(ws)))
    r = TestClient(srv.app).put("/api/jobs/j1/translation", json={"texts": texts})
    assert r.status_code == status and says in r.json()["detail"]


def test_a_running_job_cant_be_changed_or_voiced(ws, voxa_runs):
    job = _job(ws)
    asyncio.run(srv._run_job(job))
    job.status = "running"
    client = TestClient(srv.app)
    assert client.put("/api/jobs/j1/translation",
                      json={"texts": ["a", "b"]}).status_code == 409
    assert client.post("/api/jobs/j1/voice").status_code == 409
    assert client.get("/api/jobs/j1/translation").json()["editable"] is False


def test_a_job_with_no_lines_says_so(ws):
    _job(ws).status = "failed"          # before it got as far as translating
    client = TestClient(srv.app)
    assert client.get("/api/jobs/j1/translation").status_code == 404
    assert client.post("/api/jobs/j1/voice").status_code == 404
    assert client.get("/api/jobs/nope/translation").status_code == 404


def test_a_review_that_left_no_lines_fails(ws, monkeypatch):
    job = _job(ws)

    async def launch(*cmd, cwd, **kwargs):
        class Proc:
            async def _lines(self):
                yield b"[5/7] Translating\n"

            def __init__(self):
                self.stdout = self._lines()

            async def wait(self):
                return 0
        return Proc()

    monkeypatch.setattr(srv.asyncio, "create_subprocess_exec", launch)
    asyncio.run(srv._run_job(job))
    assert job.status == "failed" and "no lines to review" in job.error


def test_a_job_waiting_for_review_comes_back_after_a_restart(ws, voxa_runs):
    job = _job(ws)
    asyncio.run(srv._run_job(job))
    srv.JOBS.clear()
    assert srv.load_history() == 1
    back = srv.JOBS["j1"]
    assert back.status == "review" and back.error is None       # not "interrupted"
    assert back.config.review is True
    assert back.translation_file == job.translation_file
    view = TestClient(srv.app).get("/api/jobs/j1/translation").json()
    assert view["lines"][0]["source"] == "Good morning."


def test_its_event_stream_ends_at_review(ws, voxa_runs):
    asyncio.run(srv._run_job(_job(ws)))
    body = TestClient(srv.app).get("/api/jobs/j1/events").text
    assert body.rstrip().endswith('data: {"type": "status", "status": "review"}')


def test_a_job_voiced_again_replays_only_its_new_run(ws, voxa_runs):
    job = _job(ws)
    asyncio.run(srv._run_job(job))
    job.events.append({"type": "status", "status": "queued"})
    job.status = "queued"
    job.events.append({"type": "log", "line": "[1/7] again"})
    job.status = "done"
    job.events.append({"type": "status", "status": "done"})
    body = TestClient(srv.app).get("/api/jobs/j1/events").text
    assert '"review"' not in body
    assert body.index('"queued"') < body.index("again") < body.index('"done"')
