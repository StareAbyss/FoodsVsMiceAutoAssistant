import json
import os
import threading
import time
from ctypes import windll, byref, c_ubyte
from ctypes.wintypes import RECT, HWND
from time import sleep
from typing import Union

import cv2
import numpy as np
import win32api
import win32con
import win32gui
from PyQt6.QtCore import QObject, pyqtSignal
from numpy import uint8, frombuffer


def _input_str(handle, input: str, interval_time=0.05):
    """向窗口中输入字符串"""
    for ch in input:
        win32gui.PostMessage(handle, win32con.WM_CHAR, ord(ch), 0)
        sleep(0.05)


"""
新版点击函数集成
"""


def extension_do_left_mouse_click(handle, x, y):
    """执行动作函数 子函数"""
    x = int(x)
    y = int(y)
    point = win32api.MAKELONG(x, y)
    # 对于部分窗口，win32con.MK_LBUTTON也可以写为0，但有的窗口必须写，否则会无法正常点击
    win32api.PostMessage(handle, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, point)
    win32api.PostMessage(handle, win32con.WM_LBUTTONUP, 0, point)


def extension_do_left_mouse_move_to(handle, x, y):
    """执行动作函数 子函数"""
    x = int(x)
    y = int(y)
    windll.user32.PostMessageW(handle, 0x0200, 0, y << 16 | x)


"""
坐标转换增强函数
"""


def extension_get_scaling_factor():
    """获取窗口缩放比例（处理高DPI）"""
    hdc = windll.user32.GetDC(0)
    # 获取屏幕的水平DPI
    my_dpi = windll.gdi32.GetDeviceCaps(hdc, 88)  # 88 is the index for LOGPIXELSX
    windll.user32.ReleaseDC(0, hdc)
    return my_dpi / 96.0


"""
窗口操作函数
"""


def extension_get_window_handle(name):
    """增强版窗口查找函数"""
    source_root_handle = win32gui.FindWindow(None, name)
    if source_root_handle == 0:
        # 尝试枚举窗口
        def callback(source_root_handle, extra):
            if win32gui.GetWindowText(source_root_handle) == name:
                extra.append(source_root_handle)

        handles = []
        win32gui.EnumWindows(callback, source_root_handle)
        if handles:
            return handles[0]
        print(f"未找到标题为 '{name}' 的窗口")
        raise Exception(f"未找到标题为 '{name}' 的窗口")
    handle = win32gui.FindWindowEx(source_root_handle, None, "TabContentWnd", "")
    handle = win32gui.FindWindowEx(handle, None, "CefBrowserWindow", "")
    handle = win32gui.FindWindowEx(handle, None, "Chrome_WidgetWin_0", "")
    handle = win32gui.FindWindowEx(handle, None, "WrapperNativeWindowClass", "")
    handle = win32gui.FindWindowEx(handle, None, "NativeWindowClass", "")
    if not handle:
        handle = source_root_handle
    return source_root_handle, handle


"""
截图和识图函数, 进行了一些魔改
"""


def extension_capture_image_png_once(handle: HWND):
    # 获取窗口客户区的大小
    r = RECT()
    windll.user32.GetClientRect(handle, byref(r))  # 获取指定窗口句柄的客户区大小
    width, height = r.right, r.bottom  # 客户区宽度和高度

    # 创建设备上下文
    dc = windll.user32.GetDC(handle)  # 获取窗口的设备上下文
    cdc = windll.gdi32.CreateCompatibleDC(dc)  # 创建一个与给定设备兼容的内存设备上下文
    bitmap = windll.gdi32.CreateCompatibleBitmap(dc, width, height)  # 创建兼容位图
    windll.gdi32.SelectObject(cdc, bitmap)  # 将位图选入到内存设备上下文中，准备绘图

    # 执行位块传输，将窗口客户区的内容复制到内存设备上下文中的位图
    windll.gdi32.BitBlt(cdc, 0, 0, width, height, dc, 0, 0, 0x00CC0020)

    # 准备缓冲区，用于接收位图的像素数据
    total_bytes = width * height * 4  # 计算总字节数，每个像素4字节（RGBA）
    buffer = bytearray(total_bytes)  # 创建字节数组作为缓冲区
    byte_array = c_ubyte * total_bytes  # 定义C类型数组类型

    # 从位图中获取像素数据到缓冲区
    windll.gdi32.GetBitmapBits(bitmap, total_bytes, byte_array.from_buffer(buffer))

    # 清理资源
    windll.gdi32.DeleteObject(bitmap)  # 删除位图对象
    windll.gdi32.DeleteObject(cdc)  # 删除内存设备上下文
    windll.user32.ReleaseDC(handle, dc)  # 释放窗口的设备上下文

    # 将缓冲区数据转换为numpy数组，并重塑为图像的形状 (高度,宽度,[B G R A四通道])
    image = frombuffer(buffer, dtype=uint8).reshape(height, width, 4)
    # return cv2.cvtColor(image, cv2.COLOR_RGBA2RGB) # 这里比起FAA原版有一点修改，在返回前先做了图像处理
    return image  # 原版


def extension_restore_window_if_minimized(handle) -> bool:
    """
    :param handle: 类名为DUIWindow句柄
    :return: 如果是最小化, 并恢复至激活窗口的底层, 则返回True, 否则返回False.
    """

    # 检查窗口是否最小化
    if win32gui.IsIconic(handle):
        # 恢复窗口（但不会将其置于最前面）
        win32gui.ShowWindow(handle, win32con.SW_RESTORE)

        # 将窗口置于Z序的底部，但不改变活动状态
        win32gui.SetWindowPos(handle, win32con.HWND_BOTTOM, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
        return True
    return False


def extension_apply_dpi_scaling(x, y, scale_factor=1.0):
    """
    对坐标应用 DPI 缩放，并返回缩放后的坐标。

    参数:
        x (int): x 坐标
        y (int): y 坐标
        scale_factor (float): 缩放比，默认为1.0

    返回:
        scaled_x,scaled_y 
    """

    scaled_x = int(x * scale_factor)
    scaled_y = int(y * scale_factor)
    return scaled_x, scaled_y


def extension_png_cropping(image, raw_range: list = None):
    """
    裁剪图像
    :param image:
    :param raw_range: [左上X, 左上Y,右下X, 右下Y]
    :return:
    """
    if raw_range is None:
        return image
    return image[raw_range[1]:raw_range[3], raw_range[0]:raw_range[2], :]


def extension_is_mostly_black(image, sample_points=9):
    """
    检查图像是否主要是黑色, 通过抽样像素来判断, 能减少占用.
    :param image: NumPy数组表示的图像.
    :param sample_points: 要检查的像素点数, 默认为9.
    :return: 如果抽样的像素都是黑色,则返回True; 否则返回False.
    """
    if image.size == 0:
        return True
    height, width = image.shape[:2]

    # 定义要检查的像素位置
    positions = [
        (0, 0),
        (0, width - 1),
        (height - 1, 0),
        (height - 1, width - 1),
        (height // 2, width // 2),
        (0, width // 2),
        (height // 2, 0),
        (height - 1, width // 2),
        (height // 2, width - 1)
    ]

    # 仅使用前sample_points个位置
    positions = positions[:sample_points]

    # 检查每个位置的像素是否都是黑色
    for y, x in positions:
        if np.any(image[y, x] != 0):  # 如果任何一个像素不是全黑
            return False
    return True


def extension_capture_image_png(handle: HWND, raw_range: list, root_handle: HWND = None):
    """
    窗口客户区截图
    Args:
        handle (HWND): 要截图的窗口句柄
        raw_range: 裁剪, 为 [左上X, 左上Y,右下X, 右下Y], 右下位置超出范围取最大(不会报错)
        root_handle: 根窗口句柄, 用于检查窗口是否最小化, 如果最小化则尝试恢复至激活窗口的底层 可空置

    Returns:
        numpy.array: 截图数据 3D array (高度,宽度,[B G R A四通道])
    """

    # 尝试截图一次
    image = extension_capture_image_png_once(handle=handle)

    # image == [], 句柄错误, 返回一个对应大小的全0图像
    if image is None:
        return np.zeros((raw_range[3] - raw_range[1], raw_range[2] - raw_range[0], 3), dtype=np.uint8)

    # 检查是否为全黑 如果全0 大概率是最小化了
    if extension_is_mostly_black(image=image, sample_points=9):
        # 检查窗口是否最小化
        if root_handle:
            # 尝试恢复至激活窗口的底层
            if extension_restore_window_if_minimized(handle=root_handle):
                # 如果恢复成功, 再次尝试截图一次
                image = extension_capture_image_png_once(handle=handle)

    # 裁剪图像到指定区域
    image = extension_png_cropping(image=image, raw_range=raw_range)

    return image


def extension_mask_transform_color_to_black(mask, quick_method=True) -> np.ndarray:
    """
    将掩模板处理 把非白色都变黑色 三通道->单通道
    如果使用quick_method 将直接取 第一个颜色通道, 这要求使用的手动掩模为 的前三通道是黑白的(每个像素的BGR值都相等)
    """

    if not quick_method:
        # 创建一个布尔掩码,标记出所有非白色像素
        non_white_mask = (mask[:, :, :3] != [255, 255, 255]).any(axis=2)
        # 将非白色像素的RGB值设置为黑色
        mask[non_white_mask] = [0, 0, 0]

    # 保留一个通道
    return mask[:, :, 0]


def extension_match_template_with_optional_mask(source, template, mask=None, quick_method=True,
                                                test_show=False) -> np.ndarray:
    """
    使用可选掩模进行模板匹配-从源图搜索模板, 步骤如下.
    1. 生成 mask_from_template 将根据template图像是否存在Alpha通道, 取颜色为纯白的部分作为掩模纯白, 其他色均为黑.
    2. 处理 mask 根据输入的参数mask, 如果mask不为None的处理, 则将mask作为原始掩模, 否则将mask_from_template作为原始掩模.
    3. 如果 mask 不为None, 取颜色为纯白的部分作为掩模纯白, 其他色均为黑, 但保留其Alpha通道.
    4. 如果 mask 不为None, 将 mask和mask_from_template 合并, 若mask Alpha通道为255 该像素取mask, 否则取mask_from_template.
    5. 调用 cv2.matchTemplate 进行匹配, 并返回匹配结果.

    Args:
        :param source: numpy.ndarray 源图像. 3 or 4通道 会处理至3通道再匹配.
        :param template: numpy.ndarray 模板图像，可能包含Alpha通道作为掩模.
        :param mask: 原始掩模. 四通道图像, 透明区域将不生效, 掩模需要与template的大小完全一致.
        :param quick_method: 快速匹配方法, 取mask的第一个颜色通道作快速处理, 要求mask的前三通道是黑白的(每个像素的BGR值都相等)
        :param test_show: 测试显示
    Returns:
        numpy.ndarray: 匹配结果.

    """

    """
    函数:对应方法 匹配良好输出->匹配不好输出
    CV_TM_SQDIFF:平方差匹配法 [1]->[0]；
    CV_TM_SQDIFF_NORMED:归一化平方差匹配法 [0]->[1]；
    CV_TM_CCORR:相关匹配法 [较大值]->[0]；
    CV_TM_CCORR_NORMED:归一化相关匹配法 [1]->[0]；
    CV_TM_CCOEFF:系数匹配法；
    CV_TM_CCOEFF_NORMED:归一化相关系数匹配法 [1]->[0]->[-1]
    """
    method = cv2.TM_SQDIFF_NORMED

    # 确保源图像的长度和宽度均大于模板, 否则报错 输出源大小和目标大小
    if source.shape[0] < template.shape[0] or source.shape[1] < template.shape[1]:
        print(f"图像识别模块 - 源图像小于目标大小, 产生致命错误! 源图像大小: {source.shape} 目标大小: {template.shape}")

    # 确保source为三通道
    if source.shape[2] == 4:
        source = source[:, :, :3]

    if template.shape[2] == 4:

        # 提取Alpha通道作为掩模 单通道
        mask_from_template = template[:, :, 3]

        # 以254分割, 即白色->白色 灰色和黑色->黑色 即 透明区域完全不识别, 而不是作为权重
        _, mask_from_template = cv2.threshold(mask_from_template, 254, 255, cv2.THRESH_BINARY)

        # 模板图像包含Alpha通道
        if test_show:
            cv2.imshow(winname="template", mat=template)
            cv2.imshow(winname="mask_from_template", mat=mask_from_template)
            cv2.waitKey(0)

        # 移除Alpha通道，保留RGB部分
        template = template[:, :, :3]
    else:
        # 否则以纯白等大小单通道图像 作为掩模
        mask_from_template = np.ones((template.shape[:2]), dtype=np.uint8) * 255

    if (mask is not None) and (template.shape[0] == mask.shape[0]) and (template.shape[1] == mask.shape[1]):
        # 如果有原始的掩模 且掩模与template大小一致

        if mask.shape[2] == 3:
            # 有三个通道 RGB的掩模 直接覆盖识别template的透明度得到的mask

            # 处理彩色为黑白 (三通道->单通道, 非白色均视为黑色)
            mask = extension_mask_transform_color_to_black(mask=mask, quick_method=quick_method)

        else:
            # 有四个通道 RGBA的掩模

            # 获取PNG图像的Alpha通道
            mask_alpha_channel = mask[:, :, 3]
            # 以254分割, 即白色->白色 灰色和黑色->黑色 即 透明区域完全不识别, 而不是作为权重
            _, mask_alpha_channel = cv2.threshold(mask_alpha_channel, 254, 255, cv2.THRESH_BINARY)

            # 去除Alpha通道 处理彩色为黑白 (三通道->单通道, 非白色均视为黑色)
            mask = extension_mask_transform_color_to_black(mask=mask[:, :, :3], quick_method=quick_method)

            # 根据mask保留的阿尔法通道, 在其透明的区域, 取mask_from_template的对应区域进行合并
            mask[mask_alpha_channel != 255] = mask_from_template[mask_alpha_channel != 255]

    else:
        # 没有默认掩模或和template大小不一而不使用掩模
        result = cv2.matchTemplate(image=source, templ=template, method=method)
        return result

    if test_show:
        cv2.imshow(winname="final_mask", mat=mask)
        cv2.waitKey(0)

    # 检查掩模是否为纯白
    if np.all(mask == 255):
        # 对于不包含Alpha通道或Alpha通道为纯白的情况，直接进行匹配
        result = cv2.matchTemplate(image=source, templ=template, method=method)
        return result
    else:
        # 掩模非纯白，使用掩模进行匹配
        result = cv2.matchTemplate(image=source, templ=template, method=method, mask=mask)
        return result


def extension_match_p_in_w(
        template,
        source_handle=None,
        source_root_handle=None,
        source_img=None,
        source_range=None,
        mask=None,
        match_tolerance: float = 0.95,
        return_center=True,
        test_print=False,
        test_show=True,
        template_name="Unknown",
) -> Union[None, list]:
    """
    find target in template
    catch an image by a handle, find a smaller image(target) in this bigger one, return center relative position
    :param template: 目标图片的文件路径或numpy.ndarray
    :param source_handle: 窗口句柄, 用以获取图像
    :param source_root_handle: 根窗口句柄, 用于检查窗口是否最小化, 如果最小化则尝试恢复至激活窗口的底层, 默认不取则不检查
    :param source_img: 取代截图, 直接输入图片, 优先级更高. 至少RGB三个通道. 该参数和source_handle至少输入一个.
    :param source_range: 原始图像生效的范围,为 [左上X, 左上Y,右下X, 右下Y], 右下位置超出范围取最大(不会报错), 在输入图像模式下, 默认None不裁剪, 从全图匹配, 截图模式下必须手动输入.
    :param mask: 目标图片掩模, 若为None, 则不使用掩模
    :param match_tolerance: 捕捉准确度阈值 0-1
    :param return_center: 是否返回中心坐标, 否则返回左上坐标
    :param test_print: 仅单例测试使用, 显示匹配到的最右图像位置框
    :param test_show: 是否展示识别结果, 仅单例测试使用, 显示匹配到的最右图像位置框
    :param template_name: 目标图像名称, 用于test_print
    Returns: list[x:int, y:int] 目标的坐标
    """

    if source_img is None and source_handle is None:
        raise ValueError("source_img and source_handle can not be None at the same time")

    # 截取原始图像(windows窗口) 否则读取窗口截图
    if source_img is None:
        source_img = extension_capture_image_png(handle=source_handle, raw_range=source_range,
                                                 root_handle=source_root_handle)
    else:
        source_img = extension_png_cropping(image=source_img, raw_range=source_range)
    # 若为BGRA -> BGR
    source_img = source_img[:, :, :3]
    # cv2.imshow('a',source_img)
    # cv2.waitKey(0)

    # 根据 路径 或者 numpy.array 选择是否读取
    if type(template) is not np.ndarray:
        # 未规定输出名称
        if template_name == "Unknown" and test_print:
            template_name = template
        # 读取目标图像,中文路径兼容方案
        template = cv2.imdecode(buf=np.fromfile(file=template, dtype=np.uint8), flags=-1)

    # print(f"即将识图, size_source{source_img.shape},size_template：{template.shape}")

    # 自定义的复杂模板匹配
    result = extension_match_template_with_optional_mask(source=source_img, template=template, mask=mask)
    (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(src=result)

    # 如果匹配度<阈值，就认为没有找到
    matching_degree = 1 - minVal
    if matching_degree <= match_tolerance:
        if test_print:
            print(
                f"识别目标:{template_name}, 匹配度:{matching_degree}, 目标阈值:{match_tolerance}, 结果:失败")
        return None

    # 最优匹配的左上坐标
    (start_x, start_y) = minLoc

    # 输出识别到的中心
    center_point = [
        start_x + int(template.shape[1] / 2),
        start_y + int(template.shape[0] / 2)
    ]
    if test_print:
        print(f"识别目标:{template_name}, 匹配度:{matching_degree}, 目标阈值:{match_tolerance}, 结果:成功")

    # 测试时绘制边框
    if test_show:
        source_img = source_img.astype(np.uint8)
        # 确定起点和终点的(x，y)坐标边界框
        end_x = start_x + template.shape[1]
        end_y = start_y + template.shape[0]
        # 在图像上绘制边框
        cv2.rectangle(img=source_img, pt1=(start_x, start_y), pt2=(end_x, end_y), color=(0, 0, 255), thickness=1)
        # 绘制边框中心点
        cv2.circle(source_img, center_point, 2, (0, 0, 255), -1)
        # # 显示输出图像
        # cv2.imshow(winname="SourceImg.png", mat=source_img)
        # cv2.waitKey(0)
        return [center_point[0], center_point[1], source_img]
    return center_point

    # 弃用，全改为中心点，偏移让用户自己算
    # if return_center:
    #     return center_point
    # else:
    #     return [start_x, start_y]


def extension_loop_match_p_in_w(
        source_handle,
        source_range: list,
        template,
        template_mask=None,
        match_tolerance: float = 0.95,
        match_interval: float = 0.2,
        match_failed_check: float = 10,
        after_sleep: float = 0.05,
        click: bool = True,
        click_handle=None,
        after_click_template=None,
        after_click_template_mask=None,
        source_root_handle=None,
        offset_enabled=False,
        offset_x=0,
        offset_y=0,
        event_stop=None,
        test=False,
        point=[-1, -1]
) -> bool:
    """
    根据句柄截图, 并在截图中寻找一个较小的图片资源.
    可选: 根据句柄 点击 较小图片所在位置.
    可选: 点击后是否复核为另一图片(切换界面成功). 如果未找到仍会返回False.
    Args:
        :param source_handle: 截图句柄
        :param source_range: 截图后截取范围 [左上x,左上y,右下x,右下y]
        :param template: 目标图片. 路径或数组. 注意需要在100%缩放比下截图，类型需要为png
        :param template_mask: 可选: 目标图片掩模, 为None则不启用.
        :param match_tolerance: 可选: 自定捕捉准确度阈值 0-1, 默认0.95
        :param match_interval: 可选: 自定捕捉图片的间隔, 默认0.2, 单位秒. 不采用系统时钟, 而是直接加算. 填0会导致无限查找不终止直到找到.
        :param match_failed_check: 可选: 自定捕捉图片时间限制, 超时输出False. 默认10, 单位秒. 流程上会先识图, 识图失败加算时间判定超时, 故此处为0仍会识图1次.
        :param after_sleep: 找到图 / 失败后 / 点击后(如果点击) / 复核(如果复核) 后的休眠时间
        :param click: 是否点一下
        :param click_handle: 是否启用不一样的点击句柄
        :param after_click_template: 点击后进行检查, 若能找到该图片, 视为无效, 不输出True, 继承前者的 tolerance interval (如果要检查的话可以传和template一样的参数)
        :param after_click_template_mask: 检查 - 掩模
        :param source_root_handle: 根窗口句柄, 用于检查窗口是否最小化, 如果最小化则尝试恢复至激活窗口的底层 可空置

    return:
        是否在限定时间内找到图片
    """
    spend_time = 0.0
    while True:
        if event_stop and event_stop.is_set():
            return
        find_target = extension_match_p_in_w(
            source_handle=source_handle,
            source_range=source_range,
            template=template,
            mask=template_mask,
            match_tolerance=match_tolerance,
            source_root_handle=source_root_handle,
            test_show=test,
            test_print=test,
        )
        if find_target:
            break
        else:
            # 若超时, 查找失败
            time.sleep(match_interval)
            spend_time += match_interval
            if spend_time > match_failed_check:
                time.sleep(after_sleep)
                return False

    if not click:
        time.sleep(after_sleep)
        return True
    x = find_target[0] + source_range[0]
    y = find_target[1] + source_range[1]
    point[0] = x
    point[1] = y
    if offset_enabled:
        x += offset_x
        y += offset_y

    if test:
        # # 显示输出图像
        # 绘制偏移后的点
        cv2.circle(find_target[2], (x, y), 2, (0, 0, 255), -1)

        cv2.imshow(winname="SourceImg.png", mat=find_target[2])
        cv2.waitKey(0)

    extension_do_left_mouse_click(source_handle, x, y)

    if after_click_template is None:
        # 不需要检查是否切换到另一个界面
        time.sleep(after_sleep)
        return True

    while True:
        find_after_target = extension_match_p_in_w(
            source_handle=source_handle,
            source_range=source_range,
            template=after_click_template,
            mask=after_click_template_mask,
            match_tolerance=match_tolerance,
            source_root_handle=source_root_handle)
        if find_after_target:
            break
        else:
            # 若超时, 查找失败
            time.sleep(match_interval)
            spend_time += match_interval
            if spend_time > match_failed_check:
                time.sleep(after_sleep)
                return False

    time.sleep(after_sleep)
    return True


def extension_execute(window_name, configs_path, need_test=False, event_stop=None):
    """执行自动化脚本流程"""
    source_root_handle, handle = extension_get_window_handle(window_name)
    if not handle:
        # print("获取窗口句柄失败，请检查窗口名是否设置正确")
        return

    with open(configs_path, "r", encoding="utf-8") as f:
        configs = json.load(f)

    for step_config in configs:
        # 获取当前步骤配置参数

        # 执行匹配点击操作
        if event_stop and event_stop.is_set():
            return

        after_click_template = None

        # 点击后校验，暂时弃用
        # if step_config["check_enabled"]:
        #     after_click_template=step_config["template_path"]

        if not os.path.exists(step_config["template_path"]):
            print(f"图片【{step_config["template_path"]}】不存在，请检查图片路径")
            return
        point = [-1, -1]
        result = extension_loop_match_p_in_w(
            source_handle=handle,
            source_root_handle=source_root_handle,
            match_tolerance=step_config["tolerance"],
            template=step_config["template_path"],
            match_interval=step_config["interval"],
            match_failed_check=step_config["timeout"],
            source_range=step_config["source_range"],
            after_click_template=after_click_template,
            after_sleep=step_config["after_sleep"],
            offset_enabled=step_config["check_offset_enabled"],
            offset_x=step_config["offset_x"],
            offset_y=step_config["offset_y"],
            click=step_config["need_click"],
            event_stop=event_stop,
            test=need_test,
            point=point
        )
        x = point[0]
        y = point[1]
        if result:
            print(f"识别图片【{step_config['template_path']}】成功")
        else:
            print(f"识别图片【{step_config['template_path']}】失败")

        # 点击后输入内容
        _input_str(handle, step_config["click_input"])

        # 最后运行代码
        if step_config["check_run_code"]:
            exec(step_config["code"])

        # def click(x, y, test=False):
        #     """给用户插入代码时用的点击函数"""
        #     if test:
        #         point = (x, y)
        #         source_img = extension_capture_image_png_once(handle)
        #         cv2.circle(source_img, point, 5, (0, 0, 255), -1)
        #         cv2.imshow("result", source_img)
        #         cv2.waitKey(0)
        #     extension_do_left_mouse_click(handle, x, y)
        #
        # def input_str(string: str):
        #     """给用户插入代码时用的输入函数"""
        #     _input_str(handle, string)


class ExecuteThread(threading.Thread, QObject):
    """
    用于执行脚本的线程类，执行完成后会弹出提示框，使用多线程是为了保证ui窗口不被阻塞。
    
    继承QObject是为了使用 PyQt 的信号槽机制，从而实现线程间通信（尤其是子线程与主线程的 GUI 交互），
    因为Qt限制了只能在主线程使用消息框，因此要用信号槽机制来实现消息框提示
    """
    # 定义一个信号，用于传递消息，注意不能写在__init__函数里
    # 因为：
    # PyQt 的信号是通过 元类（MetaClass） 和 类属性声明 实现的。
    # 当你在类作用域中声明 pyqtSignal 时，PyQt 的元类会在类定义阶段自动处理这些信号，将它们转换为合法的信号对象，并赋予它们 emit() 和 connect() 等方法。
    # 而如果信号定义在 __init__ 中：
    # 它们会成为 实例属性，而非类属性。
    # PyQt 的元类无法在类定义阶段捕获和处理这些信号。
    # 最终生成的信号对象只是一个普通的 pyqtSignal 包装器，不具备 connect 或 emit 功能。
    message_signal = pyqtSignal(str, str)

    def __init__(self, window_name, configs_path, loop_times, need_test=False):
        # 显式调用所有父类构造函数
        QObject.__init__(self)
        threading.Thread.__init__(self)
        self.window_name = window_name
        self.configs_path = configs_path
        self.loop_times = loop_times
        self.need_test = need_test
        self._event_stop = threading.Event()  #标志位，用来安全中断线程

    def run(self):
        start_time = time.time()
        for i in range(self.loop_times):
            if self._event_stop.is_set():  # 安全退出
                self.message_signal.emit("失败", "脚本执行已被中断")
                return
            print(f"第{i + 1}次执行中")
            extension_execute(self.window_name, self.configs_path, self.need_test, self._event_stop)
        self.message_signal.emit("成功", "脚本执行已完成")
        end_time = time.time()
        print(f"执行完毕，共花费 {end_time - start_time} 秒")

    def stop(self):
        """安全停止线程"""
        self._event_stop.set()


if __name__ == "__main__":
    # 测试识图效果
    def test():
        # 获取窗口信息
        source_root_handle, handle = extension_get_window_handle("美食大战老鼠")
        result = extension_loop_match_p_in_w(
            source_handle=handle,
            source_range=[0, 0, 2000, 2000],
            template='2.png',  # 目标图片，即需要点击的区域

            match_tolerance=0.95,
            match_interval=0.5,
            match_failed_check=5,
            after_sleep=5,
            click=True)
        print(result)

    code_str = """extension_execute("美食大战老鼠",'点击qq头像.json',need_test=True)"""
    exec(code_str)
