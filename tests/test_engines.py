"""
Unit tests for voxa_engines: the catalogue, installing an engine into an environment of its
own, and the worker protocol Voxa uses to talk to it.

Installs run against a recording stand-in for uv/pip, and the worker tests use a tiny fake
worker (plus the real Chatterbox worker's protocol handling, which needs no Chatterbox), so
nothing is downloaded.

Run:  pytest -q tests/test_engines.py
"""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import voxa
import voxa_engines as ve


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Engines live in a fresh folder for each test."""
    monkeypatch.setenv("VOXA_ENGINES_DIR", str(tmp_path / "engines"))
    return tmp_path / "engines"


@pytest.fixture
def steps(monkeypatch):
    """Record install steps instead of running them; the venv step leaves a python behind."""
    ran = []

    def _run(cmd, log):
        ran.append(cmd)
        if "venv" in cmd:
            python = ve.env_python("chatterbox")
            python.parent.mkdir(parents=True, exist_ok=True)
            python.write_bytes(b"")
    monkeypatch.setattr(ve, "_run", _run)
    return ran


# ── The catalogue ────────────────────────────────────────
def test_catalogue_entries_are_complete():
    for engine in ve.ENGINES.values():
        assert engine.commercial in set(voxa.PIPER_LICENCE_USE.values())
        assert (ve.WORKERS_DIR / engine.worker).is_file()
        # A worker named like the engine's package would import itself instead of it.
        assert engine.worker.endswith("_worker.py")
        assert all(len(code) == 2 for code in engine.languages)
        assert engine.packages and engine.download_gb > 0


def test_engines_live_where_voxa_engines_dir_says(home):
    assert ve.engine_dir("chatterbox") == home / "chatterbox"
    assert ve.env_python("chatterbox").parent.parent == home / "chatterbox" / "env"
    assert ve.is_installed("chatterbox") is False
    assert ve.catalogue()[0]["installed"] is False


def test_unknown_engines_are_named_in_the_error():
    with pytest.raises(ve.EngineError, match="Available: chatterbox"):
        ve.get("nope")


# ── Installing and removing ──────────────────────────────
def test_install_with_uv(home, steps, monkeypatch):
    monkeypatch.setattr(ve, "find_uv", lambda: "uv")
    ve.install("chatterbox", log=lambda line: None)
    python = str(ve.env_python("chatterbox"))
    assert steps == [
        ["uv", "venv", "--python", "3.11", str(home / "chatterbox" / "env")],
        ["uv", "pip", "install", "--python", python, "--torch-backend", "auto",
         *ve.ENGINES["chatterbox"].packages],
    ]
    assert ve.is_installed("chatterbox")
    assert ve.status("chatterbox")["installedAt"]


def test_a_failed_install_is_not_installed(home, monkeypatch):
    monkeypatch.setattr(ve, "find_uv", lambda: "uv")

    def _run(cmd, log):
        if "venv" in cmd:
            ve.env_python("chatterbox").parent.mkdir(parents=True)
            ve.env_python("chatterbox").write_bytes(b"")
        else:
            raise ve.EngineError("pip failed")
    monkeypatch.setattr(ve, "_run", _run)
    with pytest.raises(ve.EngineError):
        ve.install("chatterbox", log=lambda line: None)
    assert ve.is_installed("chatterbox") is False   # the marker comes last


def test_without_uv_an_older_python_is_told_to_get_uv(home, steps, monkeypatch):
    monkeypatch.setattr(ve, "find_uv", lambda: None)
    engine = ve.ENGINES["chatterbox"]
    monkeypatch.setitem(ve.ENGINES, "chatterbox",
                        ve.Engine(**{**engine.__dict__, "python": "99.0"}))
    with pytest.raises(ve.EngineError, match="uv"):
        ve.install("chatterbox", log=lambda line: None)
    assert steps == []


def test_remove_deletes_the_engines_folder(home, steps, monkeypatch):
    monkeypatch.setattr(ve, "find_uv", lambda: "uv")
    ve.install("chatterbox", log=lambda line: None)
    ve.remove("chatterbox")
    assert not ve.engine_dir("chatterbox").exists()
    ve.remove("chatterbox")                          # removing twice is fine


# ── The worker protocol ──────────────────────────────────
FAKE_WORKER = textwrap.dedent("""\
    import json, sys
    for line in sys.stdin:
        req = json.loads(line)
        if req["cmd"] == "load":
            reply = {"ok": True, "sample_rate": 16000, "device": "cpu"}
        elif req["cmd"] == "speak":
            if not req["text"]:
                reply = {"ok": False, "error": "ValueError: empty text"}
            else:
                open(req["out"], "w").write(req["text"])
                reply = {"ok": True, "seconds": 1.0}
        elif req["cmd"] == "crash":
            print("boom: something went wrong", file=sys.stderr)
            sys.exit(3)
        else:
            print(json.dumps({"ok": True}), flush=True)
            break
        print(json.dumps(reply), flush=True)
    """)


@pytest.fixture
def fake_engine(tmp_path, monkeypatch):
    (tmp_path / "fake_worker.py").write_text(FAKE_WORKER, encoding="utf-8")
    monkeypatch.setattr(ve, "WORKERS_DIR", tmp_path)
    monkeypatch.setitem(ve.ENGINES, "fake", ve.Engine(
        id="fake", label="Fake", kind="tts", description="", licence="MIT",
        commercial="yes", languages=("tr",), cloning=False, python="3.9",
        packages=("fake",), worker="fake_worker.py", download_gb=0.1, homepage=""))
    monkeypatch.setattr(ve, "is_installed", lambda engine_id: True)
    monkeypatch.setattr(ve, "env_python", lambda engine_id: Path(sys.executable))
    return tmp_path


def test_worker_round_trip(fake_engine):
    with ve.Worker("fake", log_path=fake_engine / "worker.log") as worker:
        assert worker.start() == {"ok": True, "sample_rate": 16000, "device": "cpu"}
        out = fake_engine / "line.wav"
        assert worker.request(cmd="speak", text="Salam, dünya", out=str(out))["seconds"] == 1.0
        assert out.read_text() == "Salam, dünya"
        with pytest.raises(ve.EngineError, match="empty text"):
            worker.request(cmd="speak", text="", out=str(out))
        assert worker.request(cmd="speak", text="still here", out=str(out))["ok"]


def test_a_worker_that_dies_says_why(fake_engine):
    worker = ve.Worker("fake", log_path=fake_engine / "worker.log")
    worker.start()
    with pytest.raises(ve.EngineError, match="boom: something went wrong"):
        worker.request(cmd="crash")
    worker.close()


def test_an_engine_that_isnt_installed_has_no_worker(home):
    with pytest.raises(ve.EngineError, match="voxa engines install chatterbox"):
        ve.Worker("chatterbox")


def test_the_chatterbox_workers_protocol_without_chatterbox():
    # Before loading, nothing imports Chatterbox, so the protocol itself can be checked here.
    requests = [{"cmd": "speak", "text": "Merhaba", "language": "tr", "out": "x.wav"},
                {"cmd": "bogus"}, {"cmd": "quit"}]
    proc = subprocess.run(
        [sys.executable, str(ve.WORKERS_DIR / "chatterbox_worker.py")],
        input="".join(json.dumps(r) + "\n" for r in requests),
        capture_output=True, text=True, encoding="utf-8", timeout=60)
    replies = [json.loads(line) for line in proc.stdout.splitlines()]
    assert replies[0] == {"ok": False, "error": "RuntimeError: load the model first"}
    assert replies[1]["ok"] is False and "bogus" in replies[1]["error"]
    assert replies[2] == {"ok": True}
    assert proc.returncode == 0


# ── The console's engine routes ──────────────────────────
@pytest.fixture
def server(home, monkeypatch):
    """voxa_server's app with the local-only guard bypassed and no installs in flight."""
    from fastapi.testclient import TestClient

    import voxa_server as srv
    monkeypatch.setattr(srv, "ENGINE_INSTALLS", {})
    srv.app.dependency_overrides[srv.require_local] = lambda: None
    try:
        yield srv, TestClient(srv.app)
    finally:
        srv.app.dependency_overrides.pop(srv.require_local, None)


def _wait_for(client, engine_id, status):
    import time
    for _ in range(100):
        state = client.get(f"/api/engines/{engine_id}").json()
        if state["install"]["status"] == status:
            return state
        time.sleep(0.05)
    raise AssertionError(f"install never reached {status}: {state['install']}")


def test_engines_are_listed_and_unavailable_until_installed(server):
    srv, client = server
    listed = client.get("/api/engines").json()["engines"]
    assert listed[0]["id"] == "chatterbox" and listed[0]["installed"] is False
    tts = {e["id"]: e for e in client.get("/api/options").json()["ttsEngines"]}
    assert tts["chatterbox"]["available"] is False and tts["edge"]["available"] is True
    job = {"fileId": "x", "config": {"targetLang": "tr", "translator": "google",
                                     "tts": "chatterbox"}}
    refused = client.post("/api/jobs", json=job)
    assert refused.status_code == 400 and "Install it under Models" in refused.json()["detail"]


def test_install_from_the_console_runs_in_the_background(server, monkeypatch):
    srv, client = server

    def _install(engine_id, log):
        log("Resolved 110 packages")
        ve._marker(engine_id).parent.mkdir(parents=True, exist_ok=True)
        ve.env_python(engine_id).parent.mkdir(parents=True, exist_ok=True)
        ve.env_python(engine_id).write_bytes(b"")
        ve._marker(engine_id).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(ve, "install", _install)
    assert client.post("/api/engines/chatterbox/install").status_code == 200
    done = _wait_for(client, "chatterbox", "done")
    assert done["installed"] is True and "Resolved 110 packages" in done["install"]["log"]
    removed = client.delete("/api/engines/chatterbox").json()
    assert removed["installed"] is False and removed["install"]["status"] == "idle"


def test_a_failed_install_reports_why(server, monkeypatch):
    srv, client = server

    def _install(engine_id, log):
        raise ve.EngineError("`uv pip install` failed (exit code 1)")
    monkeypatch.setattr(ve, "install", _install)
    client.post("/api/engines/chatterbox/install")
    failed = _wait_for(client, "chatterbox", "failed")
    assert "exit code 1" in failed["install"]["error"] and failed["installed"] is False


def test_engine_routes_refuse_what_they_cant_do(server, monkeypatch):
    srv, client = server
    assert client.post("/api/engines/nope/install").status_code == 404
    monkeypatch.setitem(srv.ENGINE_INSTALLS, "chatterbox",
                        {"status": "installing", "log": [], "error": None})
    assert client.post("/api/engines/chatterbox/install").status_code == 409
    assert client.delete("/api/engines/chatterbox").status_code == 409
    srv.ENGINE_INSTALLS.clear()
    from types import SimpleNamespace
    monkeypatch.setitem(srv.JOBS, "j1", SimpleNamespace(
        config=SimpleNamespace(tts="chatterbox"), status="running"))
    assert "A dub is using it" in client.delete("/api/engines/chatterbox").json()["detail"]


def test_installing_is_for_localhost_only(home):
    from fastapi.testclient import TestClient

    import voxa_server as srv
    # TestClient's host isn't loopback, so without the override the guard answers.
    assert TestClient(srv.app).post("/api/engines/chatterbox/install").status_code == 403


# ── In the pipeline ──────────────────────────────────────
def test_chatterbox_problems(home):
    problems = voxa._chatterbox_problems("az")
    assert any("doesn't speak 'az'" in p for p in problems)
    assert any("voxa engines install chatterbox" in p for p in problems)
    assert voxa._chatterbox_problems("tr") == [
        "Chatterbox isn't installed — install it once with: voxa engines install chatterbox"]


def test_voxa_engines_command(home, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["voxa", "engines", "list", "--json"])
    with pytest.raises(SystemExit) as done:
        voxa.cli()
    assert done.value.code == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed[0]["id"] == "chatterbox" and listed[0]["installed"] is False
    monkeypatch.setattr(sys, "argv", ["voxa", "engines", "install", "nope"])
    with pytest.raises(SystemExit) as done:
        voxa.cli()
    assert done.value.code == 1 and "No engine called 'nope'" in capsys.readouterr().out
