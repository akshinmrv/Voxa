; Checks the parts VoxaSetup.exe includes: extras.nsh, the extras an upgrade keeps, and
; webview2.nsh, whether WebView2 is there. Built and run by test_parts.ps1: run silently with
; /D=<a folder holding tools\voxa-dub\uv-receipt.toml>, it writes what KeptExtras found to
; <folder>\extras.txt and what HasWebView2 found to <folder>\webview2.txt. It touches nothing
; else: no registry, no shortcuts.

Unicode true
!ifndef OUTFILE
  !error "pass -DOUTFILE=..."
!endif
OutFile "${OUTFILE}"
RequestExecutionLevel user
SilentInstall silent
InstallDir "$TEMP\voxa-parts-test"

!include "extras.nsh"
!include "webview2.nsh"

Section
  Call KeptExtras
  FileOpen $9 "$INSTDIR\extras.txt" w
  FileWrite $9 $Extras
  FileClose $9
  Call HasWebView2
  FileOpen $9 "$INSTDIR\webview2.txt" w
  FileWrite $9 $WebView2
  FileClose $9
SectionEnd
