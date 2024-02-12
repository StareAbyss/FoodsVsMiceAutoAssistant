import os

import cv2
import numpy as np

from function.get_paths import paths

# 目标行
row = 3  # 1-5

# 目标列
column = 3  # 1-10

path = paths["picture"]["item"] + "\\原始资源\\3"
img_name_list = os.listdir(path)

for name in img_name_list:
    # 实际图片 44x44
    path = paths["picture"]["item"] + "\\原始资源\\3\\" + name
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), -1)

    # 实际截图去除 可能出现数字的部分 和边角
    # 38x29 用于比较 是保存的图片战斗中查找的目标
    image = image[3:32, 3:41]
    path = paths["picture"]["item"] + "\\战斗\\" + name
    cv2.imencode('.png', image)[1].tofile(path)

    # cv2.imshow(winname="Capture Test.png", mat=image)
    # cv2.waitKey()
