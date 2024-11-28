import re

from function.scattered.extract_names_and_ids_from_json import extract_names_and_ids_from_json
from function.scattered.read_json_to_stage_info import *


def food_texts_to_battle_info(texts, self):
    """
    :param self:
    :param texts: 文本列表，每项代表文档中的一行。
    :return: 字典列表，字典包含从文本中提取的战斗信息。
    """
    default_deck = [
        "海星",
        "产火",
        "防空",
        "护罩",
        "对地",
        "照明",
        "布丁",
        "苏打气泡",
        "木盘子",
        "咖啡粉",
        "麦芽糖",
        "冰淇淋",
        "幻幻鸡",
        "创造神"
        "魔法软糖"
    ]

    name_stage_info = extract_names_and_ids_from_json()
    quest_list = []
    quest_card = "None"

    for text in texts:
        # 初始化变量
        stage_id = None
        player = [self.player] if "单人" in text else [2, 1]
        need_key = True
        ban_card_list = []

        # 提取stage_id
        for key, value in name_stage_info.items():
            if key in text:
                stage_id = value
                break
            if '-' in key:
                location, time = key.split('-')  # 地点-日/夜（水/陆）
                if (location in text) and ((time in key) and (time in text)):
                    stage_id = value
                    break

        # 如果没有找到stage_id，跳过本次循环
        if stage_id is None:
            continue

        # 检查特定卡片
        if "使用" in text:
            # 根据文本禁用卡片
            if "不" in text:
                # 提取卡片名称
                match = re.search(r'使用\s*(.*?)\s*(?=和|或|转|及|$)', text)
                if match:
                    card_name = match.group(1).strip()
                    ban_card_list.append(card_name)
            else:
                matches = re.findall(r'使用\s*(.*?)(?=或|$)', text)
                quest_card = [match.strip() for match in matches][0]
        else:
            quest_card = "None"

        # 检查卡片限制，默认欢乐互娱不会出携带超过多少卡的任务（希望吧悲）
        if "超过" in text or "少于" in text:
            match = re.search(r'(超过|少于)(\d+)张', text)
            if match:
                limit_type, limit_number = match.groups()
                limit_number = int(limit_number)

                # 移除已被禁用的卡片
                for already_ban in ban_card_list:
                    if already_ban in default_deck:
                        default_deck.remove(already_ban)

                # 根据地图要求重新排序卡组
                mat_card_opt = read_json_to_stage_info(stage_id=stage_id)["mat_card"]
                if "木盘子" in mat_card_opt:
                    default_deck.remove("木盘子")
                    default_deck.insert(0, "木盘子")
                if "麦芽糖" in mat_card_opt:
                    default_deck.remove("麦芽糖")
                    default_deck.insert(0, "麦芽糖")
                    default_deck.remove("咖啡粉")
                    default_deck.insert(0, "咖啡粉")

                # 根据限制数目选择最后几张卡片进行禁用
                if limit_type == "超过":
                    max_card_num = limit_number
                    ban_card_list.extend(default_deck[max_card_num:])
                elif limit_type == "少于":
                    # 对于“少于”情况，需要保留的卡片数量为limit_number-1
                    max_card_num = (limit_number - 1)
                    ban_card_list.extend(default_deck[max_card_num:])

        # 将战斗信息字典添加到列表中
        quest_list.append({
            "stage_id": stage_id,
            "player": player,
            "need_key": need_key,
            "max_times": 1,
            "dict_exit": {
                "other_time_player_a": [],
                "other_time_player_b": [],
                "last_time_player_a": ["竞技岛", "美食大赛领取"],
                "last_time_player_b": ["竞技岛", "美食大赛领取"]
            },

            "max_card_num": max_card_num,
            "quest_card": quest_card,
            "ban_card_list": ban_card_list,
            "deck": None,  # 外部输入 0-6
            "battle_plan_1p": None,  # 外部输入
            "battle_plan_2p": None,  # 外部输入
        })

    return quest_list
