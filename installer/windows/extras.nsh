; The extras an earlier install had, so that installing again (to upgrade) keeps them. Setup
; installs voxa-dub[serve,studio]; `voxa doctor` and the console tell how to add others
; (diarize, url...) to the same environment, and an upgrade that named only Setup's two would
; quietly take those away. uv records them in the tool's receipt, on one line:
;   requirements = [{ name = "voxa-dub", extras = ["serve", "studio", "url"], ... }]
; KeptExtras leaves them in $Extras: Setup's two first, then the others as they were.
; installer/windows/test_parts.nsi checks it on sample receipts.

!include "LogicLib.nsh"
!include "StrFunc.nsh"
${StrStr}
${StrRep}

Var Extras

Function KeptExtras
  StrCpy $Extras "serve,studio"
  ClearErrors
  FileOpen $0 "$INSTDIR\tools\voxa-dub\uv-receipt.toml" r
  ${If} ${Errors}
    Return
  ${EndIf}
  ${Do}
    ClearErrors
    FileRead $0 $1
    ${If} ${Errors}
      ${Break}
    ${EndIf}
    ${StrStr} $2 $1 'name = "voxa-dub"'
    ${If} $2 == ""
      ${Continue}
    ${EndIf}
    ${StrStr} $3 $2 "extras = ["
    ${If} $3 == ""
      ${Break}
    ${EndIf}
    ; What is between the brackets, without quotes or spaces: "serve,studio,url".
    StrCpy $3 $3 "" 10
    ${StrStr} $4 $3 "]"
    StrLen $5 $3
    StrLen $6 $4
    IntOp $5 $5 - $6
    StrCpy $3 $3 $5
    ${StrRep} $3 $3 '"' ""
    ${StrRep} $3 $3 " " ""
    ; Without Setup's own, which come first anyway.
    StrCpy $3 ",$3,"
    ${StrRep} $3 $3 ",serve," ","
    ${StrRep} $3 $3 ",studio," ","
    ${Do}
      StrCpy $4 $3 1
      ${If} $4 != ","
        ${Break}
      ${EndIf}
      StrCpy $3 $3 "" 1
    ${Loop}
    ${Do}
      StrCpy $4 $3 1 -1
      ${If} $4 != ","
        ${Break}
      ${EndIf}
      StrCpy $3 $3 -1
    ${Loop}
    ${If} $3 != ""
      StrCpy $Extras "serve,studio,$3"
    ${EndIf}
    ${Break}
  ${Loop}
  FileClose $0
FunctionEnd
