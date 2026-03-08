@echo off
where uv >nul 2>&1
if %ERRORLEVEL% neq 0 goto :error
uv run python -m function.faa_main
goto :eof

:error
(
echo msgbox "Error: uv command not found!" ^& vbCrLf ^& vbCrLf ^& "Please install uv before use FAA.", 48, "uv Error"
) > "%temp%\msg.vbs"
cscript //nologo "%temp%\msg.vbs"
del "%temp%\msg.vbs"