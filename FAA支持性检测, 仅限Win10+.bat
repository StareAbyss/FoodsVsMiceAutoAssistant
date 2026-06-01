@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ========================================================
echo   FAA 运行环境检查工具
echo ========================================================
echo.

echo 检查 DirectX 12 支持...
set DX12_OK=0
reg query "HKLM\SOFTWARE\Microsoft\DirectX" /v Version 2>nul | findstr /C:"4.09" >nul
if !errorlevel! equ 0 (
    echo   DirectX 12: 已安装
    set DX12_OK=1
) else (
    echo   DirectX 12: 未安装或版本过低
)
echo.

echo 检查 dxcore.dll...
set DXCORE_OK=0
if exist "%SystemRoot%\System32\dxcore.dll" (
    echo   dxcore.dll: 已找到
    set DXCORE_OK=1
) else (
    echo   dxcore.dll: 未找到
)
echo.

echo ========================================================
echo   检查结果与建议
echo ========================================================
echo.

if !DXCORE_OK! equ 0 (
    echo [异常] 系统中缺少 dxcore.dll
    echo.
    echo 建议解决方案:
    echo 1. Win10 系统请安装最新系统补丁，通常会包含该运行库。
    echo 2. 也可以搜索关键词「缺少 dxcore.dll」并按系统版本定向修复。
) else (
    echo [正常] dxcore.dll 已找到，系统环境正常。
)

if !DX12_OK! equ 0 (
    echo.
    echo [异常] DirectX 12 未安装或版本过低
    echo 建议安装最新版本的 DirectX 运行库。
) else (
    echo [正常] DirectX 12 已找到，系统环境正常。
)

echo.
echo 如果 FAA 启动时仍显示 DLL load failed，请在 FAA 大群内私聊群主协助排查。
echo.
echo 按任意键退出...
pause
