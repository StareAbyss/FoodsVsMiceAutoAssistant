@echo off
chcp 65001
call "F:\My RTE\Python\Venv\FoodsVsMousesAutoAssistant\Scripts\activate"

:: 执行主程序打包
pyinstaller -i "F:\My Project\Python\FoodsVsMousesAutoAssistant\resource\logo\圆角-FetDeathWing-256x-AllSize.ico" -w -D -n "FAA" -y --upx-dir "D:\Program Files\upx-4.2.4-win64" --distpath="F:\My Project\Python\_ExeWorkSpace\dist" --workpath="F:\My Project\Python\_ExeWorkSpace\build" "F:\My Project\Python\FoodsVsMousesAutoAssistant\function\faa_main.py"

:: 执行资源文件处理
echo 正在处理资源文件...
python "F:\My Project\Python\FoodsVsMousesAutoAssistant\打包 - 资源文件.py"

:: 清理构建文件
echo 清理构建文件...
rmdir /s /q "F:\My Project\Python\_ExeWorkSpace\build"

pause