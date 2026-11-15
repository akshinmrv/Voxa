# NSIS for building VoxaSetup.exe on a GitHub Actions Windows runner: the official 3.13 zip,
# checked against its SHA-256, unpacked into the runner's temp folder. Sets MAKENSIS for the
# steps that follow.
$ErrorActionPreference = 'Stop'
$version = '3.13'
$sha256 = 'BA63DFFC4410EE89193E1CB5A41989991BD77C61068DA17E3156D136B7B0B3D8'
$zip = Join-Path $env:RUNNER_TEMP "nsis-$version.zip"
Invoke-WebRequest "https://downloads.sourceforge.net/project/nsis/NSIS%203/$version/nsis-$version.zip" `
    -OutFile $zip -UserAgent 'voxa-ci'
$got = (Get-FileHash $zip -Algorithm SHA256).Hash
if ($got -ne $sha256) { throw "nsis-$version.zip: SHA-256 is $got, not $sha256" }
Expand-Archive $zip -DestinationPath $env:RUNNER_TEMP -Force
"MAKENSIS=$(Join-Path $env:RUNNER_TEMP "nsis-$version\makensis.exe")" >> $env:GITHUB_ENV
