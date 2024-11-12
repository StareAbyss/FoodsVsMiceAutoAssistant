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
    root_dir = PATHS["root"] + "\\resource\\image"

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
    root_dir = PATHS["config"] + "\\cus_images"

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
    root_dir = PATHS["logs"] + "\\match_failed"

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


def fresh_resource_b():
    # 清空
    global RESOURCE_B
    RESOURCE_B = {}
    for b_uuid, b_path in EXTRA.BATTLE_PLAN_UUID_TO_PATH.items():
        with EXTRA.FILE_LOCK:
            with open(file=b_path, mode='r', encoding='utf-8') as file:
                json_data = json.load(file)
        RESOURCE_B[b_uuid] = json_data


fresh_resource_img()
fresh_resource_cus_img()
fresh_resource_log_img()

if __name__ == '__main__':
    print(RESOURCE_LOG_IMG)
    pass
