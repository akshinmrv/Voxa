# Installs VoxaSetup.exe silently, checks what it put where, uninstalls it and checks that it's
# gone. Meant for a GitHub Actions Windows runner: like a real install, it writes the user's
# Start menu, desktop and registry.
param(
    [Parameter(Mandatory)] [string] $Installer,
    [Parameter(Mandatory)] [string] $Version,
    # The wheel Setup was built with: with it, an extra is added and Setup run again, to check
    # that an upgrade keeps it.
    [string] $Wheel
)
$ErrorActionPreference = 'Stop'
$dir = Join-Path $env:RUNNER_TEMP 'VoxaInstall'

$start = Get-Date
$setup = Start-Process -FilePath $Installer -ArgumentList '/S', "/D=$dir" -Wait -PassThru
if ($setup.ExitCode -ne 0) {
    # A silent Setup shows nothing; run its uv step again, as it does, to show why.
    $env:UV_TOOL_DIR = "$dir\tools"; $env:UV_TOOL_BIN_DIR = "$dir\bin"
    $env:UV_PYTHON_INSTALL_DIR = "$dir\python"; $env:UV_PYTHON_PREFERENCE = 'only-managed'
    $env:UV_NO_CACHE = '1'; $env:UV_NO_CONFIG = '1'; $env:UV_TORCH_BACKEND = 'auto'
    $wheel = Get-ChildItem $dir -Filter *.whl -ErrorAction SilentlyContinue | Select-Object -First 1
    $spec = if ($wheel) { "voxa-dub[serve,studio] @ $($wheel.FullName)" } else { "voxa-dub[serve,studio]==$Version" }
    if (Test-Path "$dir\uv.exe") { & "$dir\uv.exe" tool install --upgrade --python 3.12 $spec 2>&1 | Out-Host }
    throw "Setup exited with $($setup.ExitCode)"
}
'installed in {0:N0} s' -f ((Get-Date) - $start).TotalSeconds

foreach ($file in 'bin\voxa.exe', 'bin\voxa-studio.exe', 'uv.exe', 'voxa.ico', 'Uninstall Voxa.exe') {
    if (-not (Test-Path (Join-Path $dir $file))) { throw "Setup left out $file" }
}
$said = (& (Join-Path $dir 'bin\voxa.exe') --version) -join ' '
if ($said -notmatch [regex]::Escape($Version)) { throw "voxa --version says '$said', not $Version" }
& (Join-Path $dir 'tools\voxa-dub\Scripts\python.exe') -c `
    "import torch, webview, voxa_studio, voxa_server; print('torch', torch.__version__, '| pywebview', webview.__name__)"
if ($LASTEXITCODE -ne 0) { throw 'the environment Setup made is incomplete' }
# Engines (Chatterbox, Demucs, VoxCPM2) are installed with Setup's own uv, not on PATH.
$found = (& (Join-Path $dir 'tools\voxa-dub\Scripts\python.exe') -c "import voxa_engines; print(voxa_engines.find_uv())") -join ''
if ($found -ne (Join-Path $dir 'uv.exe')) { throw "engines would install with '$found', not Setup's uv" }
'engines install with ' + $found

$shortcut = Join-Path ([Environment]::GetFolderPath('Programs')) 'Voxa Studio.lnk'
if (-not (Test-Path $shortcut)) { throw 'no Start menu shortcut' }
$link = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcut)
'shortcut: ' + $link.TargetPath + ' in ' + $link.WorkingDirectory + ', icon ' + $link.IconLocation
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Voxa'
$entry = Get-ItemProperty $key
if ($entry.DisplayVersion -ne $Version) { throw "Apps & features says $($entry.DisplayVersion), not $Version" }
'Apps & features: {0} {1} by {2}, {3:N0} MB' -f $entry.DisplayName, $entry.DisplayVersion, $entry.Publisher, ($entry.EstimatedSize / 1024)

if ($Wheel) {
    # An extra added after Setup, as `voxa doctor` says to (Setup's uv, with its settings),
    # stays when Setup runs again to upgrade (extras.nsh). The command is the one Voxa gives,
    # run as it is, but for the release it names: this wheel, which PyPI may not have yet.
    $python = Join-Path $dir 'tools\voxa-dub\Scripts\python.exe'
    $hint = (& $python -c "import voxa; print(voxa._install_hint('url'))") -join ''
    'voxa doctor says: ' + $hint
    if ($hint -notmatch [regex]::Escape("$dir\uv.exe")) { throw "the hint doesn't use Setup's uv" }
    Invoke-Expression ($hint -replace '"voxa-dub\[([^\]]*)\]==[^"]*"', ('"voxa-dub[$1] @ ' + $Wheel + '"'))
    if ($LASTEXITCODE -ne 0) { throw 'adding the url extra failed' }
    $receipt = Get-Content (Join-Path $dir 'tools\voxa-dub\uv-receipt.toml') -Raw
    if ($receipt -notmatch '"url"') { throw "the command didn't add the url extra: $receipt" }
    if (Test-Path (Join-Path $env:USERPROFILE '.local\bin\voxa.exe')) { throw 'it installed a second Voxa' }
    $again = Start-Process -FilePath $Installer -ArgumentList '/S', "/D=$dir" -Wait -PassThru
    if ($again.ExitCode -ne 0) { throw "Setup, run again, exited with $($again.ExitCode)" }
    $receipt = Get-Content (Join-Path $dir 'tools\voxa-dub\uv-receipt.toml') -Raw
    if ($receipt -notmatch '"url"') { throw "the upgrade dropped the url extra: $receipt" }
    & (Join-Path $dir 'tools\voxa-dub\Scripts\python.exe') -c "import yt_dlp, webview; print('kept: yt-dlp', yt_dlp.version.__version__)"
    if ($LASTEXITCODE -ne 0) { throw 'after the upgrade, yt-dlp (the url extra) is gone' }
}

# In place (_?=), so -Wait waits for the uninstaller rather than for a copy of it in TEMP.
$uninstall = Start-Process -FilePath (Join-Path $dir 'Uninstall Voxa.exe') -ArgumentList '/S', "_?=$dir" -Wait -PassThru
if ($uninstall.ExitCode -ne 0) { throw "the uninstaller exited with $($uninstall.ExitCode)" }
foreach ($left in 'tools', 'bin', 'python', 'uv.exe', 'voxa.ico') {
    if (Test-Path (Join-Path $dir $left)) { throw "uninstalling left $left behind" }
}
if (Test-Path $shortcut) { throw 'uninstalling left the Start menu shortcut' }
if (Test-Path $key) { throw 'uninstalling left the Apps & features entry' }
if (-not (Test-Path (Join-Path $env:USERPROFILE 'Voxa'))) { throw "uninstalling removed the user's Voxa folder" }
'uninstalled cleanly; the user''s Voxa folder was kept'
