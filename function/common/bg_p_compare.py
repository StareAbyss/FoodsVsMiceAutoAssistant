from time import sleep

from cv2 import imread, IMREAD_UNCHANGED, TM_SQDIFF_NORMED, minMaxLoc, matchTemplate

from function.common.bg_mouse import mouse_left_click
from function.common.bg_p_screenshot import capture_picture_png
from function.get_paths import paths


def find_p_in_w(
        raw_w_handle,  # 句柄
        raw_range: list,  # 原始图像生效的范围
        target_path: str,
        target_tolerance: float = 0.95
):
    """
    find target in template
    catch an image by a handle, find a smaller image(target) in this bigger one, return center relative position

    :param raw_w_handle: 窗口句柄
    :param raw_range: 原始图像生效的范围,为 [左上X, 左上Y,右下X, 右下Y], 右下位置超出范围取最大(不会报错)
    :param target_path: 目标图片的文件路径
    :param target_tolerance: 捕捉准确度阈值 0-1

    Returns: 识别到的目标的中心坐标(相对于截图)


    """
    raw_img = capture_picture_png(handle=raw_w_handle, raw_range=raw_range)  # 截取原始图像(windows窗口)
    tar_img = imread(filename=target_path, flags=IMREAD_UNCHANGED)  # 读取目标图像, 带透明度

    # 执行模板匹配，采用的匹配方式cv2.TM_SQDIFF_NORMED, 仅匹配BGR不匹配A
    """
    函数:对应方法-匹配良好输出->匹配不好输出
    CV_TM_SQDIFF:平方差匹配法 [1]->[0]；
    CV_TM_SQDIFF_NORMED:归一化平方差匹配法 [0]->[1]；
    CV_TM_CCORR:相关匹配法 [较大值]->[0]；
    CV_TM_CCORR_NORMED:归一化相关匹配法 [1]->[0]；
    CV_TM_CCOEFF:系数匹配法；
    CV_TM_CCOEFF_NORMED:归一化相关系数匹配法 [1]->[0]->[-1]
    """
    result = matchTemplate(image=tar_img[:, :, :-1], templ=raw_img[:, :, :-1], method=TM_SQDIFF_NORMED)
    (minVal, maxVal, minLoc, maxLoc) = minMaxLoc(src=result)

    # 如果匹配度小于85%，就认为没有找到
    if minVal > 1 - target_tolerance:
        return None

    # 最优匹配的左上坐标
    (start_x, start_y) = minLoc

    # 测试时绘制边框
    # if __name__ == '__main__':
    #     # 确定起点和终点的(x，y)坐标边界框
    #     end_x = start_x + tar_img.shape[1]
    #     end_y = start_y + tar_img.shape[0]
    #     # 在图像上绘制边框
    #     rectangle(img=raw_img, pt1=(start_x, start_y), pt2=(end_x, end_y), color=(0, 0, 255), thickness=1)
    #     # 显示输出图像
    #     imshow(winname="Output.jpg", mat=raw_img)
    #     waitKey(0)

    # 输出识别到的中心
    return [start_x + int(tar_img.shape[1] / 2), start_y + int(tar_img.shape[0] / 2)]


def find_ps_in_w(
        raw_w_handle,  # 句柄
        raw_range: list,  # 原始图像生效的范围
        target_opts: list,
        return_mode: str
):
    """
    :param raw_w_handle: 窗口句柄
    :param raw_range: 原始图像生效的范围,为 [左上X, 左上Y,右下X, 右下Y], 右下位置超出范围取最大(不会报错)
    :param target_opts: [{"target_path":value, "target_tolerance":value},...]
    :param return_mode: 模式 and 或者 or
    :return: 通过了mode, 则返回[{"x":int,"y":int},None,...] , 否则返回None
    """
    # 截屏
    raw_img = capture_picture_png(handle=raw_w_handle, raw_range=raw_range)
    result_list = []

    for p in target_opts:

        target_path = p["target_path"]
        target_tolerance = p["target_tolerance"]
        tar_img = imread(filename=target_path, flags=IMREAD_UNCHANGED)  # 读取目标图像, 带透明度

        # 执行模板匹配，采用的匹配方式cv2.TM_SQDIFF_NORMED
        result = matchTemplate(image=tar_img[:, :, :-1], templ=raw_img[:, :, :-1], method=TM_SQDIFF_NORMED)
        (minVal, maxVal, minLoc, maxLoc) = minMaxLoc(src=result)

        # 如果匹配度小于X%，就认为没有找到
        if minVal > 1 - target_tolerance:
            result_list.append(None)
            continue

        # 最优匹配的左上坐标
        (start_x, start_y) = minLoc

        # 输出识别到的中心
        result_list.append([start_x + int(tar_img.shape[1] / 2), start_y + int(tar_img.shape[0] / 2)])

    if return_mode == "and":
        if None in result_list:
            return None
        else:
            return result_list

    if return_mode == "or":
        if all(i is None for i in result_list):
            return None
        else:
            return result_list


def loop_find_p_in_w(
        raw_w_handle,
        raw_range: list,
        target_path: str,
        target_tolerance: float = 0.95,
        target_interval: float = 0.2,
        target_failed_check: float = 10,
        target_sleep: float = 0.05,
        click: bool = True,
        click_interval: float = 0.05,  # argument click interval time
        click_zoom: float = 1.0,
        click_now_path=None
):
    """
    catch a resource by a handle, find a smaller resource in the bigger one,
    click the center of the smaller one in the bigger one by handle(relative position)
    Args:
        :param raw_w_handle: 截图句柄
        :param raw_range: 截图后截取范围
        :param target_path: 目标图片路径
        :param target_tolerance: 捕捉准确度阈值 0-1
        :param target_interval: 捕捉图片的间隔
        :param target_failed_check: # 捕捉图片时间限制, 超时输出False
        :param target_sleep: 找到图/点击后 的休眠时间
        :param click: 是否点一下
        :param click_interval: click interval 点击时的按下和抬起的间隔
        :param click_zoom: 缩放比例, 用于点击
        :param click_now_path: 点击后进行检查, 若能找到该图片, 视为无效, 不输出True, 继承前者的精准度tolerance

    return:
        是否在限定时间内找到图片

    """
    invite_time = 0.0
    while True:
        find_target = find_p_in_w(raw_w_handle=raw_w_handle,
                                  raw_range=raw_range,
                                  target_path=target_path,
                                  target_tolerance=target_tolerance)
        if find_target:
            if not click:
                sleep(target_sleep)
            else:
                mouse_left_click(handle=raw_w_handle,
                                 x=int(find_target[0] * click_zoom),
                                 y=int(find_target[1] * click_zoom),
                                 interval_time=click_interval,
                                 sleep_time=target_sleep)
                if click_now_path:
                    find_target = find_p_in_w(raw_w_handle=raw_w_handle,
                                              raw_range=raw_range,
                                              target_path=click_now_path,
                                              target_tolerance=target_tolerance)
                    if find_target:
                        continue  # 当前状态没有产生变化, 就不进行输出
            return True

        # 超时, 查找失败
        sleep(target_interval)
        invite_time += target_interval
        if invite_time > target_failed_check:
            return False


def loop_find_ps_in_w(
        raw_w_handle,
        raw_range: list,
        target_opts: list,
        target_return_mode: str,
        target_failed_check: float = 10,
        target_interval: float = 0.2,
):
    """
        :param raw_w_handle: 截图句柄
        :param raw_range: 截图后截取范围
        :param target_opts: [{"target_path":value, "target_tolerance":value},...]
        :param target_return_mode: 模式 and 或者 or
        :param target_interval: 捕捉图片的间隔
        :param target_failed_check: # 捕捉图片时间限制, 超时输出False
        :return: 通过了mode, 则返回[{"x":int,"y":int},None,...] , 否则返回None

        """
    # 截屏
    invite_time = 0.0
    while True:
        find_target = find_ps_in_w(raw_w_handle=raw_w_handle,
                                   raw_range=raw_range,
                                   target_opts=target_opts,
                                   return_mode=target_return_mode)
        if find_target:
            return True

        # 超时, 查找失败
        invite_time += target_interval
        sleep(target_interval)
        if invite_time > target_failed_check:
            return False


if __name__ == '__main__':
    from function.script.service.common import faa_get_handle


    def main():
        # handle = faa_get_handle("锑食")
        handle = faa_get_handle("深渊之下 | 锑食")
        target_path = paths["picture"]["common"] + "\\bottom_menu_goto_arena.png"
        result = loop_find_p_in_w(raw_w_handle=handle,
                                  raw_range=[0, 0, 950, 600],
                                  target_path=target_path,
                                  target_sleep=1,
                                  target_failed_check=2,
                                  click=True,
                                  click_zoom=1.5)
        # result = find_p_in_w(raw_w_handle=handle,
        #                      raw_range=[0, 0, 950, 600],
        #                      target_path=target_path)
        print(result)


    main()
