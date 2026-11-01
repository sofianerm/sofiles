Unicode True
ManifestSupportedOS all
ManifestDPIAware True
RequestExecutionLevel user
SetCompressor /SOLID lzma
Name "Sofiles ${PRODUCT_VERSION}"
OutFile "${OUTPUT_EXE}"
InstallDir "$LOCALAPPDATA\Programs\Sofiles"
InstallDirRegKey HKCU "Software\Sofiles" "InstallDir"
BrandingText "Sofiles"
ShowInstDetails show
ShowUninstDetails show
VIProductVersion "${PRODUCT_VERSION}.0"
VIAddVersionKey /LANG=1033 "ProductName" "Sofiles"
VIAddVersionKey /LANG=1033 "CompanyName" "Sofiles"
VIAddVersionKey /LANG=1033 "FileDescription" "Sofiles Setup"
VIAddVersionKey /LANG=1033 "FileVersion" "${PRODUCT_VERSION}"
VIAddVersionKey /LANG=1033 "LegalCopyright" "Sofiles contributors"

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "Sections.nsh"

!define MUI_ICON "${PRODUCT_ICON}"
!define MUI_UNICON "${PRODUCT_ICON}"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Sofiles ${PRODUCT_VERSION}"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION "RunSofiles"
!define MUI_FINISHPAGE_LINK "github.com/sofianerm/sofiles"
!define MUI_FINISHPAGE_LINK_LOCATION "https://github.com/sofianerm/sofiles"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH
!insertmacro MUI_LANGUAGE "French"
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "German"

LangString CoreName ${LANG_FRENCH} "Sofiles (obligatoire)"
LangString CoreName ${LANG_ENGLISH} "Sofiles (required)"
LangString CoreName ${LANG_GERMAN} "Sofiles (erforderlich)"
LangString DesktopName ${LANG_FRENCH} "Raccourci sur le bureau"
LangString DesktopName ${LANG_ENGLISH} "Desktop shortcut"
LangString DesktopName ${LANG_GERMAN} "Desktop-Verknüpfung"
LangString SetupFailed ${LANG_FRENCH} "Fermez Sofiles et ses réglages, puis réessayez. L'installation conserve vos favoris. Consultez le détail de l'erreur ci-dessus si le problème persiste."
LangString SetupFailed ${LANG_ENGLISH} "Close Sofiles and its settings, then try again. Your bookmarks are kept. Check the error details above if the problem continues."
LangString SetupFailed ${LANG_GERMAN} "Schließen Sie Sofiles und die Einstellungen und versuchen Sie es erneut. Ihre Lesezeichen bleiben erhalten. Beachten Sie die Fehlerdetails oben, falls das Problem weiterhin besteht."
LangString CoreDesc ${LANG_FRENCH} "Onglets, favoris, réglages, aide et langues français, anglais et allemand."
LangString CoreDesc ${LANG_ENGLISH} "Tabs, bookmarks, settings, help, and French, English and German languages."
LangString CoreDesc ${LANG_GERMAN} "Tabs, Lesezeichen, Einstellungen, Hilfe und Sprachen Französisch, Englisch und Deutsch."
LangString DesktopDesc ${LANG_FRENCH} "Ajoute un raccourci Sofiles sur le bureau."
LangString DesktopDesc ${LANG_ENGLISH} "Adds a Sofiles shortcut to the desktop."
LangString DesktopDesc ${LANG_GERMAN} "Erstellt eine Sofiles-Verknüpfung auf dem Desktop."

Var TestMode
Var LanguageCode
Var Parameters
Var Result
Var CompilerGuard
Var HelperOutput

Function SetupError
  DetailPrint "$HelperOutput"
  MessageBox MB_ICONSTOP "$(SetupFailed)$\r$\n$\r$\n$HelperOutput" /SD IDOK
  SetErrorLevel 1
  Abort
FunctionEnd

Function .onInit
  System::Call 'kernel32::CreateMutexW(p 0,i 0,w "Local\SofilesSetup") p.r0 ?e'
  Pop $1
  ${If} $1 = 183
    Abort
  ${EndIf}
  StrCpy $CompilerGuard $0
  SetShellVarContext current
  StrCpy $TestMode "0"
  ${GetParameters} $Parameters
  ${GetOptions} $Parameters "/TESTMODE=" $TestMode
  ${If} $TestMode != "1"
    StrCpy $TestMode "0"
    ReadRegStr $LANGUAGE HKCU "Software\Sofiles" "InstallerLanguage"
  ${EndIf}
  IfSilent skip_language
    !insertmacro MUI_LANGDLL_DISPLAY
  skip_language:
  ${GetOptions} $Parameters "/LANG=" $0
  ${If} $0 == "fr"
    StrCpy $LANGUAGE ${LANG_FRENCH}
  ${ElseIf} $0 == "en"
    StrCpy $LANGUAGE ${LANG_ENGLISH}
  ${ElseIf} $0 == "de"
    StrCpy $LANGUAGE ${LANG_GERMAN}
  ${EndIf}
FunctionEnd

Section "$(CoreName)" Core
  SectionIn RO
  StrCpy $LanguageCode "fr"
  ${If} $LANGUAGE = ${LANG_ENGLISH}
    StrCpy $LanguageCode "en"
  ${ElseIf} $LANGUAGE = ${LANG_GERMAN}
    StrCpy $LanguageCode "de"
  ${EndIf}
  InitPluginsDir
  SetOutPath "$PLUGINSDIR"
  File /oname=SofilesSetupHelper.exe "${SETUP_HELPER}"
  File /oname=install-files.txt "${INSTALL_MANIFEST}"
  nsExec::ExecToStack '"$PLUGINSDIR\SofilesSetupHelper.exe" --plan "$INSTDIR" "$PLUGINSDIR\install-files.txt" "$LanguageCode" "$TestMode"'
  Pop $Result
  Pop $HelperOutput
  ${If} $Result != 0
    Call SetupError
  ${EndIf}
  SetOutPath "$INSTDIR\versions\${PRODUCT_VERSION}"
  ClearErrors
  File /r /x "First Run" /x "runtime-language.json" "${PAYLOAD_DIR}\*.*"
  ${If} ${Errors}
    StrCpy $HelperOutput "SF-SETUP-COPY"
    Call SetupError
  ${EndIf}
  nsExec::ExecToStack '"$PLUGINSDIR\SofilesSetupHelper.exe" --configure "$INSTDIR" "$LanguageCode" "$TestMode"'
  Pop $Result
  Pop $HelperOutput
  ${If} $Result != 0
    Call SetupError
  ${EndIf}
  ClearErrors
  WriteINIStr "$INSTDIR\sofiles-install.ini" "Sofiles" "TestMode" "$TestMode"
  WriteINIStr "$INSTDIR\sofiles-install.ini" "Sofiles" "Version" "${PRODUCT_VERSION}"
  WriteINIStr "$INSTDIR\sofiles-install.ini" "Sofiles" "InstallerLanguage" "$LANGUAGE"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  ${If} ${Errors}
    StrCpy $HelperOutput "SF-SETUP-UNINSTALLER"
    Call SetupError
  ${EndIf}
  ClearErrors
  ${If} $TestMode == "0"
    CreateDirectory "$SMPROGRAMS\Sofiles"
    CreateShortCut "$SMPROGRAMS\Sofiles\Sofiles.lnk" "$INSTDIR\versions\${PRODUCT_VERSION}\SofilesSettings.exe" "--launch" "$INSTDIR\versions\${PRODUCT_VERSION}\assets\sofiles.ico"
    CreateShortCut "$SMPROGRAMS\Sofiles\Sofiles Settings.lnk" "$INSTDIR\versions\${PRODUCT_VERSION}\SofilesSettings.exe" "" "$INSTDIR\versions\${PRODUCT_VERSION}\assets\sofiles.ico"
    CreateShortCut "$SMPROGRAMS\Sofiles\Uninstall Sofiles.lnk" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "Software\Sofiles" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "Software\Sofiles" "InstallerLanguage" "$LANGUAGE"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sofiles" "DisplayName" "Sofiles"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sofiles" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sofiles" "Publisher" "Sofiles"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sofiles" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sofiles" "DisplayIcon" "$INSTDIR\versions\${PRODUCT_VERSION}\Sofiles.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sofiles" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sofiles" "QuietUninstallString" '$\"$INSTDIR\Uninstall.exe$\" /S'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sofiles" "HelpLink" "mailto:so.messaoudi@gmail.com"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sofiles" "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sofiles" "NoRepair" 1
  ${EndIf}
  ${If} ${Errors}
    StrCpy $HelperOutput "SF-SETUP-SHORTCUTS"
    Call SetupError
  ${EndIf}
SectionEnd

Section "$(DesktopName)" Desktop
  ${If} $TestMode == "0"
    CreateShortCut "$DESKTOP\Sofiles.lnk" "$INSTDIR\versions\${PRODUCT_VERSION}\SofilesSettings.exe" "--launch" "$INSTDIR\versions\${PRODUCT_VERSION}\assets\sofiles.ico"
    WriteINIStr "$INSTDIR\sofiles-install.ini" "Sofiles" "DesktopShortcut" "1"
  ${EndIf}
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${Core} $(CoreDesc)
  !insertmacro MUI_DESCRIPTION_TEXT ${Desktop} $(DesktopDesc)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Function RunSofiles
  ${If} $TestMode == "0"
    System::Call 'kernel32::CloseHandle(p $CompilerGuard)'
    StrCpy $CompilerGuard 0
    Exec '"$INSTDIR\versions\${PRODUCT_VERSION}\SofilesSettings.exe" --launch'
  ${EndIf}
FunctionEnd

Function un.onInit
  System::Call 'kernel32::CreateMutexW(p 0,i 0,w "Local\SofilesSetup") p.r0 ?e'
  Pop $1
  ${If} $1 = 183
    Abort
  ${EndIf}
  StrCpy $CompilerGuard $0
  SetShellVarContext current
  ReadINIStr $TestMode "$INSTDIR\sofiles-install.ini" "Sofiles" "TestMode"
  ReadINIStr $LANGUAGE "$INSTDIR\sofiles-install.ini" "Sofiles" "InstallerLanguage"
  ${If} $TestMode != "1"
    StrCpy $TestMode "0"
  ${EndIf}
FunctionEnd

Section "Uninstall"
  InitPluginsDir
  SetOutPath "$PLUGINSDIR"
  File /oname=SofilesSetupHelper.exe "${SETUP_HELPER}"
  nsExec::ExecToLog '"$PLUGINSDIR\SofilesSetupHelper.exe" --uninstall "$INSTDIR" "$TestMode"'
  Pop $Result
  ${If} $Result != 0
    MessageBox MB_ICONSTOP "$(SetupFailed)" /SD IDOK
    SetErrorLevel 1
    Abort
  ${EndIf}
  ${If} $TestMode == "0"
    Delete "$SMPROGRAMS\Sofiles\Sofiles.lnk"
    Delete "$SMPROGRAMS\Sofiles\Sofiles Settings.lnk"
    Delete "$SMPROGRAMS\Sofiles\Uninstall Sofiles.lnk"
    RMDir "$SMPROGRAMS\Sofiles"
    ReadINIStr $0 "$INSTDIR\sofiles-install.ini" "Sofiles" "DesktopShortcut"
    ${If} $0 == "1"
      Delete "$DESKTOP\Sofiles.lnk"
    ${EndIf}
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Sofiles"
    DeleteRegKey HKCU "Software\Sofiles"
  ${EndIf}
  Delete "$INSTDIR\Uninstall.exe"
  Delete "$INSTDIR\sofiles-install.ini"
  Delete "$INSTDIR\sofiles-install.json"
  RMDir "$INSTDIR"
SectionEnd
