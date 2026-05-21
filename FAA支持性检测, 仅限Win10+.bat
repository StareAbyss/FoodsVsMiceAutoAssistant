@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ========================================================
echo   FAA 运行环境检查工具
echo ========================================================
echo.

:: 检查DirectX 12支持
echo 检查DirectX 12支持...
set DX12_OK=0
reg query "HKLM\SOFTWARE\Microsoft\DirectX" /v Version 2>nul | findstr /C:"4.09" >nul
if !errorlevel! equ 0 (
    echo   DirectX 12: 已安装
    set DX12_OK=1
) else (
    echo   DirectX 12: 未安装或版本过低
)
echo.

:: 检查dxcore.dll
echo 检查dxcore.dll...
set DXCORE_OK=0
if exist "%SystemRoot%\System32\dxcore.dll" (
    echo   dxcore.dll: 已找到
    set DXCORE_OK=1
) else (
    echo   dxcore.dll: 未找到
)
echo.

echo ========================================================
echo   检查结果与建议:
echo ========================================================
echo.

:: 根据系统版本和dxcore.dll状态提供建议
if !DXCORE_OK! equ 0 (
    echo ❌ 系统中缺少 dxcore.dll
    echo.
        echo 建议解决方案:
        echo 1. Win10系统请使用最新的系统补丁, 理论上将包含该运行库, 并自动修复该问题
        echo 2. 请在网络上搜索关键词 缺少dxcore.dll并定点修复
) else (
    echo ✅ dxcore.dll 已找到，系统环境正常
)

if !DX12_OK! equ 0 (
    echo.
    echo ❌ DirectX 12 未安装或版本过低
    echo 建议安装最新版本的 DirectX 运行库
) else (
    echo ✅ DirectX 12 已找到，系统环境正常
)
echo 若仍在FAA启动时显示DLL load failed, 请在FAA大群内私聊群主以解决问题.

echo.
echo 按任意键退出...
pause