切换位置
    
    cd D:\Project_Python\exe_workspace

打包开始

    pyinstaller -i "D:\Project_Python\WorkSpace\FoodsVsMouses_AutoAssistant\resource\logo\icon-64x64.ico" -w -D  "D:\Project_Python\WorkSpace\FoodsVsMouses_AutoAssistant\function\main.py"

其他tip

    -D 产生完整目录作为可执行文件
    -w 不显示黑框
    -i 路径  icon 图标

环境迁移
下载python安装程序 v3.7.9

    https://www.python.org/ftp/python/3.7.9/python-3.7.9.exe

生成配置文件 → 导入配置文件

    pip freeze > requirements.txt

导入配置文件

    pip install -r requirements.txt
    pycharm 自动