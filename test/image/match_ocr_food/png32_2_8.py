import cv2
import numpy as np

# 读取32位PNG图像
img_32bit = cv2.imdecode(buf=np.fromfile('7.png', dtype=np.uint8), flags=-1)

# 转换为8位灰度图像
img_8bit_gray = cv2.cvtColor(img_32bit, cv2.COLOR_BGRA2GRAY)

# 保存转换后的8位灰度图像
cv2.imwrite('texts_matched/7.png', img_8bit_gray)
