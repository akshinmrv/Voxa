"""
Unit tests for the operator console bundled into the package: how `voxa serve` finds and
serves the static build (voxa_ui), and how `voxa studio` opens it.

A tiny fake build stands in for web/out, so these run without Node or a real build.

Run:  pytest -q tests/test_console.py
"""
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import voxa
import voxa_server as srv
import voxa_ui


def _fake_build(root):
    """The files a static console build has that these tests touch."""
    files = {
        "en/app/index.html": "<html>console en</html>",
        "az/app/index.html": "<html>console az</html>",
        "az/app/jobs/index.html": "<html>jobs az</html>",
        "az/app/jobs/__next.$d$locale/app/jobs.txt": "jobs segment",
        "az/app/jobs/__next.$d$locale/app/jobs/__PAGE__.txt": "jobs page segment",
        "az/app/jobs/__next._tree.txt": "tree",
        "404.html": "<html>not found</html>",
    }
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


@pytest.fixture
def console(tmp_path):
    """A fresh app with one API route, then the console mounted over "/" as the server does."""
    app = FastAPI()

    @app.get("/api/ping")
    async def ping():
        return {"ok": True}

    assert srv.mount_console(app, _fake_build(tmp_path / "static")) is True
    return TestClient(app)


# ── finding the build ────────────────────────────────────
def test_static_dir_is_none_until_the_console_is_built(tmp_path, monkeypatch):
    monkeypatch.setattr(voxa_ui, "STATIC_DIR", tmp_path / "static")
    assert voxa_ui.static_dir() is None
    _fake_build(tmp_path / "static")
    assert voxa_ui.static_dir() == tmp_path / "static"


def test_nothing_is_mounted_without_a_build():
    app = FastAPI()
    assert srv.mount_console(app, None) is False
    assert TestClient(app).get("/").status_code == 404


# ── serving it ───────────────────────────────────────────
def test_root_redirects_to_the_console_in_the_browsers_language(console):
    r = console.get("/", headers={"Accept-Language": "az-AZ,az;q=0.9,en;q=0.8"},
                    follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/az/app/"
    r = console.get("/", headers={"Accept-Language": "de-DE,de;q=0.9"}, follow_redirects=False)
    assert r.headers["location"] == "/en/app/"


def test_root_prefers_the_language_picked_before(console):
    console.cookies.set("NEXT_LOCALE", "tr")
    r = console.get("/", headers={"Accept-Language": "az"}, follow_redirects=False)
    assert r.headers["location"] == "/tr/app/"


def test_console_pages_are_served_and_the_api_still_wins(console):
    assert console.get("/az/app/").text == "<html>console az</html>"
    assert console.get("/az/app/jobs/").text == "<html>jobs az</html>"
    assert console.get("/api/ping").json() == {"ok": True}
    missing = console.get("/az/app/nope/")
    assert missing.status_code == 404 and "not found" in missing.text


def test_dot_joined_prefetch_requests_reach_the_nested_files(console):
    # Next's static build nests these, but the browser asks for them dot-joined.
    assert console.get("/az/app/jobs/__next.$d$locale.app.jobs.txt").text == "jobs segment"
    assert console.get(
        "/az/app/jobs/__next.$d$locale.app.jobs.__PAGE__.txt").text == "jobs page segment"
    assert console.get("/az/app/jobs/__next._tree.txt").text == "tree"
    assert console.get("/az/app/jobs/__next.$d$locale.app.nope.txt").status_code == 404


def test_segment_payload_path_only_rewrites_multi_segment_names():
    nested = srv.segment_payload_path(os.path.join("az", "app", "__next.$d$locale.app.txt"))
    assert nested == os.path.join("az", "app", "__next.$d$locale", "app.txt")
    assert srv.segment_payload_path(os.path.join("az", "app", "__next._tree.txt")) is None
    assert srv.segment_payload_path(os.path.join("az", "app", "index.html")) is None


@pytest.mark.parametrize("cookie, accept, expected", [
    ("", "", "en"),
    ("", "tr-TR,tr;q=0.9", "tr"),
    ("", "fr-FR, az;q=0.5", "az"),
    ("xx", "az", "az"),
    ("en", "az", "en"),
])
def test_console_locale(cookie, accept, expected):
    assert srv.console_locale(cookie, accept) == expected


# ── voxa studio ──────────────────────────────────────────
def test_voxa_studio_is_voxa_serve_that_opens_the_browser(monkeypatch):
    calls = []

    def _run(argv, prog="voxa serve"):
        calls.append((argv, prog))
        return 0

    monkeypatch.setattr(srv, "run_from_cli", _run)
    for argv, expected in ((["voxa", "studio", "--port", "9000"],
                            (["--port", "9000", "--open"], "voxa studio")),
                           (["voxa", "serve"], ([], "voxa serve"))):
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit) as done:
            voxa.cli()
        assert done.value.code == 0
        assert calls.pop() == expected


def test_open_waits_for_a_bundled_console(tmp_path, monkeypatch):
    import uvicorn
    opened = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: None)
    monkeypatch.setattr(srv, "_open_when_ready", opened.append)
    monkeypatch.setattr(srv, "WORKSPACE", tmp_path / ".voxa_serve")
    monkeypatch.setattr(srv, "ENV_FILE", srv.ENV_FILE)          # run_from_cli reassigns it
    env = ["--env-file", str(tmp_path / ".env")]                 # not the developer's own .env

    monkeypatch.setattr(srv, "CONSOLE_BUNDLED", True)
    assert srv.run_from_cli(["--open", "--host", "0.0.0.0", "--port", "9100", *env]) == 0
    assert opened == ["http://127.0.0.1:9100"]
    monkeypatch.setattr(srv, "CONSOLE_BUNDLED", False)
    assert srv.run_from_cli(["--open", *env]) == 0
    assert opened == ["http://127.0.0.1:9100"]              # nothing to open without a build
