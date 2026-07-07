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
