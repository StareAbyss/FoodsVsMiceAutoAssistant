import cv2
# 检查是否支持CUDA
if cv2.cuda.getCudaEnabledDeviceCount():
    print("检测到支持CUDA的设备数量:", cv2.cuda.getCudaEnabledDeviceCount())
else:
    print("未检测到支持CUDA的设备")

