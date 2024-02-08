import os
import random

import cv2
import numpy as np

from function.get_paths import paths

"""
战斗结果logs分析器
致谢：八重垣天知
"""


def templateMatch(block):
    items_dir = paths["picture"]["item"] + "\\战斗"

    highest_score = 0
    item_name = None

    # 遍历每个目标图像
    for target_filename in os.listdir(items_dir):
        target_path = "{}\\{}".format(items_dir, target_filename)
        target_image = cv2.imdecode(np.fromfile(target_path, dtype=np.uint8), -1)

        if target_image is not None and target_image.shape == block.shape:
            # 执行模板匹配
            result = cv2.matchTemplate(target_image, block, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            # print(f'本次匹配使用图像为 {target_filename}, 得分为 {max_val}')

            # 如果得分大于0.9,就说明对上了，返回文件名执行下一次循环
            if max_val > 0.9:
                item_name = target_filename.replace(".png", "")
                # 占位，如果读取到文件名为0的item，则结束分割图片，直接返回结果
                return item_name

            # 调试功能，暂时存储分数，以便输出未能识别图像
            if max_val > highest_score:
                highest_score = max_val

    # 调试功能，如果得分均小于0.9，则输出block，以便归类
    # 带有调试功能的模板匹配，使用根目录下items文件夹来识图，识图失败会把结果保存在block里，方便调试
    if highest_score < 0.9:
        print(f'该道具未能识别, 已在resource-picture-item-未编码索引中生成文件, 请检查')
        # 调试功能
        filename = "{}\\未编码索引\\{}.png".format(paths["picture"]["item"], random.randint(1, 1000))
        cv2.imencode('.png', block)[1].tofile(filename)
        print(f'最高分数为{highest_score}')

    return item_name


def matchImage(imagePath):
    # 读图
    img = cv2.imread(imagePath)
    if img is None:
        print('图片打不开')
        return None

    # 把每张图片分割成35 * 35像素的块，间隔的x与y都是49
    rows = 5
    column = 10

    # 保存最佳匹配道具的识图数据
    best_match_items = {}

    # 按照分割规则，遍历分割每一块，然后依次识图
    found = False
    for i in range(rows):
        if found:  # 检查标志
            break  # 如果设置了标志，跳出外层循环
        for j in range(column):
            block = img[i * 49 + 5:i * 49 + 30, j * 49 + 5:j * 49 + 44]

            # 执行模板匹配并获取最佳匹配的文件名
            best_match_item = templateMatch(block)

            if best_match_item == "无":
                found = True
                break
            if best_match_item:
                # 如果道具ID已存在，则增加数量，否则初始化数量为1
                if best_match_item in best_match_items:
                    best_match_items[best_match_item] += 1
                else:
                    best_match_items[best_match_item] = 1

    # 把识别结果显示到界面上
    # print("战利品识别结果：")
    # print(best_match_items)

    # 返回识别结果
    return best_match_items


if __name__ == '__main__':
    def main():
        matchImage(imagePath=paths["logs"] + "\\loot_picture\\CS-5-4_1P_2024-02-08_20-03-17.png")


    main()
