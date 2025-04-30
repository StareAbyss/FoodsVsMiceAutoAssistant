import json
import time
import uuid

from function.globals import EXTRA, SIGNAL
from function.globals.get_paths import PATHS
from function.scattered.class_battle_plan_v3d0 import convert_v2_to_v3
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

            added[plan_name] = ""
            need_save = False

            try:
                with open(file=file_name, mode='r', encoding='utf-8') as file:
                    json_data = json.load(file)
            except:
                added[plan_name] += "json格式错误无法解析! 请勿使用文本编辑器瞎改! 请删除对应方案, FAA已保护性自爆!"
                continue

            battle_plan_version = json_data.get("meta_data",{}).get("version", None)
            if not battle_plan_version:
                # 低于v3.0版本的战斗方案, 尝试从v2.0进行迁移
                try:
                    json_data = convert_v2_to_v3(v2_data=json_data)
                    need_save = True
                    added[plan_name] += "成功从v2.0迁至最新"
                except:
                    added[plan_name] += "方案版本过低! 请使用FAA 2.0-2.1 版本迁移至v2.0"
                    continue

            uuid_v1 = json_data["meta_data"]['uuid']

            if uuid_v1 in battle_plan_uuid_list:
                # 撞了uuid就生成
                uuid_v1 = str(uuid.uuid1())
                json_data["meta_data"]["uuid"] = uuid_v1
                added[plan_name] += "方案的uuid撞车, 已重新生成;"
                need_save = True
                # 确保uuid唯一性
                time.sleep(0.001)

            # 保存
            if need_save:
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
        SIGNAL.DIALOG.emit("方案检测和修复完成 - 方案版本 v3.0", info)


if __name__ == '__main__':
    fresh_and_check_all_battle_plan()
    print(EXTRA.BATTLE_PLAN_UUID_TO_PATH)
