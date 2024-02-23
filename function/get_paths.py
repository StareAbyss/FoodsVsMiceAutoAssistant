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


paths = {
    "root": get_root_path(),
    "battle_plan": None,
    "config": None,
    "customize_todo": None,
    "logs": None,
    # resource
    "font": None,
    "logo": None,
    "picture": {
    },
}


paths["battle_plan"] = paths["root"] + "\\battle_plan"
paths["config"] = paths["root"] + "\\config"
paths["customize_todo"] = paths["root"] + "\\customize_todo"
paths["logs"] = paths["root"] + "\\logs"

paths["font"] = paths["root"] + "\\resource\\font"
paths["logo"] = paths["root"] + "\\resource\\logo"
paths["picture"]["current"] = paths["root"] + "\\resource\\picture"

paths["picture"]["common"] = paths["picture"]["current"] + "\\common"
paths["picture"]["number"] = paths["picture"]["current"] + "\\number"
paths["picture"]["card"] = paths["picture"]["current"] + "\\card"
paths["picture"]["stage"] = paths["picture"]["current"] + "\\stage"
paths["picture"]["quest_guild"] = paths["picture"]["current"] + "\\quest_guild"
paths["picture"]["quest_spouse"] = paths["picture"]["current"] + "\\quest_spouse"
paths["picture"]["ready_check_stage"] = paths["picture"]["current"] + "\\stage_ready_check"
paths["picture"]["map"] = paths["picture"]["current"] + "\\map"
paths["picture"]["item"] = paths["picture"]["current"] + "\\item"
paths["picture"]["error"] = paths["picture"]["current"] + "\\error"


def get_paths_faa_new():
    global paths
    return paths


def get_paths_faa_old():
    """老方法, 不启用"""
    my_paths = {
        "root": get_root_path(),
        "logs": None,
        "config": None,
        "picture": {
        },
    }
    my_paths["logs"] = my_paths["root"] + "\\logs"
    my_paths["config"] = my_paths["root"] + "\\config"
    my_paths["picture"]["current"] = my_paths["root"] + "\\resource\\picture"
    my_paths["picture"]["common"] = my_paths["picture"]["current"] + "\\common"
    my_paths["picture"]["number"] = my_paths["picture"]["current"] + "\\number"
    my_paths["picture"]["card"] = my_paths["picture"]["current"] + "\\card"
    my_paths["picture"]["stage"] = my_paths["picture"]["current"] + "\\stage"
    my_paths["picture"]["guild_task"] = my_paths["picture"]["current"] + "\\quest_guild"
    my_paths["picture"]["spouse_task"] = my_paths["picture"]["current"] + "\\quest_spouse"
    my_paths["picture"]["ready_check_stage"] = my_paths["picture"]["current"] + "\\stage_ready_check"
    return my_paths


if __name__ == '__main__':
    print(get_root_path())
    print(get_paths_faa_new())
