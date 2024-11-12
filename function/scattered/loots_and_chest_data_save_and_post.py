import json
import os
import time

import requests
from requests import RequestException

from function.globals import EXTRA
from function.globals.get_paths import PATHS


def loots_and_chests_statistics_to_json(faa, loots_dict, chests_dict) -> None:
    """
    保存战利品汇总.json
    :param faa: FAA类实例
    :param loots_dict:
    :param chests_dict:
    :return:
    """

    stage_info = faa.stage_info
    faa_battle = faa.faa_battle
    player = faa.player

    file_path = "{}\\result_json\\{}P掉落汇总.json".format(PATHS["logs"], player)
    stage_name = stage_info["id"]

    # 获取本次战斗是否使用了钥匙
    if faa_battle.is_used_key:
        used_key_str = "is_used_key"
    else:
        used_key_str = "is_not_used_key"

    if os.path.exists(file_path):
        # 尝试读取现有的JSON文件 自旋锁读写, 防止多线程读写问题
        with EXTRA.FILE_LOCK:
            with open(file=file_path, mode="r", encoding="utf-8") as json_file:
                json_data = json.load(json_file)
    else:
        # 如果文件不存在，初始化
        json_data = {}

    # 检查键 不存在添加
    json_data_stage = json_data.setdefault(stage_name, {})
    json_data_used_key = json_data_stage.setdefault(used_key_str, {})
    json_data_loots = json_data_used_key.setdefault("loots", {})
    json_data_chests = json_data_used_key.setdefault("chests", {})
    json_data_count = json_data_used_key.setdefault("count", 0)

    # 更新现有数据
    for item_str, count in loots_dict.items():
        json_data_loots[item_str] = json_data_loots.get(item_str, 0) + count
    for item_str, count in chests_dict.items():
        json_data_chests[item_str] = json_data_loots.get(item_str, 0) + count
    json_data_count += 1  # 更新次数

    # 保存或更新后的战利品字典到JSON文件  自旋锁读写, 防止多线程读写问题
    with EXTRA.FILE_LOCK:
        with open(file=file_path, mode="w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)


def loots_and_chests_detail_to_json(faa, loots_dict, chests_dict) -> dict:
    """
    分P，在目录下保存战利品字典
    :param faa: FAA类实例
    :param loots_dict:
    :param chests_dict:
    :return:
    """

    player = faa.player
    stage_info = faa.stage_info
    faa_battle = faa.faa_battle

    file_path = "{}\\result_json\\{}P掉落明细.json".format(PATHS["logs"], player)
    stage_name = stage_info["id"]
    new_data = {
        "version": EXTRA.VERSION,  # 版本号
        "timestamp": time.time(),  # 时间戳
        "stage": stage_name,  # 关卡代号
        "is_used_key": faa_battle.is_used_key,
        "loots": loots_dict,
        "chests": chests_dict
    }

    if os.path.exists(file_path):
        with EXTRA.FILE_LOCK:
            with open(file=file_path, mode="r", encoding="utf-8") as json_file:
                json_data = json.load(json_file)

    else:
        # 如果文件不存在，初始化
        json_data = {}

    # 检查"data"字段是否存在
    json_data.setdefault("data", [])

    # 保存到字典数据
    json_data["data"].append(new_data)

    # 保存或更新后的战利品字典到JSON文件 自旋锁读写, 防止多线程读写问题
    with EXTRA.FILE_LOCK:
        with open(file=file_path, mode="w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)

    return new_data


def loots_and_chests_data_post_to_sever(detail_data, url=None) -> bool:
    """
    :param detail_data: loots_and_chests_detail_to_json 的 返回值
    :param url: 路径
    :return: 是否发送成功
    """
    if not url:
        # url 是 None 和 "" 这样的值
        url = 'http://stareabyss.top:5000/faa_server/data_upload/battle_drops'
    try:
        # 校验正确的url, 输出到FAA数据中心 5s超时
        response = requests.post(
            url=url, json=detail_data, timeout=5)
        # 检查响应状态码,如果不是2xx则引发异常 会被log捕获
        response.raise_for_status()
        return True
    except RequestException as e:
        return False

# if __name__ == '__main__':
#     result = loots_and_chests_data_post_to_sever(
#         detail_data={
#             "timestamp": time.time(),
#             "stage": "NO-2-6",
#             "is_used_key": True,
#             "loots": {'1级四叶草': 1, '上等香料': 3, '天然香料': 1, '菠萝爆炸面包配方': 1, '开水壶炸弹配方': 2,
#                       '果冻胶': 1, '红豆腐': 2, '电鳗鱼肉': 1, '冰包子': 1, '白砂糖': 2, '小蒸笼': 2, '水壶': 2,
#                       '木块': 2, '火药': 1},
#             "chests": {'白砂糖': 1, '果冻胶': 1}
#         }
#     )
#     print(result)
