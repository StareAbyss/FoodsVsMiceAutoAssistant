# 打包

## 打包

    记得使用资源文件打包.py 路径请自行调整 默认是在项目上一级新建目录以打包

    pyinstaller -i "F:\My Project\Python\FoodsVsMousesAutoAssistant\resource\logo\圆角-FetTuo-48x.ico" -w -D -n "FAA" -y --distpath="F:\My Project\Python\_ExeWorkSpace\dist" --workpath="F:\My Project\Python\_ExeWorkSpace\build" "F:\My Project\Python\FoodsVsMousesAutoAssistant\function\faa_main.py"

## 打包 - 调试版
    -w -> -c

    pyinstaller -i "F:\My Project\Python\FoodsVsMousesAutoAssistant\resource\logo\圆角-FetTuo-48x.ico" -c -D -n "FAA" -y --distpath="F:\My Project\Python\_ExeWorkSpace\dist" --workpath="F:\My Project\Python\_ExeWorkSpace\build" "F:\My Project\Python\FoodsVsMousesAutoAssistant\function\faa_main.py"

# 环境迁移

## 下载python安装程序 v3.12.5
    https://www.python.org/ftp/python/

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