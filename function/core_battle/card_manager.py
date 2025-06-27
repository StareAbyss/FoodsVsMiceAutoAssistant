import copy
import datetime
import math
import os
import random
import time
from ctypes import windll
from threading import Timer
from typing import Union, TYPE_CHECKING

import cv2
from PyQt6.QtCore import QThread, pyqtSignal

from function.common.bg_img_screenshot import capture_image_png, capture_image_png_all
from function.core_battle.card import Card, CardKun, SpecialCard
from function.core_battle.card_queue import CardQueue
from function.core_battle.special_card_strategy import solve_special_card_problem
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

        CUS_LOGGER.info("[战斗执行器] CardManager - stop 开始")

        self.stop_sub_threads()  # 停止子线程
        self.faa_dict.clear()  # 清空faa字典

        for timer in self.insert_action_sub_timers:
            # 取消还在运行中的定时任务
            timer.cancel()
        self.insert_action_sub_timers = None

        # 中止自身, 并让调用线程等待该操作完成
        self.exit()
        self.wait()

        CUS_LOGGER.debug("[战斗执行器] CardManager - stop 结束")

        # 在战斗结束后 打印上一次战斗到这一次战斗之间, 累计的点击队列状态
        CUS_LOGGER.info(f"[战斗执行器] 在本场战斗中, 点击队列变化状态如下, 可判断是否出现点击队列积压的情况")
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

                    result = is_special_card(cards_plan[set_priority]["name"])

                    if not result["found"]:
                        # 普通卡
                        card = Card(faa=faa, set_priority=set_priority)
                        self.card_list_dict[pid].append(card)
                        continue

                        # 高级战斗目标
                    if result["card_type"] == 11:
                        # 冰桶类
                        s_card = SpecialCard(
                            faa=faa,
                            set_priority=set_priority,
                            energy=result["energy"],
                            card_type=result["card_type"])
                        self.ice_boom_dict_list[pid].append(s_card)

                    elif result["card_type"] == 14:
                        # 草扇
                        s_card = SpecialCard(
                            faa=faa,
                            set_priority=set_priority,
                            energy=result["energy"],
                            card_type=result["card_type"])
                        self.the_9th_fan_dict_list[pid].append(s_card)

                    elif result["card_type"] <= 15:
                        # 各种炸弹类卡片 包括瓜皮类炸弹
                        s_card = SpecialCard(
                            faa=faa,
                            set_priority=set_priority,
                            energy=result["energy"],
                            card_type=result["card_type"],
                            rows=result["rows"],
                            cols=result["cols"])
                        self.special_card_list[pid].append(s_card)

                        if result["card_type"] == 12:
                            # 护罩类，除了炸弹还可能是常驻的罩子
                            card_shield = Card(faa=faa, set_priority=set_priority)
                            s_card = SpecialCard(
                                faa=faa,
                                set_priority=set_priority,
                                energy=result["energy"],
                                card_type=result["card_type"],
                                rows=result["rows"],
                                cols=result["cols"],
                                n_card=card_shield)  # 建立特殊卡护罩与常规卡护罩之间的连接
                            # 以特殊卡加入特殊放卡
                            self.shield_dict_list[pid].append(s_card)
                            # 以普通卡版本加入放卡
                            self.card_list_dict[pid].append(card_shield)

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
                    shield_dict_list=self.shield_dict_list
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

        timer = Timer(interval=interval, function=lambda: func(**func_kwargs))
        timer.start()
        self.insert_action_sub_timers.append(timer)


class ThreadCheckTimer(QThread):
    """
    定时线程, 每个角色一个该线程
    该线程将以较低频率, 重新扫描更新目前所有卡片的状态, 以确定使用方式.
    """

    def __init__(self, card_queue, faa, kun_cards, check_interval,
                 signal_change_card_plan, signal_used_key, signal_stop,thread_dict):

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
        self.thread_dict = thread_dict  #线程列表，以便动态修改参数
        self.interval=None
        self.check_interval_count=None
        if hasattr(self.faa, 'battle_plan_tweak') and isinstance(self.faa.battle_plan_tweak, dict):
            CUS_LOGGER.debug(f"[战斗执行器] ThreadCheckTimer - check - 微调方案{self.faa.battle_plan_tweak}")
            meta_data = self.faa.battle_plan_tweak.get('meta_data', {})
            self.interval = meta_data.get('interval')
            if self.interval:
                #深度battle调参未果（…^-^)
                #放卡间隔与重置单轮放卡间隔原初比例大约为0.036：1
                self.check_interval_count = (self.interval[0]+self.interval[1])*5//1
    def run(self):
        self.timer = Timer(interval=self.check_interval, function=self.callback_timer)
        self.running = True
        self.timer.start()

        self.faa.print_info('[战斗执行器] ThreadCheckTimer 启动事件循环')
        self.exec()

    def stop(self):
        self.faa.print_info(text="[战斗执行器] ThreadCheckTimer - stop - 已激活, 将关闭战斗中检测线程")

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
            CUS_LOGGER.warning(
                f"[战斗执行器] ThreadCheckTimer - callback_timer - 在运行中遭遇错误"
                f"可能是Timer线程所需参数已被释放. 后有Timer进入执行状态. 这是正常情况. 错误信息: {e}"
            )
            self.running = False

        # 回调
        if self.running:
            self.timer = Timer(interval=self.check_interval, function=self.callback_timer)
            self.timer.start()

    def _update_thread_intervals(self, interval):
        """更新所有线程中的间隔参数"""
        for thread_id, thread in self.thread_dict.items():
            random_interval = random.uniform(float(interval[0]), float(interval[1]))
            try:
                # 检查线程是否存活
                if thread and hasattr(thread, 'isRunning') and thread.isRunning():
                    # 检查线程类名以便修改对应属性
                    if thread.__class__.__name__ == 'ThreadUseCardTimer':
                        # 直接更新属性
                        thread.interval_use_card= random_interval
                        # CUS_LOGGER.debug(f"更新线程 {thread_id} 的间隔参数为: {random_interval:.3f}")

                else:
                    # CUS_LOGGER.debug(f"线程 {thread_id} 不可用，跳过更新")
                    pass

            except Exception as e:
                CUS_LOGGER.error(f"更新线程 {thread_id} 参数失败: {str(e)}")
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
        if self.interval:
            try:
                # 生成指定范围的随机浮点数
                random_interval = random.uniform(float(self.interval[0]), float(self.interval[1]))
                # 修改 click_sleep 属性
                self.faa.click_sleep = random_interval
                self._update_thread_intervals(self.interval)
                CUS_LOGGER.debug(f"成功设置 click_sleep 为随机值: {random_interval:.3f}")
            except (ValueError, TypeError) as e:
                CUS_LOGGER.error(f"生成随机间隔失败: {str(e)}")

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

        # 先清空现有队列 再初始化队列
        #这里的重置队列要适应放卡间隔
        if self.check_interval_count is None or (self.checked_round %self.check_interval_count==1):
            self.card_queue.queue.clear()
            self.card_queue.init_card_queue(
                game_image=game_image,
                check_interval=self.check_interval)
            CUS_LOGGER.debug(f"成功重置队列，本轮次{self.checked_round}")


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
                text = f"[战斗执行器] [{self.faa.player}P] "
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
        # 默认的快速使用卡的间隔
        self.fast_use_card_interval = 0.018

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
        fast_fail=False
        try:
            fast_fail=self.card_queue.use_top_card()
        except Exception as e:
            CUS_LOGGER.warning(
                f"[战斗执行器] ThreadUseCardTimer - callback_timer - 在运行中遭遇错误"
                f"可能是Timer线程调用的参数已被释放后, 有Timer进入执行状态. 这是正常情况. 错误信息: {e}"
            )

        # 回调
        if self.running:
            if fast_fail:
                self.timer = Timer(interval=self.fast_use_card_interval, function=self.callback_timer)
            else:
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

        # 内联 card_name 字段
        for event in self.insert_use_card_plan:
            event["action"]["name"] = next((card["name"] for card in self.faa.battle_plan["cards"]), "")

        self.running = False
        self.timer = None

    def run(self):

        # 没有定时放卡plan，那就整个线程一开始就结束好了
        if (not self.insert_use_card_plan) and (not self.insert_use_gem_plan):
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
            CUS_LOGGER.warning(
                f"[战斗执行器] ThreadInsertUseCardTimer - callback_timer - 在运行中遭遇错误"
                f"可能是Timer线程调用的参数已被释放后, 有Timer进入执行状态. 这是正常情况. 错误信息: {e}"
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
            event for event in self.insert_use_gem_plan if event["trigger"]["wave_id"] == int(wave)]

        for battle_event in current_wave_plan:
            self.manager.create_insert_timer_and_start(
                interval=max(0.0, battle_event["trigger"]["time"] - time_change),
                func_name="insert_use_gem",
                func_kwargs={
                    "pid": self.pid,
                    "gid": battle_event["action"]["gem_id"]}
            )


class ThreadUseSpecialCardTimer(QThread):
    def __init__(self, faa_dict, callback_interval, read_queue, is_group: bool,
                 bomb_card_list, ice_boom_dict_list, the_9th_fan_dict_list, shield_dict_list):
        """
        :param faa_dict:faa实例字典
        :param callback_interval:读取频率
        :param read_queue:高危目标队列
        :param is_group:是否组队
        :param bomb_card_list: 该类卡片为炸弹 在战斗方案中写入其from位置 在此处计算得出to位置 并进行其使用
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
        self.pid_list = [1, 2] if self.is_group else [1]

        # 记录每种类型的卡片 有哪些 格式
        # { 1: [obj_s_card_1, obj_s_card_2, ...], 2:[...] }
        self.special_card_list = bomb_card_list
        self.ice_boom_dict_list = ice_boom_dict_list
        self.the_9th_fan_dict_list = the_9th_fan_dict_list
        self.shield_dict_list = shield_dict_list

        self.shield_used_dict_list = {1: [], 2: []}

    def run(self):
        self.timer = Timer(interval=self.callback_interval, function=self.callback_timer)
        self.running = True
        self.timer.start()

        self.faa_dict[1].print_debug('[战斗执行器] 启动特殊放卡线程')
        self.exec()

        self.running = False

    def stop(self):
        self.faa_dict[1].print_info("[战斗执行器] ThreadUseSpecialCardTimer stop方法已激活")

        self.running = False
        if self.timer:
            self.timer.cancel()
        self.timer = None

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
        CUS_LOGGER.debug(f"待二次加工信息为{result} ")
        if result is None:
            return

        self.pid_list = [1, 2] if self.is_group else [1]

        # 没有1000火的角色 从pid list中移除
        self.pid_list = [pid for pid in self.pid_list if self.faa_dict[pid].fire_elemental_1000]
        if not self.pid_list:
            return

        wave, god_wind, need_boom_locations = result  # 分别为是否波次，是否神风及待炸点位列表

        if wave or god_wind or need_boom_locations:  # 任意一个就刷新状态
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
                for card in (set(self.special_card_list[pid])-set(self.card_list_can_use[pid])):
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

        if wave or god_wind or need_boom_locations:  # 任意一个就刷新状态
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
            CUS_LOGGER.warning(
                f"[战斗执行器] ThreadUseSpecialCardTimer - callback_timer - 在运行中遭遇错误"
                f"可能是Timer线程调用的参数已被释放后, 有Timer进入执行状态. 这是正常情况. 错误信息: {e}"
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
