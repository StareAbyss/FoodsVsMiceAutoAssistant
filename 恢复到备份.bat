@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "ROOT=%~dp0"
set "BACKUPS=%ROOT%backups"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"
set "UPDATER=%ROOT%plugins\updater\updater.py"

if not exist "%BACKUPS%\" (
    echo 未找到备份目录: %BACKUPS%
    pause
    exit /b 1
)

if not exist "%UPDATER%" (
    echo 未找到恢复工具: %UPDATER%
    pause
    exit /b 1
)

if not exist "%PYTHON%" (
    set "PYTHON=python"
)

set /a COUNT=0
echo 可用备份:
for /d %%D in ("%BACKUPS%\FAA.backup.*" "%BACKUPS%\FAA.before-restore.*") do (
    set /a COUNT+=1
    set "BACKUP_!COUNT!=%%~fD"
    echo !COUNT!. %%~nxD
)

if "%COUNT%"=="0" (
    echo 没有可恢复的备份。
    pause
    exit /b 1
)

set /p PICK=请输入要恢复的备份编号:
set "TARGET=!BACKUP_%PICK%!"

if not defined TARGET (
    echo 无效编号。
    pause
    exit /b 1
)

echo 即将恢复备份:
echo %TARGET%
set /p CONFIRM=确认恢复请输入 YES:
if /I not "%CONFIRM%"=="YES" (
    echo 已取消。
    pause
    exit /b 1
)

"%PYTHON%" "%UPDATER%" restore --root "%ROOT%" --backup "%TARGET%" --launch "AppInstallRun.bat"
if errorlevel 1 (
    echo 恢复失败，请查看 update_cache\updater_logs。
    pause
    exit /b 1
)

echo 恢复命令已执行。
pause
