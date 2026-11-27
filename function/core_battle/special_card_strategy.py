from pulp import *

from function.globals.log import CUS_LOGGER

# 为简化函数的调用，将策略添加到全局中
STRATEGIES = {}
STRATEGIES_2 = {}
COPY_STRATEGY = {}
COPY_STRATEGY_2 = {}

STRATEGIES_OB = {}
STRATEGIES_2_OB = {}
COPY_STRATEGY_OB = {}
COPY_STRATEGY_2_OB = {}


def generate_coverage(strategy_id):
    """
    根据策略ID生成覆盖区域。
    :param strategy_id: 策略的类型ID
    :return: 覆盖区域的坐标偏移列表
    """
    if strategy_id == 1:
        return [(i, j) for i in range(-1, 2) for j in range(-1, 2)]  # 3x3
    elif strategy_id == 2:
        return [(i, j) for i in range(-2, 2) for j in range(-1, 2)]  # 4x3
    elif strategy_id == 3:
        return [(i, j) for i in range(-2, 3) for j in range(-2, 3)]  # 5x5
    elif strategy_id == 4:
        return [(0, j) for j in range(-6, 7)]  # 全列覆盖
    elif strategy_id == 5:
        return [(i, 0) for i in range(-8, 9)]  # 全行覆盖
    elif strategy_id == 6:
        return [(0, 0), (0, 1), (0, -1), (1, 0), (-1, 0)]  # 小十字
    elif strategy_id == 7:
        return [(i, j) for j in range(-1, 2) for i in range(-8, 9)]  # 三行覆盖
    elif strategy_id == 10:
        return [(i, j) for i in range(0, 3) for j in range(-1, 2)]  # 3x3预判
    elif strategy_id == 15:
        return [(i, j) for i in range(-6, 7) for j in range(-8, 9)]  # 全屏
    else:
        # 示例调用
        raise ValueError("未知的策略ID")


def generate_cross_coverage(rows, cols):
    """
    根据给定的行数和列数生成十字覆盖范围。
    :param rows: 十字的行数
    :param cols: 十字的列数
    :return: 覆盖区域的坐标偏移列表
    """
    coverage = []
    # 纵向覆盖
    for i in range(-rows, rows + 1):
        coverage.append((i, 0))
    # 横向覆盖
    for j in range(-cols, cols + 1):
        coverage.append((0, j))
    return coverage


def generate_extra_coverage(strategy_id, extra):
    if strategy_id == 12:
        half_size = extra // 2
        return [(i, j) for i in range(-half_size, half_size + 1) for j in range(-half_size, half_size + 1)]  # 3x3或5x5

    elif strategy_id == 13:
        if extra < 3:
            return ([(i, j) for i in range(-2, 2) for j in range(-1, 2)] +
                    [(i, 0) for i in range(-8, 9)])
        else:
            return ([(i, j) for i in range(-2, 2) for j in range(-1, 2)] +
                    [(i, 0) for i in range(-8, 9)] +
                    [(0, j) for j in range(-6, 7)])


def generate_row_col_coverage(row, col):
    half_row = row // 2
    half_col = col // 2
    return [(i, j) for i in range(-half_col, half_col + 1) for j in range(-half_row, half_row + 1)]  # row行col列


def add_strategy(player, strategy_id, card, cost=0, rows=None, cols=None, extra=None):
    """
    添加策略到策略字典中，并动态生成唯一的策略ID和覆盖范围
    :param player:
    :param strategy_id: 策略的类型ID
    :param cost: 策略的成本
    :param card:
    :param rows: 十字的行数（仅用于十字策略）
    :param cols: 十字的列数（仅用于十字策略）
    :param extra:
    """

    # 根据策略类型ID生成覆盖范围
    if strategy_id == 8:  # 如果是十字策略
        coverage = generate_cross_coverage(rows, cols)
    elif strategy_id == 9:  # 复制对策，没有预定义覆盖范围
        coverage = []
    elif strategy_id == 12 or strategy_id == 13:
        coverage = generate_extra_coverage(strategy_id, extra)
    else:
        coverage = generate_coverage(strategy_id)

    # 添加策略到字典，使用唯一ID
    if player == 1:
        if strategy_id == 9:
            COPY_STRATEGY[card] = {"coverage": coverage, "cost": cost}
        else:
            STRATEGIES[card] = {"coverage": coverage, "cost": cost}
    elif player == 2:
        if strategy_id == 9:
            COPY_STRATEGY_2[card] = {"coverage": coverage, "cost": cost}
        else:
            STRATEGIES_2[card] = {"coverage": coverage, "cost": cost}


def add_strategy_ob(player, strategy_id, card, extra1=None, extra2=None):
    """
    添加清障策略到策略字典中并动态生成覆盖范围
    :param player:
    :param strategy_id: 策略的类型ID
    :param card:
    :param extra1:
    :param extra2:
    """

    # 根据策略类型ID生成覆盖范围
    if strategy_id == 18:
        coverage = generate_row_col_coverage(extra1, extra2)
    elif strategy_id == 9:  # 复制对策，没有预定义覆盖范围
        coverage = []
    else:
        coverage = generate_coverage(strategy_id)

    # 添加策略到字典，使用唯一ID
    if player == 1:
        if strategy_id == 9:
            COPY_STRATEGY_OB[card] = {"coverage": coverage}
        else:
            STRATEGIES_OB[card] = {"coverage": coverage}
    elif player == 2:
        if strategy_id == 9:
            COPY_STRATEGY_2_OB[card] = {"coverage": coverage}
        else:
            STRATEGIES_2_OB[card] = {"coverage": coverage}


def solve_special_card_problem(points_to_cover, obstacles, card_list_can_use):
    """
    :param points_to_cover:
    :param obstacles:
    :param card_list_can_use:
    :return:
    """

    # 定义问题
    prob = LpProblem("Map Coverage Problem", LpMinimize)
    print(points_to_cover, obstacles, card_list_can_use)

    # 定义常量
    MAP_WIDTH = 9
    MAP_HEIGHT = 7

    # 定义策略字典
    global STRATEGIES
    global STRATEGIES_2
    STRATEGIES = {}
    STRATEGIES_2 = {}

    # 定义复制策略字典
    global COPY_STRATEGY
    global COPY_STRATEGY_2
    COPY_STRATEGY = {}
    COPY_STRATEGY_2 = {}

    # 添加策略
    for i in range(1, 3):  # 遍历可用列表添加策略
        for card in card_list_can_use[i]:
            if card.card_type == 8:
                add_strategy(i, 8, cost=card.energy, rows=card.rows, cols=card.cols, card=card)
            elif card.card_type == 12 or card.card_type == 13:
                add_strategy(i, card.card_type, cost=card.energy, extra=card.cols, card=card)
            else:
                add_strategy(i, card.card_type, cost=card.energy, card=card)

    # 创建决策变量
    x = LpVariable.dicts(
        name="strategy",
        indices=[(i, j, s)
                 for i in range(1, MAP_WIDTH + 1)
                 for j in range(1, MAP_HEIGHT + 1)
                 for s in STRATEGIES.keys()],
        cat='Binary')
    # 创建复制对策变量
    y = LpVariable.dicts(
        name="copy_strategy",
        indices=[(i, j, s, c)
                 for i in range(1, MAP_WIDTH + 1)
                 for j in range(1, MAP_HEIGHT + 1)
                 for s in STRATEGIES.keys()
                 for c in COPY_STRATEGY.keys()],
        cat='Binary')
    z = LpVariable.dicts(
        name="strategy2",
        indices=[(i, j, s)
                 for i in range(1, MAP_WIDTH + 1)
                 for j in range(1, MAP_HEIGHT + 1)
                 for s in STRATEGIES_2.keys()],
        cat='Binary')

    # 创建复制对策变量
    w = LpVariable.dicts(
        name="copy_strategy",
        indices=[(i, j, s, c) for i in range(1, MAP_WIDTH + 1)
                 for j in range(1, MAP_HEIGHT + 1)
                 for s in STRATEGIES_2.keys()
                 for c in COPY_STRATEGY_2.keys()],
        cat='Binary')

    # 目标函数
    prob += (
            lpSum([STRATEGIES[s]["cost"] * x[i, j, s]
                   for i in range(1, MAP_WIDTH + 1)
                   for j in range(1, MAP_HEIGHT + 1)
                   for s in STRATEGIES.keys()]) +
            lpSum([COPY_STRATEGY[c]["cost"] * y[i, j, s, c]
                   for i in range(1, MAP_WIDTH + 1)
                   for j in range(1, MAP_HEIGHT + 1)
                   for s in STRATEGIES.keys()
                   for c in COPY_STRATEGY.keys()]) +
            lpSum([STRATEGIES_2[s]["cost"] * z[i, j, s]
                   for i in range(1, MAP_WIDTH + 1)
                   for j in range(1, MAP_HEIGHT + 1)
                   for s in STRATEGIES_2.keys()]) +
            lpSum([COPY_STRATEGY_2[c]["cost"] * w[i, j, s, c]
                   for i in range(1, MAP_WIDTH + 1)
                   for j in range(1, MAP_HEIGHT + 1)
                   for s in STRATEGIES_2.keys()
                   for c in COPY_STRATEGY_2.keys()]))
    # 约束条件
    # 1. 每个待处理点位至少被覆盖一次
    for point in points_to_cover:
        i, j = map(int, point.split('-'))
        prob += (
                lpSum([x[i_s, j_s, s]
                       for i_s in range(1, MAP_WIDTH + 1)
                       for j_s in range(1, MAP_HEIGHT + 1)
                       for s in STRATEGIES.keys()
                       if (i - i_s, j - j_s) in STRATEGIES[s]["coverage"]]) +
                lpSum([y[i_s, j_s, s, c]
                       for i_s in range(1, MAP_WIDTH + 1)
                       for j_s in range(1, MAP_HEIGHT + 1)
                       for s in STRATEGIES.keys()
                       for c in COPY_STRATEGY.keys()
                       if (i - i_s, j - j_s) in STRATEGIES[s]["coverage"]]) +
                lpSum([z[i_s, j_s, s]
                       for i_s in range(1, MAP_WIDTH + 1)
                       for j_s in range(1, MAP_HEIGHT + 1)
                       for s in STRATEGIES_2.keys()
                       if (i - i_s, j - j_s) in STRATEGIES_2[s]["coverage"]]) +
                lpSum([w[i_s, j_s, s, c]
                       for i_s in range(1, MAP_WIDTH + 1)
                       for j_s in range(1, MAP_HEIGHT + 1)
                       for s in STRATEGIES_2.keys()
                       for c in COPY_STRATEGY_2.keys()
                       if (i - i_s, j - j_s) in STRATEGIES_2[s]["coverage"]]) >= 1)

    # 2. 不能在障碍上放置对策
    for obstacle in obstacles:
        i, j = map(int, obstacle.split('-'))
        for s in STRATEGIES.keys():
            prob += x[i, j, s] == 0
            for c in COPY_STRATEGY.keys():
                prob += y[i, j, s, c] == 0
        for s in STRATEGIES_2.keys():
            prob += z[i, j, s] == 0
            for c in COPY_STRATEGY_2.keys():
                prob += w[i, j, s, c] == 0

    # 3. 每个策略只能被放置一次
    for s in STRATEGIES.keys():
        prob += lpSum([x[i, j, s]
                       for i in range(1, MAP_WIDTH + 1)
                       for j in range(1, MAP_HEIGHT + 1)]) <= 1
    for s in STRATEGIES_2.keys():
        prob += lpSum([z[i, j, s]
                       for i in range(1, MAP_WIDTH + 1)
                       for j in range(1, MAP_HEIGHT + 1)]) <= 1

    # 4. 每个复制对策只能被放置一次
    for s in STRATEGIES.keys():
        for c in COPY_STRATEGY.keys():
            prob += lpSum([y[i, j, s, c]
                           for i in range(1, MAP_WIDTH + 1)
                           for j in range(1, MAP_HEIGHT + 1)]) <= 1
    for s in STRATEGIES_2.keys():
        for c in COPY_STRATEGY_2.keys():
            prob += lpSum([w[i, j, s, c]
                           for i in range(1, MAP_WIDTH + 1)
                           for j in range(1, MAP_HEIGHT + 1)]) <= 1

    # 约束条件：如果复制对策被放置，则对应的原始对策必须被放置至少一次
    for c in COPY_STRATEGY.keys():

        # 对于每一个复制策略c，检查其对应的所有原始策略s
        for s in STRATEGIES.keys():
            # 确保原始策略s至少在地图上的一个位置被放置
            prob += (lpSum([x[i, j, s]
                            for i in range(1, MAP_WIDTH + 1)
                            for j in range(1, MAP_HEIGHT + 1)]) >=
                     lpSum([y[i, j, s, c]
                            for i in range(1, MAP_WIDTH + 1)
                            for j in range(1, MAP_HEIGHT + 1)]))

    for c in COPY_STRATEGY_2.keys():

        # 对于每一个复制策略c，检查其对应的所有原始策略
        for s in STRATEGIES_2.keys():
            # 确保原始策略s至少在地图上的一个位置被放置
            prob += (lpSum([z[i, j, s]
                            for i in range(1, MAP_WIDTH + 1)
                            for j in range(1, MAP_HEIGHT + 1)]) >=
                     lpSum([w[i, j, s, c]
                            for i in range(1, MAP_WIDTH + 1)
                            for j in range(1, MAP_HEIGHT + 1)]))
    # 求解问题
    prob.solve()
    # 输出结果
    print("Status:", LpStatus[prob.status])
    if LpStatus[prob.status] == "Optimal":  # 有解
        CUS_LOGGER.debug(f"火苗成本 ={value(prob.objective)}")
        strategy1 = {}
        strategy2 = {}

        for i in range(1, MAP_WIDTH + 1):

            for j in range(1, MAP_HEIGHT + 1):

                for s in STRATEGIES.keys():
                    if value(x[i, j, s]) == 1:
                        strategy1[s] = [i, j]
                        CUS_LOGGER.debug(f"1p对策卡 {s.name} 放置于 ({i},{j})")
                    for c in COPY_STRATEGY.keys():
                        if value(y[i, j, s, c]) == 1:
                            strategy1[c] = [i, j]
                            CUS_LOGGER.debug(f"1p复制类对策卡 {c.name} 复制了对策卡 {s.name} 放置于 ({i},{j})")

                for s in STRATEGIES_2.keys():
                    if value(z[i, j, s]) == 1:
                        strategy2[s] = [i, j]
                        CUS_LOGGER.debug(f"2p对策卡 {s.name} 放置于 ({i},{j})")
                    for c in COPY_STRATEGY_2.keys():
                        if value(w[i, j, s, c]) == 1:
                            strategy2[c] = [i, j]
                            CUS_LOGGER.debug(f"2p复制类对策卡 {c.name} 复制了对策卡 {s.name} 放置于 ({i},{j})")

        return strategy1, strategy2
    else:
        return None


# # 定义待处理点位列表
# points_to_cover = ["9-5", "3-2", "9-2", "1-1"]  # 添加所有待处理点位
# # 定义障碍列表
# obstacles = ["1-1", "2-3", "9-6"]  # 添加所有障碍点位
# solve_special_card_problem(points_to_cover, obstacles)


def solve_maximize_score_problem(obstacles, score_matrix, card_list_can_use, score_threshold=0):
    """
    解决最大化可消除障碍评分的问题
    :param obstacles: 固定障碍物列表，例如 ["1-1", "2-3"]
    :param score_matrix: 7x9的可消除障碍评分矩阵，表示每个位置的得分
    :param card_list_can_use: 可用卡牌列表
    :param score_threshold: 分数阈值，低于此值的位置视为0分
    :return: strategy1, strategy2 两个玩家的最佳策略
    """

    # 定义问题 - 最大化
    prob = LpProblem("Maximize_Score_Problem", LpMaximize)

    # 定义常量
    MAP_WIDTH = 9  # x坐标范围 1-9
    MAP_HEIGHT = 7  # y坐标范围 1-7
    CUS_LOGGER.debug(f"开始处理地图{score_matrix}")
    # 处理评分矩阵，应用阈值
    processed_score_matrix = []
    for row in score_matrix:
        processed_row = []
        for score in row:
            if score < score_threshold:
                processed_row.append(0)
            else:
                processed_row.append(score)
        processed_score_matrix.append(processed_row)

    # 更新障碍物列表，将非零评分位置也加入障碍物
    enhanced_obstacles = set(obstacles)  # 原始障碍物
    for j in range(MAP_HEIGHT):
        for i in range(MAP_WIDTH):
            if processed_score_matrix[j][i] > 0:
                enhanced_obstacles.add(f"{i + 1}-{j + 1}")  # 转换为1基索引并添加到障碍物列表

    # 定义策略字典
    global STRATEGIES_OB
    global STRATEGIES_2_OB
    STRATEGIES_OB = {}
    STRATEGIES_2_OB = {}

    # 定义复制策略字典
    global COPY_STRATEGY_OB
    global COPY_STRATEGY_2_OB
    COPY_STRATEGY_OB = {}
    COPY_STRATEGY_2_OB = {}

    # 添加策略
    for i in range(1, 3):  # 遍历可用列表添加策略
        for card in card_list_can_use[i]:
            if card.card_type == 18:
                add_strategy_ob(i, card.card_type, extra1=card.rows, extra2=card.cols, card=card)
            else:  # 全屏清障卡
                add_strategy_ob(i, 15, card=card)

    # 创建决策变量
    x = LpVariable.dicts(
        name="strategy",
        indices=[(i, j, s)
                 for i in range(1, MAP_WIDTH + 1)
                 for j in range(1, MAP_HEIGHT + 1)
                 for s in STRATEGIES_OB.keys()],
        cat='Binary')
    # 创建复制对策变量
    y = LpVariable.dicts(
        name="copy_strategy",
        indices=[(i, j, s, c)
                 for i in range(1, MAP_WIDTH + 1)
                 for j in range(1, MAP_HEIGHT + 1)
                 for s in STRATEGIES_OB.keys()
                 for c in COPY_STRATEGY_OB.keys()],
        cat='Binary')
    z = LpVariable.dicts(
        name="strategy2",
        indices=[(i, j, s)
                 for i in range(1, MAP_WIDTH + 1)
                 for j in range(1, MAP_HEIGHT + 1)
                 for s in STRATEGIES_2_OB.keys()],
        cat='Binary')

    # 创建复制对策变量
    w = LpVariable.dicts(
        name="copy_strategy2",
        indices=[(i, j, s, c) for i in range(1, MAP_WIDTH + 1)
                 for j in range(1, MAP_HEIGHT + 1)
                 for s in STRATEGIES_2_OB.keys()
                 for c in COPY_STRATEGY_2_OB.keys()],
        cat='Binary')

    # 创建辅助变量，表示每个位置是否被覆盖
    covered = LpVariable.dicts(
        name="covered",
        indices=[(i, j)
                 for i in range(1, MAP_WIDTH + 1)
                 for j in range(1, MAP_HEIGHT + 1)],
        cat='Binary')

    # 目标函数 - 最大化被覆盖位置的总得分（每个位置只计算一次）
    prob += lpSum([processed_score_matrix[j - 1][i - 1] * covered[i, j]
                   for i in range(1, MAP_WIDTH + 1)
                   for j in range(1, MAP_HEIGHT + 1)])

    # 约束条件
    # 1. 不能在障碍上放置对策（包括评分大于0的位置）
    for obstacle in enhanced_obstacles:
        i, j = map(int, obstacle.split('-'))
        for s in STRATEGIES_OB.keys():
            prob += x[i, j, s] == 0
            for c in COPY_STRATEGY_OB.keys():
                prob += y[i, j, s, c] == 0
        for s in STRATEGIES_2_OB.keys():
            prob += z[i, j, s] == 0
            for c in COPY_STRATEGY_2_OB.keys():
                prob += w[i, j, s, c] == 0

    # 2. 每个策略只能被放置一次
    for s in STRATEGIES_OB.keys():
        prob += lpSum([x[i, j, s]
                       for i in range(1, MAP_WIDTH + 1)
                       for j in range(1, MAP_HEIGHT + 1)]) <= 1
    for s in STRATEGIES_2_OB.keys():
        prob += lpSum([z[i, j, s]
                       for i in range(1, MAP_WIDTH + 1)
                       for j in range(1, MAP_HEIGHT + 1)]) <= 1

    # 3. 每个复制对策只能被放置一次
    for s in STRATEGIES_OB.keys():
        for c in COPY_STRATEGY_OB.keys():
            prob += lpSum([y[i, j, s, c]
                           for i in range(1, MAP_WIDTH + 1)
                           for j in range(1, MAP_HEIGHT + 1)]) <= 1
    for s in STRATEGIES_2_OB.keys():
        for c in COPY_STRATEGY_2_OB.keys():
            prob += lpSum([w[i, j, s, c]
                           for i in range(1, MAP_WIDTH + 1)
                           for j in range(1, MAP_HEIGHT + 1)]) <= 1

    # 4. 约束条件：如果复制对策被放置，则对应的原始对策必须被放置至少一次
    for c in COPY_STRATEGY_OB.keys():
        # 对于每一个复制策略c，检查其对应的所有原始策略s
        for s in STRATEGIES_OB.keys():
            # 确保原始策略s至少在地图上的一个位置被放置
            prob += (lpSum([x[i, j, s]
                            for i in range(1, MAP_WIDTH + 1)
                            for j in range(1, MAP_HEIGHT + 1)]) >=
                     lpSum([y[i, j, s, c]
                            for i in range(1, MAP_WIDTH + 1)
                            for j in range(1, MAP_HEIGHT + 1)]))

    for c in COPY_STRATEGY_2_OB.keys():
        # 对于每一个复制策略c，检查其对应的所有原始策略
        for s in STRATEGIES_2_OB.keys():
            # 确保原始策略s至少在地图上的一个位置被放置
            prob += (lpSum([z[i, j, s]
                            for i in range(1, MAP_WIDTH + 1)
                            for j in range(1, MAP_HEIGHT + 1)]) >=
                     lpSum([w[i, j, s, c]
                            for i in range(1, MAP_WIDTH + 1)
                            for j in range(1, MAP_HEIGHT + 1)]))

    # 5. 覆盖约束：如果某个位置被任何策略覆盖，则covered变量为1
    for i in range(1, MAP_WIDTH + 1):
        for j in range(1, MAP_HEIGHT + 1):
            # 收集所有可能覆盖位置(i,j)的策略
            cover_constraints = []

            # 玩家1的标准策略
            for s in STRATEGIES_OB.keys():
                for offset_i, offset_j in STRATEGIES_OB[s]["coverage"]:
                    # 检查是否有策略在(i-offset_i, j-offset_j)位置放置可以覆盖(i,j)
                    place_i, place_j = i - offset_i, j - offset_j
                    if 1 <= place_i <= MAP_WIDTH and 1 <= place_j <= MAP_HEIGHT:
                        cover_constraints.append(x[place_i, place_j, s])

            # 玩家1的复制策略
            for s in STRATEGIES_OB.keys():
                for c in COPY_STRATEGY_OB.keys():
                    for offset_i, offset_j in STRATEGIES_OB[s]["coverage"]:
                        place_i, place_j = i - offset_i, j - offset_j
                        if 1 <= place_i <= MAP_WIDTH and 1 <= place_j <= MAP_HEIGHT:
                            cover_constraints.append(y[place_i, place_j, s, c])

            # 玩家2的标准策略
            for s in STRATEGIES_2_OB.keys():
                for offset_i, offset_j in STRATEGIES_2_OB[s]["coverage"]:
                    place_i, place_j = i - offset_i, j - offset_j
                    if 1 <= place_i <= MAP_WIDTH and 1 <= place_j <= MAP_HEIGHT:
                        cover_constraints.append(z[place_i, place_j, s])

            # 玩家2的复制策略
            for s in STRATEGIES_2_OB.keys():
                for c in COPY_STRATEGY_2_OB.keys():
                    for offset_i, offset_j in STRATEGIES_2_OB[s]["coverage"]:
                        place_i, place_j = i - offset_i, j - offset_j
                        if 1 <= place_i <= MAP_WIDTH and 1 <= place_j <= MAP_HEIGHT:
                            cover_constraints.append(w[place_i, place_j, s, c])

            # 约束：如果任何策略覆盖了位置(i,j)，则covered[i,j]必须为1
            if cover_constraints:
                prob += covered[i, j] <= lpSum(cover_constraints)
                # 另一个方向的约束：如果covered[i,j]为1，则至少有一个策略覆盖它
                prob += covered[i, j] >= lpSum(cover_constraints) / len(cover_constraints) if cover_constraints else 0
            else:
                prob += covered[i, j] == 0

    # 求解问题
    prob.solve(PULP_CBC_CMD(msg=0))  # 禁止输出求解过程信息

    # 输出结果
    CUS_LOGGER.debug(f"Status: {LpStatus[prob.status]}")
    if LpStatus[prob.status] == "Optimal":  # 有解
        CUS_LOGGER.debug(f"最大得分为 = {value(prob.objective)}")
        strategy1 = {}
        strategy2 = {}

        # 计算每个策略产生的有效得分
        strategy1_scores = {}
        strategy2_scores = {}

        # 构建位置到分数的映射，用于计算每个策略的得分
        position_scores = {}
        for j in range(MAP_HEIGHT):
            for i in range(MAP_WIDTH):
                position_scores[(i + 1, j + 1)] = processed_score_matrix[j][i]

        for i in range(1, MAP_WIDTH + 1):
            for j in range(1, MAP_HEIGHT + 1):
                for s in STRATEGIES_OB.keys():
                    if value(x[i, j, s]) == 1:
                        strategy1[s] = [i, j]
                        # 计算该策略产生的得分
                        score = 0
                        covered_positions = set()
                        for offset_i, offset_j in STRATEGIES_OB[s]["coverage"]:
                            pos_i, pos_j = i + offset_i, j + offset_j
                            if 1 <= pos_i <= MAP_WIDTH and 1 <= pos_j <= MAP_HEIGHT:
                                # 检查这个位置是否是可得分位置（不在原始障碍物中，且得分大于0）
                                if f"{pos_i}-{pos_j}" not in obstacles and position_scores.get((pos_i, pos_j), 0) > 0:
                                    # 检查这个位置是否已经被其他卡牌覆盖
                                    if (pos_i, pos_j) not in covered_positions:
                                        score += position_scores.get((pos_i, pos_j), 0)
                                        covered_positions.add((pos_i, pos_j))
                        strategy1_scores[s] = score
                        CUS_LOGGER.debug(f"1p对策卡 {s.name} 放置于 ({i},{j})，产生有效得分: {score}")
                    for c in COPY_STRATEGY_OB.keys():
                        if value(y[i, j, s, c]) == 1:
                            strategy1[c] = [i, j]
                            # 计算该策略产生的得分
                            score = 0
                            covered_positions = set()
                            for offset_i, offset_j in STRATEGIES_OB[s]["coverage"]:
                                pos_i, pos_j = i + offset_i, j + offset_j
                                if 1 <= pos_i <= MAP_WIDTH and 1 <= pos_j <= MAP_HEIGHT:
                                    # 检查这个位置是否是可得分位置（不在原始障碍物中，且得分大于0）
                                    if f"{pos_i}-{pos_j}" not in obstacles and position_scores.get((pos_i, pos_j),
                                                                                                   0) > 0:
                                        # 检查这个位置是否已经被其他卡牌覆盖
                                        if (pos_i, pos_j) not in covered_positions:
                                            score += position_scores.get((pos_i, pos_j), 0)
                                            covered_positions.add((pos_i, pos_j))
                            strategy1_scores[c] = score
                            CUS_LOGGER.debug(
                                f"1p复制类对策卡 {c.name} 复制了对策卡 {s.name} 放置于 ({i},{j})，产生有效得分: {score}")

                for s in STRATEGIES_2_OB.keys():
                    if value(z[i, j, s]) == 1:
                        strategy2[s] = [i, j]
                        # 计算该策略产生的得分
                        score = 0
                        covered_positions = set()
                        for offset_i, offset_j in STRATEGIES_2_OB[s]["coverage"]:
                            pos_i, pos_j = i + offset_i, j + offset_j
                            if 1 <= pos_i <= MAP_WIDTH and 1 <= pos_j <= MAP_HEIGHT:
                                # 检查这个位置是否是可得分位置（不在原始障碍物中，且得分大于0）
                                if f"{pos_i}-{pos_j}" not in obstacles and position_scores.get((pos_i, pos_j), 0) > 0:
                                    # 检查这个位置是否已经被其他卡牌覆盖
                                    if (pos_i, pos_j) not in covered_positions:
                                        score += position_scores.get((pos_i, pos_j), 0)
                                        covered_positions.add((pos_i, pos_j))
                        strategy2_scores[s] = score
                        CUS_LOGGER.debug(f"2p对策卡 {s.name} 放置于 ({i},{j})，产生有效得分: {score}")
                    for c in COPY_STRATEGY_2_OB.keys():
                        if value(w[i, j, s, c]) == 1:
                            strategy2[c] = [i, j]
                            # 计算该策略产生的得分
                            score = 0
                            covered_positions = set()
                            for offset_i, offset_j in STRATEGIES_2_OB[s]["coverage"]:
                                pos_i, pos_j = i + offset_i, j + offset_j
                                if 1 <= pos_i <= MAP_WIDTH and 1 <= pos_j <= MAP_HEIGHT:
                                    # 检查这个位置是否是可得分位置（不在原始障碍物中，且得分大于0）
                                    if f"{pos_i}-{pos_j}" not in obstacles and position_scores.get((pos_i, pos_j),
                                                                                                   0) > 0:
                                        # 检查这个位置是否已经被其他卡牌覆盖
                                        if (pos_i, pos_j) not in covered_positions:
                                            score += position_scores.get((pos_i, pos_j), 0)
                                            covered_positions.add((pos_i, pos_j))
                            strategy2_scores[c] = score
                            CUS_LOGGER.debug(
                                f"2p复制类对策卡 {c.name} 复制了对策卡 {s.name} 放置于 ({i},{j})，产生有效得分: {score}")

        return strategy1, strategy2, strategy1_scores, strategy2_scores
    else:
        return None
