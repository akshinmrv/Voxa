#!/bin/sh
# Voxa installer for macOS and Linux:
#
#   curl -fsSL https://voxa.servoogle.com/install.sh | sh
#
# Installs uv if it is missing, then Voxa with its browser console into an environment of
# its own (uv downloads a Python for it, so none is needed beforehand), FFmpeg through
# Homebrew on macOS, and a "Voxa Studio" launcher. Running it again upgrades Voxa.
# Uninstall with:  uv tool uninstall voxa-dub
#
# Optional settings, as environment variables:
#   VOXA_EXTRAS=serve,piper   extras to install (default: serve, the browser console)
#   VOXA_VERSION=1.11.0       install this version instead of the latest
#   VOXA_WHEEL=/path/x.whl    install from this wheel instead of PyPI
#   VOXA_HOME=/path           the folder the console keeps its jobs and .env in (default: ~/Voxa)
#   VOXA_SHORTCUT_DIR=/path   put the launcher here instead of the usual place
#   VOXA_NO_SHORTCUT=1        don't create a launcher
#   VOXA_NO_FFMPEG=1          don't install FFmpeg
#   VOXA_NO_MODIFY_PATH=1     don't add uv's tool folder to PATH
#   UV_TORCH_BACKEND=cpu      the PyTorch build to install: cpu, cu128, ... (default: auto,
#                             CUDA when uv finds an NVIDIA GPU and its driver, CPU otherwise)
set -eu

say() { printf '\033[36m==> %s\033[0m\n' "$1"; }
warn() { printf '\033[33m!!  %s\033[0m\n' "$1"; }

extras="${VOXA_EXTRAS:-serve}"
voxa_home="${VOXA_HOME:-$HOME/Voxa}"

# --- uv ------------------------------------------------------------------------------
if command -v uv >/dev/null 2>&1; then
    uv="$(command -v uv)"
else
    say "Installing uv (it installs Voxa and the Python it runs on)"
    # Its installer adds its folder to PATH unless told not to; VOXA_NO_MODIFY_PATH tells it.
    curl -LsSf https://astral.sh/uv/install.sh | env ${VOXA_NO_MODIFY_PATH:+UV_NO_MODIFY_PATH=1} sh
    uv="${UV_INSTALL_DIR:-$HOME/.local/bin}/uv"
    [ -x "$uv" ] || { warn "uv was installed, but not found at $uv"; exit 1; }
fi
say "Using $uv"

# --- Voxa ----------------------------------------------------------------------------
if [ -n "${VOXA_WHEEL:-}" ]; then
    wheel="$(cd "$(dirname "$VOXA_WHEEL")" && pwd)/$(basename "$VOXA_WHEEL")"
    spec="voxa-dub[$extras] @ file://$wheel"
elif [ -n "${VOXA_VERSION:-}" ]; then
    spec="voxa-dub[$extras]==$VOXA_VERSION"
else
    spec="voxa-dub[$extras]"
fi
# On Linux, PyTorch from PyPI is a CUDA build that brings 2.5 GB of NVIDIA libraries along,
# which a machine without an NVIDIA GPU never uses; uv picks the build that fits. (A uv too
# old to know this setting ignores it and installs from PyPI, as before.)
export UV_TORCH_BACKEND="${UV_TORCH_BACKEND:-auto}"
say "Installing $spec (the first time downloads Python and PyTorch, which takes a while)"
"$uv" tool install --upgrade --python 3.12 "$spec"

bin="$("$uv" tool dir --bin)"
voxa="$bin/voxa"
[ -x "$voxa" ] || { warn "Voxa was installed, but $voxa is missing"; exit 1; }
if [ -z "${VOXA_NO_MODIFY_PATH:-}" ]; then
    "$uv" tool update-shell >/dev/null 2>&1 || true
fi

# --- FFmpeg --------------------------------------------------------------------------
if command -v ffmpeg >/dev/null 2>&1; then
    say "FFmpeg is already installed"
elif [ -n "${VOXA_NO_FFMPEG:-}" ]; then
    warn "Skipping FFmpeg (VOXA_NO_FFMPEG). Voxa needs it before it can dub."
elif [ "$(uname)" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
    say "Installing FFmpeg with Homebrew"
    brew install ffmpeg || warn "Homebrew couldn't install FFmpeg; run: brew install ffmpeg"
elif command -v apt-get >/dev/null 2>&1; then
    warn "FFmpeg is missing. Install it with:  sudo apt-get install -y ffmpeg"
elif command -v dnf >/dev/null 2>&1; then
    warn "FFmpeg is missing. Install it with:  sudo dnf install -y ffmpeg"
else
    warn "FFmpeg is missing. Install it with your package manager; Voxa needs it before it can dub."
fi

# --- Launcher ------------------------------------------------------------------------
mkdir -p "$voxa_home"
if [ -z "${VOXA_NO_SHORTCUT:-}" ]; then
    if [ "$(uname)" = "Darwin" ]; then
        # A .command file opens in Terminal, which keeps the server running until it's closed.
        dir="${VOXA_SHORTCUT_DIR:-$HOME/Desktop}"
        mkdir -p "$dir"
        launcher="$dir/Voxa Studio.command"
        printf '#!/bin/sh\ncd "%s" && exec "%s" studio\n' "$voxa_home" "$voxa" > "$launcher"
        chmod +x "$launcher"
    else
        dir="${VOXA_SHORTCUT_DIR:-$HOME/.local/share/applications}"
        mkdir -p "$dir"
        launcher="$dir/voxa-studio.desktop"
        cat > "$launcher" <<EOF
[Desktop Entry]
Type=Application
Name=Voxa Studio
Comment=Dub videos in your browser
Exec="$voxa" studio
Path=$voxa_home
Terminal=true
Categories=AudioVideo;
EOF
    fi
    say "Added a 'Voxa Studio' launcher: $launcher"
fi

# --- Check ---------------------------------------------------------------------------
say "Checking the install"
(cd "$voxa_home" && "$voxa" doctor) || true

echo ""
say "Voxa is installed."
echo "    Open 'Voxa Studio', or run:   voxa studio"
echo "    Dub from the terminal:        voxa video.mp4 --target_lang tr"
echo "    A new terminal may be needed before 'voxa' is on PATH."
echo "    Uninstall:                    uv tool uninstall voxa-dub"
