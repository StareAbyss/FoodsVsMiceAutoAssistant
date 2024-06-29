import copy
import json
import time
from pprint import pprint

import numpy as np
import pandas as pd

from function.globals.extra import EXTRA_GLOBALS
from function.scattered.read_json_to_stage_info import read_json_to_stage_info


# 可能需要pip install openpyxl
# 该工具可能会需要一些额外的依赖项, 用于直接用excel生成cus_todo.json

def main():
    ImportFilePath = "be_transformed.xlsx"
    ExportFilePath = "from_transformer.json"

    default_deck = [
        "炭烧海星",
        "小火炉",
        "糖葫芦炮弹",
        "瓜皮护罩",
        "狮子座精灵",
        "油灯",
        "樱桃反弹布丁",
        "苏打气泡",
        "木盘子",
        "咖啡粉",
        "麦芽糖",
    ]

    # 读取 转化
    df = pd.read_excel(ImportFilePath)
    df = df.T
    data_dict = df.to_dict()
    data_list = [a_dict for a_dict in data_dict.values()]
    data_list_2 = []
    # 遍历每一行
    for excel_line in data_list:

        json_line = {
            # 默认参数
            "deck": 1,
            "max_times": 1,
            "battle_plan_1p": 0,
            "battle_plan_2p": 1,
            "dict_exit": {
                "other_time_player_a": [],
                "other_time_player_b": [],
                "last_time_player_a": ["回到上一级", "美食大赛领取"],
                "last_time_player_b": ["回到上一级", "美食大赛领取"]
            },
            # 直接读取参数
            "stage_id": copy.deepcopy(excel_line["地图编号"]),
            "battle_id": copy.deepcopy(int(excel_line["任务序号"])),
            "quest_card": copy.deepcopy(excel_line["使用卡片"]),
            "need_key": copy.deepcopy(excel_line["使用钥匙"])
        }

        # transformer value of group
        if excel_line["是否组队"]:
            json_line["player"] = [2, 1]
        else:
            json_line["player"] = [1]

        """ban卡"""
        ban_card_list_str = copy.deepcopy(excel_line["不使用卡片"])

        if type(ban_card_list_str) is float:
            # 值为float(即nan), 改为空List
            json_line["ban_card_list"] = []
        else:
            # 值为str(不为nan), 根据逗号, 切割成列表
            json_line["ban_card_list"] = ban_card_list_str.split(",")

        # 根据数量限制 地图所需的承载卡 优先级 综合规划 增加ban卡
        if not np.isnan(excel_line["数量限制"]):

            # 先把已经ban了的 从卡组中 去掉
            for already_ban in json_line["ban_card_list"]:
                if already_ban in default_deck:
                    default_deck.remove(already_ban)

            # 根据地图所需的承载卡, 重新排序
            mat_card_opt = read_json_to_stage_info(stage_id=json_line["stage_id"])["mat_card"]
            if mat_card_opt == 1:
                default_deck.remove("木盘子")
                default_deck.insert(0, "木盘子")
            elif mat_card_opt == 2:
                default_deck.remove("麦芽糖")
                default_deck.insert(0, "麦芽糖")
                default_deck.remove("咖啡粉")
                default_deck.insert(0, "咖啡粉")

            # 在属于的卡中, 选出后几位ban掉, 如果有任务卡额外加一张ban掉
            max_card_num = int(excel_line["数量限制"]) + 0 if json_line["quest_card"] == "None" else 1
            json_line["ban_card_list"] = default_deck[max_card_num:]

        data_list_2.append(json_line)

    pprint(data_list_2)

    # 将list 保存为 json 自旋锁读写, 防止多线程读写问题
    while EXTRA_GLOBALS.file_is_reading_or_writing:
        time.sleep(0.1)
    EXTRA_GLOBALS.file_is_reading_or_writing = True  # 文件被访问
    with open(file=ExportFilePath, mode="w", encoding='utf-8') as json_file:
        json_file.write(json.dumps(data_list_2, indent=4, ensure_ascii=False))
    EXTRA_GLOBALS.file_is_reading_or_writing = False  # 文件已解锁


if __name__ == '__main__':
    main()
