import cProfile
import os
import random

import cv2
import numpy as np
import sys
sys.path.append('c:/192/FAA/FoodsVsMouses_AutoAssistant')

from function.common.match import match_histogram
from function.get_paths import paths

"""
战斗结果logs分析器
致谢：八重垣天知
"""

# 比较两个图像是否完全相同
def compare(imageA, imageB):
    # 直接比较图像数组
    return np.array_equal(imageA, imageB)

# 预加载图像
def preload_target_images(items_dir):
    target_images = {}
    for target_filename in os.listdir(items_dir):
        target_path = os.path.join(items_dir, target_filename)
        target_image = cv2.imdecode(np.fromfile(target_path, dtype=np.uint8), -1)
        if target_image is not None:
            # 存储图像和它的文件名（去掉扩展名）
            target_images[target_filename.replace(".png", "")] = target_image
    return target_images

def templateMatch(block, target_images):
    item_name = "识别失败"
    # 遍历预加载的目标图像
    for item_name, target_image in target_images.items():

        # 跳过大小不相等的图片
        if target_image is not None and target_image.shape == block.shape:
            # 对比 block 和 target_image
            result_bool = match_histogram(
                block=block[:, :, :-1],
                target_image=target_image[:, :, :-1])

            if result_bool:
                # 识图成功 返回识别的道具名称
                return item_name

    # 识图失败 把block保存到resource-picture-item-未编码索引中
    print(f'该道具未能识别, 已在resource-picture-item-未编码索引中生成文件, 请检查')
    # 随便编码
    filename = "{}\\未编码索引\\{}.png".format(
        paths["picture"]["item"],
        random.randint(1, 1000)
    )
    # 保存图片
    cv2.imencode('.png', block)[1].tofile(filename)

    return item_name


def matchImage(imagePath, test_print=False):
    """

    :param imagePath:
    :param test_print:
    :return:
    """
    # 读图
    img = cv2.imdecode(np.fromfile(imagePath, dtype=np.uint8), -1)
    if img is None:
        print('图片打不开')
        return None

    # 把每张图片分割成35 * 35像素的块，间隔的x与y都是49
    rows = 5
    column = 10

    # 保存最佳匹配道具的识图数据
    best_match_items = {}

    # 预加载图像
    items_dir = paths["picture"]["item"] + "\\战斗"
    target_images = preload_target_images(items_dir)

    # 按照分割规则，遍历分割每一块，然后依次识图
    found = False
    for i in range(rows):
        if found:  # 检查标志
            break  # 如果设置了标志，跳出外层循环
        for j in range(column):

            # 切分为 49x49
            block = img[i * 49:(i + 1) * 49, j * 49:(j + 1) * 49]
            # 切分为 30x36
            block = block[5:41, 5:35]

            # 执行模板匹配并获取最佳匹配的文件名
            best_match_item = templateMatch(block, target_images)

            if best_match_item == "0" or best_match_item == "1":
                found = True
                break
            if best_match_item:
                # 如果道具ID已存在，则增加数量，否则初始化数量为1
                if best_match_item in best_match_items:
                    best_match_items[best_match_item] += 1
                else:
                    best_match_items[best_match_item] = 1

    if __name__ == '__main__':
        # 把识别结果显示到界面上
        print("战利品识别结果：")
        print(best_match_items)

    # 返回识别结果
    return best_match_items


if __name__ == '__main__':
    def main():
        matchImage(imagePath=paths["logs"] + "\\img.png")


    cProfile.run("main()")
