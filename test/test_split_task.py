import glob
import os

import cv2
import matplotlib
import numpy as np
import matplotlib.pyplot as plt
from function.globals.get_paths import PATHS

# 设置中文字体和解决负号显示问题
plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
plt.rcParams['axes.unicode_minus'] = False  # 正常显示负号
matplotlib.use('TkAgg')


def detect_horizontal_edges(image):
    """
    检测图像中的水平边缘并可视化

    参数:
        image_path: 图像文件路径
    """

    # 转换为灰度图
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 使用 Sobel 算子检测水平边缘
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    abs_sobelx = np.absolute(sobelx)
    scaled_sobel = np.uint8(255 * abs_sobelx / np.max(abs_sobelx))

    # 二值化处理
    thresh_min = 20
    thresh_max = 100
    binary_output = np.zeros_like(scaled_sobel)
    binary_output[(scaled_sobel >= thresh_min) & (scaled_sobel <= thresh_max)] = 255

    # 霍夫变换检测直线
    lines = cv2.HoughLinesP(binary_output, rho=1, theta=np.pi / 180, threshold=100, minLineLength=100, maxLineGap=50)

    # 绘制检测到的直线
    line_image = np.copy(image)
    horizontal_lines = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]

            # 过滤非水平线：计算斜率并设置阈值
            dx = x2 - x1
            dy = y2 - y1
            if dx == 0:
                continue  # 排除垂直线

            slope = abs(dy / dx)
            if slope > 0.1:  # 斜率大于0.1的非水平线过滤掉（tan(5.7°)=0.1）
                continue

            # 保存水平线
            horizontal_lines.append(y1)
            cv2.line(line_image, (x1, y1), (x2, y2), (0, 0, 255), 5)  # 使用红色绘制水平线

    # 图像分割逻辑
    if horizontal_lines:
        # 去重并排序
        unique_y = sorted(set(horizontal_lines))

        # 合并过于接近的线（距离小于10像素）
        merged_lines = []
        threshold = 10  # 合并阈值
        for y in sorted(unique_y):
            if not merged_lines or y - merged_lines[-1] > threshold:
                merged_lines.append(y)
            else:
                # 合并相邻线：取平均值
                merged_lines[-1] = (merged_lines[-1] + y) // 2

        # 添加图像顶部和底部作为分割边界
        image_height = image.shape[0]
        merged_lines = [0] + merged_lines + [image_height]

        target_dir = PATHS["image"]["task"]["chaos"]
        os.makedirs(target_dir, exist_ok=True)  # 确保目录存在

        existing_files = glob.glob(os.path.join(target_dir, "*.png"))
        file_count = len(existing_files)
        # 分割图像
        for i in range(len(merged_lines) - 1):
            y_start = merged_lines[i]
            y_end = merged_lines[i + 1]

            # 忽略高度为0的区域
            if y_end > y_start:
                segment = image[y_start:y_end, :]

                # 保存图像（去除前两张）
                if i >= 2 and i!=len(merged_lines) - 2:  # 跳过前两个分割区域
                    file_count += 1
                    output_path = os.path.join(target_dir, f"{file_count}.png")
                    cv2.imwrite(output_path, segment)

    # 显示结果
    plt.figure(figsize=(15, 6))

    plt.subplot(1, 3, 1)
    plt.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    plt.title('原始图像')
    plt.axis('off')

    plt.subplot(1, 3, 2)
    plt.imshow(binary_output, cmap='gray')
    plt.title('水平边缘检测')
    plt.axis('off')

    plt.subplot(1, 3, 3)
    plt.imshow(cv2.cvtColor(line_image, cv2.COLOR_BGR2RGB))
    plt.title('霍夫变换检测水平直线')
    plt.axis('off')

    plt.tight_layout()

    plt.show()
    plt.close()


def test_test():
    # 图像路径（用户可修改）
    image_path = "./test_image.png"  # 修改为你的图像路径
    try:
        image = cv2.imread(image_path)
        detect_horizontal_edges(image)
    except Exception as e:
        print(f"处理图像时发生错误：{str(e)}")
