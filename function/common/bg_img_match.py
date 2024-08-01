import time
from typing import Union

import cv2
import numpy as np

from function.common.bg_img_screenshot import capture_image_png, png_cropping
from function.globals import init_resources
from function.globals.log import CUS_LOGGER
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER


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
            mask = mask_transform_color_to_black(mask=mask,quick_method=quick_method)

        else:
            # 有四个通道 RGBA的掩模

            # 获取PNG图像的Alpha通道
            mask_alpha_channel = mask[:, :, 3]
            # 以254分割, 即白色->白色 灰色和黑色->黑色 即 透明区域完全不识别, 而不是作为权重
            _, mask_alpha_channel = cv2.threshold(mask_alpha_channel, 254, 255, cv2.THRESH_BINARY)

            # 去除Alpha通道 处理彩色为黑白 (三通道->单通道, 非白色均视为黑色)
            mask = mask_transform_color_to_black(mask=mask[:, :, :3],quick_method=quick_method)

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


def match_p_in_w(
        source_handle,
        source_range: list,
        template,
        mask=None,
        template_name="Unknown",
        match_tolerance: float = 0.95,
        test_print=False,
        test_show=False,
        source_root_handle=None,
        return_center=True,
) -> Union[None, list]:
    """
    find target in template
    catch an image by a handle, find a smaller image(target) in this bigger one, return center relative position
    :param source_handle: 窗口句柄
    :param source_range: 原始图像生效的范围,为 [左上X, 左上Y,右下X, 右下Y], 右下位置超出范围取最大(不会报错)
    :param template: 目标图片的文件路径或numpy.ndarray
    :param template_name: 目标图像名称, 用于test_print
    :param mask: 目标图片掩模, 若为None, 则不使用掩模
    :param match_tolerance: 捕捉准确度阈值 0-1
    :param test_print: 仅单例测试使用, 显示匹配到的最右图像位置框
    :param test_show: 是否展示识别结果, 仅单例测试使用, 显示匹配到的最右图像位置框
    :param source_root_handle: 根窗口句柄, 用于检查窗口是否最小化, 如果最小化则尝试恢复至激活窗口的底层 可空置

    Returns: 识别到的目标的中心坐标(相对于截图区域左上)
    """

    # 截取原始图像(windows窗口) BGRA -> BGR
    img_source = capture_image_png(handle=source_handle, raw_range=source_range, root_handle=source_root_handle)
    img_source = img_source[:, :, :3]

    # 根据 路径 或者 numpy.array 选择是否读取
    if type(template) is not np.ndarray:
        # 未规定输出名称
        if template_name is "Unknown" and test_print is True:
            template_name = template
        # 读取目标图像,中文路径兼容方案
        template = cv2.imdecode(buf=np.fromfile(file=template, dtype=np.uint8), flags=-1)

    # 自定义的复杂模板匹配
    result = match_template_with_optional_mask(source=img_source, template=template, mask=mask)
    (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(src=result)

    # 如果匹配度<阈值，就认为没有找到
    matching_degree = 1 - minVal
    if matching_degree <= match_tolerance:
        if test_print:
            CUS_LOGGER.debug(
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
        CUS_LOGGER.debug(f"识别目标:{template_name}, 匹配度:{matching_degree}, 目标阈值:{match_tolerance}, 结果:成功")
    # 测试时绘制边框
    if test_show:
        img_source = img_source.astype(np.uint8)
        # 确定起点和终点的(x，y)坐标边界框
        end_x = start_x + template.shape[1]
        end_y = start_y + template.shape[0]
        # 在图像上绘制边框
        cv2.rectangle(img=img_source, pt1=(start_x, start_y), pt2=(end_x, end_y), color=(0, 0, 255), thickness=1)
        # 显示输出图像
        cv2.imshow(winname="SourceImg.png", mat=img_source)
        cv2.waitKey(0)

    if return_center:
        return center_point
    else:
        return [start_x,start_y]


def match_ps_in_w(
        source_handle,
        template_opts: list,
        return_mode: str,
        source_root_handle=None) -> Union[None, list]:
    """
    一次截图中找复数的图片, 性能更高的写法
    :param source_handle: 窗口句柄
    :param template_opts: [{"template":str,"source_range": [x1:int,y1:int,x2:int,y2:int],"match_tolerance":float},...]
    :param return_mode: 模式 and 或者 or
    :param source_root_handle: 根窗口句柄, 用于检查窗口是否最小化, 如果最小化则尝试恢复至激活窗口的底层 可空置
    :return: 通过了mode, 则返回[{"x":int,"y":int},None,...] , 否则返回None

    """
    # 截屏
    source_img = capture_image_png(handle=source_handle, raw_range=[0, 0, 3000, 3000], root_handle=source_root_handle)
    result_list = []

    for p in template_opts:

        source_range = png_cropping(image=source_img, raw_range=p["source_range"])  # 裁剪
        template = p["template"]  # 目标
        match_tolerance = p["match_tolerance"]  # 目标精准度阈值

        if type(template) is np.ndarray:
            template_img = template
        else:
            # 读取目标图像,中文路径兼容方案, (行,列,ABGR)
            template_img = cv2.imdecode(
                np.fromfile(
                    file=template,
                    dtype=np.uint8),
                -1)

        # 执行模板匹配，采用的匹配方式cv2.TM_SQDIFF_NORMED
        result = cv2.matchTemplate(
            image=source_range[:, :, :-1],
            templ=template_img[:, :, :-1],
            method=cv2.TM_SQDIFF_NORMED)

        (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(src=result)

        # 如果匹配度小于X%，就认为没有找到
        if minVal > 1 - match_tolerance:
            result_list.append(None)
            continue

        # 最优匹配的左上坐标
        (start_x, start_y) = minLoc

        # 输出识别到的中心
        result_list.append(
            [
                start_x + int(template_img.shape[1] / 2),
                start_y + int(template_img.shape[0] / 2)
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
    catch a resource by a handle, find a smaller resource in the bigger one,
    click the center of the smaller one in the bigger one by handle(relative position)
    Args:
        :param source_handle: 截图句柄
        :param source_range: 截图后截取范围 [左上x,左上y,右下x,右下y]
        :param template: 目标图片路径
        :param template_mask: 目标图片掩模, 若为None, 则不使用掩模
        :param match_tolerance: 捕捉准确度阈值 0-1
        :param match_interval: 捕捉图片的间隔
        :param match_failed_check: # 捕捉图片时间限制, 超时输出False
        :param after_sleep: 找到图/点击后 的休眠时间
        :param click: 是否点一下
        :param click_handle: 是否启用不一样的点击句柄
        :param after_click_template: 点击后进行检查, 若能找到该图片, 视为无效, 不输出True, 继承前者的精准度tolerance
        :param after_click_template_mask: 检查掩模
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
            source_root_handle=source_root_handle)

        if find_target:

            if not click:
                time.sleep(after_sleep)

            else:
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=click_handle if click_handle else source_handle,
                    x=find_target[0] + source_range[0],
                    y=find_target[1] + source_range[1]
                )
                time.sleep(after_sleep)

                if after_click_template:
                    find_target = match_p_in_w(
                        source_handle=source_handle,
                        source_range=source_range,
                        template=after_click_template,
                        mask=after_click_template_mask,
                        match_tolerance=match_tolerance,
                        source_root_handle=source_root_handle)
                    if find_target:
                        continue  # 当前状态没有产生变化, 就不进行输出

            return True

        # 超时, 查找失败
        time.sleep(match_interval)
        spend_time += match_interval
        if spend_time > match_failed_check:
            return False


def loop_match_ps_in_w(
        source_handle,
        template_opts: list,
        return_mode: str,
        match_failed_check: float = 10,
        match_interval: float = 0.2,
        source_root_handle=None,
) -> bool:
    """
        :param source_handle: 截图句柄
        :param template_opts: [{"template":str,"source_range": [x1:int,y1:int,x2:int,y2:int],"match_tolerance":float},...]
        :param return_mode: 模式 and 或者 or
        :param match_interval: 捕捉图片的间隔
        :param match_failed_check: # 捕捉图片时间限制, 超时输出False
        :return: 通过了mode, 则返回[{"x":int,"y":int},None,...] , 否则返回None
        :param source_root_handle: 根窗口句柄, 用于检查窗口是否最小化, 如果最小化则尝试恢复至激活窗口的底层 可空置
        """
    # 截屏
    invite_time = 0.0
    while True:
        find_target = match_ps_in_w(
            source_handle=source_handle,
            template_opts=template_opts,
            return_mode=return_mode,
            source_root_handle=source_root_handle)
        if find_target:
            return True

        # 超时, 查找失败
        invite_time += match_interval
        time.sleep(match_interval)
        if invite_time > match_failed_check:
            return False


if __name__ == '__main__':
    from function.core.FAA import faa_get_handle


    def main():
        handle = faa_get_handle(channel="锑食", mode="browser")
        root_handle = faa_get_handle(channel="锑食", mode="360")
        result = match_p_in_w(source_handle=handle,
                              source_range=[0, 0, 2000, 2000],
                              template=init_resources.RESOURCE_P["common"]["顶部菜单"]["大地图.png"],
                              match_tolerance=0.87,
                              source_root_handle=root_handle)

        print(result)
        result = (1, 2)
        if result:
            print(result[0], result[1])


    main()
