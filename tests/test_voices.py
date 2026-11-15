"""
Choosing voices: what each engine offers for a language (voxa voices, GET /api/voices), Edge's
voice by name (--edge-voice), the library of clips voices are cloned from, hearing a voice
first, and a job's voices, its own and each speaker's.

No network: Edge's list is a stand-in, and so is the speech when a voice is heard.

Run:  pytest -q tests/test_voices.py
"""
import asyncio
import json
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

import voxa

EDGE = [
    {"ShortName": "az-AZ-BanuNeural", "Locale": "az-AZ", "Gender": "Female"},
    {"ShortName": "az-AZ-BabekNeural", "Locale": "az-AZ", "Gender": "Male"},
    {"ShortName": "en-US-JennyNeural", "Locale": "en-US", "Gender": "Female",
     "StyleList": ["cheerful"]},
    {"ShortName": "en-GB-RyanNeural", "Locale": "en-GB", "Gender": "Male"},
]


@pytest.fixture
def edge_list(monkeypatch):
    monkeypatch.setattr(voxa, "_EDGE_VOICES", list(EDGE))


# ── what each engine offers ──────────────────────────────
def test_edges_voices_for_a_language(edge_list):
    voices = asyncio.run(voxa.voice_catalogue("edge", "az"))
    assert voices == [
        {"id": "az-AZ-BabekNeural", "label": "Babek", "gender": "male", "locale": "az-AZ",
         "styles": False},
        {"id": "az-AZ-BanuNeural", "label": "Banu", "gender": "female", "locale": "az-AZ",
         "styles": False}]
    english = asyncio.run(voxa.voice_catalogue("edge", "en"))
    assert [v["id"] for v in english] == ["en-GB-RyanNeural", "en-US-JennyNeural"]
    assert english[1]["styles"] is True


def test_pipers_voices_are_the_mapped_one_and_those_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(voxa.Path, "home", lambda: tmp_path)
    models = tmp_path / ".piper_models"
    models.mkdir()
    for name in ("de_DE-karlsson-low", "de_DE-thorsten-medium", "en_US-lessac-medium"):
        (models / f"{name}.onnx").write_bytes(b"")
    voices = asyncio.run(voxa.voice_catalogue("piper", "de"))
    assert [(v["id"], v["installed"]) for v in voices] == [
        ("de_DE-thorsten-medium", True), ("de_DE-karlsson-low", True)]
    assert asyncio.run(voxa.voice_catalogue("piper", "tr"))[0] == {
        "id": "tr_TR-dfki-medium", "label": "dfki", "locale": "tr-TR", "installed": False}
    assert asyncio.run(voxa.voice_catalogue("piper", "az")) == []
    assert asyncio.run(voxa.voice_catalogue("openai", "az")) == []


def test_voxa_voices_lists_them(edge_list, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(voxa.Path, "home", lambda: tmp_path)
    assert voxa.voices_cli(["--lang", "az"]) == 0
    out = capsys.readouterr().out
    assert "az-AZ-BabekNeural" in out and "male" in out and "Piper (az): none" in out
    assert voxa.voices_cli(["--lang", "en", "--engine", "edge", "--json"]) == 0
    assert [v["id"] for v in json.loads(capsys.readouterr().out)["edge"]] == \
        ["en-GB-RyanNeural", "en-US-JennyNeural"]


def test_voxa_voices_says_when_edge_cant_be_asked(monkeypatch, capsys):
    async def offline():
        raise OSError("no network")

    monkeypatch.setattr(voxa, "edge_voice_list", offline)
    assert voxa.voices_cli(["--lang", "az", "--engine", "edge"]) == 1
    assert "Couldn't list edge's voices: no network" in capsys.readouterr().err


# ── --edge-voice ─────────────────────────────────────────
def _edge_args(**kw):
    return SimpleNamespace(target_lang="az", edge_voice=None, diarize=False, no_stretch=False,
                           detect_emotion=False, auto_rate=False, quality_gate=False,
                           tts_workers=1, speaker_voices=None, **kw)


class _Log:
    def info(self, *a): pass
    def warning(self, *a): pass


def test_an_edge_voice_by_name(edge_list, monkeypatch):
    used = {}

    async def batch(subs, voice, work_dir, **kw):
        used.update(voice=voice, styles=kw["has_emotion_support"])
        return [], []

    monkeypatch.setattr(voxa, "synthesize_speech_batch", batch)
    monkeypatch.setattr(voxa, "_media_ms", lambda path: None)
    args = _edge_args()
    args.edge_voice = "en-US-JennyNeural"
    asyncio.run(voxa._tts_edge([], args, None, "v.mp4", None, _Log()))
    assert used == {"voice": "en-US-JennyNeural", "styles": True}
    args.edge_voice = "az-AZ-NobodyNeural"
    with pytest.raises(voxa.TTSError, match="Edge has no voice called az-AZ-NobodyNeural"):
        asyncio.run(voxa._tts_edge([], args, None, "v.mp4", None, _Log()))


def test_choosing_an_edge_voice_makes_the_speech_again():
    # Only when one is chosen, so the dubs made before keep their signature.
    base = dict(target_lang="az", tts="edge", no_stretch=False, detect_emotion=False,
                auto_rate=False, voice_sample=None, quality_gate=False, gate_model="base")
    assert "edge_voice" not in voxa._stage_own_params("synthesis", SimpleNamespace(**base))
    chosen = voxa._stage_own_params("synthesis",
                                    SimpleNamespace(**base, edge_voice="az-AZ-BanuNeural"))
    assert chosen["edge_voice"] == "az-AZ-BanuNeural"


# ── the console ──────────────────────────────────────────
@pytest.fixture
def server(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import voxa_server as srv
    workspace = tmp_path / ".voxa_serve"
    monkeypatch.setattr(srv, "WORKSPACE", workspace)
    monkeypatch.setattr(srv, "JOBS_DIR", workspace / "jobs")
    monkeypatch.setattr(srv, "JOBS", {})
    monkeypatch.setattr(srv, "_JOB_SLOTS", None)
    monkeypatch.setattr(srv, "_WORKDIR_LOCKS", {})
    monkeypatch.setattr(srv, "_running_jobs", 0)
    monkeypatch.setattr(srv, "read_settings", lambda: {})
    return srv, TestClient(srv.app)


needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _tone(path, seconds):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}",
                    str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return path


def test_the_voices_of_each_engine(server, edge_list):
    srv, client = server
    edge = client.get("/api/voices", params={"engine": "edge", "lang": "az"}).json()
    assert edge["listen"] is True and [v["id"] for v in edge["voices"]] == \
        ["az-AZ-BabekNeural", "az-AZ-BanuNeural"]
    openai = client.get("/api/voices", params={"engine": "openai"}).json()
    assert openai["listen"] is False and "nova" in [v["id"] for v in openai["voices"]]
    xtts = client.get("/api/voices", params={"engine": "xtts", "lang": "az"}).json()
    assert xtts == {"voices": [], "listen": False, "library": True}


@needs_ffmpeg
def test_the_voice_library(server, tmp_path):
    srv, client = server
    clip = _tone(tmp_path / "me.mp3", 5)
    with clip.open("rb") as f:
        entry = client.post("/api/voices/library", files={"file": ("me.mp3", f)},
                            data={"name": "  My   voice "}).json()
    assert entry["name"] == "My voice" and 4.5 <= entry["seconds"] <= 5.5
    kept = srv._voices_dir() / f"{entry['id']}.wav"
    assert kept.exists() and not list(srv._voices_dir().glob("*.upload"))
    assert client.get(f"/api/voices/library/{entry['id']}/audio").content[:4] == b"RIFF"
    listed = client.get("/api/voices", params={"engine": "chatterbox"}).json()["voices"]
    assert listed == [{"id": entry["id"], "label": "My voice", "seconds": entry["seconds"]}]

    long = _tone(tmp_path / "long.wav", 45)                   # cut to its first 30 s
    with long.open("rb") as f:
        assert client.post("/api/voices/library",
                           files={"file": ("long.wav", f)}).json()["seconds"] <= 30.1
    short = _tone(tmp_path / "short.wav", 1)
    with short.open("rb") as f:
        r = client.post("/api/voices/library", files={"file": ("short.wav", f)})
    assert r.status_code == 422 and "at least 3 seconds" in r.json()["detail"]
    r = client.post("/api/voices/library", files={"file": ("x.wav", b"not audio")})
    assert r.status_code == 422 and "no audio" in r.json()["detail"]

    assert len(client.delete(f"/api/voices/library/{entry['id']}").json()["voices"]) == 1
    assert not kept.exists()
    assert client.delete(f"/api/voices/library/{entry['id']}").status_code == 404
    assert client.get("/api/voices/library/../../x/audio").status_code == 404


def test_a_voice_is_heard_once_and_kept(server, monkeypatch):
    srv, client = server
    said = []

    async def speak(engine, voice, text, out):
        said.append((engine, voice, text))
        out.write_bytes(b"ID3 audio")

    monkeypatch.setattr(srv.voxa, "speak_sample", speak)
    body = {"engine": "edge", "voice": "az-AZ-BanuNeural", "lang": "az"}
    r = client.post("/api/voices/listen", json=body)
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
    assert client.post("/api/voices/listen", json=body).content == b"ID3 audio"
    assert said == [("edge", "az-AZ-BanuNeural", "Salam! Mənim səsim belə səslənir.")]
    client.post("/api/voices/listen", json={**body, "text": " Bir  sətir. "})
    assert said[-1][2] == "Bir sətir."
    assert client.post("/api/voices/listen",
                       json={**body, "engine": "openai"}).status_code == 422

    async def fail(engine, voice, text, out):
        raise ValueError("403")

    monkeypatch.setattr(srv.voxa, "speak_sample", fail)
    r = client.post("/api/voices/listen", json={**body, "voice": "az-AZ-BabekNeural"})
    assert r.status_code == 502 and "403" in r.json()["detail"]


def _job(srv, tts="edge", diarize=True, status="review"):
    work = srv.JOBS_DIR / "0123456789abcdef"
    work.mkdir(parents=True, exist_ok=True)
    config = srv.JobConfigModel(targetLang="az", translator="google", tts=tts, diarize=diarize)
    job = srv.Job(id="j1", file_name="talk.mp4", config=config, work_dir=work, status=status)
    srv.JOBS["j1"] = job
    return job


def _command(srv, job, monkeypatch):
    seen = []

    async def launch(*cmd, cwd, **kwargs):
        seen.extend(cmd)
        raise OSError("not run in a test")

    monkeypatch.setattr(srv.asyncio, "create_subprocess_exec", launch)
    asyncio.run(srv._run_job(job))
    return seen


def test_a_jobs_voices_go_to_voxa(server, monkeypatch):
    srv, client = server
    job = _job(srv)
    r = client.put("/api/jobs/j1/voices", json={
        "voice": "az-AZ-BanuNeural", "speakers": {"SPEAKER_00": "az-AZ-BabekNeural",
                                                  "SPEAKER_01": " "}})
    assert r.status_code == 200
    assert job.config.edgeVoice == "az-AZ-BanuNeural"
    assert job.config.speakerVoices == {"SPEAKER_00": "az-AZ-BabekNeural"}
    record = json.loads((srv._history_dir() / "j1.json").read_text(encoding="utf-8"))
    assert record["config"]["edgeVoice"] == "az-AZ-BanuNeural"
    cmd = _command(srv, job, monkeypatch)
    assert cmd[cmd.index("--edge-voice") + 1] == "az-AZ-BanuNeural"
    assert cmd[cmd.index("--speaker-voices") + 1] == "SPEAKER_00=az-AZ-BabekNeural"
    # Back to Voxa's choice.
    client.put("/api/jobs/j1/voices", json={})
    assert job.config.edgeVoice is None and job.config.speakerVoices is None


def test_a_cloning_job_is_given_its_library_clips(server, monkeypatch):
    srv, client = server
    job = _job(srv, tts="xtts")
    srv._voices_dir().mkdir(parents=True)
    (srv._voices_dir() / "aaaaaaaaaaaa.wav").write_bytes(b"RIFF")
    (srv._voices_dir() / "bbbbbbbbbbbb.wav").write_bytes(b"RIFF")
    client.put("/api/jobs/j1/voices", json={"voice": "aaaaaaaaaaaa",
                                           "speakers": {"SPEAKER_01": "bbbbbbbbbbbb"}})
    assert job.config.voiceSample == "aaaaaaaaaaaa"
    cmd = _command(srv, job, monkeypatch)
    assert cmd[cmd.index("--voice-sample") + 1] == str(srv._voices_dir() / "aaaaaaaaaaaa.wav")
    assert cmd[cmd.index("--speaker-voices") + 1] == \
        f"SPEAKER_01={srv._voices_dir() / 'bbbbbbbbbbbb.wav'}"


def test_voices_change_only_between_runs_and_without_commas(server):
    srv, client = server
    job = _job(srv, status="running")
    assert client.put("/api/jobs/j1/voices", json={"voice": "x"}).status_code == 409
    job.status = "done"
    r = client.put("/api/jobs/j1/voices", json={"speakers": {"SPEAKER_00": "a,b"}})
    assert r.status_code == 422 and ", or =" in r.json()["detail"]
    assert client.put("/api/jobs/nope/voices", json={}).status_code == 404


def test_the_sample_lines_are_in_each_language_offered():
    # One for every language the console lists.
    pytest.importorskip("fastapi")
    import voxa_server as srv
    assert {code for code, _ in srv.COMMON_LANGUAGES} <= set(voxa.SAMPLE_LINES)
    assert all(line.strip() for line in voxa.SAMPLE_LINES.values())
    assert sys.modules["voxa"] is voxa
