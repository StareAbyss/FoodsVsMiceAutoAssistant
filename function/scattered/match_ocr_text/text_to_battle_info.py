import re

from function.scattered.extract_names_and_ids_from_json import extract_names_and_ids_from_json
from function.scattered.read_json_to_stage_info import *


def food_texts_to_battle_info(texts, self) -> list:
    """
    :param self:
    :param texts: 文本列表，每项代表文档中的一行。
    :return: 两字典列表，一个包含单人任务，另一个包含多人任务。
    """

    name_stage_info = extract_names_and_ids_from_json()
    quests = []

    for text in texts:
        # 初始化变量
        stage_id = None
        quest_card = None
        max_card_num = None
        player = [self.player] if "单人" in text else [2, 1]
        need_key = True
        ban_card_list = []

        # 提取stage_id
        for key, value in name_stage_info.items():
            # 例如 key 茴香竹筏-日 value NO-4-1
            if key in text:
                # 游戏内文本和json完全对应
                stage_id = value
                break
            if '-' in key:
                location, time = key.split('-')  # 地点-日/夜（水/陆）
                if (location in text) and (time in text):
                    # 游戏使用了 例如 茴香竹筏(日) 或 茴香竹筏（日） 也可以识别成功!
                    stage_id = value
                    break

        # 如果没有找到stage_id，跳过本次循环
        if stage_id is None:
            continue

        # 解析是否需要用钥匙 or 徽章
        # if "击杀" in text or "清除" in text or "评分" in text or "S" in text or "A" in text:
        #     need_key = True

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

        # 检查卡片限制，默认欢乐互娱不会出携带超过多少卡的任务（希望吧悲）
        if "超过" in text or "少于" in text:
            match = re.search(r'(超过|少于)(\d+)张', text)
            if match:
                limit_type, limit_number = match.groups()
                limit_number = int(limit_number)

                # 根据限制数目选择最后几张卡片进行禁用
                if limit_type == "超过":
                    max_card_num = limit_number
                elif limit_type == "少于":
                    # 对于“少于”情况，需要保留的卡片数量为limit_number-1
                    max_card_num = (limit_number - 1)

        # 将战斗信息字典添加到列表中
        quest_info = {
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
            "global_plan_active": True,  # 强制激活全局关卡方案
            "deck": 0,  # 不生效 占位符
            "battle_plan_1p": "00000000-0000-0000-0000-000000000000",  # 不生效 占位符
            "battle_plan_2p": "00000000-0000-0000-0000-000000000001",  # 不生效 占位符
            "quest_text": text,
        }

        if "不放置任何" in text or "同时存在不超过" in text:
            CUS_LOGGER.info("暂时无法完成 '进入战斗后X秒内不放置任何美食' 类任务, 跳过")
            quest_info["global_plan_active"] = False
            quest_info["deck"] = 0  # 自动带卡
            quest_info["battle_plan_1p"] = "00000000-0000-0000-0000-000000000002"  # 特殊方案
            quest_info["battle_plan_2p"] = "00000000-0000-0000-0000-000000000002"  # 特殊方案

        if "美食等级" in text:
            continue

        quests.append(quest_info)

    # 对 quest_list 按照 stage_id 进行排序
    quests.sort(key=lambda x: x["stage_id"])

    return quests
