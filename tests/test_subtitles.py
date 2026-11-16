"""
Subtitles to read: the translated lines cut into captions that fit on screen (caption_cues),
and put in a video (--subtitles-in-video): as a track players can turn on (soft) or drawn onto
the picture (hard), in a dub or, with --subtitles-only, in the original video.

The end-to-end runs use ffmpeg on a black clip with a tone and the stand-in speech engine
(conftest.py); skipped where ffmpeg is missing.

Run:  pytest -q tests/test_subtitles.py
"""
import asyncio
import json
import subprocess
import sys

import pytest
from test_review import _line, _write, needs_ffmpeg

import voxa

SOURCE_SRT = """1
00:00:00,500 --> 00:00:03,500
Good morning, everyone.

2
00:00:04,000 --> 00:00:07,000
See you tomorrow.
"""


# ── captions ─────────────────────────────────────────────
def test_a_short_line_is_one_caption():
    assert voxa.caption_cues([_line(1.0, 3.0, "  Sabahınız   xeyir. ")]) == \
        [(1.0, 3.0, "Sabahınız xeyir.")]


def test_a_long_line_becomes_captions_that_fit_on_screen():
    text = ("Salam dostlar, necəsiniz? Partnyorumla Venesiyadayam, gözəl küçələri gəzirik "
            "və hər addımda yeni bir şey görürük. Çox xoşuma gəlir, mükəmməldir!")
    cues = voxa.caption_cues([_line(2.0, 12.0, text)])
    assert len(cues) > 1
    assert cues[0][0] == 2.0 and cues[-1][1] == 12.0
    assert all(a[1] == b[0] for a, b in zip(cues, cues[1:]))         # one after another
    for start, end, caption in cues:
        lines = caption.split("\n")
        assert len(lines) <= 2 and all(len(line) <= 52 for line in lines)
        assert end > start
    assert " ".join(c[2].replace("\n", " ") for c in cues) == text  # nothing lost
    # Cut where a clause ends, not mid-clause, when one fits.
    assert cues[0][2].replace("\n", " ").endswith((",", "?", ".", "!"))


def test_a_script_without_spaces_gets_narrower_lines():
    text = "你好，今天我们在威尼斯。街道非常漂亮，我们一起散步，看看这座城市。明天见！"
    cues = voxa.caption_cues([_line(0.0, 6.0, text)])
    assert "".join(c[2].replace("\n", "") for c in cues) == text
    assert all(len(line) <= 21 for c in cues for line in c[2].split("\n"))


def test_silent_lines_have_no_caption():
    assert voxa.caption_cues([_line(0, 1, ""), _line(1, 2, " ")]) == []


def test_two_lines_break_near_the_middle():
    # 48 characters: the space nearest the 24th is right after "altı".
    assert voxa._wrap_caption("bir iki üç dörd beş altı yeddi səkkiz doqquz on", 30) == \
        "bir iki üç dörd beş altı\nyeddi səkkiz doqquz on"
    assert voxa._wrap_caption("qısa", 30) == "qısa"


# ── in the video ─────────────────────────────────────────
@pytest.fixture
def talk(tmp_path, monkeypatch, lean_voxa):
    """A black 8 s clip with a tone, its subtitles and the lines translated, in a fresh dir."""
    monkeypatch.chdir(tmp_path)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=8",
                    "-f", "lavfi", "-i", "sine=frequency=330:duration=8",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    "talk.mp4"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   check=True)
    (tmp_path / "talk.srt").write_text(SOURCE_SRT, encoding="utf-8")
    _write(tmp_path / "lines.json", [_line(0.5, 3.5, "Hamıya sabahınız xeyir."),
                                     _line(4.0, 7.0, "Sabah görüşərik.")])
    return tmp_path


def _dub(monkeypatch, *extra):
    monkeypatch.setattr(sys, "argv", ["voxa", "talk.mp4", "--subtitles", "talk.srt",
                                      "--target_lang", "az", "--tts", "fake",
                                      "--translation", "lines.json", *extra])
    return asyncio.run(voxa.main())


def _streams(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                   "stream=codec_type,codec_name:stream_tags=language",
                                   "-of", "json", str(path)])
    return json.loads(out)["streams"]


def _brightest(path, at):
    """The brightest pixel of the frame at `at` seconds (0-255): text on a black picture."""
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", str(at), "-i", str(path),
                                   "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"])
    return max(raw)


@needs_ffmpeg
def test_subtitles_only_as_a_track_in_the_original(talk, speech, monkeypatch):
    assert _dub(monkeypatch, "--subtitles-only", "--subtitles-in-video", "soft") == 0
    assert speech == []                                       # nothing voiced
    streams = _streams(talk / "talk_subtitled_az.mp4")
    kinds = {s["codec_type"]: s for s in streams}
    assert kinds["subtitle"]["codec_name"] == "mov_text"
    assert kinds["subtitle"]["tags"]["language"] == "aze"
    assert kinds["audio"]["codec_name"] == "aac"               # its own sound
    # The subtitle file it gives is the captions, as they are in the video.
    assert (talk / "subtitles_az.srt").read_text(encoding="utf-8") == \
        (talk / "talk_work" / "captions_az.srt").read_text(encoding="utf-8")


@needs_ffmpeg
def test_a_dub_with_the_subtitles_drawn_on(talk, speech, monkeypatch):
    assert _dub(monkeypatch, "--subtitles-in-video", "hard") == 0
    out = talk / "talk_dubbed_az.mp4"
    kinds = [s["codec_type"] for s in _streams(out)]
    assert kinds.count("subtitle") == 0 and "video" in kinds and "audio" in kinds
    assert _brightest(out, 2.0) > 150                          # the words, on black
    assert _brightest(out, 3.8) < 40                           # between lines: black


@needs_ffmpeg
def test_a_dub_with_a_subtitle_track(talk, speech, monkeypatch):
    assert _dub(monkeypatch, "--subtitles-in-video", "soft") == 0
    out = talk / "talk_dubbed_az.mp4"
    assert [s["codec_type"] for s in _streams(out)].count("subtitle") == 1
    assert _brightest(out, 2.0) < 40                           # nothing drawn on


@needs_ffmpeg
def test_a_review_stops_before_any_subtitled_video(talk, speech, monkeypatch):
    assert _dub(monkeypatch, "--subtitles-only", "--subtitles-in-video", "hard",
                "--review") == 0
    assert not (talk / "talk_subtitled_az.mp4").exists()
    assert (talk / "talk_work" / "captions_az.srt").exists()


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


def _subtitle_job(srv, **config):
    work = srv.JOBS_DIR / "0123456789abcdef"
    (work / "talk_work").mkdir(parents=True, exist_ok=True)
    config = srv.JobConfigModel(targetLang="az", translator="google", tts="edge", **config)
    job = srv.Job(id="s1", file_name="talk.mp4", config=config, work_dir=work)
    srv.JOBS["s1"] = job
    return job


def _run(srv, job, monkeypatch, leaves):
    """Run the job with a stand-in voxa that leaves `leaves` (names in the work dir)."""
    seen = []

    async def launch(*cmd, cwd, **kwargs):
        seen.extend(cmd)
        for name in leaves:
            (job.work_dir / name).write_text("1\n00:00:01,000 --> 00:00:02,500\nSalam\n",
                                              encoding="utf-8")

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
    return seen


def test_a_subtitles_job_gives_its_subtitled_video_and_captions(server, monkeypatch):
    srv, client = server
    job = _subtitle_job(srv, subtitlesOnly=True, subtitlesInVideo="hard")
    cmd = _run(srv, job, monkeypatch, ["talk_dubbed_az.mp4", "talk_subtitled_az.mp4",
                                       "talk_work/subtitles_az.srt",
                                       "talk_work/captions_az.srt"])
    assert "--subtitles-only" in cmd
    assert cmd[cmd.index("--subtitles-in-video") + 1] == "hard"
    assert job.result_video.name == "talk_subtitled_az.mp4"
    assert job.result_srt.name == "captions_az.srt"
    vtt = client.get("/api/jobs/s1/result/vtt")
    assert vtt.headers["content-type"].startswith("text/vtt")
    assert vtt.text == "WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.500\nSalam\n"


def test_a_dub_from_before_captions_still_gives_its_subtitles(server, monkeypatch):
    srv, _ = server
    job = _subtitle_job(srv)
    _run(srv, job, monkeypatch, ["talk_dubbed_az.mp4", "talk_work/subtitles_az.srt"])
    assert job.result_video.name == "talk_dubbed_az.mp4"
    assert job.result_srt.name == "subtitles_az.srt"


def test_subtitles_need_no_speech_engine(server):
    srv, _ = server
    config = srv.JobConfigModel(targetLang="az", translator="google", tts="chatterbox",
                                separate=True, subtitlesOnly=True)
    assert srv.engine_problem(config) is None


def test_the_subtitles_go_in_one_of_two_ways(server, monkeypatch):
    srv, client = server
    monkeypatch.setattr(srv, "UPLOADS", {})
    r = client.post("/api/jobs", json={"fileId": "x", "config": {
        "targetLang": "az", "translator": "google", "tts": "edge",
        "subtitlesInVideo": "sideways"}})
    assert r.status_code == 422
