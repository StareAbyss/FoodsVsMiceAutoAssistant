import os

import cv2
import numpy as np

from function.globals.get_paths import PATHS

# 目标行
row = 3  # 1-5

# 目标列
column = 3  # 1-10

path = PATHS["picture"]["item"] + "\\原始资源\\2"
img_name_list = os.listdir(path)

for name in img_name_list:
    # 实际图片 44x44
    path = PATHS["picture"]["item"] + "\\原始资源\\2\\" + name
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), -1)

    # 实际截图去除 可能出现数字的部分 和边角
    # 30x36 用于比较 是保存的图片战斗中查找的目标
    image = image[4:-4, 4:-10]

    # 保存
    path = PATHS["picture"]["item"] + "\\原始资源\\transformer\\" + name
    cv2.imencode('.png', image)[1].tofile(path)

    # cv2.imshow(winname="Capture Test.png", mat=image)
    # cv2.waitKey()
