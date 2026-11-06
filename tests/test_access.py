"""Whom `voxa serve` answers: this machine by name without a token, the token's holder with one."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

import voxa_server as srv  # noqa: E402

TOKEN = "test-token-not-a-secret"


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(srv, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(srv, "ENV_FILE", str(tmp_path / ".env"))
    return tmp_path


@pytest.fixture
def local(store, monkeypatch):
    """A server on 127.0.0.1, asked for by that name, as the console and `voxa studio` do."""
    monkeypatch.setattr(srv, "ACCESS", srv.Access())
    return TestClient(srv.app, base_url="http://127.0.0.1:8000")


@pytest.fixture
def remote(store, monkeypatch):
    """A server with a token, reached from another machine (as in Docker or on a LAN)."""
    monkeypatch.setattr(srv, "ACCESS", srv.Access(token=TOKEN, cookie="voxa_token_8000"))
    return TestClient(srv.app, base_url="http://203.0.113.7:8000")


# ── without a token ──────────────────────────────────────
@pytest.mark.parametrize("name", ["127.0.0.1:8000", "localhost:8000", "[::1]:8000", "LOCALHOST"])
def test_it_answers_to_this_machine_by_name(local, name):
    assert local.get("/api/options", headers={"Host": name}).status_code == 200


@pytest.mark.parametrize("path", ["/api/keys", "/api/jobs", "/api/options", "/"])
def test_it_turns_away_another_name_as_dns_rebinding_sends(local, path):
    # A page that points its own domain at 127.0.0.1 reaches the server from this machine,
    # so the loopback check alone let it read the keys and change settings.
    r = local.get(path, headers={"Host": "rebind.example:8000"})
    assert r.status_code == 403 and "--token" in r.json()["detail"]


def test_a_rebinding_page_cant_change_settings(local, store):
    r = local.put("/api/settings", json={"advanced": {"maxConcurrentJobs": 2}},
                  headers={"Host": "rebind.example:8000"})
    assert r.status_code == 403 and not (store / "settings.json").exists()


def test_another_site_cant_upload(local, store, monkeypatch):
    monkeypatch.setattr(srv, "UPLOAD_DIR", store / "uploads")
    r = local.post("/api/upload", files={"file": ("v.mp4", b"0" * 64)},
                   headers={"Origin": "https://evil.example"})
    assert r.status_code == 403 and "another site" in r.json()["detail"]
    assert not (store / "uploads").exists()


@pytest.mark.parametrize("origin", ["http://127.0.0.1:8000",      # the bundled console
                                    "http://localhost:3000"])     # the dev console
def test_this_machines_pages_may_write(local, store, monkeypatch, origin):
    monkeypatch.setattr(srv, "UPLOAD_DIR", store / "uploads")
    r = local.post("/api/upload", files={"file": ("v.mp4", b"0" * 64)}, headers={"Origin": origin})
    assert r.status_code == 200 and r.json()["size"] == 64


def test_reads_from_another_site_are_left_to_cors(local):
    # A GET changes nothing, and the browser won't hand another site the answer.
    assert local.get("/api/options", headers={"Origin": "https://evil.example"}).status_code == 200


# ── with a token ─────────────────────────────────────────
def test_the_api_asks_for_the_token(remote):
    r = remote.get("/api/jobs")
    assert r.status_code == 401 and "?token=" in r.json()["detail"]
    assert r.headers["www-authenticate"] == "Bearer"


def test_health_needs_no_token(remote):
    # Readiness checks (voxa studio, Docker, CI) poll it before anyone has the link.
    assert remote.get("/api/health").status_code == 200


def test_a_bearer_header_or_the_cookie_lets_you_in(remote):
    assert remote.get("/api/jobs", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200
    assert remote.get("/api/jobs", headers={"Authorization": "Bearer wrong"}).status_code == 401
    remote.cookies.set("voxa_token_8000", TOKEN)
    assert remote.get("/api/jobs").status_code == 200


def test_another_ports_cookie_doesnt_count(remote):
    # Cookies don't tell ports apart; each server reads only its own.
    remote.cookies.set("voxa_token_9000", TOKEN)
    assert remote.get("/api/jobs").status_code == 401


def test_the_link_leaves_a_cookie_and_drops_the_token_from_the_address(remote):
    r = remote.get(f"/en/app/?token={TOKEN}&tab=jobs", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/en/app/?tab=jobs"
    cookie = r.headers["set-cookie"]
    assert cookie.startswith(f"voxa_token_8000={TOKEN};")
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Secure" not in cookie
    assert remote.get("/api/jobs").status_code == 200        # the client kept the cookie


def test_the_cookie_is_secure_behind_https(remote):
    r = remote.get(f"/?token={TOKEN}", follow_redirects=False,
                   headers={"X-Forwarded-Proto": "https"})
    assert "Secure" in r.headers["set-cookie"]


def test_the_link_cant_send_you_elsewhere(remote):
    # A path of "//evil.example/" would make "Location: //evil.example/" another site.
    r = remote.get(f"http://203.0.113.7:8000//evil.example/?token={TOKEN}",
                   follow_redirects=False)
    assert r.headers["location"] == "/evil.example/"


def test_a_page_without_the_token_asks_for_it(remote):
    r = remote.get("/en/app/", headers={"Accept-Language": "az"})
    assert r.status_code == 401 and 'name="token"' in r.text and "giriş tokeni" in r.text.lower()
    wrong = remote.get("/en/app/?token=wrong")
    assert wrong.status_code == 401 and "isn't this server's token" in wrong.text
    assert "set-cookie" not in wrong.headers


def test_the_holder_may_change_settings_from_anywhere(remote, store):
    # In a container no caller is loopback; the token is what lets the console's Settings
    # and Models pages work there.
    auth = {"Authorization": f"Bearer {TOKEN}"}
    r = remote.put("/api/settings", json={"defaultTts": "edge"}, headers=auth)
    assert r.status_code == 200 and (store / "settings.json").exists()
    assert remote.get("/api/keys", headers=auth).status_code == 200


def test_with_a_token_the_host_can_be_a_proxys(remote):
    # A proxy in front (RunPod, nginx) passes its own name and origin; the token settles it.
    auth = {"Authorization": f"Bearer {TOKEN}", "Host": "pod-8000.proxy.example",
            "Origin": "https://pod-8000.proxy.example"}
    assert remote.put("/api/settings", json={"defaultTts": "edge"}, headers=auth).status_code == 200


def test_the_access_log_hides_the_token():
    import logging
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 0,
                               '%s - "%s %s HTTP/%s" %d',
                               ("127.0.0.1:5000", "GET", f"/en/app/?tab=jobs&token={TOKEN}",
                                "1.1", 303), None)
    assert srv.HideToken().filter(record) is True
    line = record.getMessage()
    assert TOKEN not in line and "/en/app/?tab=jobs&token=[hidden]" in line


# ── which token ──────────────────────────────────────────
def test_beyond_loopback_it_makes_up_a_token():
    token, made_up = srv.server_token("0.0.0.0", None, None)
    assert made_up and len(token) >= 32
    assert srv.server_token("0.0.0.0", None, None)[0] != token


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "127.0.0.2"])
def test_on_loopback_it_asks_for_none(host):
    assert srv.server_token(host, None, None) == (None, False)


def test_a_given_token_wins_and_isnt_made_up():
    assert srv.server_token("0.0.0.0", "mine", "env") == ("mine", False)
    assert srv.server_token("0.0.0.0", None, "env") == ("env", False)
    # Behind a proxy on this machine, --token turns on the token on loopback too.
    assert srv.server_token("127.0.0.1", "mine", None) == ("mine", False)


def test_tests_that_import_the_app_check_nothing():
    assert srv.ACCESS is None
