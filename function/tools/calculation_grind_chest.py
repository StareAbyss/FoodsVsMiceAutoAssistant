#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Filename: calculation_grind_chest.py
Author: StareAbyss
Creation Date：2024-04-26
Last Date：2024-04-26

Description：
线性规划 以计算美食大战老鼠肝帝宝箱的最优方案 (暂不含掉落权重)
"""
import math

import pulp

# 定义问题
problem = pulp.LpProblem("Material_Collection", pulp.LpMinimize)

# 定义决策变量，即每个关卡的次数，这些变量必须是整数
stage_A = pulp.LpVariable("NO-1-7", lowBound=0, cat='Integer')
stage_B = pulp.LpVariable("NO-1-14", lowBound=0, cat='Integer')
stage_C = pulp.LpVariable("NO-2-5", lowBound=0, cat='Integer')
stage_D = pulp.LpVariable("NO-2-10", lowBound=0, cat='Integer')
stage_E = pulp.LpVariable("NO-2-15", lowBound=0, cat='Integer')
stage_F = pulp.LpVariable("NO-4-5", lowBound=0, cat='Integer')
stage_G = pulp.LpVariable("NO-4-10", lowBound=0, cat='Integer')
stages_list = [stage_A, stage_B, stage_C, stage_D, stage_E, stage_F, stage_G]

weight_A = 1
weight_B = 1
weight_C = 1
weight_D = 1
weight_E = 1
weight_F = 1
weight_G = 0.01

# 目标函数：最小化总次数
problem += stage_A + stage_B + stage_C + stage_D + stage_E + stage_F + stage_G

# 约束条件：收集到足够的材料
problem += (stage_A * weight_A) + (stage_E * weight_E) >= 48  # 材料a
problem += (stage_B * weight_B) + (stage_D * weight_D) >= 48 - 141  # 材料b
problem += (stage_B * weight_B) + (stage_E * weight_E) + (stage_G * weight_G) >= 48 + 66 * 2 - 53  # 材料c
problem += (stage_C * weight_C) + (stage_G * weight_G) >= 25 - 10  # 材料d
problem += (stage_C * weight_C) + (stage_F * weight_F) >= 25 - 15  # 材料e
problem += (stage_A * weight_A) + (stage_D * weight_D) + (stage_F * weight_F) >= 25  # 材料f

# 解决问题
problem.solve()

sum_count = 0
for stage in stages_list:
    print(f"关卡 {stage.name} 需要打:{stage.varValue}次")
    sum_count += stage.varValue
print(f"总次数合计: {sum_count}次\n")

for stage in stages_list:
    print(f"关卡 {stage.name} 每天需要打:{round(45 * stage.varValue / sum_count, 1)}次")
print(f"分摊到每天需要: {math.ceil(sum_count / 45)}天")
