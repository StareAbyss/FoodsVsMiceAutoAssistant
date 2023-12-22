import json

from function.get_paths import paths


def read_json_to_stage_info(stage_id):
    """读取文件中是否存在预设"""
    with open(paths["config"] + "//opt_stage_info.json", "r", encoding="UTF-8") as file:
        f_my_dict = json.load(file)
    # 初始化
    stage_info = f_my_dict["default"]
    stage_info["id"] = stage_id
    # 拆分关卡名称
    stage_list = stage_id.split("-")
    stage_0 = stage_list[0]  # type
    stage_1 = stage_list[1]  # map
    stage_2 = stage_list[2]  # stage
    # 如果找到预设
    if stage_0 in f_my_dict.keys():
        if stage_1 in f_my_dict[stage_0].keys():
            if stage_2 in f_my_dict[stage_0][stage_1].keys():
                # 用设定里有的键值对覆盖已有的 并填写关卡名称(没有则保持默认)
                f_stage_info_1 = f_my_dict[stage_0][stage_1][stage_2]

                stage_info = {**stage_info, **f_stage_info_1}
    return stage_info
