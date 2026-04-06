@echo off
chcp 65001 > nul

echo ========================================
echo    UV Uninstaller
echo ========================================
echo.
echo Warning: This will:
echo   1. Clean uv cache
echo   2. Delete uv Python directory
echo   3. Delete uv.exe and uvx.exe
echo   4. "!!!!!!!!!!!!!!!!!! Delete all files in this directory !!!!!!!!!!!!!!!!!"
echo.
set /p confirm=Continue uninstall? (Type Y or y to confirm): 
if /i not "%confirm%"=="Y" (
    echo.
    echo Uninstall cancelled.
    pause
    exit /b 1
)
echo.
set "SCRIPT_DIR=%~dp0"

echo "do uv cache clean"
powershell -Command "uv cache clean"

echo "do rm -r "$(uv python dir)""
powershell -Command "rm -r "$(uv python dir)""

echo rm $HOME\.local\bin\uv.exe
powershell -Command "rm $HOME\.local\bin\uv.exe"

echo rm $HOME\.local\bin\uvx.exe
powershell -Command "rm $HOME\.local\bin\uvx.exe"

echo.
echo Cleaning up directory: %SCRIPT_DIR%
cd /d "%SCRIPT_DIR%"

for /f "delims=" %%i in ('dir /a /b') do (
    if not "%%~nxi"=="%~nx0" (
        if exist "%%i\" (
            rmdir /s /q "%%i"
        ) else (
            del /q "%%i"
        )
    )
)

echo.
echo Removing self: %~nx0
timeout /t 2 /nobreak > nul
del "%~f0"

echo.
echo FINISHED!!!
pause 