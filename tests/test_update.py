"""
The update check: how often Voxa asks PyPI for its newest version, what it keeps, when it says
a newer one is out, and how each kind of install gets it (voxa.latest_version, update_status,
update_hint; GET /api/update; the Updates row of `voxa doctor`).

PyPI is never reached: conftest.py makes it unreachable, and these tests answer for it.

Run:  pytest -q tests/test_update.py
"""
import json
import sys

import pytest

import voxa

DAY = voxa.UPDATE_CHECK_EVERY


@pytest.fixture
def pypi(monkeypatch):
    """PyPI answering `answer.version`; `answer.asked` counts the questions."""
    from types import SimpleNamespace
    answer = SimpleNamespace(version="1.16.0", asked=0, down=False)

    def ask(timeout):
        answer.asked += 1
        if answer.down:
            raise OSError("offline")
        return answer.version

    monkeypatch.setattr(voxa, "_ask_pypi", ask)
    return answer


@pytest.fixture
def plain_install(monkeypatch):
    """Not a container, a VoxaSetup.exe install, a checkout, uv or pipx: plain pip."""
    monkeypatch.setattr(voxa, "_install_kind", lambda: "pip")


@pytest.mark.parametrize("version, number", [
    ("1.16.0", (1, 16, 0)), (" 2.0.10 ", (2, 0, 10)),
    ("1.17.0rc1", None), ("1.16.0.dev3", None), ("0.0.0+unknown", None), ("", None), (None, None),
])
def test_only_plain_releases_have_a_number(version, number):
    assert voxa._release_number(version) == number


# ── how often PyPI is asked ──────────────────────────────
def test_pypi_is_asked_once_a_day(pypi):
    assert voxa.latest_version(now=1000) == "1.16.0"
    pypi.version = "1.17.0"
    assert voxa.latest_version(now=1000 + DAY - 1) == "1.16.0"      # the kept answer
    assert pypi.asked == 1
    assert voxa.latest_version(now=1000 + DAY) == "1.17.0"
    assert pypi.asked == 2
    kept = json.loads(voxa._update_cache().read_text(encoding="utf-8"))
    assert kept == {"checked": 1000 + DAY, "latest": "1.17.0", "failed": False}


def test_offline_keeps_the_last_answer_and_tries_again_in_an_hour(pypi):
    voxa.latest_version(now=1000)
    pypi.down = True
    assert voxa.latest_version(now=1000 + DAY) == "1.16.0"
    assert voxa.latest_version(now=1000 + DAY + voxa.UPDATE_RETRY_AFTER - 1) == "1.16.0"
    assert pypi.asked == 2
    pypi.down, pypi.version = False, "1.17.0"
    assert voxa.latest_version(now=1000 + DAY + voxa.UPDATE_RETRY_AFTER) == "1.17.0"


def test_never_reached_is_unknown(pypi):
    pypi.down = True
    assert voxa.latest_version(now=1000) is None


@pytest.mark.parametrize("kept", ["not json", "[1, 2]", '{"checked": "soon", "latest": 3}'])
def test_a_damaged_cache_is_asked_again(pypi, kept):
    voxa._update_cache().parent.mkdir(parents=True)
    voxa._update_cache().write_text(kept, encoding="utf-8")
    assert voxa.latest_version(now=1000) == "1.16.0"
    assert pypi.asked == 1


def test_a_cache_from_the_future_is_asked_again(pypi):
    # A clock set back must not keep the answer for ever.
    voxa.latest_version(now=1000 + 10 * DAY)
    assert voxa.latest_version(now=1000) == "1.16.0"
    assert pypi.asked == 2


def test_a_cache_that_cant_be_written_still_answers(pypi, monkeypatch, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")
    monkeypatch.setattr(voxa, "_update_cache", lambda: blocker / "update.json")
    assert voxa.latest_version(now=1000) == "1.16.0"


# ── what it says ─────────────────────────────────────────
def test_a_newer_release_says_how_to_get_it(pypi, plain_install, monkeypatch):
    monkeypatch.setattr(voxa, "__version__", "1.15.2")
    pypi.version = "1.16.0"
    status = voxa.update_status()
    assert status["newer"] is True and status["latest"] == "1.16.0"
    assert status["current"] == "1.15.2"
    assert status["kind"] == "pip"
    assert status["command"] == f'"{sys.executable}" -m pip install --upgrade voxa-dub'
    assert status["download"] is None
    assert status["notes"] == "https://github.com/akshinmrv/Voxa/releases/tag/v1.16.0"


@pytest.mark.parametrize("mine, theirs", [
    ("1.16.0", "1.16.0"),           # up to date
    ("1.17.0", "1.16.0"),           # a checkout ahead of PyPI
    ("1.16.0", "1.17.0rc1"),        # a pre-release is never offered
    ("0.0.0+unknown", "1.16.0"),    # a build that doesn't know its version
    ("1.16.0", "1.16"),
])
def test_nothing_is_offered_unless_a_newer_release_is_out(pypi, plain_install, monkeypatch,
                                                          mine, theirs):
    monkeypatch.setattr(voxa, "__version__", mine)
    pypi.version = theirs
    status = voxa.update_status()
    assert status["newer"] is False
    assert status["command"] is None and status["notes"] is None


def test_turned_off_it_doesnt_ask(pypi, monkeypatch):
    assert voxa.update_status(enabled=False)["disabled"] is True
    monkeypatch.setenv("VOXA_NO_UPDATE_CHECK", "1")
    assert voxa.update_check_disabled()
    status = voxa.update_status()
    assert status["disabled"] is True and status["latest"] is None
    assert pypi.asked == 0
    monkeypatch.setenv("VOXA_NO_UPDATE_CHECK", "0")
    assert not voxa.update_check_disabled()


# ── how each install gets it ─────────────────────────────
def _receipt(prefix, extras):
    prefix.mkdir(parents=True, exist_ok=True)
    listed = ", ".join(f'"{e}"' for e in extras)
    (prefix / "uv-receipt.toml").write_text(
        f'[tool]\nrequirements = [{{ name = "voxa-dub", extras = [{listed}] }}]\n',
        encoding="utf-8")


@pytest.fixture
def elsewhere(monkeypatch, tmp_path):
    """voxa.py outside a checkout, not in a container, in a plain environment."""
    monkeypatch.setattr(voxa, "__file__", str(tmp_path / "site-packages" / "voxa.py"))
    monkeypatch.setattr(voxa, "_in_container", lambda: False)
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "venv"))
    return tmp_path


def test_voxa_setup_installs_download_the_new_setup(elsewhere, monkeypatch):
    # VoxaSetup.exe's tool environment has a uv receipt too; its own uv isn't on PATH, so a
    # `uv tool` command would install a second copy. The new Setup upgrades this one.
    prefix = elsewhere / "Programs" / "Voxa" / "tools" / "voxa-dub"
    _receipt(prefix, ["serve", "studio"])
    (elsewhere / "Programs" / "Voxa" / "Uninstall Voxa.exe").write_bytes(b"")
    monkeypatch.setattr(sys, "prefix", str(prefix))
    assert voxa.update_hint() == {
        "kind": "setup", "command": None,
        "download": "https://github.com/akshinmrv/Voxa/releases/latest/download/VoxaSetup.exe"}


def test_uv_tool_installs_keep_their_extras_and_the_cpu_torch(elsewhere, monkeypatch):
    _receipt(elsewhere / "uvtool", ["studio", "serve"])
    monkeypatch.setattr(sys, "prefix", str(elsewhere / "uvtool"))
    assert voxa.update_hint()["command"] == \
        'uv tool install --upgrade --torch-backend auto "voxa-dub[serve,studio]"'


def test_other_installs(elsewhere, monkeypatch):
    assert voxa.update_hint()["command"] == f'"{sys.executable}" -m pip install --upgrade voxa-dub'
    monkeypatch.setattr(sys, "prefix", "/home/u/.local/share/pipx/venvs/voxa-dub")
    assert voxa.update_hint()["command"] == "pipx upgrade voxa-dub"
    checkout = elsewhere / "Voxa"
    (checkout / ".git").mkdir(parents=True)
    monkeypatch.setattr(voxa, "__file__", str(checkout / "voxa.py"))
    assert voxa.update_hint()["command"] == f'git -C "{checkout.resolve()}" pull'
    monkeypatch.setattr(voxa, "_in_container", lambda: True)
    assert voxa.update_hint() == {"kind": "container", "download": None,
                                  "command": "docker pull ghcr.io/akshinmrv/voxa:latest"}


# ── voxa doctor ──────────────────────────────────────────
def _updates_row():
    rows = [c for c in voxa.doctor_checks() if c.section == "Updates"]
    assert len(rows) == 1
    return rows[0]


@pytest.fixture
def quiet_doctor(monkeypatch):
    """Doctor's other probes, made quick: nothing but the Updates row matters here."""
    monkeypatch.setattr(voxa, "_ollama_models", lambda timeout=2.0: None)
    monkeypatch.setattr(voxa, "_in_container", lambda: False)


def test_doctor_says_when_a_newer_voxa_is_out(pypi, plain_install, quiet_doctor, monkeypatch):
    monkeypatch.setattr(voxa, "__version__", "1.15.0")
    row = _updates_row()
    assert (row.status, row.detail) == ("warn", "1.16.0 is out; this is 1.15.0")
    assert row.fix == f'"{sys.executable}" -m pip install --upgrade voxa-dub'


def test_doctor_says_voxa_setup_installs_download_it(pypi, quiet_doctor, monkeypatch):
    monkeypatch.setattr(voxa, "__version__", "1.15.0")
    monkeypatch.setattr(voxa, "_install_kind", lambda: "setup")
    assert _updates_row().fix == f"download and run {voxa.SETUP_EXE_URL}"


def test_doctor_up_to_date_offline_and_off(pypi, quiet_doctor, monkeypatch):
    monkeypatch.setattr(voxa, "__version__", "1.16.0")
    assert (_updates_row().status, _updates_row().detail) == ("ok", "1.16.0, the newest")
    voxa._update_cache().unlink()
    pypi.down = True
    assert _updates_row().status == "off"
    monkeypatch.setenv("VOXA_NO_UPDATE_CHECK", "1")
    assert _updates_row().detail == "not checked (VOXA_NO_UPDATE_CHECK is set)"


# ── the console's /api/update ────────────────────────────
@pytest.fixture
def server(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import voxa_server as srv
    monkeypatch.setattr(srv, "SETTINGS_FILE", tmp_path / "settings.json")
    srv.app.dependency_overrides[srv.require_local] = lambda: None
    try:
        yield srv, TestClient(srv.app)
    finally:
        srv.app.dependency_overrides.pop(srv.require_local, None)


def test_the_console_hears_of_a_newer_voxa(server, pypi, plain_install, monkeypatch):
    srv, client = server
    monkeypatch.setattr(voxa, "__version__", "1.15.0")
    body = client.get("/api/update").json()
    assert body["newer"] is True and body["latest"] == "1.16.0" and body["current"] == "1.15.0"
    assert body["command"].endswith("-m pip install --upgrade voxa-dub")


def test_settings_turn_the_check_off(server, pypi):
    srv, client = server
    assert client.get("/api/settings").json()["advanced"]["checkUpdates"] is True
    r = client.put("/api/settings", json={"advanced": {"checkUpdates": False}})
    assert r.status_code == 200
    body = client.get("/api/update").json()
    assert body["disabled"] is True and body["current"] == voxa.__version__
    assert pypi.asked == 0
    r = client.put("/api/settings", json={"advanced": {"checkUpdates": "no"}})
    assert r.status_code == 422


def test_the_server_says_so_when_it_starts(server, pypi, plain_install, monkeypatch, capsys):
    srv, _ = server
    monkeypatch.setattr(voxa, "__version__", "1.15.0")
    srv._say_if_newer()
    assert "⬆️  Voxa 1.16.0 is out (this is 1.15.0): " in capsys.readouterr().out
    monkeypatch.setattr(voxa, "__version__", "1.16.0")
    srv._say_if_newer()
    assert capsys.readouterr().out == ""
