import cv2
import win32gui
from time import sleep
from function_common.background_mouse import mouse_left_down, mouse_left_up, mouse_left_click
from function_common.background_screenshot import capture_picture_png


def find_p_in_p(handle, target_path: str, tolerance: float = 0.95):
    """
    find target in template
    catch a resource by a handle, find a smaller resource in this bigger one(relative position)

    Args:
        handle: 窗口句柄
        target_path: 目标图片的文件路径
        tolerance: 捕捉准确度阈值 0-1

    Returns: 识别到的目标的中心坐标(相对于截图)

    """
    template = capture_picture_png(handle)
    target = cv2.imread(target_path, cv2.IMREAD_UNCHANGED)  # 读取带透明度
    # 执行模板匹配，采用的匹配方式cv2.TM_SQDIFF_NORMED
    result = cv2.matchTemplate(target, template, cv2.TM_SQDIFF_NORMED)
    (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(result)

    # 如果匹配度小于85%，就认为没有找到
    if minVal > 1 - tolerance:
        return None

    # 最优匹配的左上坐标
    (start_x, start_y) = minLoc

    # 测试时绘制边框
    if __name__ == '__main__':
        # 确定起点和终点的（x，y）坐标边界框
        end_x = start_x + target.shape[1]
        end_y = start_y + target.shape[0]
        # 在图像上绘制边框
        cv2.rectangle(template, (start_x, start_y), (end_x, end_y), (255, 255, 0), 3)
        # 显示输出图像
        cv2.imshow("Output", template)
        cv2.waitKey(0)

    # 输出识别到的中心
    return [start_x + int(target.shape[1] / 2), start_y + int(target.shape[0] / 2)]


def loop_find_p_in_p_ml_click(
        handle,  # 句柄
        target: str,  # 目标图片
        tolerance: float = 0.95,  # 捕捉准确度阈值
        l_i_time: float = 0.2,  # argument loop interval time 每次捕捉图片循环的间隔
        change_per: float = 1.0,  # 缩放比例
        c_i_time: float = 0.05,  # argument click interval time点击时的按下和抬起的间隔
        sleep_time: float = 0.05,  # 点击后的休眠时间
        click: bool = True  # 是否点一下
):
    """
    catch a resource by a handle, find a smaller resource in the bigger one,
    click the center of the smaller one in the bigger one by handle(relative position)
    Args:
        handle: 句柄
        target: 目标图片路径
        tolerance: 捕捉准确度阈值 0-1
        l_i_time: loop interval time 每次捕捉图片循环的间隔
        change_per: 缩放比例
        c_i_time: click interval time 点击时的按下和抬起的间隔
        sleep_time: 点击后的休眠时间
        click: 是否点一下

    Returns:

    """
    while True:
        a = find_p_in_p(handle, target, tolerance=tolerance)

        if a:
            if click:
                mouse_left_click(handle, int(a[0] * change_per), int(a[1] * change_per), c_i_time, sleep_time)
            break
        sleep(l_i_time)


if __name__ == '__main__':
    def main():
        # handle = win32gui.FindWindow("WTWindow", "枫叶V  唯一群号77419971       Alt+F2键 显示/隐藏 辅助")
        # handle = win32gui.FindWindowEx(handle, None, "CPageControl", "")
        # handle = win32gui.FindWindowEx(handle, None, "WTWindow", "")
        # handle = win32gui.FindWindowEx(handle, None, None, "")
        # handle = win32gui.FindWindowEx(handle, None, "MacromediaFlashPlayerActiveX", "")

        # handle = win32gui.FindWindow("ApolloRuntimeContentWindow", "美食大战老鼠 双线1服 提拉米苏")

        handle = win32gui.FindWindow("DUIWindow", None)
        handle = win32gui.FindWindowEx(handle, None, "TabContentWnd", "")
        handle = win32gui.FindWindowEx(handle, None, "CefBrowserWindow", "")
        handle = win32gui.FindWindowEx(handle, None, "Chrome_WidgetWin_0", "")
        handle = win32gui.FindWindowEx(handle, None, "WrapperNativeWindowClass", "")
        handle = win32gui.FindWindowEx(handle, None, "NativeWindowClass", "")
        print(handle)
        a = find_p_in_p(handle, "find_needed.png")
        print(a)
        if a:
            a[0] = int(a[0] * 1.5)
            a[1] = int(a[1] * 1.5)
            print(a)
            mouse_left_down(handle, a[0], a[1])
            mouse_left_up(handle, a[0], a[1])


    main()
