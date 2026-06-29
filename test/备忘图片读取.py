import cv2
import numpy as np

# 中文路径读取
img_path = "xxx.png"
img = cv2.imdecode(buf=np.fromfile(file=img_path, dtype=np.uint8), flags=-1)

# 中文路径保存
img_path = "xxx.png"
cv2.imencode(ext=".png", img=img)[1].tofile(img_path)
