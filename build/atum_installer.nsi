; NSIS Installer Script for Atum
; This creates a standard Windows .exe installer

!include "MUI2.nsh"
!include "x64.nsh"

; Application info
!define APP_NAME "Atum"
!define APP_VERSION "1.0.0"
!define APP_PUBLISHER "Atum Project"
!define APP_URL "https://github.com/yourname/atum"
!define APP_EXECUTABLE "Atum.exe"

; Installer attributes
Name "${APP_NAME} ${APP_VERSION}"
OutFile "..\dist\Atum_${APP_VERSION}_installer.exe"
InstallDir "$PROGRAMFILES\${APP_NAME}"
ShowInstDetails show
ShowUninstDetails show

; MUI Settings
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "English"

; Installer sections
Section "Install"
  SetOutPath "$INSTDIR"
  
  ; Copy executable and files
  File /r "..\dist\Atum\*.*"

  ; Optional asset/config files: only copy if present
  File /nonfatal "..\workspace-tracking-icon.png"
  File /nonfatal "..\gui_settings.json"
  File /nonfatal "..\db_config.json"

  ; Copy model files if they exist
  File /nonfatal "..\*.task"
  File /nonfatal "..\*.tflite"
  
  ; Create shortcuts
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXECUTABLE}"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk" "$INSTDIR\uninstall.exe"
  CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXECUTABLE}"
  
  ; Write uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"
  
  ; Write registry entries for uninstall
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "DisplayName" "${APP_NAME} ${APP_VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
    "InstallLocation" "$INSTDIR"
  
SectionEnd

; Uninstaller section
Section "Uninstall"
  Delete "$INSTDIR\${APP_EXECUTABLE}"
  Delete "$INSTDIR\uninstall.exe"
  Delete "$INSTDIR\*.json"
  Delete "$INSTDIR\*.task"
  Delete "$INSTDIR\*.tflite"
  
  RMDir "$INSTDIR"
  
  ; Remove shortcuts
  Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk"
  Delete "$DESKTOP\${APP_NAME}.lnk"
  RMDir "$SMPROGRAMS\${APP_NAME}"
  
  ; Remove registry entries
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
  
SectionEnd
