"""
--preview: dub only the first seconds of a video, into a work dir and an output of their own,
to hear the voice and the translation before dubbing all of it.

Runs the pipeline for real with ffmpeg on a silent clip voiced from --subtitles, with the
stand-in speech engine (`speech`, in conftest.py). Skipped where ffmpeg is missing.

Run:  pytest -q tests/test_preview.py
"""
import asyncio
import json
import subprocess
import sys

import pytest
from test_review import _line, _write, needs_ffmpeg

import voxa

SOURCE_SRT = """1
00:00:00,500 --> 00:00:01,500
Good morning.

2
00:00:04,000 --> 00:00:06,000
It's a long way.

3
00:00:08,000 --> 00:00:10,000
See you tomorrow.
"""


def test_a_preview_keeps_the_lines_that_start_inside_it():
    lines = [_line(0.5, 1.5, "a"), _line(4.0, 6.0, "b"), _line(8.0, 10.0, "c")]
    assert voxa._within(lines, 5) == [_line(0.5, 1.5, "a"), _line(4.0, 5.0, "b")]
    assert voxa._within(lines, None) is lines
    assert voxa._within_length(12.0, 5) == 5.0
    assert voxa._within_length(3.0, 5) == 3.0
    assert voxa._within_length(None, 5) is None


@pytest.fixture
def long_clip(tmp_path, monkeypatch, lean_voxa):
    """A silent 12 s clip and its subtitles, in a fresh working directory."""
    monkeypatch.chdir(tmp_path)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x120:d=12",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "talk.mp4"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    (tmp_path / "talk.srt").write_text(SOURCE_SRT, encoding="utf-8")
    return tmp_path


def _dub(monkeypatch, *extra):
    monkeypatch.setattr(sys, "argv", ["voxa", "talk.mp4", "--subtitles", "talk.srt",
                                      "--target_lang", "az", "--tts", "fake", *extra])
    return asyncio.run(voxa.main())


def _seconds(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "default=nw=1:nk=1", str(path)])
    return float(out.decode().strip())


@needs_ffmpeg
def test_a_preview_dubs_the_first_seconds_on_its_own(long_clip, speech, monkeypatch):
    given = _write(long_clip / "lines.json", [_line(0.5, 1.5, "Sabahınız xeyir."),
                                              _line(4.0, 6.0, "Uzun yoldur."),
                                              _line(8.0, 10.0, "Sabaha qədər.")])
    assert _dub(monkeypatch, "--translation", given, "--preview", "5") == 0
    assert speech == ["Sabahınız xeyir.", "Uzun yoldur."]
    out = long_clip / "talk.preview5s_dubbed_az.mp4"
    assert out.exists() and not (long_clip / "talk_dubbed_az.mp4").exists()
    assert (long_clip / "talk.preview5s_work" / "voxa.log").exists()       # its log too
    assert not (long_clip / "talk_work").exists()
    assert 4.5 <= _seconds(out) <= 5.6
    kept = json.loads((long_clip / "talk.preview5s_work" / "translated.json").read_text("utf-8"))
    assert [line["end"] for line in kept] == [1.5, 5.0]

    # Again, as is: the clip isn't cut again and nothing is voiced again.
    clip = long_clip / "talk.preview5s.mp4"
    cut_at = clip.stat().st_mtime
    speech.clear()
    assert _dub(monkeypatch, "--translation", given, "--preview", "5") == 0
    assert speech == [] and clip.stat().st_mtime == cut_at

    # The whole video is a dub of its own, beside the preview.
    assert _dub(monkeypatch, "--translation", given) == 0
    assert speech == ["Sabahınız xeyir.", "Uzun yoldur.", "Sabaha qədər."]
    assert _seconds(long_clip / "talk_dubbed_az.mp4") >= 11.5
    assert out.exists()


@needs_ffmpeg
def test_preview_on_its_own_takes_twenty_seconds(long_clip, speech, monkeypatch):
    # Longer than the video: all of it, in the preview's own files.
    given = _write(long_clip / "lines.json", [_line(0.5, 1.5, "Bir.")])
    assert _dub(monkeypatch, "--translation", given, "--preview") == 0
    assert (long_clip / "talk.preview20s_dubbed_az.mp4").exists()


@needs_ffmpeg
@pytest.mark.parametrize("seconds", ["2", "121"])
def test_a_preview_has_a_sensible_length(long_clip, speech, monkeypatch, capsys, seconds):
    assert _dub(monkeypatch, "--preview", seconds) == 1
    assert "--preview takes 5 to 120 seconds" in capsys.readouterr().out
