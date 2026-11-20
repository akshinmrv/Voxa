"""The console's System page and its Hugging Face token (S6: BE-4, BE-5): what `voxa doctor`
says, through the API; the token pyannote needs, kept like the other keys and tested against
Hugging Face; where each key comes from; and engines installed with VoxaSetup's own uv."""
import asyncio
import io
import json
import sys
import time
import urllib.error

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import voxa  # noqa: E402
import voxa_engines  # noqa: E402
import voxa_server as srv  # noqa: E402

TOKEN = "hf_" + "x" * 30 + "abcd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(srv, "ENV_FILE", str(tmp_path / ".env"))
    for name in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    srv.app.dependency_overrides[srv.require_local] = lambda: None
    try:
        yield TestClient(srv.app)
    finally:
        srv.app.dependency_overrides.pop(srv.require_local, None)


# ── BE-4: /api/doctor ──

def test_doctor_says_what_voxa_doctor_does(client, monkeypatch):
    asked = []

    def checks(online=False, deep=False):
        asked.append((online, deep))
        return [voxa.DoctorCheck("Required", "FFmpeg", "ok", "8.0"),
                voxa.DoctorCheck("Extras", "URL input", "off", "dub from a link", "pip …")]

    monkeypatch.setattr(voxa, "doctor_checks", checks)
    body = client.get("/api/doctor").json()
    assert body["sections"] == list(voxa.DOCTOR_SECTIONS)
    assert body["checks"][1] == {"section": "Extras", "name": "URL input", "status": "off",
                                 "detail": "dub from a link", "fix": "pip …"}
    assert body["ready"] is True and body["version"] == srv.app.version
    assert body["install"] in ("container", "setup", "source", "uv", "pipx", "pip")
    client.get("/api/doctor?online=true")
    # Never --deep: it loads models.
    assert asked == [(False, False), (True, False)]


def test_a_failing_check_means_not_ready(client, monkeypatch):
    monkeypatch.setattr(voxa, "doctor_checks", lambda online=False, deep=False: [
        voxa.DoctorCheck("Required", "FFmpeg", "fail", "not found", "winget install …")])
    assert client.get("/api/doctor").json()["ready"] is False


def _concurrently(path, slow_name, monkeypatch, *slow_args):
    """Ask for path while a slow call behind it runs; how long /api/health took meanwhile."""
    import httpx

    def slow(*args, **kwargs):
        time.sleep(1.0)
        return slow_args[0] if slow_args else []

    monkeypatch.setattr(*slow_name, slow)

    async def both():
        transport = httpx.ASGITransport(app=srv.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as c:
            started = time.perf_counter()
            took = {}

            async def get(method, url):
                r = await c.request(method, url)
                took[url] = time.perf_counter() - started
                return r.status_code

            codes = await asyncio.gather(get(*path), get("GET", "/api/health"))
            return codes, took

    return asyncio.run(both())


def test_the_checks_hold_up_nothing_else(client, monkeypatch):
    """They run ffmpeg and ask Ollama and PyPI: in a thread of their own."""
    codes, took = _concurrently(("GET", "/api/doctor"), (voxa, "doctor_checks"), monkeypatch)
    assert codes == [200, 200]
    assert took["/api/health"] < 0.5 <= took["/api/doctor"], took


def test_a_key_test_holds_up_nothing_else(client, monkeypatch):
    """A provider test waits on the provider's answer: in a thread of its own."""
    codes, took = _concurrently(("POST", "/api/providers/openai/test"),
                                (srv, "test_provider"), monkeypatch, {"ok": True})
    assert codes == [200, 200]
    assert took["/api/health"] < 0.5 <= took["/api/providers/openai/test"], took


# ── BE-5: the Hugging Face token ──

def test_the_token_is_kept_like_a_key_and_never_shown(client):
    assert client.get("/api/keys").json()["hf"]["hasKey"] is False
    body = client.put("/api/keys/hf", json={"value": f"  {TOKEN} "}).json()
    hf = body["hf"]
    assert hf == {"envKey": "HF_TOKEN", "hasKey": True, "masked": "••••abcd", "source": "file",
                  "models": ["https://huggingface.co/pyannote/speaker-diarization-3.1",
                             "https://huggingface.co/pyannote/segmentation-3.0"]}
    assert TOKEN not in json.dumps(body)
    assert f"HF_TOKEN={TOKEN}" in open(srv.ENV_FILE, encoding="utf-8").read()
    assert srv.os.environ["HF_TOKEN"] == TOKEN          # the next dub has it
    # Diarization in `voxa doctor`, and the System page, sees it at once.
    body = client.delete("/api/keys/hf").json()
    assert body["hf"]["hasKey"] is False and "HF_TOKEN" not in srv.os.environ
    assert "HF_TOKEN" not in open(srv.ENV_FILE, encoding="utf-8").read()


def test_where_a_key_comes_from(client, monkeypatch):
    # Set where Voxa was started: removing it in Settings lasts only until the next start.
    monkeypatch.setenv("HUGGINGFACE_TOKEN", TOKEN)
    hf = client.get("/api/keys").json()["hf"]
    assert (hf["envKey"], hf["source"]) == ("HUGGINGFACE_TOKEN", "environment")
    assert client.delete("/api/keys/hf").json()["hf"]["hasKey"] is False
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-the-shell-1234")
    openai = next(k for k in client.get("/api/keys").json()["keys"] if k["provider"] == "openai")
    assert openai["source"] == "environment"
    client.put("/api/keys/openai", json={"value": "sk-from-settings-5678"})
    openai = next(k for k in client.get("/api/keys").json()["keys"] if k["provider"] == "openai")
    assert (openai["source"], openai["masked"]) == ("file", "••••5678")
    assert client.put("/api/keys/nope", json={"value": "x"}).status_code == 404


class _Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _hugging_face(monkeypatch, whoami=200, models=(200, 200)):
    """Hugging Face's answers, by URL; what was asked, and with which token."""
    asked = []

    def urlopen(req, timeout=None):
        url = req.full_url
        asked.append((req.get_method(), url, req.get_header("Authorization")))
        if url.endswith("/api/whoami-v2"):
            if whoami != 200:
                raise urllib.error.HTTPError(url, whoami, "no", {}, None)
            return _Answer(json.dumps({"name": "akshin-test"}).encode())
        code = models[0] if "speaker-diarization" in url else models[1]
        if code != 200:
            raise urllib.error.HTTPError(url, code, "gated", {}, None)
        return _Answer(b"")

    monkeypatch.setattr(srv.urllib.request, "urlopen", urlopen)
    return asked


def test_the_token_test_asks_for_both_models(client, monkeypatch):
    client.put("/api/keys/hf", json={"value": TOKEN})
    asked = _hugging_face(monkeypatch, models=(200, 403))
    body = client.post("/api/providers/hf/test").json()
    assert body["ok"] is False and body["user"] == "akshin-test"
    assert [(m["id"], m["access"]) for m in body["models"]] == [
        ("pyannote/speaker-diarization-3.1", True), ("pyannote/segmentation-3.0", False)]
    # Only to huggingface.co, with the token as a bearer; never back to the page.
    assert all(url.startswith("https://huggingface.co/") for _, url, _ in asked)
    assert {auth for _, _, auth in asked} == {f"Bearer {TOKEN}"}
    assert [method for method, _, _ in asked] == ["GET", "HEAD", "HEAD"]
    assert TOKEN not in json.dumps(body)
    _hugging_face(monkeypatch)
    assert client.post("/api/providers/hf/test").json()["ok"] is True


def test_a_token_hugging_face_refuses_says_so(client, monkeypatch):
    client.put("/api/keys/hf", json={"value": TOKEN})
    _hugging_face(monkeypatch, whoami=401)
    assert client.post("/api/providers/hf/test").json() == {
        "ok": False, "error": "Hugging Face doesn't accept this token."}
    client.delete("/api/keys/hf")
    assert client.post("/api/providers/hf/test").json() == {"ok": False, "error": "No token set."}


# ── Engines with VoxaSetup's own uv ──

def test_engines_use_voxa_setups_own_uv(monkeypatch, tmp_path):
    """Setup's uv isn't on PATH; without it an engine was installed with venv and pip, in
    Setup's Python rather than the one the engine asks for."""
    root = tmp_path / "Voxa"
    prefix = root / "tools" / "voxa-dub"
    prefix.mkdir(parents=True)
    (root / "Uninstall Voxa.exe").write_bytes(b"")
    (root / "uv.exe").write_bytes(b"")
    monkeypatch.setattr(sys, "prefix", str(prefix))
    monkeypatch.setattr(voxa_engines.shutil, "which", lambda name: r"C:\elsewhere\uv.exe")
    assert voxa_engines.find_uv() == str(root / "uv.exe")
    (root / "Uninstall Voxa.exe").unlink()
    assert voxa_engines.find_uv() == r"C:\elsewhere\uv.exe"


def test_windows_11_is_called_so(monkeypatch):
    import platform
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(platform, "release", lambda: "10")
    monkeypatch.setattr(platform, "version", lambda: "10.0.26200")
    assert srv.os_name() == "Windows 11"
    monkeypatch.setattr(platform, "version", lambda: "10.0.19045")
    assert srv.os_name() == "Windows 10"
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "release", lambda: "6.8.0")
    assert srv.os_name() == "Linux 6.8.0"
