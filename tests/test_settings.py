"""
Unit tests for the operator server's Settings & API-key layer (P0 — Foundation).

These cover the deterministic file/merge/masking logic in isolation: the settings
JSON store, the .env key store, and value masking. Real file paths are redirected to
a tmp dir so nothing touches the developer's own .voxa_serve/ or .env.

Run:  pytest -q tests/test_settings.py
"""
import pytest
from fastapi.testclient import TestClient

import voxa_server as srv


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Point the settings file and .env at a fresh tmp dir for each test."""
    monkeypatch.setattr(srv, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(srv, "ENV_FILE", str(tmp_path / ".env"))
    # Keep the process environment clean of the keys we touch.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return tmp_path


# ── settings JSON store ──────────────────────────────────
def test_defaults_when_no_file(store):
    s = srv.read_settings()
    assert s["version"] == srv.SETTINGS_VERSION
    assert s["defaultTranslator"] == "google"
    assert s["defaultTts"] == "edge"
    assert s["translation"] == {"prompt": None}


def test_write_then_read_roundtrip(store):
    srv.write_settings({"defaultTranslator": "openai"})
    assert srv.read_settings()["defaultTranslator"] == "openai"
    # Untouched keys keep their defaults.
    assert srv.read_settings()["defaultTts"] == "edge"


def test_partial_patch_ignores_none(store):
    srv.write_settings({"defaultTranslator": "anthropic"})
    srv.write_settings({"defaultTranslator": None, "defaultTts": "openai"})
    s = srv.read_settings()
    assert s["defaultTranslator"] == "anthropic"  # None patch left it alone
    assert s["defaultTts"] == "openai"


def test_nested_group_merges(store):
    srv.write_settings({"translation": {"prompt": "Custom {target_lang}"}})
    srv.write_settings({"speech": {"instructions": "warm"}})
    s = srv.read_settings()
    assert s["translation"]["prompt"] == "Custom {target_lang}"
    assert s["speech"]["instructions"] == "warm"  # a different group is untouched


def test_missing_keys_backfilled_from_defaults(store):
    # An older/sparse on-disk file must still read back fully shaped.
    (store / "settings.json").write_text('{"defaultTranslator": "openai"}', encoding="utf-8")
    s = srv.read_settings()
    assert s["defaultTts"] == "edge"
    assert s["advanced"] == {"speechRate": None}


def test_invalid_file_falls_back_to_defaults(store):
    (store / "settings.json").write_text("not json", encoding="utf-8")
    assert srv.read_settings()["defaultTranslator"] == "google"


def test_reset_removes_file(store):
    srv.write_settings({"defaultTranslator": "openai"})
    srv.reset_settings()
    assert not (store / "settings.json").exists()
    assert srv.read_settings()["defaultTranslator"] == "google"


# ── masking ──────────────────────────────────────────────
def test_mask_shows_only_last_four():
    assert srv._mask("sk-abcdef1234") == "••••1234"


def test_mask_short_value_fully_hidden():
    assert srv._mask("abc") == "••••"
    assert srv._mask("") == "••••"


# ── .env key store ───────────────────────────────────────
def test_set_key_writes_env_and_environ(store):
    srv.set_env_key("OPENAI_API_KEY", "sk-test1234")
    assert "OPENAI_API_KEY=sk-test1234" in (store / ".env").read_text(encoding="utf-8")
    import os
    assert os.environ["OPENAI_API_KEY"] == "sk-test1234"


def test_set_key_upserts_not_duplicates(store):
    srv.set_env_key("OPENAI_API_KEY", "sk-first")
    srv.set_env_key("OPENAI_API_KEY", "sk-second")
    body = (store / ".env").read_text(encoding="utf-8")
    assert body.count("OPENAI_API_KEY=") == 1
    assert "sk-second" in body


def test_set_key_preserves_other_lines(store):
    (store / ".env").write_text("OTHER=keep\nANTHROPIC_API_KEY=sk-ant\n", encoding="utf-8")
    srv.set_env_key("OPENAI_API_KEY", "sk-new")
    body = (store / ".env").read_text(encoding="utf-8")
    assert "OTHER=keep" in body
    assert "ANTHROPIC_API_KEY=sk-ant" in body
    assert "OPENAI_API_KEY=sk-new" in body


def test_delete_key_removes_line_and_environ(store):
    srv.set_env_key("OPENAI_API_KEY", "sk-test")
    srv.delete_env_key("OPENAI_API_KEY")
    import os
    assert "OPENAI_API_KEY" not in os.environ
    assert "OPENAI_API_KEY" not in (store / ".env").read_text(encoding="utf-8")


def test_key_status_reports_masked(store):
    srv.set_env_key("OPENAI_API_KEY", "sk-abcdef9999")
    status = {row["provider"]: row for row in srv.read_key_status()}
    assert status["openai"]["hasKey"] is True
    assert status["openai"]["masked"] == "••••9999"
    assert status["anthropic"]["hasKey"] is False
    assert status["anthropic"]["masked"] is None


def test_key_status_never_returns_raw_value(store):
    srv.set_env_key("OPENAI_API_KEY", "sk-supersecret")
    for row in srv.read_key_status():
        assert "sk-supersecret" not in str(row)


# ── validation helper ────────────────────────────────────
def test_valid_translators_includes_registry_and_builtin():
    v = srv.valid_translators()
    assert {"google", "ollama", "openai", "anthropic"} <= v


# ── P1: per-provider model + connection test ─────────────
def test_default_settings_has_provider_slots():
    p = srv.default_settings()["providers"]
    assert p["openai"] == {"model": None}
    assert p["anthropic"] == {"model": None}


def test_provider_model_args_uses_saved_model():
    settings = {"providers": {"openai": {"model": "gpt-5"}}}
    assert srv.provider_model_args("openai", settings) == ["--openai_model", "gpt-5"]


def test_provider_model_args_empty_without_model():
    assert srv.provider_model_args("openai", {"providers": {"openai": {"model": None}}}) == []
    assert srv.provider_model_args("anthropic", {}) == []


def test_provider_model_args_ignores_non_llm_translator():
    assert srv.provider_model_args("google", {"providers": {"google": {"model": "x"}}}) == []


def test_provider_settings_merge_preserves_siblings(store):
    srv.write_settings({"providers": {"openai": {"model": "gpt-5"}}})
    s = srv.read_settings()
    assert s["providers"]["openai"]["model"] == "gpt-5"
    assert s["providers"]["anthropic"] == {"model": None}  # sibling untouched


def test_test_provider_unknown():
    assert srv.test_provider("gemini")["ok"] is False


def test_test_provider_no_key(store):
    result = srv.test_provider("openai")
    assert result["ok"] is False
    assert "key" in result["error"].lower()


def test_build_options_exposes_default_model():
    translators = {t["id"]: t for t in srv.build_options()["translators"]}
    assert translators["openai"]["defaultModel"] == voxa_default_model("openai")
    assert "defaultModel" not in translators["google"]  # non-LLM has no model


def voxa_default_model(pid: str) -> str:
    import voxa
    return voxa.LLM_PROVIDERS[pid]["default_model"]


# ── HTTP endpoints (FastAPI) ─────────────────────────────
@pytest.fixture
def client(store):
    """TestClient with the local-only guard bypassed (TestClient's host isn't loopback)."""
    srv.app.dependency_overrides[srv.require_local] = lambda: None
    try:
        yield TestClient(srv.app)
    finally:
        srv.app.dependency_overrides.pop(srv.require_local, None)


def test_guard_blocks_non_local_caller(store):
    # Without the override, the TestClient host ("testclient") is not loopback → 403.
    c = TestClient(srv.app)
    assert c.put("/api/settings", json={"defaultTts": "openai"}).status_code == 403


def test_get_settings_is_open(store):
    # Reading settings needs no guard (no secrets), so it works even for TestClient.
    assert TestClient(srv.app).get("/api/settings").status_code == 200


def test_put_settings_roundtrip_over_http(client):
    r = client.put("/api/settings", json={"defaultTranslator": "anthropic"})
    assert r.status_code == 200
    assert r.json()["defaultTranslator"] == "anthropic"
    assert client.get("/api/settings").json()["defaultTranslator"] == "anthropic"


def test_put_settings_rejects_unknown_translator(client):
    r = client.put("/api/settings", json={"defaultTranslator": "nope"})
    assert r.status_code == 422


def test_reset_over_http(client):
    client.put("/api/settings", json={"defaultTranslator": "openai"})
    client.post("/api/settings/reset")
    assert client.get("/api/settings").json()["defaultTranslator"] == "google"


def test_put_and_get_key_over_http(client):
    r = client.put("/api/keys/openai", json={"value": "sk-http1234"})
    assert r.status_code == 200
    openai = {row["provider"]: row for row in r.json()["keys"]}["openai"]
    assert openai["hasKey"] is True
    assert openai["masked"] == "••••1234"
    # The raw value is never in the response.
    assert "sk-http1234" not in r.text


def test_put_key_unknown_provider_404(client):
    assert client.put("/api/keys/gemini", json={"value": "x"}).status_code == 404


def test_put_key_empty_value_422(client):
    assert client.put("/api/keys/openai", json={"value": "   "}).status_code == 422


def test_delete_key_over_http(client):
    client.put("/api/keys/openai", json={"value": "sk-todelete"})
    r = client.delete("/api/keys/openai")
    assert r.status_code == 200
    openai = {row["provider"]: row for row in r.json()["keys"]}["openai"]
    assert openai["hasKey"] is False


def test_put_settings_rejects_unknown_provider(client):
    r = client.put("/api/settings", json={"providers": {"gemini": {"model": "x"}}})
    assert r.status_code == 422


def test_provider_test_endpoint_no_key(client):
    r = client.post("/api/providers/openai/test")
    assert r.status_code == 200
    assert r.json()["ok"] is False  # no key configured in the tmp env


# ── P2: translation style guidance ───────────────────────
def test_translation_prompt_args_when_set():
    settings = {"translation": {"prompt": "formal, medical register"}}
    assert srv.translation_prompt_args("openai", settings) == \
        ["--translation-prompt", "formal, medical register"]


def test_translation_prompt_args_empty():
    assert srv.translation_prompt_args("openai", {"translation": {"prompt": None}}) == []
    assert srv.translation_prompt_args("openai", {"translation": {"prompt": "  "}}) == []


def test_translation_prompt_args_ignored_for_non_llm():
    settings = {"translation": {"prompt": "x"}}
    assert srv.translation_prompt_args("google", settings) == []


def test_translation_prompt_roundtrip_over_http(client):
    r = client.put("/api/settings", json={"translation": {"prompt": "warm and concise"}})
    assert r.status_code == 200
    assert client.get("/api/settings").json()["translation"]["prompt"] == "warm and concise"


def test_translation_prompt_too_long_rejected(client):
    r = client.put("/api/settings", json={"translation": {"prompt": "x" * 4001}})
    assert r.status_code == 422


# ── P3: speech style ─────────────────────────────────────
def test_compile_speech_style_presets_and_free_text():
    settings = {"speech": {"presets": ["warm", "documentary"], "instructions": "brand voice"}}
    out = srv.compile_speech_style(settings)
    assert "warm and reassuring" in out
    assert "documentary-narrator" in out
    assert out.endswith("brand voice")


def test_compile_speech_style_ignores_unknown_presets():
    assert srv.compile_speech_style({"speech": {"presets": ["nope"]}}) == ""


def test_compile_speech_style_empty():
    assert srv.compile_speech_style({}) == ""
    assert srv.compile_speech_style({"speech": {"presets": [], "instructions": "  "}}) == ""


def test_speech_style_args_only_for_openai_tts():
    settings = {"speech": {"presets": ["warm"], "instructions": ""}}
    assert srv.speech_style_args("openai", settings) == \
        ["--openai-tts-instructions", "warm and reassuring"]
    assert srv.speech_style_args("edge", settings) == []
    assert srv.speech_style_args("piper", settings) == []


def test_speech_style_args_empty_style_passes_nothing():
    # No style → no flag → voxa falls back to the guard-only default.
    assert srv.speech_style_args("openai", {"speech": {"presets": []}}) == []


def test_speech_settings_roundtrip_over_http(client):
    r = client.put("/api/settings",
                   json={"speech": {"presets": ["warm"], "instructions": "friendly"}})
    assert r.status_code == 200
    speech = client.get("/api/settings").json()["speech"]
    assert speech["presets"] == ["warm"]
    assert speech["instructions"] == "friendly"


def test_speech_unknown_preset_rejected(client):
    r = client.put("/api/settings", json={"speech": {"presets": ["bogus"]}})
    assert r.status_code == 422


def test_speech_instructions_too_long_rejected(client):
    r = client.put("/api/settings", json={"speech": {"instructions": "x" * 2001}})
    assert r.status_code == 422


def test_build_options_exposes_speech_presets():
    presets = {p["id"] for p in srv.build_options()["speechPresets"]}
    assert {"warm", "documentary", "energetic"} <= presets


# ── Content-keyed work dir: reuse transcription across dubs (bug fix) ──
def test_same_content_key_same_work_dir():
    a = srv._video_work_dir("abc123def456ghijklmnop")
    b = srv._video_work_dir("abc123def456ghijklmnop")
    assert a == b  # same video → same dir → engine reuses its cached transcription


def test_different_content_key_different_work_dir():
    assert srv._video_work_dir("aaaa1111bbbb2222") != srv._video_work_dir("cccc3333dddd4444")


def test_work_dir_lives_under_jobs_dir():
    assert srv._video_work_dir("deadbeefdeadbeef").parent == srv.JOBS_DIR


def test_unknown_content_key_still_gives_a_dir():
    # After a restart the hash may be missing; a random dir is fine (no crash, no reuse).
    d = srv._video_work_dir(None)
    assert d.parent == srv.JOBS_DIR and len(d.name) == 16


def test_identical_bytes_hash_to_same_key():
    # The property the fix relies on: re-uploading the same video yields the same key.
    import hashlib
    data = b"fake video bytes" * 1000
    k1 = hashlib.sha256(data).hexdigest()
    k2 = hashlib.sha256(data).hexdigest()
    assert srv._video_work_dir(k1) == srv._video_work_dir(k2)
