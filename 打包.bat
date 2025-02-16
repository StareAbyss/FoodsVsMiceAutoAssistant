@echo off
chcp 65001
call "F:\My RTE\Python\Venv\FoodsVsMousesAutoAssistant\Scripts\activate"
pyinstaller -i "F:\My Project\Python\FoodsVsMousesAutoAssistant\resource\logo\圆角-FetDeathWing-256x-AllSize.ico" -w -D -n "FAA" -y --upx-dir "D:\Program Files\upx-4.2.4-win64" --distpath="F:\My Project\Python\_ExeWorkSpace\dist" --workpath="F:\My Project\Python\_ExeWorkSpace\build" "F:\My Project\Python\FoodsVsMousesAutoAssistant\function\faa_main.py"
echo 清理构建文件...
rmdir /s /q "F:\My Project\Python\_ExeWorkSpace\build"
pause