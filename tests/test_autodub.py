"""
Unit tests for AutoDub pure logic.

These intentionally cover the deterministic, dependency-free parts of the pipeline
(translation parsing, sentence merging, timing math, error classification). The heavy
runtime deps (whisper/torch/ffmpeg) are not required — autodub guards those imports.

Run:  pytest -q
"""
import pytest

import autodub


# ── OpenAI batch response parsing ────────────────────────
def test_parse_batch_basic():
    assert autodub._parse_batch_translations('{"translations": ["a", "b"]}', 2) == ["a", "b"]


def test_parse_batch_code_fence():
    raw = '```json\n{"translations": ["a", "b", "c"]}\n```'
    assert autodub._parse_batch_translations(raw, 3) == ["a", "b", "c"]


def test_parse_batch_bare_list():
    assert autodub._parse_batch_translations('["x", "y"]', 2) == ["x", "y"]


def test_parse_batch_lines_key():
    assert autodub._parse_batch_translations('{"lines": ["p", "q"]}', 2) == ["p", "q"]


def test_parse_batch_count_mismatch_returns_none():
    assert autodub._parse_batch_translations('{"translations": ["only one"]}', 2) is None


def test_parse_batch_invalid_json_returns_none():
    assert autodub._parse_batch_translations('not json at all', 2) is None


def test_parse_batch_cleans_prefixes():
    raw = '{"translations": ["Translation: Hello", "\\"World\\""]}'
    assert autodub._parse_batch_translations(raw, 2) == ["Hello", "World"]


# ── Line cleaning ────────────────────────────────────────
def test_clean_line_strips_prefix_and_quotes():
    assert autodub._clean_line('Translation: "Hello"') == "Hello"
    assert autodub._clean_line("'Salam'") == "Salam"
    assert autodub._clean_line("  plain text  ") == "plain text"


# ── Sentence merging ─────────────────────────────────────
def test_merge_sentences_groups_until_punctuation():
    segs = [
        {"text": "Hello", "start": 0.0, "end": 1.0},
        {"text": "world.", "start": 1.0, "end": 2.0},
        {"text": "Next one", "start": 2.0, "end": 3.0},
    ]
    merged = autodub.merge_segments_into_sentences(segs, max_duration=10.0)
    assert merged[0]["text"] == "Hello world."
    assert merged[0]["start"] == 0.0
    assert merged[0]["end"] == 2.0
    assert merged[1]["text"] == "Next one"


def test_merge_sentences_splits_on_long_pause():
    segs = [
        {"text": "First", "start": 0.0, "end": 1.0},
        {"text": "Second", "start": 3.0, "end": 4.0},  # 2s gap > 0.5 pause threshold
    ]
    merged = autodub.merge_segments_into_sentences(segs, max_duration=10.0)
    assert len(merged) == 2


# ── Timing / speed math ──────────────────────────────────
def test_speed_factor_within_tolerance_is_one():
    assert autodub.calculate_speed_factor(1.0, 1.0) == 1.0
    assert autodub.calculate_speed_factor(1.02, 1.0) == 1.0


def test_speed_factor_is_clamped():
    assert autodub.calculate_speed_factor(10.0, 1.0) == 2.5
    assert autodub.calculate_speed_factor(1.0, 10.0) == 0.5


def test_speed_factor_zero_target_safe():
    assert autodub.calculate_speed_factor(5.0, 0.0) == 1.0


# ── S0: TTS text normalization + chunking ────────────────
def test_normalize_tts_text_guarantees_terminal_punctuation():
    assert autodub.normalize_tts_text("hello world") == "hello world."
    assert autodub.normalize_tts_text("what?") == "what?"
    assert autodub.normalize_tts_text("  a   b  ") == "a b."
    assert autodub.normalize_tts_text("line1\nline2") == "line1 line2."
    assert autodub.normalize_tts_text("") == ""
    assert autodub.normalize_tts_text("   ") == ""


def test_normalize_tts_text_folds_typography():
    assert autodub.normalize_tts_text("“hi” — there…") == '"hi" , there.'


def test_infer_delivery():
    assert "question" in autodub.infer_delivery("Necəsən?")
    assert "energetic" in autodub.infer_delivery("Bu mükəmməldir!")
    assert "trail off" in autodub.infer_delivery("Bilmirəm...")
    assert autodub.infer_delivery("Salam dostlar.") == ""
    assert autodub.infer_delivery("") == ""


def test_split_for_tts_short_passthrough():
    assert autodub.split_for_tts("short text") == ["short text"]
    assert autodub.split_for_tts("") == []


def test_split_for_tts_respects_max_and_boundaries():
    text = "First sentence here. Second sentence here. Third sentence here."
    chunks = autodub.split_for_tts(text, max_chars=25)
    assert len(chunks) >= 2
    assert all(0 < len(c) <= 25 for c in chunks)


def test_split_for_tts_hard_wraps_unpunctuated():
    text = ("wordword " * 40).strip()   # ~350 chars, no sentence punctuation
    chunks = autodub.split_for_tts(text, max_chars=100)
    assert all(len(c) <= 100 for c in chunks)
    assert len(chunks) >= 3


# ── S2: OpenAI TTS engine (fake client, no network) ──────
def test_generate_openai_tts_places_segments(tmp_path):
    import io
    import numpy as np
    import soundfile as sf

    def _wav_bytes(dur=1.0, sr=24000):
        buf = io.BytesIO()
        sig = (0.3 * np.sin(2 * np.pi * 220 * np.arange(int(sr * dur)) / sr)).astype("float32")
        sf.write(buf, sig, sr, format="WAV", subtype="PCM_16")
        return buf.getvalue()

    class _Resp:
        content = _wav_bytes()

    class _Speech:
        def create(self, **kw):
            assert kw["model"] and kw["voice"] and kw["input"]  # request well-formed
            return _Resp()

    class _Client:
        class audio:
            speech = _Speech()

    class _T:
        def __init__(self, ms):
            self.hours, self.minutes = 0, 0
            self.seconds, self.milliseconds = ms // 1000, ms % 1000

    class _Sub:
        def __init__(self, s, e, text):
            self.start, self.end, self.text = _T(s), _T(e), text

    subs = [_Sub(0, 1000, "Salam."), _Sub(1000, 2000, "Necəsən?")]
    concat, temp = [], []
    autodub.generate_openai_tts(subs, _Client(), "alloy", "gpt-4o-mini-tts", "", "az",
                                concat, temp, tmp_path, enable_stretch=True)
    finals = [c for c in concat if "otts_fin_" in c]
    assert len(finals) == 2


# ── S1: quality scoring primitives ───────────────────────
def test_normalize_for_compare():
    assert autodub._normalize_for_compare("Hello, World!") == "hello world"
    assert autodub._normalize_for_compare("  A  b  ") == "a b"


def test_edit_distance():
    assert autodub._edit_distance(["a", "b", "c"], ["a", "b", "c"]) == 0
    assert autodub._edit_distance(["a", "b"], ["a"]) == 1
    assert autodub._edit_distance([], ["a", "b"]) == 2


def test_word_error_rate():
    assert autodub.word_error_rate("hello world", "hello world") == 0.0
    assert autodub.word_error_rate("hello world", "hello") == pytest.approx(0.5)
    assert autodub.word_error_rate("a b c", "x y z") == pytest.approx(1.0)
    assert autodub.word_error_rate("", "") == 0.0
    assert autodub.word_error_rate("", "junk") == 1.0


def test_artifact_ratios():
    import numpy as np
    assert autodub._clipping_ratio(np.array([1.0, 0.0, -1.0, 0.5], dtype="float32")) == pytest.approx(0.5)
    assert autodub._silence_ratio(np.array([0.0, 0.0, 0.5, 0.5], dtype="float32")) == pytest.approx(0.5)


def test_score_speech_flags_silence_passes_clean(tmp_path):
    import numpy as np
    import soundfile as sf
    sr = 22050
    silent = tmp_path / "silent.wav"
    sf.write(str(silent), np.zeros(sr, dtype="float32"), sr, subtype="PCM_16")
    s = autodub.score_speech(str(silent), "some words here")
    assert s["ok"] is False and "mostly_silence" in s["reasons"]

    tone = tmp_path / "tone.wav"
    sig = (0.3 * np.sin(2 * np.pi * 220 * np.arange(sr) / sr)).astype("float32")
    sf.write(str(tone), sig, sr, subtype="PCM_16")
    s2 = autodub.score_speech(str(tone), "some words here")
    assert s2["ok"] is True


# ── S0: micro-fades (declick) ────────────────────────────
def test_apply_micro_fades_ramps_edges(tmp_path):
    import numpy as np
    import soundfile as sf
    sr = 24000
    p = tmp_path / "tone.wav"
    sf.write(str(p), np.ones(sr, dtype="float32"), sr, subtype="PCM_16")  # 1s full-scale
    autodub._apply_micro_fades(p, fade_ms=8.0)
    data, _ = sf.read(str(p), dtype="float32")
    assert abs(data[0]) < 0.05      # faded in from ~0
    assert abs(data[-1]) < 0.05     # faded out to ~0
    assert data[sr // 2] > 0.9      # middle untouched


# ── S0: stretch-policy inversion (no slowdown) ───────────
def test_speed_factor_no_slowdown_policy():
    # allow_slowdown=False: never below 1.0 (pad instead), speed-up capped
    assert autodub.calculate_speed_factor(1.0, 10.0, allow_slowdown=False) == 1.0
    assert autodub.calculate_speed_factor(10.0, 1.0, allow_slowdown=False) == autodub.STRETCH_MAX_SPEEDUP
    assert autodub.calculate_speed_factor(1.2, 1.0, allow_slowdown=False) == pytest.approx(1.2)
    # default (allow_slowdown=True) is unchanged / backward compatible
    assert autodub.calculate_speed_factor(1.0, 10.0) == 0.5


# ── S0: absolute-timeline placement math ─────────────────
def test_plan_block_pads_short_clip_to_window():
    pad, cursor = autodub._plan_block(actual_ms=800, start_ms=1000, end_ms=3000)   # window 2000
    assert pad == pytest.approx(1200)
    assert cursor == 3000


def test_plan_block_overrun_pushes_cursor():
    pad, cursor = autodub._plan_block(actual_ms=2500, start_ms=1000, end_ms=3000)  # window 2000
    assert pad == 0.0
    assert cursor == 3500                                                          # next gap shrinks


def test_plan_block_within_tolerance_no_pad():
    pad, cursor = autodub._plan_block(actual_ms=1990, start_ms=0, end_ms=2000)
    assert pad == 0.0
    assert cursor == 2000


# ── SY2: absolute-anchor slot math ───────────────────────
def test_plan_anchored_block():
    # over-run: 4000ms clip into slot [1000, 4000] (room 3000) → trim 1000, pad 0
    trim, pad = autodub._plan_anchored_block(4000, 1000, 4000)
    assert trim == pytest.approx(1000) and pad == 0.0
    # short: 2000ms into room 3000 → trim 0, pad 1000
    trim, pad = autodub._plan_anchored_block(2000, 1000, 4000)
    assert trim == 0.0 and pad == pytest.approx(1000)
    # exact fit → neither
    trim, pad = autodub._plan_anchored_block(3000, 1000, 4000)
    assert trim == 0.0 and pad == 0.0


def test_sub_start_ms():
    class _T:
        hours, minutes, seconds, milliseconds = 0, 1, 2, 300

    class _S:
        start = _T()

    assert autodub._sub_start_ms(_S()) == 62300


def test_place_speech_block_anchors_and_trims_overrun(tmp_path):
    import numpy as np
    import soundfile as sf
    sr = 24000
    clip = tmp_path / "clip.wav"
    sf.write(str(clip), np.full(2 * sr, 0.3, dtype="float32"), sr, subtype="PCM_16")  # 2s
    concat, temp = [], []
    # slot [1000, 2000] → room 1000ms; the 2s clip must be trimmed and the cursor anchored
    cursor = autodub._place_speech_block(clip, 1000, 2000, 2000, sr, tmp_path, "t", concat, temp)
    assert cursor == 2000.0                              # anchored to next onset (no drift)
    assert sf.info(str(clip)).duration <= 1.05           # trimmed into the slot


def test_place_speech_block_pads_short_and_anchors(tmp_path):
    import numpy as np
    import soundfile as sf
    sr = 24000
    clip = tmp_path / "clip.wav"
    sf.write(str(clip), np.full(sr // 2, 0.3, dtype="float32"), sr, subtype="PCM_16")  # 0.5s
    concat, temp = [], []
    cursor = autodub._place_speech_block(clip, 1000, 2000, 2000, sr, tmp_path, "t", concat, temp)
    assert cursor == 2000.0
    assert any("fill_t" in c for c in concat)            # padded the 0.5s remainder


# ── Language map ─────────────────────────────────────────
def test_lang_map_core_entries():
    assert autodub.LANG_MAP["az"] == "Azerbaijani"
    assert autodub.LANG_MAP["ru"] == "Russian"
    assert autodub.LANG_MAP["en"] == "English"


# ── OpenAI error classification ──────────────────────────
def test_transient_error_detection():
    assert autodub._is_transient_error(Exception("Rate limit reached, try again")) is True
    assert autodub._is_transient_error(Exception("503 Service Unavailable")) is True
    assert autodub._is_transient_error(Exception("invalid api key")) is False


def test_param_error_detection():
    assert autodub._is_param_error(Exception("Unsupported value: 'temperature'")) is True
    assert autodub._is_param_error(Exception("some other error")) is False


# ── Usage tracking ───────────────────────────────────────
def test_record_usage_accumulates():
    autodub._llm_usage.pop("openai", None)
    autodub._record_llm_usage("openai", 10, 5)
    autodub._record_llm_usage("openai", 10, 5)
    u = autodub._llm_usage["openai"]
    assert u["calls"] == 2
    assert u["input_tokens"] == 20
    assert u["output_tokens"] == 10


# ── Provider registry ────────────────────────────────────
def test_provider_registry_has_openai_and_anthropic():
    assert "openai" in autodub.LLM_PROVIDERS
    assert "anthropic" in autodub.LLM_PROVIDERS
    for name, info in autodub.LLM_PROVIDERS.items():
        assert callable(info["chat"])
        assert info["default_model"]
        assert info["env_key"]


# ── Batch passthrough when no client (both providers) ─────
def test_duration_to_max_chars():
    assert autodub._duration_to_max_chars(3.0, 15.0) == 45
    assert autodub._duration_to_max_chars(0.5, 15.0) == 20    # floored
    assert autodub._duration_to_max_chars(2.0) == 30          # default cps 15
    assert autodub._duration_to_max_chars(10.0, 12.0) == 120


def test_openai_batch_returns_input_when_no_client(monkeypatch):
    monkeypatch.setattr(autodub, "get_openai_client", lambda api_key=None: None)
    out = autodub.translate_openai_batch(["a", "b", "c"], "ru", "gpt-5")
    assert out == ["a", "b", "c"]


def test_anthropic_batch_returns_input_when_no_client(monkeypatch):
    monkeypatch.setattr(autodub, "get_anthropic_client", lambda api_key=None: None)
    out = autodub.translate_llm_batch(["a", "b"], "ru", "anthropic")
    assert out == ["a", "b"]


def test_llm_single_returns_source_on_failure(monkeypatch):
    monkeypatch.setattr(autodub, "get_anthropic_client", lambda api_key=None: None)
    assert autodub.translate_llm("hello", "ru", "anthropic") == "hello"


# ── .env loader ──────────────────────────────────────────
def test_load_dotenv_sets_and_respects_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        '# a comment\n'
        'export AUTODUB_TEST_NEW="from_file"\n'
        "AUTODUB_TEST_EXISTING='ignored'\n"
        'blank line below\n\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("AUTODUB_TEST_EXISTING", "already_set")
    monkeypatch.delenv("AUTODUB_TEST_NEW", raising=False)
    import os
    autodub.load_dotenv(str(env))
    assert os.environ["AUTODUB_TEST_NEW"] == "from_file"
    assert os.environ["AUTODUB_TEST_EXISTING"] == "already_set"  # not overwritten


def test_load_dotenv_missing_file_is_noop(tmp_path):
    assert autodub.load_dotenv(str(tmp_path / "nope.env")) == 0


# ── JSON config defaults ─────────────────────────────────
def test_load_config_defaults_valid(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text('{"translator": "openai", "target_lang": "ru"}', encoding="utf-8")
    d = autodub.load_config_defaults(str(cfg))
    assert d == {"translator": "openai", "target_lang": "ru"}


def test_load_config_defaults_missing_and_invalid(tmp_path):
    assert autodub.load_config_defaults(str(tmp_path / "missing.json")) == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    assert autodub.load_config_defaults(str(bad)) == {}


# ── Transcription backend normalization ──────────────────
def test_transcribe_faster_normalizes(monkeypatch):
    fw = pytest.importorskip("faster_whisper")

    class _Seg:
        def __init__(self, s, e, t):
            self.start, self.end, self.text = s, e, t

    class _Info:
        language = "en"

    class _Model:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, path, **k):
            return iter([_Seg(0.0, 1.0, " hi"), _Seg(1.0, 2.0, " there")]), _Info()

    monkeypatch.setattr(fw, "WhisperModel", _Model)
    segs, lang = autodub.transcribe_audio("x.wav", "tiny", "faster", "cpu")
    assert lang == "en"
    assert segs == [{"start": 0.0, "end": 1.0, "text": " hi", "no_speech_prob": 0.0},
                    {"start": 1.0, "end": 2.0, "text": " there", "no_speech_prob": 0.0}]


def test_refine_bounds_uses_word_onsets():
    # segment start placed too early (5s) → corrected to the first word (17s)
    assert autodub._refine_bounds(5.0, 20.0, [(17.0, 17.5), (19.0, 20.0)]) == (17.0, 20.0)
    assert autodub._refine_bounds(5.0, 20.0, []) == (5.0, 20.0)   # no words → unchanged


# ── Transcription hygiene: non-speech filter ─────────────
def test_filter_nonspeech_segments():
    segs = [
        {"start": 0, "end": 3, "text": "music", "no_speech_prob": 0.9},    # intro → drop
        {"start": 17, "end": 20, "text": "hello", "no_speech_prob": 0.05},  # speech → keep
        {"start": 20, "end": 23, "text": "world"},                          # no field → keep
    ]
    kept = autodub.filter_nonspeech_segments(segs, 0.6)
    assert [s["text"] for s in kept] == ["hello", "world"]
    assert autodub.filter_nonspeech_segments(segs, 1.0) == segs            # disabled


# ── Zero-byte-aware file guard ───────────────────────────
def test_has_content(tmp_path):
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    good = tmp_path / "good.bin"
    good.write_bytes(b"x" * 200)
    assert autodub._has_content(good) is True
    assert autodub._has_content(empty) is False          # stale 0-byte treated as absent
    assert autodub._has_content(good, min_bytes=100) is True
    assert autodub._has_content(good, min_bytes=500) is False
    assert autodub._has_content(tmp_path / "missing.bin") is False


# ── Scoped unsafe torch.load (security hardening) ────────
def test_allow_unsafe_torch_load_scopes_and_restores():
    if autodub.torch is None:
        pytest.skip("torch not installed")
    original = autodub.torch.load
    with autodub._allow_unsafe_torch_load():
        assert autodub.torch.load is not original   # patched only inside the block
    assert autodub.torch.load is original           # restored afterwards


def test_apply_runtime_patches_leaves_torch_load_safe():
    # The global weights_only=False patch must be gone: _apply_runtime_patches
    # must NOT replace torch.load process-wide.
    if autodub.torch is None:
        pytest.skip("torch not installed")
    before = autodub.torch.load
    autodub._apply_runtime_patches()
    assert autodub.torch.load is before


# ── Structured (JSON) logging ────────────────────────────
def test_json_formatter_emits_valid_json():
    import json as _json
    import logging as _logging
    rec = _logging.makeLogRecord({"levelname": "INFO", "msg": "hello %s", "args": ("world",)})
    out = autodub._JsonFormatter().format(rec)
    parsed = _json.loads(out)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "hello world"
    assert "ts" in parsed
