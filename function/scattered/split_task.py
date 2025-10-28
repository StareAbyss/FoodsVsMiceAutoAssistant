import glob
import os

import cv2
import numpy as np

from function.common.bg_img_match import  match_p_in_w
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER



def create_or_load_puzzle_image(target_dir):
    """创建或加载拼图列表"""
    puzzle_path = os.path.join(target_dir, "puzzle_list.png")
    if os.path.exists(puzzle_path):
        return cv2.imread(puzzle_path)
    else:
        # 创建新的拼图列表
        return np.zeros((0, 0, 3), dtype=np.uint8)


def check_image_exists_in_puzzle(puzzle_image, segment):
    """使用match_p_in_w检查图片是否已存在于拼图列表中"""
    if puzzle_image is None:
        return False
    if puzzle_image.size == 0:
        return False  # 拼图列表为空，视为不存在

    # 设置参数用于match_p_in_w
    source_img = puzzle_image  # 使用拼图列表作为源图像
    source_range = [0, 0, source_img.shape[1], source_img.shape[0]]  # 源图像的全图范围
    tem=segment[4:26, :]
    # 使用match_p_in_w检查图片是否存在
    status_code, _ = match_p_in_w(
        template=tem,
        source_img=source_img,
        source_range=source_range,
        match_tolerance=0.985,
        test_print=True
    )

    # 状态码 2 表示匹配成功，即图片已存在
    return status_code == 2


def adjust_image_size(image, target_width, target_height):
    """调整图像尺寸以匹配目标尺寸"""
    if image.size == 0:
        return image  # 空图像直接返回

    # 创建目标尺寸的黑色背景图像
    result = np.zeros((target_height, target_width, 3), dtype=np.uint8)

    # 计算缩放比例（保持纵横比）
    scale_x = target_width / image.shape[1]
    scale_y = target_height / image.shape[0]
    scale = min(scale_x, scale_y)

    # 计算新的尺寸
    new_width = int(image.shape[1] * scale)
    new_height = int(image.shape[0] * scale)

    # 缩放图像
    resized_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)

    # 将缩放后的图像居中放置
    y_offset = (target_height - new_height) // 2
    x_offset = (target_width - new_width) // 2
    result[y_offset:y_offset + new_height, x_offset:x_offset + new_width] = resized_image

    return result


def add_to_puzzle_image(puzzle_image, segment):
    """将新图片拼接到拼图列表中"""
    # 强制转换为3通道BGR格式（特别处理alpha通道）
    if segment.shape[2] == 4 if len(segment.shape) == 3 else False:
        segment = cv2.cvtColor(segment, cv2.COLOR_BGRA2BGR)
    if puzzle_image is None:
        CUS_LOGGER.debug(f"创建与segment相同尺寸的空白拼图")
        # 创建与segment相同尺寸的空白拼图
        return segment.copy()  # 使用拷贝避免内存问题
    if puzzle_image.size == 0:
        CUS_LOGGER.debug(f"创建与segment相同尺寸的空白拼图")
        # 创建与segment相同尺寸的空白拼图
        return segment.copy()  # 使用拷贝避免内存问题


    # 获取尺寸
    puzzle_height, puzzle_width = puzzle_image.shape[:2]
    segment_height, segment_width = segment.shape[:2]

    CUS_LOGGER.debug(f"拼图尺寸: {puzzle_width}x{puzzle_height}, 段尺寸: {segment_width}x{segment_height}")


    # 垂直拼接图片
    try:
        result = cv2.vconcat([puzzle_image, segment])
        CUS_LOGGER.debug(f"拼接成功，新尺寸: {result.shape[1]}x{result.shape[0]}")
        return result
    except cv2.error as e:
        CUS_LOGGER.error(f"拼接失败: {str(e)}")
        return puzzle_image  # 拼接失败时返回原图


def save_puzzle_image(puzzle_image, target_dir):
    """保存拼图列表"""
    puzzle_path = os.path.join(target_dir, "puzzle_list.png")
    cv2.imwrite(puzzle_path, puzzle_image)


def detect_horizontal_edges(image):
    """
    检测图像中的水平边缘并分割

    参数:
        image: 图像
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
        puzzle_dir = PATHS["image"]["task"]["puzzle"]
        os.makedirs(target_dir, exist_ok=True)  # 确保目录存在
        os.makedirs(puzzle_dir, exist_ok=True)  # 确保目录存在

        existing_files = glob.glob(os.path.join(target_dir, "*.png"))
        puzzle_image = create_or_load_puzzle_image(puzzle_dir)
        file_count = len(existing_files)
        CUS_LOGGER.debug(f"文件已存在数{file_count}")
        # 分割图像
        for i in range(len(merged_lines) - 1):
            y_start = merged_lines[i]
            y_end = merged_lines[i + 1]

            if y_end > y_start:
                height = y_end - y_start

                # 新增处理逻辑
                if height < 28:
                    continue  # 舍去小于28的

                # 裁剪大于36的区域
                if height >= 36:
                    new_y_end = y_start + 29
                    segment = image[y_start:new_y_end, :]
                elif height >= 31:
                    segment = image[y_start+2:y_end, :]
                else:
                    segment = image[y_start:y_end, :]  # 保留原尺寸

                # 原有保存逻辑（排除首尾分段）
                if i >= 1 :
                    if not check_image_exists_in_puzzle(puzzle_image, segment):
                        # 如果不存在，保存并拼接
                        file_count += 1
                        output_path = os.path.join(target_dir, f"{file_count}.png")
                        cv2.imwrite(output_path, segment)
                        puzzle_image = add_to_puzzle_image(puzzle_image, segment)
        save_puzzle_image(puzzle_image, puzzle_dir)


def split_edge(image):
    """
    检测图像中的水平边缘并分割

    参数:
        image: 图像
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
        images_list=[]
        # 分割图像
        for i in range(len(merged_lines) - 1):
            y_start = merged_lines[i]
            y_end = merged_lines[i + 1]

            if y_end > y_start:
                height = y_end - y_start

                # 新增处理逻辑
                if height < 28:
                    continue  # 舍去小于28的

                # 裁剪大于36的区域
                if height >= 36:
                    new_y_end = y_start + 29
                    segment = image[y_start:new_y_end, :]
                elif height >= 31:
                    segment = image[y_start+2:y_end, :]
                else:
                    segment = image[y_start:y_end, :]  # 保留原尺寸

                # 原有保存逻辑（排除首尾分段）
                if i >= 1 :
                    images_list.append(segment)
        return images_list


def try_one():
    # 图像路径（用户可修改）
    image_path = "./test_image.png"  # 修改为你的图像路径
    try:
        image = cv2.imread(image_path)
        detect_horizontal_edges(image)
    except Exception as e:
        print(f"处理图像时发生错误：{str(e)}")


def load_tasks_from_db_and_create_puzzle(db_conn):
    """
    从数据库读取所有任务图像并创建拼图
    Args:
        db_conn: 数据库连接
    Returns:
        拼接后的图像
    """
    cursor = db_conn.cursor()
    cursor.execute("SELECT id, image_data FROM tasks")

    puzzle_dir = PATHS["image"]["task"]["puzzle"]
    os.makedirs(puzzle_dir, exist_ok=True)

    # 初始化拼图
    puzzle_image = np.zeros((0, 0, 3), dtype=np.uint8)

    # 逐个添加图像
    for task_id, image_data in cursor.fetchall():
        if image_data:
            # 将bytes转换为OpenCV图像
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is not None:
                puzzle_image = add_to_puzzle_image(puzzle_image, image)

    # 保存最终拼图
    save_puzzle_image(puzzle_image, puzzle_dir)
    return puzzle_image