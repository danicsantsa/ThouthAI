@echo off
REM Atum - Installation Script for Windows
REM Downloads and installs Atum

setlocal enabledelayedexpansion

cls

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║         Atum - Activity Tracking Application               ║
echo ║                Windows Installer                           ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Check for admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] This installer requires administrator privileges
    echo Please right-click this file and select "Run as administrator"
    pause
    exit /b 1
)

REM Check for Python
echo Checking system requirements...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Python is not installed
    echo Download Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Python !PYTHON_VERSION! found

REM Check for pip
pip --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] pip is not available
    echo Try reinstalling Python with pip enabled
    pause
    exit /b 1
)

echo [OK] pip is available

REM Download or install
setlocal enabledelayedexpansion
set "INSTALL_DIR=%ProgramFiles%\Atum"
set VERSION=latest

if "%~1"=="" (
    set INSTALL_MODE=auto
) else (
    set INSTALL_MODE=%~1
)

echo.
echo Installation directory: !INSTALL_DIR!
echo.
echo Choose installation method:
echo 1. Download installer (requires internet)
echo 2. Install from source (requires git)
echo 3. Exit
echo.

if "!INSTALL_MODE!"=="auto" (
    set /p CHOICE=Enter your choice (1-3):
) else (
    set CHOICE=!INSTALL_MODE!
)

if "!CHOICE!"=="1" (
    goto download_installer
) else if "!CHOICE!"=="2" (
    goto install_source
) else if "!CHOICE!"=="3" (
    goto end
) else (
    echo Invalid choice
    goto end
)

:download_installer
echo.
echo Downloading Atum installer...
echo.

REM Check for curl or powershell
where curl >nul 2>&1
if %errorLevel% equ 0 (
    echo Downloading Atum_latest_installer.exe...
    curl -L "https://github.com/yourname/atum/releases/download/v1.0.0/Atum_1.0.0_installer.exe" ^
        -o "%temp%\Atum_installer.exe"
    
    if !errorLevel! equ 0 (
        echo Running installer...
        start "" "%temp%\Atum_installer.exe"
        goto success
    )
) else (
    echo Using PowerShell to download...
    powershell -Command "(New-Object System.Net.ServicePointManager).SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12; ^
        (New-Object System.Net.WebClient).DownloadFile('https://github.com/yourname/atum/releases/download/v1.0.0/Atum_1.0.0_installer.exe', '%temp%\Atum_installer.exe')"
    
    if !errorLevel! equ 0 (
        echo Running installer...
        start "" "%temp%\Atum_installer.exe"
        goto success
    )
)

echo [ERROR] Failed to download installer
echo Try downloading manually from: https://github.com/yourname/atum/releases
pause
goto end

:install_source
echo.
echo Installing from source...
echo.

REM Check for git
where git >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Git is not installed
    echo Download Git from: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo Creating installation directory...
if not exist "!INSTALL_DIR!" mkdir "!INSTALL_DIR!"
cd /d "!INSTALL_DIR!"

echo Cloning repository...
git clone https://github.com/yourname/atum.git . 2>nul
if %errorLevel% neq 0 (
    echo [ERROR] Failed to clone repository
    pause
    exit /b 1
)

echo Creating Python virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

if !errorLevel! neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo Creating desktop shortcut...
powershell -Command ^
    "$WshShell = New-Object -ComObject WScript.Shell; " ^
    "$Shortcut = $WshShell.CreateShortcut('%UserProfile%\Desktop\Atum.lnk'); " ^
    "$Shortcut.TargetPath = '!INSTALL_DIR!\run.bat'; " ^
    "$Shortcut.Save()"

echo Creating start menu shortcut...
powershell -Command ^
    "$WshShell = New-Object -ComObject WScript.Shell; " ^
    "$Shortcut = $WshShell.CreateShortcut('%AppData%\Microsoft\Windows\Start Menu\Programs\Atum.lnk'); " ^
    "$Shortcut.TargetPath = '!INSTALL_DIR!\run.bat'; " ^
    "$Shortcut.Save()"

REM Create run.bat launcher
echo Creating launcher...
(
    echo @echo off
    echo cd /d "!INSTALL_DIR!"
    echo call venv\Scripts\activate.bat
    echo python atum.py
    echo pause
) > "!INSTALL_DIR!\run.bat"

goto success

:success
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║              ^! Installation Complete!                      ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo To launch Atum:
echo   - Start Menu: Search for "Atum"
echo   - Desktop: Double-click "Atum" shortcut
echo   - File Explorer: Navigate to !INSTALL_DIR!
echo.
pause
goto end

:end
echo.
echo Exiting installer...
