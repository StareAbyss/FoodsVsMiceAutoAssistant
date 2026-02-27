import json

from function.globals import EXTRA
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER


def init_mat_card_type_to_card_list(stage_info) -> dict:
    # 优先手动
    if stage_info.get("mat_card", False):
        return stage_info

        # 否则应用类
    if stage_info.get("mat_card_type", False):
        match stage_info["mat_card_type"]:
            case "":
                mat_card = []
            case "水面":
                mat_card = ["木盘子-2", "木盘子-1", "魔法软糖-2", "木盘子-0", "魔法软糖-1", "魔法软糖-0"]
            case "云洞":
                mat_card = ["棉花糖-2", "棉花糖-1", "魔法软糖-2", "棉花糖-0", "魔法软糖-1", "魔法软糖-0"]
            case "岩浆":
                mat_card = ["棉花糖-2", "棉花糖-1", "魔法软糖-2", "棉花糖-0", "魔法软糖-1", "魔法软糖-0"]
            case "海底":
                mat_card = ["麦芽糖-1", "魔法软糖-2", "气泡-1", "魔法软糖-1", "魔法软糖-0", "气泡-0"]
            case "海底-无气泡":
                mat_card = ["麦芽糖-1", "魔法软糖-2", "魔法软糖-1", "魔法软糖-0"]
            case "毒气":
                mat_card = ["棉花糖-2", "麦芽糖-1", "麦芽糖-0"]
            case _:
                mat_card = []
        stage_info["mat_card"] = mat_card
        return stage_info

    # 默认无
    stage_info["mat_card"] = []
    return stage_info


def read_json_to_stage_info(stage_id, stage_id_for_battle=None):
    """
    读取文件中是否存在预设
    :param stage_id: 关卡的id, 可以是用于某些特殊功能的 不指定特定关卡的id 比如魔塔爬塔 ID MT-1-0
    :param stage_id_for_battle: 真实关卡id 直接用于查找关卡配置 大多数情况下直接继承关卡的id
    :return: {
        "id": str,
         "b_id": str,
    }
    """
    configs = []
    with EXTRA.FILE_LOCK:

        with open(file=PATHS["config"] + "//stage_info_extra.json", mode="r", encoding="UTF-8") as file:
            stages_info_extra = json.load(file)
            configs.append(("stage_info_extra.json", stages_info_extra))

        with open(file=PATHS["config"] + "//stage_info_online.json", mode="r", encoding="UTF-8") as file:
            stages_info_online = json.load(file)
            configs.append(("stage_info_online.json", stages_info_online))

        with open(file=PATHS["config"] + "//stage_info.json", mode="r", encoding="UTF-8") as file:
            stages_info = json.load(file)
            configs.append(("stage_info.json", stages_info))

    # 初始化
    if not stage_id_for_battle:
        stage_id_for_battle = stage_id
    stage_info = stages_info["default"]
    stage_info["id"] = stage_id
    stage_info["b_id"] = stage_id_for_battle

    # 拆分关卡名称
    stage_0, stage_1, stage_2 = stage_id_for_battle.split("-")  # type map stage

    # 如果找到预设
    used_config_name = None
    for config_name, information in configs:
        try_stage_info = information.get(stage_0, {}).get(stage_1, {}).get(stage_2, None)
        if try_stage_info:
            stage_info = {**stage_info, **try_stage_info}
            used_config_name = config_name
            break

    # 转化
    stage_info = init_mat_card_type_to_card_list(stage_info)

    if used_config_name:
        CUS_LOGGER.info(f"从 {used_config_name} 读取关卡信息: {stage_info}")
    else:
        CUS_LOGGER.info(f"未找到预设，使用默认关卡信息: {stage_info}")

    return stage_info


if __name__ == '__main__':
    read_json_to_stage_info(stage_id="OR-0-2")
