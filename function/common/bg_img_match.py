import time

import cv2
import numpy as np

from function.common.bg_img_screenshot import capture_picture_png, png_cropping
from function.globals.init_resources import RESOURCE_P
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER


def match_p_in_w(
        raw_w_handle,  # 句柄
        raw_range: list,  # 原始图像生效的范围
        target_path,
        target_tolerance: float = 0.95
):
    """
    find target in template
    catch an image by a handle, find a smaller image(target) in this bigger one, return center relative position
    :param raw_w_handle: 窗口句柄
    :param raw_range: 原始图像生效的范围,为 [左上X, 左上Y,右下X, 右下Y], 右下位置超出范围取最大(不会报错)
    :param template: 目标图片的文件路径
    :param tolerance: 捕捉准确度阈值 0-1
    :param is_test: 仅单例测试使用, 显示匹配到的最右图像位置框

    Returns: 识别到的目标的中心坐标(相对于截图)
    """

    # 截取原始图像(windows窗口) BGRA -> BGR
    img_source = capture_picture_png(handle=raw_w_handle, raw_range=raw_range)
    img_source = img_source[:, :, :3]

    # 根据 路径 或者 numpy.array 选择是否读取
    if type(template) is np.ndarray:
        img_template = template
    else:
        # 读取目标图像,中文路径兼容方案
        img_template = cv2.imdecode(buf=np.fromfile(file=template, dtype=np.uint8), flags=-1)

    # 自定义的模板匹配
    result = match_template_with_optional_mask(img_source=img_source, img_template=img_template)
    (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(src=result)

    # 如果匹配度<阈值，就认为没有找到
    if minVal >= 1 - tolerance:
        return None

    # 最优匹配的左上坐标
    (start_x, start_y) = minLoc

    # 输出识别到的中心
    center_point = [
        start_x + int(img_template.shape[1] / 2),
        start_y + int(img_template.shape[0] / 2)
    ]

    # 测试时绘制边框
    if is_test:
        img_source = img_source.astype(np.uint8)
        # 确定起点和终点的(x，y)坐标边界框
        end_x = start_x + img_template.shape[1]
        end_y = start_y + img_template.shape[0]
        # 在图像上绘制边框
        cv2.rectangle(
            img=img_source,
            pt1=(start_x, start_y),
            pt2=(end_x, end_y),
            color=(0, 0, 255),
            thickness=1)
        # 显示输出图像
        cv2.imshow(
            winname="SourceImg.png",
            mat=img_source)
        cv2.waitKey(0)

    return center_point


def match_ps_in_w(
        raw_w_handle,  # 句柄
        target_opts: list,
        return_mode: str
):
    """
    一次截图中找复数的图片, 性能更高的写法
    :param raw_w_handle: 窗口句柄
    :param target_opts: [{"target_path":str,"raw_range":[x1:int,y1:int,x2:int,y2:int],"target_tolerance":float},...]
    :param return_mode: 模式 and 或者 or
    :return: 通过了mode, 则返回[{"x":int,"y":int},None,...] , 否则返回None
    """
    # 截屏
    raw_img = capture_picture_png(
        handle=raw_w_handle,
        raw_range=[0, 0, 10000, 10000])
    result_list = []

    for p in target_opts:

        raw_img_p = png_cropping(
            image=raw_img,
            raw_range=p["raw_range"])  # 裁剪
        target_path = p["target_path"]  # 目标路径
        target_tolerance = p["target_tolerance"]  # 目标精准度阈值

        if type(target_path) is np.ndarray:
            tar_img = target_path
        else:
            # 读取目标图像,中文路径兼容方案, (行,列,ABGR)
            tar_img = cv2.imdecode(
                np.fromfile(
                    file=target_path,
                    dtype=np.uint8),
                -1)

        # 执行模板匹配，采用的匹配方式cv2.TM_SQDIFF_NORMED
        result = cv2.matchTemplate(
            image=tar_img[:, :, :-1],
            templ=raw_img_p[:, :, :-1],
            method=cv2.TM_SQDIFF_NORMED)

        (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(src=result)

        # 如果匹配度小于X%，就认为没有找到
        if minVal > 1 - target_tolerance:
            result_list.append(None)
            continue

        # 最优匹配的左上坐标
        (start_x, start_y) = minLoc

        # 输出识别到的中心
        result_list.append(
            [
                start_x + int(tar_img.shape[1] / 2),
                start_y + int(tar_img.shape[0] / 2)
            ]
        )

    if return_mode == "and":
        if None in result_list:
            return None
        else:
            return result_list
    elif return_mode == "or":
        if all(i is None for i in result_list):
            return None
        else:
            return result_list


def loop_match_p_in_w(
        raw_w_handle,
        raw_range: list,
        target_path,
        target_tolerance: float = 0.95,
        target_interval: float = 0.2,
        target_failed_check: float = 10,
        target_sleep: float = 0.05,
        click: bool = True,
        click_now_path=None
):
    """
    catch a resource by a handle, find a smaller resource in the bigger one,
    click the center of the smaller one in the bigger one by handle(relative position)
    Args:
        :param raw_w_handle: 截图句柄
        :param raw_range: 截图后截取范围 [左上x,左上y,右下x,右下y]
        :param target_path: 目标图片路径
        :param target_tolerance: 捕捉准确度阈值 0-1
        :param target_interval: 捕捉图片的间隔
        :param target_failed_check: # 捕捉图片时间限制, 超时输出False
        :param target_sleep: 找到图/点击后 的休眠时间
        :param click: 是否点一下
        :param click_now_path: 点击后进行检查, 若能找到该图片, 视为无效, 不输出True, 继承前者的精准度tolerance

    return:
        是否在限定时间内找到图片

    """
    spend_time = 0.0
    while True:

        find_target = match_p_in_w(
            raw_w_handle=raw_w_handle,
            raw_range=raw_range,
            template=target_path,
            tolerance=target_tolerance)

        if find_target:

            if not click:
                time.sleep(target_sleep)

            else:
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=raw_w_handle,
                    x=find_target[0] + raw_range[0],
                    y=find_target[1] + raw_range[1]
                )
                time.sleep(target_sleep)

                if click_now_path:
                    find_target = match_p_in_w(
                        raw_w_handle=raw_w_handle,
                        raw_range=raw_range,
                        template=click_now_path,
                        tolerance=target_tolerance)
                    if find_target:
                        continue  # 当前状态没有产生变化, 就不进行输出

            return True

        # 超时, 查找失败
        time.sleep(target_interval)
        spend_time += target_interval
        if spend_time > target_failed_check:
            return False


def loop_match_ps_in_w(
        raw_w_handle,
        target_opts: list,
        target_return_mode: str,
        target_failed_check: float = 10,
        target_interval: float = 0.2,
):
    """
        :param raw_w_handle: 截图句柄
        :param target_opts: [{"target_path":str,"raw_range":[x1:int,y1:int,x2:int,y2:int],"target_tolerance":float},...]
        :param target_return_mode: 模式 and 或者 or
        :param target_interval: 捕捉图片的间隔
        :param target_failed_check: # 捕捉图片时间限制, 超时输出False
        :return: 通过了mode, 则返回[{"x":int,"y":int},None,...] , 否则返回None

        """
    # 截屏
    invite_time = 0.0
    while True:
        find_target = match_ps_in_w(raw_w_handle=raw_w_handle,
                                    target_opts=target_opts,
                                    return_mode=target_return_mode)
        if find_target:
            return True

        # 超时, 查找失败
        invite_time += target_interval
        time.sleep(target_interval)
        if invite_time > target_failed_check:
            return False


if __name__ == '__main__':
    from function.core.FAA import faa_get_handle


    def main():
        handle = faa_get_handle(channel="锑食", mode="browser")

        result = match_p_in_w(raw_w_handle=handle,
                              raw_range=[0, 0, 2000, 2000],
                              template=RESOURCE_P["common"]["顶部菜单"]["大地图.png"],
                              tolerance=0.87)

        print(result)
        result = (1, 2)
        if result:
            print(result[0], result[1])


    main()
