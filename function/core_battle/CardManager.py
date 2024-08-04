from threading import Timer
import time

from PyQt5.QtCore import QThread, pyqtSignal

from function.core_battle.Card import Card, CardKun,Special_card,is_special_card
from function.core_battle.CardQueue import CardQueue
from function.globals.extra import EXTRA_GLOBALS
from function.globals.log import CUS_LOGGER
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.core_battle.special_card_strategy import solve_special_card_problem


class CardManager:

    def __init__(self, faa_1, faa_2, solve_queue,round_interval=1):
        super().__init__()
        # 完成构造函数的所有初始化工作后，设置 is_initialized 为 True
        self.is_initialized=False
        self.card_list_dict = {}
        self.special_card_list = {}
        self.card_kun_dict = {}
        self.card_queue_dict = {}
        self.thread_dict = {}
        self.iceboom_list={1:[],2:[]}
        self.the_9th_grassfan = {1:[],2:[]}
        self.smoothie_usable_player = []

        # 一轮检测的时间 单位s, 该时间的1/20则是尝试使用一张卡的间隔, 该时间的10倍则是使用武器技能/自动拾取动作的间隔 推荐默认值 1s
        self.round_interval = round_interval

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
        #待解决队列，从这里提取信息
        self.solve_queue = solve_queue

        self.is_initialized = True#初始化完了

        # 对象分析 打包务必注释掉！
        # objgraph.show_most_common_types()
        # objgraph.show_growth()

    def init_card_list_dict(self):
        for i in ([1, 2] if self.is_group else [1]):
            cards_plan = self.faa_dict[i].battle_plan_1["card"]
            self.card_list_dict[i] = []
            self.special_card_list[i]=[]
            for j in range(len(cards_plan)):
                # 按从前到后顺序，作为优先级顺序，从0开始
                result=is_special_card(cards_plan[j]["name"])
                if result["found"]:
                    if result["card_type"]<14 and result["card_type"]!=11:#不是冰桶草扇冰沙或其他垃圾卡
                        self.special_card_list[i].append(Special_card(faa=self.faa_dict[i], priority=j,energy=result["energy"],card_type=result["card_type"],rows=result["rows"],cols=result["cols"]))
                        if result["card_type"]==12 :#护罩类，除了炸弹还可能是常驻的罩子
                            self.card_list_dict[i].append(Card(faa=self.faa_dict[i], priority=j))
                    elif result["card_type"]==11:#冰桶类
                        self.iceboom_list[i].append(Special_card(faa=self.faa_dict[i], priority=j,energy=result["energy"],card_type=result["card_type"]))
                    elif result["card_type"]==14:#草扇
                        self.the_9th_grassfan[i].append(Special_card(faa=self.faa_dict[i], priority=j,energy=result["energy"],card_type=result["card_type"]))

                else:
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
                for card in self.card_list_dict[player]:
                    if card.kun>0:
                        card.card_kun=self.card_kun_dict[player]

    def init_card_queue_dict(self):
        for i in ([1, 2] if self.is_group else [1]):
            self.card_queue_dict[i] = CardQueue(card_list=self.card_list_dict[i])

    def init_all_thread(self):
        if self.is_group:
            players = [1, 2]
        else:
            players = [1]
        # 在每个号开打前 打印上一次战斗到这一次战斗之间, 累计的点击队列状态
        CUS_LOGGER.info(f"[战斗执行器] 在两场战斗之间, 点击队列变化状态如下, 可判断是否出现点击队列积压的情况")
        T_ACTION_QUEUE_TIMER.print_queue_statue()
        # 实例化 检测线程 + 用卡线程+特殊用卡进程
        for i in players:
            self.thread_dict[i] = ThreadCheckTimer(
                card_queue=self.card_queue_dict[i],
                card_kun=self.card_kun_dict[i] if (i in self.card_kun_dict.keys()) else None,
                faa=self.faa_dict[i],
                round_interval=self.round_interval
            )
            self.thread_dict[i + 2] = ThreadUseCardTimer(
                card_queue=self.card_queue_dict[i],
                faa=self.faa_dict[i],
                round_interval=self.round_interval
            )
        self.thread_dict[4] = ThreadUseSpecialCardTimer(
            card_queue=self.special_card_list,
            faa=self.faa_dict,
            round_interval=self.round_interval,
            read_queue=self.solve_queue,
            is_group=self.is_group,
            iceboom_list=self.iceboom_list,
            the_9th_grassfan=self.the_9th_grassfan
        )

        CUS_LOGGER.debug("[战斗执行器] 线程已全部实例化")
        CUS_LOGGER.debug(self.thread_dict)

    def start_all_thread(self):
        # 开始线程
        for k, my_thread in self.thread_dict.items():
            my_thread.start()
        CUS_LOGGER.debug("[战斗执行器] 所有线程已开始")

    def run(self):
        # 开始线程
        while not self.is_initialized:
            time.sleep(0.1)
        self.start_all_thread()

    def stop(self):
        CUS_LOGGER.debug("[战斗执行器] CardManager stop方法已激活, 战斗放卡 全线程 将中止")
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
        #释放特殊卡内存
        for key, card_list in self.special_card_list.items():
            for card in card_list:
                card.destroy()  # 释放卡片内存
            card_list.clear()  # 清空卡片列表
        self.special_card_list.clear()  # 清空卡片列表字典

        # 释放坤坤卡的内存
        for key, card in self.card_kun_dict.items():
            card.destroy()  # 释放卡片内存

        # 释放卡片队列内存
        for key, card_queue in self.card_queue_dict.items():
            card_queue.queue.clear()  # 清空卡片队列

        self.card_queue_dict.clear()  # 清空卡片队列字典
        self.faa_dict.clear()  # 清空faa字典
        self.is_group = None
        CUS_LOGGER.debug("[战斗执行器] CardManager stop方法已完成, 战斗放卡 全线程 已停止")

        # 在战斗结束后 打印上一次战斗到这一次战斗之间, 累计的点击队列状态
        CUS_LOGGER.info(f"[战斗执行器] 在本场战斗中, 点击队列变化状态如下, 可判断是否出现点击队列积压的情况")
        T_ACTION_QUEUE_TIMER.print_queue_statue()


class ThreadCheckTimer(QThread):
    stop_signal = pyqtSignal()
    used_key_signal = pyqtSignal()

    def __init__(self, card_queue, faa, card_kun, round_interval):
        super().__init__()
        self.card_queue = card_queue
        self.card_kun = card_kun
        self.faa = faa
        self.stop_flag = False
        self.stopped = False
        self.timer = None
        self.running_round = 0
        self.round_interval = round_interval  # s

    def run(self):
        self.timer = Timer(self.round_interval, self.check)
        self.timer.start()
        self.faa.print_debug('[战斗执行器] 启动下层事件循环')
        while not self.stop_flag:
            QThread.msleep(100)
        self.timer.cancel()  # 停止定时器
        self.timer = None

    def stop(self):
        self.faa.print_info(text="[战斗执行器] ThreadCheckTimer stop方法已激活, 将关闭战斗中检测线程")
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

        # 实时 打印 <点击队列> 目前的状态
        # if self.faa.player == 1:
        #     T_ACTION_QUEUE_TIMER.print_queue_statue()

        # 看看是不是结束了
        self.stop_flag = self.faa.faa_battle.check_end()
        if self.stop_flag:
            if not self.stopped:#正常结束，非主动杀死线程结束
                self.faa.print_info(text='[战斗执行器] 检测到战斗结束标志, 即将关闭战斗中放卡的线程')
                self.stop_signal.emit()
                self.stopped = True  # 防止stop后再次调用
            return

        # 尝试使用钥匙 如成功 发送信号 修改faa.battle中的is_used_key为True 以标识用过了, 如果不需要使用或用过了, 会直接False
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


            # 调试打印 - 目前 <战斗管理器> 的状态
            if EXTRA_GLOBALS.battle_extra_log:
                if self.faa.player == 1:
                    text = "[战斗执行器] "
                    for card in self.card_queue.card_list:
                        text += "[{}|CD:{}|用:{}|禁:{}|坤:{}] ".format(
                            card.name[:2] if len(card.name) >= 2 else card.name,
                            'T' if card.status_cd else 'F',
                            'T' if card.status_usable else 'F',
                            card.status_ban if card.status_ban else 'F',
                            'T' if card.is_kun_target else 'F')
                    self.faa.print_debug(text)

        # 刷新全局冰沙锁的状态
        if EXTRA_GLOBALS.smoothie_lock_time != 0:
            EXTRA_GLOBALS.smoothie_lock_time -= self.round_interval

        # 定时 使用武器技能 自动拾取 考虑到火苗消失时间是7s
        if self.running_round % 7 == 0:
            self.faa.faa_battle.use_weapon_skill()
            self.faa.faa_battle.auto_pickup()

        # 回调
        if not self.stop_flag:
            self.timer = Timer(self.round_interval, self.check)
            self.timer.start()


class ThreadUseCardTimer(QThread):
    def __init__(self, card_queue, faa, round_interval):
        super().__init__()
        self.card_queue = card_queue
        self.faa = faa
        self.stop_flag = True
        self.timer = None
        self.round_interval = float(round_interval / 50)

    def run(self):
        self.stop_flag = False
        self.timer = Timer(self.round_interval, self.use_card)
        self.timer.start()
        self.faa.print_debug('[战斗执行器] 启动下层事件循环2')
        while not self.stop_flag:
            QThread.msleep(100)
        self.timer.cancel()
        self.timer = None

    def use_card(self):
        self.card_queue.use_top_card()
        if not self.stop_flag:
            self.timer = Timer(self.round_interval, self.use_card)
            self.timer.start()

    def stop(self):
        self.faa.print_debug("[战斗执行器] ThreadUseCardTimer stop方法已激活")
        # 设置Flag
        self.stop_flag = True
        # 退出线程的事件循环
        self.quit()
        self.wait()
        self.deleteLater()
        # 清除引用; 释放内存
        self.faa = None
        self.card_queue = None


class ThreadUseSpecialCardTimer(QThread):
    def __init__(self, card_queue, faa, round_interval,read_queue,is_group,iceboom_list,the_9th_grassfan):
        super().__init__()
        self.card_queue = card_queue
        self.faa = faa
        self.stop_flag = True
        self.timer = None
        self.round_interval = round_interval*2#因为读图是两秒一次，所以此处设置两秒尝试获取一次信息
        self.read_queue = read_queue
        self.is_group = is_group
        self.flag=[True,True,True]
        self.card_list_can_use=[[],[]]
        self.Todo_list={}
        self.iceboom_list = iceboom_list
        self.the_9th_grassfan = the_9th_grassfan

    def run(self):
        self.stop_flag = False
        self.timer = Timer(self.round_interval, self.analyze_special_card)
        self.timer.start()
        self.faa[0].print_debug('[战斗执行器] 启动特殊放卡线程')
        while not self.stop_flag:
            QThread.msleep(100)
        self.timer.cancel()
        self.timer = None


    def analyze_special_card(self):
        self.flag[1]=True
        self.flag[2]=True
        if self.is_group:
            self.flag[2]=False
        result = self.read_queue.get()#不管能不能用对策卡先提取信息再说，免得队列堆积
        if not self.faa[0].faa_battle.fire_elemental_1000:#没有1000火放毛线炸弹
            self.flag[1] = False
        if self.is_group:
            if not self.faa[1].faa_battle.fire_elemental_1000:
                self.flag[2] = False

        if self.flag[1] or self.flag[2]:#可以放特殊对策卡了
            if result is not None:
                wave, godwind, positions = result  # 分别为是否波次，是否神风及待炸点位列表
                if wave or godwind or positions:#任意一个就刷新状态
                    self.Todo_list={}
                    if wave:
                        for i in range(1,3):
                            waveflag=False
                            if self.flag[i]:
                                for card in self.iceboom_list[i]:#遍历冰桶卡
                                    card.fresh_status()
                                    if card.status_usable:
                                        waveflag=True
                                        self.Todo_list[i].append([card,None])
                                        break
                                if waveflag:
                                    break
                    if godwind:
                        for i in range(1, 3):
                            godwindflag = False
                            if self.flag[i]:
                                for card in self.the_9th_grassfan[i]:  # 遍历草扇卡
                                    card.fresh_status()
                                    if card.status_usable:
                                        godwindflag = True
                                        self.Todo_list[i].append([card,None])
                                        break
                                if godwindflag:
                                    break

                    if positions:
                        self.card_list_can_use = [[], []]
                        if self.flag[1]:
                            for special_card in self.card_queue[1]:
                                special_card.fresh_status()#刷新冷却状态，可用就加入对策列表
                                if special_card.status_usable:
                                    self.card_list_can_use[0].append(special_card)
                        if self.flag[2]:
                            for special_card in self.card_queue[2]:
                                special_card.fresh_status()#刷新冷却状态，可用就加入对策列表
                                if special_card.status_usable:
                                    self.card_list_can_use[1].append(special_card)
                        result=solve_special_card_problem(positions, self.faa[0].battle_plan_1["obstacle"],self.card_list_can_use)
                        if result is not None:
                            strategy1, strategy2=result
                            for card,pos in strategy1:
                                self.Todo_list[1].append([card, pos])
                            for card,pos in strategy2:
                                self.Todo_list[2].append([card, pos])

                    self.timer = Timer(self.round_interval / 200, self.use_card,args=(1,))#1p0.01秒后开始放卡
                    self.timer.start()#按todolist用卡
                    self.timer = Timer(self.round_interval / 200, self.use_card, args=(2,))  # 2p0.01秒后开始放卡
                    self.timer.start()  # 按todolist用卡



        if not self.stop_flag:
            self.timer = Timer(self.round_interval, self.analyze_special_card)
            self.timer.start()

    def use_card(self,player):
        for card in self.Todo_list[player]:
            card[0].use_card(card[1])
            if self.stop_flag:
                break
            else:
                QThread.msleep(self.round_interval / 200)




    def stop(self):
        self.faa[0].print_debug("[战斗执行器] ThreadUseSpecialCardTimer stop方法已激活")
        # 设置Flag
        self.stop_flag = True
        # 退出线程的事件循环
        self.quit()
        self.wait()
        self.deleteLater()
        # 清除引用; 释放内存
        self.faa = None
        self.card_queue = None
        self.read_queue = None