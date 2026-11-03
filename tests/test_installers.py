"""
Tests for the one-line macOS/Linux installer, web/public/install.sh.

It runs against a stand-in uv (and, for the macOS case, a stand-in uname), so what it would
install, where the launcher goes and what it runs are checked without downloading anything.
install.ps1 needs Windows' COM for its shortcut, which CI runners don't have; it was run end
to end on Windows instead.

Run:  pytest -q tests/test_installers.py
"""
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "web" / "public" / "install.sh"

pytestmark = pytest.mark.skipif(sys.platform == "win32" or shutil.which("sh") is None,
                                reason="install.sh is for macOS and Linux")


def _stub(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + textwrap.dedent(body), encoding="utf-8", newline="\n")
    path.chmod(0o755)


@pytest.fixture
def run(tmp_path):
    """Run install.sh with stand-ins on PATH; returns (result, calls) for a set of settings."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    log = tmp_path / "calls.log"
    tool_bin = tmp_path / "tool-bin"
    # uv: records its arguments; `tool install` leaves a voxa that records its own.
    _stub(stubs / "uv", f"""\
        echo "uv $*" >> "{log}"
        case "$1 $2" in
          "tool install")
            mkdir -p "{tool_bin}"
            printf '#!/bin/sh\\necho "voxa $* in $PWD" >> "{log}"\\n' > "{tool_bin}/voxa"
            chmod +x "{tool_bin}/voxa" ;;
          "tool dir") echo "{tool_bin}" ;;
        esac
        """)
    _stub(stubs / "ffmpeg", "exit 0\n")

    def _run(**settings):
        env = {**os.environ, "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}",
               "HOME": str(tmp_path / "home"),
               "VOXA_SHORTCUT_DIR": str(tmp_path / "launchers"), **settings}
        result = subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True,
                                timeout=60)
        calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        return result, calls

    _run.stubs, _run.tmp, _run.tool_bin = stubs, tmp_path, tool_bin
    return _run


def test_installs_the_console_and_adds_a_launcher(run):
    result, calls = run()
    assert result.returncode == 0, result.stderr
    assert "uv tool install --upgrade --python 3.12 voxa-dub[serve]" in calls
    assert "uv tool update-shell" in calls
    home = run.tmp / "home" / "Voxa"
    assert f"voxa doctor in {home}" in calls                 # checked from the console's folder
    launcher = (run.tmp / "launchers" / "voxa-studio.desktop").read_text(encoding="utf-8")
    assert f'Exec="{run.tool_bin}/voxa" studio' in launcher
    assert f"Path={home}" in launcher and "Terminal=true" in launcher


def test_version_extras_and_path_settings(run):
    result, calls = run(VOXA_VERSION="1.11.0", VOXA_EXTRAS="serve,piper",
                        VOXA_NO_MODIFY_PATH="1", VOXA_NO_SHORTCUT="1")
    assert result.returncode == 0, result.stderr
    assert "uv tool install --upgrade --python 3.12 voxa-dub[serve,piper]==1.11.0" in calls
    assert "uv tool update-shell" not in calls
    assert not (run.tmp / "launchers").exists()


def test_installs_from_a_wheel(run):
    wheel = run.tmp / "dist" / "voxa_dub-9.9.9-py3-none-any.whl"
    wheel.parent.mkdir()
    wheel.write_bytes(b"")
    result, calls = run(VOXA_WHEEL=str(wheel))
    assert result.returncode == 0, result.stderr
    assert f"uv tool install --upgrade --python 3.12 voxa-dub[serve] @ file://{wheel}" in calls


def test_macos_gets_a_command_file_that_starts_the_studio(run):
    _stub(run.stubs / "uname", 'echo "Darwin"\n')
    result, calls = run()
    assert result.returncode == 0, result.stderr
    launcher = run.tmp / "launchers" / "Voxa Studio.command"
    assert os.access(launcher, os.X_OK)
    body = launcher.read_text(encoding="utf-8")
    assert f'cd "{run.tmp / "home" / "Voxa"}"' in body
    assert f'exec "{run.tool_bin}/voxa" studio' in body
