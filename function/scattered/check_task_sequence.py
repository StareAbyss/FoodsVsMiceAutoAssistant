import json
import time
import uuid

from function.globals import EXTRA, SIGNAL
from function.globals.get_paths import PATHS
from function.scattered.get_task_sequence_list import get_task_sequence_list


def fresh_and_check_all_task_sequence():
    """
    刷新和检测现存所有任务序列
    如果没有 uuid 添加一个并保存进去
    :return: 创建 uuid -> 路径 的速查表
    """
    task_sequences = get_task_sequence_list(with_extension=False)

    task_sequence_uuid_to_path = {}  # { uuid:str : path:str }
    task_sequence_uuid_list = []  # 按task_sequences完全一致的顺序排列
    added = {}  # 记录添加或更改了uuid的序列

    for sequence_name in task_sequences:
        file_path = PATHS["task_sequence"] + "\\" + sequence_name + ".json"

        # 自旋锁, 防多线程读写问题
        with EXTRA.FILE_LOCK:

            added[sequence_name] = ""
            need_save = False

            try:
                with open(file=file_path, mode='r', encoding='utf-8') as file:
                    json_data = json.load(file)
            except Exception:
                added[sequence_name] += "json格式错误无法解析! 请勿使用文本编辑器瞎改! 请删除对应方案, FAA已保护性自爆!"
                continue

            # 检查是否存在meta_data字段，如果不存在则创建
            if not isinstance(json_data, list) or (
                    isinstance(json_data, list) and len(json_data) > 0 and not isinstance(json_data[0], dict)):
                added[sequence_name] += "任务序列格式不正确!"
                continue

            # 确保第一个任务包含meta_data字段
            if len(json_data) > 0:
                if not ("meta_data" in json_data[0] and "uuid" in json_data[0]["meta_data"]):
                    # 如果第一个元素不是元数据，则插入一个新的元数据元素
                    meta_data = {
                        "meta_data": {
                            "uuid": str(uuid.uuid1()),
                            "version": "1.0"
                        }
                    }
                    json_data.insert(0, meta_data)
                    need_save = True
                    added[sequence_name] += "添加了meta_data信息;"
                else:
                    # 检查UUID是否有效
                    uuid_v1 = json_data[0]["meta_data"].get('uuid')
                    if not uuid_v1:
                        uuid_v1 = str(uuid.uuid1())
                        json_data[0]["meta_data"]["uuid"] = uuid_v1
                        need_save = True
                        added[sequence_name] += "生成了新的UUID;"

                    if uuid_v1 in task_sequence_uuid_list:
                        # 撞了uuid就生成
                        uuid_v1 = str(uuid.uuid1())
                        json_data[0]["meta_data"]["uuid"] = uuid_v1
                        added[sequence_name] += "方案的uuid撞车, 已重新生成;"
                        need_save = True
                        # 确保uuid唯一性
                        time.sleep(0.001)

                    # 更新uuid列表
                    task_sequence_uuid_list.append(uuid_v1)
                    task_sequence_uuid_to_path[uuid_v1] = file_path
            else:
                # 空的任务序列文件
                uuid_v1 = str(uuid.uuid1())
                json_data.insert(0, {
                    "meta_data": {
                        "uuid": uuid_v1,
                        "version": "1.0"
                    }
                })
                need_save = True
                added[sequence_name] += "为空序列添加了meta_data信息;"

                # 更新uuid列表
                task_sequence_uuid_list.append(uuid_v1)
                task_sequence_uuid_to_path[uuid_v1] = file_path

            # 保存
            if need_save:
                with open(file=file_path, mode='w', encoding='utf-8') as file:
                    json.dump(json_data, file, ensure_ascii=False, indent=4)

    EXTRA.TASK_SEQUENCE_UUID_TO_PATH = task_sequence_uuid_to_path

    # 只有在有信息需要显示时才弹出对话框
    info = ""
    for sequence_name, msg in added.items():
        if msg != "":
            info += f"{sequence_name} -> {msg}\n"
    if info != "":
        SIGNAL.DIALOG.emit("任务序列检测和修复完成", info)

    return task_sequence_uuid_list
