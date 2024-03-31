import datetime
import json
import random
import sys
import time
from time import sleep

import requests
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import *
from PyQt5.QtWidgets import QApplication

from function.battle.CardManager import CardManager
from function.common.bg_p_match import loop_match_p_in_w
from function.common.thread_with_exception import ThreadWithException
from function.globals.get_paths import PATHS
from function.globals.init_resources import RESOURCE_P
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.gat_handle import faa_get_handle
from function.scattered.get_channel_name import get_channel_name
from function.scattered.get_customize_todo_list import get_customize_todo_list
from function.script.FAA import FAA
from function.script.ui_1_load_opt import MyMainWindow1


class Todo(QThread):

    def __init__(self, faa, opt, signal_dict):
        super().__init__()
        # 用于暂停恢复
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.is_paused = False
        # 功能需要
        self.faa = faa
        self.opt = opt
        self.thread_1p = None
        self.thread_2p = None
        self.thread_manager = None
        self.battle_mode = 0  # 1 或 0 0则代表使用老版战斗方案; 1则达标使用新版战斗方案, 新版处于测试之中. 开发者请更改为0再用
        self.card_manager = None
        # 好用的信号~
        self.signal_dict = signal_dict
        self.signal_printf = self.signal_dict["printf"]
        self.signal_dialog = self.signal_dict["dialog"]
        self.signal_end = self.signal_dict["end"]

    """业务代码, 不直接调用opt设定, 会向输出窗口传参"""

    def reload_game(self):

        self.signal_printf.emit(
            "[{}] Refresh Game...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        print("刷新两个游戏窗口 开始")

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].reload_game,
            name="1P Thread - Reload",
            kwargs={})

        self.thread_2p = ThreadWithException(
            target=self.faa[2].reload_game,
            name="2P Thread - Reload",
            kwargs={})

        self.thread_1p.start()
        time.sleep(1)
        self.thread_2p.start()
        self.thread_1p.join()
        self.thread_2p.join()

        print("刷新两个游戏窗口 结束")

    def reload_to_login_ui(self):

        self.signal_printf.emit(
            "[{}] Refresh Game...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].reload_to_login_ui,
            name="1P Thread - Reload",
            kwargs={})

        self.thread_2p = ThreadWithException(
            target=self.faa[2].reload_to_login_ui,
            name="2P Thread - Reload",
            kwargs={})
        self.thread_1p.start()
        self.thread_2p.start()
        self.thread_1p.join()
        self.thread_2p.join()

    def all_sign_in(self, is_group):

        self.signal_printf.emit(
            "[{}] [每日签到] 开始...".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            color="red")

        # 领取温馨礼包
        for i in [1, 2]:
            if self.opt["get_warm_gift"][f'{i}p']["active"]:
                openid = self.opt["get_warm_gift"][f'{i}p']["link"]
                if openid == "":
                    continue
                url = 'http://meishi.wechat.123u.com/meishi/gift?openid=' + openid
                r = requests.get(url)
                message = r.json()['msg']
                self.signal_printf.emit(f'[{i}P] 领取温馨礼包情况:' + message, color="green")
            else:
                self.signal_printf.emit(f"[{i}P] 未激活领取温馨礼包", color="red")

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].sign_in,
            name="1P Thread - SignIn",
            kwargs={})

        if is_group:
            self.thread_2p = ThreadWithException(
                target=self.faa[2].sign_in,
                name="2P Thread - SignIn",
                kwargs={})

        self.thread_1p.start()
        if is_group:
            self.thread_2p.start()

        self.thread_1p.join()
        if is_group:
            self.thread_2p.join()

        self.signal_printf.emit(
            "[{}] [每日签到] 结束".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            , color="red")

    def receive_quest_rewards(self, is_group):

        self.signal_printf.emit(
            "[{}] [领取奖励] 开始...".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            color="red")

        """普通任务"""
        self.signal_printf.emit(
            "[{}] [领取奖励] [普通任务] 开始...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].action_quest_receive_rewards,
            name="1P Thread - ReceiveQuest",
            kwargs={
                "mode": "普通任务"
            })

        if is_group:
            self.thread_2p = ThreadWithException(
                target=self.faa[2].action_quest_receive_rewards,
                name="2P Thread - ReceiveQuest",
                kwargs={
                    "mode": "普通任务"
                })

        # 涉及键盘抢夺, 容错低, 最好分开执行
        self.thread_1p.start()
        if is_group:
            sleep(0.333)
            self.thread_2p.start()

        self.thread_1p.join()
        if is_group:
            self.thread_2p.join()

        self.signal_printf.emit(
            "[{}] [领取奖励] [普通任务] 结束".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        """美食大赛"""

        self.signal_printf.emit(
            "[{}] [领取奖励] [美食大赛] 开始...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].action_quest_receive_rewards,
            name="1P Thread - Quest",
            kwargs={
                "mode": "美食大赛"
            })

        self.thread_2p = ThreadWithException(
            target=self.faa[2].action_quest_receive_rewards,
            name="2P Thread - Quest",
            kwargs={
                "mode": "美食大赛"
            })

        # 涉及键盘抢夺, 容错低, 最好分开执行
        self.thread_1p.start()
        sleep(0.333)
        self.thread_2p.start()
        self.thread_1p.join()
        self.thread_2p.join()

        self.signal_printf.emit(
            "[{}] [领取奖励] [美食大赛] 结束...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        """大富翁"""
        self.signal_printf.emit(
            "[{}] [领取奖励] [大富翁] 开始...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].action_quest_receive_rewards,
            name="1P Thread - Quest",
            kwargs={
                "mode": "大富翁"
            })

        self.thread_2p = ThreadWithException(
            target=self.faa[2].action_quest_receive_rewards,
            name="2P Thread - Quest",
            kwargs={
                "mode": "大富翁"
            })

        # 涉及键盘抢夺, 容错低, 最好分开执行
        self.thread_1p.start()
        sleep(0.333)
        self.thread_2p.start()
        self.thread_1p.join()
        self.thread_2p.join()

        self.signal_printf.emit(
            "[{}] [领取奖励] [大富翁] 结束...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        self.signal_printf.emit(
            text="[{}] 领取所有[任务]奖励, 完成".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            color="red")

    def use_items(self, is_group):

        self.signal_printf.emit(
            "[{}] 使用绑定消耗品和宝箱, 开始".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        self.signal_printf.emit(
            "[{}] 领取一般任务奖励...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].use_item,
            name="1P Thread - UseItems",
            kwargs={})

        if is_group:
            self.thread_2p = ThreadWithException(
                target=self.faa[2].use_item,
                name="2P Thread - UseItems",
                kwargs={})

        # 涉及键盘抢夺, 容错低, 最好分开执行
        self.thread_1p.start()
        if is_group:
            sleep(0.333)
            self.thread_2p.start()
        self.thread_1p.join()
        if is_group:
            self.thread_2p.join()

        self.signal_printf.emit(
            text="[{}] 使用绑定消耗品和宝箱, 完成".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    def loop_cross_server(self, is_group, deck):

        self.signal_printf.emit(
            text="[{}] 无限刷跨服任务威望启动!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            color="red"
        )

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].loop_cross_server,
            name="1P Thread",
            kwargs={"deck": deck})

        if is_group:
            self.thread_2p = ThreadWithException(
                target=self.faa[2].loop_cross_server,
                name="2P Thread",
                kwargs={"deck": deck})

        self.thread_1p.start()
        if is_group:
            self.thread_2p.start()

        self.thread_1p.join()
        if is_group:
            self.thread_2p.join()

    def invite(self, player_a, player_b):
        """
        号1邀请号2到房间 需要在同一个区
        :return: bool 是否最终找到了图片
        """

        faa_a = self.faa[player_a]
        faa_b = self.faa[player_b]

        find = loop_match_p_in_w(
            raw_w_handle=faa_a.handle,
            raw_range=[796, 413, 950, 485],
            target_path=RESOURCE_P["common"]["战斗"]["战斗前_开始按钮.png"],
            target_sleep=0.3,
            click=False,
            target_failed_check=2.0)
        if not find:
            print("2s找不到开始游戏! 土豆服务器问题, 创建房间可能失败!")
            return False

        if not faa_a.stage_info["id"].split("-")[0] == "GD":

            # 点击[房间ui-邀请按钮]
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa_a.handle, x=410, y=546)
            time.sleep(0.5)

            # 点击[房间ui-邀请ui-好友按钮]
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa_a.handle, x=535, y=130)
            time.sleep(0.5)

            # 直接邀请
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa_a.handle, x=601, y=157)
            time.sleep(0.5)

            # p2接受邀请
            find = loop_match_p_in_w(
                raw_w_handle=faa_b.handle,
                raw_range=[0, 0, 950, 600],
                target_path=RESOURCE_P["common"]["战斗"]["战斗前_接受邀请.png"],
                target_sleep=2.0,
                target_failed_check=2.0
            )

            if not find:
                print("2s没能组队? 土豆服务器问题, 尝试解决ing...")
                return False

            # p1关闭邀请窗口
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa_a.handle, x=590, y=491)
            time.sleep(1)

        return True

    def battle(self, player_a, player_b):
        """
        从进入房间到回到房间的流程
        :param player_a: 玩家A
        :param player_b: 玩家B
        :return:
            result_id 结束id 用于判定战斗是否成功 或 失败原因
            result_loot 战利品dict 包含多号的战利品和宝箱识别情况
        """

        is_group = self.faa[player_a].is_group
        result_id = 0
        result_loot = {
            player_a: {},
            player_b: {}
        }
        result_spend_time = 0

        """同时进行战前准备"""
        if result_id == 0:

            # 初始化多线程
            self.thread_1p = ThreadWithException(
                target=self.faa[player_a].action_round_of_battle_before,
                name="{}P Thread - Battle - Before".format(player_a),
                kwargs={})
            if is_group:
                self.thread_2p = ThreadWithException(
                    target=self.faa[player_b].action_round_of_battle_before,
                    name="{}P Thread - Battle - Before".format(player_b),
                    kwargs={})

            # 开始多线程
            if is_group:
                self.thread_2p.start()
                time.sleep(3)
            self.thread_1p.start()

            # 阻塞进程让进程执行完再继续本循环函数
            self.thread_1p.join()
            if is_group:
                self.thread_2p.join()

            # 获取返回值
            result_id = max(result_id, self.thread_1p.get_return_value())
            if is_group:
                result_id = max(result_id, self.thread_2p.get_return_value())

        """多线程进行战斗 此处1p-ap 2p-bp 战斗部分没有返回值"""

        if result_id == 0:

            battle_start_time = time.time()

            # 初始化多线程
            self.thread_1p = ThreadWithException(
                target=self.faa[player_a].action_round_of_battle_self,
                name="{}P Thread - Battle".format(player_a),
                kwargs={})
            if is_group:
                self.thread_2p = ThreadWithException(
                    target=self.faa[player_b].action_round_of_battle_self,
                    name="{}P Thread - Battle".format(player_b),
                    kwargs={})

            # 开始多线程
            self.thread_1p.start()
            if is_group:
                self.thread_2p.start()

            # 阻塞进程让进程执行完再继续本循环函数
            self.thread_1p.join()
            if is_group:
                self.thread_2p.join()

            if self.faa[player_a].battle_mode == 1:
                self.thread_manager = CardManager(self.faa[1], self.faa[2])
                # 创建一个事件循环
                loop = QEventLoop()
                # 连接CardManager的stopped信号到事件循环的quit槽
                self.thread_manager.stopped.connect(loop.quit)
                # 启动CardManager
                self.thread_manager.start()
                # 执行事件循环,阻塞等待stopped信号
                loop.exec()
                # 收到信号后，循环终止，使用stop方法
                self.thread_manager.stop()
                self.thread_manager = None
                print("新战斗方法已完成执行并不再阻塞Todo线程")

            result_spend_time = time.time() - battle_start_time

        print("战斗循环 已完成")

        """多线程进行战利品和宝箱检查 此处1p-ap 2p-bp"""

        if result_id == 0:

            # 初始化多线程
            self.thread_1p = ThreadWithException(
                target=self.faa[player_a].action_round_of_battle_screen,
                name="{}P Thread - Battle - Screen".format(player_a),
                kwargs={})
            if is_group:
                self.thread_2p = ThreadWithException(
                    target=self.faa[player_b].action_round_of_battle_screen,
                    name="{}P Thread - Battle - Screen".format(player_b),
                    kwargs={})

            # 开始多线程
            self.thread_1p.start()
            if is_group:
                self.thread_2p.start()

            # 阻塞进程让进程执行完再继续本循环函数
            self.thread_1p.join()
            if is_group:
                self.thread_2p.join()

            result = self.thread_1p.get_return_value()
            result_id = max(result_id, result[0])
            result_loot[player_a] = result[1]
            if is_group:
                result = self.thread_2p.get_return_value()
                result_id = max(result_id, result[0])
                result_loot[player_b] = result[1]

        print("多线程进行战利品和宝箱检查 已完成")

        """分开进行战后检查"""
        if result_id == 0:
            result_id = self.faa[player_a].action_round_of_battle_after()
            if is_group:
                result_id = self.faa[player_b].action_round_of_battle_after()

        print("战后检查完成 battle 函数执行结束")
        return result_id, result_loot, result_spend_time

    def goto_stage_and_invite(self, stage_id, mt_first_time, player_a, player_b):

        # 自定义作战直接调出
        is_cu = "CU" in stage_id
        if is_cu:
            return 0

        is_cs = "CS" in stage_id
        is_mt = "MT" in stage_id

        faa_a = self.faa[player_a]
        faa_b = self.faa[player_b]

        failed_round = 0  # 计数失败轮次

        while True:

            failed_time = 0  # 计数失败次数

            while True:
                if not is_mt:
                    # 非魔塔进入
                    faa_a.action_goto_stage()
                    faa_b.action_goto_stage()
                else:
                    # 魔塔进入
                    faa_a.action_goto_stage(mt_first_time=mt_first_time)
                    if mt_first_time:
                        faa_b.action_goto_stage(mt_first_time=mt_first_time)

                sleep(3)

                if is_cs:
                    # 跨服副本 直接退出
                    return 0
                invite_success = self.invite(player_a=player_a, player_b=player_b)

                if invite_success:
                    text = "[{}] [单本轮战] 邀请成功".format(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        failed_time)
                    print(text)
                    self.signal_printf.emit(text)
                    # 邀请成功 返回退出
                    return 0

                else:
                    failed_time += 1
                    mt_first_time = True

                    text = "[{}] [单本轮战] 服务器抽风,进入竞技岛重新邀请...({}/3)".format(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        failed_time)
                    print(text)
                    self.signal_printf.emit(text)

                    if failed_time == 3:
                        text = "[{}] [单本轮战] 服务器抽风过头, 刷新游戏!".format(
                            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            failed_time)
                        print(text)
                        self.signal_printf.emit(text)
                        failed_round += 1
                        self.reload_game()
                        break

                    faa_a.action_exit(mode="竞技岛")
                    faa_b.action_exit(mode="竞技岛")

            if failed_round == 3:
                text = "[{}] [单本轮战] 刷新游戏次数过多".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    failed_time)
                print(text)
                self.signal_printf.emit(text)
                return 2

    def n_battle_customize_battle_error_print(self, success_battle_time):
        # 结束提示文本
        text = "[{}] [单本轮战] 第{}次, 出现未知异常! 刷新后卡死, 以防止更多问题, 出现此问题可上报作者".format(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            success_battle_time)
        print(text)
        self.signal_printf.emit(text)
        self.reload_game()
        sleep(60 * 60 * 24)

    def n_battle(self, stage_id, player, is_use_key, max_times, dict_exit,
                 deck, quest_card, ban_card_list, battle_plan_1p, battle_plan_2p):
        """
        [单本轮战]1次 副本外 → 副本内n次战斗 → 副本外
        player: [1],[2],[1,2],[2,1]
        """

        # 判断是不是打魔塔 或 自建房
        is_mt = "MT" in stage_id
        is_cu = "CU" in stage_id
        is_cs = "CS" in stage_id

        # 判断是不是组队
        if len(player) == 1:
            is_group = False
        else:
            is_group = True

        # 如果是多人跨服 防呆重写 2,1 为 1,2
        if is_cs and is_group:
            player = [1, 2]

        # 处理多人信息 (这些信息只影响函数内, 所以不判断是否组队)
        player_a = player[0]  # 房主 创建房间者
        player_b = 1 if player_a == 2 else 2  # 非房主
        faa_a = self.faa[player_a]
        faa_b = self.faa[player_b]
        battle_plan_a = battle_plan_1p if player_a == 1 else battle_plan_2p
        battle_plan_b = battle_plan_1p if player_b == 1 else battle_plan_2p

        # 填入战斗方案和关卡信息, 之后会大量动作和更改类属性, 所以需要判断是否组队
        faa_a.set_config_for_battle(
            battle_mode=self.battle_mode,
            is_main=True,
            is_group=is_group,
            is_use_key=is_use_key,
            deck=deck,
            quest_card=quest_card,
            ban_card_list=ban_card_list,
            battle_plan_index=battle_plan_a,
            stage_id=stage_id)
        if is_group:
            faa_b.set_config_for_battle(
                battle_mode=self.battle_mode,
                is_main=False,
                is_group=is_group,
                is_use_key=is_use_key,
                deck=deck,
                quest_card=quest_card,
                ban_card_list=ban_card_list,
                battle_plan_index=battle_plan_b,
                stage_id=stage_id)

        self.signal_printf.emit(
            "[{}] [单本轮战] {} {}次 开始".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                stage_id,
                max_times))

        # 检查人物等级 先检查 player_a 组队额外检查 player_b

        if not faa_a.check_level():
            self.signal_printf.emit(
                "[{}] [单本轮战] {}P等级不足, 跳过".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    player_a
                ))
            return False

        if is_group:
            if not faa_b.check_level():
                self.signal_printf.emit(
                    "[{}] [单本轮战] {}P等级不足, 跳过".format(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        player_b
                    ))
                return False

        # 标记是否需要进入副本
        need_goto_stage = not is_cu

        success_battle_time = 0  # 记录成功战斗次数
        result_list = []  # 记录成功场次
        # 轮次作战
        while success_battle_time < max_times:

            # 前往副本
            result_id = 0
            if not is_mt:
                # 非魔塔
                if need_goto_stage:
                    if not is_group:
                        # 单人前往副本
                        faa_a.action_goto_stage()
                    else:
                        # 多人前往副本
                        result_id = self.goto_stage_and_invite(
                            stage_id=stage_id,
                            mt_first_time=False,
                            player_a=player_a,
                            player_b=player_b)

                    need_goto_stage = False  # 进入后Flag变化
            else:
                # 魔塔
                if not is_group:
                    # 单人前往副本
                    faa_a.action_goto_stage(mt_first_time=need_goto_stage)
                else:
                    # 多人前往副本
                    result_id = self.goto_stage_and_invite(
                        stage_id=stage_id,
                        mt_first_time=need_goto_stage,
                        player_a=player_a,
                        player_b=player_b)

                need_goto_stage = False  # 进入后Flag变化

            if result_id == 2:
                # 跳过本次 计数+1
                success_battle_time += 1
                # 进入异常, 跳过
                need_goto_stage = True
                # 结束提示文本
                text = "[{}] [单本轮战] 第{}次, 创建房间多次异常, 重启跳过".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    success_battle_time)
                print(text)
                self.signal_printf.emit(text)

                self.reload_game()

            print("=" * 150)
            text = "[{}] [单本轮战] 第{}次, 开始".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                success_battle_time + 1)
            print(text)
            self.signal_printf.emit(text)

            # 开始战斗循环
            result_id, result_loot, result_spend_time = self.battle(player_a=player_a, player_b=player_b)

            if result_id == 0:
                # 战斗成功 计数+1
                success_battle_time += 1

                # 退出函数
                if success_battle_time < max_times:
                    # 常规退出方式
                    for j in dict_exit["other_time_player_a"]:
                        faa_a.action_exit(mode=j)
                    if is_group:
                        for j in dict_exit["other_time_player_b"]:
                            faa_b.action_exit(mode=j)
                else:
                    # 最后一次退出方式
                    for j in dict_exit["last_time_player_a"]:
                        faa_a.action_exit(mode=j)
                    if is_group:
                        for j in dict_exit["last_time_player_b"]:
                            faa_b.action_exit(mode=j)

                # 加入结果统计列表
                result_list.append({
                    "time_spend": result_spend_time,
                    "loot_dict_list": result_loot  # result_loot_dict_list = [{a掉落}, {b掉落}]
                })

                # 时间
                text = "[{}] [单本轮战] 第{}次, 正常结束, 耗时:{}分{}秒".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    success_battle_time,
                    *divmod(int(result_spend_time), 60)
                )

                print(text)
                self.signal_printf.emit(text)

            if result_id == 1:

                if "CU" in stage_id:
                    # 进入异常 但是自定义
                    self.n_battle_customize_battle_error_print(success_battle_time=success_battle_time)

                else:
                    # 进入异常, 重启再来
                    need_goto_stage = True

                    # 结束提示文本
                    text = "[{}] [单本轮战] 第{}次, 异常结束, 重启再来".format(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        success_battle_time + 1)
                    print(text)
                    self.signal_printf.emit(text)

                    self.reload_game()

            if result_id == 2:

                if "CU" in stage_id:
                    # 进入异常 但是自定义
                    self.n_battle_customize_battle_error_print(success_battle_time=success_battle_time)
                else:
                    # 跳过本次 计数+1
                    success_battle_time += 1

                    # 进入异常, 跳过
                    need_goto_stage = True

                    # 结束提示文本
                    text = "[{}] [单本轮战] 第{}次, 开始游戏异常, 重启跳过".format(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        success_battle_time)
                    print(text)
                    self.signal_printf.emit(text)

                    self.reload_game()

        """结束后进行统计和输出"""
        print("result_list:")
        print(result_list)
        valid_time = len(result_list)

        # 时间
        sum_time_spend = 0
        average_time_spend = 0

        if valid_time != 0:
            for result in result_list:
                sum_time_spend += result["time_spend"]
            average_time_spend = sum_time_spend / valid_time

        self.signal_printf.emit(
            "[{}] [单本轮战] {} {}次 结束 ".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                stage_id,
                max_times
            )
        )
        self.signal_printf.emit(
            "正常场次:{}次 总耗时:{}分{}秒 场均耗时:{}分{}秒".format(
                valid_time, *divmod(int(sum_time_spend), 60), *divmod(int(average_time_spend), 60)
            )
        )

        def print_player_loot(player_id):
            """
            打印玩家掉落信息
            :param player_id:  player_a, player_b int 1 2
            :return:
            关于 result_list
            """
            # 输入为
            count_loots_dict = {}
            count_chests_dict = {}

            # 复制key
            for _result in result_list:
                loots = _result["loot_dict_list"][player_id]["loots"]
                if loots is not None:
                    for key in loots.keys():
                        count_loots_dict[key] = 0
                chests = _result["loot_dict_list"][player_id]["chests"]
                if chests is not None:
                    for key in chests.keys():
                        count_chests_dict[key] = 0

            # 累加数据
            for _result in result_list:
                loots = _result["loot_dict_list"][player_id]["loots"]
                if loots is not None:
                    for k, v in loots.items():
                        count_loots_dict[k] += v
                chests = _result["loot_dict_list"][player_id]["chests"]
                if chests is not None:
                    for k, v in chests.items():
                        count_chests_dict[k] += v

            # 生成文本
            loots_text = ""
            chests_text = ""
            # for name, count in count_loots_dict.items():
            #     loots_text += "{}[{}|{:.1f}] ".format(name, count, count / valid_time)
            # for name, count in count_chests_dict.items():
            #     chests_text += "{}[{}|{:.1f}] ".format(name, count, count / valid_time)
            for name, count in count_loots_dict.items():
                loots_text += "{}x{:.1f} ".format(name, count / valid_time)
            for name, count in count_chests_dict.items():
                chests_text += "{}x{:.1f} ".format(name, count / valid_time)

            # 玩家A掉落
            self.signal_printf.emit(
                "[{}P掉落/场]  {}".format(
                    player_id,
                    loots_text,
                )
            )
            self.signal_printf.emit(
                "[{}P宝箱/场]  {}".format(
                    player_id,
                    chests_text
                )
            )

        if len(player) == 1:
            # 单人
            print_player_loot(player_id=player_a)
        else:
            # 多人
            print_player_loot(player_id=1)
            print_player_loot(player_id=2)

        self.signal_printf.emit("")

    def n_n_battle(self, quest_list, list_type):
        """
        [多本战斗]n次 副本外 -> 副本内n次战斗 -> 副本外
        :param quest_list: 任务清单
        :param list_type: 打哪些类型的副本 比如 ["NO","CS"]
        """

        # 战斗开始
        self.signal_printf.emit(
            "[{}] [多本轮战] 开始...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

        # 遍历完成每一个任务
        for i in range(len(quest_list)):
            quest = quest_list[i]
            # 判断不打的任务
            if quest["stage_id"].split("-")[0] in list_type:

                self.signal_printf.emit(
                    "[{}] [多本轮战] 事项{},{},{},{}次,带卡:{},Ban卡:{}".format(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        quest["battle_id"] if "battle_id" in quest else (i + 1),
                        "组队" if len(quest["player"]) == 2 else "单人",
                        quest["stage_id"],
                        quest["max_times"],
                        quest["quest_card"],
                        quest["list_ban_card"]))

                self.n_battle(
                    stage_id=quest["stage_id"],
                    max_times=quest["max_times"],
                    deck=quest["deck"],
                    player=quest["player"],
                    is_use_key=quest["is_use_key"],
                    battle_plan_1p=quest["battle_plan_1p"],
                    battle_plan_2p=quest["battle_plan_2p"],
                    quest_card=quest["quest_card"],
                    ban_card_list=quest["list_ban_card"],
                    dict_exit=quest["dict_exit"])

            else:

                self.signal_printf.emit(
                    "[{}] [多本轮战] 事项{},{},{},{}次,带卡:{},Ban卡:{},不打的地图Skip".format(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        quest["battle_id"] if "battle_id" in quest else (i + 1),
                        "组队" if quest["battle_plan_2p"] else "单人",
                        quest["stage_id"],
                        quest["max_times"],
                        quest["quest_card"],
                        quest["list_ban_card"]))
                continue

        # 战斗结束
        self.signal_printf.emit(
            "[{}] [多本轮战] 结束".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ))

    """使用n_n_battle为核心的变种函数"""

    def easy_battle(self, text_, stage_id, player, max_times,
                    deck, battle_plan_1p, battle_plan_2p, dict_exit):
        """仅调用 n_battle的简易作战"""
        # 战斗开始
        self.signal_printf.emit(
            "\n[{}] {} Link Start!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_),
            color="red")

        quest_list = [
            {
                "stage_id": stage_id,
                "max_times": max_times,
                "player": player,
                "deck": deck,
                "is_use_key": True,
                "battle_plan_1p": battle_plan_1p,
                "battle_plan_2p": battle_plan_2p,
                "quest_card": "None",
                "list_ban_card": [],
                "dict_exit": dict_exit
            }]
        self.n_n_battle(
            quest_list=quest_list,
            list_type=["NO", "EX", "MT", "CS", "OR", "PT", "CU", "GD"])

        # 战斗结束
        self.signal_printf.emit(
            "[{}] {} Completed!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_),
            color="red")

    def offer_reward(self, text_, max_times_1, max_times_2, max_times_3,
                     deck, battle_plan_1p, battle_plan_2p):

        self.signal_printf.emit(
            "\n[{}] {} Link Start!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_),
            color="red")

        self.signal_printf.emit(
            "[{}] {}开始[多本轮战]...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

        quest_list = []
        for i in range(3):
            quest_list.append({
                "deck": deck,
                "player": [2, 1],
                "is_use_key": True,
                "battle_plan_1p": battle_plan_1p,
                "battle_plan_2p": battle_plan_2p,
                "stage_id": "OR-0-" + str(i + 1),
                "max_times": [max_times_1, max_times_2, max_times_3][i],
                "quest_card": "None",
                "list_ban_card": [],
                "dict_exit": {
                    "other_time_player_a": [],
                    "other_time_player_b": [],
                    "last_time_player_a": ["竞技岛"],
                    "last_time_player_b": ["竞技岛"]}
            })
        self.n_n_battle(quest_list=quest_list, list_type=["OR"])

        # 领取奖励
        self.faa[1].action_quest_receive_rewards(mode="悬赏任务")
        self.faa[2].action_quest_receive_rewards(mode="悬赏任务")

        self.signal_printf.emit(
            "[{}] {} Completed!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_),
            color="red")

    def guild_or_spouse_quest(self, text_, quest_mode,
                              deck, battle_plan_1p, battle_plan_2p, stage=False):
        """完成公会or情侣任务"""

        self.signal_printf.emit(
            "\n[{}] {} Link Start!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_),
            color="red")

        self.signal_printf.emit(
            "[{}] {} 检查领取奖励...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))
        self.faa[1].action_quest_receive_rewards(mode=quest_mode)
        self.faa[2].action_quest_receive_rewards(mode=quest_mode)

        self.signal_printf.emit(
            "[{}] {} 获取任务列表...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

        quest_list = self.faa[1].action_get_quest(mode=quest_mode, qg_cs=stage)

        for i in quest_list:
            self.signal_printf.emit(
                "[{}] 副本:{},额外带卡:{}".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    i["stage_id"],
                    i["quest_card"]))

        for i in range(len(quest_list)):
            quest_list[i]["is_use_key"] = True
            quest_list[i]["deck"] = deck
            quest_list[i]["battle_plan_1p"] = battle_plan_1p
            quest_list[i]["battle_plan_2p"] = battle_plan_2p
            quest_list[i]["max_times"] = 1
            quest_list[i]["list_ban_card"] = []
            quest_list[i]["dict_exit"] = {
                "other_time_player_a": ["none"],
                "other_time_player_b": ["none"],
                "last_time_player_a": ["竞技岛"],
                "last_time_player_b": ["竞技岛"]
            }

        self.n_n_battle(
            quest_list=quest_list,
            list_type=["NO", "EX", "MT", "CS", "OR", "PT", "CU", "GD"])

        self.signal_printf.emit(
            "[{}] {} 检查领取奖励中...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

        self.faa[1].action_quest_receive_rewards(mode=quest_mode)
        self.faa[2].action_quest_receive_rewards(mode=quest_mode)

        self.signal_printf.emit(
            "[{}] {} Completed!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_),
            color="red")

    def guild_dungeon(self, text_, deck, battle_plan_1p, battle_plan_2p):

        self.signal_printf.emit(
            "\n[{}] {} Link Start!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_),
            color="red")

        self.signal_printf.emit(
            "[{}] {}开始[多本轮战]...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

        quest_list = []
        for i in range(3):
            quest_list.append({
                "deck": deck,
                "player": [2, 1],
                "is_use_key": True,
                "battle_plan_1p": battle_plan_1p,
                "battle_plan_2p": battle_plan_2p,
                "stage_id": "GD-0-" + str(i + 1),
                "max_times": 3,
                "quest_card": "None",
                "list_ban_card": [],
                "dict_exit": {
                    "other_time_player_a": [],
                    "other_time_player_b": [],
                    "last_time_player_a": ["竞技岛"],
                    "last_time_player_b": ["竞技岛"]}
            })
        self.n_n_battle(quest_list=quest_list, list_type=["GD"])

        self.signal_printf.emit(
            "[{}] {} Completed!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_),
            color="red")

    def alone_magic_tower_prison(self, text_, player, deck, battle_plan_1p, sutra_pavilion):

        self.signal_printf.emit(
            "\n[{}] {} Link Start!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_),
            color="red")

        if sutra_pavilion:
            stage_list = ["MT-3-1", "MT-3-2", "MT-3-3", "MT-3-4"]
        else:
            stage_list = ["MT-3-1", "MT-3-3", "MT-3-4"]

        quest_list = []
        for stage in stage_list:
            quest_list.append(
                {
                    "player": player,
                    "is_use_key": True,
                    "deck": deck,
                    "battle_plan_1p": battle_plan_1p,
                    "battle_plan_2p": battle_plan_1p,
                    "stage_id": stage,
                    "max_times": 1,
                    "quest_card": "None",
                    "list_ban_card": [],
                    "dict_exit": {
                        "other_time_player_a": [],
                        "other_time_player_b": [],
                        "last_time_player_a": ["普通红叉"],
                        "last_time_player_b": ["普通红叉"]
                    }
                }
            )
        self.n_n_battle(quest_list=quest_list, list_type=["MT"])

        self.signal_printf.emit(
            "[{}] {} Completed!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_),
            color="red")

    def customize_todo(self, text_, stage_begin: int, customize_todo_index: int):

        def read_json_to_customize_todo():
            customize_todo_list = get_customize_todo_list(with_extension=True)
            customize_todo_path = "{}\\{}".format(
                PATHS["customize_todo"],
                customize_todo_list[customize_todo_index]
            )
            with open(customize_todo_path, "r", encoding="UTF-8") as file:
                return json.load(file)

        # 开始链接
        self.signal_printf.emit(
            "[{}] {} Link Start!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_),
            color="red")

        # 战斗开始
        self.signal_printf.emit(
            "[{}] {} 开始[多本论战]".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

        # 读取json文件
        quest_list = read_json_to_customize_todo()

        # 获得最高方案的id
        max_battle_id = 1
        for quest in quest_list:
            max_battle_id = max(max_battle_id, quest["battle_id"])

        if stage_begin > max_battle_id:
            self.signal_printf.emit(
                "[{}] {} 任务序号超过了该方案最高序号! 将直接跳过!".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    text_))
            return

        # 由于任务id从1开始, 故需要减1
        # 去除序号小于stage_begin的任务
        my_list = []
        for quest in quest_list:
            if quest["battle_id"] >= stage_begin:
                my_list.append(quest)
        quest_list = my_list

        # 开始战斗
        self.n_n_battle(
            quest_list=quest_list,
            list_type=["NO", "EX", "MT", "CS", "OR", "PT", "CU", "GD"])

        # 战斗结束
        self.signal_printf.emit(
            "[{}] {} Completed!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_),
            color="red")

    def auto_food(self, deck):

        text_ = "全自动大赛"

        def a_round():

            # 两个号分别读取任务
            quest_list_1 = self.faa[1].action_get_quest(mode="美食大赛")
            quest_list_2 = self.faa[2].action_get_quest(mode="美食大赛")
            quest_list = quest_list_1 + quest_list_2

            if not quest_list:
                return False

            # 去重
            unique_data = []
            for d in quest_list:
                if d not in unique_data:
                    unique_data.append(d)
            quest_list = unique_data

            print("去重后")
            print(quest_list)

            for i in range(len(quest_list)):

                if len(quest_list[i]["player"]) == 2:
                    player_text = "组队"
                else:
                    player_text = "单人1P" if quest_list[i]["player"] == [1] else "单人2P"

                self.signal_printf.emit(
                    "[{}] [多本轮战] 事项{},{},{},{},{}次,带卡:{},Ban卡:{}".format(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        i + 1,
                        player_text,
                        quest_list[i]["stage_id"],
                        "用钥匙" if quest_list[i]["stage_id"] else "无钥匙",
                        quest_list[i]["max_times"],
                        quest_list[i]["quest_card"],
                        quest_list[i]["list_ban_card"]))

            for i in range(len(quest_list)):
                quest_list[i]["deck"] = deck
                quest_list[i]["battle_plan_1p"] = 0
                quest_list[i]["battle_plan_2p"] = 1

            self.n_n_battle(
                quest_list=quest_list,
                list_type=["NO", "EX", "MT", "CS", "OR", "PT", "CU", "GD"])

            return True

        def auto_food_main():

            # 开始链接
            self.signal_printf.emit(
                "[{}] [{}] Link Start!".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    text_),
                color="red")

            # 先领一下已经完成的大赛任务
            self.faa[1].action_get_quest(mode="美食大赛")
            self.faa[2].action_get_quest(mode="美食大赛")

            i = 0
            while True:
                i += 1
                self.signal_printf.emit("[{}] [{}] 第{}次循环，开始".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    text_,
                    i))
                round_result = a_round()

                self.signal_printf.emit("[{}] [{}] 第{}次循环，结束".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    text_,
                    i))
                if not round_result:
                    break

            self.signal_printf.emit("[{}] [{}] 所有被记录的任务已完成!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

            # 开始链接
            self.signal_printf.emit(
                "[{}] [{}] Completed!".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    text_),
                color="red")

        auto_food_main()

    """主要线程"""

    def run(self):

        # current todo plan option
        c_opt = self.opt["todo_plans"][self.opt["current_plan"]]

        self.signal_printf.emit(
            "每一个大类的任务开始前均会重启游戏以防止bug...")
        start_time = datetime.datetime.now()

        need_reload = False
        need_reload = need_reload or c_opt["sign_in"]["active"]
        need_reload = need_reload or c_opt["fed_and_watered"]["active"]
        need_reload = need_reload or c_opt["warrior"]["active"]
        if need_reload:
            self.reload_game()

        my_opt = c_opt["sign_in"]
        if my_opt["active"]:
            self.all_sign_in(
                is_group=my_opt["is_group"]
            )

        my_opt = c_opt["fed_and_watered"]
        if my_opt["active"]:
            self.signal_printf.emit(
                "[{}] [浇水 施肥 摘果 领取] 执行中...".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            self.faa[1].fed_and_watered()
            if my_opt["is_group"]:
                self.faa[2].fed_and_watered()

        my_opt = c_opt["warrior"]
        if my_opt["active"]:
            self.easy_battle(
                text_="[勇士挑战]",
                stage_id="NO-2-17",
                player=[2, 1] if my_opt["is_group"] else [1],
                max_times=int(my_opt["max_times"]),
                deck=my_opt["deck"],
                battle_plan_1p=my_opt["battle_plan_1p"],
                battle_plan_2p=my_opt["battle_plan_2p"],
                dict_exit={
                    "other_time_player_a": [],
                    "other_time_player_b": [],
                    "last_time_player_a": ["竞技岛"],
                    "last_time_player_b": ["竞技岛"]
                })

            # 勇士挑战在全部完成后, [进入竞技岛], 创建房间者[有概率]会保留勇士挑战选择关卡的界面.
            # 对于创建房间者, 在触发后, 需要设定完成后退出方案为[进入竞技岛 → 点X] 才能完成退出.
            # 对于非创建房间者, 由于号1不会出现选择关卡界面, 会因为找不到[X]而卡死.
            # 无论如何都会出现卡死的可能性.
            # 因此此处选择退出方案直接选择[进入竞技岛], 并将勇士挑战选择放在本大类的最后进行, 依靠下一个大类开始后的重启游戏刷新.

        need_reload = False
        need_reload = need_reload or c_opt["normal_battle"]["active"]
        need_reload = need_reload or c_opt["offer_reward"]["active"]
        need_reload = need_reload or c_opt["cross_server"]["active"]

        if need_reload:
            self.reload_game()

        my_opt = c_opt["normal_battle"]
        if my_opt["active"]:
            self.easy_battle(
                text_="[常规刷本]",
                stage_id=my_opt["stage"],
                player=[2, 1] if my_opt["is_group"] else [1],
                max_times=int(my_opt["max_times"]),
                deck=my_opt["deck"],
                battle_plan_1p=my_opt["battle_plan_1p"],
                battle_plan_2p=my_opt["battle_plan_2p"],
                dict_exit={
                    "other_time_player_a": [],
                    "other_time_player_b": [],
                    "last_time_player_a": ["竞技岛"],
                    "last_time_player_b": ["竞技岛"]
                })

        my_opt = c_opt["offer_reward"]
        if my_opt["active"]:
            self.offer_reward(
                text_="[悬赏任务]",
                deck=my_opt["deck"],
                max_times_1=my_opt["max_times_1"],
                max_times_2=my_opt["max_times_2"],
                max_times_3=my_opt["max_times_3"],
                battle_plan_1p=my_opt["battle_plan_1p"],
                battle_plan_2p=my_opt["battle_plan_2p"])

        my_opt = c_opt["cross_server"]
        if my_opt["active"]:
            self.easy_battle(
                text_="[跨服副本]",
                stage_id=my_opt["stage"],
                player=[1, 2] if my_opt["is_group"] else [1],
                max_times=int(my_opt["max_times"]),
                deck=my_opt["deck"],
                battle_plan_1p=my_opt["battle_plan_1p"],
                battle_plan_2p=my_opt["battle_plan_2p"],
                dict_exit={
                    "other_time_player_a": [],
                    "other_time_player_b": [],
                    "last_time_player_a": ["竞技岛"],
                    "last_time_player_b": ["竞技岛"]
                })

        need_reload = False
        need_reload = need_reload or c_opt["quest_guild"]["active"]
        need_reload = need_reload or c_opt["guild_dungeon"]["active"]
        need_reload = need_reload or c_opt["quest_spouse"]["active"]
        need_reload = need_reload or c_opt["relic"]["active"]

        if need_reload:
            self.reload_game()

        my_opt = c_opt["quest_guild"]
        if my_opt["active"]:
            self.guild_or_spouse_quest(
                text_="[公会任务]",
                quest_mode="公会任务",
                deck=my_opt["deck"],
                battle_plan_1p=my_opt["battle_plan_1p"],
                battle_plan_2p=my_opt["battle_plan_2p"],
                stage=my_opt["stage"])

        my_opt = c_opt["guild_dungeon"]
        if my_opt["active"]:
            self.guild_dungeon(
                text_="[公会副本]",
                deck=c_opt["quest_guild"]["deck"],
                battle_plan_1p=c_opt["quest_guild"]["battle_plan_1p"],
                battle_plan_2p=c_opt["quest_guild"]["battle_plan_2p"])

        my_opt = c_opt["quest_spouse"]
        if my_opt["active"]:
            self.guild_or_spouse_quest(
                text_="[情侣任务]",
                quest_mode="情侣任务",
                deck=c_opt["quest_guild"]["deck"],
                battle_plan_1p=c_opt["quest_guild"]["battle_plan_1p"],
                battle_plan_2p=c_opt["quest_guild"]["battle_plan_2p"])

        my_opt = c_opt["relic"]
        if my_opt["active"]:
            self.easy_battle(
                text_="[火山遗迹]",
                stage_id=my_opt["stage"],
                player=[2, 1] if my_opt["is_group"] else [1],
                max_times=int(my_opt["max_times"]),
                deck=my_opt["deck"],
                battle_plan_1p=my_opt["battle_plan_1p"],
                battle_plan_2p=my_opt["battle_plan_2p"],
                dict_exit={
                    "other_time_player_a": [],
                    "other_time_player_b": [],
                    "last_time_player_a": ["竞技岛"],
                    "last_time_player_b": ["竞技岛"]
                })

        need_reload = False
        need_reload = need_reload or c_opt["magic_tower_alone_1"]["active"]
        need_reload = need_reload or c_opt["magic_tower_alone_2"]["active"]
        need_reload = need_reload or c_opt["magic_tower_prison_1"]["active"]
        need_reload = need_reload or c_opt["magic_tower_prison_2"]["active"]
        need_reload = need_reload or c_opt["magic_tower_double"]["active"]
        need_reload = need_reload or c_opt["pet_temple_1"]["active"]
        need_reload = need_reload or c_opt["pet_temple_2"]["active"]
        if need_reload:
            self.reload_game()

        for player_id in [1, 2]:
            my_opt = c_opt["magic_tower_alone_{}".format(player_id)]
            if my_opt["active"]:
                self.easy_battle(
                    text_="[魔塔单人_{}P]".format(player_id),
                    stage_id="MT-1-" + str(my_opt["stage"]),
                    player=[player_id],
                    max_times=int(my_opt["max_times"]),
                    deck=my_opt["deck"],
                    battle_plan_1p=my_opt["battle_plan_1p"],
                    battle_plan_2p=my_opt["battle_plan_1p"],
                    dict_exit={
                        "other_time_player_a": [],
                        "other_time_player_b": [],
                        "last_time_player_a": ["普通红叉"],
                        "last_time_player_b": []
                    }
                )

        for player_id in [1, 2]:
            my_opt = c_opt["magic_tower_prison_{}".format(player_id)]
            if my_opt["active"]:
                self.alone_magic_tower_prison(
                    text_="[魔塔密室_{}P]".format(player_id),
                    player=[player_id],
                    deck=my_opt["deck"],
                    battle_plan_1p=my_opt["battle_plan_1p"],
                    sutra_pavilion=my_opt["stage"])

        my_opt = c_opt["magic_tower_double"]
        if my_opt["active"]:
            self.easy_battle(
                text_="[魔塔双人]",
                stage_id="MT-2-" + str(my_opt["stage"]),
                player=[2, 1],
                max_times=int(my_opt["max_times"]),
                deck=my_opt["deck"],
                battle_plan_1p=my_opt["battle_plan_1p"],
                battle_plan_2p=my_opt["battle_plan_2p"],
                dict_exit={
                    "other_time_player_a": [],
                    "other_time_player_b": ["回到上一级"],
                    "last_time_player_a": ["普通红叉"],
                    "last_time_player_b": ["回到上一级"]
                }
            )

        for player_id in [1, 2]:
            my_opt = c_opt["pet_temple_{}".format(player_id)]
            if my_opt["active"]:
                self.easy_battle(
                    text_="[萌宠神殿_{}P]".format(player_id),
                    stage_id="PT-0-" + str(my_opt["stage"]),
                    player=[player_id],
                    max_times=1,
                    deck=my_opt["deck"],
                    battle_plan_1p=my_opt["battle_plan_1p"],
                    battle_plan_2p=my_opt["battle_plan_1p"],
                    dict_exit={
                        "other_time_player_a": [],
                        "other_time_player_b": [],
                        "last_time_player_a": [],  # "回到上一级","普通红叉" 但之后会刷新 所以不管了
                        "last_time_player_b": []
                    }
                )

        self.signal_printf.emit(
            "[{}] 全部主要事项已完成! 耗时:{}".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                datetime.datetime.now() - start_time
            )
        )

        need_reload = False
        need_reload = need_reload or c_opt["receive_awards"]["active"]
        need_reload = need_reload or c_opt["use_items"]["active"]
        need_reload = need_reload or c_opt["loop_cross_server"]["active"]
        need_reload = need_reload or c_opt["customize"]["active"]
        need_reload = need_reload or c_opt["auto_food"]["active"]

        if need_reload:
            self.reload_game()

        my_opt = c_opt["receive_awards"]
        if my_opt["active"]:
            self.receive_quest_rewards(
                is_group=my_opt["is_group"]
            )

        my_opt = c_opt["use_items"]
        if my_opt["active"]:
            self.use_items(
                is_group=my_opt["is_group"])

        my_opt = c_opt["loop_cross_server"]
        if my_opt["active"]:
            self.loop_cross_server(
                is_group=my_opt["is_group"],
                deck=c_opt["quest_guild"]["deck"])

        my_opt = c_opt["customize_battle"]
        if my_opt["active"]:
            self.easy_battle(
                text_="[自建房战斗]",
                stage_id="CU-0-0",
                player=[[1, 2], [2, 1], [1], [2]][my_opt["is_group"]],
                max_times=int(my_opt["max_times"]),
                deck=my_opt["deck"],
                battle_plan_1p=my_opt["battle_plan_1p"],
                battle_plan_2p=my_opt["battle_plan_2p"],
                dict_exit={
                    "other_time_player_a": [],
                    "other_time_player_b": [],
                    "last_time_player_a": [],
                    "last_time_player_b": []
                }
            )

        my_opt = c_opt["customize"]
        if my_opt["active"]:
            self.customize_todo(
                text_="[高级自定义]",
                stage_begin=my_opt["stage"],
                customize_todo_index=my_opt["battle_plan_1p"])

        my_opt = c_opt["auto_food"]
        if my_opt["active"]:
            self.auto_food(
                deck=my_opt["deck"],
            )
        # 全部完成了刷新一下
        self.signal_printf.emit(
            "\n[{}] 已完成所有事项！建议勾选刷新游戏回到登录界面, 防止长期运行flash导致卡顿".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        if c_opt["end_exit_game"]:
            self.reload_to_login_ui()

        # 全部完成了发个信号
        self.signal_end.emit()

    def pause(self):
        """暂停"""
        self.mutex.lock()
        self.is_paused = True
        self.mutex.unlock()

    def resume(self):
        """恢复暂停"""
        self.mutex.lock()
        self.is_paused = False
        self.condition.wakeAll()
        self.mutex.unlock()


class MyMainWindow2(MyMainWindow1):
    signal_dialog = pyqtSignal(str, str)  # 标题, 正文
    signal_end = pyqtSignal()
    signal_printf_1 = pyqtSignal(str)
    signal_printf_2 = pyqtSignal(str, str)

    def __init__(self):
        # 继承父类构造方法
        super().__init__()
        self.thread_todo = None
        self.reply = None
        self.faa = [None, None, None]
        # 线程激活即为True
        self.thread_states = False
        # 链接防呆弹窗
        self.signal_dialog.connect(self.show_dialog)
        # 链接日志输入
        self.signal_printf = self.SignalPrintf(signal_1=self.signal_printf_1, signal_2=self.signal_printf_2)
        self.signal_printf_1.connect(self.printf)
        self.signal_printf_2.connect(self.printf)
        # 链接中止函数
        self.signal_end.connect(self.todo_end)
        # 储存所有信号
        self.signal_dict = {
            "printf": self.signal_printf,
            "dialog": self.signal_dialog,
            "end": self.signal_end
        }

    class SignalPrintf(QObject):

        def __init__(self, signal_1, signal_2):
            super().__init__()
            self.signal_1 = signal_1
            self.signal_2 = signal_2

        def emit(self, text, color=None):
            # 根据提供的参数数量发射不同的信号
            if color is not None:
                self.signal_2.emit(text, color)
            else:
                self.signal_1.emit(text)

    def todo_end(self):
        # 设置flag
        self.thread_states = False
        # 设置按钮文本
        self.Button_Start.setText("开始\nLink Start")
        # 设置输出文本
        self.printf("\n>>> 全部完成 线程关闭 <<<\n")
        # 中止点击处理
        T_ACTION_QUEUE_TIMER.stop()

    def todo_start(self):
        # 设置flag
        self.thread_states = True
        # 设置按钮文本
        self.Button_Start.setText("终止\nEnd")
        # 设置输出文本
        self.TextBrowser.clear()
        self.start_print()
        self.printf("\n>>> 链接开始 线程开启 <<<\n")
        # 启动点击处理
        T_ACTION_QUEUE_TIMER.start()

    def start_all(self):

        # 先读取界面上的方案
        self.ui_to_opt()

        channel_1p, channel_2p = get_channel_name(
            game_name=self.opt["base_settings"]["game_name"],
            name_1p=self.opt["base_settings"]["name_1p"],
            name_2p=self.opt["base_settings"]["name_2p"])
        # 防呆测试 不通过就直接结束弹窗
        handles = {
            1: faa_get_handle(channel=channel_1p, mode="360"),
            2: faa_get_handle(channel=channel_2p, mode="360")}
        for player, handle in handles.items():
            if handle is None or handle == 0:
                # 报错弹窗
                self.signal_dialog.emit(
                    "出错！(╬◣д◢)",
                    f"{player}P存在错误的窗口名或游戏名称, 请参考 [使用前看我!.pdf] 或 [README.md]")
                return

        self.todo_start()

        # 生成随机数种子
        random_seed = random.randint(-100, 100)

        # 开始创建faa
        faa = [None, None, None]
        faa[1] = FAA(
            channel=channel_1p,
            player=1,
            character_level=self.opt["base_settings"]["level_1p"],
            is_auto_battle=self.opt["advanced_settings"]["auto_use_card"],  # bool 自动战斗
            is_auto_pickup=self.opt["advanced_settings"]["auto_pickup_1p"],
            random_seed=random_seed,
            signal_dict=self.signal_dict)
        faa[2] = FAA(
            channel=channel_2p,
            player=2,
            character_level=self.opt["base_settings"]["level_2p"],
            is_auto_battle=self.opt["advanced_settings"]["auto_use_card"],
            is_auto_pickup=self.opt["advanced_settings"]["auto_pickup_2p"],
            random_seed=random_seed,
            signal_dict=self.signal_dict)

        # 创造todo线程
        self.thread_todo = Todo(faa=faa, opt=self.opt, signal_dict=self.signal_dict)

        # 开始线程
        self.thread_todo.start()

    def stop_all(self):
        """
                  线程已经激活 则从外到内中断,再从内到外销毁
                  thread_todo (QThread)
                      |-- thread_1p (ThreadWithException)
                      |-- thread_2p (ThreadWithException)
                  """
        # 暂停外部线程
        self.thread_todo.pause()

        # 中断[内部战斗线程]
        # Q thread 线程 stop方法需要自己手写
        thread = self.thread_todo.thread_manager
        if thread is not None:
            thread.stop()
            thread.wait()

        # python 默认线程 可用stop线程
        for thread in [self.thread_todo.thread_1p, self.thread_todo.thread_2p]:
            if thread is not None:
                thread.stop()
                thread.join()  # 等待线程确实中断

        # 中断 销毁 [任务线程]
        self.thread_todo.terminate()
        self.thread_todo.wait()  # 等待线程确实中断
        self.thread_todo.deleteLater()

        # 结束线程后的ui处理
        self.todo_end()

    def click_btn_start(self):
        """战斗开始函数"""

        # 线程没有激活
        if not self.thread_states:
            self.start_all()
        else:
            self.stop_all()

    @QtCore.pyqtSlot(str, str)
    def show_dialog(self, title, message):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        msg.exec_()


def main():
    # 实例化 PyQt后台管理
    app = QApplication(sys.argv)

    # 实例化 主窗口
    window = MyMainWindow2()

    # 注册函数：开始/结束/高级设置按钮
    window.Button_Start.clicked.connect(lambda: window.click_btn_start())
    window.Button_Save.clicked.connect(lambda: window.click_btn_save())
    window.Button_DeletePlan.clicked.connect(lambda: window.delete_current_plan())
    window.Button_RenamePlan.clicked.connect(lambda: window.rename_current_plan())
    window.Button_CreatePlan.clicked.connect(lambda: window.create_new_plan())
    window.CurrentPlan.currentIndexChanged.connect(lambda: window.opt_to_ui_todo_plans())

    # window.Button_AdvancedSettings.clicked.connect(lambda: window.click_btn_advanced_settings())

    # 主窗口 实现
    window.show()

    # 运行主循环，必须调用此函数才可以开始事件处理
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
