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


def build_paths(root):
    # 定义一个辅助函数来构建路径
    return {
        "root": root,
        "battle_plan": os.path.join(root, "battle_plan"),
        "config": os.path.join(root, "config"),
        "customize_todo": os.path.join(root, "customize_todo"),
        "logs": os.path.join(root, "logs"),
        # 资源文件
        "font": os.path.join(root, "resource", "font"),
        "logo": os.path.join(root, "resource", "logo"),
        "picture": {
            "current": os.path.join(root, "resource", "picture"),
            "common": os.path.join(root, "resource", "picture", "common"),
            "number": os.path.join(root, "resource", "picture", "number"),
            "card": os.path.join(root, "resource", "picture", "card"),
            "stage": os.path.join(root, "resource", "picture", "stage"),
            "quest_guild": os.path.join(root, "resource", "picture", "quest_guild"),
            "quest_spouse": os.path.join(root, "resource", "picture", "quest_spouse"),
            "quest_food": os.path.join(root, "resource", "picture", "quest_food"),
            "ready_check_stage": os.path.join(root, "resource", "picture", "stage_ready_check"),
            "map": os.path.join(root, "resource", "picture", "map"),
            "item": os.path.join(root, "resource", "picture", "item"),
            "error": os.path.join(root, "resource", "picture", "error"),
        }
    }


# 定义为全局变量 一般以固定备份调用 可以直接import该变量
PATHS = build_paths(get_root_path())


def ensure_directory_exists(path):
    """检测路径是否存在"""

    # 检查路径是否存在
    if not os.path.exists(path):
        # 如果路径不存在，则创建它
        os.makedirs(path)
        print(f"路径不存在, 已创建: {path}")
    else:
        print(f"路径存在, 检测通过: {path}")


def check_paths():
    """检测所有路径是否存在"""
    paths = [
        "\\battle_plan_not_active",
        "\\logs",
        "\\logs\\chests_picture",
        "\\logs\\loots_picture",
        "\\logs\\match_failed",
        "\\logs\\match_failed\\loots",
        "\\logs\\match_failed\\texts",
        "\\logs\\result_json"
    ]
    for path in paths:
        ensure_directory_exists(PATHS["root"] + path)


# 创建所有缺失的目录
check_paths()

if __name__ == '__main__':
    print(PATHS)
