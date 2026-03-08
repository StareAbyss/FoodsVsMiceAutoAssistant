@echo off
chcp 65001 > nul
echo Step 1: Check if uv is already installed
where uv >nul 2>nul
if %errorlevel% equ 0 (
    echo uv is already installed, skipping installation
) else (
    echo uv not found, installing from local
    cd /d "%~dp0uv"
    rem Set INSTALLER_DOWNLOAD_URL environment variable for local installation
    for /f "delims=" %%a in ('powershell -command "(Get-Location).Path"') do set "INSTALLER_DOWNLOAD_URL=%%a"
    rem Execute uv-installer.ps1 script (requires PowerShell)
    powershell -ExecutionPolicy Bypass -File .\uv-installer.ps1
)
cd /d "%~dp0"
echo Install Python environment
echo Installing Python with mirror configuration...
set UV_PYTHON_INSTALL_MIRROR=https://ghfast.top/https://github.com/astral-sh/python-build-standalone/releases/download
uv python install 3.12
echo Restore environment using uv
uv sync
echo Run app
uv run python -m function.faa_main
echo Press Enter to exit
pause
