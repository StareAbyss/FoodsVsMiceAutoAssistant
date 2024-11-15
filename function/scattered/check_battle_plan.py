import json
import time
import uuid

from function.globals import EXTRA, SIGNAL
from function.globals.get_paths import PATHS
from function.scattered.get_list_battle_plan import get_list_battle_plan


def fresh_and_check_all_battle_plan():
    """
    刷新和检测现存所有方案
    如果没有 uuid 添加一个并保存进去
    如果有Card字段(老方案) 迁移到Default
    :return: 创建 uuid -> 路径 的速查表
    """
    battle_plans = get_list_battle_plan(with_extension=False)

    battle_plan_uuid_to_path = {}  # { uuid:str : path:str }
    battle_plan_uuid_list = []  # 按battle_plans完全一致的顺序排列
    added = {}  # 记录添加或更改了uuid的plan

    for plan_name in battle_plans:
        file_name = PATHS["battle_plan"] + "\\" + plan_name + ".json"

        # 自旋锁, 防多线程读写问题
        with EXTRA.FILE_LOCK:

            with open(file=file_name, mode='r', encoding='utf-8') as file:
                json_data = json.load(file)

            added[plan_name] = ""
            changed = False

            uuid_v1 = json_data.get('uuid')

            if uuid_v1 in battle_plan_uuid_list:
                # 撞了uuid就生成
                uuid_v1 = str(uuid.uuid1())
                json_data["uuid"] = uuid_v1
                added[plan_name] += "FAA v1.5.0以下 uuid撞车重新生成;"
                changed = True
                # 确保uuid唯一性
                time.sleep(0.001)

            if not uuid_v1:
                # 没有uuid重新生成
                uuid_v1 = str(uuid.uuid1())
                json_data["uuid"] = uuid_v1
                added[plan_name] += "FAA v1.5.0以下 uuid缺失立刻生成;"
                changed = True
                # 确保uuid唯一性
                time.sleep(0.001)

            card = json_data.get("card")

            if type(card) is list:
                json_data["card"] = {"default": card, "wave": {}}
                added[plan_name] += "FAA v1.5.7以下 缺失波次信息;"
                changed = True

            # 保存
            if changed:
                with open(file=file_name, mode='w', encoding='utf-8') as file:
                    json.dump(json_data, file, ensure_ascii=False, indent=4)

        battle_plan_uuid_list.append(uuid_v1)
        battle_plan_uuid_to_path[uuid_v1] = file_name

    EXTRA.BATTLE_PLAN_UUID_TO_PATH = battle_plan_uuid_to_path

    info = ""
    for plan_name, msg in added.items():
        if msg != "":
            info += f"{plan_name} -> {msg}\n"
    if info != "":
        SIGNAL.DIALOG.emit("方案检测和修复完成", info)


if __name__ == '__main__':
    fresh_and_check_all_battle_plan()
    print(EXTRA.BATTLE_PLAN_UUID_TO_PATH)
