from pulp import *

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
        return [(i, j) for j in range(-1, 2)for i in range(-8, 9)]  # 三行覆盖
    else:
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

def add_strategy(strategies, strategy_id, cost, rows=None, cols=None):
    """
    添加策略到策略字典中，并动态生成唯一的策略ID和覆盖范围。

    :param strategies: 策略字典
    :param strategy_id: 策略的类型ID
    :param cost: 策略的成本
    :param rows: 十字的行数（仅用于十字策略）
    :param cols: 十字的列数（仅用于十字策略）
    """
    global strategy_count
    strategy_count += 1  # 增加计数器

    # 根据策略类型ID生成覆盖范围
    if strategy_id == 8:  # 如果是十字策略
        coverage = generate_cross_coverage(rows, cols)
    else:
        coverage = generate_coverage(strategy_id)

    # 添加策略到字典，使用唯一ID
    strategies[f"{strategy_count}"] = {"coverage": coverage, "cost": cost}


def solve_special_card_problem(points_to_cover, obstacles):
    # 定义问题
    prob = LpProblem("Map Coverage Problem", LpMinimize)

    # 定义常量
    MAP_WIDTH = 9
    MAP_HEIGHT = 7

    strategies = {}
    # 定义一个全局计数器，用于生成唯一的策略ID
    global strategy_count
    strategy_count = 0

    # 添加策略
    # add_strategy(strategies, 1, 10)  # 3x3
    # add_strategy(strategies, 2, 150)  # 4x3
    # add_strategy(strategies, 3, 275)  # 5x5
    # add_strategy(strategies, 4, 20)  # 全行覆盖
    # add_strategy(strategies, 5, 20)  # 全列覆盖
    # add_strategy(strategies, 6, 10)  # 小十字
    add_strategy(strategies, 7, 30)  # 三行覆盖
    add_strategy(strategies, 7, 30)
    add_strategy(strategies, 7, 30)
    add_strategy(strategies, 8, 15, rows=2, cols=2)  # 十字策略
    # print(strategies)

    # 创建决策变量
    x = LpVariable.dicts("strategy",
                         [(i, j, s) for i in range(1, MAP_WIDTH+1)
                                    for j in range(1, MAP_HEIGHT+1)
                                    for s in strategies.keys()],
                         cat='Binary')

    # 目标函数
    prob += lpSum([strategies[s]["cost"] * x[i,j,s] for i in range(1, MAP_WIDTH+1)
                                                    for j in range(1, MAP_HEIGHT+1)
                                                    for s in strategies.keys()])

    # 约束条件
    # 1. 每个待处理点位至少被覆盖一次
    for point in points_to_cover:
        i, j = map(int, point.split('-'))
        prob += lpSum([x[i_s,j_s,s] for i_s in range(1, MAP_WIDTH+1)
                                    for j_s in range(1, MAP_HEIGHT+1)
                                    for s in strategies.keys()
                                    if (i-i_s, j-j_s) in strategies[s]["coverage"]]) >= 1

    # 2. 不能在障碍上放置对策
    for obstacle in obstacles:
        i, j = map(int, obstacle.split('-'))
        for s in strategies.keys():
            prob += x[i,j,s] == 0
    #3.每个策略只能被放置一次
    for s in strategies.keys():
        prob += lpSum([x[i, j, s] for i in range(1, MAP_WIDTH + 1)
                       for j in range(1, MAP_HEIGHT + 1)]) <= 1

    # 求解问题
    prob.solve()

    # 输出结果
    print("Status:", LpStatus[prob.status])
    if LpStatus[prob.status] == "Optimal":#有解
        print("Optimal Cost =", value(prob.objective))
        for i in range(1, MAP_WIDTH+1):
            for j in range(1, MAP_HEIGHT+1):
                for s in strategies.keys():
                    if value(x[i,j,s]) == 1:
                        print(f"Place strategy {s} at position ({i},{j})")

    # 定义待处理点位列表
points_to_cover = ["9-5", "3-2","9-2", "1-1"]  # 添加所有待处理点位

    # 定义障碍列表
obstacles = ["1-1", "2-3","9-6"]  # 添加所有障碍点位
solve_special_card_problem(points_to_cover, obstacles)