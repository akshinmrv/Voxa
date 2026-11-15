"""Shared test setup.

Voxa asks PyPI once a day whether a newer version is out (voxa.latest_version). No test may
do that for real or touch the developer's ~/.voxa/update.json: every test gets an empty cache
in its own tmp dir and a PyPI that can't be reached. Tests of the update check give PyPI an
answer themselves.
"""
import sys

import pytest


@pytest.fixture(autouse=True)
def _no_pypi(monkeypatch, tmp_path):
    voxa = sys.modules.get("voxa")
    if voxa is None:
        return

    def unreachable(timeout):
        raise OSError("tests don't reach PyPI")

    monkeypatch.setattr(voxa, "_ask_pypi", unreachable)
    monkeypatch.setattr(voxa, "_update_cache", lambda: tmp_path / ".voxa" / "update.json")
    monkeypatch.delenv("VOXA_NO_UPDATE_CHECK", raising=False)
