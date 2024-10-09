import json

from function.globals import g_extra
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER


def read_json_to_stage_info(stage_id, stage_id_for_battle=None):
    """
    读取文件中是否存在预设
    :param stage_id: 关卡的id, 可以是用于某些特殊功能的 不指定特定关卡的id 比如魔塔爬塔和自建房战斗的 ID MT-1-0 CU-0-0
    :param stage_id_for_battle: 真实关卡id 直接用于查找关卡配置 大多数情况下直接继承关卡的id
    :return: {"id": str, }
    """
    with g_extra.GLOBAL_EXTRA.file_lock:
        with open(file=PATHS["config"] + "//stage_info.json", mode="r", encoding="UTF-8") as file:
            stages_info = json.load(file)
        with open(file=PATHS["config"] + "//stage_info_extra.json", mode="r", encoding="UTF-8") as file:
            stages_info_extra = json.load(file)

    # 初始化
    if not stage_id_for_battle:
        stage_id_for_battle = stage_id
    stage_info = stages_info["default"]
    stage_info["id"] = stage_id

    # 拆分关卡名称
    stage_0, stage_1, stage_2 = stage_id_for_battle.split("-")  # type map stage

    # 如果找到预设
    for information in [stages_info_extra, stages_info]:
        try_stage_info = information.get(stage_0, {}).get(stage_1, {}).get(stage_2, None)
        if try_stage_info:
            stage_info = {**stage_info, **try_stage_info}
            break

    CUS_LOGGER.info("读取关卡信息: {}".format(stage_info))
    return stage_info


if __name__ == '__main__':
    read_json_to_stage_info(stage_id="OR-0-2")
