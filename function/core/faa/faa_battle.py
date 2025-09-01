import copy
import time
from typing import TYPE_CHECKING

import numpy as np

from function.common.bg_img_match import match_p_in_w, match_ps_in_w, loop_match_p_in_w
from function.common.bg_img_screenshot import capture_image_png
from function.common.window_recorder import WindowRecorder
from function.globals import EXTRA
from function.globals.g_resources import RESOURCE_P
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER

if TYPE_CHECKING:
    from function.core.faa.faa_mix import FAA


class FAABattle:

    def __init__(self):
        self.recorder = None

    def faa_battle_re_init(self: "FAA"):
        """战斗前调用, 重新初始化部分每场战斗都要重新刷新的该内私有属性"""
        self.is_used_key = False
        self.fire_elemental_1000 = False
        self.smoothie_usable = self.player == 1
        self.wave = 0  # 当前波次归零
        self.start_time = time.time()
        # 获取所有定时宝石事件
        gem_events = [e for e in self.battle_plan["events"] if e["action"]["type"] == "insert_use_gem"]

        if gem_events:
            # 获取最大波次
            self.max_wave = max(e["trigger"]["wave_id"] for e in gem_events)
        else:
            self.max_wave = -1

    """铲子"""

    def init_battle_plan_shovel(self: "FAA", locations):

        self.shovel_locations = copy.deepcopy(locations)

        self.print_debug(f"[战斗执行器] 即将铲卡, 位置:{self.shovel_locations}")

        bp_cell = copy.deepcopy(self.bp_cell)
        list_shovel = copy.deepcopy(self.shovel_locations)
        list_shovel = [bp_cell[location] for location in list_shovel]
        self.shovel_coordinates = copy.deepcopy(list_shovel)

    def use_shovel_all(self: "FAA", coordinates=None, need_lock=False):
        """
        用全部的铲子
        """

        if need_lock:
            with self.battle_lock:
                if coordinates is None:
                    coordinates = self.shovel_coordinates
                for coordinate in coordinates:
                    self.use_shovel(x=coordinate[0], y=coordinate[1])
        else:
            if coordinates is None:
                coordinates = self.shovel_coordinates
            for coordinate in coordinates:
                self.use_shovel(x=coordinate[0], y=coordinate[1])

    def use_shovel(self: "FAA", x, y):
        """
        :param x: 像素坐标
        :param y: 像素坐标
        :return:
        """
        # 选择铲子
        T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=self.handle, key="1")
        time.sleep(self.click_sleep)

        # 铲两次确保成功!
        for _ in range(2):
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=x, y=y)
            time.sleep(self.click_sleep)

    """人物"""

    def init_battle_plan_player(self: "FAA", locations):

        self.player_locations = copy.deepcopy(locations)

    def use_player_all(self: "FAA"):

        self.print_info(text="[战斗] 开始放置玩家:{}".format(self.player_locations))

        for location in self.player_locations:
            self.use_player(location=location)

    def use_player(self: "FAA", location):

        T_ACTION_QUEUE_TIMER.add_click_to_queue(
            handle=self.handle,
            x=self.bp_cell[location][0],
            y=self.bp_cell[location][1])
        time.sleep(self.click_sleep)
        T_ACTION_QUEUE_TIMER.add_click_to_queue(
            handle=self.handle,
            x=self.bp_cell[location][0],
            y=self.bp_cell[location][1])
        time.sleep(self.click_sleep)

    """状态监测"""

    def use_key(self: "FAA"):
        """
        使用钥匙的函数
        :return:
            None
        """

        # 如果 已经用过钥匙 直接输出
        if self.is_used_key:
            return False

        _, find = match_p_in_w(
            source_handle=self.handle,
            source_range=[386, 332, 463, 362],
            match_tolerance=0.95,
            template=RESOURCE_P["common"]["战斗"]["战斗中_继续作战.png"])

        # 立刻清空列表 就算堵. 也不会对点继续作战造成影响了!
        T_ACTION_QUEUE_TIMER.action_queue.queue.clear()

        if not find:
            return False

        self.print_info(text="找到了 [继续作战] 图标")

        while find:
            if self.need_key:
                template = RESOURCE_P["common"]["战斗"]["战斗中_继续作战.png"]
                source_range = [446, 340, 502, 354]
            else:
                template = RESOURCE_P["common"]["战斗"]["战斗中_领取奖品.png"]
                source_range = [544, 340, 606, 354]
            loop_match_p_in_w(
                template=template,
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=source_range,
                match_tolerance=0.95,
                match_interval=0.2,
                match_failed_check=10,
                after_sleep=0.25,
                click=True)

            # 是否还在选继续界面
            _, find = match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[302, 263, 396, 289],
                match_tolerance=0.95,
                template=RESOURCE_P["common"]["战斗"]["战斗中_精英鼠军.png"])

        if self.need_key:
            self.print_info(text="点击了 [继续作战] 图标")
            return True
        else:
            self.print_info(text="点击了 [领取奖品] 图标")
            return False

    def check_end(self: "FAA"):

        if EXTRA.MAX_BATTLE_TIME != 0:
            duration = time.time() - self.start_time
            if EXTRA.MAX_BATTLE_TIME * 60 < duration:
                self.print_info(text=f"[战斗] 战斗时间:{duration:.0f}s已到, 退出战斗")
                return True

        img = capture_image_png(
            handle=self.handle,
            root_handle=self.handle_360,
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

    def check_wave(self: "FAA", img=None) -> bool:
        """识图检测目前的波次"""

        new_wave = self.match_wave(img=img)

        # 如果检测失败，使用当前波次
        if not new_wave:
            new_wave = self.wave

        # 波次无变化
        if self.wave == new_wave:
            return False

        # 新波次无方案
        wave_ids = [
            e["trigger"]["wave_id"] for e in self.battle_plan["events"]
            if e["action"]["type"] == "loop_use_cards"
        ]

        if new_wave not in wave_ids:
            CUS_LOGGER.debug(f"[{self.player}P] 当前波次:{new_wave}, 已检测到转变, 但该波次无变阵方案")
            self.wave = new_wave
            return False

        CUS_LOGGER.info(f"[{self.player}P] 当前波次:{new_wave}, 已检测到转变, 即将启动变阵方案")

        # 备份旧方案
        plans = {
            "old": copy.deepcopy(self.battle_plan_card),
            "new": None
        }

        # 重载战斗方案
        self.init_battle_plan_card(wave=new_wave)

        # 获取新方案
        plans["new"] = copy.deepcopy(self.battle_plan_card)

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
                                if ("护罩" not in card["name"]) and ("瓜皮" not in card["name"]):
                                    location_cid[p_type][location].append(card["card_id"])

                if location_cid["old"][location] == location_cid["new"][location]:
                    continue
                else:
                    need_shovel.append(location)

        self.init_battle_plan_shovel(locations=need_shovel)
        self.use_shovel_all(need_lock=True)

        # 更新变量
        self.wave = new_wave
        return True

    def match_wave(self: "FAA", img=None):

        if img is None:
            img = capture_image_png(
                handle=self.handle,
                raw_range=[0, 0, 950, 600],
                root_handle=self.handle_360
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

    """其他动作"""

    def use_card_once(self: "FAA", card_id: int, location: str, click_space=True):
        """
        Args:
            card_id: 使用的卡片的序号
            location: 使用的卡片对应的格子 从左上开始 "1-1" to "9-7"
            click_space:  是否点一下空白地区防卡住
        """
        with self.battle_lock:
            # 注 美食大战老鼠中 放卡动作 需要按下一下 然后拖动 然后按下并松开 才能完成 整个动作
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=self.handle,
                x=self.bp_card[card_id][0] + 25,
                y=self.bp_card[card_id][1] + 35)
            time.sleep(self.click_sleep)

            for _ in range(2):
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=self.bp_cell[location][0],
                    y=self.bp_cell[location][1])
                time.sleep(self.click_sleep)

            # 点一下空白
            if click_space:

                T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=295, y=485)
                time.sleep(self.click_sleep)

                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=295, y=485)
                time.sleep(self.click_sleep)

    def use_gem_skill(self: "FAA"):
        """使用武器技能"""

        # 如果当前波次小于等于最大定时波次，禁止自动宝石点击
        if self.wave <= self.max_wave:
            CUS_LOGGER.debug(f"当前波次:{self.wave}, 最大定时波次:{self.max_wave}, 禁止自动宝石点击")
            return

        # 上锁, 防止和放卡冲突
        with self.battle_lock:
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=23, y=200)
            time.sleep(self.click_sleep)
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=23, y=250)
            time.sleep(self.click_sleep)
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=23, y=297)
            time.sleep(self.click_sleep)

    def auto_pickup(self: "FAA"):
        if not self.is_auto_pickup:
            return
        # 注意上锁, 防止和放卡冲突

        with self.battle_lock:
            for coordinate in self.auto_collect_cells_coordinate:
                T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=coordinate[0], y=coordinate[1])

                time.sleep(self.click_sleep)

    def update_fire_elemental_1000(self: "FAA", img=None):
        if img is None:
            img = capture_image_png(
                handle=self.handle,
                raw_range=[0, 0, 950, 600],
                root_handle=self.handle_360
            )
        img = img[75:85, 161:164, :3]
        img = img.reshape(-1, img.shape[-1])  # 减少一个多余的维度
        self.fire_elemental_1000 = np.any(img == [0, 0, 0])

        # # 调试打印
        # if self.player == 1:
        #     # self.print_debug("战斗火苗能量>1000:", self.fire_elemental_1000)
        #     CUS_LOGGER.debug(f"有没有1000火{self.fire_elemental_1000}")

    def start_battle_recording(self,timestamp):
        """战斗开始时启动录制"""
        if hasattr(self, 'handle'):
            self.recorder = WindowRecorder(output_file=PATHS["logs"]+"//recording//",window_title=self.channel,handle=self.handle,see_time= timestamp)
            self.recorder.start_recording()
            CUS_LOGGER.info("战斗录制已启动")

    def stop_battle_recording(self):
        """战斗结束时停止录制"""
        if hasattr(self, 'recorder') and self.recorder:
            if self.recorder is not None:
                self.recorder.stop_recording()
                CUS_LOGGER.info(f"战斗录制已保存")
                self.recorder= None
