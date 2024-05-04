import cv2
import numpy as np

# 读取底层图片和顶层图片
bottom_img = cv2.imdecode(buf=np.fromfile(file='template.png', dtype=np.uint8), flags=-1)
top_img = cv2.imdecode(buf=np.fromfile(file='角标-物品44x44.png', dtype=np.uint8), flags=-1)


# 创建一个掩码，用于找出顶层图片中所有非透明的像素
# 顶层图片的alpha通道不为0的地方即为非透明
mask = top_img[:, :, 3] == 255

# 将顶层图片中非透明的像素复制到底层图片对应位置
# 对于RGBA图像，我们需要处理所有四个通道
for c in range(0, 3):
    bottom_img[:, :, c][mask] = top_img[:, :, c][mask]
# 将合并后的图片所有像素的Alpha通道值设置为255（完全不透明）
bottom_img[:, :, 3] = 255
# 保存合并后的图片
cv2.imwrite('template_lock.png', bottom_img)