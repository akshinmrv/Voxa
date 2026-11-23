"""How a dubbed line is fitted into the time it has: the placement plan, the checks every clip
passes, what a cloning engine says after its line, the translator shortening a line that
doesn't fit, and the original's voice kept out of the mix.

The numbers in the regressions come from a real dub (en→tr, Chatterbox, 28 s): a 27-letter line
was given 4.3 s of audio, of which 1.4 s were words; placement played it 2.5x faster and then
cut 724 ms, so the listener heard a different word."""
import asyncio
import shutil
import sys
import types

import numpy as np
import pytest
import soundfile as sf

import voxa

RATE = 24000
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")


def _tone(seconds, rate=RATE, level=0.3):
    return (level * np.sin(2 * np.pi * 220 * np.arange(int(seconds * rate)) / rate)).astype(
        "float32")


def _write(path, *parts, rate=RATE):
    """A WAV of tone and silence, given as ("tone", s) / ("quiet", s) pieces."""
    audio = [(_tone(s, rate) if kind == "tone" else np.zeros(int(s * rate), "float32"))
             for kind, s in parts]
    sf.write(str(path), np.concatenate(audio), rate, subtype="PCM_16")


def _sub(i, start_ms, end_ms, text):
    return voxa.Subtitle(i + 1, voxa._seconds_to_subtime(start_ms / 1000),
                         voxa._seconds_to_subtime(end_ms / 1000), text)


def _timeline(subs, render, work_dir, **kw):
    concat, temps = [], []
    n = asyncio.run(voxa.synthesize_timeline(
        subs, engine="test", prefix="t", sample_rate=RATE, work_dir=work_dir,
        concat_list=concat, temp_files=temps, render=render, text_of=lambda s: s.text,
        desc="test", **kw))
    return n, concat


def _placed(work_dir, i):
    return sf.info(str(work_dir / f"t_put_{i}.wav")).duration * 1000.0


@pytest.fixture(autouse=True)
def _fresh_timing(monkeypatch):
    monkeypatch.setattr(voxa, "_TIMING", voxa._TimingRun())


# ── The plan: where a clip goes and how fast it is played ─────────────────────
def test_a_line_that_fits_is_played_as_spoken_at_its_onset():
    plan = voxa._plan_line(1500, 1000, None, 4000)
    assert plan.start_ms == 1000 and plan.speed == 1.0 and plan.lag_ms == 0
    assert plan.end_ms == 2500 and plan.overrun_ms == 0


def test_a_line_a_little_too_long_is_played_a_little_faster_first():
    gap = voxa.MIN_INTER_LINE_GAP_MS
    # 2000 ms of room before the next line's gap; 2100 ms of speech needs 1.05x.
    plan = voxa._plan_line(2100, 0, None, 2000 + gap)
    assert plan.speed == pytest.approx(1.05)
    assert plan.end_ms == pytest.approx(2000)        # the next line starts on time


def test_past_the_natural_speedup_it_borrows_from_the_next_line():
    gap = voxa.MIN_INTER_LINE_GAP_MS
    # 2000 ms of room; 2400 ms needs 1.2x. At 1.10x it ends 182 ms late, which the lag allows.
    plan = voxa._plan_line(2400, 0, None, 2000 + gap)
    assert plan.speed == pytest.approx(voxa.NATURAL_SPEEDUP)
    assert 2000 < plan.end_ms <= 2000 + voxa.MAX_LAG_MS
    assert plan.overrun_ms == 0


def test_a_line_far_too_long_is_capped_and_kept_whole():
    # The measured line: 4.3 s of audio for 1.02 s. Before, 2.5x and a 724 ms cut.
    plan = voxa._plan_line(4320, 18740, None, 19760)
    assert plan.speed == voxa.MAX_SPEEDUP
    assert plan.end_ms - plan.start_ms == pytest.approx(4320 / voxa.MAX_SPEEDUP)
    assert plan.overrun_ms > 0                         # said whole, so it runs on


def test_the_lag_is_paid_back_in_the_next_pause():
    gap = voxa.MIN_INTER_LINE_GAP_MS
    first = voxa._plan_line(2400, 0, None, 2000 + gap)
    second = voxa._plan_line(1000, 2000 + gap, first.end_ms, 6000)
    assert second.lag_ms > 0                           # it starts after the first one ends
    assert second.start_ms == pytest.approx(first.end_ms + gap)
    third = voxa._plan_line(800, 6000, second.end_ms, 9000)
    assert third.lag_ms == 0                           # back on its onset


def test_a_line_is_never_slowed_down():
    rng = np.random.default_rng(7)
    for _ in range(500):
        onset = float(rng.uniform(0, 10000))
        clip = float(rng.uniform(50, 8000))
        nxt = onset + float(rng.uniform(100, 6000))
        prev = onset - float(rng.uniform(-500, 2000))
        plan = voxa._plan_line(clip, onset, prev, nxt)
        assert 1.0 <= plan.speed <= voxa.MAX_SPEEDUP
        assert plan.lag_ms >= 0
        assert plan.end_ms - plan.start_ms == pytest.approx(clip / plan.speed)


def test_without_stretching_a_long_line_runs_on_at_its_own_pace():
    plan = voxa._plan_line(3000, 0, None, 2000, max_speedup=1.0)
    assert plan.speed == 1.0 and plan.end_ms == 3000 and plan.overrun_ms > 0


def test_the_last_line_has_the_media_to_its_end():
    assert voxa._plan_line(3000, 10000, None, None, media_end_ms=14000).speed == 1.0
    assert voxa._plan_line(3000, 10000, None, None, media_end_ms=12500).speed == \
        pytest.approx(1.2)
    assert voxa._plan_line(30000, 0, None, None).speed == 1.0     # no end known: as spoken


# ── The translation's budget is the time placement gives the line ─────────────
def test_a_line_followed_by_a_pause_gets_the_pause_in_its_budget():
    gap = voxa.MIN_INTER_LINE_GAP_MS / 1000
    lines = [{"start": 0.0, "end": 2.0}, {"start": 6.0, "end": 7.0},
             {"start": 6.5, "end": 9.0}]
    budgets = voxa._line_budgets(lines, 15.0)
    assert budgets[0] == int((6.0 - gap) * 15)        # up to the next line, not just 2 s
    assert budgets[1] == 15                            # overlapping: its own 1 s
    assert budgets[2] == int(2.5 * 15)                 # the last: its own time


# ── Every clip is prepared and checked the same way ───────────────────────────
def test_a_clip_loses_the_engine_s_silence_but_not_its_pauses(tmp_path):
    src, dst = tmp_path / "raw.wav", tmp_path / "fin.wav"
    _write(src, ("quiet", 0.5), ("tone", 0.6), ("quiet", 0.3), ("tone", 0.6), ("quiet", 0.9))
    assert voxa._prepare_clip(src, dst, RATE)
    length = sf.info(str(dst)).duration
    expected = 1.5 + (voxa.CLIP_LEAD_MS + voxa.CLIP_TAIL_MS) / 1000
    assert length == pytest.approx(expected, abs=0.02)   # the pause inside is kept


def test_a_silent_clip_cant_be_prepared(tmp_path):
    src = tmp_path / "raw.wav"
    _write(src, ("quiet", 1.0))
    assert voxa._prepare_clip(src, tmp_path / "fin.wav", RATE) is False


def test_the_clip_check(tmp_path):
    long_line = "Vadeli işlem sözleşmelerini anlamak, bilmeniz gereken her şey."
    silent, short, right, garbage = (tmp_path / f"{n}.wav" for n in "abcd")
    _write(silent, ("quiet", 2.0))
    _write(short, ("tone", 0.6))
    _write(right, ("tone", 4.0))
    garbage.write_bytes(b"not a wav")
    assert voxa._clip_problem(silent, long_line) == "silent"
    assert voxa._clip_problem(short, long_line) == "cut short"
    assert voxa._clip_problem(right, long_line) is None
    assert voxa._clip_problem(garbage, long_line) == "no audio"
    assert voxa._clip_problem(short, "3.") is None    # a short line needs little sound


# ── What a cloning engine says after its line is cut off ──────────────────────
def _word(word, start, end):
    return types.SimpleNamespace(word=word, start=start, end=end)


def test_a_wordless_run_on_after_the_line_is_found():
    heard = [_word("Bu", 0.0, 0.26), _word("yüzden", 0.26, 0.48), _word("çok", 0.48, 0.7),
             _word("heyecanlıyım.", 0.7, 1.4)]
    # The measured clip: 4.32 s, its words over at 1.40 s, then 2.2 s of murmur.
    assert voxa._trailing_speech_cut(heard, "Bu yüzden çok heyecanlıyım.", 4.32) == (1.4, [])
    assert voxa._trailing_speech_cut(heard, "Bu yüzden çok heyecanlıyım.", 1.6) is None
    assert voxa._trailing_speech_cut(heard, "Bu yüzden çok heyecanlıyım.") is None


def test_the_cut_goes_in_the_pause_after_the_last_word():
    data = np.concatenate([_tone(1.4), np.zeros(int(0.5 * RATE), "float32"), _tone(2.0)])
    at = voxa._run_on_cut_at(data, RATE, 1.35) / RATE
    assert 1.4 <= at <= 1.5
    no_pause = _tone(3.0)
    assert voxa._run_on_cut_at(no_pause, RATE, 1.0) / RATE == pytest.approx(1.12, abs=0.01)


def test_a_consonant_s_closure_is_not_taken_for_the_pause():
    # 40 ms of silence inside the last word (a closure), then its release.
    data = np.concatenate([_tone(1.0), np.zeros(int(0.04 * RATE), "float32"), _tone(0.1),
                           np.zeros(int(0.5 * RATE), "float32"), _tone(1.0)])
    at = voxa._run_on_cut_at(data, RATE, 0.98) / RATE
    assert at >= 1.14                                 # after the release, in the real pause


def test_openai_whisper_answers_like_faster_whisper():
    class _Model:
        def transcribe(self, path, **kw):
            assert kw["word_timestamps"] is True
            return {"segments": [{"text": " Merhaba dünya.", "words": [
                {"word": " Merhaba", "start": 0.0, "end": 0.5},
                {"word": " dünya.", "start": 0.5, "end": 1.0}]}]}

    segments, _ = voxa._WhisperWords(_Model()).transcribe("x.wav", language="tr",
                                                          word_timestamps=True)
    words = [w for s in segments for w in s.words]
    assert [w.word for w in words] == [" Merhaba", " dünya."] and words[-1].end == 1.0
    assert voxa._trailing_speech_cut(words, "Merhaba dünya.", 3.0) == (1.0, [])


# ── The whole pass, with real audio ───────────────────────────────────────────
@needs_ffmpeg
def test_no_spoken_audio_is_cut_and_nothing_is_rushed(tmp_path):
    # Three lines; the first too long for its time, the others with room.
    lengths = {0: 2.4, 1: 0.8, 2: 1.0}

    def render(i, text, final_file, target):
        _write(final_file, ("tone", lengths[i]))
        return True

    subs = [_sub(0, 0, 1800, "a" * 30), _sub(1, 2150, 3000, "b" * 12),
            _sub(2, 6000, 7000, "c" * 14)]
    n, concat = _timeline(subs, render, tmp_path, media_ms=8000)
    assert n == 3
    for i, natural in lengths.items():
        placed = _placed(tmp_path, i)
        speed = natural * 1000 / placed
        assert 1.0 - 0.01 <= speed <= voxa.MAX_SPEEDUP + 0.01      # never rushed
        assert placed * speed == pytest.approx(natural * 1000, rel=0.02)  # all of it


@needs_ffmpeg
def test_the_lines_land_where_the_plan_puts_them(tmp_path):
    def render(i, text, final_file, target):
        _write(final_file, ("tone", 0.5))
        return True

    subs = [_sub(0, 1000, 1500, "x" * 8), _sub(1, 3000, 3500, "y" * 8)]
    _timeline(subs, render, tmp_path, media_ms=5000)
    track = []
    for line in (tmp_path / "t_sil_0.wav", tmp_path / "t_put_0.wav",
                 tmp_path / "t_sil_1.wav", tmp_path / "t_put_1.wav"):
        track.append(sf.read(str(line), dtype="float32")[0])
    track = np.concatenate(track)
    loud = np.flatnonzero(np.abs(track) > 0.05) / RATE
    assert loud[0] == pytest.approx(1.0, abs=0.02)                # first line on its onset
    second = loud[loud > 2.0]
    assert second[0] == pytest.approx(3.0, abs=0.02)              # and the second on its own


def test_without_ffmpeg_a_line_plays_as_spoken(tmp_path, monkeypatch):
    def no_ffmpeg(*a, **k):
        raise FileNotFoundError("ffmpeg")

    monkeypatch.setattr(voxa.subprocess, "run", no_ffmpeg)
    src, dst = tmp_path / "fin.wav", tmp_path / "put.wav"
    _write(src, ("tone", 1.5))
    voxa._play_at(src, dst, 1.2, RATE)
    assert sf.info(str(dst)).duration == pytest.approx(1.5)


def test_a_silent_take_is_voiced_again(tmp_path, monkeypatch):
    monkeypatch.setattr(voxa, "_play_at", lambda src, dst, speed, sr: shutil.copyfile(src, dst))
    calls = []

    def render(i, text, final_file, target):
        calls.append(i)
        _write(final_file, ("quiet", 1.0) if len(calls) == 1 else ("tone", 1.0))
        return True

    n, _ = _timeline([_sub(0, 0, 2000, "Salam dostlar.")], render, tmp_path)
    assert n == 1 and calls == [0, 0]


def test_a_cut_short_take_is_voiced_again(tmp_path, monkeypatch):
    monkeypatch.setattr(voxa, "_play_at", lambda src, dst, speed, sr: shutil.copyfile(src, dst))
    takes = iter([0.4, 4.0])
    line = "Vadeli işlem sözleşmelerini anlamak, bilmeniz gereken her şey."

    def render(i, text, final_file, target):
        _write(final_file, ("tone", next(takes)))
        return True

    n, _ = _timeline([_sub(0, 0, 5000, line)], render, tmp_path, media_ms=6000)
    assert n == 1 and sf.info(str(tmp_path / "t_fin_0.wav")).duration == pytest.approx(4.0)


def test_a_line_no_take_voices_fails_the_run_and_keeps_the_rest(tmp_path, monkeypatch):
    monkeypatch.setattr(voxa, "_play_at", lambda src, dst, speed, sr: shutil.copyfile(src, dst))
    calls = []

    def render(i, text, final_file, target):
        calls.append(i)
        if i == 0:
            raise RuntimeError("IndexError: max(): Expected reduction dim 1")
        _write(final_file, ("tone", 0.8))
        return True

    with pytest.raises(voxa.TTSError) as exc:
        _timeline([_sub(0, 0, 900, "3."), _sub(1, 1000, 2000, "Merhaba.")], render, tmp_path)
    assert "couldn't voice 1 of 2 lines" in str(exc.value)
    assert calls.count(0) == voxa.RENDER_ATTEMPTS
    assert (tmp_path / "t_fin_1.wav").exists()       # the line that worked is kept


def test_nothing_voiced_still_says_the_dub_would_be_silent(tmp_path):
    with pytest.raises(voxa.TTSError) as exc:
        _timeline([_sub(0, 0, 900, "a"), _sub(1, 1000, 2000, "b")],
                  lambda i, t, f, d: False, tmp_path)
    assert "no speech" in str(exc.value).lower()


def test_an_engine_that_is_down_is_not_tried_on_every_line(tmp_path):
    # Edge's 403 refused every line; each was tried three times before the run failed.
    calls = []

    def refused(i, text, final_file, target):
        calls.append(i)
        raise RuntimeError("403, message='Invalid response status'")

    subs = [_sub(k, k * 1000, k * 1000 + 800, f"line {k}") for k in range(10)]
    with pytest.raises(voxa.TTSError) as exc:
        _timeline(subs, refused, tmp_path)
    assert "the first 3 of the 10 segments" in str(exc.value)
    assert sorted(set(calls)) == [0, 1, 2]
    assert len(calls) == voxa.GIVE_UP_AFTER * voxa.RENDER_ATTEMPTS


def _say(final_file, text, cps=12.0):
    _write(final_file, ("tone", len(text) / cps))
    return True


@needs_ffmpeg
def test_a_line_too_long_is_said_in_fewer_words(tmp_path):
    asked = []

    def shorten(text, max_chars):
        asked.append((text, max_chars))
        return text[:max_chars]

    voxa._TIMING.shorten = shorten
    voiced = []

    def render(i, text, final_file, target):
        voiced.append(text)
        return _say(final_file, text)

    long_line = "x" * 48                              # 4 s of speech for 2 s of room
    n, _ = _timeline([_sub(0, 0, 2000, long_line), _sub(1, 2150, 3000, "y" * 10)],
                     render, tmp_path, media_ms=4000)
    assert n == 2
    assert asked and asked[0][0] == long_line and asked[0][1] < len(long_line)
    assert voxa._TIMING.shortened[0] == voiced[1]     # the shorter wording was voiced
    assert len(voiced[1]) < len(long_line)
    assert _placed(tmp_path, 0) * 1.0 <= 2000 * voxa.SHORTEN_ABOVE + voxa.MAX_LAG_MS


def test_only_a_line_well_past_its_time_is_reworded():
    gap = voxa.MIN_INTER_LINE_GAP_MS
    # The measured short line: 1.0 s of speech for 0.8 s. 1.25x covers it; rewording it
    # turned "are you here?" into "is it here?".
    short = voxa._plan_line(1000, 0, None, 800 + gap - voxa.MAX_LAG_MS)
    assert short.needed > voxa.SHORTEN_ABOVE and not voxa._worth_shortening(1000, short)
    # 6.2 s for 5.0 s: 0.6 s would be left over even at 1.10x.
    long_ = voxa._plan_line(6200, 0, None, 5000 + gap - voxa.MAX_LAG_MS)
    assert voxa._worth_shortening(6200, long_)
    assert not voxa._worth_shortening(2000, voxa._plan_line(2000, 0, None, 5000))


def test_a_take_kept_over_a_new_wording_leaves_nothing_of_it(tmp_path, monkeypatch):
    monkeypatch.setattr(voxa, "_play_at", lambda src, dst, speed, sr: shutil.copyfile(src, dst))
    voxa._TIMING.shorten = lambda text, max_chars: text[:max_chars]

    def render(i, text, final_file, target):
        raw = final_file.with_name(f"t_raw_{i}.wav")
        _write(raw, ("tone", 3.0))                    # a slow take: longer whatever it says
        shutil.copyfile(raw, final_file)
        return True

    _timeline([_sub(0, 0, 1000, "w" * 40)], render, tmp_path, media_ms=1200)
    assert not voxa._TIMING.shortened                 # the new wording wasn't shorter
    assert not (tmp_path / "t_raw_0.wav").exists()    # and nothing of it stays to be reused
    assert (tmp_path / "t_fin_0.wav").exists()


def test_a_wording_that_isnt_shorter_keeps_the_take(tmp_path, monkeypatch):
    monkeypatch.setattr(voxa, "_play_at", lambda src, dst, speed, sr: shutil.copyfile(src, dst))
    voxa._TIMING.shorten = lambda text, max_chars: None
    calls = []

    def render(i, text, final_file, target):
        calls.append(text)
        return _say(final_file, text)

    _timeline([_sub(0, 0, 1000, "z" * 40)], render, tmp_path, media_ms=1200)
    assert calls == ["z" * 40] and not voxa._TIMING.shortened


@needs_ffmpeg
def test_a_cloning_engine_s_run_on_is_cut(tmp_path):
    class _Asr:
        def transcribe(self, path, language=None, word_timestamps=False):
            return [types.SimpleNamespace(text="Hoş geldiniz.", words=[
                _word("Hoş", 0.0, 0.3), _word("geldiniz.", 0.3, 0.6)])], None

    def render(i, text, final_file, target):
        _write(final_file, ("tone", 0.6), ("quiet", 0.5), ("tone", 2.0))   # murmur after it
        return True

    _timeline([_sub(0, 20480, 20720, "Hoş geldiniz.")], render, tmp_path, media_ms=22200,
              check_run_on=True, asr_model=_Asr(), gate_lang="tr")
    assert sf.info(str(tmp_path / "t_fin_0.wav")).duration < 0.8
    assert _placed(tmp_path, 0) < 800                 # placed whole, at its own pace


def test_stale_clips_of_every_engine_are_cleared(tmp_path):
    for name in ("cbx_fin_0.wav", "vcpm_fin_0.wav", "edge_fin_0.wav", "cbx_put_0.wav"):
        (tmp_path / name).write_bytes(b"x")
    assert voxa._purge_synthesis_artifacts(tmp_path) == 4
    assert not list(tmp_path.iterdir())


# ── The shortened lines go back into the translation ─────────────────────────
def test_a_shortened_line_is_kept_in_the_translation_and_the_record():
    subs = [_sub(0, 1000, 2000, "uzun bir cümle burada"), _sub(1, 3000, 4000, "ikinci")]
    segments = [{"start": 1.0, "end": 2.0, "text": "uzun bir cümle burada"},
                {"start": 3.0, "end": 4.0, "text": "ikinci"}]
    spoken = [voxa._spoken_line(s) for s in subs]
    assert voxa._keep_shortened({0: "kısa cümle"}, subs, segments, spoken) == 1
    assert segments[0]["text"] == "kısa cümle" and segments[1]["text"] == "ikinci"
    assert spoken[0][2] == "kısa cümle"


def test_the_translator_s_shorter_wording_is_checked(monkeypatch):
    replies = iter(["Kısa.", "Bu çok daha uzun bir cevap olacaktır, fazlasıyla.", "Короче."])
    monkeypatch.setitem(voxa.LLM_PROVIDERS, "fake", {
        "chat": lambda system, user, model, want_json, key: next(replies),
        "default_model": "m"})
    line = "Bu kursta öğrenecekleriniz bunlar."
    assert voxa._shorten_for_time(line, 20, "tr", "fake") == "Kısa."
    assert voxa._shorten_for_time(line, 20, "tr", "fake") is None   # not shorter
    assert voxa._shorten_for_time(line, 20, "tr", "fake") is None   # not Turkish


def test_only_an_llm_translator_shortens():
    args = types.SimpleNamespace(translator="google", target_lang="tr")
    assert voxa._line_shortener(args) is None
    args = types.SimpleNamespace(translator="openai", target_lang="tr", openai_model="gpt-5",
                                 openai_api_key=None, translation_prompt=None)
    assert callable(voxa._line_shortener(args))


# ── The original's voice is never in the mix ──────────────────────────────────
def _levels(n, values):
    return [float(v) for v in np.resize(values, n)]


def test_a_background_that_follows_the_voice_is_muted_there():
    frames = 60
    syllables = np.where(np.arange(frames) % 4 < 2, -20.0, -38.0)      # the voice
    speech = [-90.0] * 10 + list(syllables[:40]) + [-90.0] * 10
    leaking = [-70.0] * 10 + list(syllables[:40] - 25) + [-70.0] * 10   # the voice, 25 dB down
    music = [-30.0 + (k % 7) for k in range(frames)]                    # its own rhythm
    plan, stretches = voxa._leak_plan(speech, leaking)
    assert stretches == 1 and len(plan) == 1 and plan[0][2] <= -60
    assert voxa._leak_plan(speech, music)[0] == []
    assert voxa._leak_plan(speech, [-80.0] * frames)[0] == []          # too quiet to hear


def test_the_leak_gate_mutes_the_voice_and_keeps_the_music(tmp_path):
    rate = 16000
    t = np.arange(rate * 6) / rate
    voice = np.zeros_like(t)
    talking = (t >= 2) & (t < 4)
    voice[talking] = 0.3 * np.sin(2 * np.pi * 180 * t[talking]) * (np.sin(2 * np.pi * 4 * t[
        talking]) > 0)
    music = 0.05 * np.sin(2 * np.pi * 440 * t)
    speech, background = tmp_path / "speech.wav", tmp_path / "background.wav"
    sf.write(str(speech), voice.astype("float32"), rate)
    sf.write(str(background), (music + 0.2 * voice).astype("float32"), rate)
    out = tmp_path / "clean.wav"
    muted, stretches = voxa.gate_vocal_leakage(background, speech, out)
    assert muted == 1 and stretches == 1
    clean, _ = sf.read(str(out), dtype="float32")
    assert np.abs(clean[int(2.3 * rate):int(3.8 * rate)]).max() < 0.001   # no voice left
    assert np.abs(clean[:int(1.5 * rate)]).max() > 0.04                   # music kept


def test_without_the_speech_track_the_background_isn_t_vouched_for(tmp_path):
    background = tmp_path / "background.wav"
    sf.write(str(background), np.zeros(1600, "float32"), 16000)
    assert voxa.gate_vocal_leakage(background, tmp_path / "missing.wav",
                                   tmp_path / "out.wav") is None


@needs_ffmpeg
def test_where_the_dub_pauses_the_original_is_not_heard(tmp_path):
    import subprocess
    src, vo, out = tmp_path / "src.mp4", tmp_path / "vo.wav", tmp_path / "out.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=black:s=320x240:d=4", "-f", "lavfi", "-i",
                    "sine=frequency=1000:duration=4", "-c:v", "libx264", "-c:a", "aac",
                    "-pix_fmt", "yuv420p", str(src)], check=True)
    _write(vo, ("tone", 2.0), ("quiet", 2.0), rate=22050)       # the dub speaks, then pauses
    voxa._assemble_final_video(str(src), str(vo), str(out), 0.05, 1.5)
    mix = tmp_path / "mix.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out), "-ac", "1", "-ar", "16000",
                    str(mix)], check=True)
    audio, rate = sf.read(str(mix), dtype="float32")
    pause = audio[int(2.3 * rate):int(3.9 * rate)]
    assert np.abs(pause).max() < 1e-3                 # not the original's 1 kHz, not anything
    assert np.abs(audio[:int(1.8 * rate)]).max() > 0.1


# ── Chatterbox's short-line guard ─────────────────────────────────────────────
def test_chatterbox_short_lines_are_voiced(monkeypatch):
    torch = pytest.importorskip("torch")

    class Analyzer:
        def __init__(self, tokens, held=0):
            self.alignment = torch.zeros(10, tokens)
            self.alignment[5:5 + held, -1] = 1.0
            self.complete, self.completed_at = True, 5
            self.curr_frame_pos, self.eos_idx = 0, 0

        def step(self, logits, next_token=None):
            self.alignment[:, :-5].max(dim=1)        # Chatterbox 0.1.7's failing line
            self.curr_frame_pos += 1
            return logits

    module = types.ModuleType("alignment_stream_analyzer")
    module.AlignmentStreamAnalyzer = Analyzer
    for name in ("chatterbox", "chatterbox.models", "chatterbox.models.t3",
                 "chatterbox.models.t3.inference"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules,
                        "chatterbox.models.t3.inference.alignment_stream_analyzer", module)
    from voxa_engines.workers import chatterbox_worker
    chatterbox_worker.guard_short_lines()

    logits = torch.zeros(1, 4)
    short = Analyzer(tokens=4)
    assert torch.equal(short.step(logits), logits) and short.curr_frame_pos == 1
    held = Analyzer(tokens=4, held=5)
    ended = held.step(torch.zeros(1, 4))
    assert ended[0, 0] > 0 and ended[0, 1] < 0        # a last token held 200 ms ends it
    Analyzer(tokens=8).step(logits)                   # longer lines run as they did
