import copy
import datetime
import math
import os
import random
import time
import traceback
from ctypes import windll
from threading import Timer, Thread
from typing import Union, TYPE_CHECKING
import numpy as np
import cv2

from PyQt6.QtCore import QThread, pyqtSignal

from function.common.bg_img_screenshot import capture_image_png, capture_image_png_all
from function.core_battle.card import Card, CardKun, SpecialCard
from function.core_battle.card_queue import CardQueue
from function.core_battle.special_card_strategy import solve_special_card_problem, solve_maximize_score_problem, \
    STRATEGIES_OB, STRATEGIES_2_OB
from function.globals import EXTRA, SIGNAL
from function.globals.get_paths import PATHS
from function.globals.location_card_cell_in_battle import COORDINATE_CARD_CELL_IN_BATTLE
from function.globals.log import CUS_LOGGER
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER

if TYPE_CHECKING:
    from function.core.todo import ThreadTodo
    from function.core.faa.faa_mix import FAA


def is_special_card(card_name):
    """判断是否为特殊卡，并返回匹配文件所在子目录的名称"""
    base_path = PATHS["image"]["card"] + "\\特殊对策卡"
    card_name = os.path.splitext(card_name)[0]  # 移除传入名字的扩展名

    # 遍历目录及其子目录
    for root, dirs, files in os.walk(base_path):
        for file in files:
            # 解析文件名并移除扩展名
            base_name = os.path.splitext(file)[0]
            energy = None
            rows = None
            cols = None
            if '_' in base_name:
                parts = base_name.split('_')
                base_name = parts[0]
                card_type = parts[1]
                if len(parts) > 2:
                    energy = int(parts[2])
                if len(parts) > 3:
                    cols = int(parts[3])
                if len(parts) > 4:  # 目前只有大十字
                    rows = int(parts[4])

            # 检查是否匹配
            if base_name == card_name:
                # 计算子目录的名称
                subdir_name = os.path.relpath(root, base_path)
                return {
                    "found": True,
                    "subdir_name": subdir_name,
                    "energy": energy,
                    "card_type": int(card_type),
                    "rows": rows,
                    "cols": cols}
                # 返回匹配状态和匹配文件所在子目录的名称

    # 如果没有找到匹配的文件，返回匹配状态为False
    return {"found": False}
def is_obstacle_card(card_name):
    """判断是否为清障类卡，并返回匹配文件所在子目录的名称"""
    base_path = PATHS["image"]["card"] + "\\障碍对策"
    card_name = os.path.splitext(card_name)[0]  # 移除传入名字的扩展名

    # 遍历目录及其子目录
    for root, dirs, files in os.walk(base_path):
        for file in files:
            # 解析文件名并移除扩展名
            base_name = os.path.splitext(file)[0]
            rows = None
            cols = None
            if '_' in base_name:
                parts = base_name.split('_')
                base_name = parts[0]
                card_type = parts[1]
                if len(parts) > 2:
                    cols = int(parts[2])
                if len(parts) > 3:
                    rows = int(parts[3])

            # 检查是否匹配
            if base_name == card_name:
                # 计算子目录的名称
                subdir_name = os.path.relpath(root, base_path)
                return {
                    "found": True,
                    "subdir_name": subdir_name,
                    "card_type": int(card_type),
                    "rows": rows,
                    "cols": cols}
                # 返回匹配状态和匹配文件所在子目录的名称

    # 如果没有找到匹配的文件，返回匹配状态为False
    return {"found": False}

# # 示例使用
# card_name = "电音镭射喵"
# result = is_special_card(card_name)
#
# if result["found"]:
#     print(f"{card_name} 是特殊卡，位于子目录：{result['subdir_name']},耗能为{result['energy']},类型为{result['card_type']}")
# else:
#     print(f"{card_name} 不是特殊卡，未找到匹配文件。")

class CardManager(QThread):
    # 注册信号
    signal_change_card_plan = pyqtSignal()
    signal_used_key = pyqtSignal()
    signal_stop = pyqtSignal()

    def __init__(
            self,
            todo: "ThreadTodo",
            faa_a: "FAA",
            faa_b: "FAA",
            solve_queue, senior_callback_interval, start_time, check_interval=0.5):
        """
        :param faa_a: 主号 -> 1
        :param faa_b: 副号 -> 2
        :param solve_queue: 高危目标待解决列表 如果为None 说明高级战斗未激活
        :param senior_callback_interval: 高级战斗回调函数 间隔时间
        :param check_interval: 许多项检测的时间间隔
        :param start_time: 用于校准计时器 游戏开始的时间戳
        """

        super().__init__()
        # # 完成构造函数的所有初始化工作后，设置 is_initialized 为 True
        # self.is_initialized = False

        """
        从外部强引用的类, 结束时注意清理引用
        """

        self.todo = todo

        # 多人作战, a代表队长 b代表队友; 单人作战, a代表目标 b为None
        self.faa_dict = {1: faa_a, 2: faa_b}
        self.is_group = copy.deepcopy(faa_a.is_group)
        self.pid_list = [1, 2] if self.is_group else [1]

        # 待解决队列，从这里提取信息
        self.solve_queue = solve_queue

        # 高级战斗的间隔时间
        self.senior_interval = senior_callback_interval

        # 精准战斗开始时间
        self.start_time = start_time

        # 一轮检测的时间 单位s
        self.check_interval = check_interval

        # 一次点击的时间 单位s
        self.click_sleep = faa_a.click_sleep

        """
        线程管理
        """

        self.running = False
        self.card_list_dict = {}
        self.card_list_unique = {}
        self.special_card_list = {}

        self.break_ice_card_list = {}
        self.kun_cards_dict = {}
        self.card_queue_dict = {}

        thread_dict_value_types = Union[
            ThreadCheckTimer, ThreadUseCardTimer, ThreadUseSpecialCardTimer, ThreadInsertUseCardTimer]
        self.thread_dict: dict[int, thread_dict_value_types] = {}

        self.insert_action_sub_timers = []

        """
        功能属性
        """

        # 特殊放卡列表
        self.ice_boom_dict_list = {1: [], 2: []}
        self.the_9th_fan_dict_list = {1: [], 2: []}
        self.shield_dict_list = {1: [], 2: []}
        self.obstacle_card_list = {1: [], 2: []}

        # 刷新全局冰沙锁
        EXTRA.SMOOTHIE_LOCK_TIME = 0

        """
        信号绑定
        """

        self.signal_change_card_plan.connect(self.change_card_plan)
        self.signal_used_key.connect(self.set_is_used_key_true)
        self.signal_stop.connect(self.stop)

        # 先创建 card_list_dict
        self.init_from_battle_plan()

    def run(self):

        # 开始线程
        self.start_sub_threads()

        # 开启事件循环
        self.exec()

    def stop(self):

        CUS_LOGGER.info("[战斗执行器] [CardManager] stop 开始")

        self.stop_sub_threads()  # 停止子线程
        self.faa_dict.clear()  # 清空faa字典

        for timer in self.insert_action_sub_timers:
            # 取消还在运行中的定时任务
            timer.cancel()
        self.insert_action_sub_timers = None

        # 中止自身, 并让调用线程等待该操作完成
        self.exit()
        self.wait()

        CUS_LOGGER.debug("[战斗执行器] [CardManager] stop 结束")

        # 在战斗结束后 打印上一次战斗到这一次战斗之间, 累计的点击队列状态
        CUS_LOGGER.info(f"[战斗执行器] [CardManager] 在本场战斗中, 点击队列变化状态如下, 可判断是否出现点击队列积压的情况")
        undone_times = T_ACTION_QUEUE_TIMER.print_queue_statue()
        if undone_times > 100:
            SIGNAL.DIALOG.emit(
                "警告 - 战斗中点击队列无法及时处理完毕, 堆积超过100",
                "请按照提示优化问题, 否则可能出现无法点击继续战斗按钮等问题.\n"
                "1. 减少战斗方案中需要轮替放置的卡牌数; 错误案例: 每个格子上三张瓜皮\n"
                "2. 进阶功能 - 点击频率适当提高 (120 -> 150 -> 180); \n"
                "3. 进阶功能 - 游戏最低帧数, 适当调低 (10 -> 7 -> 5)")

        # 退出父线程的事件循环
        self.todo.exit()

        # 清理引用
        self.todo = None
        self.faa_dict = None
        self.solve_queue = None

    def init_from_battle_plan(self):

        def init_card_list_dict():
            def init_card_list_dict_normal(cards_plan, faa, pid):
                for set_priority in range(len(cards_plan)):
                    # 未激活高级战斗
                    card = Card(faa=faa, set_priority=set_priority)
                    self.card_list_dict[pid].append(card)
                    continue

            def init_card_list_dict_advanced(cards_plan, faa, pid):
                # 激活了高级战斗
                for set_priority in range(len(cards_plan)):

                    result1 = is_special_card(cards_plan[set_priority]["name"])
                    result2 = is_obstacle_card(cards_plan[set_priority]["name"])

                    if not result1["found"] and not result2["found"]:
                        # 普通卡
                        card = Card(faa=faa, set_priority=set_priority)
                        self.card_list_dict[pid].append(card)
                        continue
                    if result1["found"]:
                        # 高级战斗目标
                        if result1["card_type"] == 11:
                            # 冰桶类
                            s_card = SpecialCard(
                                faa=faa,
                                set_priority=set_priority,
                                energy=result1["energy"],
                                card_type=result1["card_type"])
                            self.ice_boom_dict_list[pid].append(s_card)

                        elif result1["card_type"] == 14:
                            # 草扇
                            s_card = SpecialCard(
                                faa=faa,
                                set_priority=set_priority,
                                energy=result1["energy"],
                                card_type=result1["card_type"])
                            self.the_9th_fan_dict_list[pid].append(s_card)

                        elif result1["card_type"] <= 15:
                            # 各种炸弹类卡片 包括瓜皮类炸弹
                            s_card = SpecialCard(
                                faa=faa,
                                set_priority=set_priority,
                                energy=result1["energy"],
                                card_type=result1["card_type"],
                                rows=result1["rows"],
                                cols=result1["cols"])
                            self.special_card_list[pid].append(s_card)

                            if result1["card_type"] == 12:
                                # 护罩类，除了炸弹还可能是常驻的罩子
                                card_shield = Card(faa=faa, set_priority=set_priority)
                                s_card = SpecialCard(
                                    faa=faa,
                                    set_priority=set_priority,
                                    energy=result1["energy"],
                                    card_type=result1["card_type"],
                                    rows=result1["rows"],
                                    cols=result1["cols"],
                                    n_card=card_shield)  # 建立特殊卡护罩与常规卡护罩之间的连接
                                # 以特殊卡加入特殊放卡
                                self.shield_dict_list[pid].append(s_card)
                                # 以普通卡版本加入放卡
                                self.card_list_dict[pid].append(card_shield)
                    if result2["found"]:
                        if result2["card_type"] == 17:
                            # 各种碎冰类卡片
                            s_card = SpecialCard(
                                faa=faa,
                                set_priority=set_priority,
                                card_type=result2["card_type"],
                                rows=result2["rows"],
                                cols=result2["cols"])
                            self.break_ice_card_list[pid].append(s_card)
                        elif result2["card_type"] == 18:
                            # 各种清障类卡片
                            s_card = SpecialCard(
                                faa=faa,
                                set_priority=set_priority,
                                card_type=result2["card_type"],
                                rows=result2["rows"],
                                cols=result2["cols"])
                            self.obstacle_card_list[pid].append(s_card)
                        elif result2["card_type"] == 19:
                            # 全屏清障类卡片
                            s_card = SpecialCard(
                                faa=faa,
                                set_priority=set_priority,
                                card_type=result2["card_type"])
                            self.obstacle_card_list[pid].append(s_card)
            for pid in self.pid_list:

                faa = self.faa_dict[pid]

                self.card_list_dict[pid] = []
                self.special_card_list[pid] = []

                if self.solve_queue is None:
                    init_card_list_dict_normal(cards_plan=faa.battle_plan_card, faa=faa, pid=pid)
                else:
                    init_card_list_dict_advanced(cards_plan=faa.battle_plan_card, faa=faa, pid=pid)

            for pid in self.pid_list:
                kun_cards = []
                # 添加坤
                kun_cards_info = self.faa_dict[pid].kun_cards_info
                if kun_cards_info:
                    for kun_card_info in kun_cards_info:
                        kun_card = CardKun(
                            faa=self.faa_dict[pid],
                            name=kun_card_info["name"],
                            c_id=kun_card_info["card_id"],
                            coordinate_from=kun_card_info["coordinate_from"],
                        )
                        kun_cards.append(kun_card)
                self.kun_cards_dict[pid] = kun_cards
                for card in self.card_list_dict[pid]:
                    if card.kun > 0:
                        card.kun_cards = kun_cards
            for pid in self.pid_list:
                sorted_cards = sorted(self.card_list_dict[pid], key=lambda x: x.c_id)
                unique_cards = []
                seen = set()
                for card in sorted_cards:
                    if card.c_id not in seen:
                        seen.add(card.c_id)
                        unique_cards.append(card)
                # 按照c_id（卡槽位置）排序并去重
                self.card_list_unique[pid] = unique_cards

        def init_card_queue_dict():
            for pid in self.pid_list:
                self.card_queue_dict[pid] = CardQueue(
                    card_list=self.card_list_dict[pid],
                    handle=self.faa_dict[pid].handle,
                    handle_360=self.faa_dict[pid].handle_360)

        def init_all_thread():
            """
            初始化所有线程
            1 - FAA 检测线程1
            2 - FAA 检测线程2
            3 - FAA 用卡线程1
            4 - FAA 用卡线程2
            5 - FAA 定时用卡线程1
            6 - FAA 定时用卡线程2
            7 - 高级战斗线程
            :return:
            """
            # 在每个号开打前 打印上一次战斗到这一次战斗之间, 累计的点击队列状态
            CUS_LOGGER.info(f"[战斗执行器] 在两场战斗之间, 点击队列变化状态如下, 可判断是否出现点击队列积压的情况")
            undone_times = T_ACTION_QUEUE_TIMER.print_queue_statue()
            if undone_times > 100:
                SIGNAL.DIALOG.emit(
                    "警告 - 战斗中点击队列无法及时处理完毕, 堆积超过100",
                    "请按照提示优化问题, 否则可能出现无法点击继续战斗按钮等问题.\n"
                    "1. 减少战斗方案中需要轮替放置的卡牌数; 错误案例: 每个格子上三张瓜皮\n"
                    "2. 进阶功能 - 点击频率适当提高 (120 -> 150 -> 180); \n"
                    "3. 进阶功能 - 游戏最低帧数, 适当调低 (10 -> 7 -> 5)")

            # 实例化 检测线程 + 用卡线程+特殊用卡进程
            for pid in self.pid_list:
                self.thread_dict[pid] = ThreadCheckTimer(
                    card_queue=self.card_queue_dict[pid],
                    kun_cards=self.kun_cards_dict.get(pid, None),
                    faa=self.faa_dict[pid],
                    check_interval=self.check_interval,
                    signal_stop=self.signal_stop,
                    signal_used_key=self.signal_used_key,
                    signal_change_card_plan=self.signal_change_card_plan,
                    thread_dict=self.thread_dict,
                )
                self.thread_dict[pid + 2] = ThreadUseCardTimer(
                    card_queue=self.card_queue_dict[pid],
                    faa=self.faa_dict[pid]
                )
                self.thread_dict[pid + 4] = ThreadInsertUseCardTimer(
                    manager=self,
                    pid=pid,
                    faa=self.faa_dict[pid],
                    start_time=self.start_time
                )

            if self.solve_queue is not None:
                # 不是空的，说明启动了高级战斗
                self.thread_dict[7] = ThreadUseSpecialCardTimer(
                    bomb_card_list=self.special_card_list,
                    faa_dict=self.faa_dict,
                    callback_interval=self.senior_interval,
                    read_queue=self.solve_queue,
                    is_group=self.is_group,
                    ice_boom_dict_list=self.ice_boom_dict_list,
                    the_9th_fan_dict_list=self.the_9th_fan_dict_list,
                    shield_dict_list=self.shield_dict_list,
                    obstacle_card_list=self.obstacle_card_list,
                    break_ice_card_list=self.break_ice_card_list
                )

            CUS_LOGGER.info("[战斗执行器] 线程已全部实例化")
            # CUS_LOGGER.debug(self.thread_dict)

        # 先创建 card_list_dict
        init_card_list_dict()

        # 根据 card_list_dict 创建 card_queue_dict
        init_card_queue_dict()

        # 实例化线程
        init_all_thread()

    def start_sub_threads(self):

        # 防抖
        if self.running:
            return
        self.running = True

        # 开始线程
        for _, my_thread in self.thread_dict.items():
            my_thread.start()

        CUS_LOGGER.info("[战斗执行器] 子线程已全部启动.")

    def stop_sub_threads(self):

        # 防止 变换波次 和 结束战斗 同时发生
        if not self.running:
            return

        self.running = False

        CUS_LOGGER.info("[战斗执行器] CardManager - stop_use_card - 开始, 战斗放卡 全线程 将中止")

        # 中止已经存在的子线程
        for k, my_thread in self.thread_dict.items():
            if my_thread is not None:
                my_thread.stop()  # 调用它们注册的stop方法 包括了 子线程的子线程的中止和确保完成
        self.thread_dict.clear()  # 清空字典键值对

        # 释放卡片列表中的卡片的内存
        for key, card_list in self.card_list_dict.items():
            for card in card_list:
                card.destroy()  # 释放卡片内存
            card_list.clear()  # 清空卡片列表
        self.card_list_dict.clear()  # 清空字典键值对

        # 释放特殊卡内存
        for key, card_list in self.special_card_list.items():
            for card in card_list:
                card.destroy()  # 释放卡片内存
            card_list.clear()  # 清空卡片列表
        self.special_card_list.clear()  # 清空字典键值对

        # 释放坤坤卡的内存
        for key, card_list in self.kun_cards_dict.items():
            for card in card_list:
                card.destroy()  # 清空字典键值对

        # 释放卡片队列内存
        for key, card_queue in self.card_queue_dict.items():
            card_queue.queue.clear()  # 清空卡片队列
        self.card_queue_dict.clear()  # 清空卡片队列字典

        CUS_LOGGER.info("[战斗执行器] CardManager - stop_use_card - 结束")

    def change_card_plan(self):
        """如果战斗方案发生了变更"""

        self.start_time = time.time()

        # 注意线程同步问题. 需要确保两个FAA都已经完成了波次检测, 并完成了对应的方案切换后, 再进行重载.
        if self.is_group:
            for i in range(50):
                if self.faa_dict[1].wave != self.faa_dict[2].wave:
                    time.sleep(0.1)

        self.stop_sub_threads()
        self.init_from_battle_plan()
        self.start_sub_threads()

    def set_is_used_key_true(self):
        """
        在作战时, 只要有任何一方 使用了钥匙, 都设置两个号在本场作战均是用了钥匙
        在战斗结束进行通报汇总分类 各个faa都依赖自身的该参数, 因此需要对两者都做更改
        此外, 双人双线程时, 有两个本线程的实例控制的均为同样的faa实例, 若一方用钥匙,另一方也会悲改为用, 但魔塔不会存在该问题, 故暂时不管.
        """

        CUS_LOGGER.debug("[战斗执行器] 成功接收到使用钥匙信号")

        self.faa_dict[1].is_used_key = True
        if self.is_group:
            self.faa_dict[2].is_used_key = True

    def _insert_use_shovel(self, pid, location):
        faa = self.faa_dict[pid]
        x = faa.bp_cell[location][0]
        y = faa.bp_cell[location][1]

        with faa.battle_lock:
            # 选择铲子
            T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=faa.handle, key="1")
            time.sleep(self.click_sleep)
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa.handle, x=x, y=y)
            time.sleep(self.click_sleep)

        CUS_LOGGER.debug(f"成功定时铲")
    def _ban_card_state_change(self, pid, cid,state):
        faa = self.faa_dict[pid]
        #cid参数为零将会通一对所有卡的ban状态进行修改
        if cid!=0:
            card=self.card_list_unique[pid][cid-1]

            with faa.battle_lock:
                card.banning=state
                CUS_LOGGER.debug(f"成功改变ban卡{card.name}状态{state}")
        else:
            with faa.battle_lock:
                for card in self.card_list_unique[pid]:
                    card.banning=state
            CUS_LOGGER.debug(f"成功改变所有卡状态{state}")

    def _insert_use_card(self, pid, card_id, location):

        faa = self.faa_dict[pid]
        # 做两次动作 保证百分百放下来!
        for _ in range(2):
            faa.use_card_once(card_id=card_id, location=location, click_space=True)

        CUS_LOGGER.debug("成功定时放卡")

        battle_log = False

        if battle_log:
            time.sleep(0.75)

            def try_get_picture_now(handle):
                windll.user32.SetProcessDPIAware()
                output_base_path = PATHS["logs"] + "\\yolo_output"
                now = datetime.datetime.now()
                timestamp = now.strftime("%Y%m%d%H%M%S")
                output_img_path = f"{output_base_path}/images/{timestamp}.png"
                original_image = capture_image_png_all(handle)[:, :, :3]
                cv2.imwrite(output_img_path, original_image)

            try_get_picture_now(handle=faa.handle)
            CUS_LOGGER.debug(f"成功定时放卡{card_id}于{location}")

    def _insert_use_gem(self, pid, gid):

        faa = self.faa_dict[pid]

        with faa.battle_lock:

            CUS_LOGGER.debug(f"[战斗执行器] ThreadTimePutCardTimer - use_gemstone 宝石{gid}启动")
            match gid:
                case 1:
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa.handle, x=23, y=200)
                case 2:
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa.handle, x=23, y=250)
                case 3:
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa.handle, x=23, y=297)
                case _:
                    CUS_LOGGER.warning(f"[战斗执行器] ThreadTimePutCardTimer - use_gemstone - 错误: id={id} 不存在")

        CUS_LOGGER.debug("成功定时宝石技能")
    def _escape(self, pid):

        faa = self.faa_dict[pid]

        with faa.battle_lock:

            CUS_LOGGER.debug(f"[战斗执行器] ThreadTimePutCardTimer - _escape 玩家{pid}逃跑中")
            if self.is_group:
                if self.thread_dict.get(pid):#检测线程
                    self.thread_dict[pid].stop()
                    self.thread_dict[pid]=None
                if self.thread_dict.get(pid+2):#用卡线程
                    self.thread_dict[pid+2].stop()
                    self.thread_dict[pid+2]=None
                if self.thread_dict.get(pid+4):#定时线程
                    self.thread_dict[pid+4].stop()
                    self.thread_dict[pid+4]=None
                #将打关参数改为单人
                self.pid_list.remove(pid)
                self.is_group=False
                if self.thread_dict.get(7):
                    self.thread_dict[7].is_group=False
                    self.thread_dict[7].pid_list.remove(pid)
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa.handle, x=924, y=576)
                time.sleep(self.click_sleep)
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa.handle, x=422, y=388)
                CUS_LOGGER.debug(f"玩家{pid}成功逃跑")
            else:
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa.handle, x=924, y=576)
                time.sleep(self.click_sleep)
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa.handle, x=422, y=388)
                CUS_LOGGER.debug(f"单人玩家成功逃跑")
                self.stop()

    def _handle_random_single_card(self, pid, card_index):
        """处理单卡随机：打乱指定卡片的位置顺序"""
        CUS_LOGGER.debug(f"尝试打乱单卡位置顺序{card_index}")
        if pid not in self.card_queue_dict:
            return

        card_queue = self.card_queue_dict[pid]
        if not card_queue.card_list:
            return

        if 0 <= card_index < len(card_queue.card_list):
            card = card_queue.card_list[card_index]

            # 打乱位置顺序
            import random
            if len(card.coordinate_to) > 1:
                random.shuffle(card.coordinate_to)
            CUS_LOGGER.debug(f"打乱卡{card.name}位置顺序{card.coordinate_to}")

    def _handle_random_multi_card(self, pid, card_indices):
        """处理多卡随机：仅在指定索引位置之间随机变换，其余保持原位置"""
        # time.sleep(1)
        CUS_LOGGER.debug(f"尝试打乱多卡玩家{pid}位置顺序{card_indices}")

        card_queue = self.card_queue_dict[pid]

        # 获取队列中所有卡片（每个item是(priority, card)的元组）
        items = []
        count=0
        while card_queue.empty():
            time.sleep(0.1)
            count+=1
            if count>100:
                break
        if card_queue.empty():
            CUS_LOGGER.debug(f"获取队列超时")
            return
        while not card_queue.empty():
            items.append(card_queue.get())
        CUS_LOGGER.debug(items)
        # 验证索引有效性并提取有效索引
        valid_indices = sorted([i for i in card_indices if 0 <= i < len(items)])
        if not valid_indices:
            # 无效索引直接恢复原队列
            for item in items:
                card_queue.put(item)
            return

        # 提取需要随机的卡片及其原始位置（保留priority信息）
        selected = [(i, items[i]) for i in valid_indices]
        original_positions = [i for i, _ in selected]
        cards_to_shuffle = [item for _, item in selected]  # 保留(priority, card)元组
        random.shuffle(cards_to_shuffle)

        # 创建新的重组列表
        reordered = items.copy()

        # 将打乱后的卡片放回原指定位置
        for pos, item in zip(original_positions, cards_to_shuffle):
            reordered[pos] = item  # 直接替换整个元组

        # 为打乱后的卡片分配新的优先级
        for idx, (priority, card) in enumerate(reordered):
            if idx in valid_indices:
                card.set_priority = idx  # 修改卡片的优先级
        # 重新恢复队列
        for priority, card in reordered:
            card_queue.put((card.set_priority, card))  # 使用新的优先级重新入队
        CUS_LOGGER.debug(f"打乱前: {[item[1].name for item in items]}")
        CUS_LOGGER.debug(f"打乱后: {[item[1].name for item in reordered]}")
        card_queue.print_self()
    def create_insert_timer_and_start(self, interval, func_name, func_kwargs):

        match func_name:
            case "insert_use_shovel":
                func = self._insert_use_shovel
            case "insert_use_card":
                func = self._insert_use_card
            case "insert_use_gem":
                func = self._insert_use_gem
            case "ban_card":
                func=self._ban_card_state_change
            case "escape":
                func=self._escape
            case "random_single_card":  # 新增单卡随机处理
                func = self._handle_random_single_card
            case "random_multi_card":  # 新增多卡随机处理
                func = self._handle_random_multi_card

        timer = Timer(interval=interval, function=lambda: func(**func_kwargs))
        timer.start()
        self.insert_action_sub_timers.append(timer)


class ThreadCheckTimer(QThread):
    """
    定时线程, 每个角色一个该线程
    该线程将以较低频率, 重新扫描更新目前所有卡片的状态, 以确定使用方式.
    """

    def __init__(self, card_queue, faa, kun_cards, check_interval,
                 signal_change_card_plan, signal_used_key, signal_stop, thread_dict):

        super().__init__()

        # 引用的类 注意消除引用
        self.card_queue = card_queue
        self.faa = faa
        self.kun_cards = kun_cards

        self.signal_change_card_plan = signal_change_card_plan
        self.signal_used_key = signal_used_key
        self.signal_stop = signal_stop

        self.running = False
        self.stopped = False
        self.timer = None
        self.checked_round = 0
        self.check_interval = check_interval  # 默认0.5s
        self.thread_dict = thread_dict  # 线程列表，以便动态修改参数
        self.check_interval_count = None
        if faa.battle_plan_tweak:
            self.faa.print_info(f"[战斗执行器] ThreadCheckTimer - check - 应用微调方案: {self.faa.battle_plan_tweak}")
            meta_data = self.faa.battle_plan_tweak.get('meta_data', {})
            cd_after_use_random_range = meta_data.get('cd_after_use_random_range')
            if cd_after_use_random_range:
                # 放卡间隔与重置单轮放卡间隔原初比例大约为0.036：1
                self.check_interval_count = (cd_after_use_random_range[0] + cd_after_use_random_range[1]) * 5 // 1
        else:
            self.faa.print_info(f"[战斗执行器] ThreadCheckTimer - check - 不应用微调方案")

    def run(self):
        self.timer = Timer(interval=self.check_interval, function=self.callback_timer)
        self.running = True
        self.timer.start()

        self.faa.print_info(f'[战斗执行器] ThreadCheckTimer 启动事件循环')
        self.exec()

    def stop(self):
        self.faa.print_info(text=f"[战斗执行器] ThreadCheckTimer - stop - 已激活, 将关闭战斗中检测线程")

        self.running = False
        if self.timer:
            self.timer.cancel()
        self.timer = None

        # 清除引用; 释放内存; 如果对应的timer正在运行中 会当场报错强制退出
        self.card_queue = None
        self.faa = None
        self.kun_cards = None

        # 退出事件循环
        self.quit()
        self.wait()

    def callback_timer(self):
        """
        一轮检测, 包括结束检测 / 继续战斗检测 / 自动战斗的状态检测 / 定时武器使用和拾取 / 按波次变阵检测
        回调不断重复
        """

        try:
            self.check()
        except Exception as e:
            self.faa.print_warning(
                f"[战斗执行器] ThreadCheckTimer - callback_timer - 在运行中遭遇错误"
                f"可能是Timer线程所需参数已被释放. 后有Timer进入执行状态. 这是正常情况. 错误信息: {e}"
            )
            self.running = False

        # 回调
        if self.running:
            self.timer = Timer(interval=self.check_interval, function=self.callback_timer)
            self.timer.start()

    def check(self):
        self.checked_round += 1

        """结束检测"""
        # 仅房主完成该检测操作
        if self.faa.is_main:
            self.running = not self.faa.check_end()
            if not self.running:
                if not self.stopped:
                    # 正常结束，非主动杀死线程结束
                    self.faa.print_info(text='[战斗执行器] 房主 检测到战斗结束标志, 即将关闭战斗中放卡的线程')
                    self.signal_stop.emit()
                    # 防止stop后再次调用 信号发出到中止事件循环可期间, 本函数还会多次运行.
                    self.stopped = True
                return

        """钥匙检测"""
        # 尝试使用钥匙 如成功 发送信号 修改faa.battle中的is_used_key为True 以标识用过了, 如果不需要使用或用过了, 会直接Fals
        # 不需要判定主号 直接使用即可
        if self.faa.use_key():
            self.signal_used_key.emit()

        """ 自动战斗"""

        if not self.faa.is_auto_battle:
            return

        # 仅截图一次, 降低重复次数
        game_image = capture_image_png(
            handle=self.faa.handle,
            root_handle=self.faa.handle_360,
            raw_range=[0, 0, 950, 600],
        )

        # 尝试检测变阵 注意仅主号完成该操作 操作的目标是manager实例对象
        result = self.faa.check_wave(img=game_image)
        if result:
            if self.faa.is_main:
                self.running = False
                self.signal_change_card_plan.emit()
                return

        # 先清空现有队列 再初始化队列 这里的重置队列要适应放卡间隔
        if self.check_interval_count is None or (self.checked_round % self.check_interval_count == 1):
            self.card_queue.queue.clear()
            self.card_queue.init_card_queue(
                game_image=game_image,
                check_interval=self.check_interval)

        # 更新火苗
        self.faa.update_fire_elemental_1000(img=game_image)

        # 根据情况判断是否加入执行坤函数的动作
        if self.kun_cards:
            self.check_for_kun(game_image=game_image)

        # 刷新全局冰沙锁 和 宝石技能锁 的状态
        if self.faa.is_group and self.faa.is_main:
            if EXTRA.SMOOTHIE_LOCK_TIME > 0:
                EXTRA.SMOOTHIE_LOCK_TIME -= self.check_interval
                if EXTRA.SMOOTHIE_LOCK_TIME <= 0:
                    EXTRA.SMOOTHIE_LOCK_TIME = 0

        # 调试打印 - 目前 <战斗管理器> 的状态
        if EXTRA.EXTRA_LOG_BATTLE:
            if self.faa.player == 1:
                text = f"[战斗执行器] [{self.faa.player}P] [第{self.checked_round}轮状态]"
                for card in self.card_queue.card_list:
                    text += "[{}|状:{}|CD:{}|用:{}|禁:{}|坤:{}] ".format(
                        card.name[:2] if len(card.name) >= 2 else card.name,
                        'T' if card.state_images["冷却"] is not None else 'F',
                        'T' if card.status_cd else 'F',
                        'T' if card.status_usable else 'F',
                        card.status_ban if card.status_ban else 'F',
                        'T' if card.is_kun_target else 'F')
                for card in self.kun_cards:
                    text += "[{}|状:{}|CD:{}|用:{}|禁:{}]".format(
                        card.name[:2] if len(card.name) >= 2 else card.name,
                        'T' if card.state_images["冷却"] is not None else 'F',
                        'T' if card.status_cd else 'F',
                        'T' if card.status_usable else 'F',
                        card.status_ban if card.status_ban else 'F')

                CUS_LOGGER.debug(text)

        # 定时 使用武器宝石技能 自动拾取 考虑到火苗消失时间是7s 快一点5s更好
        if self.checked_round % math.ceil(5 / self.check_interval) == 0:
            self.faa.use_gem_skill()
            self.faa.auto_pickup()

    def check_for_kun(self, game_image=None):
        """
        战斗中坤卡部分的检测
        """

        # 要求火苗1000+
        if not self.faa.fire_elemental_1000:
            return

        any_kun_usable = False

        for kun_card in self.kun_cards:

            # 检测坤卡是否已经成功获取到状态图片
            if kun_card.try_get_img_for_check_card_states() != 1:
                continue

            # 要求kun卡状态可用
            kun_card.fresh_status(game_image=game_image)
            if kun_card.status_usable:
                any_kun_usable = True

        if any_kun_usable:
            # 定位坤卡的目标
            kun_tar_index = 0
            max_card = None
            for i in range(len(self.card_queue.card_list)):
                card = self.card_queue.card_list[i]
                # 先将所有卡片的is_kun_target设置为False
                card.is_kun_target = False
                if not card.status_ban:
                    # 从没有被ban的卡中找出优先级最高的卡片
                    if card.kun > kun_tar_index:
                        kun_tar_index = card.kun
                        max_card = card
            # 设置优先级最高的卡片为kun目标
            if max_card:
                max_card.is_kun_target = True


class ThreadUseCardTimer(QThread):
    def __init__(self, card_queue, faa: "FAA"):
        super().__init__()
        """引用的类"""
        self.card_queue = card_queue
        self.faa = faa

        self.running = False
        self.timer = None
        self.interval_use_card = self.faa.click_sleep

    def run(self):
        self.timer = Timer(interval=self.interval_use_card, function=self.callback_timer)
        self.running = True
        self.timer.start()

        self.faa.print_info('[战斗执行器] ThreadUseCardTimer 启动事件循环')
        self.exec()

        self.running = False

    def stop(self):
        self.faa.print_info("[战斗执行器] ThreadUseCardTimer - stop - 已激活 中止事件循环")

        self.running = False
        if self.timer:
            self.timer.cancel()
        self.timer = None

        # 清除引用; 释放内存; 如果对应的timer正在运行中 会当场报错强制退出
        self.card_queue = None
        self.faa = None

        # 退出事件循环
        self.quit()
        # print("[战斗执行器] ThreadUseCardTimer - stop - 事件循环已退出")
        self.wait()
        # print("[战斗执行器] ThreadUseCardTimer - stop - 线程已等待完成")

    def callback_timer(self):
        try:
            self.card_queue.use_top_card()
        except Exception as e:
            # 获取完整的堆栈跟踪信息
            error_info = traceback.format_exc()
            CUS_LOGGER.warning(
                f"[战斗执行器] ThreadUseCardTimer - callback_timer - 在运行中遭遇错误\n"
                f"可能是Timer线程调用的参数已被释放后, 有Timer进入执行状态. 这是正常情况. 错误信息: {e}\n"
                f"详细堆栈信息:\n{error_info}"
            )

        # 回调
        if self.running:
            self.timer = Timer(interval=self.interval_use_card, function=self.callback_timer)
            self.timer.start()


class ThreadInsertUseCardTimer(QThread):
    def __init__(self, manager: CardManager, pid: int, faa: "FAA", start_time):
        super().__init__()
        """引用的类"""
        self.pid = pid
        self.manager = manager
        self.faa = faa
        self.callback_interval = 0.1
        self.interval_use_card = self.faa.click_sleep
        self.start_time = start_time

        # 初始化波次
        self.wave = -1
        # 初始化后的 第一波
        self.first_wave_this_init = True

        # 筛选出对应的战斗方案们
        self.insert_use_card_plan = [event for event in self.faa.battle_plan["events"] if (
                event["trigger"]["type"] == "wave_timer" and
                event["action"]["type"] == "insert_use_card"
        )]
        self.insert_use_shovel = [event for event in self.faa.battle_plan["events"] if (
                event["trigger"]["type"] == "wave_timer" and
                event["action"]["type"] == "shovel"
        )]
        self.insert_use_gem_plan = [event for event in self.faa.battle_plan["events"] if (
                event["trigger"]["type"] == "wave_timer" and
                event["action"]["type"] == "insert_use_gem"
        )]
        self.insert_escape_plan = [event for event in self.faa.battle_plan["events"] if (
                event["trigger"]["type"] == "wave_timer" and
                event["action"]["type"] == "escape"
        )]
        self.insert_ban_card_plan = [event for event in self.faa.battle_plan["events"] if (
                event["trigger"]["type"] == "wave_timer" and
                event["action"]["type"] == "ban_card"
        )]
        self.insert_random_single_plan = [event for event in self.faa.battle_plan["events"] if (
                event["trigger"]["type"] == "wave_timer" and
                event["action"]["type"] == "random_single_card"
        )]
        self.insert_random_multi_plan = [event for event in self.faa.battle_plan["events"] if (
                event["trigger"]["type"] == "wave_timer" and
                event["action"]["type"] == "random_multi_card"
        )]

        # 内联 card_name 字段
        for event in self.insert_use_card_plan:
            event["action"]["name"] = next((card["name"] for card in self.faa.battle_plan["cards"]), "")

        self.running = False
        self.timer = None

    def run(self):

        # 没有定时放卡plan，那就整个线程一开始就结束好了
        if (not self.insert_use_card_plan) and (not self.insert_use_shovel) and (not self.insert_use_gem_plan) and (not self.insert_escape_plan) and (not self.insert_ban_card_plan) and (not self.insert_random_single_plan) and (not self.insert_random_multi_plan):
            self.faa.print_debug('[战斗执行器] ThreadInsertUseCardTimer 方案不包含定时操作 不启用')
            return

        self.faa.print_debug('[战斗执行器] ThreadInsertUseCardTimer 启动')
        self.running = True

        self.timer = Timer(interval=self.callback_interval, function=self.callback_timer)
        self.timer.start()
        self.exec()

        self.running = False

    def stop(self):
        if not self.running:
            self.faa.print_info("[战斗执行器] ThreadInsertUseCardTimer - stop - 已激活 但其实压根没有启动过!")
            return

        self.faa.print_info("[战斗执行器] ThreadInsertUseCardTimer - stop - 已激活 中止事件循环")
        self.running = False

        if self.timer:
            self.timer.cancel()
        self.timer = None

        # 清理索引
        self.manager = None
        self.faa = None

        # 退出事件循环
        self.quit()
        self.wait()

    def callback_timer(self):

        try:
            # 获取当前波次
            if self.wave != self.faa.wave:
                self.wave = copy.deepcopy(self.faa.wave)
                # 识别到了新波次则设置该波次的定时放卡
                if self.first_wave_this_init:
                    time_change = time.time() - self.start_time
                    self.set_timer_for_wave(wave=self.wave, time_change=time_change)
                    if self.faa.is_main:
                        CUS_LOGGER.debug(f"[战斗执行器] ThreadInsertUseCardTimer 重新启动用了{time_change}秒, 将校准.")
                    self.first_wave_this_init = False
                else:
                    self.set_timer_for_wave(wave=self.wave, time_change=0)

        except Exception as e:
            # 获取完整的堆栈跟踪信息
            error_info = traceback.format_exc()
            CUS_LOGGER.warning(
                f"[战斗执行器] ThreadInsertUseCardTimer - callback_timer - 在运行中遭遇错误\n"
                f"可能是Timer线程调用的参数已被释放后, 有Timer进入执行状态. 这是正常情况. 错误信息: {e}\n"
                f"详细堆栈信息:\n{error_info}"
            )

        # 回调
        if self.running:
            self.timer = Timer(interval=self.callback_interval, function=self.callback_timer)
            self.timer.start()

    def set_timer_for_wave(self, wave, time_change=0.0):

        current_wave_plan = [
            event for event in self.insert_use_card_plan if event["trigger"]["wave_id"] == int(wave)]

        # 遍历创建所有定时器
        for battle_event in current_wave_plan:

            # 进行校准
            wait_time = max(0.0, float(battle_event["trigger"]["time"]) - time_change)

            if battle_event["action"]["before_shovel"]:
                self.manager.create_insert_timer_and_start(
                    interval=max(0.0, wait_time - 0.6),
                    func_name="insert_use_shovel",
                    func_kwargs={
                        "pid": self.pid,
                        "location": battle_event["action"]["location"]}
                )

            # 放卡定时器
            self.manager.create_insert_timer_and_start(
                interval=wait_time,
                func_name="insert_use_card",
                func_kwargs={
                    "pid": self.pid,
                    "card_id": battle_event["action"]["card_id"],
                    "location": battle_event["action"]["location"]}
            )

            if battle_event["action"]["after_shovel"]:
                self.manager.create_insert_timer_and_start(
                    interval=wait_time + battle_event["action"]["after_shovel_time"],
                    func_name="insert_use_shovel",
                    func_kwargs={
                        "pid": self.pid,
                        "location": battle_event["action"]["location"]}
                )

        current_wave_plan = [
            event for event in self.insert_use_shovel if event["trigger"]["wave_id"] == int(wave)]

        # 遍历铲子定时器
        for battle_event in current_wave_plan:
            # 铲卡定时器
            self.manager.create_insert_timer_and_start(
                interval=max(0.0, battle_event["trigger"]["time"] - time_change),
                func_name="insert_use_shovel",
                func_kwargs={
                    "pid": self.pid,
                    "location": battle_event["action"]["location"]}
            )
        current_wave_plan = [
            event for event in self.insert_ban_card_plan if event["trigger"]["wave_id"] == int(wave)]

        # 遍历ban卡定时器
        for battle_event in current_wave_plan:
            # 铲卡定时器
            self.manager.create_insert_timer_and_start(
                interval=max(0.0, battle_event["action"]["start_time"] - time_change),
                func_name="ban_card",
                func_kwargs={
                    "pid": self.pid,
                    "cid": battle_event["action"]["card_id"],
                    "state": True}
            )
            self.manager.create_insert_timer_and_start(
                interval=max(0.0, battle_event["action"]["end_time"] - time_change),
                func_name="ban_card",
                func_kwargs={
                    "pid": self.pid,
                    "cid": battle_event["action"]["card_id"],
                    "state": False}
            )
        current_wave_plan = [
            event for event in self.insert_escape_plan if event["trigger"]["wave_id"] == int(wave)]
        for battle_event in current_wave_plan:
            self.manager.create_insert_timer_and_start(
                interval=max(0.0, battle_event["trigger"]["time"] - time_change),
                func_name="escape",
                func_kwargs={
                    "pid": self.pid}
            )
        current_wave_plan = [
            event for event in self.insert_use_gem_plan if event["trigger"]["wave_id"] == int(wave)]

        for battle_event in current_wave_plan:
            self.manager.create_insert_timer_and_start(
                interval=max(0.0, battle_event["trigger"]["time"] - time_change),
                func_name="insert_use_gem",
                func_kwargs={
                    "pid": self.pid,
                    "gid": battle_event["action"]["gem_id"]}
            )
        current_wave_plan = [
            event for event in self.insert_random_single_plan if event["trigger"]["wave_id"] == int(wave)]

        for battle_event in current_wave_plan:
            self.manager.create_insert_timer_and_start(
                interval=max(0.0, battle_event["trigger"]["time"] - time_change),
                func_name="random_single_card",
                func_kwargs={
                    "pid": self.pid,
                    "card_index": battle_event["action"]["card_index"]}
            )
        current_wave_plan = [
            event for event in self.insert_random_multi_plan if event["trigger"]["wave_id"] == int(wave)]

        for battle_event in current_wave_plan:
            self.manager.create_insert_timer_and_start(
                interval=max(0.0, battle_event["trigger"]["time"] - time_change),
                func_name="random_multi_card",
                func_kwargs={
                    "pid": self.pid,
                    "card_indices": battle_event["action"]["card_indices"]}
            )


class ThreadUseSpecialCardTimer(QThread):
    def __init__(self, faa_dict, callback_interval, read_queue, is_group: bool,
                 bomb_card_list,obstacle_card_list,break_ice_card_list, ice_boom_dict_list, the_9th_fan_dict_list, shield_dict_list):
        """
        :param faa_dict:faa实例字典
        :param callback_interval:读取频率
        :param read_queue:高危目标队列
        :param is_group:是否组队
        :param bomb_card_list: 该类卡片为炸弹 在战斗方案中写入其from位置 在此处计算得出to位置 并进行其使用
        :param obstacle_card_list: 该类卡片为清障卡 在战斗方案中写入其from位置 在此处计算得出to位置 并进行其使用
        :param break_ice_card_list: 该类卡片为碎冰卡 在战斗方案中写入其from位置 在此处计算得出to位置 并进行其使用
        :param ice_boom_dict_list: 该类卡片为冰冻 在战斗方案中指定其from和to位置 在此处仅进行使用
        :param the_9th_fan_dict_list: 该类卡片为草扇 在战斗方案中指定其from和to位置 在此处仅进行使用
        :param shield_dict_list: 该类卡片为 炸弹类护罩 额外记录 以方便锁定和解锁相应的卡片的普通放卡
        """
        super().__init__()

        self.faa_dict = faa_dict
        self.running = False
        self.timer = None
        self.callback_interval = callback_interval
        self.read_queue = read_queue
        self.is_group = is_group
        self.flag = None
        self.todo_dict = {1: [], 2: []}
        self.card_list_can_use = {1: [], 2: []}
        self.card_list_can_use_obstacle = {1: [], 2: []}
        self.pid_list = [1, 2] if self.is_group else [1]

        # 记录每种类型的卡片 有哪些 格式
        # { 1: [obj_s_card_1, obj_s_card_2, ...], 2:[...] }
        self.special_card_list = bomb_card_list
        self.obstacle_card_list = obstacle_card_list
        self.break_ice_card_list = break_ice_card_list
        self.ice_boom_dict_list = ice_boom_dict_list
        self.the_9th_fan_dict_list = the_9th_fan_dict_list
        self.shield_dict_list = shield_dict_list

        self.shield_used_dict_list = {1: [], 2: []}
        
        # 添加记忆化障碍情况的属性
        self.obstacle_memory = []  # 存储最近几次的障碍情况
        self.score_matrix = np.zeros((7, 9))  # 7x9的评分矩阵，初始化为0
        self.max_memory_length = 5  # 最大记忆长度
        
        # 添加策略执行历史记录
        self.strategy_history = []  # 存储最近几次的策略执行记录
        self.max_strategy_history_length = 3  # 最大策略历史记录长度
        
        # 添加可调节参数
        self.min_appearances_for_real_obstacle = 2  # 判断为真实障碍的最小出现次数
        self.strategy_effect_duration = 3.3  # 策略效果持续时间（秒）
        self.score_reduction_during_strategy = 3  # 策略影响期间的评分降低值
        self.score_reduction_when_absent = 1  # 当前不存在时的评分降低值
        self.min_score_after_strategy_effect = 1.0  # 策略影响期间的最低评分
        """
        1. 障碍判断参数
        min_appearances_for_real_obstacle (默认值: 2)
        用途：判断一个位置是否为真实障碍所需的最小出现次数
        调整建议：
        增大该值：系统变得更保守，只有非常确定的障碍才会被处理
        减小该值：系统变得更敏感，可能会处理一些偶发的障碍
        2. 策略效果参数
        strategy_effect_duration (默认值: 3.3)
        用途：策略被认为有效的持续时间（秒）
        调整建议：
        增大该值：系统会给策略更长的生效时间窗口
        减小该值：系统会更快地重新评估策略效果
        3. 评分调整参数
        score_reduction_during_strategy (默认值: 3)
        用途：当位置受策略影响时的评分降低值
        调整建议：
        增大该值：系统更倾向于认为策略正在生效，会更大程度地降低评分
        减小该值：系统对策略效果持更保守态度
        min_score_after_strategy_effect (默认值: 1.0)
        用途：策略影响期间的最低评分（防止评分降至0）
        调整建议：
        增大该值：即使在策略影响下，障碍仍会被认为有一定重要性
        减小该值：策略影响下障碍的重要性会更低
        score_reduction_when_absent (默认值: 1)
        用途：当障碍当前不存在时的评分降低值
        调整建议：
        增大该值：系统更快地忘记已不存在的障碍
        减小该值：系统更缓慢地降低不存在障碍的评分
        4. 记忆长度参数
        max_memory_length (默认值: 5)
        用途：保存的障碍检测历史记录的最大数量
        调整建议：
        增大该值：系统考虑更多的历史信息，判断更稳定但响应较慢
        减小该值：系统更关注近期信息，响应更快但可能不够稳定
        max_strategy_history_length (默认值: 3)
        用途：保存的策略执行历史记录的最大数量
        调整建议：
        增大该值：系统考虑更多的策略历史，但可能增加计算负担
        减小该值：系统只关注最近的策略，计算更快但可能遗漏信息
        """
        
        # 添加可视化相关的属性
        self.visualization_thread = None
        self.visualization_running = False
        
        # 添加用于存储策略影响前评分矩阵的属性
        self.previous_score_matrix = np.zeros((7, 9))  # 7x9的评分矩阵，初始化为0
        self.now_score_matrix = np.zeros((7, 9))  # 7x9的评分矩阵，初始化为0

    def run(self):
        self.timer = Timer(interval=self.callback_interval, function=self.callback_timer)
        self.running = True
        self.timer.start()

        # 启动清障可视化线程（供调试看效果用）
        # self.start_visualization()

        self.faa_dict[1].print_debug('[战斗执行器] 启动特殊放卡线程')
        self.exec()

        self.running = False


    def stop(self):
        self.faa_dict[1].print_info("[战斗执行器] ThreadUseSpecialCardTimer stop方法已激活")

        self.running = False
        if self.timer:
            self.timer.cancel()
        self.timer = None

        # 停止可视化线程
        self.stop_visualization()

        # 清除引用; 释放内存; 如果对应的timer正在运行中 会当场报错强制退出
        self.faa_dict = None
        self.special_card_list = None
        self.read_queue = None

        # 退出事件循环
        self.quit()
        # print("[战斗执行器] ThreadUseCardTimer - stop - 事件循环已退出")
        self.wait()
        # print("[战斗执行器] ThreadUseCardTimer - stop - 线程已等待完成")


    def fresh_all_card_status(self):
        for pid in self.pid_list:
            faa = self.faa_dict[pid]
            # 仅截图一次, 降低重复次数
            game_image = capture_image_png(handle=faa.handle, raw_range=[0, 0, 950, 600], root_handle=faa.handle_360)

            for card_list_list in [self.special_card_list[pid], self.ice_boom_dict_list[pid],
                                   self.the_9th_fan_dict_list[pid]]:
                for card in card_list_list:
                    card.fresh_status(game_image)


    def check_special_card(self):

        result = self.read_queue.get()  # 不管能不能用对策卡先提取信息再说，免得队列堆积
        CUS_LOGGER.debug(f"从管道获取到状态信息：{result} ")
        if result is None:
            return

        self.pid_list = [1, 2] if self.is_group else [1]

        # 没有1000火的角色 从pid list中移除
        self.pid_list = [pid for pid in self.pid_list if self.faa_dict[pid].fire_elemental_1000]
        if not self.pid_list:
            return

        wave, god_wind, need_boom_locations, obstacle = result  # 分别为是否波次，是否神风及待炸点位列表,可清除障碍列表

        # 更新障碍记忆
        if obstacle is not None:
            self.update_obstacle_memory(obstacle)
            
            # 打印当前评分矩阵用于调试
            CUS_LOGGER.debug(f"当前障碍评分矩阵:\n{self.score_matrix}")

        
        if wave or god_wind or need_boom_locations or  obstacle:  # 任意一个就刷新状态
            CUS_LOGGER.debug(f"刷新特殊放卡状态")
            self.todo_dict = {1: [], 2: []}  # 1 2 对应两个角色
        else:
            return

        def wave_or_god_wind_append_to_todo(card_list) -> None:

            for pid in self.pid_list:

                not_got_state_images_card = [card for card in card_list[pid] if card.state_images["冷却"] is None]

                # 还有未完成试色的卡片, 直接指定其中一张使用并试色
                if not_got_state_images_card:
                    self.todo_dict[pid].append({
                        "card": not_got_state_images_card[0],
                        "location": not_got_state_images_card[0].location_template
                    })
                    return

                # 全部已试色
                for card in card_list[pid]:
                    card.fresh_status()
                    if card.status_usable:
                        self.todo_dict[pid].append({
                            "card": card,
                            "location": card.location_template})
                        return

        if wave:
            wave_or_god_wind_append_to_todo(card_list=self.ice_boom_dict_list)

        if god_wind:
            wave_or_god_wind_append_to_todo(card_list=self.the_9th_fan_dict_list)

        # 处理可清除障碍的最大化得分策略（与爆炸点位最小化成本策略独立并行）
        if obstacle is not None:
            self.card_list_can_use_obstacle = {1: [], 2: []}

            for pid in self.pid_list:

                # 获取 是否有卡片 没有完成状态监测
                not_got_state_images_cards = []
                for card in self.obstacle_card_list[pid]:
                    if card.state_images["冷却"] is None:
                        not_got_state_images_cards.append(card)
                CUS_LOGGER.debug(f"未完成列表{not_got_state_images_cards}")
                if not_got_state_images_cards:
                    # 如果有卡片未完成状态监测, 则将未完成状态监测的卡片加入到待处理列表中
                    self.card_list_can_use_obstacle[pid] = not_got_state_images_cards
                else:
                    # 如果均完成了状态监测, 则将所有状态为可用的卡片加入待处理列表中
                    self.card_list_can_use_obstacle[pid] = []
                for card in (set(self.obstacle_card_list[pid]) - set(self.card_list_can_use_obstacle[pid])):
                    card.fresh_status()
                    if card.status_usable:
                        self.card_list_can_use_obstacle[pid].append(card)
            CUS_LOGGER.debug(f"当前可用清障卡片队列{self.card_list_can_use_obstacle}")
            self.handle_maximize_score_strategy(obstacle)

        if need_boom_locations:
            self.card_list_can_use = {1: [], 2: []}
            self.shield_used_dict_list = {1: [], 2: []}

            for pid in self.pid_list:

                # 锁定所有护罩卡
                for shield in self.shield_dict_list[pid]:
                    if shield.n_card is not None:
                        shield.n_card.can_use = False

                # 获取 是否有卡片 没有完成状态监测
                not_got_state_images_cards = []
                for card in self.special_card_list[pid]:
                    if card.state_images["冷却"] is None:
                        not_got_state_images_cards.append(card)
                CUS_LOGGER.debug(f"未完成列表{not_got_state_images_cards}")
                if not_got_state_images_cards:
                    # 如果有卡片未完成状态监测, 则将未完成状态监测的卡片加入到待处理列表中
                    self.card_list_can_use[pid] = not_got_state_images_cards
                else:
                    # 如果均完成了状态监测, 则将所有状态为可用的卡片加入待处理列表中
                    self.card_list_can_use[pid] = []
                for card in (set(self.special_card_list[pid]) - set(self.card_list_can_use[pid])):
                    card.fresh_status()
                    if card.status_usable:
                        self.card_list_can_use[pid].append(card)
            CUS_LOGGER.debug(f"当前可用卡片队列{self.card_list_can_use}")
            result = solve_special_card_problem(
                points_to_cover=need_boom_locations,
                obstacles=self.faa_dict[1].stage_info["obstacle"],
                card_list_can_use=self.card_list_can_use)

            if result is not None:
                strategy1, strategy2 = result
                strategy_dict = {1: strategy1, 2: strategy2}
                for pid in self.pid_list:
                    for card, pos in strategy_dict[pid].items():
                        # 将计算完成的放卡结构 写入到对应角色的todo dict 中

                        self.todo_dict[pid].append({"card": card, "location": [f"{pos[0]}-{pos[1]}"]})
                        # 记录某个角色的某个护罩已经被使用过

                        if card.card_type == 12:
                            self.shield_used_dict_list[pid].append(card)

            # 计算后, 之前被锁定, 但并未使用的护罩, 将其可用属性恢复为True (被使用的使用完成后会自动归位为True)
            for pid in self.pid_list:
                unused_shields = []
                for card in self.shield_dict_list[pid]:
                    if card not in self.shield_used_dict_list[pid]:
                        unused_shields.append(card)
                for card in unused_shields:
                    card.n_card.can_use = True

        if wave or god_wind or need_boom_locations or obstacle is not None:  # 任意一个就刷新状态
            CUS_LOGGER.debug(f"特殊用卡队列: {self.todo_dict}")
            CUS_LOGGER.debug(f"0.01秒后开始特殊对策卡放卡")
            self.timer = Timer(interval=0.01, function=self.use_card, args=(1,))  # 1p 0.01秒后开始放卡
            self.timer.start()  # 按todolist用卡
            self.timer = Timer(interval=0.01, function=self.use_card, args=(2,))  # 2p 0.01秒后开始放卡
            self.timer.start()  # 按todolist用卡

    def callback_timer(self):

        try:
            self.check_special_card()
        except Exception as e:
            # 获取完整的堆栈跟踪信息
            error_info = traceback.format_exc()
            CUS_LOGGER.warning(
                f"[战斗执行器] ThreadUseSpecialCardTimer - callback_timer - 在运行中遭遇错误\n"
                f"可能是Timer线程调用的参数已被释放后, 有Timer进入执行状态. 这是正常情况. 错误信息: {e}\n"
                f"详细堆栈信息:\n{error_info}"
            )

        if self.running:
            self.timer = Timer(interval=self.callback_interval, function=self.callback_timer)
            self.timer.start()

    def use_card(self, player):

        for todo in self.todo_dict[player]:

            card = todo["card"]
            # format [‘x-y’,'x-y',...]
            card.location = todo["location"]
            # format [[x,y],[x,y]...]
            card.coordinate_to = [COORDINATE_CARD_CELL_IN_BATTLE[loc] for loc in card.location]

            result = card.try_get_img_for_check_card_states()
            if result == 0:
                # 什么? 怎么可能居然获取失败了?!
                card.location = []  # 清空location
                card.coordinate_to = []  # 清空coordinate_to
                continue
            elif result == 1:
                # 之前已经判定过肯定是获取到的
                card.use_card()
                card.location = []  # 清空location
                card.coordinate_to = []  # 清空coordinate_to
            elif result == 2:
                # 直接就通过试色完成了使用!
                card.location = []  # 清空location
                card.coordinate_to = []  # 清空coordinate_to
                continue

            # 清空对应任务
            self.todo_dict[player] = []

    def update_obstacle_memory(self, current_obstacles):
        """
        更新障碍记忆，维护一个固定长度的历史记录
        :param current_obstacles: 当前障碍列表
        """
        # 将当前障碍添加到记忆中，包含时间戳
        self.obstacle_memory.append({
            "time": time.time(),
            "obstacles": set(current_obstacles)
        })
        
        # 如果记忆超过最大长度，则移除最旧的记录
        if len(self.obstacle_memory) > self.max_memory_length:
            self.obstacle_memory.pop(0)
            
        CUS_LOGGER.debug(f"更新障碍记忆，当前记忆长度: {len(self.obstacle_memory)}")

    def handle_maximize_score_strategy(self, current_obstacles):
        """
        处理最大化得分策略（与爆炸点位最小化成本策略独立）
        :param current_obstacles: 当前障碍列表
        """

        
        # 根据记忆化的历史障碍信息生成可靠的评分矩阵
        self.update_score_matrix_from_memory(current_obstacles)

        # 设定阈值，用于区分真正存在的障碍和误识别/漏识别的障碍
        score_threshold = self.min_appearances_for_real_obstacle  # 使用可调节参数

        # 保存策略执行前的评分矩阵用于可视化显示
        self.now_score_matrix = self.score_matrix.copy()

        # 调用 solve_maximize_score_problem 获取最佳策略
        result = solve_maximize_score_problem(
            obstacles=self.faa_dict[1].stage_info["obstacle"],  # 传递固定障碍物列表
            score_matrix=self.score_matrix.tolist(),
            card_list_can_use=self.card_list_can_use_obstacle,
            score_threshold=score_threshold
        )

        if result is not None:
            strategy1, strategy2, strategy1_scores, strategy2_scores = result
            
            # 导入策略字典
            from function.core_battle.special_card_strategy import STRATEGIES_OB, STRATEGIES_2_OB
            
            # 为策略1添加覆盖范围信息
            strategy1_with_coverage = {}
            for card, pos in strategy1.items():
                coverage = STRATEGIES_OB.get(card, {}).get("coverage", [])
                strategy1_with_coverage[card] = {"pos": pos, "coverage": coverage}
            
            # 为策略2添加覆盖范围信息
            strategy2_with_coverage = {}
            for card, pos in strategy2.items():
                coverage = STRATEGIES_2_OB.get(card, {}).get("coverage", [])
                strategy2_with_coverage[card] = {"pos": pos, "coverage": coverage}

            # 创建策略记录
            strategy_record = {
                "time": time.time(),
                "strategy1": strategy1_with_coverage,
                "strategy2": strategy2_with_coverage,
                "scores1": strategy1_scores,
                "scores2": strategy2_scores
            }
            
            # 正式记录策略执行历史
            self.strategy_history.append(strategy_record)
            
            # 如果历史记录超过最大长度，则移除最旧的记录
            if len(self.strategy_history) > self.max_strategy_history_length:
                self.strategy_history.pop(0)

            # 根据策略执行操作
            strategy_dict = {1: strategy1, 2: strategy2}

            for pid in self.pid_list:
                for card, pos in strategy_dict[pid].items():
                    # 将计算完成的放卡结构 写入到对应角色的todo dict 中
                    self.todo_dict[pid].append({"card": card, "location": [f"{pos[0]}-{pos[1]}"]})



    def update_score_matrix_from_memory(self, current_obstacles, strategy_history=None):
        """
        根据记忆化的障碍历史更新评分矩阵，用于确定真正存在的障碍
        :param current_obstacles: 当前障碍列表
        :param strategy_history: 策略历史记录（可选，默认使用self.strategy_history）
        """
        # 重置评分矩阵
        self.score_matrix = np.zeros((7, 9))
        
        # 如果没有历史记录，则无需更新
        if not self.obstacle_memory:
            return
        
        current_time = time.time()
        
        # 统计每个位置在历史中作为障碍出现的次数，并考虑时间因素
        for record in self.obstacle_memory:
            time_diff = current_time - record["time"]
            # 根据时间差计算权重，越近的记录权重越高
            time_weight = 1.0
            if self.strategy_effect_duration > 0:
                # 距离现在越近权重越高，最多1.5倍权重
                time_weight = min(1.5, max(0.5, 1.0 + (0.5 * (self.strategy_effect_duration - time_diff) / self.strategy_effect_duration)))
            
            for obstacle in record["obstacles"]:
                # 解析障碍位置 "x-y" 格式
                x, y = map(int, obstacle.split('-'))
                # 转换为0基索引
                if 1 <= x <= 9 and 1 <= y <= 7:
                    self.score_matrix[y-1][x-1] += time_weight
        
        current_time = time.time()
        current_obstacle_set = set(current_obstacles)
        # 在执行策略前保存评分矩阵，确保正确反映策略执行前的状态
        self.previous_score_matrix = self.score_matrix.copy()
        # 对于每个位置，根据出现频率和策略影响来调整评分
        for y in range(7):
            for x in range(9):
                coord = f"{x+1}-{y+1}"
                
                # 检查该位置在最近几次检测中的出现次数
                recent_appearances = 0
                for record in self.obstacle_memory:
                    if coord in record["obstacles"]:
                        recent_appearances += 1
                
                # 检查最近是否有策略作用于该位置
                recent_strategy_effect = self.check_recent_strategy_effect(x+1, y+1, current_time, strategy_history)
                
                # 使用可调节参数的核心逻辑：
                # 1. 如果位置在最近记忆中多次出现（≥min_appearances_for_real_obstacle）
                #    - 如果最近没有策略影响：认为是真实障碍，使用原始评分
                #    - 如果最近有策略影响：暂时降低评分（策略可能正在生效）
                # 2. 如果位置出现次数较少（<min_appearances_for_real_obstacle）
                #    - 如果最近有策略影响：进一步降低评分（策略可能已生效）
                #    - 如果最近无策略影响：可能是偶尔出现的误检，降低评分
                # 3. 如果当前位置没有该障碍：降低评分（可能已被清除）
                
                if recent_appearances >= self.min_appearances_for_real_obstacle:  # 最近多次出现
                    if recent_strategy_effect > 0:  # 最近有策略影响
                        # 策略可能正在生效，暂时降低评分
                        # 直接使用设定的评分降低值
                        reduction = self.score_reduction_during_strategy
                        self.score_matrix[y][x] = max(
                            self.min_score_after_strategy_effect, 
                            self.score_matrix[y][x] - reduction)
                    # 如果最近无策略影响，保持原始评分（认为是真实障碍）
                else:  # 出现次数较少
                    if recent_strategy_effect > 0:  # 有策略影响
                        # 策略可能已生效，降低评分
                        # 直接使用设定的评分降低值
                        reduction = self.score_reduction_during_strategy
                        self.score_matrix[y][x] = max(0, self.score_matrix[y][x] - reduction)
                    # 如果无策略影响且出现次数少，评分已在初始化时设为0
                
        # 对于当前未检测到的障碍，进一步降低评分
        for y in range(7):
            for x in range(9):
                coord = f"{x+1}-{y+1}"
                # 如果该位置当前不是障碍但历史评分大于0，则降低评分
                if self.score_matrix[y][x] > 0 and coord not in current_obstacle_set:
                    self.score_matrix[y][x] = max(0, self.score_matrix[y][x] - self.score_reduction_when_absent)

    def check_recent_strategy_effect(self, x, y, current_time, strategy_history=None):
        """
        检查最近是否有策略作用于指定位置
        :param x: x坐标 (1-9)
        :param y: y坐标 (1-7)
        :param current_time: 当前时间
        :param strategy_history: 策略历史记录（可选，默认使用self.strategy_history）
        :return: 是否有最近策略作用
        """
        
        # 如果提供了策略历史记录，则使用它，否则使用默认的历史记录
        if strategy_history is None:
            strategy_history = self.strategy_history
        
        # 检查最近的策略执行记录
        for record in strategy_history:
            # 使用可调节参数：只考虑策略效果持续时间内的策略执行记录
            time_diff = current_time - record["time"]
            if time_diff <= self.strategy_effect_duration:
                # 检查策略1
                for card, info in record["strategy1"].items():
                    pos = info["pos"]
                    coverage = info["coverage"]
                    # 遍历卡片的覆盖范围
                    for offset_x, offset_y in coverage:
                        target_x, target_y = pos[0] + offset_x, pos[1] + offset_y
                        # 检查该策略是否覆盖了指定位置
                        if target_x == x and target_y == y:
                            return 1.0  # 返回固定权重1.0，确保评分降低值为2
                
                # 检查策略2
                for card, info in record["strategy2"].items():
                    pos = info["pos"]
                    coverage = info["coverage"]
                    # 遍历卡片的覆盖范围
                    for offset_x, offset_y in coverage:
                        target_x, target_y = pos[0] + offset_x, pos[1] + offset_y
                        # 检查该策略是否覆盖了指定位置
                        if target_x == x and target_y == y:
                            return 1.0  # 返回固定权重1.0，确保评分降低值为2
        
        return 0.0  # 没有策略影响则返回0

    def start_visualization(self):
        """
        启动可视化线程，专门用于显示障碍评分情况
        """
        if self.visualization_thread is None or not self.visualization_thread.is_alive():
            self.visualization_running = True
            self.visualization_thread = Thread(target=self.visualization_worker)
            self.visualization_thread.daemon = True
            self.visualization_thread.start()
            CUS_LOGGER.info("[战斗执行器] 障碍评分可视化线程已启动")

    def stop_visualization(self):
        """
        停止可视化线程
        """
        self.visualization_running = False
        if self.visualization_thread and self.visualization_thread.is_alive():
            self.visualization_thread.join(timeout=1.0)
        self.visualization_thread=None
        CUS_LOGGER.info("[战斗执行器] 障碍评分可视化线程已停止")

    def visualization_worker(self):
        """
        可视化工作线程函数
        """
        while self.visualization_running:
            try:
                # 创建一个图像来显示评分矩阵
                self.display_score_matrix()
                time.sleep(1.0)  # 每秒更新一次
            except Exception as e:
                CUS_LOGGER.error(f"[战斗执行器] 可视化线程出错: {e}")
                time.sleep(1.0)  # 出错时也继续运行

    def display_score_matrix(self):
        """
        显示当前的评分矩阵和策略影响前的评分矩阵
        """
        if not self.visualization_running:
            return
        display_height, display_width = 350, 450
        img = np.zeros((display_height, display_width, 3), dtype=np.uint8)

        img[:] = (30, 30, 30)
        cell_height = display_height // 7
        cell_width = display_width // 9
        
        # 计算两个矩阵的最大评分
        max_score_before = np.max(self.previous_score_matrix) if np.max(self.previous_score_matrix) > 0 else 1
        max_score_after = np.max(self.score_matrix) if np.max(self.score_matrix) > 0 else 1
        max_score = max(max_score_before, max_score_after)
        
        for y in range(7):
            for x in range(9):
                # 计算单元格位置
                x1 = x * cell_width
                y1 = y * cell_height
                x2 = x1 + cell_width
                y2 = y1 + cell_height
                score_before = self.previous_score_matrix[y, x]
                score_after = self.now_score_matrix[y, x]
                if score_after > 0:
                    normalized_score = score_after / max_score
                    if normalized_score < 0.5:
                        b = int(255 * (1 - normalized_score * 2))
                        g = int(255 * normalized_score * 2)
                        r = 0
                    else:
                        b = 0
                        g = int(255 * (1 - (normalized_score - 0.5) * 2))
                        r = int(255 * (normalized_score - 0.5) * 2)
                    cv2.rectangle(img, (x1, y1), (x2, y2), (b, g, r), -1)
                elif score_before > 0:
                    cv2.rectangle(img, (x1, y1), (x2, y2), (100, 100, 100), -1)
                else:

                    cv2.rectangle(img, (x1, y1), (x2, y2), (50, 50, 50), -1)
                cv2.rectangle(img, (x1, y1), (x2, y2), (100, 100, 100), 1)
                if score_before > 0 or score_after > 0:
                    # 在同一个位置显示两个评分，用/区分
                    text = f"{score_before:.1f}/{score_after:.1f}"
                    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
                    text_x = x1 + (cell_width - text_size[0]) // 2
                    text_y = y1 + (cell_height + text_size[1]) // 2
                    cv2.putText(img, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # 显示当前生效的策略
        self.overlay_active_strategies(img, cell_width, cell_height)
        cv2.imshow("障碍评分矩阵及清障卡预判覆盖范围", img)
        cv2.waitKey(1)

    def overlay_active_strategies(self, img, cell_width, cell_height, offset_y=0):
        """
        在评分矩阵上叠加显示当前生效的策略
        :param img: 图像对象
        :param cell_width: 单元格宽度
        :param cell_height: 单元格高度
        :param offset_y: Y轴偏移量
        """
        current_time = time.time()
        for record in self.strategy_history:
            time_diff = current_time - record["time"]
            
            # 检查策略是否仍在生效期内
            if time_diff <= self.strategy_effect_duration:
                alpha = 0.3  # 透明度
                for card, info in record["strategy1"].items():
                    coverage = info["coverage"]
                    pos = info["pos"]
                    self.draw_card_coverage(img, coverage, pos, (0, 255, 0), alpha, cell_width, cell_height, offset_y)  # 绿色表示策略1
                for card, info in record["strategy2"].items():
                    coverage = info["coverage"]
                    pos = info["pos"]
                    self.draw_card_coverage(img, coverage, pos, (255, 0, 0), alpha, cell_width, cell_height, offset_y)  # 红色表示策略2

    def draw_card_coverage(self, img, coverage, pos, color, alpha, cell_width, cell_height, offset_y=0):
        """
        绘制卡片的覆盖范围
        :param img: 图像对象
        :param coverage: 卡片覆盖范围 [(offset_x, offset_y), ...]
        :param pos: 卡片放置位置 [x, y]
        :param color: 颜色 (B, G, R)
        :param alpha: 透明度
        :param cell_width: 单元格宽度
        :param cell_height: 单元格高度
        :param offset_y: Y轴偏移量
        """
        card_x, card_y = pos[0], pos[1]
        
        for offset_x, offset_y in coverage:
            target_x = card_x + offset_x
            target_y = card_y + offset_y
            if 1 <= target_x <= 9 and 1 <= target_y <= 7:
                # 计算单元格位置 (注意y轴索引需要转换)
                x1 = (target_x - 1) * cell_width
                y1 = offset_y + (target_y - 1) * cell_height
                x2 = x1 + cell_width
                y2 = y1 + cell_height
                overlay = img.copy()
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
                cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
