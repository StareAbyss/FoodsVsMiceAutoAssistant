@echo off
setlocal
chcp 65001 > nul

set "SCRIPT_DIR=%~dp0"
set "UV_EXE=%SCRIPT_DIR%bin\uv.exe"
set "APP_DIR=%SCRIPT_DIR%"

if not exist "%APP_DIR%pyproject.toml" (
    if exist "%SCRIPT_DIR%..\..\pyproject.toml" (
        for %%I in ("%SCRIPT_DIR%..\..") do set "APP_DIR=%%~fI\"
    )
)

if not exist "%UV_EXE%" goto :error
if not exist "%APP_DIR%pyproject.toml" goto :error

cd /d "%APP_DIR%"
"%UV_EXE%" run python -m function.faa_main
goto :eof

:error
(
echo msgbox "Error: project-local uv or pyproject.toml not found!" ^& vbCrLf ^& vbCrLf ^& "Please run AppInstallRun.bat before debug_run.bat.", 48, "uv Error"
) > "%temp%\msg.vbs"
cscript //nologo "%temp%\msg.vbs"
del "%temp%\msg.vbs"
exit /b 1
