# coding:utf-8

import PIL
import numpy
from function_common.background_screenshot import capture_picture_png


def find_pixel_in_picture(f_handle, axis_x, axis_y, color_r, color_g, color_b, tolerance):
    image_array_bgra = capture_picture_png(f_handle)  # 根据句柄运行函数截图,截图后为 像素*BGRA的二维数组
    image_array_bgr = image_array_bgra[:, :, 0:3]  # 转化数组为BGR排序
    image_array_rgb = image_array_bgr[:, :, ::-1]  # 转化数组为RGB排序
    image_image = PIL.Image.fromarray(numpy.uint8(image_array_rgb))
    pix_color = image_image.getpixel((axis_x, axis_y))  # 截图的窗口不包含title部分 需要注意xy值
    # # 测试 一直输出检测的像素的颜色值，需要的值
    # print(
    #     '检到值：(' +
    #     str(pix_color[0]) + ',' + str(pix_color[1]) + ',' + str(pix_color[2]) + ')' +
    #     '  需求值：(' +
    #     str(color_r) + ',' + str(color_g) + ',' + str(color_b) + ')' +
    #     '  差值：(' +
    #     str(pix_color[0] - color_r) + ',' + str(pix_color[1] - color_g) + ',' + str(pix_color[2] - color_b) + ')')
    #
    # # 测试 保存图片到本地
    # image_image.save('图片.png')
    #
    # # 测试 显示图片
    # cv2.imshow("Capture Test", image_array_bgra)
    # cv2.waitKey()

    if abs(pix_color[0] - color_r) < tolerance and abs(pix_color[1] - color_g) < tolerance and abs(
            pix_color[2] - color_b) < tolerance:
        return True
    else:
        return False
