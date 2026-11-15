"""Build VoxaSetup.exe from installer/windows/voxa.nsi.

Fetches uv for Windows (the release pinned below, checked against its SHA-256) and runs NSIS's
makensis, which runs on Linux and macOS as well as Windows. Usage:

  python scripts/build_windows_installer.py 1.16.0                  # installs 1.16.0 from PyPI
  python scripts/build_windows_installer.py 1.16.0 --wheel dist/voxa_dub-1.16.0-py3-none-any.whl

The second bundles a wheel, so an unreleased build can be installed and tested. makensis comes
from --makensis, MAKENSIS, or PATH.
"""
import argparse
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "installer" / "windows" / "voxa.nsi"
UV_VERSION = "0.13.8"
UV_ZIP = "uv-x86_64-pc-windows-msvc.zip"
UV_SHA256 = "529e78a9cec6cd7e3e014f7ecd8bda0c113969d4ed0f2efeedb85c30943325b8"


def fetch_uv(cache: Path) -> Path:
    """uv.exe for Windows, downloaded once and kept in `cache`."""
    target = cache / f"uv-{UV_VERSION}.exe"
    if target.is_file():
        return target
    url = f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}/{UV_ZIP}"
    request = urllib.request.Request(url, headers={"User-Agent": "voxa-installer-build"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != UV_SHA256:
        sys.exit(f"{UV_ZIP} {UV_VERSION}: SHA-256 is {digest}, not {UV_SHA256}")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        name = next(n for n in archive.namelist() if n.endswith("uv.exe"))
        cache.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(name))
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="the Voxa release it installs, x.y.z")
    parser.add_argument("--wheel", help="bundle this wheel instead of installing from PyPI")
    parser.add_argument("--out", default=str(ROOT / "dist"), help="folder for the installer")
    parser.add_argument("--makensis",
                        default=os.environ.get("MAKENSIS") or shutil.which("makensis"))
    args = parser.parse_args()

    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        sys.exit(f"version must be x.y.z, not {args.version!r}")
    if not args.makensis:
        sys.exit("makensis not found: install NSIS, or pass --makensis")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    installer = out / f"VoxaSetup-{args.version}.exe"
    defines = [f"-DVERSION={args.version}", f"-DUV={fetch_uv(out / '.uv')}",
               f"-DOUTFILE={installer}"]
    if args.wheel:
        defines.append(f"-DWHEEL={Path(args.wheel).resolve()}")
    subprocess.run([args.makensis, "-V2", "-INPUTCHARSET", "UTF8", *defines, str(SCRIPT)],
                   check=True)
    print(f"{installer} ({installer.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
