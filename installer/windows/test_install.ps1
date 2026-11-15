# Installs VoxaSetup.exe silently, checks what it put where, uninstalls it and checks that it's
# gone. Meant for a GitHub Actions Windows runner: like a real install, it writes the user's
# Start menu, desktop and registry.
param(
    [Parameter(Mandatory)] [string] $Installer,
    [Parameter(Mandatory)] [string] $Version
)
$ErrorActionPreference = 'Stop'
$dir = Join-Path $env:RUNNER_TEMP 'VoxaInstall'

$start = Get-Date
$setup = Start-Process -FilePath $Installer -ArgumentList '/S', "/D=$dir" -Wait -PassThru
if ($setup.ExitCode -ne 0) { throw "Setup exited with $($setup.ExitCode)" }
'installed in {0:N0} s' -f ((Get-Date) - $start).TotalSeconds

foreach ($file in 'bin\voxa.exe', 'bin\voxa-studio.exe', 'uv.exe', 'voxa.ico', 'Uninstall Voxa.exe') {
    if (-not (Test-Path (Join-Path $dir $file))) { throw "Setup left out $file" }
}
$said = (& (Join-Path $dir 'bin\voxa.exe') --version) -join ' '
if ($said -notmatch [regex]::Escape($Version)) { throw "voxa --version says '$said', not $Version" }
& (Join-Path $dir 'tools\voxa-dub\Scripts\python.exe') -c `
    "import torch, webview, voxa_studio, voxa_server; print('torch', torch.__version__, '| pywebview', webview.__name__)"
if ($LASTEXITCODE -ne 0) { throw 'the environment Setup made is incomplete' }

$shortcut = Join-Path ([Environment]::GetFolderPath('Programs')) 'Voxa Studio.lnk'
if (-not (Test-Path $shortcut)) { throw 'no Start menu shortcut' }
$link = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcut)
'shortcut: ' + $link.TargetPath + ' in ' + $link.WorkingDirectory + ', icon ' + $link.IconLocation
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Voxa'
$entry = Get-ItemProperty $key
if ($entry.DisplayVersion -ne $Version) { throw "Apps & features says $($entry.DisplayVersion), not $Version" }
'Apps & features: {0} {1} by {2}, {3:N0} MB' -f $entry.DisplayName, $entry.DisplayVersion, $entry.Publisher, ($entry.EstimatedSize / 1024)

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
