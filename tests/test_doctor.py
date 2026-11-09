"""
Unit tests for `voxa doctor`: what it reports for a given install, and the fixes it suggests.

Everything it would probe on the real machine (ffmpeg, Ollama, installed packages, disk) is
replaced with a stand-in, so the results don't depend on what this machine has.

Run:  pytest -q tests/test_doctor.py
"""
import json
import sys
from collections import namedtuple
from pathlib import Path

import pytest

import voxa
import voxa_ui

KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "HF_TOKEN",
        "HUGGINGFACE_TOKEN", "OPENAI_TTS_BASE_URL", "OPENAI_TTS_API_KEY")


@pytest.fixture
def machine(monkeypatch, tmp_path):
    """A plain install: ffmpeg on PATH, no GPU, no extras, no keys, Ollama not running.
    Tests change what they need through the returned namespace."""
    from types import SimpleNamespace
    state = SimpleNamespace(tools={"ffmpeg": "/usr/bin/ffmpeg"}, modules=set(), ollama=None,
                            free_gb=50)
    monkeypatch.setattr(voxa.shutil, "which", lambda name: state.tools.get(name))
    monkeypatch.setattr(voxa, "_in_container", lambda: False)
    monkeypatch.setattr(voxa.shutil, "disk_usage",
                        lambda _: namedtuple("Usage", "total used free")(0, 0,
                                                                         state.free_gb * 1024 ** 3))
    monkeypatch.setattr(voxa, "_tool_version", lambda cmd: "7.1")
    monkeypatch.setattr(voxa, "_ollama_models", lambda timeout=2.0: state.ollama)
    monkeypatch.setattr(voxa, "_has_module", lambda name: name in state.modules)
    monkeypatch.setattr(voxa, "_find_piper", lambda: state.tools.get("piper"))
    monkeypatch.setattr(voxa, "_ytdlp_available", lambda: "yt_dlp" in state.modules)
    monkeypatch.setattr(voxa, "torch", None)
    monkeypatch.setattr(voxa, "edge_tts", object())       # CI doesn't install edge-tts
    monkeypatch.setattr(voxa, "_MISSING_DEPS", [])
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    state.env_file = str(tmp_path / ".env")          # never the developer's own .env
    monkeypatch.setenv("VOXA_ENGINES_DIR", str(tmp_path / "engines"))
    return state


def _by_name(checks):
    return {(c.section, c.name): c for c in checks}


def test_a_plain_install_is_ready_with_the_extras_off(machine, capsys):
    checks = _by_name(voxa.doctor_checks())
    assert checks[("Required", "FFmpeg")].status == "ok"
    assert checks[("Speed", "GPU")].status == "warn"
    assert checks[("Speech", "Piper")].status == "off"
    assert checks[("Translation", "Ollama")].status == "off"
    chatterbox = checks[("Speech", "Chatterbox")]
    assert chatterbox.status == "off" and chatterbox.fix.startswith("voxa engines install")
    voxcpm = checks[("Speech", "VoxCPM2")]
    assert voxcpm.status == "off" and "about 6.4 GB" in voxcpm.fix
    demucs = checks[("Extras", "Demucs")]               # not a voice, so not under Speech
    assert demucs.status == "off" and demucs.fix.startswith("voxa engines install demucs")
    assert not any(c.status == "fail" for c in checks.values())
    assert voxa.doctor_cli(["--env-file", machine.env_file]) == 0
    assert "Ready to dub" in capsys.readouterr().out


def test_missing_ffmpeg_fails_and_says_how_to_install_it(machine, capsys):
    machine.tools.pop("ffmpeg")
    ffmpeg = _by_name(voxa.doctor_checks())[("Required", "FFmpeg")]
    assert ffmpeg.status == "fail" and ffmpeg.fix == voxa._ffmpeg_hint()
    assert voxa.doctor_cli(["--env-file", machine.env_file]) == 1
    assert "can't dub" in capsys.readouterr().out


def test_keys_are_reported_but_never_shown(machine, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-123")
    assert voxa.doctor_cli(["--json", "--env-file", machine.env_file]) == 0
    out = capsys.readouterr().out
    checks = {(c["section"], c["name"]): c for c in json.loads(out)}
    assert checks[("Translation", "OpenAI")]["status"] == "ok"
    assert checks[("Speech", "OpenAI")]["detail"] == "OPENAI_API_KEY is set"
    assert "sk-test-secret-123" not in out


def test_a_self_hosted_speech_server_is_reported_with_the_key_it_gets(machine, monkeypatch,
                                                                     capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-123")
    monkeypatch.setenv("OPENAI_TTS_BASE_URL", "http://127.0.0.1:3900/v1")
    for server_key, detail in ((None, "no key is sent to it"),
                               ("srv-secret-456", "OPENAI_TTS_API_KEY is sent to it")):
        if server_key:
            monkeypatch.setenv("OPENAI_TTS_API_KEY", server_key)
        voxa.doctor_cli(["--json", "--env-file", machine.env_file])
        out = capsys.readouterr().out
        speech = {c["name"]: c for c in json.loads(out) if c["section"] == "Speech"}
        assert speech["OpenAI"]["detail"] == \
            f"self-hosted server: http://127.0.0.1:3900/v1; {detail}"
        assert "secret" not in out


def test_install_hints_match_how_voxa_was_installed(monkeypatch):
    import importlib.metadata
    monkeypatch.setattr(voxa, "_in_container", lambda: False)
    monkeypatch.setattr(importlib.metadata, "requires", lambda dist: [
        'piper-tts; extra == "piper"', 'fastapi; extra == "serve"',
        'uvicorn[standard]; extra == "serve"'])
    monkeypatch.setattr(sys, "prefix", "/home/u/.local/share/pipx/venvs/voxa-dub")
    assert voxa._install_hint("piper") == "pipx inject voxa-dub piper-tts"
    assert voxa._install_hint("serve") == 'pipx inject voxa-dub fastapi "uvicorn[standard]"'
    assert voxa._reinstall_hint() == "pipx reinstall voxa-dub"
    # Anywhere else, the pip of the Python running Voxa, so it lands in the right environment.
    monkeypatch.setattr(sys, "prefix", "/opt/venv")
    assert voxa._install_hint("piper") == f'"{sys.executable}" -m pip install "voxa-dub[piper]"'


def test_a_uv_tool_install_keeps_its_extras(monkeypatch, tmp_path):
    # The one-line installers use `uv tool install`, whose environment has no pip. uv replaces
    # that environment on a change, so the hint names the extras it already has as well.
    (tmp_path / "uv-receipt.toml").write_text(
        '[tool]\nrequirements = [{ name = "voxa-dub", extras = ["serve"], path = "x.whl" }]\n'
        'python = "3.12"\n', encoding="utf-8")
    monkeypatch.setattr(sys, "prefix", str(tmp_path))
    assert voxa._install_hint("piper") == 'uv tool install --upgrade "voxa-dub[piper,serve]"'
    assert voxa._install_hint("serve") == 'uv tool install --upgrade "voxa-dub[serve]"'
    assert voxa._reinstall_hint() == 'uv tool install --reinstall "voxa-dub[serve]"'


def test_find_piper_next_to_python_when_it_isnt_on_path(monkeypatch, tmp_path):
    # pipx doesn't put a dependency's scripts on PATH, and on Windows the file is piper.exe.
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    (scripts / "piper.exe").write_bytes(b"")
    monkeypatch.setattr(voxa.shutil, "which", lambda name: None)
    monkeypatch.setattr(sys, "executable", str(scripts / "python.exe"))
    monkeypatch.setattr(voxa.sysconfig, "get_path", lambda name: str(scripts))
    assert voxa._find_piper() == str(scripts / "piper.exe")


def test_the_environments_own_piper_wins_over_one_on_path(monkeypatch, tmp_path):
    # The one on PATH may be another install's, older, or GNOME's mouse app (/usr/bin/piper).
    env_bin = tmp_path / "env" / "bin"
    env_bin.mkdir(parents=True)
    (env_bin / "piper").write_bytes(b"")
    monkeypatch.setattr(voxa.shutil, "which", lambda name: "/usr/bin/piper")
    monkeypatch.setattr(sys, "executable", str(env_bin / "python"))
    monkeypatch.setattr(voxa.sysconfig, "get_path", lambda name: str(env_bin))
    assert voxa._find_piper() == str(env_bin / "piper")


def test_a_global_windows_python_keeps_piper_in_scripts(monkeypatch, tmp_path):
    # python.exe sits in the install folder, the scripts pip writes in its Scripts folder.
    scripts = tmp_path / "Python312" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "piper.exe").write_bytes(b"")
    monkeypatch.setattr(voxa.shutil, "which", lambda name: None)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Python312" / "python.exe"))
    monkeypatch.setattr(voxa.sysconfig, "get_path", lambda name: str(scripts))
    assert voxa._find_piper() == str(scripts / "piper.exe")


def test_without_its_own_piper_it_takes_the_one_on_path(monkeypatch, tmp_path):
    monkeypatch.setattr(voxa.shutil, "which", lambda name: "/opt/piper/piper")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))
    monkeypatch.setattr(voxa.sysconfig, "get_path", lambda name: str(tmp_path / "Scripts"))
    assert voxa._find_piper() == "/opt/piper/piper"


@pytest.mark.parametrize("models, status", [(None, "off"), ([], "warn"),
                                            (["llama3:latest"], "ok")])
def test_ollama(machine, models, status):
    machine.ollama = models
    assert _by_name(voxa.doctor_checks())[("Translation", "Ollama")].status == status


def test_deep_imports_xtts_and_reports_a_broken_install(machine, monkeypatch):
    machine.modules.add("TTS")
    imported = []

    def _broken(module):
        imported.append(module)
        return "ImportError"

    monkeypatch.setattr(voxa, "_imports_cleanly", _broken)
    assert _by_name(voxa.doctor_checks())[("Speech", "XTTS")].status == "ok"
    assert imported == []                                   # the quick check only finds it
    xtts = _by_name(voxa.doctor_checks(deep=True))[("Speech", "XTTS")]
    assert xtts.status == "warn" and "transformers" in xtts.fix
    assert imported == ["TTS.api"]


def test_in_a_container_the_fixes_are_for_the_image(machine, monkeypatch):
    # A pip install in a running container is gone with it, and the console's Settings can't
    # be changed from inside one; the fixes say what works there.
    monkeypatch.setattr(voxa, "_in_container", lambda: True)
    checks = _by_name(voxa.doctor_checks())
    assert checks[("Speed", "faster-whisper")].fix == \
        'add it to the image:  RUN pip install "voxa-dub[faster]"'
    assert checks[("Translation", "OpenAI")].fix == \
        "pass it to the container:  docker run -e OPENAI_API_KEY=..."


def test_console_needs_the_server_and_a_build(machine, monkeypatch, tmp_path):
    assert _by_name(voxa.doctor_checks())[("Extras", "Console")].status == "off"
    machine.modules.update({"fastapi", "uvicorn"})
    monkeypatch.setattr(voxa_ui, "static_dir", lambda: None)
    assert _by_name(voxa.doctor_checks())[("Extras", "Console")].status == "warn"
    monkeypatch.setattr(voxa_ui, "static_dir", lambda: tmp_path)
    console = _by_name(voxa.doctor_checks())[("Extras", "Console")]
    assert console.status == "ok" and "voxa studio" in console.detail


def test_low_disk_space_is_a_warning(machine):
    machine.free_gb = 3
    assert _by_name(voxa.doctor_checks())[("Disk", "Free space")].status == "warn"


def test_voxa_doctor_command(machine, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["voxa", "doctor", "--json", "--env-file",
                                      machine.env_file])
    with pytest.raises(SystemExit) as done:
        voxa.cli()
    assert done.value.code == 0
    assert any(c["name"] == "FFmpeg" for c in json.loads(capsys.readouterr().out))
    assert Path(machine.env_file).exists() is False         # it only reads the .env
