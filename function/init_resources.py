# 初始化资源，并放到字典里

from get_paths import paths
import cv2
import numpy as np
import os

class InitResource:
    def __init__(self):
        self.resource = {}
        # 遍历文件夹结构，读取所有名称后缀为.png的文件，加入到字典中
        root_dir = paths["root"] + "\\resource\\picture"
        
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if file.endswith(".png"):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, root_dir)
                    img = self.imread(file_path)
                    self.add_to_resource(relative_path, img)

    def imread(self, img_path):
        return cv2.imdecode(buf=np.fromfile(file=img_path, dtype=np.uint8), flags=-1)

    def add_to_resource(self, relative_path, img):
        path_parts = relative_path.split(os.sep)
        current_dict = self.resource
        for part in path_parts[:-1]:
            if part not in current_dict:
                current_dict[part] = {}
            current_dict = current_dict[part]
        current_dict[path_parts[-1]] = img