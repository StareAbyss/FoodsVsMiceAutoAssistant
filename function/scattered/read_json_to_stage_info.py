import json

from function.globals import EXTRA
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER


def read_json_to_stage_info(stage_id, stage_id_for_battle=None):
    """
    读取文件中是否存在预设
    :param stage_id: 关卡的id, 可以是用于某些特殊功能的 不指定特定关卡的id 比如魔塔爬塔和自建房战斗的 ID MT-1-0 CU-0-0
    :param stage_id_for_battle: 真实关卡id 直接用于查找关卡配置 大多数情况下直接继承关卡的id
    :return: {"id": str, }
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

    # 拆分关卡名称
    stage_0, stage_1, stage_2 = stage_id_for_battle.split("-")  # type map stage

    # 如果找到预设
    for config_name, information in configs:
        try_stage_info = information.get(stage_0, {}).get(stage_1, {}).get(stage_2, None)
        if try_stage_info:
            stage_info = {**stage_info, **try_stage_info}
            CUS_LOGGER.info("从 {} 读取关卡信息: {}".format(config_name, stage_info))
            break
    else:
        CUS_LOGGER.info("未找到预设，使用默认关卡信息: {}".format(stage_info))

    return stage_info


if __name__ == '__main__':
    read_json_to_stage_info(stage_id="OR-0-2")
