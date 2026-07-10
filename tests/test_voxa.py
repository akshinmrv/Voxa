"""
Unit tests for Voxa pure logic.

These intentionally cover the deterministic, dependency-free parts of the pipeline
(translation parsing, sentence merging, timing math, error classification). The heavy
runtime deps (whisper/torch/ffmpeg) are not required — voxa guards those imports.

Run:  pytest -q
"""
import pytest

import voxa


# ── OpenAI batch response parsing ────────────────────────
def test_parse_batch_basic():
    assert voxa._parse_batch_translations('{"translations": ["a", "b"]}', 2) == ["a", "b"]


def test_parse_batch_code_fence():
    raw = '```json\n{"translations": ["a", "b", "c"]}\n```'
    assert voxa._parse_batch_translations(raw, 3) == ["a", "b", "c"]


def test_parse_batch_bare_list():
    assert voxa._parse_batch_translations('["x", "y"]', 2) == ["x", "y"]


def test_parse_batch_lines_key():
    assert voxa._parse_batch_translations('{"lines": ["p", "q"]}', 2) == ["p", "q"]


def test_parse_batch_count_mismatch_returns_none():
    assert voxa._parse_batch_translations('{"translations": ["only one"]}', 2) is None


def test_parse_batch_invalid_json_returns_none():
    assert voxa._parse_batch_translations('not json at all', 2) is None


def test_parse_batch_cleans_prefixes():
    raw = '{"translations": ["Translation: Hello", "\\"World\\""]}'
    assert voxa._parse_batch_translations(raw, 2) == ["Hello", "World"]


# ── Line cleaning ────────────────────────────────────────
def test_clean_line_strips_prefix_and_quotes():
    assert voxa._clean_line('Translation: "Hello"') == "Hello"
    assert voxa._clean_line("'Salam'") == "Salam"
    assert voxa._clean_line("  plain text  ") == "plain text"


# ── Sentence merging ─────────────────────────────────────
def test_merge_sentences_groups_until_punctuation():
    segs = [
        {"text": "Hello", "start": 0.0, "end": 1.0},
        {"text": "world.", "start": 1.0, "end": 2.0},
        {"text": "Next one", "start": 2.0, "end": 3.0},
    ]
    merged = voxa.merge_segments_into_sentences(segs, max_duration=10.0)
    assert merged[0]["text"] == "Hello world."
    assert merged[0]["start"] == 0.0
    assert merged[0]["end"] == 2.0
    assert merged[1]["text"] == "Next one"


def test_merge_sentences_splits_on_long_pause():
    segs = [
        {"text": "First", "start": 0.0, "end": 1.0},
        {"text": "Second", "start": 3.0, "end": 4.0},  # 2s gap > 0.5 pause threshold
    ]
    merged = voxa.merge_segments_into_sentences(segs, max_duration=10.0)
    assert len(merged) == 2


# ── Timing / speed math ──────────────────────────────────
def test_speed_factor_within_tolerance_is_one():
    assert voxa.calculate_speed_factor(1.0, 1.0) == 1.0
    assert voxa.calculate_speed_factor(1.02, 1.0) == 1.0


def test_speed_factor_is_clamped():
    assert voxa.calculate_speed_factor(10.0, 1.0) == 2.5
    assert voxa.calculate_speed_factor(1.0, 10.0) == 0.5


def test_speed_factor_zero_target_safe():
    assert voxa.calculate_speed_factor(5.0, 0.0) == 1.0


# ── S0: TTS text normalization + chunking ────────────────
def test_normalize_tts_text_guarantees_terminal_punctuation():
    assert voxa.normalize_tts_text("hello world") == "hello world."
    assert voxa.normalize_tts_text("what?") == "what?"
    assert voxa.normalize_tts_text("  a   b  ") == "a b."
    assert voxa.normalize_tts_text("line1\nline2") == "line1 line2."
    assert voxa.normalize_tts_text("") == ""
    assert voxa.normalize_tts_text("   ") == ""


def test_normalize_tts_text_folds_typography():
    assert voxa.normalize_tts_text("“hi” — there…") == '"hi" , there.'


def test_infer_delivery():
    assert "question" in voxa.infer_delivery("Necəsən?")
    assert "energetic" in voxa.infer_delivery("Bu mükəmməldir!")
    assert "trail off" in voxa.infer_delivery("Bilmirəm...")
    assert voxa.infer_delivery("Salam dostlar.") == ""
    assert voxa.infer_delivery("") == ""


def test_split_for_tts_short_passthrough():
    assert voxa.split_for_tts("short text") == ["short text"]
    assert voxa.split_for_tts("") == []


def test_split_for_tts_respects_max_and_boundaries():
    text = "First sentence here. Second sentence here. Third sentence here."
    chunks = voxa.split_for_tts(text, max_chars=25)
    assert len(chunks) >= 2
    assert all(0 < len(c) <= 25 for c in chunks)


def test_split_for_tts_hard_wraps_unpunctuated():
    text = ("wordword " * 40).strip()   # ~350 chars, no sentence punctuation
    chunks = voxa.split_for_tts(text, max_chars=100)
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
    voxa.generate_openai_tts(subs, _Client(), "alloy", "gpt-4o-mini-tts", "", "az",
                                concat, temp, tmp_path, enable_stretch=True)
    finals = [c for c in concat if "otts_fin_" in c]
    assert len(finals) == 2


# ── S1: quality scoring primitives ───────────────────────
def test_normalize_for_compare():
    assert voxa._normalize_for_compare("Hello, World!") == "hello world"
    assert voxa._normalize_for_compare("  A  b  ") == "a b"


def test_edit_distance():
    assert voxa._edit_distance(["a", "b", "c"], ["a", "b", "c"]) == 0
    assert voxa._edit_distance(["a", "b"], ["a"]) == 1
    assert voxa._edit_distance([], ["a", "b"]) == 2


def test_word_error_rate():
    assert voxa.word_error_rate("hello world", "hello world") == 0.0
    assert voxa.word_error_rate("hello world", "hello") == pytest.approx(0.5)
    assert voxa.word_error_rate("a b c", "x y z") == pytest.approx(1.0)
    assert voxa.word_error_rate("", "") == 0.0
    assert voxa.word_error_rate("", "junk") == 1.0


def test_artifact_ratios():
    import numpy as np
    assert voxa._clipping_ratio(np.array([1.0, 0.0, -1.0, 0.5], dtype="float32")) == pytest.approx(0.5)
    assert voxa._silence_ratio(np.array([0.0, 0.0, 0.5, 0.5], dtype="float32")) == pytest.approx(0.5)


def test_score_speech_flags_silence_passes_clean(tmp_path):
    import numpy as np
    import soundfile as sf
    sr = 22050
    silent = tmp_path / "silent.wav"
    sf.write(str(silent), np.zeros(sr, dtype="float32"), sr, subtype="PCM_16")
    s = voxa.score_speech(str(silent), "some words here")
    assert s["ok"] is False and "mostly_silence" in s["reasons"]

    tone = tmp_path / "tone.wav"
    sig = (0.3 * np.sin(2 * np.pi * 220 * np.arange(sr) / sr)).astype("float32")
    sf.write(str(tone), sig, sr, subtype="PCM_16")
    s2 = voxa.score_speech(str(tone), "some words here")
    assert s2["ok"] is True


# ── S0: micro-fades (declick) ────────────────────────────
def test_apply_micro_fades_ramps_edges(tmp_path):
    import numpy as np
    import soundfile as sf
    sr = 24000
    p = tmp_path / "tone.wav"
    sf.write(str(p), np.ones(sr, dtype="float32"), sr, subtype="PCM_16")  # 1s full-scale
    voxa._apply_micro_fades(p, fade_ms=8.0)
    data, _ = sf.read(str(p), dtype="float32")
    assert abs(data[0]) < 0.05      # faded in from ~0
    assert abs(data[-1]) < 0.05     # faded out to ~0
    assert data[sr // 2] > 0.9      # middle untouched


# ── S0: stretch-policy inversion (no slowdown) ───────────
def test_speed_factor_no_slowdown_policy():
    # allow_slowdown=False: never below 1.0 (pad instead), speed-up capped
    assert voxa.calculate_speed_factor(1.0, 10.0, allow_slowdown=False) == 1.0
    assert voxa.calculate_speed_factor(10.0, 1.0, allow_slowdown=False) == voxa.STRETCH_MAX_SPEEDUP
    assert voxa.calculate_speed_factor(1.2, 1.0, allow_slowdown=False) == pytest.approx(1.2)
    # default (allow_slowdown=True) is unchanged / backward compatible
    assert voxa.calculate_speed_factor(1.0, 10.0) == 0.5


# ── S0: absolute-timeline placement math ─────────────────
def test_plan_block_pads_short_clip_to_window():
    pad, cursor = voxa._plan_block(actual_ms=800, start_ms=1000, end_ms=3000)   # window 2000
    assert pad == pytest.approx(1200)
    assert cursor == 3000


def test_plan_block_overrun_pushes_cursor():
    pad, cursor = voxa._plan_block(actual_ms=2500, start_ms=1000, end_ms=3000)  # window 2000
    assert pad == 0.0
    assert cursor == 3500                                                          # next gap shrinks


def test_plan_block_within_tolerance_no_pad():
    pad, cursor = voxa._plan_block(actual_ms=1990, start_ms=0, end_ms=2000)
    assert pad == 0.0
    assert cursor == 2000


# ── SY2: absolute-anchor slot math ───────────────────────
def test_plan_anchored_block():
    # over-run: 4000ms clip into slot [1000, 4000] (room 3000) → trim 1000, pad 0
    trim, pad = voxa._plan_anchored_block(4000, 1000, 4000)
    assert trim == pytest.approx(1000) and pad == 0.0
    # short: 2000ms into room 3000 → trim 0, pad 1000
    trim, pad = voxa._plan_anchored_block(2000, 1000, 4000)
    assert trim == 0.0 and pad == pytest.approx(1000)
    # exact fit → neither
    trim, pad = voxa._plan_anchored_block(3000, 1000, 4000)
    assert trim == 0.0 and pad == 0.0


def test_sub_start_ms():
    class _T:
        hours, minutes, seconds, milliseconds = 0, 1, 2, 300

    class _S:
        start = _T()

    assert voxa._sub_start_ms(_S()) == 62300


def test_place_speech_block_anchors_and_trims_overrun(tmp_path):
    import numpy as np
    import soundfile as sf
    sr = 24000
    clip = tmp_path / "clip.wav"
    sf.write(str(clip), np.full(2 * sr, 0.3, dtype="float32"), sr, subtype="PCM_16")  # 2s
    concat, temp = [], []
    # slot [1000, 2000] → room 1000ms; the 2s clip must be trimmed and the cursor anchored
    cursor = voxa._place_speech_block(clip, 1000, 2000, 2000, sr, tmp_path, "t", concat, temp)
    assert cursor == 2000.0                              # anchored to next onset (no drift)
    assert sf.info(str(clip)).duration <= 1.05           # trimmed into the slot


def test_place_speech_block_pads_short_and_anchors(tmp_path):
    import numpy as np
    import soundfile as sf
    sr = 24000
    clip = tmp_path / "clip.wav"
    sf.write(str(clip), np.full(sr // 2, 0.3, dtype="float32"), sr, subtype="PCM_16")  # 0.5s
    concat, temp = [], []
    cursor = voxa._place_speech_block(clip, 1000, 2000, 2000, sr, tmp_path, "t", concat, temp)
    assert cursor == 2000.0
    assert any("fill_t" in c for c in concat)            # padded the 0.5s remainder


# ── Language map ─────────────────────────────────────────
def test_lang_map_core_entries():
    assert voxa.LANG_MAP["az"] == "Azerbaijani"
    assert voxa.LANG_MAP["ru"] == "Russian"
    assert voxa.LANG_MAP["en"] == "English"


# ── OpenAI error classification ──────────────────────────
def test_transient_error_detection():
    assert voxa._is_transient_error(Exception("Rate limit reached, try again")) is True
    assert voxa._is_transient_error(Exception("503 Service Unavailable")) is True
    assert voxa._is_transient_error(Exception("invalid api key")) is False


def test_param_error_detection():
    assert voxa._is_param_error(Exception("Unsupported value: 'temperature'")) is True
    assert voxa._is_param_error(Exception("some other error")) is False


# ── Usage tracking ───────────────────────────────────────
def test_record_usage_accumulates():
    voxa._llm_usage.pop("openai", None)
    voxa._record_llm_usage("openai", 10, 5)
    voxa._record_llm_usage("openai", 10, 5)
    u = voxa._llm_usage["openai"]
    assert u["calls"] == 2
    assert u["input_tokens"] == 20
    assert u["output_tokens"] == 10


# ── Provider registry ────────────────────────────────────
def test_provider_registry_has_openai_and_anthropic():
    assert "openai" in voxa.LLM_PROVIDERS
    assert "anthropic" in voxa.LLM_PROVIDERS
    for name, info in voxa.LLM_PROVIDERS.items():
        assert callable(info["chat"])
        assert info["default_model"]
        assert info["env_key"]


# ── Batch passthrough when no client (both providers) ─────
def test_duration_to_max_chars():
    assert voxa._duration_to_max_chars(3.0, 15.0) == 45
    assert voxa._duration_to_max_chars(0.5, 15.0) == 20    # floored
    assert voxa._duration_to_max_chars(2.0) == 30          # default cps 15
    assert voxa._duration_to_max_chars(10.0, 12.0) == 120


def test_openai_batch_returns_input_when_no_client(monkeypatch):
    monkeypatch.setattr(voxa, "get_openai_client", lambda api_key=None: None)
    out = voxa.translate_openai_batch(["a", "b", "c"], "ru", "gpt-5")
    assert out == ["a", "b", "c"]


def test_anthropic_batch_returns_input_when_no_client(monkeypatch):
    monkeypatch.setattr(voxa, "get_anthropic_client", lambda api_key=None: None)
    out = voxa.translate_llm_batch(["a", "b"], "ru", "anthropic")
    assert out == ["a", "b"]


def test_llm_single_returns_source_on_failure(monkeypatch):
    monkeypatch.setattr(voxa, "get_anthropic_client", lambda api_key=None: None)
    assert voxa.translate_llm("hello", "ru", "anthropic") == "hello"


# ── .env loader ──────────────────────────────────────────
def test_load_dotenv_sets_and_respects_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        '# a comment\n'
        'export VOXA_TEST_NEW="from_file"\n'
        "VOXA_TEST_EXISTING='ignored'\n"
        'blank line below\n\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("VOXA_TEST_EXISTING", "already_set")
    monkeypatch.delenv("VOXA_TEST_NEW", raising=False)
    import os
    voxa.load_dotenv(str(env))
    assert os.environ["VOXA_TEST_NEW"] == "from_file"
    assert os.environ["VOXA_TEST_EXISTING"] == "already_set"  # not overwritten


def test_load_dotenv_missing_file_is_noop(tmp_path):
    assert voxa.load_dotenv(str(tmp_path / "nope.env")) == 0


# ── JSON config defaults ─────────────────────────────────
def test_load_config_defaults_valid(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text('{"translator": "openai", "target_lang": "ru"}', encoding="utf-8")
    d = voxa.load_config_defaults(str(cfg))
    assert d == {"translator": "openai", "target_lang": "ru"}


def test_load_config_defaults_missing_and_invalid(tmp_path):
    assert voxa.load_config_defaults(str(tmp_path / "missing.json")) == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    assert voxa.load_config_defaults(str(bad)) == {}


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
    segs, lang = voxa.transcribe_audio("x.wav", "tiny", "faster", "cpu")
    assert lang == "en"
    assert segs == [{"start": 0.0, "end": 1.0, "text": " hi", "no_speech_prob": 0.0},
                    {"start": 1.0, "end": 2.0, "text": " there", "no_speech_prob": 0.0}]


def test_refine_bounds_uses_word_onsets():
    # segment start placed too early (5s) → corrected to the first word (17s)
    assert voxa._refine_bounds(5.0, 20.0, [(17.0, 17.5), (19.0, 20.0)]) == (17.0, 20.0)
    assert voxa._refine_bounds(5.0, 20.0, []) == (5.0, 20.0)   # no words → unchanged


# ── Transcription hygiene: non-speech filter ─────────────
def test_filter_nonspeech_segments():
    segs = [
        {"start": 0, "end": 3, "text": "music", "no_speech_prob": 0.9},    # intro → drop
        {"start": 17, "end": 20, "text": "hello", "no_speech_prob": 0.05},  # speech → keep
        {"start": 20, "end": 23, "text": "world"},                          # no field → keep
    ]
    kept = voxa.filter_nonspeech_segments(segs, 0.6)
    assert [s["text"] for s in kept] == ["hello", "world"]
    assert voxa.filter_nonspeech_segments(segs, 1.0) == segs            # disabled


# ── Zero-byte-aware file guard ───────────────────────────
def test_has_content(tmp_path):
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    good = tmp_path / "good.bin"
    good.write_bytes(b"x" * 200)
    assert voxa._has_content(good) is True
    assert voxa._has_content(empty) is False          # stale 0-byte treated as absent
    assert voxa._has_content(good, min_bytes=100) is True
    assert voxa._has_content(good, min_bytes=500) is False
    assert voxa._has_content(tmp_path / "missing.bin") is False


# ── Scoped unsafe torch.load (security hardening) ────────
def test_allow_unsafe_torch_load_scopes_and_restores():
    if voxa.torch is None:
        pytest.skip("torch not installed")
    original = voxa.torch.load
    with voxa._allow_unsafe_torch_load():
        assert voxa.torch.load is not original   # patched only inside the block
    assert voxa.torch.load is original           # restored afterwards


def test_apply_runtime_patches_leaves_torch_load_safe():
    # The global weights_only=False patch must be gone: _apply_runtime_patches
    # must NOT replace torch.load process-wide.
    if voxa.torch is None:
        pytest.skip("torch not installed")
    before = voxa.torch.load
    voxa._apply_runtime_patches()
    assert voxa.torch.load is before


# ── Structured (JSON) logging ────────────────────────────
def test_json_formatter_emits_valid_json():
    import json as _json
    import logging as _logging
    rec = _logging.makeLogRecord({"levelname": "INFO", "msg": "hello %s", "args": ("world",)})
    out = voxa._JsonFormatter().format(rec)
    parsed = _json.loads(out)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "hello world"
    assert "ts" in parsed


# ── TTS provider registry ────────────────────────────────
def _fake_logger():
    import logging as _logging
    return _logging.getLogger("test_voxa_tts")


def test_tts_providers_registry_shape():
    # Registry is the single source of truth for --tts; every engine has an adapter.
    assert set(voxa.TTS_PROVIDERS) == {"edge", "piper", "xtts", "openai"}
    for name, spec in voxa.TTS_PROVIDERS.items():
        assert callable(spec["synthesize"]), name


def test_tts_error_is_exception():
    assert issubclass(voxa.TTSError, Exception)


def test_tts_xtts_rejects_unsupported_language():
    # 'az' is not an XTTS language -> adapter aborts before any model load.
    import asyncio
    from types import SimpleNamespace
    args = SimpleNamespace(target_lang="az", voice_sample=None, no_stretch=True,
                           quality_gate=False)
    with pytest.raises(voxa.TTSError):
        asyncio.run(voxa._tts_xtts(None, args, None, None, None, _fake_logger()))


def test_tts_openai_requires_key(monkeypatch):
    # No usable client -> adapter raises TTSError (dispatch turns this into exit 1).
    import asyncio
    from types import SimpleNamespace
    monkeypatch.setattr(voxa, "get_openai_client", lambda *a, **k: None)
    args = SimpleNamespace(openai_api_key=None, target_lang="en", no_stretch=True,
                           quality_gate=False, openai_voice="nova",
                           openai_tts_model="gpt-4o-mini-tts", openai_tts_instructions="")
    with pytest.raises(voxa.TTSError):
        asyncio.run(voxa._tts_openai(None, args, None, None, None, _fake_logger()))


# ── A2 T1: LLM-inferred per-line delivery ────────────────
def test_parse_delivery_json_valid():
    assert voxa._parse_delivery_json('{"deliveries": ["warm", "", "urgent"]}', 3) == \
        ["warm", "", "urgent"]


def test_parse_delivery_json_bare_list_and_fence():
    assert voxa._parse_delivery_json('```json\n["a", "b"]\n```', 2) == ["a", "b"]


def test_parse_delivery_json_count_mismatch_is_neutral():
    # Wrong count -> all neutral so the caller falls back to the heuristic.
    assert voxa._parse_delivery_json('{"deliveries": ["only one"]}', 3) == ["", "", ""]


def test_parse_delivery_json_unparseable_is_neutral():
    assert voxa._parse_delivery_json("not json at all", 2) == ["", ""]
    assert voxa._parse_delivery_json("", 2) == ["", ""]


def test_infer_delivery_llm_no_client_is_neutral():
    assert voxa.infer_delivery_llm(["a", "b"], None) == ["", ""]
    assert voxa.infer_delivery_llm([], object()) == []


def test_infer_delivery_llm_uses_client():
    from types import SimpleNamespace
    captured = {}

    def _create(**kwargs):
        captured.update(kwargs)
        msg = SimpleNamespace(content='{"deliveries": ["calm, warm", "tense, fast"]}')
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    out = voxa.infer_delivery_llm(["Hello.", "Run!"], client)
    assert out == ["calm, warm", "tense, fast"]
    # both source lines are handed to the model in order
    assert "Hello." in captured["messages"][1]["content"]
    assert "Run!" in captured["messages"][1]["content"]


def test_delivery_hint_prefers_llm_tag():
    assert voxa._delivery_hint(1, ["", "warm, unhurried"], "Salam.") == "warm, unhurried"


def test_delivery_hint_falls_back_to_structural():
    assert "question" in voxa._delivery_hint(0, [], "Necəsən?")
    assert "question" in voxa._delivery_hint(0, [""], "Necəsən?")     # empty LLM tag
    assert "question" in voxa._delivery_hint(5, ["a"], "Necəsən?")    # index out of range


def test_delivery_hint_uses_raw_line_not_normalized():
    # normalize_tts_text folds '…' to '.', which would hide the trailing-off hint —
    # the hint must therefore be inferred from the raw subtitle line.
    raw = "Bilmirəm…"
    assert voxa.normalize_tts_text(raw) == "Bilmirəm."
    assert voxa.infer_delivery(voxa.normalize_tts_text(raw)) == ""
    assert "trail off" in voxa._delivery_hint(0, [], raw)


def test_infer_delivery_llm_client_error_is_neutral():
    from types import SimpleNamespace

    def _boom(**kwargs):
        raise RuntimeError("api down")

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_boom)))
    assert voxa.infer_delivery_llm(["a", "b", "c"], client) == ["", "", ""]


# ── A3: quality-gate auto-regeneration (XTTS) selection logic ──
def test_score_better_prefers_passing_gate():
    ok = {"ok": True, "reasons": [], "wer": 0.9}
    bad = {"ok": False, "reasons": ["asr"], "wer": 0.1}
    assert voxa._score_better(ok, bad)
    assert not voxa._score_better(bad, ok)


def test_score_better_fewer_failed_checks():
    assert voxa._score_better({"ok": False, "reasons": ["asr"], "wer": 0.7},
                                 {"ok": False, "reasons": ["asr", "clipping"], "wer": 0.7})


def test_score_better_lower_wer_on_tie():
    assert voxa._score_better({"ok": False, "reasons": ["asr"], "wer": 0.65},
                                 {"ok": False, "reasons": ["asr"], "wer": 0.80})
    same = {"ok": False, "reasons": ["asr"], "wer": 0.7}
    assert not voxa._score_better(same, dict(same))   # not strictly better than itself


def test_safe_unlink_removes_and_ignores_missing(tmp_path):
    p = tmp_path / "x.wav"
    p.write_bytes(b"data")
    voxa._safe_unlink(p, tmp_path / "missing.wav")   # must not raise on the missing one
    assert not p.exists()


def _fake_sub(text, start_ms, end_ms):
    from types import SimpleNamespace

    def _t(ms):
        return SimpleNamespace(hours=0, minutes=0, seconds=ms // 1000, milliseconds=ms % 1000)
    return SimpleNamespace(text=text, start=_t(start_ms), end=_t(end_ms))


# ── T1: Piper brought up to the S0/SY2 standard ──────────
class _FakePiperPopen:
    """Stand-in for the piper binary: writes a non-empty WAV to --output_file."""
    def __init__(self, cmd, **kwargs):
        self.cmd = cmd

    def communicate(self, input=None):
        from pathlib import Path as _P
        out = _P(self.cmd[self.cmd.index("--output_file") + 1])
        out.write_bytes(b"RAW".ljust(1500, b"0"))
        return b"", b""


def _patch_piper_placement(monkeypatch):
    """Replace placement with a recorder; returns the list it appends to."""
    placed = []

    def _place(final_file, start_ms, end_ms, next_start_ms, sr, work_dir, tag,
               concat_list, temp_files):
        placed.append({"tag": tag, "start": start_ms, "next": next_start_ms})
        concat_list.append(f"file '{final_file}'")
        return float(next_start_ms) if next_start_ms is not None else float(end_ms)

    monkeypatch.setattr(voxa, "_place_speech_block", _place)
    return placed


def test_piper_anchors_placement_and_never_slows_down(tmp_path, monkeypatch):
    monkeypatch.setattr(voxa.shutil, "which", lambda name: "piper")
    monkeypatch.setattr(voxa.subprocess, "Popen", _FakePiperPopen)

    captured = {}

    def _stretch(src, dst, target, work_dir, sr, allow_slowdown=True):
        captured["allow_slowdown"] = allow_slowdown
        __import__("pathlib").Path(dst).write_bytes(b"FIN".ljust(1500, b"0"))
        return True
    monkeypatch.setattr(voxa, "stretch_audio_smart", _stretch)
    placed = _patch_piper_placement(monkeypatch)

    subs = [_fake_sub("Salam dostlar.", 0, 1000), _fake_sub("Necəsən?", 1500, 2500)]
    concat, temps = [], []
    voxa.generate_piper(subs, tmp_path / "model.onnx", concat, temps, tmp_path,
                           enable_stretch=True)

    assert captured["allow_slowdown"] is False        # S0: speed up only, never drag
    assert len(placed) == 2                            # every segment placed
    assert placed[0]["next"] == 1500                   # SY2: anchored to the next onset
    assert placed[1]["next"] is None                   # last segment pads to its window


def test_piper_resume_places_cached_segment(tmp_path, monkeypatch):
    """Regression: placement used to live inside the `not exists` branch, so a resumed run
    silently dropped every already-synthesized segment from the concat list."""
    monkeypatch.setattr(voxa.shutil, "which", lambda name: "piper")

    def _boom(*a, **k):
        raise AssertionError("piper must not be re-invoked for a cached segment")
    monkeypatch.setattr(voxa.subprocess, "Popen", _boom)
    placed = _patch_piper_placement(monkeypatch)

    (tmp_path / "p_fin_0.wav").write_bytes(b"CACHED".ljust(1500, b"0"))

    concat, temps = [], []
    voxa.generate_piper([_fake_sub("Salam.", 0, 1000)], tmp_path / "model.onnx",
                           concat, temps, tmp_path, enable_stretch=True)

    assert len(placed) == 1
    assert concat and "p_fin_0.wav" in concat[0]


def test_a3_regen_keeps_best_take(tmp_path, monkeypatch):
    """A3 orchestration (dev-side, XTTS mocked): a flagged first take is re-rolled and the
    best-scoring candidate is promoted to the placed file. Validates the regen loop without
    a real XTTS install (the actual synthesis is validated by the user on Ubuntu)."""
    spk = tmp_path / "spk.wav"
    spk.write_bytes(b"\0" * 2000)

    # First-attempt synth + fit -> writes raw then final (>=1000 bytes each).
    monkeypatch.setattr(voxa, "_xtts_synthesize_segment",
                        lambda *a, **k: (a[4].write_bytes(b"FIRST".ljust(1500, b"0")) or True))
    monkeypatch.setattr(voxa, "stretch_audio_smart",
                        lambda src, dst, *a, **k: (__import__("pathlib").Path(dst)
                                                   .write_bytes(b"FIRST".ljust(1500, b"0")) or True))

    # Each regeneration writes distinctive content so we can see which one was promoted.
    calls = {"fit": 0}

    def _cand(model, text, spk_, lang, raw_path, fin_path, work_dir, tag, sr, dur, stretch):
        calls["fit"] += 1
        fin_path.write_bytes(f"CAND{calls['fit']}".encode().ljust(1500, b"0"))
        return True
    monkeypatch.setattr(voxa, "_xtts_fit_candidate", _cand)

    # Scripted scores: first take flagged, cand1 better-but-flagged, cand2 passes.
    seq = iter([
        {"ok": False, "reasons": ["asr"], "wer": 0.8},   # first take
        {"ok": False, "reasons": ["asr"], "wer": 0.4},   # candidate 1
        {"ok": True,  "reasons": [],      "wer": 0.1},   # candidate 2
    ])
    monkeypatch.setattr(voxa, "score_speech", lambda *a, **k: next(seq))

    placed = {}
    monkeypatch.setattr(voxa, "_place_speech_block",
                        lambda final_file, *a, **k: (placed.update(
                            bytes=final_file.read_bytes()) or 1000.0))

    concat, temps = [], []
    voxa.generate_xtts([_fake_sub("Merhaba dünya", 0, 1000)], object(), str(spk), "tr",
                          concat, temps, tmp_path, enable_stretch=True,
                          quality_gate=True, asr_model=object())

    assert calls["fit"] == 2                       # re-rolled until it passed (2 attempts)
    assert placed["bytes"].startswith(b"CAND2")    # the passing take was promoted + placed
