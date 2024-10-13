import os

import cv2
import numpy as np

from function.common.bg_img_screenshot import capture_image_png
from function.core_battle.get_position_in_battle import get_position_card_deck_in_battle
from function.scattered.gat_handle import faa_get_handle


class Card:
    def __init__(self):
        self.channel = "锑食-微端"
        self.handle = faa_get_handle(channel=self.channel, mode="flash")
        self.handle_360 = faa_get_handle(channel=self.channel, mode="360")
        self.cid = 2
        self.location_from = get_position_card_deck_in_battle(handle=self.handle, handle_360=self.handle_360)[self.cid]

    def get_card_current_img(self, game_image=None):
        """
        获取用于 判定 卡片状态 的图像
        :param game_image: 可选, 是否从已有的完成游戏图像中拆解, 不截图
        :return:
        """
        x1 = self.location_from[0]
        x2 = x1 + 53
        y1 = self.location_from[1]
        y2 = y1 + 70

        if game_image is None:
            img = capture_image_png(handle=self.handle, raw_range=[x1, y1, x2, y2], root_handle=self.handle_360)
        else:
            img = game_image[y1:y2, x1:x2]

        # img的格式[y1:y2,x1:x2,bgra] 注意不是 r g b α 而是 b g r α
        pixels_top_left = img[0:1, 2:20, :3]  # 18个像素图片 (1, 18, 3)
        pixels_top_right = img[0:1, 33:51, :3]  # 18个像素图片 (1, 18, 3)
        pixels_all = np.hstack((pixels_top_left, pixels_top_right))  # 36个像素图片 (1, 36, 3)

        return pixels_all


card = Card()
img = card.get_card_current_img()
if not os.path.exists("img"):
    os.makedirs("img")
cv2.imencode(ext=".png", img=img)[1].tofile("core\\test.png")

