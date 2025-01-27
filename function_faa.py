from ctypes import windll, byref, c_ubyte
from ctypes.wintypes import RECT, HWND
import win32con, win32gui
import cv2
from numpy import uint8, frombuffer
import numpy as np

# ---------------------- 新版点击函数集成 ----------------------
def do_left_mouse_click( handle, x, y):
    """执行动作函数 子函数"""
    x = int(x )
    y = int(y )
    windll.user32.PostMessageW(handle, 0x0201, 0, y << 16 | x)
    windll.user32.PostMessageW(handle, 0x0202, 0, y << 16 | x)

def do_left_mouse_move_to( handle, x, y):
    """执行动作函数 子函数"""
    x = int(x )
    y = int(y )
    windll.user32.PostMessageW(handle, 0x0200, 0, y << 16 | x)



# ---------------------- 坐标转换增强函数 ----------------------
def get_scaling_factor():
    """获取窗口缩放比例（处理高DPI）"""
    hdc = windll.user32.GetDC(0)
    # 获取屏幕的水平DPI
    my_dpi = windll.gdi32.GetDeviceCaps(hdc, 88)  # 88 is the index for LOGPIXELSX
    windll.user32.ReleaseDC(0, hdc)
    return my_dpi / 96.0


# ---------------------- 窗口操作函数 ----------------------
def get_window_handle(name):
    """增强版窗口查找函数"""
    source_root_handle = win32gui.FindWindow('DUIWindow', name)
    if source_root_handle == 0:
        # 尝试枚举窗口
        def callback(source_root_handle, extra):
            if win32gui.GetWindowText(source_root_handle) == name:
                extra.append(source_root_handle)
        handles = []
        win32gui.EnumWindows(callback, source_root_handle)
        if handles:
            return handles[0]
        raise Exception(f"未找到标题为 '{name}' 的窗口")
    handle = win32gui.FindWindowEx(source_root_handle, None, "TabContentWnd", "")
    handle = win32gui.FindWindowEx(handle, None, "CefBrowserWindow", "")      
    handle = win32gui.FindWindowEx(handle, None, "Chrome_WidgetWin_0", "")  
    handle = win32gui.FindWindowEx(handle, None, "WrapperNativeWindowClass", "")  
    handle = win32gui.FindWindowEx(handle, None, "NativeWindowClass", "")  
    return source_root_handle,handle

# ---------------------- 截图函数（保持原样）----------------------
def capture_image_png_once(handle: HWND):
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
    return image # 原版

# ---------------------- 图像匹配函数（增加可视化）----------------------
def match_template(source_img, template_path, match_threshold=0.9):
    template = cv2.imread(template_path)
    if template is None:
        raise Exception(f"无法读取模板图像: {template_path}")
    
    h, w = template.shape[:2]
    result = cv2.matchTemplate(source_img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    
    if max_val < match_threshold:
        return None, source_img
    
    top_left = max_loc
    center = (top_left[0] + w//2, top_left[1] + h//2)
    
    # 增强可视化标记
    marked_img = source_img.copy()
    cv2.rectangle(marked_img, top_left, (top_left[0]+w, top_left[1]+h), (0,255,0), 2)
    cv2.circle(marked_img, center, 5, (0,0,255), -1)
    cv2.putText(marked_img, f"Confidence: {max_val:.2f}", (10,30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,0,0), 2)
    
    return center, marked_img

def restore_window_if_minimized(handle) -> bool:
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


def apply_dpi_scaling(x,y,scale_factor=1.0):
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
    return scaled_x,scaled_y



def match_and_click(handle,img_path:str,test:bool=True):
    '''匹配图片并进行点击'''
    
    # 激活窗口
    restore_window_if_minimized(handle)
    
    # 获取缩放比
    scale_factor = get_scaling_factor()
    # print(f"检测到缩放比例: {scale_factor:.2f}x")
    
    # 截图
    img = capture_image_png_once(handle)
    
    # 图像匹配
    target_pos, result_img = match_template(img, img_path, 0.9)
    if test:
        cv2.imshow('result',result_img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
    # 添加匹配失败处理
    if target_pos is None:
        print(f"⚠️ 未匹配到图片 {img_path}，跳过点击")
        return
    # 应用缩放
    scaled_x,scaled_y=apply_dpi_scaling(target_pos[0],target_pos[1],scale_factor)
    
    # 执行点击操作
    do_left_mouse_click(handle, scaled_x, scaled_y)



def png_cropping(image, raw_range: list = None):
    """
    裁剪图像
    :param image:
    :param raw_range: [左上X, 左上Y,右下X, 右下Y]
    :return:
    """
    if raw_range is None:
        return image
    return image[raw_range[1]:raw_range[3], raw_range[0]:raw_range[2], :]



def is_mostly_black(image, sample_points=9):
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



def capture_image_png(handle: HWND, raw_range: list, root_handle: HWND = None):
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
    image = capture_image_png_once(handle=handle)

    # image == [], 句柄错误, 返回一个对应大小的全0图像
    if image is None:
        return np.zeros((raw_range[3] - raw_range[1], raw_range[2] - raw_range[0], 3), dtype=np.uint8)

    # 检查是否为全黑 如果全0 大概率是最小化了
    if is_mostly_black(image=image, sample_points=9):
        # 检查窗口是否最小化
        if root_handle:
            # 尝试恢复至激活窗口的底层
            if restore_window_if_minimized(handle=root_handle):
                # 如果恢复成功, 再次尝试截图一次
                image = capture_image_png_once(handle=handle)

    # 裁剪图像到指定区域
    image = png_cropping(image=image, raw_range=raw_range)

    return image


def mask_transform_color_to_black(mask, quick_method=True) -> np.ndarray:
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



def match_template_with_optional_mask(source, template, mask=None, quick_method=True, test_show=False) -> np.ndarray:
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
            mask = mask_transform_color_to_black(mask=mask, quick_method=quick_method)

        else:
            # 有四个通道 RGBA的掩模

            # 获取PNG图像的Alpha通道
            mask_alpha_channel = mask[:, :, 3]
            # 以254分割, 即白色->白色 灰色和黑色->黑色 即 透明区域完全不识别, 而不是作为权重
            _, mask_alpha_channel = cv2.threshold(mask_alpha_channel, 254, 255, cv2.THRESH_BINARY)

            # 去除Alpha通道 处理彩色为黑白 (三通道->单通道, 非白色均视为黑色)
            mask = mask_transform_color_to_black(mask=mask[:, :, :3], quick_method=quick_method)

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







from typing import Union

def match_p_in_w(
        template,
        source_handle=None,
        source_root_handle=None,
        source_img=None,
        source_range=None,
        mask=None,
        match_tolerance: float = 0.95,
        return_center=True,
        test_print=False,
        test_show=False,
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
        source_img = capture_image_png(handle=source_handle, raw_range=source_range, root_handle=source_root_handle)
    else:
        source_img = png_cropping(image=source_img, raw_range=source_range)
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
    result = match_template_with_optional_mask(source=source_img, template=template, mask=mask)
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
        # 显示输出图像
        cv2.imshow(winname="SourceImg.png", mat=source_img)
        cv2.waitKey(0)

    if return_center:
        return center_point
    else:
        return [start_x, start_y]

import time

def loop_match_p_in_w(
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
        :param after_click_template: 点击后进行检查, 若能找到该图片, 视为无效, 不输出True, 继承前者的 tolerance interval
        :param after_click_template_mask: 检查 - 掩模
        :param source_root_handle: 根窗口句柄, 用于检查窗口是否最小化, 如果最小化则尝试恢复至激活窗口的底层 可空置

    return:
        是否在限定时间内找到图片
    """
    spend_time = 0.0
    while True:

        find_target = match_p_in_w(
            source_handle=source_handle,
            source_range=source_range,
            template=template,
            mask=template_mask,
            match_tolerance=match_tolerance,
            source_root_handle=source_root_handle,
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

    do_left_mouse_click(source_handle,find_target[0] + source_range[0],find_target[1] + source_range[1])

    if after_click_template is None:
        # 不需要检查是否切换到另一个界面
        time.sleep(after_sleep)
        return True

    while True:
        find_after_target = match_p_in_w(
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

import json
from time import sleep
def load_config(config_path):
    """读取JSON配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)
    
    
def execute(window_name, configs_path):
    """执行自动化脚本流程"""
    source_root_handle,handle=get_window_handle(window_name)
    configs=load_config(configs_path)
    for step_config in configs:
        # 获取当前步骤配置参数
        template_path = step_config["template_path"]
        after_sleep = step_config["after_sleep"]
        template = cv2.imdecode(buf=np.fromfile(file=template_path, dtype=np.uint8), flags=-1)
        # 执行匹配点击操作
        # match_and_click(handle, template_path)
        loop_match_p_in_w(source_handle=handle,match_tolerance=0.95,template=template,source_range=[0, 0, 2000, 2000],source_root_handle=source_root_handle)
        # 执行后等待
        sleep(after_sleep)


# 测试识图效果
def test():
    # 获取窗口信息
    source_root_handle,handle=get_window_handle("美食大战老鼠")
    result=loop_match_p_in_w(
        source_handle=handle,
        source_range=[0, 0, 2000, 2000],
        template='2.png', # 目标图片，即需要点击的区域
        
        match_tolerance=0.95,
        match_interval=0.5,
        match_failed_check=5,
        after_sleep=5,
        click=True)
    print(result)

    
# # ---------------------- 主程序 ----------------------
if __name__ == "__main__":
    execute("美食大战老鼠",'1111.json')