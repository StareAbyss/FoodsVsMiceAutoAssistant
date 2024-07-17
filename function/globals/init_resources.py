import os

import cv2
import numpy as np

from function.globals.get_paths import PATHS

RESOURCE_P = {}
RESOURCE_CP = {}
RESOURCE_B = {}


def im_read(img_path):
    return cv2.imdecode(buf=np.fromfile(file=img_path, dtype=np.uint8), flags=-1)


def add_to_resource_p(relative_path, img):
    global RESOURCE_P
    path_parts = relative_path.split(os.sep)
    current_level = RESOURCE_P
    for part in path_parts[:-1]:
        if part not in current_level:
            current_level[part] = {}
        current_level = current_level[part]
    current_level[path_parts[-1]] = img


def fresh_resource_i():
    # 遍历文件夹结构，读取所有名称后缀为.png的文件，加入到字典中
    root_dir = PATHS["root"] + "\\resource\\picture"

    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".png"):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, root_dir)
                img = im_read(file_path)
                add_to_resource_p(relative_path, img)


def add_to_resource_cp(relative_path, img):
    global RESOURCE_CP
    path_parts = relative_path.split(os.sep)
    current_level = RESOURCE_CP
    for part in path_parts[:-1]:
        if part not in current_level:
            current_level[part] = {}
        current_level = current_level[part]
    current_level[path_parts[-1]] = img


def fresh_resource_ci():
    # 遍历文件夹结构，读取所有名称后缀为.png的文件，加入到字典中
    root_dir = PATHS["config"] + "\\cus_images"

    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".png"):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, root_dir)
                img = im_read(file_path)
                add_to_resource_cp(relative_path, img)



if __name__ == '__main__':
    image = RESOURCE_P["common"]["任务_完成.png"]
    cv2.imshow('Image', image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
