# coding:utf-8

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from function.core.QMW_3_service import main


if __name__ == '__main__':
    # 游戏[固定]分辨率 950* 600 19:12 完全可以在识别图像时提前裁剪来减小消耗
    # 截图[不会]缩放, 点击位置[需要]缩放, 这为制作脚本提供了极大便利

    main()
