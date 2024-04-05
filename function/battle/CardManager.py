import sys
from threading import Timer

import objgraph
from PyQt5.QtCore import QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QApplication

from function.battle.Card import Card
from function.battle.CardQueue import CardQueue
from function.battle.get_position_in_battle import get_position_card_deck_in_battle
from function.script.FAA import FAA


class CardManager:

    def __init__(self, faa_1, faa_2):
        super().__init__()
        self.card_list_dict = {}
        self.card_queue_dict = {}
        self.thread_dict = {}
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

        # 对象分析
        objgraph.show_most_common_types()
        objgraph.show_growth()

    def init_card_list_dict(self):
        for i in ([1, 2] if self.is_group else [1]):
            cards_plan = self.faa_dict[i].battle_plan_1["card"]
            self.card_list_dict[i] = []
            for j in range(len(cards_plan)):
                # 按从前到后顺序，作为优先级顺序，从0开始
                self.card_list_dict[i].append(Card(faa=self.faa_dict[i], priority=j))

    def init_card_queue_dict(self):
        for i in ([1, 2] if self.is_group else [1]):
            self.card_queue_dict[i] = CardQueue(card_list=self.card_list_dict[i])

        if __name__ == '__main__':
            print(self.card_queue_dict)

    def init_all_thread(self):
        if self.is_group:
            players = [1, 2]
        else:
            players = [1]
        # 实例化 检测线程 + 用卡线程
        for i in players:
            self.thread_dict[i] = ThreadCheckTimer(
                card_queue=self.card_queue_dict[i],
                faa=self.faa_dict[i])
            self.thread_dict[i + 2] = ThreadUseCardTimer(
                card_queue=self.card_queue_dict[i],
                faa=self.faa_dict[i])

        print("线程已全部实例化")
        print(self.thread_dict)

    def start_all_thread(self):
        # 开始线程
        for k, my_thread in self.thread_dict.items():
            my_thread.start()
        print("所有线程已开始")

    def use_kun(self, kun, card):
        # 如果幻幻鸡卡片在冷却，就return
        if kun.status_cd > 0:
            return
        # 使用幻幻鸡，队列卡片就下一位，遍历卡片就下一位遍历
        kun_position = card.position[1, ""]
        # 将幻幻鸡添加到点击队列中

    def run(self):
        # 开始线程
        self.start_all_thread()

    def stop(self):
        print("CardManager stop方法已激活")
        self.stop_mode = 1
        # 中止已经存在的子线程
        for k, my_thread in self.thread_dict.items():
            if my_thread is not None:
                my_thread.stop()
        self.thread_dict.clear()  # 清空线程字典
        for key, cardlist in self.card_list_dict.items():
            for card in cardlist:
                card.destroy()  # 释放卡片内存
            cardlist.clear()  # 清空卡片列表
        self.card_list_dict.clear()  # 清空卡片列表字典
        # 释放卡片队列内存
        for key, cardqueue in self.card_queue_dict.items():
            cardqueue.queue.clear()  # 清空卡片队列
        self.card_queue_dict.clear()  # 清空卡片队列字典
        self.faa_dict.clear()  # 清空faa字典
        self.is_group = None
        print("CardManager 内部线程已停止")


class ThreadCheckTimer(QThread):
    stop_signal = pyqtSignal()

    def __init__(self, card_queue, faa):
        super().__init__()
        self.card_queue = card_queue
        self.faa = faa
        self.running_round = 0
        self.stop_flag = True
        self.timer = None

    def run(self):
        self.stop_flag = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.check)
        self.timer.start(1000)  # 设置定时器每1000毫秒触发一次
        print('启动下层事件循环')
        self.exec_()
        self.timer.stop()  # 停止定时器
        self.timer = None

    def stop(self):
        print("{}P ThreadCheckTimer stop方法已激活".format(self.faa.player))
        self.stop_flag = True
        self.faa = None
        self.card_queue = None
        self.quit()  # 退出事件循环
        self.wait()
        self.deleteLater()

    def check(self):
        """先检查是否出现战斗完成或需要使用钥匙，如果完成，至二级"""
        self.running_round += 1

        if self.faa.faa_battle.use_key_and_check_end():
            self.stop_flag = True
            print('检测到战斗结束')
            self.stop_signal.emit()
            return

        if self.faa.is_auto_battle:
            # 先清空现有队列
            self.card_queue.queue.clear()
            # 再初始化队列
            self.card_queue.init_card_queue()
            # 更新火苗
            self.faa.faa_battle.update_fire_elemental_1000()
            # 调试打印目前list状态
            if self.faa.player == 1:
                text = ""
                for card in self.card_queue.card_list:
                    text += "[name:{}|cd:{}|usable:{}|ban:{}]".format(
                        card.name, card.status_cd, card.status_usable, card.status_ban)
                print(text)

        if self.running_round % 10 == 0:
            self.faa.faa_battle.use_weapon_skill()
            self.faa.faa_battle.auto_pickup()


class ThreadUseCardTimer(QThread):
    def __init__(self, card_queue, faa):
        super().__init__()
        self.card_queue = card_queue
        self.faa = faa
        self.object_use_card_timer = None
        self.stop_flag = True
        self.timer = None

    def run(self):
        self.stop_flag = False
        self.timer = Timer(0.02, self.use_card)
        self.timer.start()
        print('启动下层事件循环2')
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
        print("{}P ThreadUseCardTimer stop方法已激活".format(self.faa.player))
        self.stop_flag = True
        self.faa = None
        self.card_queue = None
        # 退出线程的事件循环
        self.quit()
        self.wait()
        self.deleteLater()


if __name__ == '__main__':
    class Todo(QMainWindow):
        """模拟todo类"""

        def __init__(self):
            super().__init__()
            self.t1 = None
            self.card_manager = None

        def run(self):
            faa_1 = FAA(channel="锑食")
            faa_2 = FAA(channel="深渊之下 | 锑食")

            faa_1.set_config_for_battle(
                stage_id="NO-1-14",
                is_group=True,
                battle_plan_index=0)
            faa_2.set_config_for_battle(
                stage_id="NO-1-14",
                is_group=True,
                battle_plan_index=0)

            # 1.识图承载卡参数
            faa_1.init_mat_card_position()
            faa_2.init_mat_card_position()

            # 2.识图卡片数量，确定卡片在deck中的位置
            faa_1.bp_card = get_position_card_deck_in_battle(handle=faa_1.handle)
            faa_2.bp_card = get_position_card_deck_in_battle(handle=faa_2.handle)

            # 3.计算所有坐标
            faa_1.init_battle_plan_1()
            faa_2.init_battle_plan_1()

            # 4.刷新faa放卡实例
            faa_1.init_battle_object()
            faa_2.init_battle_object()

            print("准备工作完成")
            self.card_manager = CardManager(faa_1=faa_1, faa_2=faa_2)
            self.card_manager.run()


    class MainWindow(QMainWindow):
        """模拟窗口主线程"""

        def __init__(self):
            super().__init__()
            self.initUI()
            self.t1 = Todo()
            self.t1.run()

        def initUI(self):
            self.setWindowTitle('计时器示例')
            self.setGeometry(300, 300, 250, 150)

        def do_something(self):
            todo = Todo()
            todo.start()


    """模拟启动"""
    app = QApplication(sys.argv)

    main_win = MainWindow()
    main_win.show()

    sys.exit(app.exec())
