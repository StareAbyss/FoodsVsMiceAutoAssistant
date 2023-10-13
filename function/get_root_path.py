import os
import sys
from pathlib import Path


def get_root_path():
    # 封装为exe使用
    # my_path = str(os.path.dirname(os.path.realpath(sys.executable)))
    # pycharm调试使用
    my_path = str(Path(__file__).resolve().parent.parent)
    return my_path


if __name__ == '__main__':
    print(get_root_path())
