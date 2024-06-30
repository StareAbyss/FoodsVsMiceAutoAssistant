from pandas import DataFrame

from function.scattered.read_json_to_stage_info import read_json_to_stage_info

# stage_list_1 = ["NO", "EX", "CS"]
stage_list_1 = ["EX"]

stage_list_2 = []
for i in [5]:
    stage_list_2.append(str(i))

stage_list_3 = []
for i in range(8):
    stage_list_3.append(str(i))

stage_info_list = []
for stage_1 in stage_list_1:
    for stage_2 in stage_list_2:
        for stage_3 in stage_list_3:
            stage_info_list.append(read_json_to_stage_info(f"{stage_1}-{stage_2}-{stage_3}"))

result_dict = {}
for i in range(1, 10):
    for j in range(1, 8):
        result_dict["{}-{}".format(i, j)] = 0

for i in result_dict:
    for stage_info in stage_info_list:
        for o_p in stage_info["obstacle"]:
            if o_p == i:
                result_dict[i] += 1

df = DataFrame(index=[1, 2, 3, 4, 5, 6, 7], columns=[1, 2, 3, 4, 5, 6, 7, 8, 9])
for cell in result_dict:
    if cell != 0:
        df[int(cell[0])][int(cell[2])] = result_dict[cell]
print(df)
