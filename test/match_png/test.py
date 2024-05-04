import cv2
import numpy as np


def test_match_template():
    # 加载源图像和模板图像
    img_source = cv2.imread('source.png')  # 直接读取就是BGR格式 不包含Alpha通道
    # img_template = cv2.imread('template.png')  # 直接读取就是BGR格式 不包含Alpha通道
    img_template = cv2.imread('template_lock.png')  # 直接读取就是BGR格式 不包含Alpha通道
    mask = cv2.imread('mask.bmp')

    # 使用matchTemplate函数和掩模进行匹配
    # 纯黑即灰度为0的部分被无视 非0部分则被认为是匹配区域
    result = cv2.matchTemplate(image=img_source, templ=img_template, method=cv2.TM_SQDIFF_NORMED, mask=mask)

    # 找到最优匹配的位置
    (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(src=result)

    # 如果匹配度<阈值，就认为没有找到
    # if minVal >= 0.01:
    #     print(f"最优匹配坐标: {minLoc}, 匹配值: {minVal} 匹配失败")
    #     return None

    # 最优匹配的左上坐标
    (start_x, start_y) = minLoc

    # 在源图像上绘制矩形框
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
    # 最优匹配坐标和匹配值
    print(f"最优匹配坐标: {minLoc}, 匹配值: {minVal:.4f} 匹配成功")

    # 显示输出图像
    cv2.imshow(winname="SourceImg.png", mat=img_source)
    cv2.waitKey(0)


test_match_template()
