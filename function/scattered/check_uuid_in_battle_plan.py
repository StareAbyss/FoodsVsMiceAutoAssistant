import json
import time
import uuid

from function.globals.extra import EXTRA_GLOBALS
from function.globals.get_paths import PATHS
from function.scattered.get_list_battle_plan import get_list_battle_plan


def check_battle_plan_with_uuid():
    """
    检测是否已经存在uuid在所有方案中
    如果没有 添加一个并保存进去
    :return: 创建 uuid -> 路径的速查表
    """
    battle_plans = get_list_battle_plan(with_extension=True)

    battle_plan_uuid_to_path = {}
    battle_plan_uuid_list = []

    for battle_plan in battle_plans:
        file_name = PATHS["battle_plan"] + "\\" + battle_plan

        # 自旋锁读写, 防止多线程读写问题
        while EXTRA_GLOBALS.file_is_reading_or_writing:
            time.sleep(0.1)

        EXTRA_GLOBALS.file_is_reading_or_writing = True  # 文件被访问

        with open(file=file_name, mode='r', encoding='utf-8') as file:
            json_data = json.load(file)

        uuid_v1 = json_data.get('uuid')
        if uuid_v1 in battle_plan_uuid_list or not uuid_v1:
            # 没有或者撞了uuid就生成
            uuid_v1 = str(uuid.uuid1())
            json_data["uuid"] = uuid_v1
            with open(file=file_name, mode='w', encoding='utf-8') as file:
                json.dump(json_data, file, ensure_ascii=False, indent=4)
            time.sleep(0.001)  # 确保uuid唯一性
        EXTRA_GLOBALS.file_is_reading_or_writing = False  # 文件已解锁

        battle_plan_uuid_to_path[uuid_v1] = file_name
        battle_plan_uuid_list.append(uuid_v1)

    EXTRA_GLOBALS.battle_plan_uuid_list = battle_plan_uuid_list
    EXTRA_GLOBALS.battle_plan_uuid_to_path = battle_plan_uuid_to_path


if __name__ == '__main__':
    check_battle_plan_with_uuid()
    print(EXTRA_GLOBALS.battle_plan_uuid_list)
