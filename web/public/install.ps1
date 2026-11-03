# Voxa installer for Windows:
#
#   irm https://voxa.servoogle.com/install.ps1 | iex
#
# Installs uv if it is missing, then Voxa with its browser console into an environment of
# its own (uv downloads a Python for it, so none is needed beforehand), FFmpeg through
# winget, and a "Voxa Studio" shortcut in the Start menu and on the desktop. Running it
# again upgrades Voxa. Uninstall with:  uv tool uninstall voxa-dub
#
# Optional settings, as environment variables:
#   VOXA_EXTRAS=serve,piper   extras to install (default: serve, the browser console)
#   VOXA_VERSION=1.11.0       install this version instead of the latest
#   VOXA_WHEEL=C:\...\x.whl   install from this wheel instead of PyPI
#   VOXA_HOME=C:\...          the folder the console keeps its jobs and .env in (default: ~\Voxa)
#   VOXA_SHORTCUT_DIR=C:\...  put the shortcut here instead of the Start menu and desktop
#   VOXA_NO_SHORTCUT=1        don't create a shortcut
#   VOXA_NO_FFMPEG=1          don't install FFmpeg
#   VOXA_NO_MODIFY_PATH=1     don't add uv's tool folder to PATH

$ErrorActionPreference = "Stop"

function Say($message) { Write-Host "==> $message" -ForegroundColor Cyan }
function Warn($message) { Write-Host "!!  $message" -ForegroundColor Yellow }

$extras = if ($env:VOXA_EXTRAS) { $env:VOXA_EXTRAS } else { "serve" }
$voxaHome = if ($env:VOXA_HOME) { $env:VOXA_HOME } else { Join-Path $HOME "Voxa" }

# --- uv ------------------------------------------------------------------------------
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
    Say "Installing uv (it installs Voxa and the Python it runs on)"
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $uvDir = if ($env:UV_INSTALL_DIR) { $env:UV_INSTALL_DIR } else { Join-Path $HOME ".local\bin" }
    $uv = Join-Path $uvDir "uv.exe"
    if (-not (Test-Path $uv)) { throw "uv was installed, but not found at $uv" }
}
Say "Using $uv"

# --- Voxa ----------------------------------------------------------------------------
if ($env:VOXA_WHEEL) {
    $wheel = (Resolve-Path $env:VOXA_WHEEL).Path
    $spec = "voxa-dub[$extras] @ file:///" + ($wheel -replace "\\", "/")
} elseif ($env:VOXA_VERSION) {
    $spec = "voxa-dub[$extras]==$($env:VOXA_VERSION)"
} else {
    $spec = "voxa-dub[$extras]"
}
Say "Installing $spec (the first time downloads Python and PyTorch, which takes a while)"
& $uv tool install --upgrade --python 3.12 $spec
if ($LASTEXITCODE -ne 0) { throw "uv tool install failed (exit code $LASTEXITCODE)" }

$bin = (& $uv tool dir --bin).Trim()
$voxa = Join-Path $bin "voxa.exe"
if (-not (Test-Path $voxa)) { throw "Voxa was installed, but $voxa is missing" }
if (-not $env:VOXA_NO_MODIFY_PATH) {
    & $uv tool update-shell | Out-Null
}

# --- FFmpeg --------------------------------------------------------------------------
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Say "FFmpeg is already installed"
} elseif ($env:VOXA_NO_FFMPEG) {
    Warn "Skipping FFmpeg (VOXA_NO_FFMPEG). Voxa needs it: winget install Gyan.FFmpeg"
} elseif (Get-Command winget -ErrorAction SilentlyContinue) {
    Say "Installing FFmpeg with winget"
    winget install --id Gyan.FFmpeg --exact --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { Warn "winget couldn't install FFmpeg; install it yourself: winget install Gyan.FFmpeg" }
} else {
    Warn "FFmpeg is missing and winget isn't available. Get FFmpeg from https://www.gyan.dev/ffmpeg/builds/ and put it on PATH."
}

# --- Shortcut ------------------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $voxaHome | Out-Null
if (-not $env:VOXA_NO_SHORTCUT) {
    $folders = @([Environment]::GetFolderPath("Programs"), [Environment]::GetFolderPath("Desktop"))
    if ($env:VOXA_SHORTCUT_DIR) { $folders = @($env:VOXA_SHORTCUT_DIR) }
    $shell = New-Object -ComObject WScript.Shell
    foreach ($folder in $folders) {
        New-Item -ItemType Directory -Force -Path $folder | Out-Null
        $link = $shell.CreateShortcut((Join-Path $folder "Voxa Studio.lnk"))
        $link.TargetPath = $voxa
        $link.Arguments = "studio"
        # The console keeps its jobs, uploads and saved API keys (.env) in this folder.
        $link.WorkingDirectory = $voxaHome
        $link.Description = "Voxa Studio - dub videos in your browser"
        $link.Save()
    }
    Say "Added a 'Voxa Studio' shortcut ($($folders -join ', '))"
}

# --- Check ---------------------------------------------------------------------------
Say "Checking the install"
Push-Location $voxaHome
try { & $voxa doctor } finally { Pop-Location }

Write-Host ""
Say "Voxa is installed."
Write-Host "    Open 'Voxa Studio' from the Start menu, or run:  voxa studio"
Write-Host "    Dub from the terminal:                         voxa video.mp4 --target_lang tr"
Write-Host "    A new terminal may be needed before 'voxa' is on PATH."
Write-Host "    Uninstall:                                     uv tool uninstall voxa-dub"
