@echo off
setlocal
chcp 65001 > nul
title FAA Startup

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%AppInstallRun.ps1"

if not exist "%PS_SCRIPT%" (
    echo ERROR: Missing startup script:
    echo "%PS_SCRIPT%"
    echo Please extract the complete FAA package and start again.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
exit /b %ERRORLEVEL%
