# coding:utf-8

import os
from pathlib import Path
from time import sleep


def get_root_path():
    my_path = Path(__file__).resolve()  # 该.py所在目录

    for i in range(5):
        if os.path.exists(str(my_path) + "\\LICENSE"):
            return str(my_path)
        else:
            my_path = my_path.parent  # 上一级
    print("呃呃,路径问题... 请终止")
    sleep(10000)


def get_paths():
    paths = {
        "root": get_root_path(),
        "logs": None,
        "config": None,
        "picture": {
        },
    }
    paths["logs"] = paths["root"] + "\\logs"
    paths["config"] = paths["root"] + "\\config"
    paths["picture"]["current"] = paths["root"] + "\\resource\\picture"
    paths["picture"]["common"] = paths["picture"]["current"] + "\\common"
    paths["picture"]["card"] = paths["picture"]["current"] + "\\card"
    paths["picture"]["stage"] = paths["picture"]["current"] + "\\stage"
    paths["picture"]["guild_task"] = paths["picture"]["current"] + "\\task_guild"
    paths["picture"]["spouse_task"] = paths["picture"]["current"] + "\\task_spouse"
    paths["picture"]["ready_check_stage"] = paths["picture"]["current"] + "\\stage_ready_check"

    return paths


if __name__ == '__main__':
    print(get_root_path())
