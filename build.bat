@echo off
REM ----------------------------------------------------------------------
REM 强制 CMD 使用 UTF-8 编码，解决中文乱码问题
chcp 65001 > nul
REM ----------------------------------------------------------------------

REM --- 变量定义及路径设置 ---
set "APP_NAME=FAA"

REM 脚本所在的目录 (项目根目录)
set "PROJECT_ROOT=%~dp0"
set "POST_BUILD_SCRIPT=%PROJECT_ROOT%打包 - 资源文件.py"

REM 输出路径：使用相对路径 ..\_ExeWorkSpace
set "DIST_PATH=%PROJECT_ROOT%..\_ExeWorkSpace\dist"
set "WORK_PATH=%PROJECT_ROOT%..\_ExeWorkSpace\build"

set "ICON_PATH=%PROJECT_ROOT%resource\logo\圆角-FetDeathWing-256x-AllSize.ico"
set "MAIN_SCRIPT=%PROJECT_ROOT%function\faa_main.py"

echo ----------------------------------------------------
echo 🚀 开始 PyInstaller 打包流程: %APP_NAME%
echo ----------------------------------------------------

REM ----------------------------------------------------
REM --- 2. UPX 路径参数检查 (支持默认值) ---
REM ----------------------------------------------------

REM 检查是否提供了参数 (%1)
IF "%~1"=="" (
    REM **未提供参数，使用默认路径**
    set "UPX_PATH=%PROJECT_ROOT%upx"
    echo ℹ️ 未指定 UPX 路径，使用默认路径: "%UPX_PATH%"
) ELSE (
    REM **提供了参数，使用用户指定的路径**
    set "UPX_PATH=%~1"
    echo ℹ️ 已指定 UPX 路径: "%UPX_PATH%"
)

REM 统一检查 upx.exe 是否存在于设定的路径中
IF NOT EXIST "%UPX_PATH%\upx.exe" (
    echo.
    echo ❌ 错误：在指定的 UPX 路径中未找到 upx.exe 文件。
    echo    请将 upx.exe 放在该目录下，或通过参数指定正确的 UPX 目录。
    echo    检查路径: "%UPX_PATH%\upx.exe"
    pause
    goto :eof
)

echo ✅ UPX 路径和 upx.exe 检查通过。

REM ----------------------------------------------------
REM --- 1. 关键文件存在性检查 ---
REM ----------------------------------------------------

REM 检查图标文件
IF NOT EXIST "%ICON_PATH%" (
    echo.
    echo ❌ 错误：打包图标文件不存在！
    echo    检查路径: "%ICON_PATH%"
    pause
    goto :eof
)

REM 检查主脚本文件
IF NOT EXIST "%MAIN_SCRIPT%" (
    echo.
    echo ❌ 错误：主脚本文件不存在！
    echo    检查路径: "%MAIN_SCRIPT%"
    pause
    goto :eof
)

echo ✅ 图标和主脚本文件检查通过。
echo ----------------------------------------------------

REM ----------------------------------------------------
REM --- 执行 PyInstaller 打包 ---
REM ----------------------------------------------------

pyinstaller -i "%ICON_PATH%" ^
    -w -D -n "%APP_NAME%" -y ^
    --upx-dir "%UPX_PATH%" ^
    --distpath="%DIST_PATH%" ^
    --workpath="%WORK_PATH%" ^
    --exclude PyQt6 ^
    "%MAIN_SCRIPT%"

REM 检查 PyInstaller 的退出代码
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ 打包失败，请检查上面的 PyInstaller 错误信息。
    pause
    goto :eof
)

echo.
echo ✅ 主程序打包成功! 可执行文件位于: %DIST_PATH%\%APP_NAME%
echo ----------------------------------------------------

REM ----------------------------------------------------
REM --- 3. 打包后执行自动化脚本 ---
REM ----------------------------------------------------

REM 检查打包后脚本是否存在
IF NOT EXIST "%POST_BUILD_SCRIPT%" (
    echo.
    echo ⚠️ 警告：打包后脚本 "%POST_BUILD_SCRIPT%" 不存在，跳过执行资源文件处理。
    goto :skip_post_build_check
)

echo.
echo 📦 打包成功，开始自动执行资源文件处理脚本...

REM 使用 CALL 命令执行 Python 脚本，并将所有输出重定向到 NUL
CALL python "%POST_BUILD_SCRIPT%" 2>&1 > NUL

REM 检查 python 脚本的退出代码
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ⚠️ 警告：资源文件脚本执行失败 退出代码 %ERRORLEVEL% ，请检查脚本输出。
) ELSE (
    echo.
    echo ✅ 资源文件脚本执行成功。
)

:skip_post_build_check

echo.
echo ====================================================
echo ✨ 所有操作完成。
echo ====================================================