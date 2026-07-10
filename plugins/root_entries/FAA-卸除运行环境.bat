@echo off
setlocal
chcp 65001 > nul
title FAA Local Environment Uninstaller

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%plugins\launcher_scripts\UVFAAUninstaller.ps1"
if not exist "%PS_SCRIPT%" set "PS_SCRIPT=%SCRIPT_DIR%..\launcher_scripts\UVFAAUninstaller.ps1"

if not exist "%PS_SCRIPT%" (
    echo ERROR: Missing uninstaller script:
    echo "%PS_SCRIPT%"
    echo Please extract the complete FAA package and try again.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
exit /b %ERRORLEVEL%
