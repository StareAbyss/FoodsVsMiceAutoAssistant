import cv2
import numpy as np

from function.get_paths import paths

# 目标行
row = 2  # 1-5

# 目标列
column = 1  # 1-10

# 49*49 是战斗中截图的大小
target_path = paths["logs"] + "\\img.png"
image = cv2.imdecode(np.fromfile(target_path, dtype=np.uint8), -1)
image = image[49 * (row - 1):49 * row, 49 * (column - 1):49 * column]
cv2.imshow(winname="Capture Test.png", mat=image)
cv2.waitKey()

# 实际截图去除 可能出现数字的部分 和边角
# 44x44
image = image[1:-4, 1:-4]
# 30x36
image = image[4:-4, 4:-10]
# tip 合并起来就是 [5:41,5:35]
cv2.imshow(winname="Capture Test.png", mat=image)
cv2.waitKey()

path = "test.png"
cv2.imencode('.png', image)[1].tofile(path)