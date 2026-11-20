; Whether Microsoft Edge WebView2, which Voxa Studio's window is drawn with, is installed.
; Microsoft's own check: the runtime's version under EdgeUpdate, machine-wide (on 64-bit
; Windows a 32-bit installer reads it from WOW6432Node, where the runtime registers it) or for
; this user. Without it, pywebview falls back to Internet Explorer's engine, and Voxa Studio
; opens the console in the browser instead (voxa_studio.say_no_webview2).
; HasWebView2 leaves "1" or "0" in $WebView2. installer/windows/test_parts.nsi checks it.

!include "LogicLib.nsh"

Var WebView2
!define WEBVIEW2_KEY "SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

Function HasWebView2
  Push $0
  StrCpy $WebView2 "0"
  ReadRegStr $0 HKLM "${WEBVIEW2_KEY}" "pv"
  ${If} $0 == ""
  ${OrIf} $0 == "0.0.0.0"
    ReadRegStr $0 HKCU "${WEBVIEW2_KEY}" "pv"
  ${EndIf}
  ${If} $0 != ""
  ${AndIf} $0 != "0.0.0.0"
    StrCpy $WebView2 "1"
  ${EndIf}
  Pop $0
FunctionEnd
