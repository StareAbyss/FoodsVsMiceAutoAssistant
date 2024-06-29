# 打包
## 切换位置
    cd "F:\My Project\Python\_ExeWorkSpace"

## 打包开始
    pyinstaller -i "F:\My Project\Python\FoodsVsMousesAutoAssistant\resource\logo\圆角-FetTuo-48x.ico" -w -D "F:\My Project\Python\FoodsVsMousesAutoAssistant\function\faa_main.py" 
## 打包开始(调试版)
    pyinstaller -i "F:\My Project\Python\FoodsVsMousesAutoAssistant\resource\logo\圆角-FetTuo-48x.ico" -D "F:\My Project\Python\FoodsVsMousesAutoAssistant\function\faa_main.py" 
## 其他tip
    `-D` 产生完整目录作为可执行文件
    `-w` 不显示黑框
    `-i 路径`  icon 图标

# 环境迁移

## 下载python安装程序 v3.7.9
    https://www.python.org/ftp/python/3.7.9/python-3.7.9.exe

## 生成配置文件
    cd "F:\My Project\Python\FoodsVsMousesAutoAssistant"
    pip freeze > requirements.txt

## 导入配置文件
    pip install -r requirements.txt

# git抽风无法提交到github
## 在git仓库打开终端 并输入下文

    git config --global --unset http.proxy
    git config --global --unset https.proxy

    git config --global http.proxy http://127.0.0.1:10809
    git config --global https.proxy http://127.0.0.1:10809