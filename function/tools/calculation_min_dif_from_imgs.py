import os

import cv2
import numpy as np

from function.globals.get_paths import PATHS

# 定义路径
path = PATHS["picture"]["card"] + "\\状态判定"

# 读取路径下所有图像文件
images = []
for filename in os.listdir(path):
    if filename.endswith(".png"):  # 支持的图像格式
        img_path = os.path.join(path, filename)
        img = cv2.imdecode(buf=np.fromfile(file=img_path, dtype=np.uint8), flags=-1)
        if img is not None:
            images.append(img)
        else:
            print(f"无法读取图像: {filename}")

# 确保至少有两张图像
if len(images) < 2:
    print("需要至少两张图像来进行比较")
    exit()

# 计算所有图像之间对应位置像素的三通道差值的绝对值之和
height, width, _ = images[0].shape
min_sums = {}  # 初始化最小和值数组

# 将图片的数字转化为int32 而非int8 防止做减法溢出
images = [arr.astype(np.int32) for arr in images]

# 遍历每个像素位置
for x in range(width):
    min_sums[x] = {}
    for y in range(height):
        min_sums[x][y] = 255
        # 计算该位置所有图像组合的差值绝对值之和
        for i in range(len(images)):
            for j in range(i + 1, len(images) - i):
                diff_sum = np.sum(abs(images[i][y, x] - images[j][y, x]))
                min_sums[x][y] = min(min_sums[x][y], diff_sum)

# 输出每个坐标的最小和值
for y in range(height):
    for x in range(width):
        print(f"坐标({y}, {x})的最小和值: {min_sums[x][y]}")
