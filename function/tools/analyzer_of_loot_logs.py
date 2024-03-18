import cProfile
import os
import random

import cv2
import numpy as np

from function.common.match import match_histogram
from function.globals.get_paths import PATHS

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
    print(f'该道具未能识别, 已在 [ resource / picture /  item / 未编码索引中 ] 生成文件, 请检查')
    # 随便编码
    filename = "{}\\未编码索引\\{}.png".format(
        PATHS["picture"]["item"],
        random.randint(1, 1000)
    )
    # 保存图片
    cv2.imencode('.png', block)[1].tofile(filename)

    return "识别失败"


def matchImage(img_path, img, mode='loots', test_print=False):
    """
    分析图片，获取战利品字典，尽可能不要输出None
    :param img_path:
    :param img:
    :param mode:
    :param test_print:
    :return:
    """

    cv2.imencode('.png', img)[1].tofile(img_path)
    block_list = []
    if mode == 'loots':
        # 把每张图片分割成35 * 35像素的块，间隔的x与y都是49
        rows = 5
        column = 10

        for i in range(rows):
            for j in range(column):
                # 切分为 49x49
                block = img[i * 49:(i + 1) * 49, j * 49:(j + 1) * 49]
                # 切分为 30x36
                block = block[5:41, 5:35]
                block_list.append(block)

    elif mode == 'chests':
        block_list.append(img[4:-4, 4:-54])
        block_list.append(img[4:-4, 48:-10])

    # 保存最佳匹配道具的识图数据
    best_match_items = {}

    # 预加载图像
    items_dir = PATHS["picture"]["item"] + "\\战斗"
    target_images = preload_target_images(items_dir)

    # 按照分割规则，遍历分割每一块，然后依次识图

    for block in block_list:
        # 执行模板匹配并获取最佳匹配的文件名
        best_match_item = templateMatch(block, target_images)
        if best_match_item in ['0', '1', '2']:
            break
        if best_match_item:
            # 如果道具ID已存在，则增加数量，否则初始化数量为1
            if best_match_item in best_match_items:
                best_match_items[best_match_item] += 1
            else:
                best_match_items[best_match_item] = 1

    if test_print:
        # 把识别结果显示到界面上
        print("matchImage方法 战利品识别结果：")
        print(best_match_items)

    # 返回识别结果
    return best_match_items


if __name__ == '__main__':
    def main():
        img = cv2.imread(PATHS["logs"] + "\\img.png")
        matchImage(img_path="{}\\img.png".format(PATHS["logs"]), img=img)


    cProfile.run("main()")
