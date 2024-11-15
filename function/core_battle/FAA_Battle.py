import copy
import time

import numpy as np

from function.common.bg_img_match import match_p_in_w, match_ps_in_w, loop_match_p_in_w
from function.common.bg_img_screenshot import capture_image_png
from function.globals import EXTRA
from function.globals.g_resources import RESOURCE_P
from function.globals.log import CUS_LOGGER
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER


class Battle:
    def __init__(self, faa):
        """FAA的战斗类，包含了各种战斗中专用的方法"""
        # 复制faa实例的属性
        # 如果直接调用该类可以从faa实例中获取动态变化的其属性值, 但如果赋值到本类内部属性则会固定为静态
        self.faa = faa

        # 战斗专用私有属性 - 每次战斗刷新
        self.is_used_key = False  # 仅由外部信号更改, 用于标识战斗是否使用了钥匙
        self.fire_elemental_1000 = None
        self.smoothie_usable = None
        self.wave = 0  # 当前波次归零

        self.player_locations = None  # 战斗开始放人物的位置 - 代号list
        self.shovel_locations = None  # 放铲子的位置 - 代号list
        self.shovel_coordinates = None  # 放铲子的位置 - 坐标list

        # 战斗专用私有属性 - 静态
        self.click_sleep = 1 / EXTRA.CLICK_PER_SECOND * 2  # 每次点击时 按下和抬起之间的间隔 秒

        # 自动拾取的格子
        self.auto_collect_cells = [
            "1-1", "2-1", "3-1", "4-1", "5-1", "6-1", "7-1", "8-1", "9-1",
            "1-2", "2-2", "3-2", "4-2", "5-2", "6-2", "7-2", "8-2", "9-2",
            "1-3", "2-3", "3-3", "4-3", "5-3", "6-3", "7-3", "8-3", "9-3",
            "1-4", "2-4", "3-4", "4-4", "5-4", "6-4", "7-4", "8-4", "9-4",
            "1-5", "2-5", "3-5", "4-5", "5-5", "6-5", "7-5", "8-5", "9-5",
            "1-6", "2-6", "3-6", "4-6", "5-6", "6-6", "7-6", "8-6", "9-6",
            "1-7", "2-7", "3-7", "4-7", "5-7", "6-7", "7-7", "8-7", "9-7"
        ]

        # 自动拾取的坐标
        self.auto_collect_cells_coordinate = []
        for i in self.auto_collect_cells:
            self.auto_collect_cells_coordinate.append(self.faa.bp_cell[i])

    """ 战斗方案和关卡方案的处理"""

    def init_battle_plan_shovel(self, locations):

        self.shovel_locations = copy.deepcopy(locations)

        self.faa.print_debug(f"[战斗执行器] 即将铲卡, 位置:{self.shovel_locations}")

        bp_cell = copy.deepcopy(self.faa.bp_cell)
        list_shovel = copy.deepcopy(self.shovel_locations)
        list_shovel = [bp_cell[location] for location in list_shovel]
        self.shovel_coordinates = copy.deepcopy(list_shovel)

    def init_battle_plan_player(self, locations):
        self.player_locations = copy.deepcopy(locations)

    """ 战斗内的子函数 """

    def re_init(self):
        """战斗前调用, 重新初始化部分每场战斗都要重新刷新的该内私有属性"""
        self.is_used_key = False
        self.fire_elemental_1000 = False
        self.smoothie_usable = self.faa.player == 1
        self.wave = 0  # 当前波次归零

    def use_player_all(self):

        self.faa.print_info(text="[战斗] 开始放置玩家:{}".format(self.player_locations))

        for location in self.player_locations:
            self.use_player(location=location)

    def use_player(self, location):
        T_ACTION_QUEUE_TIMER.add_click_to_queue(
            handle=self.faa.handle,
            x=self.faa.bp_cell[location][0],
            y=self.faa.bp_cell[location][1])
        time.sleep(self.click_sleep)
        T_ACTION_QUEUE_TIMER.add_click_to_queue(
            handle=self.faa.handle,
            x=self.faa.bp_cell[location][0],
            y=self.faa.bp_cell[location][1])
        time.sleep(self.click_sleep)

    def use_shovel_all(self, coordinates=None):
        """
        用全部的铲子
        """

        # 战斗操作锁
        with self.faa.battle_lock:

            if coordinates is None:
                coordinates = self.shovel_coordinates

            for coordinate in coordinates:
                self.use_shovel(x=coordinate[0], y=coordinate[1])

    def use_shovel(self, x, y):
        """
        :param x: 像素坐标
        :param y: 像素坐标
        :return:
        """
        T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=self.faa.handle, key="1")
        time.sleep(self.click_sleep)  # 必须的间隔
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.faa.handle, x=x, y=y)
        time.sleep(self.click_sleep * 2)

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

        img = capture_image_png(
            handle=self.faa.handle,
            root_handle=self.faa.handle_360,
            raw_range=[0, 0, 950, 600])

        # 找到战利品字样(被黑色透明物遮挡,会看不到)
        result = match_ps_in_w(
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
            return_mode="or",
            quick_mode=True,
            source_img=img
        )

        return result

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
        # 注意上锁, 防止和放卡冲突
        with self.faa.battle_lock:
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.faa.handle, x=23, y=200)
            time.sleep(self.click_sleep)
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.faa.handle, x=23, y=250)
            time.sleep(self.click_sleep)
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.faa.handle, x=23, y=297)
            time.sleep(self.click_sleep)

    def auto_pickup(self):
        if not self.faa.is_auto_pickup:
            return
        # 注意上锁, 防止和放卡冲突
        with self.faa.battle_lock:
            for coordinate in self.auto_collect_cells_coordinate:
                T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.faa.handle, x=coordinate[0], y=coordinate[1])
                time.sleep(self.click_sleep)

    def update_fire_elemental_1000(self, img=None):
        if img is None:
            img = capture_image_png(
                handle=self.faa.handle,
                raw_range=[0, 0, 950, 600],
                root_handle=self.faa.handle_360
            )
        img = img[75:85, 161:164, :3]
        img = img.reshape(-1, img.shape[-1])  # 减少一个多余的维度
        self.fire_elemental_1000 = np.any(img == [0, 0, 0])

        # # 调试打印
        # if self.faa.player == 1:
        #     # self.faa.print_debug("战斗火苗能量>1000:", self.fire_elemental_1000)
        #     CUS_LOGGER.debug(f"有没有1000火{self.fire_elemental_1000}")

    def check_wave(self, img=None):
        """识图检测目前的波次"""

        new_wave = self.match_wave(img=img)

        # 如果检测失败，使用当前波次
        if not new_wave:
            new_wave = self.wave

        # 波次无变化
        if self.wave == new_wave:
            # CUS_LOGGER.debug(f"[{self.faa.player}P] 当前波次:{self.wave}, 识别波次:{new_wave}无变化")
            return False

        # 更新变量
        self.wave = new_wave

        # 新波次无方案
        if str(new_wave) not in self.faa.battle_plan["card"]["wave"].keys():
            CUS_LOGGER.debug(f"[{self.faa.player}P] 当前波次:{new_wave}, 已检测到转变, 但该波次无变阵方案")
            return False

        CUS_LOGGER.debug(f"[{self.faa.player}P] 当前波次:{new_wave}, 已检测到转变, 即将启动变阵方案")

        # 备份旧方案
        plans = {
            "old": copy.deepcopy(self.faa.battle_plan_card),
            "new": None
        }

        # 重载战斗方案
        self.faa.init_battle_plan_card()
        # 获取新方案
        plans["new"] = copy.deepcopy(self.faa.battle_plan_card)

        """差异铲卡 寻找id相同, 但上面的卡片的id不同的格子 全部铲一遍"""
        location_cid = {
            "old": {},
            "new": {}
        }
        need_shovel = []

        for x in range(1, 10):
            for y in range(1, 8):
                location = f"{x}-{y}"

                for p_type in ["old", "new"]:
                    if location not in location_cid[p_type]:
                        location_cid[p_type][location] = []

                    for card in plans[p_type]:

                        if location in card["location"]:
                            if card["name"] != "":
                                if "护罩" in card["name"] or "瓜皮" in card["name"]:
                                    location_cid[p_type][location].append(card["id"])

                if location_cid["old"][location] == location_cid["new"][location]:
                    continue
                else:
                    need_shovel.append(location)

        self.faa.faa_battle.init_battle_plan_shovel(need_shovel)

        if self.faa.is_main:
            self.use_shovel_all()

        return True

    def match_wave(self, img=None):

        if img is None:
            img = capture_image_png(
                handle=self.faa.handle,
                raw_range=[0, 0, 950, 600],
                root_handle=self.faa.handle_360
            )

        pix = img[552, 670][:3][::-1]  # 获取该像素颜色 注意将 GBRA -> RGB
        pix_dict = {
            0: (250, 213, 153),  # √
            1: (255, 233, 166),  # √
            2: (252, 200, 141),  # √
            3: (255, 223, 107),  # √
            4: (255, 247, 146),  # √
            5: (255, 228, 174),  # √
            6: (255, 251, 121),  # √
            7: (255, 223, 119),  # √
            8: (238, 218, 100),  # √
            9: (255, 196, 126),  # √
            10: (46, 37, 25),  # √
            11: (33, 13, 0),
            12: (135, 118, 65),
            13: (160, 150, 90),
        }

        for wave, color in pix_dict.items():
            if all(p == c for p, c in zip(pix, color)):
                if EXTRA.EXTRA_LOG_BATTLE:
                    CUS_LOGGER.debug(f"成功读取到波次: {wave}")
                return wave
        else:
            if EXTRA.EXTRA_LOG_BATTLE:
                CUS_LOGGER.warning("未能成功读取到波次, 可能在Boss战斗或选择是否钥匙. 默认返回 None")
            return None
