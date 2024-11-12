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
        "task_sequence": os.path.join(root, "task_sequence"),
        "logs": os.path.join(root, "logs"),
        # 资源文件
        "font": os.path.join(root, "resource", "font"),
        "logo": os.path.join(root, "resource", "logo"),
        "model": os.path.join(root, "resource", "model"),
        "theme": os.path.join(root, "resource", "theme"),
        "image": {
            "current": os.path.join(root, "resource", "image"),
            "common": os.path.join(root, "resource", "image", "common"),
            "number": os.path.join(root, "resource", "image", "number"),
            "card": os.path.join(root, "resource", "image", "card"),
            "stage": os.path.join(root, "resource", "image", "stage"),
            "quest_guild": os.path.join(root, "resource", "image", "quest_guild"),
            "quest_spouse": os.path.join(root, "resource", "image", "quest_spouse"),
            "quest_food": os.path.join(root, "resource", "image", "quest_food"),
            "ready_check_stage": os.path.join(root, "resource", "image", "stage_ready_check"),
            "map": os.path.join(root, "resource", "image", "map"),
            "item": os.path.join(root, "resource", "image", "item"),
            "error": os.path.join(root, "resource", "image", "error"),
        }
    }


# 定义为全局变量 几乎完全是静态导入 可以直接import该变量
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
        "\\logs\\chests_image",
        "\\logs\\loots_image",
        "\\logs\\match_failed",
        "\\logs\\match_failed\\loots",
        "\\logs\\match_failed\\texts_美食大赛\\blocks",
        "\\logs\\match_failed\\texts_美食大赛\\blocks_half",
        "\\logs\\match_failed\\texts_关卡名称\\blocks",
        "\\logs\\match_failed\\texts_关卡名称\\blocks_half",
        "\\logs\\result_json",
        "\\logs\\yolo_output",
        "\\logs\\yolo_output\\images",
        "\\logs\\yolo_output\\labels",
        "\\logs\\guild_manager",
        "\\logs\\guild_manager\\guild_member_images"
    ]
    for path in paths:
        ensure_directory_exists(PATHS["root"] + path)


# 创建所有缺失的目录
check_paths()

if __name__ == '__main__':
    print(PATHS)
