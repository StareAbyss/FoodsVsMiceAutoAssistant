import time

import numpy as np

from function.common.bg_keyboard import key_down_up
from function.common.bg_p_compare import find_p_in_w, find_ps_in_w
from function.common.bg_p_screenshot import capture_picture_png
from function.globals.init_resources import RESOURCE_P
from function.globals.thread_click_queue import T_CLICK_QUEUE_TIMER


class Battle:
    def __init__(self, faa):
        """FAA的战斗类，包含了各种战斗中专用的方法"""
        """调用faa属性"""
        self.handle = faa.handle
        self.player = faa.player
        self.is_auto_battle = faa.is_auto_battle
        self.is_auto_pickup = faa.is_auto_pickup
        self.is_use_key = faa.is_use_key
        self.bp_cell = faa.bp_cell
        self.bp_card = faa.bp_card
        self.battle_plan_1 = faa.battle_plan_1

        """战斗专用属性"""
        self.fire_elemental_1000 = False

        """老方法其他手动内部参数"""
        # 每次点击时 按下和抬起之间的间隔 秒
        self.click_interval = 0.025
        # 每次点击时 按下和抬起之间的间隔 秒
        self.click_sleep = 0.025

        # the locations of cell easy touch the use-key UI by mistake
        self.warning_cell = ["4-4", "4-5"]
        self.auto_collect_cells = [
            "1-1", "2-1", "8-1", "9-1",
            "1-2", "2-2", "8-2", "9-2",
            "1-3", "2-3", "8-3", "9-3",
            "1-4", "2-4", "8-4", "9-4",
            "1-5", "2-5", "8-5", "9-5",
            "1-6", "2-6", "8-6", "9-6",
            "1-7", "2-7", "8-7", "9-7"
        ]
        self.auto_collect_cells = [i for i in self.auto_collect_cells if i not in self.warning_cell]

        self.auto_collect_cells_coordinate = []
        for i in self.auto_collect_cells:
            self.auto_collect_cells_coordinate.append(self.bp_cell[i])

    """ 战斗内的子函数 """

    def use_player(self, num_cell):
        T_CLICK_QUEUE_TIMER.add_click_to_queue(
            handle=self.handle,
            x=self.bp_cell[num_cell][0],
            y=self.bp_cell[num_cell][1])
        time.sleep(self.click_sleep)

    def use_shovel(self, position=None):
        """
        根据战斗方案用铲子
        """
        positions = self.battle_plan_1["shovel"]
        if positions is None:
            positions = []

        if position is not None:
            positions.append(position)

        for position in positions:
            key_down_up(handle=self.handle, key="1")
            T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=position[0], y=position[1])

    def use_key(self, mode: int = 0):
        """
        使用钥匙的函数,
        :param mode:
            the mode of use key.
            0: click on the location of "next UI".
            1: if you find the picture of "next UI", click it.
            3
        :return:
            None
        """
        if self.is_use_key:
            if mode == 0:
                T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=427, y=360)
                time.sleep(self.click_sleep)
                T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=427, y=360)
                time.sleep(self.click_sleep)
                T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=427, y=360)
                time.sleep(self.click_sleep)

            if mode == 1:
                find = find_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=RESOURCE_P["common"]["战斗"]["战斗中_继续作战.png"])
                if find:
                    T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=427, y=360)
                    time.sleep(self.click_sleep)
                    T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=427, y=360)
                    time.sleep(self.click_sleep)
                    T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=427, y=360)
                    time.sleep(self.click_sleep)

    def use_key_and_check_end(self):
        # 找到战利品字样(被黑色透明物遮挡,会看不到)
        self.use_key(mode=1)
        result = find_ps_in_w(
            raw_w_handle=self.handle,
            target_opts=[
                {
                    "raw_range": [202, 419, 306, 461],
                    "target_path": RESOURCE_P["common"]["战斗"]["战斗后_1_战利品.png"],

                    "target_tolerance": 0.999
                },
                {
                    "raw_range": [202, 419, 306, 461],
                    "target_path": RESOURCE_P["common"]["战斗"]["战斗后_2_战利品阴影版.png"],
                    "target_tolerance": 0.999
                },
                {
                    "raw_range": [400, 47, 550, 88],
                    "target_path": RESOURCE_P["common"]["战斗"]["战斗后_3_战斗结算.png"],
                    "target_tolerance": 0.999
                },
                {
                    "raw_range": [400, 35, 550, 75],
                    "target_path": RESOURCE_P["common"]["战斗"]["战斗后_4_翻宝箱.png"],
                    "target_tolerance": 0.999
                },
                {
                    "raw_range": [350, 275, 600, 360],
                    "target_path": RESOURCE_P["error"]["登录超时.png"],
                    "target_tolerance": 0.999
                },
                {
                    "raw_range": [350, 275, 600, 360],
                    "target_path": RESOURCE_P["error"]["断开连接.png"],
                    "target_tolerance": 0.999
                },
                {
                    "raw_range": [350, 275, 600, 360],
                    "target_path": RESOURCE_P["error"]["Flash爆炸.png"],
                    "target_tolerance": 0.999
                },
            ],
            return_mode="or")
        return result

    def use_card_once(self, num_card: int, num_cell: str, click_space=True):
        """
        Args:
            num_card: 使用的卡片的序号
            num_cell: 使用的卡片对应的格子 从左上开始 "1-1" to "9-7"
            click_space:  是否点一下空白地区防卡住
        """
        # 注 美食大战老鼠中 放卡动作 需要按下一下 然后拖动 然后按下并松开 才能完成 整个动作
        T_CLICK_QUEUE_TIMER.add_click_to_queue(
            handle=self.handle,
            x=self.bp_card[num_card][0],
            y=self.bp_card[num_card][1])
        time.sleep(self.click_sleep)

        T_CLICK_QUEUE_TIMER.add_click_to_queue(
            handle=self.handle,
            x=self.bp_cell[num_cell][0],
            y=self.bp_cell[num_cell][1])
        time.sleep(self.click_sleep)

        # 点一下空白
        if click_space:
            T_CLICK_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=200, y=350)
            T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=200, y=350)
            time.sleep(self.click_sleep)

    def use_weapon_skill(self):
        """使用武器技能"""
        T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=23, y=200)
        time.sleep(self.click_sleep)
        T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=23, y=250)
        time.sleep(self.click_sleep)
        T_CLICK_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=23, y=297)
        time.sleep(self.click_sleep)

    def auto_pickup(self):
        if self.is_auto_pickup:
            for coordinate in self.auto_collect_cells_coordinate:
                T_CLICK_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=coordinate[0], y=coordinate[1])
                time.sleep(self.click_sleep)

    def update_fire_elemental_1000(self):
        image = capture_picture_png(handle=self.handle, raw_range=[161, 75, 164, 85])
        image = image[:, :, :3]
        image = image.reshape(-1, image.shape[-1])  # 减少一个多余的维度
        self.fire_elemental_1000 = np.any(image == [0, 0, 0])

        if self.player == 1:
            print("1p火苗>1000:", self.fire_elemental_1000)
