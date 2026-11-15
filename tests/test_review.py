"""
Reviewing a translation before it is voiced (--review), dubbing from given lines
(--translation), and voicing again only the lines that changed.

The pipeline runs for real on a tiny silent clip voiced from --subtitles, with ffmpeg; the
speech engine is a stand-in that records which lines it was asked to say. No network, no
models, no keys. Skipped where ffmpeg is missing (a CI job installs it).

Run:  pytest -q tests/test_review.py
"""
import asyncio
import json
import shutil
import subprocess
import sys

import pytest

import voxa

SOURCE_SRT = """1
00:00:00,500 --> 00:00:01,500
Good morning.

2
00:00:02,000 --> 00:00:03,200
See you tomorrow.
"""


def _line(start, end, text):
    return {"text": text, "start": start, "end": end}


@pytest.fixture(autouse=True)
def _keep_voxa_logging(monkeypatch):
    """voxa.main() points Voxa's logger at the run's log file and stops it propagating. Put it
    back afterwards, or later tests' caplog no longer hears it."""
    log = voxa._LOG
    monkeypatch.setattr(log, "handlers", list(log.handlers))
    monkeypatch.setattr(log, "propagate", log.propagate)
    monkeypatch.setattr(log, "level", log.level)
    yield
    for handler in log.handlers:        # the run's, before monkeypatch restores the list
        handler.close()


# ── load_translation ─────────────────────────────────────
def test_a_translation_is_read_from_json_or_srt(tmp_path):
    given = tmp_path / "lines.json"
    given.write_text(json.dumps([
        {"start": 0.5, "end": 1.5, "text": "  Günaydın.\n"},
        {"start": 2, "end": 3.2, "text": "", "speaker": "SPEAKER_01"},
    ]), encoding="utf-8")
    assert voxa.load_translation(given) == [
        _line(0.5, 1.5, "Günaydın."), {**_line(2.0, 3.2, ""), "speaker": "SPEAKER_01"}]
    srt = tmp_path / "lines.srt"
    srt.write_text(SOURCE_SRT, encoding="utf-8")
    assert voxa.load_translation(srt) == [_line(0.5, 1.5, "Good morning."),
                                          _line(2.0, 3.2, "See you tomorrow.")]


@pytest.mark.parametrize("content, says", [
    ("not json", "isn't JSON"),
    ('{"start": 1}', "JSON list"),
    ('[1]', "line 1 isn't an object"),
    ('[{"text": "x"}]', "line 1 needs a start and an end"),
    ('[{"start": 3, "end": 1, "text": "x"}]', "line 1 ends before it starts"),
    ('[{"start": 0, "end": 1, "text": 5}]', "its text should be a string"),
    ('[{"start": 0, "end": 1, "text": " "}]', "no line to speak"),
    ('[]', "no line to speak"),
])
def test_a_translation_that_cant_be_used_says_why(tmp_path, content, says):
    given = tmp_path / "lines.json"
    given.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=says):
        voxa.load_translation(given)


def test_only_what_changed_lines_were_made_of_is_dropped(tmp_path):
    # The engines reuse what a line was made from when it's there (Edge its mp3 and its
    # conversion), so all of it goes, not just the placed clip.
    names = ["edge_raw_1.mp3", "edge_cnv_1.wav", "edge_fin_1.wav", "otts_rawcand_2.wav",
             "xtts_raw_2_0.wav", "xtts_fincand_2_1.wav", "piper_raw_2.wav", "edge_fin_2.wav",
             # kept: other lines' files, and whatever isn't a line's
             "edge_raw_0.mp3", "edge_fin_0.wav", "edge_fin_12.wav", "edge_raw_21.mp3",
             "edge_sil_1.wav", "fill_1.wav", "voiceover.wav"]
    for name in names:
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "deliveries.json").write_text("[]", encoding="utf-8")
    voiced = [[0, 1000, "a", None], [1000, 2000, "b", None], [2000, 3000, "c", None]]
    spoken = [[0, 1000, "a", None], [1000, 2000, "B", None], [2000, 3000, "c", "S1"]]
    assert voxa._drop_changed_clips(tmp_path, voiced, spoken) == 2
    assert sorted(p.name for p in tmp_path.iterdir() if p.suffix != ".json") == sorted(
        ["edge_raw_0.mp3", "edge_fin_0.wav", "edge_fin_12.wav", "edge_raw_21.mp3",
         "edge_sil_1.wav", "fill_1.wav", "voiceover.wav"])
    assert not (tmp_path / "deliveries.json").exists()
    assert voxa._drop_changed_clips(tmp_path, spoken, spoken) == 0


# ── the pipeline, end to end ─────────────────────────────
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@pytest.fixture
def clip(tmp_path, monkeypatch):
    """A silent 4 s clip and its source-language subtitles, in a fresh working directory.
    The packages these runs don't use are taken away, as CI's test jobs don't install them."""
    monkeypatch.chdir(tmp_path)
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(voxa, "_MISSING_DEPS", [])
    for module in ("whisper", "torch", "edge_tts", "GoogleTranslator", "requests", "nr"):
        monkeypatch.setattr(voxa, module, None)
    monkeypatch.setattr(voxa, "tqdm", voxa._NoProgress)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x120:d=4",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "clip.mp4"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    (tmp_path / "clip.srt").write_text(SOURCE_SRT, encoding="utf-8")
    return tmp_path


@pytest.fixture
def speech(monkeypatch):
    """A speech engine ("fake") that says nothing, quickly, and records what it was given.
    Like Edge, it keeps what it said (fake_raw_<i>.wav) and reuses it when it's there."""
    said = []

    async def _tts_fake(subs, args, work_dir, video_path, gate_asr, logger):
        concat_list, temp_files = [], []

        def render(i, text, final_file, target_duration):
            raw = work_dir / f"fake_raw_{i}.wav"
            if not raw.exists():
                said.append(text)
                voxa.create_silence_wav(0.4, str(raw), 22050)
            shutil.copyfile(raw, final_file)
            return True

        await voxa.synthesize_timeline(
            subs, engine="fake", prefix="fake", sample_rate=22050, work_dir=work_dir,
            concat_list=concat_list, temp_files=temp_files, render=render,
            text_of=lambda s: s.text.strip(), desc="Fake")
        return concat_list, temp_files

    monkeypatch.setitem(voxa.TTS_PROVIDERS, "fake", {"synthesize": _tts_fake})
    return said


def _dub(monkeypatch, *extra):
    monkeypatch.setattr(sys, "argv", ["voxa", "clip.mp4", "--subtitles", "clip.srt",
                                      "--target_lang", "az", "--tts", "fake", *extra])
    return asyncio.run(voxa.main())


def _write(path, lines):
    path.write_text(json.dumps(lines, ensure_ascii=False), encoding="utf-8")
    return str(path)


@needs_ffmpeg
def test_review_stops_before_speech_and_voices_only_what_changes(clip, speech, monkeypatch):
    first = _write(clip / "first.json", [_line(0.5, 1.5, "Sabahınız xeyir."),
                                         _line(2.0, 3.2, "Sabah görüşərik.")])
    # Reviewing: translated, and nothing voiced.
    assert _dub(monkeypatch, "--translation", first, "--review") == 0
    work = clip / "clip_work"
    assert json.loads((work / "translated.json").read_text(encoding="utf-8"))[1]["text"] == \
        "Sabah görüşərik."
    assert speech == [] and not (clip / "clip_dubbed_az.mp4").exists()

    # Voiced as reviewed: every line.
    edited = _write(clip / "edited.json", [_line(0.5, 1.5, "Sabahınız xeyir."),
                                           _line(2.0, 3.2, "Sabaha qədər.")])
    assert _dub(monkeypatch, "--translation", edited) == 0
    assert speech == ["Sabahınız xeyir.", "Sabaha qədər."]
    assert (clip / "clip_dubbed_az.mp4").exists()

    # One line changed afterwards: only it is voiced again.
    speech.clear()
    again = _write(clip / "again.json", [_line(0.5, 1.5, "Günaydın."),
                                         _line(2.0, 3.2, "Sabaha qədər.")])
    assert _dub(monkeypatch, "--translation", again) == 0
    assert speech == ["Günaydın."]

    # Nothing changed: nothing voiced.
    speech.clear()
    assert _dub(monkeypatch, "--translation", again) == 0
    assert speech == []

    # Changed in translated.json itself, on the command line: that line is voiced again.
    lines = json.loads((work / "translated.json").read_text(encoding="utf-8"))
    lines[1]["text"] = "Sabah yenə."
    _write(work / "translated.json", lines)
    assert _dub(monkeypatch) == 0
    assert speech == ["Sabah yenə."]


@needs_ffmpeg
def test_a_line_left_empty_stays_silent(clip, speech, monkeypatch):
    given = _write(clip / "lines.json", [_line(0.5, 1.5, ""), _line(2.0, 3.2, "Sağ olun.")])
    assert _dub(monkeypatch, "--translation", given) == 0
    assert speech == ["Sağ olun."]


@needs_ffmpeg
def test_a_dub_voiced_before_lines_were_recorded_is_voiced_again_when_they_change(
        clip, speech, monkeypatch):
    # An older Voxa left no synthesized_lines.json: what it voiced is what translated.json
    # held when this run began.
    given = _write(clip / "lines.json", [_line(0.5, 1.5, "Bir."), _line(2.0, 3.2, "İki.")])
    assert _dub(monkeypatch, "--translation", given) == 0
    (clip / "clip_work" / "synthesized_lines.json").unlink()
    speech.clear()
    assert _dub(monkeypatch, "--translation", given) == 0       # unchanged: kept
    assert speech == []
    assert not (clip / "clip_work" / "synthesized_lines.json").exists()
    changed = _write(clip / "changed.json", [_line(0.5, 1.5, "Bir."), _line(2.0, 3.2, "Üç.")])
    assert _dub(monkeypatch, "--translation", changed) == 0     # changed: all of it again
    assert speech == ["Bir.", "Üç."]


@needs_ffmpeg
def test_an_older_dub_changed_in_translated_json_is_voiced_again(clip, speech, monkeypatch):
    # No synthesized_lines.json, and translated.json changed after the dub was voiced: what
    # it was voiced from is unknown, so all of it is voiced again.
    import os
    given = _write(clip / "lines.json", [_line(0.5, 1.5, "Bir."), _line(2.0, 3.2, "İki.")])
    assert _dub(monkeypatch, "--translation", given) == 0
    work = clip / "clip_work"
    (work / "synthesized_lines.json").unlink()
    lines = json.loads((work / "translated.json").read_text(encoding="utf-8"))
    lines[1]["text"] = "Üç."
    _write(work / "translated.json", lines)
    voiced_at = (work / "voiceover_normalized.wav").stat().st_mtime
    os.utime(work / "translated.json", (voiced_at + 5, voiced_at + 5))
    speech.clear()
    assert _dub(monkeypatch) == 0
    assert speech == ["Bir.", "Üç."]


@needs_ffmpeg
def test_a_translation_file_is_checked_before_anything_runs(clip, speech, monkeypatch, capsys):
    (clip / "bad.json").write_text("[1]", encoding="utf-8")
    assert _dub(monkeypatch, "--translation", "bad.json") == 1
    assert "Can't use the translation in bad.json: line 1 isn't an object" in \
        capsys.readouterr().out
    assert _dub(monkeypatch, "--translation", "missing.json") == 1
    assert not (clip / "clip_work").exists()
