import time

from function.common.bg_img_screenshot import capture_image_png
from function.scattered.gat_handle import faa_get_handle

handle = faa_get_handle("锑食-微端")

# y,x,bgra，此处获取客户端图像，由于raw_range已知传入固定值
p = capture_image_png(handle=handle, raw_range=[0, 0, 950, 600], root_handle=None)

# 判断卡片是否可用，传入图像，识别坐标
"""
png_img_arr:图像信号的数组：__class__=numpy.arr
list_of_check：根据页面判定的坐标数组，开始战斗前需要初始化，减少计算量，建议与实例化对象绑定：__class__=list
return:
card_useable_list:布尔值列表，与卡片ID顺序一致：__class__=bool
"""


def card_useable(png_img_arr, list_of_check):
    card_useable_list = []
    # 分离获取G通道数据
    g_po_arr = png_img_arr[:, :, 1:2]
    # 获取对应坐标的色度值,判定其数值
    for j, i in list_of_check:
        flg = int(g_po_arr[i, j][0:1])
        card_useable_list.append(flg > 200)
    return card_useable_list


# 坐标系识别与进入判断
def point_init(png_img):
    """
    1.识别是否进入战斗，5点像素判定，未进入战斗返回False
    2.识别卡槽偏移，判断坐标类型
    传入值：png_img:实时图像:__class__=numpy.arr
    :return:
    flag1:进入战斗：__class__=bool
    flag2:卡槽类型：__class__=int
    """

    flag_3_s = [(88, 40), (227, 7), (156, 38)]

    list_of_card_point12 = [
        (261, 13), (314, 13), (366, 13), (420, 13), (473, 13), (526, 13), (578, 13), (632, 13),
        (684, 13), (738, 13), (791, 13), (844, 13)
    ]

    list_of_card_point13 = [
        (239, 13), (292, 13), (345, 13), (397, 13), (451, 13), (504, 13), (557, 13), (609, 13),
        (663, 13), (715, 13), (769, 13), (822, 13), (875, 13),
        (929, 13), (929, 82), (929, 151), (929, 220), (929, 289), (929, 358), (929, 427),
        (929, 496)
    ]

    fl3 = int(png_img[int(flag_3_s[2][1]), int(flag_3_s[2][0]), 1:2])

    if fl3 > 180:  # 改为具体数值，True为12卡以下

        return {"flag1": True, "flag2": list_of_card_point12}

    else:

        return {"flag1": True, "flag2": list_of_card_point13}



"""
以下调试
"""


def run():
    img = capture_image_png(handle=handle, raw_range=[0, 0, 950, 600], root_handle=None)

    card_useable_get = card_useable(
        png_img_arr=img,
        list_of_check=point_init(img).get("flag2"))

    for i in range(len(card_useable_get)):
        print("卡{}:{}".format(i + 1, card_useable_get[i]), end=";")
    print()
    time.sleep(1)
    run()


if __name__ == '__main__':
    run()
