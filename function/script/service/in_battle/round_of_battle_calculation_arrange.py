"""计算卡片的部署方案相关的函数"""


def calculation_card_task(list_cell_all, task_card):
    """计算步骤一 加入任务卡的摆放坐标"""
    # 任务卡 大号小号开始位置不同 任务卡id = 0 则为没有
    locations = ["6-1", "6-2", "6-3", "6-4", "6-5", "6-6", "6-7"]
    if task_card != "None":
        # 遍历删除 主要卡中 占用了任务卡摆放的坐标
        new_list = []
        for card in list_cell_all:
            for location in card["location"]:
                if location in locations:
                    card["location"].remove(location)
            new_list.append(card)
        # 设定任务卡dict
        dict_task = {"id": 3 + len(new_list),
                     "name": task_card,
                     "ergodic": True,
                     "queue": True,
                     "location": locations}
        # 加入数组
        new_list.append(dict_task)
        return new_list
    else:
        return list_cell_all


def calculation_card_mat(list_cell_all, stage_info, player, is_group):
    """步骤二 2张承载卡"""
    # 预设中该关卡无垫子
    if stage_info["mat_card"] == 0:
        return list_cell_all

    # 分辨不同的垫子卡
    elif stage_info["mat_card"] == 1:
        # 木盘子会被毁 队列 + 遍历
        mat_name = "木盘子"
        ergodic = True
        queue = True
    else:
        # 麦芽糖坏不掉 所以只队列 不遍历
        mat_name = "麦芽糖"
        ergodic = False
        queue = True
    # 预设中该关卡有垫子 或采用了默认的没有垫子
    dict_mat = {"id": stage_info["mat_card"],
                "name": mat_name,
                "ergodic": ergodic,
                "queue": queue,
                "location": stage_info["mat_cell"]}
    # p1p2分别摆一半加入数组
    if is_group:
        if player == "1P":
            dict_mat["location"] = dict_mat["location"][::2]  # 奇数
        else:
            dict_mat["location"] = dict_mat["location"][1::2]  # 偶数
    list_cell_all.append(dict_mat)

    return list_cell_all


def calculation_card_ban(list_cell_all, list_ban_card):
    """步骤三 ban掉某些卡, 依据[卡组信息中的name字段] 和 ban卡信息中的字符串 是否重复"""
    list_new = []
    for i in list_cell_all:
        if not (i["name"] in list_ban_card):
            list_new.append(i)
    # 遍历更改删卡后的位置
    for card_new in list_new:
        cum_card_left = 0
        for ban_card in list_ban_card:
            for c_card in list_cell_all:
                if c_card["name"] == ban_card:
                    if card_new["id"] > c_card["id"]:
                        cum_card_left += 1
        card_new["id"] -= cum_card_left

    return list_new


def calculation_obstacle(list_cell_all, stage_info):
    """去除有障碍的位置的放卡"""
    # 预设中 该关卡有障碍物
    new_list_1 = []
    for i in list_cell_all:
        for location in i["location"]:
            if location in stage_info["obstacle"]:
                i["location"].remove(location)
        new_list_1.append(i)
    # 如果location被删完了 就去掉它
    new_list_2 = []
    for i in new_list_1:
        if i["location"]:
            new_list_2.append(i)
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


def calculation_one_card(option):
    """
    计算卡片部署方案
    Args:
        option: 部署参数
            example = {"begin": [int 开始点x, int 开始点y],"end": [int 结束点x, int 结束点y]}
    Returns: 卡片的部署方案字典 (输出后 多个该字典存入数组 进行循环)
        example = ["x-y","x-y","x-y",...]
    """
    my_list = []
    for i in range(option["begin"][0], option["end"][0] + 1):
        for j in range(option["begin"][1], option["end"][1] + 1):
            my_list.append(str(str(i) + "-" + str(j)))
    return my_list


def calculation_mat_card(cell_need_mat, cell_all_dict):
    """
    计算承载卡的部署方案 - 通过其他需要部署的卡 和此处option定义的区域的 [交集] 来计算
    Args:
        cell_need_mat: 需要垫子的部署位数组
        cell_all_dict: 其他所有卡片的部署方案字典
    Returns:
        承载卡的部署方案字典 同上
    """
    # 其他卡 部署位置
    cell_all_card = []
    for i in cell_all_dict:
        cell_all_card = cell_all_card + cell_all_dict[i]["location"]

    # 计算重复的部分
    cell_2 = []
    for i in cell_need_mat:
        for j in cell_all_card:
            if i == j:
                cell_2.append(i)
                break

    # 输出
    return cell_2


def calculation_cell_all_card(stage_info, battle_plan, player, is_group, task_card, list_ban_card):
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

    # 初始化数组 + 调用战斗卡
    list_cell_all = battle_plan

    # 调用计算任务卡
    list_cell_all = calculation_card_task(list_cell_all=list_cell_all, task_card=task_card)

    # 调用计算承载卡
    list_cell_all = calculation_card_mat(list_cell_all=list_cell_all, stage_info=stage_info, player=player,
                                         is_group=is_group)

    # 调用ban掉某些卡(不使用该卡)
    list_cell_all = calculation_card_ban(list_cell_all=list_cell_all, list_ban_card=list_ban_card)



    # 调用去掉障碍位置
    list_cell_all = calculation_obstacle(list_cell_all=list_cell_all, stage_info=stage_info)

    # 颠倒2P的放置顺序
    # list_cell_all = solve_alt_transformer(list_cell_all=list_cell_all, player=player)

    # 调用计算铲子卡
    list_shovel = calculation_shovel(stage_info=stage_info)
    return list_cell_all, list_shovel
