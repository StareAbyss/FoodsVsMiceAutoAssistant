# 从FAA Web的接口获取数据
import json
from datetime import datetime

import requests

from function.globals.get_paths import PATHS


def get_stage_info_online() -> str:
    """
    从FAA云端试图获取stage_info.
    :return: 描述字符串
    """
    # 获取云端json的更新时间 格式示例 2021-08-08 14:05:04
    try:
        url = "http://stareabyss.top:5000/faa_server/data_export/stage_info_online_update/time"
        headers = {}
        # 发起GET请求
        response = requests.get(url, headers=headers, timeout=5)
        # 确保请求成功
        if response.status_code == 200:
            origin_update_time = response.json()["update_time"]
        else:
            return f"获取云端关卡信息 - 获取云端上次更新时间 失败!\n状态码：{response.status_code}, 原因：{response.text}"
    except requests.exceptions.Timeout as e:
        return f"获取云端关卡信息 - 获取云端上次更新时间 超时!\n信息：{e}"

    # 校验本地json的更新时间
    with open(file=PATHS["config"] + "//stage_info_online.json", mode="r", encoding="UTF-8") as file:
        stages_info_online = json.load(file)
    local_update_time = stages_info_online["update_time"]

    origin_dt = datetime.strptime(origin_update_time, "%Y-%m-%d %H:%M:%S")
    local_dt = datetime.strptime(local_update_time, "%Y-%m-%d %H:%M:%S")

    # 如果云端不比本地更新, 直接返回
    if origin_dt <= local_dt:
        return f"获取云端关卡信息 放弃!\n本地数据为最新, 云端数据时间: {origin_update_time}, 本地数据时间: {local_update_time}"

    # 获取云端json的数据
    try:
        url = "http://stareabyss.top:5000/faa_server/data_export/stage_info_online_update/data"
        headers = {}
        # 发起GET请求
        response = requests.get(url, headers=headers, timeout=5)
        # 确保请求成功
        if response.status_code == 200:
            new_stage_info = response.json()
        else:
            return f"获取云端关卡信息 失败!\n状态码：{response.status_code}, 原因：{response.text}"
    except requests.exceptions.Timeout as e:
        return f"获取云端关卡信息 超时!\n信息：{e}"

    # 覆盖本地
    with open(file=PATHS["config"] + "//stage_info_online.json", mode="w", encoding="UTF-8") as file:
        json.dump(new_stage_info, file, ensure_ascii=False, indent=4)

    return f"获取云端关卡信息 大成功!\n数据已更新到本地, 最新数据时间:{origin_update_time}"
