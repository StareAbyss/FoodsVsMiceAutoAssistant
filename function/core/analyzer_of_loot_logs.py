import cProfile
import random

import cv2

from function.common.match import match
from function.globals.get_paths import PATHS
from function.globals.init_resources import RESOURCE_P

"""
战斗结果logs分析模块
致谢：八重垣天知
"""


def item_match(block):

    # 遍历预加载的目标图像
    for item_name, item_img in RESOURCE_P["item"]["战斗"].items():

        # 跳过大小不相等的图片
        if item_img.shape != block.shape:
            continue

        # 对比 block 和 target_image
        if match(block=block[:, :, :-1], tar_img=item_img[:, :, :-1], mode="match_template"):
            # 识图成功 返回识别的道具名称(不含扩展名)
            return item_name.replace(".png", "")

    # 识图失败 把block保存到resource-picture-item-未编码索引中
    print(f'该道具未能识别, 已在 [ resource / picture /  item / 未编码索引中 ] 生成文件, 请检查')

    # 随便编码
    filename = "{}\\未编码索引\\{}.png".format(PATHS["picture"]["item"],random.randint(1, 100))

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

    # 按模式分割图片
    if mode == 'loots':
        # 战利品模式 把每张图片分割成35 * 35像素的块，间隔的x与y都是49
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
        # 开宝箱模式
        block_list.append(img[4:-4, 4:-54])
        block_list.append(img[4:-4, 48:-10])

    # 保存最佳匹配道具的识图数据
    best_match_items = {}

    # 按照分割规则，遍历分割每一块，然后依次识图

    for block in block_list:
        # 执行模板匹配并获取最佳匹配的文件名
        best_match_item = item_match(block)
        if best_match_item in ['None-0', 'None-1', 'None-2']:
            # 识别为无
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
