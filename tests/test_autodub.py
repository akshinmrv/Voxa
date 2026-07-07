"""
Unit tests for AutoDub pure logic.

These intentionally cover the deterministic, dependency-free parts of the pipeline
(translation parsing, sentence merging, timing math, error classification). The heavy
runtime deps (whisper/torch/ffmpeg) are not required — autodub guards those imports.

Run:  pytest -q
"""
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
    for k in autodub._openai_usage:
        autodub._openai_usage[k] = 0

    class _Usage:
        prompt_tokens = 10
        completion_tokens = 5
        total_tokens = 15

    autodub._record_openai_usage(_Usage())
    autodub._record_openai_usage(_Usage())
    assert autodub._openai_usage["calls"] == 2
    assert autodub._openai_usage["total_tokens"] == 30


# ── Batch passthrough when no client ─────────────────────
def test_batch_returns_input_when_no_client(monkeypatch):
    monkeypatch.setattr(autodub, "get_openai_client", lambda api_key=None: None)
    out = autodub.translate_openai_batch(["a", "b", "c"], "ru", "gpt-5")
    assert out == ["a", "b", "c"]
