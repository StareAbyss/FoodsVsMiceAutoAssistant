import os
import sys
from pathlib import Path
from time import sleep


def get_root_path():
    my_path = Path(__file__).resolve()  # 该.py所在目录
    my_path = my_path.parent  # 上一级
    my_path = my_path.parent  # 上一级

    for i in range(3):
        if os.path.exists(str(my_path) + "\\todo.json"):
            return str(my_path)
        else:
            my_path = my_path.parent  # 上一级
    print("呃呃,路径问题... 请终止")
    sleep(10000)


if __name__ == '__main__':
    print(get_root_path())
