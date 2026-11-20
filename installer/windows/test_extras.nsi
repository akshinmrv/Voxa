; Checks extras.nsh, the extras an upgrade keeps. Built and run by test_extras.ps1: run silently
; with /D=<a folder holding tools\voxa-dub\uv-receipt.toml>, it writes what KeptExtras found
; to <folder>\extras.txt. It touches nothing else: no registry, no shortcuts.

Unicode true
!ifndef OUTFILE
  !error "pass -DOUTFILE=..."
!endif
OutFile "${OUTFILE}"
RequestExecutionLevel user
SilentInstall silent
InstallDir "$TEMP\voxa-extras-test"

!include "extras.nsh"

Section
  Call KeptExtras
  FileOpen $9 "$INSTDIR\extras.txt" w
  FileWrite $9 $Extras
  FileClose $9
SectionEnd
