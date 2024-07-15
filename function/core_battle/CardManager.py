from threading import Timer

from PyQt5.QtCore import QThread, pyqtSignal

from function.core_battle.Card import Card, CardKun
from function.core_battle.CardQueue import CardQueue
from function.globals.extra import EXTRA_GLOBALS
from function.globals.log import CUS_LOGGER


class CardManager:

    def __init__(self, faa_1, faa_2):
        super().__init__()
        self.card_list_dict = {}
        self.card_kun_dict = {}
        self.card_queue_dict = {}
        self.thread_dict = {}
        self.smoothie_usable_player = []

        # 此处的 faa_1 和 faa_2 实例代表的是 多人战斗中作为队长 或 单人战斗中作为目标的 角色
        self.faa_dict = {1: faa_1, 2: faa_2}

        self.stop_mode = 0  # 停止模式，如果是直接调用的stop方法，会先设置这个标识，避免重复杀死线程
        self.is_running = False

        # 直接从faa中获取
        self.is_group = faa_1.is_group

        # 先创建 card_list_dict
        self.init_card_list_dict()

        # 根据 card_list_dict 创建 card_queue_dict
        self.init_card_queue_dict()

        # 实例化线程
        self.init_all_thread()

        # 刷新全局冰沙锁
        EXTRA_GLOBALS.smoothie_lock_time = 0

        # 对象分析 打包务必注释掉！
        # objgraph.show_most_common_types()
        # objgraph.show_growth()

    def init_card_list_dict(self):
        for i in ([1, 2] if self.is_group else [1]):
            cards_plan = self.faa_dict[i].battle_plan_1["card"]
            self.card_list_dict[i] = []
            for j in range(len(cards_plan)):
                # 按从前到后顺序，作为优先级顺序，从0开始
                self.card_list_dict[i].append(Card(faa=self.faa_dict[i], priority=j))

        # 将包含了极寒冰沙卡片的号筛选出来
        for player in ([1, 2] if self.is_group else [1]):
            for card in self.card_list_dict[player]:
                if card.is_smoothie:
                    self.smoothie_usable_player.append(player)

        # 添加坤
        for player in ([1, 2] if self.is_group else [1]):
            if self.faa_dict[player].kun_position:
                self.card_kun_dict[player] = CardKun(faa=self.faa_dict[player])

    def init_card_queue_dict(self):
        for i in ([1, 2] if self.is_group else [1]):
            self.card_queue_dict[i] = CardQueue(card_list=self.card_list_dict[i])

    def init_all_thread(self):
        if self.is_group:
            players = [1, 2]
        else:
            players = [1]
        # 实例化 检测线程 + 用卡线程
        for i in players:
            self.thread_dict[i] = ThreadCheckTimer(
                card_queue=self.card_queue_dict[i],
                card_kun=self.card_kun_dict[i] if (i in self.card_kun_dict.keys()) else None,
                faa=self.faa_dict[i])
            self.thread_dict[i + 2] = ThreadUseCardTimer(
                card_queue=self.card_queue_dict[i],
                faa=self.faa_dict[i])

        CUS_LOGGER.debug("线程已全部实例化")
        CUS_LOGGER.debug(self.thread_dict)

    def start_all_thread(self):
        # 开始线程
        for k, my_thread in self.thread_dict.items():
            my_thread.start()
        CUS_LOGGER.debug("所有线程已开始")

    def run(self):
        # 开始线程
        self.start_all_thread()

    def stop(self):
        CUS_LOGGER.debug("CardManager stop方法已激活")
        self.stop_mode = 1

        # 中止已经存在的子线程
        for k, my_thread in self.thread_dict.items():
            if my_thread is not None:
                my_thread.stop()
        self.thread_dict.clear()  # 清空线程字典

        # 释放卡片列表中的卡片的内存
        for key, card_list in self.card_list_dict.items():
            for card in card_list:
                card.destroy()  # 释放卡片内存
            card_list.clear()  # 清空卡片列表
        self.card_list_dict.clear()  # 清空卡片列表字典

        # 释放坤坤卡的内存
        for key, card in self.card_kun_dict.items():
            card.destroy()  # 释放卡片内存

        # 释放卡片队列内存
        for key, card_queue in self.card_queue_dict.items():
            card_queue.queue.clear()  # 清空卡片队列

        self.card_queue_dict.clear()  # 清空卡片队列字典
        self.faa_dict.clear()  # 清空faa字典
        self.is_group = None
        CUS_LOGGER.debug("CardManager 内部线程已停止")


class ThreadCheckTimer(QThread):
    stop_signal = pyqtSignal()
    used_key_signal = pyqtSignal()

    def __init__(self, card_queue, faa, card_kun):
        super().__init__()
        self.card_queue = card_queue
        self.card_kun = card_kun
        self.faa = faa
        self.stop_flag = False
        self.stopped = False
        self.timer = None
        self.running_round = 0
        self.interval = 1  # s

    def run(self):
        self.timer = Timer(self.interval, self.check)
        self.timer.start()
        self.faa.print_debug('启动下层事件循环')
        while not self.stop_flag:
            QThread.msleep(100)
        self.timer.cancel()  # 停止定时器
        self.timer = None

    def stop(self):
        self.faa.print_info(text="ThreadCheckTimer stop方法已激活")
        # 设置Flag
        self.stop_flag = True
        # 退出事件循环
        self.quit()
        self.wait()
        self.deleteLater()
        # 清除引用; 释放内存
        self.faa = None
        self.card_queue = None

    def check(self):
        """先检查是否出现战斗完成或需要使用钥匙，如果完成，至二级"""
        self.running_round += 1

        # 看看是不是结束了
        self.stop_flag = self.faa.faa_battle.check_end()
        if self.stop_flag:
            if not self.stopped:
                self.faa.print_info(text='检测到战斗结束')
                self.stop_signal.emit()
                self.stopped = True  # 防止stop后再次调用
            return

        # 看看是不是需要使用钥匙 如果使用成功 发送信号 修改faa.battle中的相关参数为True 以标识
        if self.faa.faa_battle.use_key():
            self.used_key_signal.emit()

        if self.faa.is_auto_battle:
            # 先清空现有队列
            self.card_queue.queue.clear()
            # 再初始化队列
            self.card_queue.init_card_queue()
            # 更新火苗
            self.faa.faa_battle.update_fire_elemental_1000()

            # 根据情况判断是否加入执行坤函数的动作
            if self.card_kun:
                # 先刷新坤卡状态
                self.card_kun.fresh_status()
                if self.faa.faa_battle.fire_elemental_1000 and self.card_kun.status_usable:
                    # 要求该窗口被找到坤位置, 并且火苗1000+, 且坤可用
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

            # 调试打印目前list状态
            # if self.faa.player == 1:
            #     text = ""
            #     for card in self.card_queue.card_list:
            #         text += "[name:{}|cd:{}|usable:{}|ban:{}|kun_tar:{}]".format(
            #             card.name, card.status_cd, card.status_usable, card.status_ban, card.is_kun_target)
            #     self.faa.print_debug(text)

        # 刷新全局冰沙锁的状态
        if EXTRA_GLOBALS.smoothie_lock_time != 0:
            EXTRA_GLOBALS.smoothie_lock_time -= self.interval

        # 定时使用武器技能和检测是否继续
        if self.running_round % 10 == 0:
            self.faa.faa_battle.use_weapon_skill()
            self.faa.faa_battle.auto_pickup()

        # 回调
        if not self.stop_flag:
            self.timer = Timer(self.interval, self.check)
            self.timer.start()


class ThreadUseCardTimer(QThread):
    def __init__(self, card_queue, faa):
        super().__init__()
        self.card_queue = card_queue
        self.faa = faa
        self.stop_flag = True
        self.timer = None

    def run(self):
        self.stop_flag = False
        self.timer = Timer(0.02, self.use_card)
        self.timer.start()
        self.faa.print_debug('启动下层事件循环2')
        while not self.stop_flag:
            QThread.msleep(100)
        self.timer.cancel()
        self.timer = None

    def use_card(self):
        self.card_queue.use_top_card()
        if not self.stop_flag:
            self.timer = Timer(0.02, self.use_card)
            self.timer.start()

    def stop(self):
        self.faa.print_debug("ThreadUseCardTimer stop方法已激活")
        # 设置Flag
        self.stop_flag = True
        # 退出线程的事件循环
        self.quit()
        self.wait()
        self.deleteLater()
        # 清除引用; 释放内存
        self.faa = None
        self.card_queue = None
