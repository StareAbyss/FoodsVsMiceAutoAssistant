import time

import numpy as np

from function.common.bg_p_screenshot import capture_picture_png
from function.globals.thread_click_queue import T_CLICK_QUEUE_TIMER


def compare_pixels(pixels, reference):
    """为抵消游戏蒙版色，导致的差距，用于对比识别目标像素和标准像素的函数"""
    # 计算每个像素与参照物之间的差异
    diff = np.abs(pixels - reference)
    # 计算每个像素的差异之和
    diff_sum = np.sum(diff, axis=-1)
    # 判断差异之和是否小于等于20
    result = any(diff_sum <= 20)
    return result


class Card:

    def __init__(self, priority, faa):
        # 直接塞进来一个faa的实例地址, 直接从该实例中拉取方法和属性作为参数~
        self.faa = faa
        # 优先级
        self.priority = priority

        """直接从FAA类读取的属性"""
        self.handle = faa.handle
        self.is_use_key = faa.is_use_key
        self.is_auto_battle = faa.is_auto_battle
        self.faa_battle = faa.faa_battle
        self.player = faa.player

        """从FAA类的battle_plan_1中读取的属性"""
        # 根据优先级（也是在战斗方案中的index）直接读取faa
        self.name = faa.battle_plan_1["card"][priority]["name"]
        self.id = faa.battle_plan_1["card"][priority]["id"]
        self.location = faa.battle_plan_1["card"][priority]["location"]
        self.ergodic = faa.battle_plan_1["card"][priority]["ergodic"]
        self.queue = faa.battle_plan_1["card"][priority]["queue"]
        # 坐标 [x,y]
        self.location_from = faa.battle_plan_1["card"][priority]["location_from"]
        # dict {"1-1": [x,y],....}
        self.location_to = faa.battle_plan_1["card"][priority]["location_to"]

        """用于完成放卡的额外类属性"""
        # 状态 冷却完成 默认已完成
        self.status_cd = False
        # 状态 可用
        self.status_usable = False
        # 状态 被ban时间 当放卡，但已完成所有指定位置的放卡导致放卡后立刻检测到冷却完成，则进入该ban状态8s
        self.status_ban = 0
        self.warning_cell = ["4-4", "4-5"]
        self.is_smoothie = self.name in ["冰淇淋", "极寒冰沙", "冰沙"]
        self.ban_white_list = ["冰淇淋", "极寒冰沙", "冰沙"]

    def use_card(self):

        if not self.is_auto_battle:
            return
        if self.is_smoothie and not self.faa_battle.fire_elemental_1000:
            return
        if self.status_cd or self.status_ban:
            return

        # 点击 选中卡片
        T_CLICK_QUEUE_TIMER.add_click_to_queue(
            handle=self.handle,
            x=self.location_from[0],
            y=self.location_from[1])

        if self.ergodic:
            # 遍历模式: True 遍历该卡每一个可以放的位置
            my_len = len(self.location)
            my_to_list = range(my_len)
        else:
            # 遍历模式: False 只放第一张, 为保证放下去, 同一个位置点两次
            my_len = 2
            my_to_list = [0, 0]

        for j in my_to_list:
            # 防止误触, 仅需识图, 不消耗时间
            if self.is_use_key and (self.location[j] in self.warning_cell):
                self.faa_battle.use_key(mode=1)
            # 点击 放下卡片
            T_CLICK_QUEUE_TIMER.add_click_to_queue(
                handle=self.handle,
                x=self.location_to[j][0],
                y=self.location_to[j][1])

        # 放卡后点一下空白
        T_CLICK_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=200, y=350)
        T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=200, y=350)

        # 统一计算点击间隔时间
        time.sleep(self.faa_battle.click_sleep * (2 + my_len))

        # 如果放卡后还可用,自ban 若干s
        # 判断可用 如果不知道其还可用。会导致不自ban，导致无意义点击出现，后果更小。1轮扫描后纠正。
        # 判断冷却 如果不知道其进入了冷却。会导致错误的额外的自ban，导致放卡逻辑错乱。ban描述后纠正。
        self.fresh_status()
        if self.status_usable and (self.name not in self.ban_white_list):
            self.status_ban = 7

        # 如果启动队列模式放卡参数, 使用一次后, 第一个目标位置移动到末位
        if self.queue:
            self.location.append(self.location[0])
            self.location.remove(self.location[0])
            self.location_to.append(self.location_to[0])
            self.location_to.remove(self.location_to[0])

    def fresh_status(self):
        """判断颜色来更改自身冷却和可用属性"""
        img = capture_picture_png(
            handle=self.handle,
            raw_range=[
                self.location_from[0] - 45,
                self.location_from[1] - 64,
                self.location_from[0] + 8,
                self.location_from[1] + 6]
        )

        # 注意 y x bgr 和 rgb是翻过来的！
        # 将三维数组转换为二维数组
        pixels_top_left = img[0:1, 3:20, :3]
        pixels_top_right = img[0:1, 33:51, :3]
        pixels_top_left_2d = pixels_top_left.reshape(-1, pixels_top_left.shape[-1])
        pixels_top_right_2d = pixels_top_right.reshape(-1, pixels_top_right.shape[-1])
        # 使用vstack垂直堆叠
        pixels_top = np.vstack((pixels_top_left_2d, pixels_top_right_2d))
        pixels_bottom = np.squeeze(img[69:70, 2:51, :3])

        # 可用卡 不同地图有蒙版色 需要用容差来做判断，目前设定 三个加起来不超过20
        # 普通卡 rgb 顶部 38 147 155 底部 25 66 69
        # 夜间卡 rgb 顶部 103 38 157 底部 51 24 68
        # 金卡 rgb 顶部 ？ ？ ？ 底部 ？ ？ ？
        self.status_usable = (
                compare_pixels(pixels_top, [157, 149, 38]) or
                compare_pixels(pixels_bottom, [69, 66, 25]) or
                compare_pixels(pixels_top, [157, 38, 103]) or
                compare_pixels(pixels_bottom, [68, 24, 51]) or
                compare_pixels(pixels_top, [155, 147, 38]) or
                compare_pixels(pixels_bottom, [69, 66, 25])
        )

        # 普通卡 rgb 顶部 35 117 124 底部 48 64 68
        # 夜间卡 rgb 顶部 84 35 125 底部 58 47 68
        # 金卡 rgb 顶部 ？ ？ ？ 底部 ？ ？ ？
        self.status_cd = (
                (compare_pixels(pixels_top, [125, 118, 35]) and
                 compare_pixels(pixels_bottom, [68, 64, 48])) or
                (compare_pixels(pixels_top, [125, 35, 84]) and
                 compare_pixels(pixels_bottom, [68, 47, 58])) or
                (compare_pixels(pixels_top, [124, 117, 35]) and
                 compare_pixels(pixels_bottom, [68, 64, 48]))
        )
        #
        # if self.faa.player == 1 and self.name == "炭烧海星":
        #     print(
        #         "top:", pixels_top[0],
        #         "bottom:", pixels_bottom[0],
        #         "可用", self.status_usable,
        #         "cd", self.status_cd)
