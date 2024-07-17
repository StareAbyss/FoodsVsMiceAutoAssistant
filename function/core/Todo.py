import copy
import datetime
import json
import os
import time
from time import sleep

import requests
from PyQt5.QtCore import *
from requests import RequestException

from function.common.bg_img_match import loop_match_p_in_w
from function.common.thread_with_exception import ThreadWithException
from function.core.analyzer_of_loot_logs import update_dag_graph, find_longest_path_from_dag
from function.core_battle.CardManager import CardManager
from function.globals.extra import EXTRA_GLOBALS
from function.globals.get_paths import PATHS
from function.globals.init_resources import RESOURCE_P
from function.globals.log import CUS_LOGGER
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.get_customize_todo_list import get_customize_todo_list
from function.scattered.loots_and_chest_data_save_and_post import loots_and_chests_detail_to_json, \
    loots_and_chests_data_post_to_sever, loots_and_chests_statistics_to_json


class ThreadTodo(QThread):
    signal_start_todo_2_battle = pyqtSignal(dict)
    signal_todo_lock = pyqtSignal(bool)

    def __init__(self, faa, opt, running_todo_plan_index, signal_dict, todo_id):
        super().__init__()

        # 用于暂停恢复
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.is_paused = False

        # 功能需要
        self.faa = faa
        self.opt = copy.deepcopy(opt)  # 深拷贝 在作战中如果进行更改, 不会生效
        self.opt_todo_plans = self.opt["todo_plans"][running_todo_plan_index]  # 选择运行的 opt 的 todo plan 部分
        self.thread_1p = None
        self.thread_2p = None
        self.thread_card_manager = None
        self.card_manager = None
        self.battle_check_interval = 1  # 战斗线程中, 进行一次战斗结束和卡片状态检测的间隔, 其他动作的间隔与该时间成比例
        self.auto_food_stage_ban_list = []  # 用于防止缺乏钥匙/次数时无限重复某些关卡

        # 多人双线程相关
        self.my_lock = False  # 多人单线程的互锁, 需要彼此完成方可解除对方的锁
        self.todo_id = todo_id  # id == 1 默认 id==2 处理双单人多线程
        self.extra_opt = None  # 用来给双单人多线程的2P传递参数

        # 好用的信号~
        self.signal_dict = signal_dict
        self.signal_print_to_ui = self.signal_dict["print_to_ui"]
        self.signal_dialog = self.signal_dict["dialog"]
        self.signal_todo_end = self.signal_dict["end"]

    """非脚本操作的业务代码"""

    def model_start_print(self, text):
        # 在函数执行前发送的信号
        self.signal_print_to_ui.emit(text="", time=False)
        self.signal_print_to_ui.emit(text=f"[{text}] Link Start!", color="#C80000")

    def model_end_print(self, text):
        self.signal_print_to_ui.emit(text=f"[{text}] Completed!", color="#C80000")

    def change_lock(self, my_bool):
        self.my_lock = my_bool

    def set_is_used_key_true(self):
        """
        在作战时, 只要有任何一方 使用了钥匙, 都设置两个号在本场作战均是用了钥匙
        在战斗结束进行通报汇总分类 各个faa都依赖自身的该参数, 因此需要对两者都做更改
        此外, 双人双线程时, 有两个本线程的实例控制的均为同样的faa实例, 若一方用钥匙,另一方也会悲改为用, 但魔塔不会存在该问题, 故暂时不管.
        """

        self.faa[1].faa_battle.is_used_key = True
        self.faa[2].faa_battle.is_used_key = True

    def remove_outdated_log_images(self):
        self.signal_print_to_ui.emit("正在清理超过3天的log图片...")

        now = datetime.datetime.now()
        expiration_period = datetime.timedelta(days=3)
        deleted_files_count = 0

        directory_path = PATHS["logs"] + "\\loots_picture"
        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)
            file_mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

            if now - file_mod_time > expiration_period and filename.lower().endswith('.png'):
                os.remove(file_path)
                deleted_files_count += 1

        directory_path = PATHS["logs"] + "\\chests_picture"
        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)
            file_mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

            if now - file_mod_time > expiration_period and filename.lower().endswith('.png'):
                os.remove(file_path)
                deleted_files_count += 1

        self.signal_print_to_ui.emit(f"清理完成... {deleted_files_count}张图片已清理.")

    def cus_quit(self):
        CUS_LOGGER.debug("已激活ThreadTodo quit")
        self.quit()

    """业务代码 - 战斗以外"""

    def batch_level_2_action(self, title_text, is_group, dark_crystal=False):

        # 在该动作前已经完成了游戏刷新 可以尽可能保证欢乐互娱不作妖
        if self.opt["level_2"]["1p"]["active"] or self.opt["level_2"]["2p"]["active"]:
            self.signal_print_to_ui.emit(
                text=f"[{title_text}] [二级功能] 您输入二级激活了该功能. 将送免费花 + 兑换暗晶 + 删除多余技能书",
                color="E67800")

        # 高危动作 慢慢执行
        if self.opt["level_2"]["1p"]["active"]:
            self.faa[1].input_level_2_password_and_gift_flower(password=self.opt["level_2"]["1p"]["password"])
            self.faa[1].delete_items()
            if dark_crystal:
                self.faa[1].get_dark_crystal()

        if is_group and self.opt["level_2"]["2p"]["active"]:
            self.faa[2].input_level_2_password_and_gift_flower(password=self.opt["level_2"]["2p"]["password"])
            self.faa[2].delete_items()
            if dark_crystal:
                self.faa[2].get_dark_crystal()

        # 执行完毕后立刻刷新游戏 以清除二级输入状态
        if self.opt["level_2"]["1p"]["active"] or self.opt["level_2"]["2p"]["active"]:
            self.signal_print_to_ui.emit(
                text=f"[{title_text}] [二级功能] 结束, 即将刷新游戏以清除二级输入的状态...", color="E67800")
            self.batch_reload_game()

    def batch_reload_game(self):

        self.signal_print_to_ui.emit("Refresh Game...")

        CUS_LOGGER.debug("刷新两个游戏窗口 开始")

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

        CUS_LOGGER.debug("刷新两个游戏窗口 结束")

    def batch_click_refresh_btn(self):

        self.signal_print_to_ui.emit("Refresh Game...")

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].click_refresh_btn,
            name="1P Thread - Reload",
            kwargs={})

        self.thread_2p = ThreadWithException(
            target=self.faa[2].click_refresh_btn,
            name="2P Thread - Reload",
            kwargs={})
        self.thread_1p.start()
        self.thread_2p.start()
        self.thread_1p.join()
        self.thread_2p.join()

    def batch_sign_in(self, is_group):

        title_text = "每日签到"
        self.model_start_print(text=title_text)

        # 激活删除物品高危功能(可选) + 领取奖励一次
        self.batch_level_2_action(is_group=is_group, title_text=title_text, dark_crystal=False)

        # 领取温馨礼包
        for i in [1, 2]:
            if self.opt["get_warm_gift"][f'{i}p']["active"]:
                openid = self.opt["get_warm_gift"][f'{i}p']["link"]
                if openid == "":
                    continue
                url = 'http://meishi.wechat.123u.com/meishi/gift?openid=' + openid

                try:
                    r = requests.get(url, timeout=10)  # 设置超时
                    r.raise_for_status()  # 如果响应状态不是200，将抛出HTTPError异常
                    message = r.json()['msg']
                    self.signal_print_to_ui.emit(f'[{i}P] 领取温馨礼包情况:' + message, color="E67800")
                except RequestException as e:
                    # 这里处理请求发生的任何错误，如网络问题、超时、服务器无响应等
                    self.signal_print_to_ui.emit(f'[{i}P] 领取温馨礼包情况: 失败, 欢乐互娱的服务器炸了, {e}',
                                                 color="E67800")
            else:
                self.signal_print_to_ui.emit(f"[{i}P] 未激活领取温馨礼包", color="E67800")

        self.signal_print_to_ui.emit(f"开始 VIP签到/每日签到/美食活动/塔罗/法老/会长发任务/营地领钥匙")

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

        self.model_end_print(text=title_text)

    def batch_receive_all_quest_rewards(self, is_group):

        title_text = "领取奖励"
        self.model_start_print(text=title_text)

        """激活了删除物品高危功能"""
        self.batch_level_2_action(is_group=is_group, title_text=title_text, dark_crystal=True)

        """普通任务"""
        self.signal_print_to_ui.emit(text=f"[{title_text}] [普通任务] 开始...")

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].receive_quest_rewards,
            name="1P Thread - ReceiveQuest",
            kwargs={
                "mode": "普通任务"
            })

        if is_group:
            self.thread_2p = ThreadWithException(
                target=self.faa[2].receive_quest_rewards,
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

        self.signal_print_to_ui.emit(text=f"[{title_text}] [普通任务] 结束")

        """美食大赛"""

        self.signal_print_to_ui.emit(text=f"[{title_text}] [美食大赛] 开始...")

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].receive_quest_rewards,
            name="1P Thread - Quest",
            kwargs={
                "mode": "美食大赛"
            })

        self.thread_2p = ThreadWithException(
            target=self.faa[2].receive_quest_rewards,
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

        self.signal_print_to_ui.emit(text=f"[{title_text}] [美食大赛] 结束...")

        """大富翁"""
        self.signal_print_to_ui.emit(text=f"[{title_text}] [大富翁] 开始...")

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].receive_quest_rewards,
            name="1P Thread - Quest",
            kwargs={
                "mode": "大富翁"
            })

        self.thread_2p = ThreadWithException(
            target=self.faa[2].receive_quest_rewards,
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

        self.signal_print_to_ui.emit(text=f"[{title_text}] [大富翁] 结束...")

        self.model_end_print(text=title_text)

    def batch_use_items_consumables(self, is_group):

        title_text = "使用绑定消耗品"
        self.model_start_print(text=title_text)

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].use_items_consumables,
            name="1P Thread - UseItems",
            kwargs={})

        if is_group:
            self.thread_2p = ThreadWithException(
                target=self.faa[2].use_items_consumables,
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

        self.model_end_print(text=title_text)

    def batch_use_items_double_card(self, is_group, max_times):

        title_text = "使用双爆卡"
        self.model_start_print(text=title_text)

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa[1].use_items_double_card,
            name="1P Thread - UseItems",
            kwargs={"max_times": max_times})

        if is_group:
            self.thread_2p = ThreadWithException(
                target=self.faa[2].use_items_double_card,
                name="2P Thread - UseItems",
                kwargs={"max_times": max_times})

        # 涉及键盘抢夺, 容错低, 最好分开执行
        self.thread_1p.start()
        if is_group:
            sleep(0.333)
            self.thread_2p.start()
        self.thread_1p.join()
        if is_group:
            self.thread_2p.join()

        self.model_end_print(text=title_text)

    def batch_loop_cross_server(self, is_group, deck):

        title_text = "无限跨服刷威望"
        self.model_start_print(text=title_text)

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

    """业务代码 - 战斗相关"""

    def invite(self, player_a, player_b):
        """
        号1邀请号2到房间 需要在同一个区
        :return: bool 是否最终找到了图片
        """

        faa_a = self.faa[player_a]
        faa_b = self.faa[player_b]

        find = loop_match_p_in_w(
            source_handle=faa_a.handle,
            source_root_handle=faa_a.handle_360,
            source_range=[796, 413, 950, 485],
            template=RESOURCE_P["common"]["战斗"]["战斗前_开始按钮.png"],
            after_sleep=0.3,
            click=False,
            match_failed_check=2.0)
        if not find:
            CUS_LOGGER.warning("2s找不到开始游戏! 土豆服务器问题, 创建房间可能失败!")
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
                source_handle=faa_b.handle,
                source_root_handle=faa_a.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["战斗"]["战斗前_接受邀请.png"],
                after_sleep=2.0,
                match_failed_check=2.0
            )

            if not find:
                CUS_LOGGER.warning("2s没能组队? 土豆服务器问题, 尝试解决ing...")
                return False

            # p1关闭邀请窗口
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa_a.handle, x=590, y=491)
            time.sleep(1)

        return True

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
                    self.signal_print_to_ui.emit(text="[单本轮战] 邀请成功")
                    # 邀请成功 返回退出
                    return 0

                else:
                    failed_time += 1
                    mt_first_time = True

                    self.signal_print_to_ui.emit(text=f"[单本轮战] 服务器抽风,进入竞技岛重新邀请...({failed_time}/3)")

                    if failed_time == 3:
                        self.signal_print_to_ui.emit(text="[单本轮战] 服务器抽风过头, 刷新游戏!")
                        failed_round += 1
                        self.batch_reload_game()
                        break

                    faa_a.action_exit(mode="竞技岛")
                    faa_b.action_exit(mode="竞技岛")

            if failed_round == 3:
                self.signal_print_to_ui.emit(text=f"[单本轮战] 刷新游戏次数过多")
                return 2

    def battle(self, player_a, player_b):
        """
        从进入房间到回到房间的流程
        :param player_a: 玩家A
        :param player_b: 玩家B
        :return:
            int id 用于判定战斗是 成功 或某种原因的失败 1-成功 2-服务器卡顿,需要重来 3-玩家设置的次数不足,跳过;
            dict 包含player_a和player_b的[战利品]和[宝箱]识别到的情况;
            int 战斗消耗时间(秒);
        """

        is_group = self.faa[player_a].is_group
        result_id = 0
        result_loot = {}
        result_spend_time = 0

        """同时进行战前准备"""
        if result_id == 0:

            # 初始化多线程
            self.thread_1p = ThreadWithException(
                target=self.faa[player_a].battle_a_round_room_preparatory,
                name="{}P Thread - Battle - Before".format(player_a),
                kwargs={})
            if is_group:
                self.thread_2p = ThreadWithException(
                    target=self.faa[player_b].battle_a_round_room_preparatory,
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
                target=self.faa[player_a].battle_a_round_init_battle_plan,
                name="{}P Thread - Battle".format(player_a),
                kwargs={})
            if is_group:
                self.thread_2p = ThreadWithException(
                    target=self.faa[player_b].battle_a_round_init_battle_plan,
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

            # 实例化放卡管理器
            self.thread_card_manager = CardManager(
                faa_1=self.faa[player_a],
                faa_2=self.faa[player_b],
                round_interval=self.battle_check_interval
            )
            self.msleep(500)
            self.thread_card_manager.run()
            self.msleep(1000)

            # 绑定结束信号
            self.thread_card_manager.thread_dict[1].stop_signal.connect(self.cus_quit)
            self.thread_card_manager.thread_dict[1].stop_signal.connect(self.thread_card_manager.stop)

            # 绑定使用钥匙信号
            for i in [1, 2]:
                if i in self.thread_card_manager.thread_dict.keys():
                    self.thread_card_manager.thread_dict[i].used_key_signal.connect(self.set_is_used_key_true)

            CUS_LOGGER.debug('启动Todo中的事件循环, 用以战斗')
            self.exec_()

            # 此处的重新变为None是为了让中止todo实例时时该属性仍存在
            CUS_LOGGER.debug('销毁thread_card_manager的调用')
            self.thread_card_manager = None

            result_spend_time = time.time() - battle_start_time

        CUS_LOGGER.debug("战斗循环 已完成")

        """多线程进行战利品和宝箱检查 此处1p-ap 2p-bp"""

        if result_id == 0:

            # 初始化多线程
            self.thread_1p = ThreadWithException(
                target=self.faa[player_a].battle_a_round_loots,
                name="{}P Thread - Battle - Screen".format(player_a),
                kwargs={})
            if is_group:
                self.thread_2p = ThreadWithException(
                    target=self.faa[player_b].battle_a_round_loots,
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
            if result[1]:
                result_loot[player_a] = result[1]  # 可能是None 或 dict 故判空
            if is_group:
                result = self.thread_2p.get_return_value()
                result_id = max(result_id, result[0])
                if result[1]:
                    result_loot[player_b] = result[1]  # 可能是None 或 dict 故判空

            """构建有向无环图, 校验数据准确度, 并酌情发送至服务器和更新至Ranking"""
            # result_loot = {
            #   1:{"loots":{"物品":数量,...},"chests":{"物品":数量,...}} //数据 可能不存在 None
            #   2:{"loots":{"物品":数量,...},"chests":{"物品":数量,...}} //数据 可能不存在 None或不组队
            #   }
            update_dag_result_dict = False

            for player_index, player_data in result_loot.items():
                # 两种战利品的数据
                loots_dict = player_data["loots"]
                chests_dict = player_data["chests"]

                # 仅使用战利品更新item_dag_graph文件
                best_match_items_success = copy.deepcopy(list(player_data["loots"].keys()))
                # 不包含失败的识别
                if "识别失败" in best_match_items_success:
                    best_match_items_success.remove("识别失败")
                # 更新 item_dag_graph 文件
                update_dag_result = update_dag_graph(item_list_new=best_match_items_success)
                # 更新成功, 记录
                update_dag_result_dict = update_dag_result or update_dag_result_dict

                if update_dag_result:
                    CUS_LOGGER.debug(f"[战利品识别] [有向无环图] [更新] [{player_index}P] 成功! 成功构筑 DAG.")

                    # 保存详细数据到json
                    loots_and_chests_statistics_to_json(
                        faa=self.faa[player_index],
                        loots_dict=loots_dict,
                        chests_dict=chests_dict)
                    CUS_LOGGER.info(f"[战利品识别] [保存日志] [{player_index}P] 成功保存一条详细数据!")

                    # 保存汇总统计数据到json
                    detail_data = loots_and_chests_detail_to_json(
                        faa=self.faa[player_index],
                        loots_dict=loots_dict,
                        chests_dict=chests_dict)
                    CUS_LOGGER.info(f"[战利品识别] [保存日志] [{player_index}P] 成功保存至统计数据!")

                    # 发送到服务器
                    if loots_and_chests_data_post_to_sever(detail_data=detail_data):
                        CUS_LOGGER.info(f"[战利品识别] [发送服务器] [{player_index}P] 成功发送一条数据!")
                    else:
                        CUS_LOGGER.warning(f"[战利品识别] [发送服务器] [{player_index}P] 超时! 可能是服务器炸了...")

                else:
                    CUS_LOGGER.debug(
                        "[战利品识别] [有向无环图] [更新] [{player_index}P] 失败! 本次数据无法构筑 DAG，存在环.")

            if update_dag_result_dict:
                # 如果成功更新了 item_dag_graph.json, 更新ranking
                ranking_new = find_longest_path_from_dag()  # 成功返回更新后的 ranking 失败返回None
                if ranking_new:
                    CUS_LOGGER.info(
                        f"[根据有向无环图寻找最长链] item_ranking_dag_graph.json 已更新 , 结果:{ranking_new}")
                else:
                    CUS_LOGGER.warning(f"[根据有向无环图寻找最长链] item_ranking_dag_graph.json 更新失败!")
            else:
                CUS_LOGGER.warning(
                    f"[根据有向无环图寻找最长链] item_ranking_dag_graph.json 更新失败! 本次未获得任何有效数据!")

        CUS_LOGGER.debug("多线程进行战利品和宝箱检查 已完成")

        """分开进行战后检查"""
        if result_id == 0:
            result_id = self.faa[player_a].battle_a_round_warp_up()
            if is_group:
                result_id = self.faa[player_b].battle_a_round_warp_up()

        CUS_LOGGER.debug("战后检查完成 battle 函数执行结束")

        return result_id, result_loot, result_spend_time

    def n_battle_customize_battle_error_print(self, success_battle_time):
        # 结束提示文本
        self.signal_print_to_ui.emit(
            text=f"[单本轮战] 第{success_battle_time}次, 出现未知异常! 刷新后卡死, 以防止更多问题, 出现此问题可上报作者")
        self.batch_reload_game()
        sleep(60 * 60 * 24)

    def battle_1_1_n(self, stage_id, player, need_key, max_times, dict_exit,
                     deck, quest_card, ban_card_list, battle_plan_1p, battle_plan_2p, title_text, need_lock=False):
        """
        1轮次 1关卡 n次数
        副本外 -> (副本内战斗 * n次) -> 副本外
        player: [1], [2], [1,2], [2,1] 分别代表 1P单人 2P单人 1P队长 2P队长
        """

        # 组合完整的title
        title = f"[单本轮战] {title_text}"

        # 判断是不是打魔塔 或 自建房
        is_mt = "MT" in stage_id
        is_cu = "CU" in stage_id
        is_cs = "CS" in stage_id

        # 判断是不是组队
        is_group = len(player) > 1

        # 如果是多人跨服 防呆重写 2,1 为 1,2
        if is_cs and is_group:
            player = [1, 2]

        # 处理多人信息 (这些信息只影响函数内, 所以不判断是否组队)
        player_a = player[0]  # 房主 创建房间者
        player_b = 1 if player_a == 2 else 2  # 非房主
        faa_a, faa_b = self.faa[player_a], self.faa[player_b]
        battle_plan_a = battle_plan_1p if player_a == 1 else battle_plan_2p
        battle_plan_b = battle_plan_1p if player_b == 1 else battle_plan_2p

        def check_level_and_times():
            """
            检查人物等级和次数是否充足
            """
            if not faa_a.check_level():
                self.signal_print_to_ui.emit(text=f"{title}{player_a}P等级不足, 跳过")
                return False

            if is_group:
                if not faa_b.check_level():
                    self.signal_print_to_ui.emit(text=f"{title}{player_b}P等级不足, 跳过")
                    return False

            if max_times < 1:
                self.signal_print_to_ui.emit(text=f"{title}{stage_id} 设置次数不足 跳过")
                return False

            return True

        def multi_round_battle():
            # 标记是否需要进入副本
            need_goto_stage = not is_cu

            battle_count = 0  # 记录成功的次数
            result_list = []  # 记录成功场次的战斗结果记录

            # 轮次作战
            while battle_count < max_times:

                # 初始
                result_id = 0

                # 前往副本
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
                    battle_count += 1
                    # 进入异常, 跳过
                    need_goto_stage = True
                    # 结束提示文本
                    self.signal_print_to_ui.emit(text=f"{title}第{battle_count}次, 创建房间多次异常, 重启跳过")

                    self.batch_reload_game()

                self.signal_print_to_ui.emit(text=f"{title}第{battle_count + 1}次, 开始")

                # 开始战斗循环
                result_id, result_loot, result_spend_time = self.battle(player_a=player_a, player_b=player_b)

                if result_id == 0:

                    # 战斗成功 计数+1
                    battle_count += 1

                    # 计数战斗是否使用了钥匙, 由于一个号用过后两个号都会被修改为用过, 故不需要多余的判断
                    # this_battle_is_used_key = faa_a.faa_battle.is_used_key
                    # if is_group:
                    #     this_battle_is_used_key = this_battle_is_used_key or faa_b.faa_battle.is_used_key

                    if battle_count < max_times:
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

                    # 获取是否使用了钥匙 仅查看房主(任意一个号用了钥匙都会更改为两个号都用了)
                    is_used_key = faa_a.faa_battle.is_used_key

                    # 加入结果统计列表
                    result_list.append({
                        "time_spend": result_spend_time,
                        "is_used_key": is_used_key,
                        "loot_dict_list": result_loot  # result_loot_dict_list = [{a掉落}, {b掉落}]
                    })

                    # 时间
                    self.signal_print_to_ui.emit(
                        text="{}第{}次, {}, 正常结束, 耗时:{}分{}秒".format(
                            title,
                            battle_count,
                            "使用钥匙" if is_used_key else "未使用钥匙",
                            *divmod(int(result_spend_time), 60)
                        )
                    )

                    # 如果使用钥匙情况和要求不符, 加入美食大赛黑名单
                    if is_used_key == need_key:
                        CUS_LOGGER.debug(
                            f"{title}钥匙使用要求和实际情况一致~ 要求: {need_key}, 实际: {is_used_key}")
                    else:
                        CUS_LOGGER.debug(
                            f"{title}钥匙使用要求和实际情况不同! 要求: {need_key}, 实际: {is_used_key}")
                        self.auto_food_stage_ban_list.append(
                            {
                                "stage_id": stage_id,
                                "player": player,  # 1 单人 2 组队
                                "need_key": need_key,  # 注意类型转化
                                "max_times": max_times,
                                "quest_card": quest_card,
                                "ban_card_list": ban_card_list,
                                "dict_exit": dict_exit
                            }
                        )

                if result_id == 1:

                    if is_cu:
                        # 进入异常 但是自定义
                        self.n_battle_customize_battle_error_print(success_battle_time=battle_count)

                    else:
                        # 进入异常, 重启再来
                        need_goto_stage = True

                        # 结束提示文本
                        self.signal_print_to_ui.emit(text=f"{title}第{battle_count + 1}次, 异常结束, 重启再来")

                        if not need_lock:
                            # 非单人多线程
                            self.batch_reload_game()
                        else:
                            # 单人多线程 只reload自己
                            faa_a.reload_game()

                if result_id == 2:

                    if is_cu:
                        # 进入异常 但是自定义
                        self.n_battle_customize_battle_error_print(success_battle_time=battle_count)
                    else:
                        # 跳过本次 计数+1
                        battle_count += 1

                        # 进入异常, 跳过
                        need_goto_stage = True

                        # 结束提示文本
                        self.signal_print_to_ui.emit(text=f"{title}第{battle_count}次, 开始游戏异常, 重启跳过")

                        if not need_lock:
                            # 非单人多线程
                            self.batch_reload_game()
                        else:
                            # 单人多线程 只reload自己
                            faa_a.reload_game()

            return result_list

        def end_statistic_print(result_list):
            """
            结束后进行 本次 多本轮战的 战利品 统计和输出, 由于其统计为本次多本轮战, 故不能改变其位置
            """

            CUS_LOGGER.debug("result_list:")
            CUS_LOGGER.debug(str(result_list))

            valid_total_count = len(result_list)

            # 如果没有正常完成的场次, 直接跳过统计输出的部分
            if valid_total_count == 0:
                return

            # 时间
            sum_time_spend = 0
            count_used_key = 0

            for result in result_list:
                # 合计时间
                sum_time_spend += result["time_spend"]
                # 合计消耗钥匙的次数
                if result["is_used_key"]:
                    count_used_key += 1
            average_time_spend = sum_time_spend / valid_total_count

            self.signal_print_to_ui.emit(text="正常场次:{}次 使用钥匙:{}次 总耗时:{}分{}秒  场均耗时:{}分{}秒".format(
                valid_total_count,
                count_used_key,
                *divmod(int(sum_time_spend), 60),
                *divmod(int(average_time_spend), 60)
            ))

            if len(player) == 1:
                # 单人
                self.output_player_loot(player_id=player_a, result_list=result_list)
            else:
                # 多人
                self.output_player_loot(player_id=1, result_list=result_list)
                self.output_player_loot(player_id=2, result_list=result_list)

        def main():
            self.signal_print_to_ui.emit(text=f"{title}{stage_id} {max_times}次 开始", color="#0056A6")

            # 填入战斗方案和关卡信息, 之后会大量动作和更改类属性, 所以需要判断是否组队
            faa_a.set_config_for_battle(
                is_main=True,
                is_group=is_group,
                need_key=need_key,
                deck=deck,
                quest_card=quest_card,
                ban_card_list=ban_card_list,
                battle_plan_index=battle_plan_a,
                stage_id=stage_id)
            if is_group:
                faa_b.set_config_for_battle(
                    is_main=False,
                    is_group=is_group,
                    need_key=need_key,
                    deck=deck,
                    quest_card=quest_card,
                    ban_card_list=ban_card_list,
                    battle_plan_index=battle_plan_b,
                    stage_id=stage_id)

            if not check_level_and_times():
                return False

            # 进行 1本n次 返回 成功的每次战斗结果组成的list
            result_list = multi_round_battle()

            # 根据多次战斗结果组成的list 打印 1本n次 的汇总结果
            end_statistic_print(result_list=result_list)

            self.signal_print_to_ui.emit(text=f"{title}{stage_id} {max_times}次 结束 ", color="#0056A6")

        main()

    def output_player_loot(self, player_id, result_list):
        """
        打印玩家掉落信息

        :param player_id:  player_a, player_b int 1 2
        :param result_list: list, result of b
        :return:
        关于 result_list
        """
        valid_time = len(result_list)

        # 输入为
        count_loots_dict = {}
        count_chests_dict = {}

        # 复制key
        for result_ in result_list:
            loots = result_["loot_dict_list"][player_id]["loots"]
            if loots is not None:
                for key in loots.keys():
                    count_loots_dict[key] = 0
            chests = result_["loot_dict_list"][player_id]["chests"]
            if chests is not None:
                for key in chests.keys():
                    count_chests_dict[key] = 0

        # 累加数据
        for result_ in result_list:
            loots = result_["loot_dict_list"][player_id]["loots"]
            if loots is not None:
                for k, v in loots.items():
                    count_loots_dict[k] += v
            chests = result_["loot_dict_list"][player_id]["chests"]
            if chests is not None:
                for k, v in chests.items():
                    count_chests_dict[k] += v

        # 生成文本
        loots_text = ""
        chests_text = ""
        for name, count in count_loots_dict.items():
            loots_text += "{}x{:.1f}; ".format(name, count / valid_time)
        for name, count in count_chests_dict.items():
            chests_text += "{}x{:.1f}; ".format(name, count / valid_time)

        # 玩家A掉落
        self.signal_print_to_ui.emit(
            text="[{}P掉落/场]  {}".format(
                player_id,
                loots_text,
            ),
            time=False
        )
        self.signal_print_to_ui.emit(
            text="[{}P宝箱/场]  {}".format(
                player_id,
                chests_text
            ),
            time=False
        )

    def battle_1_n_n(self, quest_list, extra_title=None, need_lock=False):
        """
        1轮次 n关卡 n次数
        (副本外 -> (副本内战斗 * n次) -> 副本外) * 重复n次
        :param quest_list: 任务清单
        :param extra_title: 输出中的额外文本 会自动加上 [ ]
        :param need_lock:  用于多线程单人作战时设定为True 以进行上锁解锁
        """
        # 输出文本的title
        extra_title = f"[{extra_title}] " if extra_title else ""
        title = f"[多本轮战] {extra_title}"

        if need_lock:
            # 上锁
            self.signal_print_to_ui.emit(
                text=f"[双线程单人] {self.todo_id}P已开始任务! 进行自锁!",
                color="#006400")
            self.my_lock = True

        self.signal_print_to_ui.emit(text=f"{title}开始...", color="#006400")

        # 遍历完成每一个任务
        for i in range(len(quest_list)):

            quest = quest_list[i]

            # 判断显著错误的关卡名称
            if quest["stage_id"].split("-")[0] not in ["NO", "EX", "MT", "CS", "OR", "PT", "CU", "GD"]:
                self.signal_print_to_ui.emit(
                    text="{}事项{},{},错误的关卡名称!跳过".format(
                        title,
                        quest["battle_id"] if "battle_id" in quest else (i + 1),
                        quest["stage_id"]),
                    color="#C80000"
                )
                continue

            else:
                self.signal_print_to_ui.emit(
                    text="{}事项{}, 开始,{},{},{}次,带卡:{},Ban卡:{}".format(
                        title,
                        quest["battle_id"] if "battle_id" in quest else (i + 1),
                        "组队" if len(quest["player"]) == 2 else "单人",
                        quest["stage_id"],
                        quest["max_times"],
                        quest["quest_card"],
                        quest["ban_card_list"]
                    ),
                    color="#009688"
                )

                self.battle_1_1_n(
                    stage_id=quest["stage_id"],
                    max_times=quest["max_times"],
                    deck=quest["deck"],
                    player=quest["player"],
                    need_key=quest["need_key"],
                    battle_plan_1p=quest["battle_plan_1p"],
                    battle_plan_2p=quest["battle_plan_2p"],
                    quest_card=quest["quest_card"],
                    ban_card_list=quest["ban_card_list"],
                    dict_exit=quest["dict_exit"],
                    title_text=extra_title,
                    need_lock=need_lock
                )

                self.signal_print_to_ui.emit(
                    text="{}事项{}, 结束".format(
                        title,
                        quest["battle_id"] if "battle_id" in quest else (i + 1)
                    ),
                    color="#009688"
                )

        self.signal_print_to_ui.emit(text=f"{title}结束", color="#006400")

        if need_lock:
            self.signal_print_to_ui.emit(
                text=f"双线程单人功能中, {self.todo_id}P已完成所有任务! 已解锁另一线程!",
                color="#006400"
            )

            # 为另一个todo解锁
            self.signal_todo_lock.emit(False)
            # 如果自身是主线程, 且未被解锁, 循环等待
            if self.todo_id == 1:
                while self.my_lock:
                    sleep(1)

    """使用n_n_battle为核心的变种 [单线程][单人或双人]"""

    def easy_battle(self, text_, stage_id, player, max_times,
                    deck, battle_plan_1p, battle_plan_2p, dict_exit):
        """仅调用 n_battle的简易作战"""
        self.model_start_print(text=text_)

        quest_list = [
            {
                "stage_id": stage_id,
                "max_times": max_times,
                "player": player,
                "deck": deck,
                "need_key": True,
                "battle_plan_1p": battle_plan_1p,
                "battle_plan_2p": battle_plan_2p,
                "quest_card": "None",
                "ban_card_list": [],
                "dict_exit": dict_exit
            }]
        self.battle_1_n_n(quest_list=quest_list)

        self.model_end_print(text=text_)

    def offer_reward(self, text_, max_times_1, max_times_2, max_times_3,
                     deck, battle_plan_1p, battle_plan_2p):

        self.model_start_print(text=text_)

        self.signal_print_to_ui.emit(text=f"[{text_}] 开始[多本轮战]...")

        quest_list = []
        for i in range(3):
            quest_list.append({
                "deck": deck,
                "player": [2, 1],
                "need_key": True,
                "battle_plan_1p": battle_plan_1p,
                "battle_plan_2p": battle_plan_2p,
                "stage_id": "OR-0-" + str(i + 1),
                "max_times": [max_times_1, max_times_2, max_times_3][i],
                "quest_card": "None",
                "ban_card_list": [],
                "dict_exit": {
                    "other_time_player_a": [],
                    "other_time_player_b": [],
                    "last_time_player_a": ["竞技岛"],
                    "last_time_player_b": ["竞技岛"]}
            })
        self.battle_1_n_n(quest_list=quest_list)

        # 领取奖励
        self.faa[1].receive_quest_rewards(mode="悬赏任务")
        self.faa[2].receive_quest_rewards(mode="悬赏任务")

        self.model_end_print(text=text_)

    def guild_or_spouse_quest(self, title_text, quest_mode,
                              deck, battle_plan_1p, battle_plan_2p, stage=False):
        """完成公会or情侣任务"""

        self.model_start_print(text=title_text)

        # 激活删除物品高危功能(可选) + 领取奖励一次
        if quest_mode == "公会任务":
            self.batch_level_2_action(is_group=True, title_text=title_text, dark_crystal=False)
        self.signal_print_to_ui.emit(text=f"[{title_text}] 检查领取奖励...")
        self.faa[1].receive_quest_rewards(mode=quest_mode)
        self.faa[2].receive_quest_rewards(mode=quest_mode)

        # 获取任务
        self.signal_print_to_ui.emit(text=f"[{title_text}] 获取任务列表...")
        quest_list = self.faa[1].match_quests(mode=quest_mode, qg_cs=stage)
        for i in quest_list:
            self.signal_print_to_ui.emit(
                text="副本:{},额外带卡:{}".format(
                    i["stage_id"],
                    i["quest_card"]))
        for i in range(len(quest_list)):
            quest_list[i]["deck"] = deck
            quest_list[i]["battle_plan_1p"] = battle_plan_1p
            quest_list[i]["battle_plan_2p"] = battle_plan_2p

        # 完成任务
        self.battle_1_n_n(quest_list=quest_list)

        # 激活删除物品高危功能(可选) + 领取奖励一次
        if quest_mode == "公会任务":
            self.batch_level_2_action(is_group=True, title_text=title_text, dark_crystal=False)
        self.signal_print_to_ui.emit(text=f"[{title_text}] 检查领取奖励中...")
        self.faa[1].receive_quest_rewards(mode=quest_mode)
        self.faa[2].receive_quest_rewards(mode=quest_mode)

        self.model_end_print(text=title_text)

    def guild_dungeon(self, text_, deck, battle_plan_1p, battle_plan_2p):

        self.model_start_print(text=text_)

        self.signal_print_to_ui.emit(text=f"[{text_}] 开始[多本轮战]...")

        quest_list = []
        for i in range(3):
            quest_list.append({
                "deck": deck,
                "player": [2, 1],
                "need_key": True,
                "battle_plan_1p": battle_plan_1p,
                "battle_plan_2p": battle_plan_2p,
                "stage_id": "GD-0-" + str(i + 1),
                "max_times": 3,
                "quest_card": "None",
                "ban_card_list": [],
                "dict_exit": {
                    "other_time_player_a": [],
                    "other_time_player_b": [],
                    "last_time_player_a": ["竞技岛"],
                    "last_time_player_b": ["竞技岛"]}
            })
        self.battle_1_n_n(quest_list=quest_list)

        self.model_end_print(text=text_)

    def customize_todo(self, text_, stage_begin: int, customize_todo_index: int):

        def read_json_to_customize_todo():
            customize_todo_list = get_customize_todo_list(with_extension=True)
            customize_todo_path = "{}\\{}".format(
                PATHS["customize_todo"],
                customize_todo_list[customize_todo_index]
            )

            # 自旋锁读写, 防止多线程读写问题
            while EXTRA_GLOBALS.file_is_reading_or_writing:
                time.sleep(0.1)
            EXTRA_GLOBALS.file_is_reading_or_writing = True  # 文件被访问
            with open(file=customize_todo_path, mode="r", encoding="UTF-8") as file:
                data = json.load(file)
            EXTRA_GLOBALS.file_is_reading_or_writing = False  # 文件已解锁
            return data

        self.model_start_print(text=text_)

        # 战斗开始
        self.signal_print_to_ui.emit(text=f"[{text_}] 开始[多本论战]")

        # 读取json文件
        quest_list = read_json_to_customize_todo()

        # 获得最高方案的id
        max_battle_id = 1
        for quest in quest_list:
            max_battle_id = max(max_battle_id, quest["battle_id"])

        if stage_begin > max_battle_id:
            self.signal_print_to_ui.emit(text=f"[{text_}] 任务序号超过了该方案最高序号! 将直接跳过!")
            return

        # 由于任务id从1开始, 故需要减1
        # 去除序号小于stage_begin的任务
        my_list = []
        for quest in quest_list:
            if quest["battle_id"] >= stage_begin:
                my_list.append(quest)
        quest_list = my_list

        # 开始战斗
        self.battle_1_n_n(quest_list=quest_list)

        # 战斗结束
        self.model_end_print(text=text_)

    def auto_food(self, deck):

        def a_round():
            """
            一轮美食大赛战斗
            :return: 是否还有任务在美食大赛中
            """

            # 两个号分别读取任务
            quest_list_1 = self.faa[1].match_quests(mode="美食大赛")
            quest_list_2 = self.faa[2].match_quests(mode="美食大赛")
            quest_list = quest_list_1 + quest_list_2

            if not quest_list:
                return False

            # 去重
            unique_data = []
            for quest in quest_list:
                if quest not in unique_data:
                    unique_data.append(quest)
            quest_list = unique_data

            CUS_LOGGER.debug("[全自动大赛] 去重后任务列表如下:")
            CUS_LOGGER.debug(quest_list)

            # 去被ban的任务 一般是由于 需要使用钥匙但没有使用钥匙 或 没有某些关卡的次数 但尝试进入
            for quest in quest_list:
                if quest in self.auto_food_stage_ban_list:
                    CUS_LOGGER.debug(f"[全自动大赛] 该任务已经被ban, 故移出任务列表: {quest}")
                    quest_list.remove(quest)

            CUS_LOGGER.debug("[全自动大赛] 去Ban后任务列表如下:")
            CUS_LOGGER.debug(quest_list)

            self.signal_print_to_ui.emit(
                text="[全自动大赛] 已完成任务获取, 结果如下:",
                color="#006400"
            )

            for i in range(len(quest_list)):

                if len(quest_list[i]["player"]) == 2:
                    player_text = "组队"
                else:
                    player_text = "单人1P" if quest_list[i]["player"] == [1] else "单人2P"

                self.signal_print_to_ui.emit(
                    text="[全自动大赛] 事项{},{},{},{},{}次,带卡:{},Ban卡:{}".format(
                        i + 1,
                        player_text,
                        quest_list[i]["stage_id"],
                        "用钥匙" if quest_list[i]["stage_id"] else "无钥匙",
                        quest_list[i]["max_times"],
                        quest_list[i]["quest_card"],
                        quest_list[i]["ban_card_list"]),
                    color="#006400"
                )

            for i in range(len(quest_list)):
                quest_list[i]["deck"] = deck
                quest_list[i]["battle_plan_1p"] = 0
                quest_list[i]["battle_plan_2p"] = 1

            self.battle_1_n_n(quest_list=quest_list)

            return True

        def auto_food_main():
            text_ = "全自动大赛"
            self.model_start_print(text=text_)

            # 先领一下已经完成的大赛任务
            self.faa[1].receive_quest_rewards(mode="美食大赛")
            self.faa[2].receive_quest_rewards(mode="美食大赛")

            # 重置美食大赛任务 ban list
            self.auto_food_stage_ban_list = []  # 用于防止缺乏钥匙/次数时无限重复某些关卡

            i = 0
            while True:
                i += 1
                self.signal_print_to_ui.emit(text=f"[{text_}] 第{i}次循环，开始", color="#E67800")

                round_result = a_round()

                self.signal_print_to_ui.emit(text=f"[{text_}] 第{i}次循环，结束", color="#E67800")
                if not round_result:
                    break

            self.signal_print_to_ui.emit(text=f"[{text_}] 所有被记录的任务已完成!", color="#E67800")

            self.model_end_print(text=text_)

        auto_food_main()

    """使用n_n_battle为核心的变种 [双线程][单人]"""

    def alone_magic_tower(self):

        c_opt = self.opt_todo_plans

        def one_player():
            for player in [1, 2]:
                my_opt = c_opt[f"magic_tower_alone_{player}"]
                if my_opt["active"]:
                    self.easy_battle(
                        text_="[魔塔单人] [多线程{}P]".format(player),
                        stage_id="MT-1-" + str(my_opt["stage"]),
                        player=[player],
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

        def multi_player():
            quest_lists = {}
            for player in [1, 2]:
                my_opt = c_opt[f"magic_tower_alone_{player}"]
                quest_lists[player] = [
                    {
                        "player": [player],
                        "need_key": True,
                        "deck": my_opt["deck"],
                        "battle_plan_1p": my_opt["battle_plan_1p"],
                        "battle_plan_2p": my_opt["battle_plan_1p"],
                        "stage_id": "MT-1-" + str(my_opt["stage"]),
                        "max_times": int(my_opt["max_times"]),
                        "quest_card": "None",
                        "ban_card_list": [],
                        "dict_exit": {
                            "other_time_player_a": [],
                            "other_time_player_b": [],
                            "last_time_player_a": ["普通红叉"],
                            "last_time_player_b": []
                        }
                    }
                ]

            # 信号无法使用 具名参数
            self.signal_start_todo_2_battle.emit({
                "quest_list": quest_lists[2],
                "extra_title": "多线程单人2P",
                "need_lock": True
            })
            self.battle_1_n_n(
                quest_list=quest_lists[1],
                extra_title="多线程单人1P",
                need_lock=True)

        def main():
            text_ = "单人魔塔"
            # 计算需使用该功能的玩家数
            active_player_count = sum(c_opt[f"magic_tower_alone_{player_id}"]["active"] for player_id in [1, 2])
            if active_player_count == 1:
                # 单人情况 以easy battle 完成即可
                self.model_start_print(text=text_)
                one_player()
                self.model_end_print(text=text_)
            if active_player_count == 2:
                # 多人情况 直接调用以lock battle 完成1P 以信号调用另一个todo 完成2P
                self.model_start_print(text=text_)
                multi_player()
                self.model_end_print(text=text_)
                # 休息五秒, 防止1P后完成任务, 跨线程解锁2P需要一定时间, 却在1P线程中再次激发start2P线程, 导致2P线程瘫痪
                sleep(5)

        main()

    def alone_magic_tower_prison(self):

        c_opt = self.opt_todo_plans

        def one_player():
            for player in [1, 2]:
                my_opt = c_opt[f"magic_tower_prison_{player}"]
                if my_opt["stage"]:
                    stage_list = ["MT-3-1", "MT-3-2", "MT-3-3", "MT-3-4"]
                else:
                    stage_list = ["MT-3-1", "MT-3-3", "MT-3-4"]

                if my_opt["active"]:
                    quest_list = []
                    for stage in stage_list:
                        quest_list.append(
                            {
                                "player": [player],
                                "need_key": True,
                                "deck": my_opt["deck"],
                                "battle_plan_1p": my_opt["battle_plan_1p"],
                                "battle_plan_2p": my_opt["battle_plan_1p"],
                                "stage_id": stage,
                                "max_times": 1,
                                "quest_card": "None",
                                "ban_card_list": [],
                                "dict_exit": {
                                    "other_time_player_a": [],
                                    "other_time_player_b": [],
                                    "last_time_player_a": ["普通红叉"],
                                    "last_time_player_b": ["普通红叉"]
                                }
                            }
                        )
                    self.battle_1_n_n(quest_list=quest_list)

        def multi_player():
            quest_lists = {}
            for player in [1, 2]:
                my_opt = c_opt[f"magic_tower_prison_{player}"]
                if my_opt["stage"]:
                    stage_list = ["MT-3-1", "MT-3-2", "MT-3-3", "MT-3-4"]
                else:
                    stage_list = ["MT-3-1", "MT-3-3", "MT-3-4"]
                quest_lists[player] = []
                for stage in stage_list:
                    quest_lists[player].append(
                        {
                            "player": [player],
                            "need_key": False,
                            "deck": my_opt["deck"],
                            "battle_plan_1p": my_opt["battle_plan_1p"],
                            "battle_plan_2p": my_opt["battle_plan_1p"],
                            "stage_id": stage,
                            "max_times": 1,
                            "quest_card": "None",
                            "ban_card_list": [],
                            "dict_exit": {
                                "other_time_player_a": [],
                                "other_time_player_b": [],
                                "last_time_player_a": ["普通红叉"],
                                "last_time_player_b": ["普通红叉"]
                            }
                        }
                    )

            # 信号无法使用 具名参数
            self.signal_start_todo_2_battle.emit({
                "quest_list": quest_lists[2],
                "extra_title": "多线程单人2P",
                "need_lock": True})
            self.battle_1_n_n(
                quest_list=quest_lists[1],
                extra_title="多线程单人1P",
                need_lock=True)

        def main():
            text_ = "魔塔密室"
            # 计算需使用该功能的玩家数
            active_player_count = sum(c_opt[f"magic_tower_prison_{player_id}"]["active"] for player_id in [1, 2])
            if active_player_count == 1:
                # 单人情况 以easy battle 完成即可
                self.model_start_print(text=text_)
                one_player()
                self.model_end_print(text=text_)
            if active_player_count == 2:
                # 多人情况 直接调用以lock battle 完成1P 以信号调用另一个todo 完成2P
                self.model_start_print(text=text_)
                multi_player()
                self.model_end_print(text=text_)
                # 休息五秒, 防止1P后完成任务, 跨线程解锁2P需要一定时间, 却在1P线程中再次激发start2P线程, 导致2P线程瘫痪
                sleep(5)

        main()

    def pet_temple(self):

        c_opt = self.opt_todo_plans

        def one_player():
            for player in [1, 2]:
                my_opt = c_opt[f"pet_temple_{player}"]
                if my_opt["active"]:
                    self.easy_battle(
                        text_=f"[萌宠神殿] [{player}P]",
                        stage_id="PT-0-" + str(my_opt["stage"]),
                        player=[player],
                        max_times=1,
                        deck=my_opt["deck"],
                        battle_plan_1p=my_opt["battle_plan_1p"],
                        battle_plan_2p=my_opt["battle_plan_1p"],
                        dict_exit={
                            "other_time_player_a": [],
                            "other_time_player_b": [],
                            "last_time_player_a": [],  # "回到上一级","普通红叉" 但之后刷新 所以空
                            "last_time_player_b": []
                        }
                    )

        def multi_player():
            quest_lists = {}
            for player in [1, 2]:
                my_opt = c_opt[f"pet_temple_{player}"]
                quest_lists[player] = [
                    {
                        "player": [player],
                        "need_key": True,
                        "deck": my_opt["deck"],
                        "battle_plan_1p": my_opt["battle_plan_1p"],
                        "battle_plan_2p": my_opt["battle_plan_1p"],
                        "stage_id": "PT-0-" + str(my_opt["stage"]),
                        "max_times": 1,
                        "quest_card": "None",
                        "ban_card_list": [],
                        "dict_exit": {
                            "other_time_player_a": [],
                            "other_time_player_b": [],
                            "last_time_player_a": [],  # "回到上一级","普通红叉" 但之后刷新 所以空
                            "last_time_player_b": []
                        }
                    }
                ]

            # 信号无法使用 具名参数
            self.signal_start_todo_2_battle.emit({
                "quest_list": quest_lists[2],
                "extra_title": "多线程单人2P",
                "need_lock": True
            })
            self.battle_1_n_n(
                quest_list=quest_lists[1],
                extra_title="多线程单人1P",
                need_lock=True)

        def main():
            text_ = "萌宠神殿"
            active_player_count = 0
            for player_id in [1, 2]:
                my_opt = c_opt[f"pet_temple_{player_id}"]
                if my_opt["active"]:
                    active_player_count += 1
            if active_player_count == 1:
                # 单人情况 以easy battle 完成即可
                self.model_start_print(text=text_)
                one_player()
                self.model_end_print(text=text_)
            if active_player_count == 2:
                # 多人情况 直接调用以lock battle 完成1P 以信号调用另一个todo 完成2P
                self.model_start_print(text=text_)
                multi_player()
                self.model_end_print(text=text_)
                # 休息五秒, 防止1P后完成任务, 跨线程解锁2P需要一定时间, 却在1P线程中再次激发start2P线程, 导致2P线程瘫痪
                sleep(5)

        main()

    """主要线程"""

    def set_extra_opt_and_start(self, extra_opt):
        self.extra_opt = extra_opt
        self.start()

    def run(self):
        if self.todo_id == 1:
            self.run_1()
        if self.todo_id == 2:
            self.run_2()

    def run_1(self):

        # current todo plan option
        c_opt = self.opt_todo_plans

        start_time = datetime.datetime.now()

        self.signal_print_to_ui.emit("每一个大类的任务开始前均会重启游戏以防止bug...")

        if self.opt["advanced_settings"]["auto_delete_old_images"]:
            self.remove_outdated_log_images()

        need_reload = False
        need_reload = need_reload or c_opt["sign_in"]["active"]
        need_reload = need_reload or c_opt["fed_and_watered"]["active"]
        need_reload = need_reload or c_opt["use_double_card"]["active"]
        need_reload = need_reload or c_opt["warrior"]["active"]
        if need_reload:
            self.batch_reload_game()

        my_opt = c_opt["sign_in"]
        if my_opt["active"]:
            self.batch_sign_in(
                is_group=my_opt["is_group"]
            )

        my_opt = c_opt["fed_and_watered"]
        if my_opt["active"]:
            self.faa[1].fed_and_watered()
            if my_opt["is_group"]:
                self.faa[2].fed_and_watered()

        my_opt = c_opt["use_double_card"]
        if my_opt["active"]:
            self.batch_use_items_double_card(
                max_times=my_opt["max_times"],
                is_group=my_opt["is_group"]
            )

        my_opt = c_opt["warrior"]
        if my_opt["active"]:
            self.easy_battle(
                text_="勇士挑战",
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
            self.batch_reload_game()

        my_opt = c_opt["normal_battle"]
        if my_opt["active"]:
            self.easy_battle(
                text_="常规刷本",
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
                text_="悬赏任务",
                deck=my_opt["deck"],
                max_times_1=my_opt["max_times_1"],
                max_times_2=my_opt["max_times_2"],
                max_times_3=my_opt["max_times_3"],
                battle_plan_1p=my_opt["battle_plan_1p"],
                battle_plan_2p=my_opt["battle_plan_2p"])

        my_opt = c_opt["cross_server"]
        if my_opt["active"]:
            self.easy_battle(
                text_="跨服副本",
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
            self.batch_reload_game()

        my_opt = c_opt["quest_guild"]
        if my_opt["active"]:
            self.guild_or_spouse_quest(
                title_text="公会任务",
                quest_mode="公会任务",
                deck=my_opt["deck"],
                battle_plan_1p=my_opt["battle_plan_1p"],
                battle_plan_2p=my_opt["battle_plan_2p"],
                stage=my_opt["stage"])

        my_opt = c_opt["guild_dungeon"]
        if my_opt["active"]:
            self.guild_dungeon(
                text_="公会副本",
                deck=c_opt["quest_guild"]["deck"],
                battle_plan_1p=c_opt["quest_guild"]["battle_plan_1p"],
                battle_plan_2p=c_opt["quest_guild"]["battle_plan_2p"])

        my_opt = c_opt["quest_spouse"]
        if my_opt["active"]:
            self.guild_or_spouse_quest(
                title_text="情侣任务",
                quest_mode="情侣任务",
                deck=c_opt["quest_guild"]["deck"],
                battle_plan_1p=c_opt["quest_guild"]["battle_plan_1p"],
                battle_plan_2p=c_opt["quest_guild"]["battle_plan_2p"])

        my_opt = c_opt["relic"]
        if my_opt["active"]:
            self.easy_battle(
                text_="火山遗迹",
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
            self.batch_reload_game()

        self.alone_magic_tower()

        self.alone_magic_tower_prison()

        my_opt = c_opt["magic_tower_double"]
        if my_opt["active"]:
            self.easy_battle(
                text_="魔塔双人",
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

        self.pet_temple()

        self.signal_print_to_ui.emit(text=f"全部主要事项已完成! 耗时:{datetime.datetime.now() - start_time}")

        need_reload = False
        need_reload = need_reload or c_opt["receive_awards"]["active"]
        need_reload = need_reload or c_opt["use_items"]["active"]
        need_reload = need_reload or c_opt["loop_cross_server"]["active"]
        need_reload = need_reload or c_opt["customize"]["active"]
        need_reload = need_reload or c_opt["auto_food"]["active"]

        if need_reload:
            self.batch_reload_game()

        my_opt = c_opt["receive_awards"]
        if my_opt["active"]:
            self.batch_receive_all_quest_rewards(
                is_group=my_opt["is_group"]
            )

        my_opt = c_opt["use_items"]
        if my_opt["active"]:
            self.batch_use_items_consumables(
                is_group=my_opt["is_group"])

        my_opt = c_opt["loop_cross_server"]
        if my_opt["active"]:
            self.batch_loop_cross_server(
                is_group=my_opt["is_group"],
                deck=c_opt["quest_guild"]["deck"])

        my_opt = c_opt["customize_battle"]
        if my_opt["active"]:
            self.easy_battle(
                text_="自建房战斗",
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
                text_="高级自定义",
                stage_begin=my_opt["stage"],
                customize_todo_index=my_opt["battle_plan_1p"])

        my_opt = c_opt["auto_food"]
        if my_opt["active"]:
            self.auto_food(
                deck=my_opt["deck"],
            )

        if self.opt["advanced_settings"]["end_exit_game"]:
            self.signal_print_to_ui.emit(text="已完成所有额外事项！及将刷新游戏")
            self.batch_click_refresh_btn()
        else:
            self.signal_print_to_ui.emit(
                text="已完成所有额外事项！推荐勾选高级设置-完成后刷新游戏, 防止长期运行flash导致卡顿")

        # 全部完成了发个信号
        self.signal_todo_end.emit()

    def run_2(self):
        self.battle_1_n_n(
            quest_list=self.extra_opt["quest_list"],
            extra_title=self.extra_opt["extra_title"],
            need_lock=self.extra_opt["need_lock"])
        self.extra_opt = None

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
