import csv
import json
import os

import cv2
import numpy as np

from function.globals import EXTRA
from function.globals.get_paths import PATHS


def im_read(img_path):
    # 读取图像，处理中文路径
    img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), -1)

    # 调试代码，通过重新保存清除libpng警告
    # 使用imencode处理中文路径的问题
    # ext = img_path.split('.')[-1]  # 获取文件扩展名
    # _, buf = cv2.imencode(f'.{ext}', img)
    # with open(img_path, 'wb') as f:
    #     f.write(buf)

    return img


"""RESOURCE_P 常规图片资源 通常为静态 可以直接调用"""

RESOURCE_P = {}
ITEM_LOOT_BLACKLIST_CSV = os.path.join(PATHS["root"], "resource", "image", "item", "无法掉落道具名单.csv")
_ITEM_LOOT_BLACKLIST_CACHE = None
_ITEM_LOOT_BLACKLIST_CACHE_MTIME = None


def add_to_resource_img(relative_path, img):
    global RESOURCE_P
    current_level = RESOURCE_P

    path_parts = relative_path.split(os.sep)

    for part in path_parts[:-1]:
        if part not in current_level:
            current_level[part] = {}  # 初始化一个新的字典
        current_level = current_level[part]

    # 设置最终的图像数据
    current_level[path_parts[-1]] = img


def fresh_resource_img():
    # 清空
    global RESOURCE_P
    RESOURCE_P = {}

    # 遍历文件夹结构，读取所有名称后缀为.png的文件，加入到字典中
    root_dir = os.path.join(PATHS["root"], 'resource', 'image')

    for root, dirs, files in os.walk(root_dir):
        # 对于每个子文件夹，创建对应的字典层级
        for c_dir in dirs:
            relative_path = os.path.relpath(os.path.join(root, c_dir), root_dir)
            add_to_resource_img(relative_path, {})  # 创建字典层级，值可以设为None

        # 读取所有名称后缀为.png的文件，加入到字典中
        for file in files:
            if file.endswith(".png"):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, root_dir)
                img = im_read(file_path)
                add_to_resource_img(relative_path, img)


def flatten_resource_images(resource_node):
    """
    将嵌套资源节点展开为文件名到图片对象的平铺映射。

    战利品图片允许按类型放入子文件夹，但识别流程仍按历史逻辑通过
    `物品名.png` 直接取图，因此这里保留分类目录结构的同时提供平铺视图。

    Args:
        resource_node: RESOURCE_P 中的任意资源节点，通常是嵌套 dict。

    Returns:
        dict[str, numpy.ndarray]: 以图片文件名为 key、图片对象为 value 的平铺资源映射。
        传入节点不是 dict 时返回空 dict。
    """
    flat_images = {}
    if not isinstance(resource_node, dict):
        return flat_images

    for name, value in resource_node.items():
        if isinstance(value, dict):
            flat_images.update(flatten_resource_images(value))
        else:
            flat_images[name] = value
    return flat_images


def get_item_loot_blacklist():
    """
    读取不会在战利品中掉落的物品名单。

    黑名单 CSV 位于 `resource/image/item/无法掉落道具名单.csv`，只包含 `类型,名称` 两列。
    战利品资源本身按 `resource/image/item/战利品/类型/名称.png` 存放，因此读取后转换为
    `(类型, 名称.png)` 集合供展平资源时过滤。

    Returns:
        set[tuple[str, str]]: 需要从战利品识别临时平铺资源中排除的 `(类型, 文件名)` 集合。
    """
    global _ITEM_LOOT_BLACKLIST_CACHE
    global _ITEM_LOOT_BLACKLIST_CACHE_MTIME

    if not os.path.exists(ITEM_LOOT_BLACKLIST_CSV):
        _ITEM_LOOT_BLACKLIST_CACHE = set()
        _ITEM_LOOT_BLACKLIST_CACHE_MTIME = None
        return _ITEM_LOOT_BLACKLIST_CACHE

    csv_mtime = os.path.getmtime(ITEM_LOOT_BLACKLIST_CSV)
    if _ITEM_LOOT_BLACKLIST_CACHE is not None and _ITEM_LOOT_BLACKLIST_CACHE_MTIME == csv_mtime:
        return _ITEM_LOOT_BLACKLIST_CACHE

    blacklist = set()
    with open(ITEM_LOOT_BLACKLIST_CSV, newline="", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            item_type = row[0].strip()
            item_name = row[1].strip()
            if item_type and item_name:
                blacklist.add((item_type, f"{item_name}.png"))

    _ITEM_LOOT_BLACKLIST_CACHE = blacklist
    _ITEM_LOOT_BLACKLIST_CACHE_MTIME = csv_mtime
    return _ITEM_LOOT_BLACKLIST_CACHE


def flatten_item_loot_images(resource_node, blacklist, item_type=None):
    """
    将战利品资源节点展平，并排除不会实际掉落的黑名单物品。

    战利品目录的第一层子目录即物品类型；黑名单使用 `类型,名称` 标记。展平时保留历史的
    `{文件名: 图片对象}` 返回形式，但不会把黑名单物品放入识别候选。

    Args:
        resource_node: RESOURCE_P["item"]["战利品"] 或其子节点。
        blacklist: `get_item_loot_blacklist()` 返回的 `(类型, 文件名)` 集合。
        item_type: 当前递归所在的第一层物品类型。

    Returns:
        dict[str, numpy.ndarray]: 已过滤黑名单的战利品平铺资源映射。
    """
    flat_images = {}
    if not isinstance(resource_node, dict):
        return flat_images

    for name, value in resource_node.items():
        if isinstance(value, dict):
            next_item_type = name if item_type is None else item_type
            flat_images.update(flatten_item_loot_images(
                resource_node=value,
                blacklist=blacklist,
                item_type=next_item_type,
            ))
        elif (item_type, name) not in blacklist:
            flat_images[name] = value
    return flat_images


def get_item_loot_images():
    """
    获取所有战利品识别图片的平铺资源映射。

    `RESOURCE_P["item"]["战利品"]` 保留真实文件夹层级；战利品识别和掉落展示
    调用本函数获得兼容旧调用方式的 `{图片文件名: 图片对象}` 映射。

    Returns:
        dict[str, numpy.ndarray]: 包含战利品目录及其子分类目录下全部图片的平铺映射。
    """
    return flatten_item_loot_images(
        resource_node=RESOURCE_P.get("item", {}).get("战利品", {}),
        blacklist=get_item_loot_blacklist(),
    )


"""RESOURCE_CP 用户自定义图片资源"""

RESOURCE_CP = {}


def add_to_resource_cus_img(relative_path, img):
    global RESOURCE_CP
    current_level = RESOURCE_CP

    path_parts = relative_path.split(os.sep)

    for part in path_parts[:-1]:
        if part not in current_level:
            current_level[part] = {}  # 初始化一个新的字典
        current_level = current_level[part]

    # 设置最终的图像数据
    current_level[path_parts[-1]] = img


def fresh_resource_cus_img():
    # 清空
    global RESOURCE_CP
    RESOURCE_CP = {}

    # 遍历文件夹结构，读取所有名称后缀为.png的文件，加入到字典中
    root_dir = os.path.join(PATHS["config"], 'cus_images')

    for root, dirs, files in os.walk(root_dir):
        # 对于每个子文件夹，创建对应的字典层级
        for c_dir in dirs:
            relative_path = os.path.relpath(os.path.join(root, c_dir), root_dir)
            add_to_resource_cus_img(relative_path, {})  # 创建字典层级，值可以设为None

        # 读取所有名称后缀为.png的文件，加入到字典中
        for file in files:
            if file.endswith(".png"):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, root_dir)
                img = im_read(file_path)
                add_to_resource_cus_img(relative_path, img)


"""RESOURCE_LOG_IMG 日志图片资源 由于会出现变动, 请务import .py而非单独的全局变量"""

RESOURCE_LOG_IMG = {}


def add_to_resource_log_img(relative_path, img):
    global RESOURCE_LOG_IMG
    current_level = RESOURCE_LOG_IMG

    path_parts = relative_path.split(os.sep)

    for part in path_parts[:-1]:
        if part not in current_level:
            current_level[part] = {}  # 初始化一个新的字典
        current_level = current_level[part]

    # 设置最终的图像数据
    current_level[path_parts[-1]] = img


def fresh_resource_log_img():
    # 清空
    global RESOURCE_LOG_IMG
    RESOURCE_LOG_IMG = {}

    # 遍历文件夹结构
    root_dir = os.path.join(PATHS["logs"], 'match_failed')

    for root, dirs, files in os.walk(root_dir):
        # 对于每个子文件夹，创建对应的字典层级
        for c_dir in dirs:
            relative_path = os.path.relpath(os.path.join(root, c_dir), root_dir)
            add_to_resource_log_img(relative_path, {})  # 创建字典层级，值可以设为None

        # 读取所有名称后缀为.png的文件，加入到字典中
        for file in files:
            if file.endswith(".png"):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, root_dir)
                img = im_read(file_path)
                add_to_resource_log_img(relative_path, img)


"""RESOURCE_B 战斗方案资源 由于会出现变动, 请务import .py而非单独的全局变量"""

RESOURCE_B = {}
RESOURCE_T = {}


def fresh_resource_b():
    # 清空
    global RESOURCE_B
    RESOURCE_B = {}
    for b_uuid, b_path in EXTRA.BATTLE_PLAN_UUID_TO_PATH.items():
        with EXTRA.FILE_LOCK:
            with open(file=b_path, mode='r', encoding='utf-8') as file:
                json_data = json.load(file)
        RESOURCE_B[b_uuid] = json_data


def fresh_resource_t():
    # 清空
    global RESOURCE_T
    RESOURCE_T = {}
    for b_uuid, b_path in EXTRA.TWEAK_BATTLE_PLAN_UUID_TO_PATH.items():
        with EXTRA.FILE_LOCK:
            with open(file=b_path, mode='r', encoding='utf-8') as file:
                json_data = json.load(file)
        RESOURCE_T[b_uuid] = json_data


fresh_resource_img()
fresh_resource_cus_img()
fresh_resource_log_img()

if __name__ == '__main__':
    print(RESOURCE_LOG_IMG)
    pass
