import cv2
import numpy as np

from function.get_paths import paths

# 目标行
row = 2  # 1-5

# 目标列
column = 1  # 1-10

# 49*49 是战斗中截图的大小
target_path = paths["picture"]["item"] + "\\test_img.png"
image = cv2.imdecode(np.fromfile(target_path, dtype=np.uint8), -1)
image = image[49 * (row - 1):49 * row, 49 * (column - 1):49 * column]
cv2.imshow(winname="Capture Test.png", mat=image)
cv2.waitKey()

# 实际截图去除 可能出现数字的部分 和边角
# 38x29 用于比较 是保存的图片战斗中查找的目标
# image = image[3+1:32+1, 3+1:41+1]
image = image[4:33, 4:42]
cv2.imshow(winname="Capture Test.png", mat=image)
cv2.waitKey()
