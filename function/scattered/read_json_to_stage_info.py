import json
import time

from function.globals.extra import EXTRA_GLOBALS
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER


def read_json_to_stage_info(stage_id):
    """读取文件中是否存在预设"""
    # 自旋锁读写, 防止多线程读写问题
    while EXTRA_GLOBALS.file_is_reading_or_writing:
        time.sleep(0.1)
    EXTRA_GLOBALS.file_is_reading_or_writing = True  # 文件被访问
    with open(file=PATHS["config"] + "//stage_info.json", mode="r", encoding="UTF-8") as file:
        stages_info = json.load(file)
    with open(file=PATHS["config"] + "//stage_info_extra.json", mode="r", encoding="UTF-8") as file:
        stages_info_extra = json.load(file)
    EXTRA_GLOBALS.file_is_reading_or_writing = False  # 文件已解锁

    # 初始化
    stage_info = stages_info["default"]
    stage_info["id"] = stage_id

    # 拆分关卡名称
    stage_0, stage_1, stage_2 = stage_id.split("-")  # type map stage

    # 如果找到预设
    for information in [stages_info, stages_info_extra]:
        try_stage_info = information.get(stage_0, {}).get(stage_1, {}).get(stage_2, None)
        if try_stage_info:
            stage_info = {**stage_info, **try_stage_info}
            break

    CUS_LOGGER.info("读取关卡信息: {}".format(stage_info))
    return stage_info


if __name__ == '__main__':
    read_json_to_stage_info(stage_id="OR-0-2")
