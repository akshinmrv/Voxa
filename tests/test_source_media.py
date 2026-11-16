"""The original video a job dubs, served to the console's player (S4, BE-1)."""
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


def _job(ws, source_url=None, name="talk.mp4"):
    work = ws / "jobs" / "0123456789abcdef"
    work.mkdir(parents=True, exist_ok=True)
    config = srv.JobConfigModel(targetLang="de", translator="google", tts="edge")
    job = srv.Job(id="j1", file_name=source_url or name, config=config, work_dir=work,
                  source_url=source_url)
    srv.JOBS["j1"] = job
    return job


VIDEO = bytes(range(256)) * 40          # 10 KB, every byte known


def test_an_uploaded_video_is_served_to_play_and_seek(ws):
    job = _job(ws)
    (job.work_dir / "talk.mp4").write_bytes(VIDEO)
    client = TestClient(srv.app)
    whole = client.get("/api/jobs/j1/source")
    assert whole.status_code == 200 and whole.content == VIDEO
    assert whole.headers["content-disposition"].startswith("inline")
    part = client.get("/api/jobs/j1/source", headers={"Range": "bytes=1000-1999"})
    assert part.status_code == 206 and part.content == VIDEO[1000:2000]
    assert client.get("/api/jobs/j1").json()["hasSource"] is True


def test_a_linked_video_is_found_among_what_voxa_made(ws):
    job = _job(ws, source_url="https://example.com/watch?v=1")
    for name, size in (("My talk [abc].webm", 5000), ("My talk [abc]_dubbed_de.mp4", 9000),
                       ("My talk [abc]_subtitled_de.mp4", 9000),
                       ("My talk [abc].preview20s.webm", 7000), ("notes.txt", 9999)):
        (job.work_dir / name).write_bytes(b"x" * size)
    assert srv.source_media(job).name == "My talk [abc].webm"


def test_a_video_no_longer_there_says_so(ws):
    _job(ws)
    response = TestClient(srv.app).get("/api/jobs/j1/source")
    assert response.status_code == 404 and "isn't in its folder" in response.json()["detail"]
    assert TestClient(srv.app).get("/api/jobs/j1").json()["hasSource"] is False
    assert TestClient(srv.app).get("/api/jobs/nope/source").status_code == 404
