import time

import numpy as np

from function.common.bg_p_screenshot import capture_picture_png
from function.globals.extra import EXTRA_GLOBALS
from function.globals.init_resources import RESOURCE_P
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER


def compare_pixels(img, tar_img):
    """为抵消游戏蒙版色，导致的差距，用于对比识别目标像素和标准像素的函数"""
    for i in range(len(img[0])):
        if np.sum(img[0][i] - tar_img[0][i]) < 25:
            return True
    return False


class Card:

    def __init__(self, priority, faa):
        # 直接塞进来一个faa的实例地址, 直接从该实例中拉取方法和属性作为参数~
        self.faa = faa
        # 优先级
        self.priority = priority

        """直接从FAA类读取的属性"""
        self.handle = self.faa.handle
        self.is_use_key = self.faa.is_use_key
        self.is_auto_battle = self.faa.is_auto_battle
        self.faa_battle = self.faa.faa_battle
        self.player = self.faa.player

        """从FAA类的battle_plan_1中读取的属性"""
        # 根据优先级（也是在战斗方案中的index）直接读取faa
        self.name = self.faa.battle_plan_1["card"][priority]["name"]
        self.id = self.faa.battle_plan_1["card"][priority]["id"]
        self.location = self.faa.battle_plan_1["card"][priority]["location"]
        self.ergodic = self.faa.battle_plan_1["card"][priority]["ergodic"]
        self.queue = self.faa.battle_plan_1["card"][priority]["queue"]
        # 坐标 [x,y]
        self.location_from = self.faa.battle_plan_1["card"][priority]["location_from"]
        # dict {"1-1": [x,y],....}
        self.location_to = self.faa.battle_plan_1["card"][priority]["location_to"]
        # 坤优先级
        self.kun = self.faa.battle_plan_1["card"][priority]["kun"]

        """用于完成放卡的额外类属性"""
        # 状态 冷却完成 默认已完成
        self.status_cd = False
        # 状态 可用
        self.status_usable = False
        # 状态 被ban时间 当放卡，但已完成所有指定位置的放卡导致放卡后立刻检测到冷却完成，则进入该ban状态8s
        self.status_ban = 0
        # 是否是当前角色的坤目标
        self.is_kun_target = False
        # 危险的区域 防止点到继续战斗
        self.warning_cell = ["4-4", "4-5"]
        # 判定自身是不是极寒冰沙
        self.is_smoothie = self.name in ["极寒冰沙", "冰沙"]
        # 不进入放满自ban的 白名单
        self.ban_white_list = ["极寒冰沙", "冰沙"]

    def use_card(self):

        if not self.is_auto_battle:
            return
        if self.is_smoothie:
            if not self.faa_battle.fire_elemental_1000:
                return
            if EXTRA_GLOBALS.smoothie_lock_time != 0:
                return
            EXTRA_GLOBALS.smoothie_lock_time = 7
        if self.status_cd or self.status_ban:
            return

        # 点击 选中卡片
        T_ACTION_QUEUE_TIMER.add_click_to_queue(
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
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=self.handle,
                x=self.location_to[j][0],
                y=self.location_to[j][1])

        # 放卡后点一下空白
        T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=200, y=350)
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=200, y=350)

        # 统一计算点击间隔时间
        time.sleep(0.05 + self.faa_battle.click_sleep * my_len)

        # 如果启动队列模式放卡参数, 使用一次后, 第一个目标位置移动到末位
        if self.queue:
            self.location.append(self.location[0])
            self.location.remove(self.location[0])
            self.location_to.append(self.location_to[0])
            self.location_to.remove(self.location_to[0])

        # 如果放卡后还可用,自ban 若干s
        # 判断可用 如果不知道其还可用。会导致不自ban，导致无意义点击出现，后果更小。1轮扫描后纠正。
        # 判断冷却 如果不知道其进入了冷却。会导致错误的额外的自ban，导致放卡逻辑错乱。ban描述后纠正。
        self.fresh_status()

        if self.status_usable and (self.name not in self.ban_white_list):
            # 放置失败 说明放满了 如果不在白名单 就自ban
            self.status_ban = 7
        else:
            if self.is_kun_target:
                # 放置成功 如果是坤目标, 复制自身放卡的逻辑

                # 点击 选中卡片 但坤
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=self.faa.kun_position["location_from"][0],
                    y=self.faa.kun_position["location_from"][1])

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
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(
                        handle=self.handle,
                        x=self.location_to[j][0],
                        y=self.location_to[j][1])

                # 放卡后点一下空白
                T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=200, y=350)
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=200, y=350)

                # 统一计算点击间隔时间
                time.sleep(0.05 + self.faa_battle.click_sleep * my_len)

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
        pixels_top_left = np.squeeze(img[0:1, 2:20, :3])  # 18个像素
        pixels_top_right = np.squeeze(img[0:1, 33:51, :3])  # 18个像素
        pixels_bottom = np.squeeze(img[69:70, 2:51, :3])  # 49个像素

        pixels_all = [[]]
        for axis_0 in [pixels_top_left, pixels_top_right, pixels_bottom]:
            for pixel in axis_0:
                pixels_all[0].append(pixel)
        pixels_all = np.array(pixels_all)

        self.status_usable = (compare_pixels(pixels_all, RESOURCE_P["card"]["状态判定"]["可用状态_0.png"]) or
                              compare_pixels(pixels_all, RESOURCE_P["card"]["状态判定"]["可用状态_1.png"]) or
                              compare_pixels(pixels_all, RESOURCE_P["card"]["状态判定"]["可用状态_2.png"]))

        self.status_cd = (compare_pixels(pixels_all, RESOURCE_P["card"]["状态判定"]["冷却状态_0.png"]) or
                          compare_pixels(pixels_all, RESOURCE_P["card"]["状态判定"]["冷却状态_1.png"]) or
                          compare_pixels(pixels_all, RESOURCE_P["card"]["状态判定"]["冷却状态_2.png"]))

    def destroy(self):
        self.faa = None
        self.priority = None


class CardKun:
    def __init__(self, faa):
        # 直接塞进来一个faa的实例地址, 直接从该实例中拉取方法和属性作为参数~
        self.faa = faa

        """直接从FAA类读取的属性"""
        self.handle = self.faa.handle

        # 坐标 [x,y]
        self.location_from = self.faa.kun_position["location_from"]

        """用于完成放卡的额外类属性"""
        # 状态 可用
        self.status_usable = False

    def fresh_status(self):
        """判断颜色来更改自身冷却和可用属性"""
        print(self.location_from)
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
        pixels_top_left = np.squeeze(img[0:1, 2:20, :3])  # 18个像素
        pixels_top_right = np.squeeze(img[0:1, 33:51, :3])  # 18个像素
        pixels_bottom = np.squeeze(img[69:70, 2:51, :3])  # 49个像素


        pixels_all = [[]]
        for axis_0 in [pixels_top_left, pixels_top_right, pixels_bottom]:
            for pixel in axis_0:
                pixels_all[0].append(pixel)
        pixels_all = np.array(pixels_all)
        self.status_usable = compare_pixels(pixels_all, RESOURCE_P["card"]["状态判定"]["可用状态_0.png"])

    def destroy(self):
        self.faa = None
