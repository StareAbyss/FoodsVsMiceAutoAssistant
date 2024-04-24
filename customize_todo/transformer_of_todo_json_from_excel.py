import json
from pprint import pprint

import numpy as np
import pandas as pd

from function.scattered.read_json_to_stage_info import read_json_to_stage_info


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

    # pprint(data_list)

    # 遍历每一行
    for a_dict in data_list:

        # 去除无用列
        a_dict.pop("产火数")
        a_dict.pop("评分要求")

        # 默认参数
        a_dict["deck"] = 1
        a_dict["is_use_key"] = True
        a_dict["max_times"] = 1
        a_dict["dict_exit"] = {
            "other_time_player_a": [],
            "other_time_player_b": [],
            "last_time_player_a": ["回到上一级", "美食大赛领取"],
            "last_time_player_b": ["回到上一级", "美食大赛领取"]
        }

        # 直接读取参数
        a_dict["stage_id"] = a_dict.pop("地图编号")
        a_dict["battle_id"] = int(a_dict.pop("任务序号"))
        a_dict["quest_card"] = a_dict.pop("使用卡片")

        # transformer value of group
        a_dict["player"] = a_dict.pop("是否组队")  # this type already is bool
        if a_dict["player"]:
            a_dict["player"] = [2, 1]
        else:
            a_dict["player"] = [1]

        a_dict["battle_plan_1p"] = 0
        a_dict["battle_plan_2p"] = 1

        """ban卡"""
        a_dict["list_ban_card"] = a_dict.pop("不使用卡片")

        if type(a_dict["list_ban_card"]) is float:
            # 值为float(即nan), 改为空List
            a_dict["list_ban_card"] = []
        else:
            # 值为str(不为nan), 根据逗号, 切割成列表
            a_dict["list_ban_card"] = a_dict["list_ban_card"].split(",")

        # 根据数量限制 地图所需的承载卡 优先级 综合规划 增加ban卡
        if not np.isnan(a_dict["数量限制"]):

            # 先把已经ban了的 从卡组中 去掉
            for already_ban in a_dict["list_ban_card"]:
                if already_ban in default_deck:
                    default_deck.remove(already_ban)

            # 根据地图所需的承载卡, 重新排序
            mat_card_opt = read_json_to_stage_info(stage_id=a_dict["stage_id"])["mat_card"]
            if mat_card_opt == 1:
                default_deck.remove("木盘子")
                default_deck.insert(0, "木盘子")
            elif mat_card_opt == 2:
                default_deck.remove("麦芽糖")
                default_deck.insert(0, "麦芽糖")
                default_deck.remove("咖啡粉")
                default_deck.insert(0, "咖啡粉")

            # 在属于的卡中, 选出后几位ban掉, 如果有任务卡额外加一张ban掉
            max_card_num = int(a_dict["数量限制"]) + 0 if a_dict["quest_card"] == "None" else 1
            a_dict["list_ban_card"] = default_deck[max_card_num:]

        # 卸磨杀驴数量限制列
        a_dict.pop("数量限制")

    pprint(data_list)

    # 将list 保存为 json
    with open(ExportFilePath, "w", encoding='utf-8') as json_file:
        json_file.write(json.dumps(data_list, indent=4, ensure_ascii=False))


if __name__ == '__main__':
    main()
