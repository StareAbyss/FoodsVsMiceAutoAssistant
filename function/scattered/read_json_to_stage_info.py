import json

from function.globals import EXTRA
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER

# 全局变量，用于缓存卡片类型配置
MAT_CARD_TYPE_CONFIG = None


def load_mat_card_type_config():
    """
    加载卡片材质类型配置文件
    返回一个字典，key为类型名称，value为卡片列表
    """
    global MAT_CARD_TYPE_CONFIG
    
    # 如果已经加载过，直接返回缓存
    if MAT_CARD_TYPE_CONFIG is not None:
        return MAT_CARD_TYPE_CONFIG
    
    try:
        config_path = PATHS["config"] + "//card_type_mat.json"
        with open(file=config_path, mode="r", encoding="UTF-8") as file:
            MAT_CARD_TYPE_CONFIG = json.load(file)
        CUS_LOGGER.info(f"成功加载卡片材质类型配置: {config_path}")
    except FileNotFoundError:
        CUS_LOGGER.warning(f"卡片材质类型配置文件不存在: {config_path}，使用空配置. 无法自动使用承载!")
        MAT_CARD_TYPE_CONFIG = {}
    except json.JSONDecodeError as e:
        CUS_LOGGER.error(f"卡片材质类型配置文件格式错误: {e}，使用空配置. 无法自动使用承载!")
        MAT_CARD_TYPE_CONFIG = {}
    
    return MAT_CARD_TYPE_CONFIG


def init_mat_card_type_to_card_list(stage_info) -> dict:
    """
    根据关卡信息中的 mat_card_type 字段，初始化 mat_card 卡片列表
    
    优先级：
    1. 如果 stage_info 中已有 mat_card，直接使用
    2. 如果 stage_info 中有 mat_card_type，从配置文件查找对应的卡片列表
    3. 默认设置为空列表
    """
    # 优先手动指定的卡片列表
    if stage_info.get("mat_card", False):
        return stage_info

    # 否则根据类型从配置文件查找
    if stage_info.get("mat_card_type", False):
        mat_card_type = stage_info["mat_card_type"]
        
        # 加载配置文件
        config = load_mat_card_type_config()
        
        # 从配置中获取对应的卡片列表，如果找不到则使用空列表
        mat_card = config.get(mat_card_type, [])
        
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
