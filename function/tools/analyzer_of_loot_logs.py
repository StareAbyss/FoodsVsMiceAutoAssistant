import os
import random

import cv2

from function.get_paths import paths

"""
战斗结果logs分析器
致谢：八重垣天知
"""


class LogsAnalyzer:

    def matchImage(self,imagePath):
        print("成功调用该函数")
        # 读图
        img = cv2.imread(imagePath)
        if img is None:
            print('图片打不开')
            return None

        # 从文件名中提取地图名
        map_name = os.path.basename(imagePath).split('_')[0]

        # 把每张图片分割成35 * 35像素的块，间隔的x与y都是49
        rows = 5
        cols = 10

        # 保存最佳匹配道具的识图数据
        best_match_items = {}
        # 初始化或更新best_match_items字典
        if map_name not in best_match_items:
            best_match_items[map_name] = {}

        # 按照分割规则，遍历分割每一块，然后依次识图
        found = False
        for i in range(rows):
            if found:  # 检查标志
                break  # 如果设置了标志，跳出外层循环
            for j in range(cols):
                block = img[i * 49 + 5:i * 49 + 30, j * 49 + 5:j * 49 + 44]

                # 执行模板匹配并获取最佳匹配的文件名
                best_match_item = LogsAnalyzer.templateMatch(block)

                if best_match_item == 999:
                    found = True
                    break
                if best_match_item:
                    # 如果道具ID已存在，则增加数量，否则初始化数量为1
                    if best_match_item in best_match_items[map_name]:
                        best_match_items[map_name][best_match_item] += 1
                    else:
                        best_match_items[map_name][best_match_item] = 1

        # 把识别结果显示到界面上
        print(best_match_items[map_name])

        # 返回识别结果
        return best_match_items

    # 带有调试功能的模板匹配，使用根目录下items文件夹来识图，识图失败会把结果保存在block里，方便调试

    def templateMatch(self, block):
        items_dir = paths["picture"]["item"] + "\\战斗"

        highest_score = 0
        item_name = None

        # 遍历每个目标图像
        for target_filename in os.listdir(items_dir):
            target_path = os.path.join(items_dir, target_filename)
            target_image = cv2.imread(target_path)

            if target_image is not None and target_image.shape == block.shape:
                # 执行模板匹配
                result = cv2.matchTemplate(target_image, block, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                # print(f'本次匹配使用图像为 {target_filename}, 得分为 {max_val}')

                # 如果得分大于0.9,就说明对上了，返回文件名执行下一次循环
                if max_val > 0.9:
                    item_name = int(target_filename.replace('.png', ''))
                    # 占位，如果读取到文件名为0的item，则结束分割图片，直接返回结果
                    return item_name

                # 调试功能，暂时存储分数，以便输出未能识别图像
                if max_val > highest_score:
                    highest_score = max_val

        # 调试功能，如果得分均小于0.9，则输出block，以便归类
        if highest_score < 0.9:
            print(f'该道具未能识别，已在根目录下生成文件，请检查')
            # 调试功能，确保block目录存在
            block_filename = os.path.join(paths["picture"]["item"] + "\\block", f'{random.randint(1, 1000)}.png')
            cv2.imwrite(block_filename, block)
            print(f'最高分数为{highest_score}')

        return item_name

