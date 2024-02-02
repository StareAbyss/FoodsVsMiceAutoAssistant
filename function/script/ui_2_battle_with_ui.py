import datetime
import json
import sys
import time
from time import sleep

from PyQt5.QtCore import *
from PyQt5.QtWidgets import QApplication

from function.common.bg_mouse import mouse_left_click
from function.common.bg_p_compare import loop_find_p_in_w
from function.common.thread_with_exception import ThreadWithException
from function.get_paths import paths
from function.script.common import FAA
from function.script.scattered.get_channel_name import get_channel_name
from function.script.scattered.get_customize_todo_list import get_customize_todo_list
from function.script.ui_1_load_opt import MyMainWindow1


class Todo(QThread):
    # 初始化向外发射信号
    sin_out = pyqtSignal(str)
    sin_out_completed = pyqtSignal()

    def __init__(self, faa, opt):
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

    """业务代码, 不直接调用opt设定, 会向输出窗口传参"""

    def reload_game(self):

        self.sin_out.emit(
            "[{}] Refresh Game...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

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
        sleep(0.5)
        self.thread_2p.start()
        self.thread_1p.join()
        self.thread_2p.join()

    def reload_to_login_ui(self):

        self.sin_out.emit(
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
        sleep(0.5)
        self.thread_2p.start()
        self.thread_1p.join()
        self.thread_2p.join()

    def receive_quest_rewards(self):

        self.sin_out.emit(
            "[{}] [领取奖励] 开始...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        """普通任务"""
        self.sin_out.emit(
            "[{}] [领取奖励] [普通任务] 开始...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].action_quest_receive_rewards,
            name="1P Thread - ReceiveQuest",
            kwargs={
                "mode": "普通任务"
            })

        self.thread_2p = ThreadWithException(
            target=self.faa[2].action_quest_receive_rewards,
            name="2P Thread - ReceiveQuest",
            kwargs={
                "mode": "普通任务"
            })

        # 涉及键盘抢夺, 容错低, 最好分开执行
        self.thread_1p.start()
        sleep(0.333)
        self.thread_2p.start()
        self.thread_1p.join()
        self.thread_2p.join()

        self.sin_out.emit(
            "[{}] [领取奖励] [普通任务] 结束".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        """美食大赛"""

        self.sin_out.emit(
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

        self.sin_out.emit(
            "[{}] [领取奖励] [美食大赛] 结束...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        """大富翁"""
        self.sin_out.emit(
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

        self.sin_out.emit(
            "[{}] [领取奖励] [大富翁] 结束...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        self.sin_out.emit(
            "[{}] 领取所有[任务]奖励, 完成".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    def use_items(self):

        self.sin_out.emit(
            "[{}] 使用绑定消耗品和宝箱, 开始".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        self.sin_out.emit(
            "[{}] 领取一般任务奖励...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].use_item,
            name="1P Thread - UseItems",
            kwargs={})

        self.thread_2p = ThreadWithException(
            target=self.faa[2].use_item,
            name="2P Thread - UseItems",
            kwargs={})

        # 涉及键盘抢夺, 容错低, 最好分开执行
        self.thread_1p.start()
        sleep(0.333)
        self.thread_2p.start()
        self.thread_1p.join()
        self.thread_2p.join()

        self.sin_out.emit(
            "[{}] 使用绑定消耗品和宝箱, 完成".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    def cross_server_reputation(self, deck):

        self.sin_out.emit(
            "[{}] 无限刷跨服启动!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].cross_server_reputation,
            name="1P Thread",
            kwargs={"deck": deck})

        self.thread_2p = ThreadWithException(
            target=self.faa[2].cross_server_reputation,
            name="2P Thread",
            kwargs={"deck": deck})

        self.thread_1p.start()
        sleep(0.5)
        self.thread_2p.start()
        self.thread_1p.join()
        self.thread_2p.join()

    def invite(
            self,
            player_a,
            player_b):
        """
        号1邀请号2到房间 需要在同一个区
        :return: bool 是否最终找到了图片
        """

        faa_a = self.faa[player_a]
        faa_b = self.faa[player_b]

        zoom = self.faa[1].zoom

        find = loop_find_p_in_w(
            raw_w_handle=faa_a.handle,
            raw_range=[796, 413, 950, 485],
            target_path=paths["picture"]["common"] + "\\战斗\\战斗前_开始按钮.png",
            click_zoom=zoom,
            target_sleep=0.3,
            click=False,
            target_failed_check=2.0)
        if not find:
            print("2s找不到开始游戏! 土豆服务器问题, 创建房间可能失败!")
            return False

        # 点击[房间ui-邀请按钮]
        mouse_left_click(
            handle=faa_a.handle,
            x=int(410 * zoom),
            y=int(546 * zoom),
            sleep_time=0.5)

        # 点击[房间ui-邀请ui-好友按钮]
        mouse_left_click(
            handle=faa_a.handle,
            x=int(535 * zoom),
            y=int(130 * zoom),
            sleep_time=0.5)

        # 直接邀请
        mouse_left_click(
            handle=faa_a.handle,
            x=int(601 * zoom),
            y=int(157 * zoom),
            sleep_time=0.5)

        # p2接受邀请
        find = loop_find_p_in_w(
            raw_w_handle=faa_b.handle,
            raw_range=[0, 0, 950, 600],
            target_path=paths["picture"]["common"] + "\\战斗\\战斗前_接受邀请.png",
            click_zoom=zoom,
            target_sleep=2.0,
            target_failed_check=2.0)

        if not find:
            print("2s没能组队? 土豆服务器问题, 尝试解决ing...")
            return False

        # p1关闭邀请窗口
        mouse_left_click(
            handle=faa_a.handle,
            x=int(590 * zoom),
            y=int(491 * zoom),
            sleep_time=1)

        return True

    def battle(
            self,
            player_a,
            player_b):

        is_group = self.faa[player_a].is_group
        result = 0
        # 分开进行战前准备
        if result == 0:
            if is_group:
                result = max(result, self.faa[player_b].action_round_of_battle_before())
            result = max(result, self.faa[player_a].action_round_of_battle_before())

        if result == 0:
            # 多线程进行战斗
            self.thread_1p = ThreadWithException(
                target=self.faa[player_a].action_round_of_battle_self,
                name="{}P Thread - Battle".format(player_a),
                kwargs={})
            if is_group:
                self.thread_2p = ThreadWithException(
                    target=self.faa[player_b].action_round_of_battle_self,
                    name="{}P Thread - Battle".format(player_b),
                    kwargs={})

            self.thread_1p.start()
            if is_group:
                self.thread_2p.start()

            # 阻塞进程让进程执行完再继续本循环函数
            self.thread_1p.join()
            if is_group:
                self.thread_2p.join()

            result = self.thread_1p.get_return_value()
            if is_group:
                result = max(result, self.thread_2p.get_return_value())

        if result == 0:
            # 分开进行战后检查
            result = self.faa[player_a].action_round_of_battle_after()
            if is_group:
                result = self.faa[player_b].action_round_of_battle_after()

        return result

    def goto_stage_and_invite(
            self,
            stage_id,
            mt_first_time,
            player_a,
            player_b):

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
                    faa_a.action_goto_stage(room_creator=True)
                    faa_b.action_goto_stage(room_creator=False)
                else:
                    # 魔塔进入
                    faa_a.action_goto_stage(room_creator=True, mt_first_time=mt_first_time)
                    if mt_first_time:
                        faa_b.action_goto_stage(room_creator=False, mt_first_time=mt_first_time)

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
                    self.sin_out.emit(text)
                    # 邀请成功 返回退出
                    return 0

                else:
                    failed_time += 1
                    mt_first_time = True

                    text = "[{}] [单本轮战] 服务器抽风,进入竞技岛重新邀请...({}/3)".format(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        failed_time)
                    print(text)
                    self.sin_out.emit(text)

                    if failed_time == 3:
                        text = "[{}] [单本轮战] 服务器抽风过头, 刷新游戏!".format(
                            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            failed_time)
                        print(text)
                        self.sin_out.emit(text)
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
                self.sin_out.emit(text)
                return 2

    def n_battle(
            self,
            stage_id,
            player,  # [1],[2],[1,2],[2,1]
            max_times,
            deck,
            quest_card,
            ban_card_list,
            battle_plan_1p,
            battle_plan_2p,
            dict_exit
    ):
        """[单本轮战]1次 副本外 → 副本内n次战斗 → 副本外"""

        # 判断是不是打魔塔
        is_mt = "MT" in stage_id

        # 处理多人信息
        is_group = False
        player_a = player[0]
        player_b = 1 if player_a == 2 else 2
        faa_a = self.faa[player_a]
        faa_b = self.faa[player_b]
        if len(player) == 2:
            is_group = True
            player_b = player[1]
        battle_plan_a = battle_plan_1p if player_a == 1 else battle_plan_2p
        battle_plan_b = battle_plan_1p if player_b == 1 else battle_plan_2p

        self.sin_out.emit(
            "[{}] [单本轮战] {} {}次".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                stage_id,
                max_times))

        # 填入战斗方案和关卡信息
        faa_a.set_config_for_battle(
            battle_mode=0,
            is_group=is_group,
            deck=deck,
            quest_card=quest_card,
            ban_card_list=ban_card_list,
            battle_plan_index=battle_plan_a,
            stage_id=stage_id)
        faa_b.set_config_for_battle(
            battle_mode=0,
            is_group=is_group,
            deck=deck,
            quest_card=quest_card,
            ban_card_list=ban_card_list,
            battle_plan_index=battle_plan_b,
            stage_id=stage_id)

        # 检查人物等级 先检查 player_a 组队额外检查 player_b
        if not faa_a.check_level():
            self.sin_out.emit(
                "[{}] [单本轮战] {}P等级不足, 跳过".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    player_a
                ))
            return False
        if is_group:
            if not faa_b.check_level():
                self.sin_out.emit(
                    "[{}] [单本轮战] {}P等级不足, 跳过".format(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        player_b
                    ))
                return False

        need_goto_stage = True  # 标记是否需要进入副本
        success_battle_time = 0  # 记录成功战斗次数

        # 轮次作战
        while success_battle_time < max_times:

            # 前往副本
            result = 0
            if not is_mt:
                # 非魔塔
                if need_goto_stage:
                    if not is_group:
                        # 单人前往副本
                        faa_a.action_goto_stage(
                            room_creator=True)
                    else:
                        # 多人前往副本
                        result = self.goto_stage_and_invite(
                            stage_id=stage_id,
                            mt_first_time=False,
                            player_a=player_a,
                            player_b=player_b)

                    need_goto_stage = False  # 进入后Flag变化
            else:
                # 魔塔
                if not is_group:
                    # 单人前往副本
                    faa_a.action_goto_stage(room_creator=True, mt_first_time=need_goto_stage)
                else:
                    # 多人前往副本
                    result = self.goto_stage_and_invite(
                        stage_id=stage_id,
                        mt_first_time=need_goto_stage,
                        player_a=player_a,
                        player_b=player_b)

                need_goto_stage = False  # 进入后Flag变化

            if result == 2:
                # 跳过本次 计数+1
                success_battle_time += 1
                # 进入异常, 跳过
                need_goto_stage = True
                # 结束提示文本
                text = "[{}] [单本轮战] 第{}次, 创建房间多次异常, 重启跳过".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    success_battle_time)
                print(text)
                self.sin_out.emit(text)

                self.reload_game()

            timer_begin = time.time()

            print("=" * 50)
            text = "[{}] [单本轮战] 第{}次, 开始".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                success_battle_time + 1)
            print(text)
            self.sin_out.emit(text)

            # 创建战斗进程 -> 开始进程
            result = self.battle(player_a=player_a, player_b=player_b)

            if result == 0:
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

                # 结束提示文本
                text = "[{}] [单本轮战] 第{}次, 正常结束, 耗时:{:.0f}s".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    success_battle_time,
                    time.time() - timer_begin)
                print(text)
                self.sin_out.emit(text)

            if result == 1:
                # 进入异常, 重启再来
                need_goto_stage = True

                # 结束提示文本
                text = "[{}] [单本轮战] 第{}次, 异常结束, 重启再来".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    success_battle_time + 1)
                print(text)
                self.sin_out.emit(text)

                self.reload_game()

            if result == 2:
                # 跳过本次 计数+1
                success_battle_time += 1

                # 进入异常, 跳过
                need_goto_stage = True

                # 结束提示文本
                text = "[{}] [单本轮战] 第{}次, 开始游戏异常, 重启跳过".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    success_battle_time)
                print(text)
                self.sin_out.emit(text)

                self.reload_game()

    def n_n_battle(
            self,
            quest_list,
            list_type
    ):
        """
        [多本战斗]n次 副本外 -> 副本内n次战斗 -> 副本外
        :param quest_list: 任务清单
        :param list_type: 打哪些类型的副本 比如 ["NO","CS"]
        """

        # 战斗开始
        self.sin_out.emit(
            "[{}] [多本轮战] 开始...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

        # 遍历完成每一个任务
        for i in range(len(quest_list)):
            quest = quest_list[i]
            # 判断不打的任务
            if quest["stage_id"].split("-")[0] in list_type:

                self.sin_out.emit(
                    "[{}] [多本轮战] 事项{},{},{},{}次,带卡:{},Ban卡:{}".format(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        i + 1,
                        "组队" if quest["battle_plan_2p"] else "单人",
                        quest["stage_id"],
                        quest["max_times"],
                        quest["quest_card"],
                        quest["list_ban_card"]))

                self.n_battle(
                    stage_id=quest["stage_id"],
                    max_times=quest["max_times"],
                    deck=quest["deck"],
                    player=quest["player"],
                    battle_plan_1p=quest["battle_plan_1p"],
                    battle_plan_2p=quest["battle_plan_2p"],
                    quest_card=quest["quest_card"],
                    ban_card_list=quest["list_ban_card"],
                    dict_exit=quest["dict_exit"])

            else:

                self.sin_out.emit(
                    "[{}] [多本轮战] 事项{},{},{},{}次,带卡:{},Ban卡:{},不打的地图Skip".format(
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        i + 1,
                        "组队" if quest["battle_plan_2p"] else "单人",
                        quest["stage_id"],
                        quest["max_times"],
                        quest["quest_card"],
                        quest["list_ban_card"]))
                continue

        # 战斗开始
        self.sin_out.emit(
            "[{}] [多本轮战] 结束".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

    def n_battle_customize(
            self,
            text_,
            is_group,
            max_times,
            deck,
            battle_plan_1p,
            battle_plan_2p,
    ):
        """
        用于自建房对战
        """
        self.sin_out.emit(
            "\n[{}] {} Link Start!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

        # index of player -> list of player
        player = [2, 1]
        if is_group == 0:
            player = [1, 2]
        elif is_group == 1:
            player = [2, 1]
        elif is_group == 2:
            player = [1]
        elif is_group == 3:
            player = [2]

        # 处理多人信息
        is_group = False
        player_a = player[0]
        player_b = 1 if player_a == 2 else 2
        faa_a = self.faa[player_a]
        faa_b = self.faa[player_b]
        if len(player) == 2:
            is_group = True
            player_b = player[1]
        battle_plan_a = battle_plan_1p if player_a == 1 else battle_plan_2p
        battle_plan_b = battle_plan_1p if player_b == 1 else battle_plan_2p

        # 填入战斗方案和关卡信息
        faa_a.set_config_for_battle(
            battle_mode=0,
            is_group=is_group,
            deck=deck,
            quest_card="None",
            ban_card_list=[],
            battle_plan_index=battle_plan_a,
            stage_id="OR-1-0"  # 该地图不自动放承载卡, 且铲所有卡~
        )
        faa_b.set_config_for_battle(
            battle_mode=0,
            is_group=is_group,
            deck=deck,
            quest_card="None",
            ban_card_list=[],
            battle_plan_index=battle_plan_b,
            stage_id="OR-1-0"  # 该地图不自动放承载卡, 且铲所有卡~
        )

        success_battle_time = 0  # 记录成功战斗次数

        # 轮次作战
        while success_battle_time < max_times:

            timer_begin = time.time()

            print("=" * 50)
            text = "[{}] [单本轮战] 第{}次, 开始".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                success_battle_time + 1)
            print(text)
            self.sin_out.emit(text)

            # 创建战斗进程 -> 开始进程
            result = self.battle(player_a=player_a, player_b=player_b)

            if result == 0:
                # 战斗成功 计数+1
                success_battle_time += 1

                # 结束提示文本
                text = "[{}] [单本轮战] 第{}次, 正常结束, 耗时:{:.0f}s".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    success_battle_time,
                    time.time() - timer_begin)
                print(text)
                self.sin_out.emit(text)

            else:
                # 结束提示文本
                text = "[{}] [单本轮战] 第{}次, 出现未知异常! 刷新后卡死, 以防止更多问题, 出现此问题可上报作者".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    success_battle_time)
                print(text)
                self.sin_out.emit(text)

                self.reload_game()
                sleep(60 * 60 * 24)

        # 战斗结束
        self.sin_out.emit(
            "[{}] {} Completed!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

    def guild_or_spouse_quest(
            self,
            text_,
            quest_mode,
            deck,
            battle_plan_1p,
            battle_plan_2p
    ):
        """完成公会or情侣任务"""

        self.sin_out.emit(
            "\n[{}] {} Link Start!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

        self.sin_out.emit(
            "[{}] {} 检查领取奖励...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))
        self.faa[1].action_quest_receive_rewards(mode=quest_mode)
        self.faa[2].action_quest_receive_rewards(mode=quest_mode)

        self.sin_out.emit(
            "[{}] {} 获取任务列表...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))
        quest_list = self.faa[1].action_get_quest(mode=quest_mode)
        for i in quest_list:
            self.sin_out.emit(
                "[{}] 副本:{},额外带卡:{}".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    i["stage_id"],
                    i["quest_card"]))
        for i in range(len(quest_list)):
            quest_list[i]["deck"] = deck
            quest_list[i]["battle_plan_1p"] = battle_plan_1p
            quest_list[i]["battle_plan_2p"] = battle_plan_2p

        self.n_n_battle(
            quest_list=quest_list,
            list_type=["NO"])

        self.sin_out.emit(
            "[{}] {} 检查领取奖励中...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

        self.faa[1].action_quest_receive_rewards(mode=quest_mode)
        self.faa[2].action_quest_receive_rewards(mode=quest_mode)

        self.sin_out.emit(
            "[{}] {} Completed!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

    """使用n_n_battle为核心的变种函数"""

    def easy_battle(
            self, text_, stage_id, player, max_times,
            deck,
            battle_plan_1p, battle_plan_2p, dict_exit):
        """仅调用 n_battle"""
        # 战斗开始
        self.sin_out.emit(
            "\n[{}] {} Link Start!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

        quest_list = [
            {
                "stage_id": stage_id,
                "max_times": max_times,
                "deck": deck,
                "player": player,
                "battle_plan_1p": battle_plan_1p,
                "battle_plan_2p": battle_plan_2p,
                "quest_card": "None",
                "list_ban_card": [],
                "dict_exit": dict_exit
            }]
        self.n_n_battle(
            quest_list=quest_list,
            list_type=["NO", "OR", "CS", "EX", "MT"])

        # 战斗结束
        self.sin_out.emit(
            "[{}] {} Completed!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

    def double_offer_reward(
            self, text_, max_times,
            deck,
            battle_plan_1p, battle_plan_2p):

        self.sin_out.emit(
            "\n[{}] {}Link Start!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

        self.sin_out.emit(
            "[{}] {}开始[多本轮战]...".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

        quest_list = []
        for i in range(3):
            quest_list.append({
                "player": [2, 1],
                "deck": deck,
                "battle_plan_1p": battle_plan_1p,
                "battle_plan_2p": battle_plan_2p,
                "stage_id": "OR-" + str(i + 1) + "-0",
                "max_times": max_times,
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

        self.sin_out.emit(
            "[{}] {}Completed!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

    def alone_magic_tower_prison(
            self, text_, player,
            deck,
            battle_plan_1p, sutra_pavilion):

        self.sin_out.emit(
            "\n[{}] {} Link Start!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

        if sutra_pavilion:
            stage_list = ["MT-3-1", "MT-3-2", "MT-3-3", "MT-3-4"]
        else:
            stage_list = ["MT-3-1", "MT-3-3", "MT-3-4"]

        quest_list = []
        for stage in stage_list:
            quest_list.append(
                {
                    "player": player,
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

        self.sin_out.emit(
            "[{}] {} Completed!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

    def customize_todo(
            self, text_, customize_todo_index: int):

        def read_json_to_customize_todo():
            customize_todo_list = get_customize_todo_list(with_extension=True)
            customize_todo_path = "{}\\{}".format(
                paths["customize_todo"],
                customize_todo_list[customize_todo_index]
            )
            with open(customize_todo_path, "r", encoding="UTF-8") as file:
                return json.load(file)

        # 开始链接
        self.sin_out.emit(
            "[{}] {} Link Start!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

        # 战斗开始
        self.sin_out.emit(
            "[{}] {} 开始[多本论战]".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

        quest_list = read_json_to_customize_todo()

        self.n_n_battle(
            quest_list=quest_list,
            list_type=["NO", "EX", "CS"])

        # 战斗结束
        self.sin_out.emit(
            "[{}] {} Completed!".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                text_))

    """主要线程"""

    def run(self):

        self.sin_out.emit(
            "每一个大类的任务开始前均会重启游戏以防止bug...")
        start_time = datetime.datetime.now()

        need_reload = False
        need_reload = need_reload or self.opt["sign_in"]["active"]
        need_reload = need_reload or self.opt["fed_and_watered"]["active"]
        need_reload = need_reload or self.opt["normal_battle"]["active"]
        if need_reload:
            self.reload_game()

        my_opt = self.opt["sign_in"]
        if my_opt["active"]:
            self.sin_out.emit(
                "[{}] 每日签到检查中...".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            self.faa[1].sign_in()
            self.faa[2].sign_in()

        my_opt = self.opt["fed_and_watered"]
        if my_opt["active"]:
            self.sin_out.emit(
                "[{}] 公会浇水施肥摘果子中, 领取奖励需激活[公会任务], 否则只完成不领取奖励...".format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            self.faa[1].fed_and_watered()
            self.faa[2].fed_and_watered()

        my_opt = self.opt["normal_battle"]
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

        need_reload = False
        need_reload = need_reload or self.opt["quest_guild"]["active"]
        need_reload = need_reload or self.opt["quest_spouse"]["active"]
        need_reload = need_reload or self.opt["offer_reward"]["active"]
        if need_reload:
            self.reload_game()

        my_opt = self.opt["quest_guild"]
        if my_opt["active"]:
            self.guild_or_spouse_quest(
                text_="[公会任务]",
                quest_mode="公会任务",
                deck=my_opt["deck"],
                battle_plan_1p=my_opt["battle_plan_1p"],
                battle_plan_2p=my_opt["battle_plan_2p"])

        my_opt = self.opt["quest_spouse"]
        if my_opt["active"]:
            self.guild_or_spouse_quest(
                text_="[情侣任务]",
                quest_mode="情侣任务",
                deck=self.opt["quest_guild"]["deck"],
                battle_plan_1p=self.opt["quest_guild"]["battle_plan_1p"],
                battle_plan_2p=self.opt["quest_guild"]["battle_plan_2p"])

        my_opt = self.opt["offer_reward"]
        if my_opt["active"]:
            self.double_offer_reward(
                text_="[悬赏任务]",
                deck=my_opt["deck"],
                max_times=my_opt["max_times"],
                battle_plan_1p=my_opt["battle_plan_1p"],
                battle_plan_2p=my_opt["battle_plan_2p"])

        need_reload = False
        need_reload = need_reload or self.opt["relic"]["active"]
        need_reload = need_reload or self.opt["cross_server"]["active"]
        need_reload = need_reload or self.opt["warrior"]["active"]
        if need_reload:
            self.reload_game()

        my_opt = self.opt["relic"]
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

        my_opt = self.opt["cross_server"]
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

        my_opt = self.opt["warrior"]
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
        need_reload = need_reload or self.opt["magic_tower_alone_1"]["active"]
        need_reload = need_reload or self.opt["magic_tower_alone_2"]["active"]
        need_reload = need_reload or self.opt["magic_tower_prison_1"]["active"]
        need_reload = need_reload or self.opt["magic_tower_prison_2"]["active"]
        need_reload = need_reload or self.opt["magic_tower_double"]["active"]
        if need_reload:
            self.reload_game()

        for player_id in [1, 2]:
            my_opt = self.opt["magic_tower_alone_{}".format(player_id)]
            if my_opt["active"]:
                self.easy_battle(
                    text_="[魔塔单人_{}P]".format(player_id),
                    stage_id="MT-1-" + str(my_opt["stage"]),
                    player=[1] if player_id == 1 else [2],
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
            my_opt = self.opt["magic_tower_prison_{}".format(player_id)]
            if my_opt["active"]:
                self.alone_magic_tower_prison(
                    text_="[魔塔密室_{}P]".format(player_id),
                    player=[1] if player_id == 1 else [2],
                    deck=my_opt["deck"],
                    battle_plan_1p=my_opt["battle_plan_1p"],
                    sutra_pavilion=my_opt["stage"])

        my_opt = self.opt["magic_tower_double"]
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

        self.sin_out.emit(
            "[{}] 全部主要事项已完成! 耗时:{}".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                datetime.datetime.now() - start_time
            )
        )

        need_reload = False
        need_reload = need_reload or self.opt["receive_awards"]["active"]
        need_reload = need_reload or self.opt["use_items"]["active"]
        need_reload = need_reload or self.opt["cross_server_reputation"]["active"]
        need_reload = need_reload or self.opt["customize"]["active"]

        if need_reload:
            self.reload_game()

        if self.opt["receive_awards"]["active"]:
            self.receive_quest_rewards()

        if self.opt["use_items"]["active"]:
            self.use_items()

        if self.opt["cross_server_reputation"]["active"]:
            self.cross_server_reputation(deck=self.opt["quest_guild"]["deck"])

        my_opt = self.opt["customize_battle"]
        if my_opt["active"]:
            self.n_battle_customize(
                text_="[自建房战斗]",
                is_group=my_opt["is_group"],
                max_times=int(my_opt["max_times"]),
                deck=my_opt["deck"],
                battle_plan_1p=my_opt["battle_plan_1p"],
                battle_plan_2p=my_opt["battle_plan_2p"],

            )

        my_opt = self.opt["customize"]
        if my_opt["active"]:
            self.customize_todo(
                text_="[高级自定义]",
                customize_todo_index=my_opt["battle_plan_1p"])

        # 全部完成了刷新一下
        self.sin_out.emit(
            "\n[{}] 已完成所有事项, 刷新游戏回到登录界面, 防止长期运行flash导致卡顿".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.reload_to_login_ui()

        # 全部完成了发个信号
        self.sin_out_completed.emit()

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

    def __init__(self):
        # 继承父类构造方法
        super().__init__()
        self.thread_todo = None
        self.reply = None
        self.faa = [None, None, None]
        # 线程激活即为True
        self.thread_states = False

    def todo_completed(self):
        self.thread_states = False  # 设置flag
        self.Button_Start.setText("开始\nLink Start")  # 设置按钮文本
        # 设置输出文本
        self.printf("\n>>> 全任务完成 线程关闭 <<<\n")

    def todo_start(self):

        self.thread_states = True  # 设置flag
        self.Button_Start.setText("终止\nEnd")  # 设置按钮文本
        # 设置输出文本
        self.TextBrowser.clear()
        self.start_print()
        self.printf("\n>>> 链接开始 线程开启 <<<")

    def click_btn_start(self):
        """战斗开始函数"""
        # 线程没有激活
        if not self.thread_states:
            self.ui_to_opt()
            game_name = self.opt["game_name"]
            name_1p = self.opt["name_1p"]
            name_2p = self.opt["name_2p"]
            channel_1p, channel_2p = get_channel_name(game_name, name_1p, name_2p)

            # 把索引变值 需要注意的是 battle_plan均为索引 需要在FAA类中处理
            zoom_ratio = {
                0: 1.00,
                1: 1.25,
                2: 1.50,
                3: 1.75,
                4: 2.00,
                5: 2.25,
                6: 2.50}
            zoom_ratio = zoom_ratio[self.opt["zoom_ratio"]]

            faa = [None, None, None]
            faa[1] = FAA(
                channel=channel_1p,
                zoom=zoom_ratio,
                player=1,
                character_level=self.opt["level_1p"],
                is_use_key=True,  # boolean 是否使用钥匙 做任务必须选择 是
                is_auto_battle=self.opt["auto_use_card"],  # boolean 是否使用自动战斗 做任务必须选择 是
                is_auto_pickup=self.opt["auto_pickup_1p"])

            faa[2] = FAA(
                channel=channel_2p,
                zoom=zoom_ratio,
                player=2,
                character_level=self.opt["level_2p"],
                is_use_key=True,
                is_auto_battle=self.opt["auto_use_card"],
                is_auto_pickup=self.opt["auto_pickup_2p"])

            self.todo_start()

            self.thread_todo = Todo(faa=faa, opt=self.opt)
            # 绑定手动结束线程
            self.thread_todo.sin_out_completed.connect(self.todo_completed)
            # 绑定文本输出
            self.thread_todo.sin_out.connect(self.printf)
            # 开始线程
            self.thread_todo.start()

        else:
            """
            线程已经激活 则从外到内中断,再从内到外销毁
            thread_todo (QThread)
                |-- thread_1p (ThreadWithException)
                |-- thread_2p (ThreadWithException)
            """
            # 暂停外部线程
            self.thread_todo.pause()

            # 中断[内部战斗线程]
            for thread in [self.thread_todo.thread_1p, self.thread_todo.thread_2p]:
                if thread is not None:
                    thread.stop()
                    thread.join()  # 等待线程确实中断

            # 中断 销毁 [任务线程]
            self.thread_todo.terminate()
            self.thread_todo.wait()  # 等待线程确实中断
            self.thread_todo.deleteLater()

            # 结束线程后的ui处理
            self.todo_completed()


def main():
    # 实例化 PyQt后台管理
    app = QApplication(sys.argv)

    # 实例化 主窗口
    window = MyMainWindow2()

    # 注册函数：开始/结束按钮
    window.Button_Start.clicked.connect(lambda: window.click_btn_start())

    window.Button_Save.clicked.connect(lambda: window.click_btn_save())

    # 主窗口 实现
    window.show()

    # 运行主循环，必须调用此函数才可以开始事件处理
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
