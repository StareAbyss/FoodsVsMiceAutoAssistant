from pulp import *

# 定义问题
prob = LpProblem("Map Coverage Problem", LpMinimize)

# 定义常量
MAP_WIDTH = 9
MAP_HEIGHT = 7

# 定义待处理点位列表
points_to_cover = ["9-5", "3-2"]  # 添加所有待处理点位

# 定义障碍列表
obstacles = ["1-1", "2-3"]  # 添加所有障碍点位

# 定义对策及其代价
strategies = {
    1: {"coverage": [(0,0), (0,1), (0,-1), (1,0), (1,1), (1,-1), (-1,0), (-1,1), (-1,-1)], "cost": 10},
    2: {"coverage": [(0,0), (0,1), (0,-1), (1,0), (1,1), (1,-1), (2,0), (2,1), (2,-1), (3,0), (3,1), (3,-1)], "cost": 15},
    # ... 添加其他对策
}

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

# 求解问题
prob.solve()

# 输出结果
print("Status:", LpStatus[prob.status])
if LpStatus[prob.status] == "Optimal":
    print("Optimal Cost =", value(prob.objective))
    for i in range(1, MAP_WIDTH+1):
        for j in range(1, MAP_HEIGHT+1):
            for s in strategies.keys():
                if value(x[i,j,s]) == 1:
                    print(f"Place strategy {s} at position ({i},{j})")