# Builds test_parts.nsi and runs it on sample uv receipts: an upgrade keeps the extras an
# install had (Setup's serve and studio first), and with no receipt, or a broken one, it
# installs Setup's own. It also says whether WebView2 is installed, which it is on Windows 11
# and on GitHub's Windows runners: found there, or the check is broken. Needs MAKENSIS
# (get_nsis.ps1 sets it).
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$work = Join-Path ([IO.Path]::GetTempPath()) "voxa-parts-$PID"
New-Item -ItemType Directory -Force $work | Out-Null
$exe = Join-Path $work 'test_parts.exe'
& $env:MAKENSIS -V2 "-DOUTFILE=$exe" (Join-Path $here 'test_parts.nsi')
if ($LASTEXITCODE -ne 0) { throw 'test_parts.nsi did not build' }

$cases = [ordered]@{
    # As uv writes it after Setup, and after `voxa doctor`'s command added url.
    'setup' = @('requirements = [{ name = "voxa-dub", extras = ["serve", "studio"], specifier = "==1.18.0" }]', 'serve,studio')
    'added' = @('requirements = [{ name = "voxa-dub", extras = ["diarize", "serve", "studio", "url"], specifier = "==1.18.0" }]', 'serve,studio,diarize,url')
    'wheel' = @('requirements = [{ name = "voxa-dub", extras = ["serve", "url", "studio"], path = "C:\\Users\\a\\voxa_dub-1.19.0-py3-none-any.whl" }]', 'serve,studio,url')
    'none'  = @('requirements = [{ name = "voxa-dub", specifier = "==1.18.0" }]', 'serve,studio')
    'other' = @('requirements = [{ name = "something-else", extras = ["x"] }]', 'serve,studio')
    'empty' = @($null, 'serve,studio')
}
$failed = 0
foreach ($name in $cases.Keys) {
    $receipt, $want = $cases[$name]
    $dir = Join-Path $work $name
    New-Item -ItemType Directory -Force (Join-Path $dir 'tools\voxa-dub') | Out-Null
    if ($null -ne $receipt) {
        $text = "[tool]`r`n$receipt`r`nentrypoints = [`r`n    { name = `"voxa`", from = `"voxa-dub`" },`r`n]`r`n"
        [IO.File]::WriteAllText((Join-Path $dir 'tools\voxa-dub\uv-receipt.toml'), $text)
    }
    $run = Start-Process -FilePath $exe -ArgumentList '/S', "/D=$dir" -Wait -PassThru
    $got = [IO.File]::ReadAllText((Join-Path $dir 'extras.txt'))
    $ok = $run.ExitCode -eq 0 -and $got -eq $want
    if (-not $ok) { $failed++ }
    '{0} {1}: {2}' -f ($(if ($ok) { 'PASS' } else { 'FAIL' })), $name, $got
}
$webview2 = [IO.File]::ReadAllText((Join-Path (Join-Path $work 'setup') 'webview2.txt'))
if ($webview2 -ne '1') { $failed++ }
'{0} WebView2 found: {1}' -f ($(if ($webview2 -eq '1') { 'PASS' } else { 'FAIL' })), $webview2
Remove-Item -Recurse -Force $work
if ($failed) { throw "$failed case(s) failed" }
