import time

import numpy as np

from function.common.bg_img_match import match_p_in_w, match_ps_in_w, loop_match_p_in_w
from function.common.bg_img_screenshot import capture_image_png
from function.globals.init_resources import RESOURCE_P
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER


class Battle:
    def __init__(self, faa):
        """FAA的战斗类，包含了各种战斗中专用的方法"""
        # 复制faa实例的属性
        # 如果直接调用该类可以从faa实例中获取动态变化的其属性值, 但如果赋值到本类内部属性则会固定为静态
        self.faa = faa

        # 战斗专用私有属性 - 每次战斗刷新
        self.fire_elemental_1000 = None
        self.smoothie_usable = None
        self.is_used_key = False  # 仅由外部信号更改, 用于标识战斗是否使用了钥匙

        # 战斗专用私有属性 - 静态

        # 每次点击时 按下和抬起之间的间隔 秒
        self.click_interval = 0.016

        # 每次点击时 按下和抬起之间的间隔 秒
        self.click_sleep = 0.016

        # 自动拾取的格子
        self.auto_collect_cells = [
            "1-1", "2-1", "8-1", "9-1",
            "1-2", "2-2", "8-2", "9-2",
            "1-3", "2-3", "8-3", "9-3",
            "1-4", "2-4", "8-4", "9-4",
            "1-5", "2-5", "8-5", "9-5",
            "1-6", "2-6", "8-6", "9-6",
            "1-7", "2-7", "8-7", "9-7"
        ]

        # 自动拾取的坐标
        self.auto_collect_cells_coordinate = []
        for i in self.auto_collect_cells:
            self.auto_collect_cells_coordinate.append(self.faa.bp_cell[i])

    """ 战斗内的子函数 """

    def re_init(self):
        """战斗前调用, 重新初始化部分每场战斗都要重新刷新的该内私有属性"""
        self.is_used_key = False
        self.fire_elemental_1000 = False
        self.smoothie_usable = self.faa.player == 1

    def use_player_once(self, num_cell):
        T_ACTION_QUEUE_TIMER.add_click_to_queue(
            handle=self.faa.handle,
            x=self.faa.bp_cell[num_cell][0],
            y=self.faa.bp_cell[num_cell][1])
        time.sleep(self.click_sleep)

    def use_player_all(self):
        self.faa.print_info(text="[战斗] 开始放置玩家:{}".format(self.faa.battle_plan_0["player"]))
        for i in self.faa.battle_plan_0["player"]:
            self.use_player_once(i)
            time.sleep(self.click_sleep)

    def use_shovel_all(self, position=None):
        """
        根据战斗方案用铲子
        """
        positions = self.faa.battle_plan_1["shovel"]
        if positions is None:
            positions = []

        if position is not None:
            positions.append(position)

        for position in positions:
            T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=self.faa.handle, key="1")
            time.sleep(self.click_sleep / 2)  # 必须的间隔
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.faa.handle, x=position[0], y=position[1])
            time.sleep(self.click_sleep)

    def use_key(self):
        """
        使用钥匙的函数
        :return:
            None
        """
        # 如果不需要使用钥匙 或者 已经用过钥匙 直接输出
        if not self.faa.need_key or self.is_used_key:
            return False

        find = match_p_in_w(
            source_handle=self.faa.handle,
            source_range=[386, 332, 463, 362],
            match_tolerance=0.95,
            template=RESOURCE_P["common"]["战斗"]["战斗中_继续作战.png"])
        if find:
            self.faa.print_info(text="找到了 [继续作战] 图标")
            while find:
                loop_match_p_in_w(
                    source_handle=self.faa.handle,
                    source_root_handle=self.faa.handle_360,
                    source_range=[386, 332, 463, 362],
                    match_tolerance=0.95,
                    template=RESOURCE_P["common"]["战斗"]["战斗中_继续作战.png"],
                    after_sleep=0.5,
                    click=True)
                find = match_p_in_w(
                    source_handle=self.faa.handle,
                    source_root_handle=self.faa.handle_360,
                    source_range=[302, 263, 396, 289],
                    match_tolerance=0.95,
                    template=RESOURCE_P["common"]["战斗"]["战斗中_精英鼠军.png"])
            self.faa.print_info(text="点击了 [继续作战] 图标")
            return True
        return False

    def check_end(self):
        # 找到战利品字样(被黑色透明物遮挡,会看不到)
        result_is_end = match_ps_in_w(
            source_handle=self.faa.handle,
            source_root_handle=self.faa.handle_360,
            template_opts=[
                {
                    "source_range": [202, 419, 306, 461],
                    "template": RESOURCE_P["common"]["战斗"]["战斗后_1_战利品.png"],
                    "match_tolerance": 0.999
                },
                {
                    "source_range": [202, 419, 306, 461],
                    "template": RESOURCE_P["common"]["战斗"]["战斗后_2_战利品阴影版.png"],
                    "match_tolerance": 0.999
                },
                {
                    "source_range": [400, 47, 550, 88],
                    "template": RESOURCE_P["common"]["战斗"]["战斗后_3_战斗结算.png"],
                    "match_tolerance": 0.999
                },
                {
                    "source_range": [400, 35, 550, 75],
                    "template": RESOURCE_P["common"]["战斗"]["战斗后_4_翻宝箱.png"],
                    "match_tolerance": 0.999
                },
                {
                    "source_range": [350, 275, 600, 360],
                    "template": RESOURCE_P["error"]["登录超时.png"],
                    "match_tolerance": 0.999
                },
                {
                    "source_range": [350, 275, 600, 360],
                    "template": RESOURCE_P["error"]["断开连接.png"],
                    "match_tolerance": 0.999
                },
                {
                    "source_range": [350, 275, 600, 360],
                    "template": RESOURCE_P["error"]["Flash爆炸.png"],
                    "match_tolerance": 0.999
                },
            ],
            return_mode="or")
        return result_is_end

    def use_card_once(self, num_card: int, num_cell: str, click_space=True):
        """
        Args:
            num_card: 使用的卡片的序号
            num_cell: 使用的卡片对应的格子 从左上开始 "1-1" to "9-7"
            click_space:  是否点一下空白地区防卡住
        """
        # 注 美食大战老鼠中 放卡动作 需要按下一下 然后拖动 然后按下并松开 才能完成 整个动作
        T_ACTION_QUEUE_TIMER.add_click_to_queue(
            handle=self.faa.handle,
            x=self.faa.bp_card[num_card][0],
            y=self.faa.bp_card[num_card][1])
        time.sleep(self.click_sleep)

        T_ACTION_QUEUE_TIMER.add_click_to_queue(
            handle=self.faa.handle,
            x=self.faa.bp_cell[num_cell][0],
            y=self.faa.bp_cell[num_cell][1])
        time.sleep(self.click_sleep)

        # 点一下空白
        if click_space:
            T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.faa.handle, x=200, y=350)
            time.sleep(self.click_sleep)
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.faa.handle, x=200, y=350)
            time.sleep(self.click_sleep)

    def use_weapon_skill(self):
        """使用武器技能"""
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.faa.handle, x=23, y=200)
        time.sleep(self.click_sleep)
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.faa.handle, x=23, y=250)
        time.sleep(self.click_sleep)
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.faa.handle, x=23, y=297)
        time.sleep(self.click_sleep)

    def auto_pickup(self):
        if self.faa.is_auto_pickup:
            for coordinate in self.auto_collect_cells_coordinate:
                T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.faa.handle, x=coordinate[0], y=coordinate[1])
                time.sleep(self.click_sleep)

    def update_fire_elemental_1000(self):
        image = capture_image_png(handle=self.faa.handle, raw_range=[161, 75, 164, 85])
        image = image[:, :, :3]
        image = image.reshape(-1, image.shape[-1])  # 减少一个多余的维度
        self.fire_elemental_1000 = np.any(image == [0, 0, 0])

        # 调试打印
        # if self.faa.player == 1:
        #     self.faa.print_debug("战斗火苗能量>1000:", self.fire_elemental_1000)
