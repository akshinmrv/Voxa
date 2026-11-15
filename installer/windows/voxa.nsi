; VoxaSetup.exe: Voxa for Windows, for the current user, with no administrator rights.
;
; Everything goes into one folder (by default %LOCALAPPDATA%\Programs\Voxa): uv, the Python
; uv downloads, and Voxa with its console in a uv tool environment. The dubs, the console's
; settings and its API keys live in %USERPROFILE%\Voxa, which uninstalling keeps.
;
; Built by scripts/build_windows_installer.py, which passes:
;   VERSION   the Voxa release it installs, x.y.z
;   UV        uv.exe for Windows
;   OUTFILE   where the installer goes
;   WHEEL     (optional) a wheel to install instead of the release from PyPI, for testing

Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

!ifndef VERSION | UV | OUTFILE
  !error "build it with scripts/build_windows_installer.py"
!endif

!define APP "Voxa"
!define PUBLISHER "Servoogle"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Voxa"
!define STUDIO "Voxa Studio"

Name "${APP}"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\Programs\Voxa"
InstallDirRegKey HKCU "Software\Voxa" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
BrandingText "${APP} ${VERSION}"
ShowInstDetails show
ShowUninstDetails show

VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "${APP}"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "FileDescription" "${APP} Setup"
VIAddVersionKey "CompanyName" "${PUBLISHER}"
VIAddVersionKey "LegalCopyright" "MIT License"

!define MUI_ICON "..\..\voxa_ui\icons\voxa.ico"
!define MUI_UNICON "..\..\voxa_ui\icons\voxa.ico"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "$(RunStudio)"
!define MUI_FINISHPAGE_RUN_FUNCTION RunStudio

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; The first is the default; Windows' own language picks among them.
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Turkish"

LangString SecVoxa ${LANG_ENGLISH} "Voxa and Voxa Studio"
LangString SecVoxa ${LANG_TURKISH} "Voxa ve Voxa Studio"
LangString SecDesktop ${LANG_ENGLISH} "Desktop shortcut"
LangString SecDesktop ${LANG_TURKISH} "Masaüstü kısayolu"
LangString Downloading ${LANG_ENGLISH} "Downloading Python, PyTorch and Voxa (about 1 GB). This takes a few minutes."
LangString Downloading ${LANG_TURKISH} "Python, PyTorch ve Voxa indiriliyor (yaklaşık 1 GB). Bu birkaç dakika sürer."
LangString Failed ${LANG_ENGLISH} "Voxa couldn't be installed (uv exited with $0). The details above say why; check the internet connection and run Setup again."
LangString Failed ${LANG_TURKISH} "Voxa kurulamadı (uv $0 koduyla çıktı). Nedeni yukarıdaki ayrıntılarda; internet bağlantısını kontrol edip kurulumu yeniden çalıştırın."
LangString FfmpegThere ${LANG_ENGLISH} "FFmpeg is already installed."
LangString FfmpegThere ${LANG_TURKISH} "FFmpeg zaten kurulu."
LangString FfmpegWinget ${LANG_ENGLISH} "Installing FFmpeg with winget..."
LangString FfmpegWinget ${LANG_TURKISH} "FFmpeg winget ile kuruluyor..."
LangString FfmpegMissing ${LANG_ENGLISH} "FFmpeg is missing, and Voxa needs it: winget install Gyan.FFmpeg"
LangString FfmpegMissing ${LANG_TURKISH} "FFmpeg eksik ve Voxa'nın buna ihtiyacı var: winget install Gyan.FFmpeg"
LangString RunStudio ${LANG_ENGLISH} "Open Voxa Studio"
LangString RunStudio ${LANG_TURKISH} "Voxa Studio'yu aç"
LangString StudioOpen ${LANG_ENGLISH} "Voxa Studio is open. Close it, then press OK."
LangString StudioOpen ${LANG_TURKISH} "Voxa Studio açık. Kapatıp Tamam'a basın."
LangString Kept ${LANG_ENGLISH} "Your dubs, settings and API keys in $PROFILE\Voxa were kept, as were engines in $PROFILE\.voxa."
LangString Kept ${LANG_TURKISH} "$PROFILE\Voxa içindeki dublajlarınız, ayarlarınız ve API anahtarlarınız ile $PROFILE\.voxa içindeki motorlar korundu."

!define SPEC_RELEASE "voxa-dub[serve,studio]==${VERSION}"

; uv's settings for this install: everything inside $INSTDIR, Python included, nothing cached.
!macro UvEnvironment
  System::Call 'Kernel32::SetEnvironmentVariable(t "UV_TOOL_DIR", t "$INSTDIR\tools")'
  System::Call 'Kernel32::SetEnvironmentVariable(t "UV_TOOL_BIN_DIR", t "$INSTDIR\bin")'
  System::Call 'Kernel32::SetEnvironmentVariable(t "UV_PYTHON_INSTALL_DIR", t "$INSTDIR\python")'
  System::Call 'Kernel32::SetEnvironmentVariable(t "UV_PYTHON_PREFERENCE", t "only-managed")'
  System::Call 'Kernel32::SetEnvironmentVariable(t "UV_NO_CACHE", t "1")'
  System::Call 'Kernel32::SetEnvironmentVariable(t "UV_NO_CONFIG", t "1")'
  ; CUDA when uv finds an NVIDIA GPU and its driver, CPU otherwise (PyPI's Windows build is
  ; CPU-only, so a GPU would go unused).
  System::Call 'Kernel32::SetEnvironmentVariable(t "UV_TORCH_BACKEND", t "auto")'
!macroend

; Files can't be replaced or removed while Voxa Studio runs from them.
!macro WaitForStudioClosed
  ${Do}
    System::Call 'user32::FindWindow(p 0, t "${STUDIO}") p .r9'
    ${If} $9 == 0
      ${Break}
    ${EndIf}
    MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION "$(StudioOpen)" /SD IDCANCEL IDOK +2
    Abort
  ${Loop}
!macroend

Function .onInit
  !insertmacro WaitForStudioClosed
FunctionEnd

Function un.onInit
  !insertmacro WaitForStudioClosed
FunctionEnd

Section "$(SecVoxa)" SecVoxa
  SectionIn RO
  SetOutPath "$INSTDIR"
  File "/oname=uv.exe" "${UV}"
  File "/oname=voxa.ico" "..\..\voxa_ui\icons\voxa.ico"
  !insertmacro UvEnvironment

  !ifdef WHEEL
    File "/oname=voxa-dub.whl" "${WHEEL}"
    StrCpy $1 "voxa-dub[serve,studio] @ file:///$INSTDIR\voxa-dub.whl"
  !else
    StrCpy $1 "${SPEC_RELEASE}"
  !endif

  DetailPrint "$(Downloading)"
  nsExec::ExecToLog '"$INSTDIR\uv.exe" tool install --upgrade --python 3.12 "$1"'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_OK|MB_ICONSTOP "$(Failed)" /SD IDOK
    Abort
  ${EndIf}
  !ifdef WHEEL
    Delete "$INSTDIR\voxa-dub.whl"
  !endif

  ; FFmpeg, as the one-line installer does: winget when it's missing.
  nsExec::ExecToStack 'cmd /c where ffmpeg'
  Pop $0
  Pop $2
  ${If} $0 == 0
    DetailPrint "$(FfmpegThere)"
  ${Else}
    nsExec::ExecToStack 'cmd /c where winget'
    Pop $0
    Pop $2
    ${If} $0 == 0
      DetailPrint "$(FfmpegWinget)"
      nsExec::ExecToLog 'winget install --id Gyan.FFmpeg --exact --silent --accept-package-agreements --accept-source-agreements'
      Pop $0
    ${Else}
      DetailPrint "$(FfmpegMissing)"
    ${EndIf}
  ${EndIf}

  ; The console keeps its jobs, uploads and API keys (.env) in this folder.
  CreateDirectory "$PROFILE\Voxa"
  SetOutPath "$PROFILE\Voxa"
  CreateShortCut "$SMPROGRAMS\${STUDIO}.lnk" "$INSTDIR\bin\voxa-studio.exe" "" "$INSTDIR\voxa.ico" 0

  WriteUninstaller "$INSTDIR\Uninstall Voxa.exe"
  WriteRegStr HKCU "Software\Voxa" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "${APP}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "${PUBLISHER}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\voxa.ico"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "URLInfoAbout" "https://voxa.servoogle.com"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall Voxa.exe"'
  WriteRegStr HKCU "${UNINSTALL_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall Voxa.exe" /S'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "EstimatedSize" $0
SectionEnd

Section "$(SecDesktop)" SecDesktop
  SetOutPath "$PROFILE\Voxa"
  CreateShortCut "$DESKTOP\${STUDIO}.lnk" "$INSTDIR\bin\voxa-studio.exe" "" "$INSTDIR\voxa.ico" 0
SectionEnd

Function RunStudio
  SetOutPath "$PROFILE\Voxa"
  Exec '"$INSTDIR\bin\voxa-studio.exe"'
FunctionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\${STUDIO}.lnk"
  Delete "$DESKTOP\${STUDIO}.lnk"
  ; Only what Setup put here: the folder may have been chosen with other things in it.
  RMDir /r "$INSTDIR\tools"
  RMDir /r "$INSTDIR\bin"
  RMDir /r "$INSTDIR\python"
  Delete "$INSTDIR\uv.exe"
  Delete "$INSTDIR\voxa.ico"
  Delete "$INSTDIR\Uninstall Voxa.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
  DeleteRegKey HKCU "Software\Voxa"
  DetailPrint "$(Kept)"
SectionEnd
