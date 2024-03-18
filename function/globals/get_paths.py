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


# 定义为全局变量
PATHS = {
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

PATHS["battle_plan"] = PATHS["root"] + "\\battle_plan"
PATHS["config"] = PATHS["root"] + "\\config"
PATHS["customize_todo"] = PATHS["root"] + "\\customize_todo"
PATHS["logs"] = PATHS["root"] + "\\logs"

PATHS["font"] = PATHS["root"] + "\\resource\\font"
PATHS["logo"] = PATHS["root"] + "\\resource\\logo"
PATHS["picture"]["current"] = PATHS["root"] + "\\resource\\picture"

PATHS["picture"]["common"] = PATHS["picture"]["current"] + "\\common"
PATHS["picture"]["number"] = PATHS["picture"]["current"] + "\\number"
PATHS["picture"]["card"] = PATHS["picture"]["current"] + "\\card"
PATHS["picture"]["stage"] = PATHS["picture"]["current"] + "\\stage"
PATHS["picture"]["quest_guild"] = PATHS["picture"]["current"] + "\\quest_guild"
PATHS["picture"]["quest_spouse"] = PATHS["picture"]["current"] + "\\quest_spouse"
PATHS["picture"]["quest_food"] = PATHS["picture"]["current"] + "\\quest_food"
PATHS["picture"]["ready_check_stage"] = PATHS["picture"]["current"] + "\\stage_ready_check"
PATHS["picture"]["map"] = PATHS["picture"]["current"] + "\\map"
PATHS["picture"]["item"] = PATHS["picture"]["current"] + "\\item"
PATHS["picture"]["error"] = PATHS["picture"]["current"] + "\\error"

if __name__ == '__main__':
    print(PATHS)
