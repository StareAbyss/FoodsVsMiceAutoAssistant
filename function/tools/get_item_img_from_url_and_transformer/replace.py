import os

import cv2
import numpy as np

from function.get_paths import paths

path = paths["picture"]["item"] + "\\原始资源\\transformer"
img_all_list = os.listdir(path)

path = paths["picture"]["item"] + "\\战斗"
img_need_list = os.listdir(path)

for img_name in img_all_list:
    if img_name in img_need_list:
        # 读取
        path = paths["picture"]["item"] + "\\原始资源\\transformer\\" + img_name
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), -1)

        # 保存
        path = paths["picture"]["item"] + "\\战斗\\" + img_name
        cv2.imencode('.png', image)[1].tofile(path)
