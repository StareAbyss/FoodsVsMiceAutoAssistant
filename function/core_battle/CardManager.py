import copy
import datetime
import os
import time
from ctypes import windll
from threading import Timer

import cv2
from PyQt6.QtCore import QThread, pyqtSignal

from function.common.bg_img_screenshot import capture_image_png, capture_image_png_all
from function.core_battle.Card import Card, CardKun, SpecialCard
from function.core_battle.CardQueue import CardQueue
from function.core_battle.special_card_strategy import solve_special_card_problem
from function.globals import EXTRA
from function.globals.get_paths import PATHS
from function.globals.location_card_cell_in_battle import COORDINATE_CARD_CELL_IN_BATTLE
from function.globals.log import CUS_LOGGER
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER


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
    signal_change_card_plan = pyqtSignal()
    signal_used_key = pyqtSignal()
    signal_stop = pyqtSignal()

    def __init__(self, todo, faa_a, faa_b, solve_queue, senior_interval,start_time, check_interval=1):
        """
        :param faa_a: 主号 -> 1
        :param faa_b: 副号 -> 2
        :param solve_queue: 高危目标待解决列表 如果为None 说明高级战斗未激活
        :param senior_interval: 高级战斗间隔时间
        :param check_interval:
        """
        super().__init__()
        # # 完成构造函数的所有初始化工作后，设置 is_initialized 为 True
        # self.is_initialized = False

        """从外部直接引用的类"""
        self.todo = todo
        # a 代表的是 多人战斗中作为队长 或 单人战斗中作为目标的 角色
        self.faa_dict = {1: faa_a, 2: faa_b}
        # 待解决队列，从这里提取信息
        self.solve_queue = solve_queue

        self.card_list_dict = {}
        self.special_card_list = {}
        self.kun_cards_dict = {}
        self.card_queue_dict = {}
        self.thread_dict = {}

        # 特殊放卡列表
        self.ice_boom_dict_list = {1: [], 2: []}
        self.the_9th_fan_dict_list = {1: [], 2: []}
        self.shield_dict_list = {1: [], 2: []}

        # 高级战斗的间隔时间
        self.senior_interval = senior_interval
        #精准战斗开始时间
        self.start_time = start_time

        # 一轮检测的时间 单位s, 该时间的1/20则是尝试使用一张卡的间隔, 该时间的10倍则是使用武器技能/自动拾取动作的间隔 推荐默认值 1s
        self.check_interval = check_interval

        # 直接从faa中获取
        self.is_group = copy.deepcopy(faa_a.is_group)
        self.pid_list = [1, 2] if self.is_group else [1]

        # 刷新全局冰沙锁
        EXTRA.SMOOTHIE_LOCK_TIME = 0

        # 绑定
        self.signal_change_card_plan.connect(self.change_card_plan)

        # 绑定使用钥匙信号
        self.signal_used_key.connect(self.set_is_used_key_true)

        # 绑定结束信号
        self.signal_stop.connect(self.stop)

        self.signals = {
            "change_card_plan": self.signal_change_card_plan,
            "used_key": self.signal_used_key,
            "stop": self.signal_stop
        }

        # 先创建 card_list_dict
        self.init_from_battle_plan()

    def init_from_battle_plan(self):

        # # 完成构造函数的所有初始化工作后，设置 is_initialized 为 True
        # self.is_initialized = False

        # 先创建 card_list_dict
        self.init_card_list_dict()

        # 根据 card_list_dict 创建 card_queue_dict
        self.init_card_queue_dict()

        # 实例化线程
        self.init_all_thread()

        # # 初始化完了
        # self.is_initialized = True

    def init_card_list_dict(self):
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

                elif result["card_type"] < 14:
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
                        c_id=kun_card_info["id"],
                        coordinate_from=kun_card_info["coordinate_from"],
                    )
                    kun_cards.append(kun_card)
            self.kun_cards_dict[pid] = kun_cards
            for card in self.card_list_dict[pid]:
                if card.kun > 0:
                    card.kun_cards = kun_cards

    def init_card_queue_dict(self):
        for pid in self.pid_list:
            self.card_queue_dict[pid] = CardQueue(
                card_list=self.card_list_dict[pid],
                handle=self.faa_dict[pid].handle,
                handle_360=self.faa_dict[pid].handle_360)

    def init_all_thread(self):
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
        T_ACTION_QUEUE_TIMER.print_queue_statue()

        # 实例化 检测线程 + 用卡线程+特殊用卡进程
        for pid in self.pid_list:
            self.thread_dict[pid] = ThreadCheckTimer(
                signals=self.signals,
                card_queue=self.card_queue_dict[pid],
                kun_cards=self.kun_cards_dict.get(pid, None),
                faa=self.faa_dict[pid],
                check_interval=self.check_interval
            )
            self.thread_dict[pid + 2] = ThreadUseCardTimer(
                card_queue=self.card_queue_dict[pid],
                faa=self.faa_dict[pid],
                check_interval=self.check_interval
            )
            self.thread_dict[pid + 4] = ThreadTimePutCardTimer(
                faa=self.faa_dict[pid],
                check_interval=self.check_interval,
                start_time=self.start_time
            )

        if self.solve_queue is not None:
            # 不是空的，说明启动了高级战斗
            self.thread_dict[7] = ThreadUseSpecialCardTimer(
                bomb_card_list=self.special_card_list,
                faa_dict=self.faa_dict,
                check_interval=self.senior_interval,
                read_queue=self.solve_queue,
                is_group=self.is_group,
                ice_boom_dict_list=self.ice_boom_dict_list,
                the_9th_fan_dict_list=self.the_9th_fan_dict_list,
                shield_dict_list=self.shield_dict_list
            )

        CUS_LOGGER.debug("[战斗执行器] 线程已全部实例化")
        CUS_LOGGER.debug(self.thread_dict)

    def start_all_thread(self):
        # 开始线程
        for _, my_thread in self.thread_dict.items():
            my_thread.start()

        CUS_LOGGER.debug("[Todo] [战斗执行器] 检测/放卡 线程已开始.")

    def change_card_plan(self):
        self.stop_sub_thread()
        self.init_from_battle_plan()
        self.start_all_thread()

    def stop_sub_thread(self):

        CUS_LOGGER.info("[Todo] [战斗执行器] CardManager - stop_use_card - 激活, 战斗放卡 全线程 将中止")

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

    def stop(self):

        CUS_LOGGER.info("[战斗执行器] CardManager stop方法已激活, 将销毁")

        self.stop_sub_thread()  # 停止子线程
        self.faa_dict.clear()  # 清空faa字典

        self.exit()
        self.wait()

        CUS_LOGGER.debug("[战斗执行器] CardManager stop方法已完成, 已销毁")

        # 在战斗结束后 打印上一次战斗到这一次战斗之间, 累计的点击队列状态
        CUS_LOGGER.info(f"[战斗执行器] 在本场战斗中, 点击队列变化状态如下, 可判断是否出现点击队列积压的情况")
        T_ACTION_QUEUE_TIMER.print_queue_statue()

        # 退出父线程的事件循环
        self.todo.exit()

        # 清理引用
        self.todo = None
        self.faa_dict = None
        self.solve_queue = None

    def set_is_used_key_true(self):
        """
        在作战时, 只要有任何一方 使用了钥匙, 都设置两个号在本场作战均是用了钥匙
        在战斗结束进行通报汇总分类 各个faa都依赖自身的该参数, 因此需要对两者都做更改
        此外, 双人双线程时, 有两个本线程的实例控制的均为同样的faa实例, 若一方用钥匙,另一方也会悲改为用, 但魔塔不会存在该问题, 故暂时不管.
        """

        CUS_LOGGER.debug("[战斗执行器] 成功接收到使用钥匙信号")

        self.faa_dict[1].faa_battle.is_used_key = True
        if self.is_group:
            self.faa_dict[2].faa_battle.is_used_key = True

    def run(self):

        # while not self.is_initialized:
        #     time.sleep(0.1)

        # 开始线程
        self.start_all_thread()

        # 开启事件循环
        self.exec()


class ThreadCheckTimer(QThread):
    """
    定时线程, 每个角色一个该线程
    该线程将以较低频率, 重新扫描更新目前所有卡片的状态, 以确定使用方式.
    """

    def __init__(self, signals, card_queue, faa, kun_cards, check_interval):
        super().__init__()
        """引用的类"""
        self.card_queue = card_queue
        self.faa = faa
        self.kun_cards = kun_cards

        self.signals = signals
        self.running = False
        self.stopped = False
        self.timer = None
        self.checked_round = 0
        self.check_interval = check_interval  # s

    def run(self):
        self.timer = Timer(self.check_interval, self.callback_timer)
        self.running = True
        self.timer.start()

        self.faa.print_debug('[战斗执行器] ThreadCheckTimer 启动事件循环')
        self.exec()

    def stop(self):
        self.faa.print_info(text="[战斗执行器] ThreadCheckTimer - stop - 已激活, 将关闭战斗中检测线程")

        self.running = False
        if self.timer:
            self.timer.cancel()

        # 清除引用; 释放内存; 如果对应的timer正在运行中 会当场报错强制退出
        self.card_queue = None
        self.faa = None
        self.kun_cards = None

        # 退出事件循环
        self.quit()
        # print("[战斗执行器] ThreadCheckTimer - stop - 事件循环已退出")
        self.wait()
        # print("[战斗执行器] ThreadCheckTimer - stop - 线程已等待完成")

    def callback_timer(self):
        """
        一轮检测, 包括结束检测 / 继续战斗检测 / 自动战斗的状态检测 / 定时武器使用和拾取 / 按波次变阵检测
        回调不断重复
        """

        try:
            self.check()
        except Exception as e:
            CUS_LOGGER.warning(
                f"[战斗执行器] ThreadUseCardTimer - callback_timer - 在运行中遭遇错误"
                f"可能是Timer线程调用的参数已被释放后, 有Timer进入执行状态. 这是正常情况. 错误信息: {e}"
            )

        # 回调
        if self.running:
            self.timer = Timer(self.check_interval, self.callback_timer)
            self.timer.start()

    def check(self):
        self.checked_round += 1

        # 看看是不是结束了 注意仅主号完成该操作 操作的目标是manager实例对象
        if self.faa.is_main:
            self.running = not self.faa.faa_battle.check_end()
            if not self.running:
                if not self.stopped:  # 正常结束，非主动杀死线程结束
                    self.faa.print_info(text='[战斗执行器] 房主 检测到战斗结束标志, 即将关闭战斗中放卡的线程')
                    self.signals["stop"].emit()
                    self.stopped = True  # 防止stop后再次调用
                return

        # 尝试使用钥匙 如成功 发送信号 修改faa.battle中的is_used_key为True 以标识用过了, 如果不需要使用或用过了, 会直接Fals
        # 不需要判定主号 直接使用即可
        if self.faa.faa_battle.use_key():
            self.signals["used_key"].emit()

        # 自动战斗部分的处理
        self.check_for_auto_battle()

        # 定时 使用武器技能 自动拾取 考虑到火苗消失时间是7s 快一点5s更好
        if self.checked_round % 5 == 0:
            self.faa.faa_battle.use_weapon_skill()
            self.faa.faa_battle.auto_pickup()

    def check_for_kun(self, game_image=None):
        """
        战斗中坤卡部分的检测
        """

        # 要求火苗1000+
        if not self.faa.faa_battle.fire_elemental_1000:
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

    def check_for_auto_battle(self):
        """
        战斗部分的检测
        """
        if not self.faa.is_auto_battle:
            return

        # 仅截图一次, 降低重复次数
        game_image = capture_image_png(
            handle=self.faa.handle,
            root_handle=self.faa.handle_360,
            raw_range=[0, 0, 950, 600],
        )

        # 尝试检测变阵 注意仅主号完成该操作 操作的目标是manager实例对象
        result = self.faa.faa_battle.check_wave(img=game_image)
        if result:
            if self.faa.is_main:
                self.signals["change_card_plan"].emit()

        # 先清空现有队列 再初始化队列
        self.card_queue.queue.clear()
        self.card_queue.init_card_queue(game_image=game_image)

        # 更新火苗
        self.faa.faa_battle.update_fire_elemental_1000(img=game_image)

        # 根据情况判断是否加入执行坤函数的动作
        if self.kun_cards:
            self.check_for_kun(game_image=game_image)

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

        # 刷新全局冰沙锁的状态
        if EXTRA.SMOOTHIE_LOCK_TIME > 0:
            EXTRA.SMOOTHIE_LOCK_TIME -= self.check_interval


class ThreadUseCardTimer(QThread):
    def __init__(self, card_queue, faa, check_interval):
        super().__init__()
        """引用的类"""
        self.card_queue = card_queue
        self.faa = faa

        self.running = False
        self.timer = None
        self.interval_use_card = float(check_interval / 50)

    def run(self):
        self.timer = Timer(self.interval_use_card, self.callback_timer)
        self.running = True
        self.timer.start()

        self.faa.print_debug('[战斗执行器] ThreadUseCardTimer 启动事件循环')
        self.exec()

        self.running = False

    def stop(self):
        self.faa.print_info("[战斗执行器] ThreadUseCardTimer - stop - 已激活 中止事件循环")

        self.running = False
        if self.timer:
            self.timer.cancel()

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
            CUS_LOGGER.warning(
                f"[战斗执行器] ThreadUseCardTimer - callback_timer - 在运行中遭遇错误"
                f"可能是Timer线程调用的参数已被释放后, 有Timer进入执行状态. 这是正常情况. 错误信息: {e}"
            )

        # 回调
        if self.running:
            self.timer = Timer(self.interval_use_card, self.callback_timer)
            self.timer.start()

class ThreadTimePutCardTimer(QThread):
    def __init__(self, faa, check_interval,start_time):
        super().__init__()
        """引用的类"""
        self.faa = faa
        self.wave=0#初始化肯定是波次为0的
        try :
            self.timer_plan=self.faa.battle_plan["card"]["timer_plan"]
        except Exception as e:
            self.timer_plan=None
            #如果没有这个键就直接返回了
        self.bp_card = copy.deepcopy(self.faa.bp_card)
        self.bp_cell = copy.deepcopy(self.faa.bp_cell)
        self.start_time = start_time

        self.running = False
        self.timer = None
        self.interval_use_card = float(check_interval / 50)

    def run(self):
        if self.timer_plan is not None:#没有定时放卡plan，那就整个线程一开始就结束好了

            self.timer = Timer(self.interval_use_card, self.callback_timer)
            # 记录结束时间
            end_time = time.time()
            battle_start_time = end_time - self.start_time

            self.set_timer_for_wave(0,time_change=battle_start_time)#初始化时设置第零波所有计时器
            self.running = True
            self.timer.start()

            self.faa.print_debug('[战斗执行器] ThreadTimePutCardTimer 启动')
            self.exec()

            self.running = False

    def stop(self):
        self.faa.print_info("[战斗执行器] ThreadTimePutCardTimer - stop - 已激活 中止事件循环")

        self.running = False
        if self.timer:
            self.timer.cancel()

        # 清除引用; 释放内存; 如果对应的timer正在运行中 会当场报错强制退出
        self.faa = None

        # 退出事件循环
        self.quit()
        # print("[战斗执行器] ThreadUseCardTimer - stop - 事件循环已退出")
        self.wait()
        # print("[战斗执行器] ThreadUseCardTimer - stop - 线程已等待完成")

    def callback_timer(self):

        try:
            wave=self.faa.faa_battle.wave#获取当前波次
            if self.wave!=wave:
                self.wave=wave
                self.set_timer_for_wave(wave)#识别到了新波次则设置该波次的定时放卡
        except Exception as e:
            CUS_LOGGER.warning(
                f"[战斗执行器] ThreadTimePutCardTimer - callback_timer - 在运行中遭遇错误"
                f"可能是Timer线程调用的参数已被释放后, 有Timer进入执行状态. 这是正常情况. 错误信息: {e}"
            )

        # 回调
        if self.running:
            self.timer = Timer(self.interval_use_card, self.callback_timer)
            self.timer.start()
    def set_timer_for_wave(self,wave,time_change=0):

        if str(wave) in self.timer_plan["wave"].keys():  # 波次定时放卡检测
            for wave_plan in self.timer_plan["wave"][str(wave)]:
                c_time=wave_plan["time"]
                # 如果是第零波，减去 time_change 时间，并确保时间不小于0，进行时间准确矫正
                if wave == 0:
                    CUS_LOGGER.debug(f"faa战斗执行器启动用了整整{time_change}秒！")
                    c_time = max(0, c_time - time_change)

                def create_timer_callback( func, *args):
                    return lambda: func(*args)

                if wave_plan["front_shovel"]:
                    front_shovel_timer = Timer(
                        max(0, c_time - 0.5),
                        create_timer_callback( self.use_shovel_with_lock, wave_plan["location"])
                    )
                    front_shovel_timer.start()

                card_timer = Timer(
                    c_time,
                    create_timer_callback( self.use_card_with_lock, wave_plan["cid"],
                                          wave_plan["location"])
                )
                card_timer.start()

                if wave_plan["back_shovel"]:
                    back_shovel_timer = Timer(
                        c_time + wave_plan["back_shovel_time"],
                        create_timer_callback(
                                              self.use_shovel_with_lock, wave_plan["location"])
                    )
                    back_shovel_timer.start()

        # 波次定时宝石使用检测
        if "gem" in self.timer_plan.keys():
            if str(wave) in self.timer_plan["gem"]["wave"].keys():
                for wave_plan_gem in self.timer_plan["gem"]["wave"][str(wave)]:
                    g_time=wave_plan_gem["time"]
                    if wave==0:
                        g_time=max(0,g_time-time_change)
                    def create_timer_callback(func, *args):
                        return lambda: func(*args)
                    gemstone_timer = Timer(
                        g_time,
                        create_timer_callback(self.use_gemstone, wave_plan_gem["gid"])
                    )
                    gemstone_timer.start()
    def use_shovel_with_lock(self,location):
        """
        :param x: 像素坐标
        :param y: 像素坐标
        :return:
        """
        x = self.bp_cell[location][0]
        y = self.bp_cell[location][1]
        with self.faa.battle_lock:
            # 选择铲子
            T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=self.faa.handle, key="1")
            time.sleep(1/240)
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.faa.handle, x=x, y=y)
            time.sleep(1/240)
        CUS_LOGGER.debug(f"成功完成铲")
    def use_gemstone(self,gid):
        """使用宝石"""
        # 注意上锁, 防止和放卡冲突
        with self.faa.battle_lock:
            match gid:
                case 1:
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.faa.handle, x=23, y=200)
                case 2:
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.faa.handle, x=23, y=250)
                case 3:
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.faa.handle, x=23, y=297)
                case _:
                    CUS_LOGGER.warning(f"[战斗执行器] ThreadTimePutCardTimer - use_gemstone - 错误: id={id} 不存在")
    def use_card_with_lock(self,card_id,location):
        """
        :param card_id: 卡片id
        :param x: 像素坐标
        :param y: 像素坐标
        """
        battle_log=False
        with self.faa.battle_lock:
            #选卡操作
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=self.faa.handle,
                x=self.bp_card[card_id][0] + 25,
                y=self.bp_card[card_id][1] + 35)
            time.sleep(1/240)
            #放卡操作
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=self.faa.handle,
                x=self.bp_cell[location][0],
                y=self.bp_cell[location][1])
        if battle_log:
            time.sleep(0.75)
            self.try_get_picture_now()
            CUS_LOGGER.debug(f"成功定时放卡{card_id}于{location}")
    def try_get_picture_now(self):
        windll.user32.SetProcessDPIAware()
        output_base_path = PATHS["logs"] + "\\yolo_output"
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d%H%M%S")
        output_img_path = f"{output_base_path}/images/{timestamp}.png"
        original_image = capture_image_png_all(self.faa.handle)[:, :, :3]
        cv2.imwrite(output_img_path, original_image)




class ThreadUseSpecialCardTimer(QThread):
    def __init__(self, faa_dict, check_interval, read_queue, is_group,
                 bomb_card_list, ice_boom_dict_list, the_9th_fan_dict_list, shield_dict_list):
        """
        :param faa_dict:faa实例字典
        :param check_interval:读取频率
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
        self.interval_use_special_card = check_interval
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
        self.timer = Timer(self.interval_use_special_card, self.callback_timer)
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
        self.pid_list = [pid for pid in self.pid_list if self.faa_dict[pid].faa_battle.fire_elemental_1000]
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

                if not_got_state_images_cards:
                    # 如果有卡片未完成状态监测, 则将未完成状态监测的卡片加入到待处理列表中
                    self.card_list_can_use[pid] = not_got_state_images_cards
                else:
                    # 如果均完成了状态监测, 则将所有状态为可用的卡片加入待处理列表中
                    self.card_list_can_use[pid] = []
                    for card in self.special_card_list[pid]:
                        card.fresh_status()
                        if card.status_usable:
                            self.card_list_can_use[pid].append(card)

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
            self.timer = Timer(self.interval_use_special_card / 200, self.use_card, args=(1,))  # 1p0.01秒后开始放卡
            self.timer.start()  # 按todolist用卡
            self.timer = Timer(self.interval_use_special_card / 200, self.use_card, args=(2,))  # 2p0.01秒后开始放卡
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
            self.timer = Timer(self.interval_use_special_card, self.callback_timer)
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
