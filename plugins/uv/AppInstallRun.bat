@echo off
setlocal
chcp 65001 > nul

set "SCRIPT_DIR=%~dp0"
set "UV_DIR=%SCRIPT_DIR%uv"
set "UV_BIN_DIR=%SCRIPT_DIR%bin"
set "UV_EXE=%UV_BIN_DIR%\uv.exe"
set "UV_ZIP=%UV_DIR%\uv-x86_64-pc-windows-msvc.zip"
set "UV_ZIP_SHA256=30FDF26C209F0CB7C97D3B08A26AB4E78CE5AE0E031B88798CBACCC0F24F452B"
set "APP_DIR=%SCRIPT_DIR%"

call :FindAppDir || goto :Abort
call :PrepareUv || goto :Abort
call :InstallPython || goto :Abort
call :SyncLocked || goto :Abort
call :RunApp || goto :Abort

echo Press Enter to exit
pause
exit /b 0

:FindAppDir
if exist "%APP_DIR%pyproject.toml" exit /b 0

if exist "%SCRIPT_DIR%..\..\pyproject.toml" (
    for %%I in ("%SCRIPT_DIR%..\..") do set "APP_DIR=%%~fI\"
    exit /b 0
)

echo ERROR: pyproject.toml not found. Run this script from the packaged app root, or keep it under plugins\uv in the source tree.
exit /b 1

:PrepareUv
echo Step 1: Prepare project-local uv
if exist "%UV_EXE%" (
    echo Using project-local uv: %UV_EXE%
    exit /b 0
)

echo Project-local uv not found, installing from bundled package...
if not exist "%UV_DIR%\uv-installer.ps1" (
    echo ERROR: Missing installer: %UV_DIR%\uv-installer.ps1
    exit /b 1
)
if not exist "%UV_ZIP%" (
    echo ERROR: Missing bundled uv package: %UV_ZIP%
    exit /b 1
)

echo Verifying bundled uv package...
powershell -NoProfile -ExecutionPolicy Bypass -Command "if ((Get-FileHash -Algorithm SHA256 -LiteralPath $env:UV_ZIP).Hash -ne $env:UV_ZIP_SHA256) { exit 1 }"
if errorlevel 1 (
    echo ERROR: bundled uv package SHA256 mismatch.
    exit /b 1
)

set "UV_INSTALL_DIR=%UV_BIN_DIR%"
set "UV_NO_MODIFY_PATH=1"
set "UV_DISABLE_UPDATE=1"
set "INSTALLER_DOWNLOAD_URL=%UV_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%UV_DIR%\uv-installer.ps1"
if errorlevel 1 (
    echo ERROR: uv installer failed.
    exit /b 1
)

if not exist "%UV_EXE%" (
    echo ERROR: uv.exe was not installed to %UV_EXE%
    exit /b 1
)

exit /b 0

:InstallPython
cd /d "%APP_DIR%"
echo Step 2: Install Python environment
"%UV_EXE%" python install 3.12
if errorlevel 1 (
    echo ERROR: uv python install failed.
    exit /b 1
)
exit /b 0

:SyncLocked
cd /d "%APP_DIR%"
echo Step 3: Restore environment using locked dependencies
"%UV_EXE%" sync --locked
if errorlevel 1 (
    echo ERROR: uv sync --locked failed.
    exit /b 1
)
exit /b 0

:RunApp
cd /d "%APP_DIR%"
echo Step 4: Run app
"%UV_EXE%" run python -m function.faa_main
if errorlevel 1 (
    echo ERROR: app exited with an error.
    exit /b 1
)
exit /b 0

:Abort
echo.
echo Installation or startup failed.
pause
exit /b 1
