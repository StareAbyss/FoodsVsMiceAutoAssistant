"""计算卡片的部署方案相关的函数"""


def calculation_card_quest(list_cell_all, quest_card):
    """计算步骤一 加入任务卡的摆放坐标"""

    # 任务卡 大号小号开始位置不同 任务卡id = 0 则为没有
    locations = ["6-1", "6-2", "6-3", "6-4", "6-5", "6-6", "6-7"]

    if quest_card == "None":
        return list_cell_all

    else:

        # 遍历删除 主要卡中 占用了任务卡摆放的坐标
        new_list = []
        for card in list_cell_all:
            card["location"] = list(filter(lambda x: x not in locations, card["location"]))
            new_list.append(card)

        # 计算任务卡的id
        card_id_list = []
        for card in list_cell_all:
            card_id_list.append(card["id"])
        quest_card_id = max(card_id_list) + 1  # 取其中最大的卡片id + 1

        # 设定任务卡dict
        dict_quest = {
            "id": quest_card_id,
            "name": quest_card,
            "ergodic": True,
            "queue": True,
            "location": locations
        }

        # 加入数组
        new_list.append(dict_quest)
        return new_list


def calculation_card_mat(list_cell_all, stage_info, player, is_group):
    """步骤二 2张承载卡"""

    # 预设中该关卡无垫子
    if stage_info["mat_card"] == 0:
        return list_cell_all

    # 分辨不同的垫子卡
    dict_mat_1 = {"id": 1, "name": "木盘子", "ergodic": True, "queue": True, "location": []}
    dict_mat_2 = {"id": 2, "name": "麦芽糖", "ergodic": False, "queue": True, "location": []}
    location = stage_info["mat_cell"]

    # p1p2分别摆一半
    if is_group:
        if player == "1P":
            location = location[::2]  # 奇数
        else:
            location = location[1::2]  # 偶数

    if stage_info["mat_card"] == 1:
        dict_mat_1["location"] = location
    else:
        dict_mat_2["location"] = location

    # 加入数组 输出
    list_cell_all.append(dict_mat_1)
    list_cell_all.append(dict_mat_2)

    return list_cell_all


def calculation_card_ban(list_cell_all, list_ban_card):
    """步骤三 ban掉某些卡, 依据[卡组信息中的name字段] 和 ban卡信息中的字符串 是否重复"""

    list_new = []
    for card in list_cell_all:
        if not (card["name"] in list_ban_card):
            list_new.append(card)

    # 遍历更改删卡后的位置
    for card in list_new:
        cum_card_left = 0
        for ban_card in list_ban_card:
            for c_card in list_cell_all:
                if c_card["name"] == ban_card:
                    if card["id"] > c_card["id"]:
                        cum_card_left += 1
        card["id"] -= cum_card_left

    return list_new


def calculation_obstacle(list_cell_all, stage_info):
    """去除有障碍的位置的放卡"""

    # 预设中 该关卡有障碍物
    new_list_1 = []
    for card in list_cell_all:
        for location in card["location"]:
            if location in stage_info["obstacle"]:
                card["location"].remove(location)
        new_list_1.append(card)

    # 如果location被删完了 就去掉它
    new_list_2 = []
    for card in new_list_1:
        if card["location"]:
            new_list_2.append(card)
    return new_list_2


def calculation_alt_transformer(list_cell_all, player):
    """[非]1P, 队列模式, 就颠倒坐标数组, [非]队列模式代表着优先级很重要的卡片, 所以不颠倒"""
    if player == "2P":
        for i in range(len(list_cell_all)):
            if list_cell_all[i]["queue"]:
                list_cell_all[i]["location"] = list_cell_all[i]["location"][::-1]
    return list_cell_all


def calculation_shovel(stage_info):
    """铲子位置 """
    list_shovel = stage_info["shovel"]
    return list_shovel


def calculation_cell_all_card(stage_info, battle_plan, player, is_group, quest_card, list_ban_card):
    """
    计算所有卡片的部署方案
    Return:卡片的部署方案字典
        example = [
            {
                "id": int,
                "location": ["x-y","x-y","x-y",...]
            },
            ...
        ]
    """

    # 初始化数组 + 复制一份全新的 battle_plan
    list_cell_all = battle_plan

    # 调用计算任务卡
    list_cell_all = calculation_card_quest(
        list_cell_all=list_cell_all,
        quest_card=quest_card)

    # 调用计算承载卡
    list_cell_all = calculation_card_mat(
        list_cell_all=list_cell_all,
        stage_info=stage_info,
        player=player,
        is_group=is_group)

    # 调用ban掉某些卡(不使用该卡)
    list_cell_all = calculation_card_ban(
        list_cell_all=list_cell_all,
        list_ban_card=list_ban_card)

    # 调用去掉障碍位置
    list_cell_all = calculation_obstacle(
        list_cell_all=list_cell_all,
        stage_info=stage_info)

    # 颠倒2P的放置顺序

    # 调用计算铲子卡
    list_shovel = calculation_shovel(stage_info=stage_info)

    # 调试print
    # print("调试info: 你的战斗放卡opt如下")
    # print(list_cell_all)

    return list_cell_all, list_shovel
