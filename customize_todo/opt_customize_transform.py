import csv
import json
from pprint import pprint

from function.script.scattered.read_json_to_stage_info import read_json_to_stage_info

csvFilePath = "csv_美食大赛.csv"
jsonFilePath = "1 - 231221-240118 大赛.json"

my_list = []

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
    "麦芽糖"
]

with open(csvFilePath, "r", encoding='utf-8') as csv_file:
    # 读取文本为有序字典
    csv_reader = csv.DictReader(csv_file)
    for rows in csv_reader:
        # 将有序字典转为无序字典
        info = json.loads(json.dumps(rows))
        # 添加到数据中
        my_list.append(info)

for my_dict in my_list:
    my_dict.pop("产火数")

    my_dict["battle_id"] = int(my_dict.pop("任务序号"))

    my_dict["stage_id"] = my_dict.pop("地图编号")
    my_dict["max_times"] = 1
    my_dict["deck"] = 1

    my_dict["player"] = my_dict.pop("是否组队")
    if my_dict["player"] == "True":
        my_dict["player"] = [2,1]
    else:
        my_dict["player"] = [1]

    my_dict["battle_plan_1p"] = 0
    my_dict["battle_plan_2p"] = 1

    my_dict["quest_card"] = my_dict.pop("使用卡片")

    """ban卡"""
    my_dict["list_ban_card"] = my_dict.pop("不使用卡片")
    my_dict["list_ban_card"] = my_dict["list_ban_card"].split(",")
    # 去list的空值
    if "" in my_dict["list_ban_card"]:
        my_dict["list_ban_card"].remove("")
    # 根据数量限制 地图所需的承载卡 优先级 综合规划 增加ban卡
    if not (my_dict["数量限制"] == "0" or my_dict["数量限制"] == ""):
        # 先把已经ban了的 从卡组中 去掉
        for already_ban in my_dict["list_ban_card"]:
            if already_ban in default_deck:
                default_deck.remove(already_ban)
        # 根据地图所需的承载卡, 重新排序
        mat_card_opt = read_json_to_stage_info(stage_id=my_dict["stage_id"])["mat_card"]
        if mat_card_opt == 1:
            default_deck.remove("木盘子")
            default_deck.insert(0, "木盘子")
        elif mat_card_opt == 2:
            default_deck.remove("麦芽糖")
            default_deck.insert(0, "麦芽糖")
        # 在属于的卡中, 选出后几位ban掉, 多ban一张, 因为咖啡粉在第12个格子不好ban
        for j in default_deck[int(my_dict["数量限制"]) - 1:]:
            my_dict["list_ban_card"].append(j)
    my_dict.pop("数量限制")

    my_dict["dict_exit"] = {
        "other_time_player_a": [],
        "other_time_player_b": [],
        "last_time_player_a": ["美食大赛领取"],
        "last_time_player_b": ["美食大赛领取"]
    }

pprint(my_list)

with open(jsonFilePath, "w", encoding='utf-8') as json_file:
    json_file.write(json.dumps(my_list, indent=4, ensure_ascii=False))
