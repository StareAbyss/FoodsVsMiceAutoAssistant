@echo off
setlocal
chcp 65001 > nul

set "SCRIPT_DIR=%~dp0"
set "UV_BIN_DIR=%SCRIPT_DIR%bin"
set "APP_DIR=%SCRIPT_DIR%"

if not exist "%APP_DIR%pyproject.toml" (
    if exist "%SCRIPT_DIR%..\..\pyproject.toml" (
        for %%I in ("%SCRIPT_DIR%..\..") do set "APP_DIR=%%~fI\"
    )
)

set "LOCAL_VENV_DIR=%APP_DIR%.venv"

echo ========================================
echo    FAA Local UV Uninstaller
echo ========================================
echo.
echo This only removes FAA-managed local files:
echo   %UV_BIN_DIR%
echo   %LOCAL_VENV_DIR%
echo.
echo It will NOT remove user global uv, uv cache, uv-managed Python installs,
echo or files outside this script directory.
echo.

set /p "confirm=Continue uninstall? (Type Y or y to confirm): "
if /i not "%confirm%"=="Y" (
    echo.
    echo Uninstall cancelled.
    pause
    exit /b 1
)

echo.
if exist "%UV_BIN_DIR%\" (
    echo Removing local uv directory: %UV_BIN_DIR%
    rmdir /s /q "%UV_BIN_DIR%"
    if errorlevel 1 (
        echo ERROR: Failed to remove %UV_BIN_DIR%
        pause
        exit /b 1
    )
) else (
    echo Local uv directory not found: %UV_BIN_DIR%
)

if exist "%LOCAL_VENV_DIR%\" (
    echo Removing local virtual environment: %LOCAL_VENV_DIR%
    rmdir /s /q "%LOCAL_VENV_DIR%"
    if errorlevel 1 (
        echo ERROR: Failed to remove %LOCAL_VENV_DIR%
        pause
        exit /b 1
    )
) else (
    echo Local virtual environment not found: %LOCAL_VENV_DIR%
)

echo.
echo FINISHED.
pause
