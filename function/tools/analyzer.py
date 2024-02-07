import os
import sys

import cv2
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QFileDialog, QVBoxLayout, QLabel

"""
战斗结果logs分析器
致谢：八重垣天知
"""


def calculate_histogram(image):
    """
    计算颜色直方图的函数
    """
    # 转换到 HSV 颜色空间
    hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # 计算直方图 (考虑 H 和 S 两个通道)
    hist = cv2.calcHist([hsv_image], [0, 1], None, [180, 256], [0, 180, 0, 256])
    # 归一化直方图
    cv2.normalize(hist, hist)
    return hist.flatten()


class LogsAnalyzer(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.test_number = 0

    def initUI(self):
        self.setWindowTitle('logs分析器')
        self.layout = QVBoxLayout()

        self.btnOpen = QPushButton('选择图片', self)
        self.btnOpen.clicked.connect(self.openImage)
        self.layout.addWidget(self.btnOpen)

        self.lblResult = QLabel('', self)
        self.layout.addWidget(self.lblResult)

        self.setLayout(self.layout)
        self.show()

    def openImage(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(
            self,
            "QFileDialog.getOpenFileName()",
            "",
            "PNG Files (*.png)",
            options=options)

        if fileName:
            self.matchImage(fileName)

    def matchImage(self, imagePath):
        # 读图
        img = cv2.imread(imagePath)
        if img is None:
            self.lblResult.setText('Error: Unable to open image.')
            return

        # 把每张图片分割成35 * 35像素的块，间隔的x与y都是49
        rows = 5
        cols = 10

        # 保存最佳匹配道具的识图数据
        best_match_items = []

        # 按照分割规则，遍历分割每一块，然后依次识图
        for i in range(rows):
            for j in range(cols):
                block = img[i * 49 + 4:i * 49 + 34, j * 49 + 6:j * 49 + 41]

                # 执行模板匹配并获取最佳匹配的文件名
                best_match_item = self.templateMatch(block)
                if best_match_item:
                    print(f'块 ({i + 1}, {j + 1}) 最匹配的是 {best_match_item}')
                    best_match_items.append(best_match_item)
                    best_match_item = 0

        # 把识别结果显示到界面上    
        print(best_match_items)

    # 带有调试功能的模板匹配，使用根目录下items文件夹来识图，识图失败会把结果保存在block里，方便调试
    def templateMatch(self, block):
        items_dir = os.path.join(os.getcwd(), 'items')
        if not os.path.exists(items_dir):
            print("根目录下没有items文件夹,自己创建一个")
            return None

        highest_score = 0
        item_name = None

        # 计算 block 的颜色直方图
        block_hist = calculate_histogram(block)

        # 遍历每个目标图像
        for target_filename in os.listdir(items_dir):
            target_path = os.path.join(items_dir, target_filename)
            target_image = cv2.imread(target_path)

            if target_image is not None and target_image.shape[:2] == block.shape[:2]:
                # 计算目标图像的颜色直方图
                target_hist = calculate_histogram(target_image)

                # 比较直方图
                score = cv2.compareHist(block_hist, target_hist, cv2.HISTCMP_CORREL)
                # print(f'本次匹配使用图像为 {target_filename}, 得分为 {score}')

                # 如果得分大于0.8,就说明对上了，返回文件名执行下一次循环
                if score > 0.8:
                    item_name = int(target_filename.replace('.png', ''))
                    # 占位，如果读取到文件名为0的item，则结束分割图片，直接返回结果
                    return item_name

                # 调试功能，暂时存储分数，以便输出未能识别图像
                if score > highest_score:
                    highest_score = score

        # 调试功能，如果得分均小于0.8，则输出block，以便归类
        if highest_score < 0.8:
            print(f'该道具未能识别，已在根目录下生成文件，请检查')
            # 调试功能，确保block目录存在
            self.test_number += 1
            current_dir = os.getcwd()
            block_dir = os.path.join(current_dir, 'block')
            if not os.path.exists(block_dir):
                os.makedirs(block_dir)
            block_filename = os.path.join(block_dir, f'{self.test_number}.png')
            cv2.imwrite(block_filename, block)
            print(f'最高分数为{highest_score}')

        return item_name


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = LogsAnalyzer()
    sys.exit(app.exec_())
