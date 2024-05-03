from itertools import combinations

from function.scattered.read_json_to_stage_info import read_json_to_stage_info

stage_list_1 = ["NO", "EX", "CS"]

stage_list_2 = []
for i in range(10):
    stage_list_2.append(str(i))

stage_list_3 = []
for i in range(20):
    stage_list_3.append(str(i))

stage_info_list = []
for stage_1 in stage_list_1:
    for stage_2 in stage_list_2:
        for stage_3 in stage_list_3:
            stage_info_list.append(
                read_json_to_stage_info(
                    "{}-{}-{}".format(
                        stage_1,
                        stage_2,
                        stage_3)))

# 生成所有可能的四格组合
target_cells = ["2-1", "2-2", "2-3", "2-5", "2-6", "2-7",
                "3-1", "3-2", "3-3", "3-5", "3-6", "3-7"]
all_combinations = combinations(target_cells, 4)


# 检查组合在每个关卡中与障碍物重合的格子数是否最多只有一个
def is_combination_valid(combination, stage_info_list):
    for stage_info in stage_info_list:
        overlap_count = sum(1 for cell in combination if cell not in stage_info["obstacle"])
        # 需要达到指定数量 方可通过
        if overlap_count >= 1:
            return True
    return False


# # 找到符合条件的组合
# valid_combinations = []
# for comb in all_combinations:
#     if is_combination_valid(comb, stage_info_list=stage_info_list):
#         valid_combinations.append(comb)
#
# # 打印结果
# print("Valid positions combinations:")
# for pos in valid_combinations:
#     print(pos)

print("结果:" + str(
    is_combination_valid(
        combination=["2-2","2-3","2-6", "2-5"],
        stage_info_list=stage_info_list
    )
))
