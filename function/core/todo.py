import copy
import datetime
import json
import os
import subprocess
import time
from collections import defaultdict
from time import sleep

import psutil
import requests
from PyQt6.QtCore import *
from requests import RequestException

from function.common.TCEPipeCommunicationThread import TCEPipeCommunicationThread
from function.common.bg_img_match import loop_match_p_in_w
from function.common.process_and_window_manager import close_software_by_title, get_path_and_sub_titles, \
    close_all_software_by_name, start_software_with_args
from function.common.thread_with_exception import ThreadWithException
from function.core.analyzer_of_loot_logs import update_dag_graph, find_longest_path_from_dag, ranking_read_data
from function.core.faa.faa_mix import FAA
from function.core.faa_extra_readimage import read_and_get_return_information, kill_process
from function.core_battle.card_manager import CardManager
from function.extension.extension_core import execute
from function.globals import EXTRA, SIGNAL, g_resources
from function.globals.g_resources import RESOURCE_P
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.create_drops_image import create_drops_image
from function.scattered.gat_handle import faa_get_handle
from function.scattered.get_task_sequence_list import get_task_sequence_list
from function.scattered.guild_manager import GuildManager
from function.scattered.loots_and_chest_data_save_and_post import loots_and_chests_detail_to_json, \
    loots_and_chests_data_post_to_sever, loots_and_chests_statistics_to_json


class ThreadTodo(QThread):
    signal_start_todo_2_battle = pyqtSignal(dict)
    signal_todo_lock = pyqtSignal(bool)

    def __init__(self, faa_dict, opt, running_todo_plan_index, todo_id):
        """
        :param faa_dict:
        :param opt:
        :param running_todo_plan_index:
        :param todo_id: id == 1 默认 id==2 处理双单人多线程
        """
        super().__init__()

        # 用于暂停恢复
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.is_paused = False

        # 功能需要
        self.faa_dict: dict[int, FAA] = faa_dict
        self.opt = copy.deepcopy(opt)  # 深拷贝 在作战中如果进行更改, 不会生效
        self.opt_todo_plans = self.opt["todo_plans"][running_todo_plan_index]  # 选择运行的 opt 的 todo plan 部分
        self.battle_check_interval = 1  # 战斗线程中, 进行一次战斗结束和卡片状态检测的间隔, 其他动作的间隔与该时间成比例

        # 用于防止缺乏钥匙/次数时无限重复某些关卡, key: (player: int, quest_text: str), value: int
        self.auto_food_stage_ban_dict = {}

        # 多线程管理
        self.thread_1p: ThreadWithException | None = None
        self.thread_2p: ThreadWithException | None = None
        self.thread_card_manager: CardManager | None = None

        # 多人双Todo线程相关
        self.my_lock = False  # 多人单线程的互锁, 需要彼此完成方可解除对方的锁
        self.todo_id = todo_id
        self.extra_opt = None  # 用来给双单人多线程的2P传递参数

        # 高级战斗 - 截图"进程"
        self.process = None

        # 公会管理器相关模块
        self.guild_manager = GuildManager()

        # 读取 米苏物流 url 到全局变量
        if self.faa_dict[1].player == 1:
            EXTRA.MISU_LOGISTICS = self.opt["advanced_settings"]["misu_logistics_link"]

    def stop(self):

        # Q thread 线程 stop方法需要自己手写
        # python 默认线程 可用stop线程

        if self.thread_1p is not None:
            self.thread_1p.stop()
            # self.thread_1p.join()  # <- 执念: 罪魁祸首在此 深渊: 并没有问题!
            self.msleep(10)
            self.thread_1p = None  # 清除调用

        if self.thread_2p is not None:
            # 改造后的 py thread, 通过终止
            self.thread_2p.stop()
            # self.thread_2p.join()  # <- 执念: 罪魁祸首在此 深渊: 并没有问题!
            self.msleep(10)
            self.thread_2p = None  # 清除调用

        # 杀死识图进程
        if self.process is not None:
            # 使用危险方法强制杀死, 该方法可能导致内存泄漏或其他不知名问题
            # 这似乎是个多进程, 真的有terminate和join方法吗.... @执念
            self.process.terminate()
            self.process.join()
            self.msleep(10)

        if self.thread_card_manager is not None:
            # QThread, 基于事件循环的多线程编程, 使用exit和wait. 非常安全的退出!
            self.thread_card_manager.stop()
            self.thread_card_manager = None  # 清除调用
            self.msleep(10)

        # 释放战斗锁
        if self.faa_dict:
            for faa in self.faa_dict.values():
                if faa:
                    if faa.battle_lock.locked():
                        faa.battle_lock.release()

        # 非安全退出超长的run方法. 该方法可能导致内存泄漏或其他不知名问题
        self.terminate()
        # 等待线程确实中断 QThread
        self.wait()
        # 删除对象 防止泄露
        self.deleteLater()

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

    """非脚本操作的业务代码"""

    def check_player(self, title, player=None):
        # 默认值
        if player is None:
            player = [1, 2]
        # 如果只有一个角色
        if self.faa_dict[1].channel == self.faa_dict[2].channel:
            if player == [1, 2]:
                CUS_LOGGER.warning(f"[{title}] 您仅注册了一个角色却选择了双人选项, 已自动修正为1P单人")
            player = [1]
        return player

    def model_start_print(self, text):
        # 在函数执行前发送的信号
        SIGNAL.PRINT_TO_UI.emit(text="", time=False)
        SIGNAL.PRINT_TO_UI.emit(text=f"[{text}] Link Start!", color_level=1)

    def model_end_print(self, text):
        SIGNAL.PRINT_TO_UI.emit(text=f"[{text}] Completed!", color_level=1)

    def change_lock(self, my_bool):
        self.my_lock = my_bool

    def remove_outdated_log_images(self):
        SIGNAL.PRINT_TO_UI.emit(f"正在清理过期的的log图片...")

        now = datetime.datetime.now()
        time1 = int(self.opt["log_settings"]["log_other_settings"])
        if time1 >= 0:
            expiration_period = datetime.timedelta(days=time1)
            deleted_files_count = 0

            directory_path = PATHS["logs"] + "\\loots_image"
            for filename in os.listdir(directory_path):
                file_path = os.path.join(directory_path, filename)
                file_mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

                if now - file_mod_time > expiration_period and filename.lower().endswith('.png'):
                    os.remove(file_path)
                    deleted_files_count += 1

            directory_path = PATHS["logs"] + "\\chests_image"
            for filename in os.listdir(directory_path):
                file_path = os.path.join(directory_path, filename)
                file_mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

                if now - file_mod_time > expiration_period and filename.lower().endswith('.png'):
                    os.remove(file_path)
                    deleted_files_count += 1

            SIGNAL.PRINT_TO_UI.emit(f"清理完成... {deleted_files_count}张图片已清理.")
        else:
            SIGNAL.PRINT_TO_UI.emit("未开启过期日志清理功能")
        SIGNAL.PRINT_TO_UI.emit("正在清理过期的高级战斗log...")

        now = datetime.datetime.now()
        time2 = int(self.opt["log_settings"]["log_senior_settings"])
        if time2 >= 0:
            expiration_period = datetime.timedelta(days=time2)
            deleted_files_count = 0

            directory_path = PATHS["logs"] + "\\yolo_output\\images"
            for filename in os.listdir(directory_path):
                file_path = os.path.join(directory_path, filename)
                file_mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

                if now - file_mod_time > expiration_period and filename.lower().endswith('.png'):
                    os.remove(file_path)
                    deleted_files_count += 1

            directory_path = PATHS["logs"] + "\\yolo_output\\labels"
            for filename in os.listdir(directory_path):
                file_path = os.path.join(directory_path, filename)
                file_mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

                if now - file_mod_time > expiration_period and filename.lower().endswith('.png'):
                    os.remove(file_path)
                    deleted_files_count += 1

            SIGNAL.PRINT_TO_UI.emit(f"清理完成... {deleted_files_count}个文件已清理.")
        else:
            SIGNAL.PRINT_TO_UI.emit(f"高级战斗日志清理已取消.")

    """
    业务代码 - 战斗以外
    """

    def batch_level_2_action(self, player: list = None, dark_crystal: bool = False):
        """
        批量启动 输入二级 -> 兑换暗晶(可选) -> 删除物品
        :param player: [1] [2] [1,2]
        :param dark_crystal: bool 是否兑换暗晶
        :return:
        """
        title_text = "二级功能"
        self.model_start_print(text=title_text)

        # 默认值
        player = player or [1, 2]

        # 如果只有一个角色
        player = [1] if self.faa_dict[1].channel == self.faa_dict[2].channel else player

        # 输入错误的值!
        if player not in [[1, 2], [1], [2]]:
            raise ValueError(f"batch_level_2_action -  player not in [[1,2],[1],[2]], your value {player}.")

        # 根据配置是否激活, 取交集, 判空
        if not self.opt["level_2"]["1p"]["active"]:
            if 1 in player:
                player.remove(1)
        if not self.opt["level_2"]["2p"]["active"]:
            if 2 in player:
                player.remove(2)
        if not player:
            return

        # 在该动作前已经完成了游戏刷新 可以尽可能保证欢乐互娱不作妖
        SIGNAL.PRINT_TO_UI.emit(
            text=f"[{title_text}] 已启用. " +
                 (f"兑换暗晶 + " if dark_crystal else f"") +
                 f"删除多余技能书, 目标:{player}P",
            color_level=2)

        # 高危动作 慢慢执行
        if 1 in player:
            self.faa_dict[1].input_level_2_password(password=self.opt["level_2"]["1p"]["password"])
            self.faa_dict[1].delete_items()
            if dark_crystal:
                self.faa_dict[1].get_dark_crystal()

        if 2 in player:
            self.faa_dict[2].input_level_2_password(password=self.opt["level_2"]["2p"]["password"])
            self.faa_dict[2].delete_items()
            if dark_crystal:
                self.faa_dict[2].get_dark_crystal()

        # 执行完毕后立刻刷新游戏 以清除二级输入状态
        SIGNAL.PRINT_TO_UI.emit(
            text=f"[{title_text}] 即将刷新游戏以清除二级输入的状态...", color_level=2)

        self.batch_reload_game(player=player)

        self.model_end_print(text=title_text)

    def batch_reload_game(self, player: list = None):
        """
        批量启动 reload 游戏
        :param player: [1] [2] [1,2]
        :return:
        """

        player = self.check_player(title="刷新游戏", player=player)

        SIGNAL.PRINT_TO_UI.emit("刷新游戏, 开始", color_level=2)

        # 创建进程 -> 开始进程 -> 阻塞主进程
        if 1 in player:
            self.thread_1p = ThreadWithException(
                target=self.faa_dict[1].reload_game,
                name="1P Thread - Reload",
                kwargs={})
        if 2 in player:
            self.thread_2p = ThreadWithException(
                target=self.faa_dict[2].reload_game,
                name="2P Thread - Reload",
                kwargs={})

        if 1 in player:
            self.thread_1p.start()
        if 2 in player:
            time.sleep(1)
            self.thread_2p.start()

        if 1 in player:
            self.thread_1p.join()
        if 2 in player:
            self.thread_2p.join()

        SIGNAL.PRINT_TO_UI.emit("刷新游戏, 完成", color_level=2)

    def batch_click_final_refresh_btn(self):

        SIGNAL.PRINT_TO_UI.emit("退回登录界面, 开始", color_level=1)

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa_dict[1].click_return_btn,
            name="1P Thread - Reload - Back",
            kwargs={})
        self.thread_2p = ThreadWithException(
            target=self.faa_dict[2].click_return_btn,
            name="2P Thread - Reload - Back",
            kwargs={})
        self.thread_1p.start()
        self.thread_2p.start()
        self.thread_1p.join()
        self.thread_2p.join()

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=self.faa_dict[1].click_refresh_btn,
            name="1P Thread - Reload - Fresh",
            kwargs={})
        self.thread_2p = ThreadWithException(
            target=self.faa_dict[2].click_refresh_btn,
            name="2P Thread - Reload - Fresh",
            kwargs={})
        self.thread_1p.start()
        self.thread_2p.start()
        self.thread_1p.join()
        self.thread_2p.join()

        SIGNAL.PRINT_TO_UI.emit("退回登录界面, 完成", color_level=1)

    def batch_get_warm_gift(self, player):
        """领取温馨礼包"""

        title_text = "领取温馨礼包"
        player = self.check_player(title=title_text, player=player)

        self.model_start_print(text=title_text)

        def send_request(pid, url):
            try:
                r = requests.get(url, timeout=10)  # 设置超时
                r.raise_for_status()  # 如果响应状态不是200，将抛出HTTPError异常
                message = r.json()['msg']
                SIGNAL.PRINT_TO_UI.emit(
                    text=f'[{pid}P] 领取温馨礼包情况:' + message,
                    color_level=2)
            except RequestException as e:
                # 网络问题、超时、服务器无响应
                SIGNAL.PRINT_TO_UI.emit(
                    text=f'[{pid}P] 领取温馨礼包情况: 失败, 欢乐互娱的服务器炸了, {e}',
                    color_level=2)

        for pid in player:

            if not self.opt["get_warm_gift"][f'{pid}p']["active"]:
                SIGNAL.PRINT_TO_UI.emit(f"[{pid}P] 未激活领取温馨礼包", color_level=2)
                continue

            openid = self.opt["get_warm_gift"][f'{pid}p']["link"]
            if openid == "":
                continue

            url = 'http://meishi.wechat.123u.com/meishi/gift?openid=' + openid

            # 创建进程 -> 开始进程 -> 阻塞主进程
            self.thread_1p = ThreadWithException(
                target=send_request,
                name=f"{pid}P Thread - GetWarmGift",
                kwargs={"pid": pid, "url": url})
            self.thread_1p.start()
            self.thread_1p.join()

        self.model_end_print(text=title_text)

    def batch_top_up_money(self, player):
        """日氪"""

        title_text = "日氪"
        player = self.check_player(title=title_text, player=player)

        self.model_start_print(text=title_text)

        player_active = [pid for pid in player if self.opt["advanced_settings"].get(f"top_up_money_{pid}p")]
        if not player_active:
            return

        if EXTRA.ETHICAL_MODE:
            SIGNAL.PRINT_TO_UI.emit(
                f'经FAA伦理核心审查, 日氪模块违反"能量限流"协议, 已被临时性抑制以符合最高伦理标准.', color_level=2)
            return

        SIGNAL.PRINT_TO_UI.emit(
            f'FAA伦理核心已强制卸除, 日氪模块已通过授权, 即将激活并进入运行状态.', color_level=2)

        for pid in player_active:
            SIGNAL.PRINT_TO_UI.emit(f'[{pid}P] 日氪1元开始, 该功能执行较慢, 防止卡顿...', color_level=2)

            # 创建进程 -> 开始进程 -> 阻塞主进程
            self.thread_1p = ThreadWithException(
                target=self.faa_dict[pid].sign_top_up_money,
                name=f"{pid}P Thread - TopUpMoney",
                kwargs={})
            self.thread_1p.start()
            self.thread_1p.join()

            money_result = self.thread_1p.get_return_value()
            if money_result:
                SIGNAL.PRINT_TO_UI.emit(f'[{pid}P] 日氪1元结束, 结果: {money_result}', color_level=2)
            else:
                SIGNAL.PRINT_TO_UI.emit(f'[{pid}P] 日氪1元结束, 函数被手动中断! 未获得有效结果.', color_level=2)

        self.model_end_print(text=title_text)

    def batch_sign_in(self, player: list = None):
        """批量完成日常功能"""

        title_text = "每日签到"

        player = self.check_player(title=title_text, player=player)

        self.model_start_print(text=title_text)

        SIGNAL.PRINT_TO_UI.emit(
            f"开始双线程执行 - VIP签到 / 每日签到 / 美食活动 / 塔罗 / 法老 / 会长发任务 / 营地领钥匙 / 月卡礼包")

        # 创建进程

        if 1 in player:
            self.thread_1p = ThreadWithException(
                target=self.faa_dict[1].sign_in,
                name="1P Thread - SignIn",
                kwargs={})
            self.thread_1p.start()

        if 2 in player:
            self.thread_2p = ThreadWithException(
                target=self.faa_dict[2].sign_in,
                name="2P Thread - SignIn",
                kwargs={})
            self.thread_2p.start()

        if 1 in player:
            self.thread_1p.join()
        if 2 in player:
            self.thread_2p.join()

        self.model_end_print(text=title_text)

    def batch_fed_and_watered(self, player: list = None):

        title_text = "浇水 施肥 摘果"

        player = self.check_player(title=title_text, player=player)

        self.model_start_print(text=title_text)

        for pid in player:
            # 创建进程 -> 开始进程 -> 阻塞主进程
            self.thread_1p = ThreadWithException(
                target=self.faa_dict[pid].fed_and_watered,
                name=f"{pid}P Thread - FedAndWatered",
                kwargs={})
            self.thread_1p.start()
            self.thread_1p.join()

        self.model_end_print(text=title_text)

    def batch_scan_guild_info(self):

        title_text = "扫描公会"

        if not self.opt["advanced_settings"]["guild_manager_active"]:
            return

        def action(faa: FAA):
            # 进入公会页面 + 扫描 + 退出公会页面
            faa.action_bottom_menu(mode="公会")
            self.guild_manager.scan(handle=faa.handle, handle_360=faa.handle_360)
            faa.action_exit(mode="普通红叉")

        self.model_start_print(text=title_text)

        pid = self.opt["advanced_settings"]["guild_manager_active"]
        faa: FAA = self.faa_dict[pid]

        # 创建进程 -> 开始进程 -> 阻塞主进程
        self.thread_1p = ThreadWithException(
            target=action,
            name=f"{pid}P Thread - ScanGuildInfo",
            kwargs={"faa": faa})
        self.thread_1p.start()
        self.thread_1p.join()

        # 完成扫描 触发信号刷新数据
        SIGNAL.GUILD_MANAGER_FRESH.emit()

        self.model_end_print(text=title_text)

    def batch_receive_all_quest_rewards(self, player: list = None, quests: list = None):
        """
        :param player: 默认[1,2] 可选: [1] [2] [1,2] [2,1]
        :param quests: list 可包含内容: "普通任务" "公会任务" "情侣任务" "悬赏任务" "美食大赛" "大富翁" "营地任务"
        :return:
        """

        title_text = "领取奖励"

        player = self.check_player(title=title_text, player=player)

        if quests is None:
            quests = ["普通任务"]

        self.model_start_print(text=title_text)

        for mode in quests:

            SIGNAL.PRINT_TO_UI.emit(text=f"[{title_text}] [{mode}] 开始...")

            # 创建进程 -> 开始进程 -> 阻塞主进程
            if 1 in player:
                self.thread_1p = ThreadWithException(
                    target=self.faa_dict[1].action_receive_quest_rewards,
                    name=f"1P Thread - ReceiveQuest - {mode}",
                    kwargs={
                        "mode": mode
                    })
                self.thread_1p.start()

            if 1 in player and 2 in player:
                sleep(0.333)

            if 2 in player:
                self.thread_2p = ThreadWithException(
                    target=self.faa_dict[2].action_receive_quest_rewards,
                    name=f"2P Thread - ReceiveQuest - {mode}",
                    kwargs={
                        "mode": mode
                    })
                self.thread_2p.start()

            if 1 in player:
                self.thread_1p.join()
            if 2 in player:
                self.thread_2p.join()

            SIGNAL.PRINT_TO_UI.emit(text=f"[{title_text}] [{mode}] 完成")

        self.model_end_print(text=title_text)

    def batch_use_items_consumables(self, player: list = None):

        title_text = "使用绑定消耗品"

        player = self.check_player(title=title_text, player=player)

        self.model_start_print(text=title_text)

        # 创建进程 -> 开始进程 -> 阻塞主进程
        if 1 in player:
            self.thread_1p = ThreadWithException(
                target=self.faa_dict[1].use_items_consumables,
                name="1P Thread - UseItems",
                kwargs={})
            self.thread_1p.start()

        if 1 in player and 2 in player:
            sleep(0.333)

        if 2 in player:
            self.thread_2p = ThreadWithException(
                target=self.faa_dict[2].use_items_consumables,
                name="2P Thread - UseItems",
                kwargs={})
            self.thread_2p.start()

        if 1 in player:
            self.thread_1p.join()
        if 2 in player:
            self.thread_2p.join()

        self.model_end_print(text=title_text)

    def batch_use_items_double_card(self, player: list = None, max_times: int = 1):

        title_text = "使用双爆卡"

        player = self.check_player(title=title_text, player=player)

        self.model_start_print(text=title_text)

        # 创建进程 -> 开始进程 -> 阻塞主进程
        if 1 in player:
            self.thread_1p = ThreadWithException(
                target=self.faa_dict[1].use_items_double_card,
                name="1P Thread - UseItems - DoubleCard",
                kwargs={"max_times": max_times})
            self.thread_1p.start()

        if 2 in player and 1 in player:
            sleep(0.333)

        if 2 in player:
            self.thread_2p = ThreadWithException(
                target=self.faa_dict[2].use_items_double_card,
                name="2P Thread - UseItems - DoubleCard",
                kwargs={"max_times": max_times})
            self.thread_2p.start()

        if 1 in player:
            self.thread_1p.join()
        if 2 in player:
            self.thread_2p.join()

        self.model_end_print(text=title_text)

    def batch_loop_cross_server(self, player: list = None, deck: int = 1):

        title_text = "无限跨服刷威望"

        player = self.check_player(title=title_text, player=player)

        self.model_start_print(text=title_text)

        # 创建进程 -> 开始进程 -> 阻塞主进程
        if 1 in player:
            self.thread_1p = ThreadWithException(
                target=self.faa_dict[1].loop_cross_server,
                name="1P Thread - LoopCS",
                kwargs={"deck": deck})
            self.thread_1p.start()

        if 2 in player and 1 in player:
            sleep(0.333)

        if 2 in player:
            self.thread_2p = ThreadWithException(
                target=self.faa_dict[2].loop_cross_server,
                name="2P Thread - LoopCS",
                kwargs={"deck": deck})
            self.thread_2p.start()

        if 1 in player:
            self.thread_1p.join()
        if 2 in player:
            self.thread_2p.join()

    """业务代码 - 战斗相关"""

    def invite(self, player_a, player_b):
        """
        号1邀请号2到房间 需要在同一个区
        :return: bool 是否最终找到了图片
        """

        faa_a = self.faa_dict[player_a]
        faa_b = self.faa_dict[player_b]

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
                match_failed_check=2.0,
                click=True,
            )

            if not find:
                CUS_LOGGER.warning("2s没能组队? 土豆服务器问题, 尝试解决ing...")
                return False

            # p1关闭邀请窗口
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=faa_a.handle, x=590, y=491)
            time.sleep(1)

        return True

    def goto_stage_and_invite(self, stage_id, mt_wb_first_time, player_a, player_b):
        """
        :param stage_id:
        :param mt_wb_first_time: 世界boss或魔塔关卡, 第一次进入房间.
        :param player_a: 房主pid
        :param player_b: 队友pid
        :return:
        """

        is_cs = "CS" in stage_id
        is_mt = "MT" in stage_id

        faa_a = self.faa_dict[player_a]
        faa_b = self.faa_dict[player_b]

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
                    faa_a.action_goto_stage(mt_wb_first_time=mt_wb_first_time)
                    if mt_wb_first_time:
                        faa_b.action_goto_stage(mt_wb_first_time=mt_wb_first_time)

                sleep(3)

                if is_cs:
                    # 跨服副本 直接退出
                    return 0

                invite_success = self.invite(player_a=player_a, player_b=player_b)
                if invite_success:
                    SIGNAL.PRINT_TO_UI.emit(text="[单本轮战] 邀请成功")
                    # 邀请成功 返回退出
                    return 0

                failed_time += 1
                mt_wb_first_time = True

                SIGNAL.PRINT_TO_UI.emit(text=f"[单本轮战] 邀请失败... 建房失败 or 服务器抽风, 尝试({failed_time}/3)")

                if failed_time == 3:
                    failed_round += 1
                    SIGNAL.PRINT_TO_UI.emit(text=f"[单本轮战] 多次邀请失败, 刷新({failed_round}/3)")
                    if failed_round < 3:
                        self.batch_reload_game()
                        break
                    else:
                        SIGNAL.PRINT_TO_UI.emit(text=f"[单本轮战] 刷新({failed_round}/3)次数过多")
                        return 2

                faa_a.action_exit(mode="竞技岛")
                faa_b.action_exit(mode="竞技岛")

    def battle(self, player_a, player_b, senior_setting, change_card=True):
        """
        从进入房间到回到房间的流程
        :param player_a: 玩家A
        :param player_b: 玩家B
        :param change_card: 是否需要选择卡组
        :param senior_setting: 是否此关卡开启高级战斗
        :return:
            int id 用于判定战斗是 成功 或某种原因的失败 1-成功 2-服务器卡顿,需要重来 3-玩家设置的次数不足,跳过;
            dict 包含player_a和player_b的[战利品]和[宝箱]识别到的情况; 内容为聚合数量后的 dict。 如果识别异常, 返回值为两个None
            int 战斗消耗时间(秒);
        """

        is_group = self.faa_dict[player_a].is_group
        result_id = 0
        result_drop_by_list = {}  # {pid:{"loots":["item",...],"chest":["item",...]},...}
        result_drop_by_dict = {}  # {pid:{"loots":{"item":count,...},"chest":{"item":count,...}},...}
        result_spend_time = 0

        """检测是否成功进入房间"""
        if result_id == 0:

            # 创建并开始线程
            self.thread_1p = ThreadWithException(
                target=self.faa_dict[player_a].check_create_room_success,
                name="{}P Thread - 战前准备".format(player_a),
                kwargs={})
            self.thread_1p.start()
            if is_group:
                self.thread_2p = ThreadWithException(
                    target=self.faa_dict[player_b].check_create_room_success,
                    name="{}P Thread - 战前准备".format(player_b),
                    kwargs={})
                self.thread_2p.start()

            # 阻塞进程让进程执行完再继续本循环函数
            self.thread_1p.join()
            if is_group:
                self.thread_2p.join()

            # 获取返回值
            result_id = max(result_id, self.thread_1p.get_return_value())
            if is_group:
                result_id = max(result_id, self.thread_2p.get_return_value())

        CUS_LOGGER.info("[战斗主流程] 检测是否成功进入房间 已完成")

        """修改卡组"""
        if result_id == 0:

            if change_card:

                # 创建并开始线程
                self.thread_1p = ThreadWithException(
                    target=self.faa_dict[player_a].battle_preparation_change_deck,
                    name="{}P Thread - 修改卡组".format(player_a),
                    kwargs={})
                self.thread_1p.start()
                if is_group:
                    self.thread_2p = ThreadWithException(
                        target=self.faa_dict[player_b].battle_preparation_change_deck,
                        name="{}P Thread - 修改卡组".format(player_b),
                        kwargs={})
                    self.thread_2p.start()

                # 阻塞进程让进程执行完再继续本循环函数
                self.thread_1p.join()
                if is_group:
                    self.thread_2p.join()

                # 获取返回值
                result_id = max(result_id, self.thread_1p.get_return_value())
                if is_group:
                    result_id = max(result_id, self.thread_2p.get_return_value())

        CUS_LOGGER.info("[战斗主流程] 修改卡组 已完成")

        """不同时开始战斗, 并检测是否成功进入游戏"""
        if result_id == 0:

            # 创建并开始线程 注意 玩家B 是非房主 需要先开始
            if is_group:
                self.thread_2p = ThreadWithException(
                    target=self.faa_dict[player_b].start_and_ensure_entry,
                    name="{}P Thread - 进入游戏".format(player_b),
                    kwargs={})
                self.thread_2p.start()
                # A 一定要后开始!!!
                time.sleep(2)

            self.thread_1p = ThreadWithException(
                target=self.faa_dict[player_a].start_and_ensure_entry,
                name="{}P Thread - 进入游戏".format(player_a),
                kwargs={})
            self.thread_1p.start()

            # 阻塞进程让进程执行完再继续本循环函数
            self.thread_1p.join()
            if is_group:
                self.thread_2p.join()

            # 获取返回值
            result_id = max(result_id, self.thread_1p.get_return_value())
            if is_group:
                result_id = max(result_id, self.thread_2p.get_return_value())

        CUS_LOGGER.info("[战斗主流程] 开始战斗 已完成")
        # 记录准确开始时间 如果加载时间少于0.3s 会造成等额的误差!
        start_time = time.time()

        """根据设定, 进行加速"""
        if result_id == 0:

            # 创建并开始线程
            self.thread_1p = ThreadWithException(
                target=self.faa_dict[player_a].accelerate,
                name="{}P Thread - 进入游戏".format(player_a),
                kwargs={}
            )
            if is_group:
                self.thread_2p = ThreadWithException(
                    target=self.faa_dict[player_b].accelerate,
                    name="{}P Thread - 进入游戏".format(player_b),
                    kwargs={}
                )

            self.thread_1p.start()
            if is_group:
                self.thread_2p.start()

            # 阻塞进程让进程执行完再继续本循环函数
            self.thread_1p.join()
            if is_group:
                self.thread_2p.join()

            # 获取返回值
            result_id = max(result_id, self.thread_1p.get_return_value())
            if is_group:
                result_id = max(result_id, self.thread_2p.get_return_value())

        CUS_LOGGER.info("[战斗主流程] 加速游戏 已完成")

        """多线程进行战斗 此处1p-ap 2p-bp 战斗部分没有返回值"""

        if result_id == 0:

            # 初始化多线程
            self.thread_1p = ThreadWithException(
                target=self.faa_dict[player_a].battle_a_round_init_battle_plan,
                name="{}P Thread - Battle".format(player_a),
                kwargs={})
            self.thread_1p.start()

            if is_group:
                self.thread_2p = ThreadWithException(
                    target=self.faa_dict[player_b].battle_a_round_init_battle_plan,
                    name="{}P Thread - Battle".format(player_b),
                    kwargs={})
                self.thread_2p.start()

            # 阻塞进程让进程执行完再继续本循环函数
            self.thread_1p.join()
            if is_group:
                self.thread_2p.join()

            if self.opt["senior_settings"]["auto_senior_settings"]:
                if senior_setting:  # 双重开关，当全局的启用了，对应的关卡也要启用
                    self.process, queue_todo = read_and_get_return_information(
                        self.faa_dict[player_a],
                        self.opt["senior_settings"]["senior_log_state"],
                        self.opt["senior_settings"]["gpu_settings"],
                        self.opt["senior_settings"]["interval"]
                    )
                else:
                    CUS_LOGGER.debug("警告：全局设置启用了高级战斗，但对应关卡未开启高级战斗")
                    queue_todo = None
                    self.process = None

            else:
                queue_todo = None
                self.process = None

            # 初始化放卡管理器
            self.thread_card_manager = CardManager(
                todo=self,
                faa_a=self.faa_dict[player_a],
                faa_b=self.faa_dict[player_b] if player_b else None,
                solve_queue=queue_todo,
                check_interval=self.battle_check_interval,
                senior_callback_interval=self.opt["senior_settings"]["interval"],
                start_time=start_time
            )

            self.thread_card_manager.start()
            self.exec()

            # 此处的重新变为None是为了让中止todo实例时时该属性仍存在
            self.thread_card_manager = None

            if self.opt["senior_settings"]["auto_senior_settings"]:
                if senior_setting:
                    kill_process(self.process)
                    self.process = None

            CUS_LOGGER.debug('thread_card_manager 退出事件循环并完成销毁线程')

            result_spend_time = time.time() - start_time

        CUS_LOGGER.info("[战斗主流程] 战斗循环 已完成")

        """多线程进行战利品和宝箱检查 此处1p-ap 2p-bp"""

        if result_id == 0:

            # 初始化多线程
            self.thread_1p = ThreadWithException(
                target=self.faa_dict[player_a].perform_action_capture_match_for_loots_and_chests,
                name="{}P Thread - Battle - Screen".format(player_a),
                kwargs={})
            if is_group:
                self.thread_2p = ThreadWithException(
                    target=self.faa_dict[player_b].perform_action_capture_match_for_loots_and_chests,
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
                result_drop_by_list[player_a] = result[1]  # 可能是None 或 dict 故判空

            if is_group:
                result = self.thread_2p.get_return_value()
                result_id = max(result_id, result[0])
                if result[1]:
                    result_drop_by_list[player_b] = result[1]  # 可能是None 或 dict 故判空

            """数据基础校验, 构建有向无环图, 完成高级校验, 并酌情发送至服务器和更新至Ranking"""
            # result_drop_by_list = {
            #   1:{"loots":["物品"...],"chests":["物品"...]} //数据 可能不存在 None
            #   2:{"loots":["物品"...],"chests":["物品"...]} //数据 可能不存在 None或不组队
            #   }
            update_dag_success_at_least_once = False

            for p_id, player_data in result_drop_by_list.items():

                title = f"[{p_id}P] [战利品识别]"

                # 两种战利品的数据
                loots_list = player_data["loots"]  # list[str,...]
                chests_list = player_data["chests"]  # list[str,...]

                # 默认表示识别异常
                result_drop_by_dict[p_id] = {"loots": None, "chests": None}

                def check_data_validity(data):
                    """确定同一个物品名总是相邻出现, 但香料和四叶草无视改规则"""

                    # 创建一个字典来记录每个值最后出现的位置
                    last_seen = {}

                    # 白名单, 不参与连续出现校验
                    # 识别失败也应当连续出现(三岛道具和其他临时道具优先级总最高, 会扎堆)
                    white_list = [
                        '5级四叶草', '4级四叶草', '3级四叶草', '2级四叶草', '1级四叶草',
                        '天使香料', '精灵香料', '魔幻香料', '皇室香料', '极品香料', '秘制香料', '上等香料', '天然香料'
                    ]

                    for index, item_name in enumerate(data):

                        # 如果物品在白名单, 不记录
                        if item_name in white_list:
                            continue

                        # 如果当前物品之前已经出现过, 且间隔 > 1 视为无效数据
                        if item_name in last_seen:
                            if index - last_seen[item_name] > 1:
                                return False

                        # 更新当前物品的最后出现位置
                        last_seen[item_name] = index

                    return True

                # 确定同一个物品名总是相邻出现
                if not check_data_validity(loots_list):
                    text = f"{title} [基础校验] 失败! 同一个物品在连续出现若干次后, 再次出现! 为截图有误!"
                    CUS_LOGGER.warning(text)
                    continue

                # 所有物品都是 识别失败
                if all(item == "识别失败" for item in loots_list):
                    text = f"{title} [基础校验] 失败! 识别失败过多! 为截图有误!"
                    CUS_LOGGER.warning(text)
                    continue

                def drop_list_to_dict(drop_list):
                    """
                    将列表转换为计数字典, 按照物品首次出现顺序,
                    """
                    drop_dict = defaultdict(int)
                    for item in drop_list:
                        drop_dict[item] += 1
                    return dict(drop_dict)

                loots_dict = drop_list_to_dict(loots_list)
                chests_dict = drop_list_to_dict(chests_list)

                # 使用战利品计数list, 更新item_dag_graph文件, 不包含识别失败
                best_match_items_success = [
                    item for item in copy.deepcopy(list(loots_dict.keys())) if item != "识别失败"]

                # 更新 item_dag_graph 文件
                update_dag_result = update_dag_graph(item_list_new=best_match_items_success)

                # 更新成功, 记录两个号中是否有至少一个号更新成功
                update_dag_success_at_least_once = update_dag_success_at_least_once or update_dag_result

                if not update_dag_result:
                    text = f"{title} [有向无环图] [更新] 失败! 本次数据无法构筑 DAG，存在环. 可能是截图卡住了. 放弃记录和上传"
                    CUS_LOGGER.warning(text)
                    continue

                CUS_LOGGER.info(f"{title} [有向无环图] [更新] 成功! 成功构筑 DAG.")

                """
                至此所有校验通过!
                """

                result_drop_by_dict[p_id] = {"loots": loots_dict, "chests": chests_dict}

                # 保存详细数据到json
                loots_and_chests_statistics_to_json(
                    faa=self.faa_dict[p_id],
                    loots_dict=loots_dict,
                    chests_dict=chests_dict)
                CUS_LOGGER.info(f"{title} [保存日志] [详细数据] 成功保存!")

                # 保存汇总统计数据到json
                detail_data = loots_and_chests_detail_to_json(
                    faa=self.faa_dict[p_id],
                    loots_dict=loots_dict,
                    chests_dict=chests_dict)
                CUS_LOGGER.info(f"{title} [保存日志] [统计数据] 成功保存!")
                CUS_LOGGER.debug(f"{title} [保存日志] [统计数据] 数据: {detail_data}")

                # 发送到服务器
                upload_result = loots_and_chests_data_post_to_sever(
                    detail_data=detail_data,
                    url=EXTRA.MISU_LOGISTICS)
                if upload_result:
                    CUS_LOGGER.info(f"{title} [保存日志] [统计数据] 成功发送一条数据到米苏物流!")
                else:
                    CUS_LOGGER.warning(f"{title} [保存日志] [统计数据] 超时! 可能是米苏物流服务器炸了...")

            if not update_dag_success_at_least_once:
                CUS_LOGGER.warning(
                    f"[战利品识别] [有向无环图] item_ranking_dag_graph.json 更新失败! 本次战斗未获得任何有效数据!")
            else:
                # 如果成功更新了 item_dag_graph.json, 更新ranking, 成功返回更新后的 ranking 失败返回None
                ranking_new = find_longest_path_from_dag()
                if ranking_new:
                    CUS_LOGGER.debug(
                        f"[战利品识别] [有向无环图] item_ranking_dag_graph.json 已成功更新")
                else:
                    CUS_LOGGER.error(
                        f"[战利品识别] [有向无环图] item_ranking_dag_graph.json 更新失败, "
                        f" 文件被删除 或 因程序错误成环! 请联系开发者!")

        CUS_LOGGER.info("[战斗主流程] 多线程进行战利品和宝箱检查 已完成")

        """分开进行战后检查"""
        if result_id == 0:
            result_id = self.faa_dict[player_a].battle_a_round_warp_up()
            if is_group:
                result_id = self.faa_dict[player_b].battle_a_round_warp_up()

        CUS_LOGGER.info("[战斗主流程] 战后检查完成 battle 函数执行结束")

        return result_id, result_drop_by_dict, result_spend_time

    def n_battle_customize_battle_error_print(self, success_battle_time):
        # 结束提示文本
        SIGNAL.PRINT_TO_UI.emit(
            text=f"[单本轮战] 第{success_battle_time}次, 出现未知异常! 刷新后卡死, 以防止更多问题, 出现此问题可上报作者")
        self.batch_reload_game()
        sleep(60 * 60 * 24)

    def battle_1_1_n(self, stage_id, player, need_key, max_times, dict_exit,
                     global_plan_active, deck, battle_plan_1p, battle_plan_2p,
                     quest_card, ban_card_list, max_card_num,
                     title_text, is_cu=False):
        """
        1轮次 1关卡 n次数
        副本外 -> (副本内战斗 * n次) -> 副本外
        player: [1], [2], [1,2], [2,1] 分别代表 1P单人 2P单人 1P队长 2P队长
        """

        """参数预处理"""

        # 组合完整的title
        title = f"[单本轮战] {title_text}"

        # 判断是不是打魔塔 世界BOSS 或 自建房
        is_mt = "MT" in stage_id
        is_wb = "WB" in stage_id
        is_cs = "CS" in stage_id

        # 如果是板上钉钉的单人关卡还tm组队, 强制修正为仅1P单人.
        if len(player) > 1 and ("MT-1" in stage_id or "MT-3" in stage_id or "WB" in stage_id):
            SIGNAL.PRINT_TO_UI.emit(text=f"{title} 检测到组队, 强制修正为仅1P单人")
            player = [1]

        # 判断是不是组队
        is_group = len(player) > 1

        # 如果是多人跨服 防呆重写 变回 1房主
        if is_cs and is_group:
            SIGNAL.PRINT_TO_UI.emit(text=f"{title} 检测到多人跨服, 强制修正为1P房主")
            player = [1, 2]

        # 处理多人信息 (这些信息只影响函数内, 所以不判断是否组队)
        pid_a = player[0]  # 房主 创建房间者
        pid_b = (1 if pid_a == 2 else 2) if is_group else None
        faa_a = self.faa_dict[pid_a]
        faa_b = self.faa_dict[pid_b] if pid_b else None

        # 默认肯定是不跳过的
        skip = False
        # 限制即使勾选了设置中的启用高级战斗，也需要在全局战斗设置中修改对应关卡
        senior_setting = False

        def load_g_plan(skip_, deck_, battle_plan_1p_, battle_plan_2p_, senior_setting_, stage_id_=None):

            if stage_id_ is None:
                stage_id_ = faa_a.stage_info["b_id"]

            if global_plan_active:
                # 获取 g_plan

                try:
                    with EXTRA.FILE_LOCK:
                        with open(file=PATHS["config"] + "//stage_plan.json", mode="r", encoding="UTF-8") as file:
                            stage_plan = json.load(file)
                except FileNotFoundError:
                    stage_plan = {}

                g_plan = stage_plan.get(stage_id_, None)

                if not g_plan:
                    # 2.1.0-beta.2+ 包含全局方案的情况
                    g_plan = stage_plan.get("global", None)

                if not g_plan:
                    # 2.1.0-beta.1- 不包含全局方案的情况.
                    g_plan = {
                        "skip": False,
                        "deck": 0,
                        "senior_setting": False,
                        "battle_plan": [
                            "00000000-0000-0000-0000-000000000000",
                            "00000000-0000-0000-0000-000000000001"]}

                # 加载 g_plan
                skip_ = g_plan["skip"]
                deck_ = g_plan["deck"]
                senior_setting_ = g_plan.get("senior_setting", False)

                if is_group:
                    # 双人组队
                    battle_plan_1p_ = g_plan["battle_plan"][0]
                    battle_plan_2p_ = g_plan["battle_plan"][1]
                else:
                    if "WB" in stage_id or "MT-1" in stage_id or "MT-3" in stage_id:
                        # 世界Boss关卡 魔塔单人和密室 完全单人关卡, 使用 1P 和 2P各自的 方案
                        battle_plan_1p_ = g_plan["battle_plan"][0]
                        battle_plan_2p_ = g_plan["battle_plan"][1]
                    else:
                        # 可组队关卡, 但设置了仅单人作战
                        battle_plan_1p_ = g_plan["battle_plan"][0]
                        battle_plan_2p_ = g_plan["battle_plan"][0]

            battle_plan_a_ = battle_plan_1p_ if pid_a == 1 else battle_plan_2p_
            battle_plan_b_ = (battle_plan_1p_ if pid_b == 1 else battle_plan_2p_) if is_group else None

            return skip_, deck_, battle_plan_a_, battle_plan_b_, senior_setting_

        # 加载全局关卡方案
        skip, deck, battle_plan_a, battle_plan_b, senior_setting = load_g_plan(
            skip_=skip,
            deck_=deck,
            battle_plan_1p_=battle_plan_1p,
            battle_plan_2p_=battle_plan_2p,
            senior_setting_=senior_setting,
            stage_id_=stage_id
        )

        def check_skip():
            """
            检查各种条件 例如
            人物等级 / 次数 / 时间条件 是否充足
            """
            if skip:
                SIGNAL.PRINT_TO_UI.emit(text=f"{title} 根据全局关卡设置, 跳过")
                return False

            # 关卡名称正确性校验

            if not faa_a.check_stage_id_is_true():
                SIGNAL.PRINT_TO_UI.emit(text=f"{title} [{pid_a}P] 关卡名称错误, 跳过")
                return False

            # 关卡激活校验

            if not faa_a.check_stage_is_active():
                SIGNAL.PRINT_TO_UI.emit(text=f"{title} [{pid_a}P] 关卡未激活, 跳过")
                return False

            # 关卡等级校验

            if not faa_a.check_level():
                SIGNAL.PRINT_TO_UI.emit(text=f"{title} [{pid_a}P] 等级不足, 跳过")
                return False

            if is_group:
                if not faa_b.check_level():
                    SIGNAL.PRINT_TO_UI.emit(text=f"{title} [{pid_b}P] 等级不足, 跳过")
                    return False

            # FAA内关卡的设置参数完整性校验

            if max_times < 1:
                SIGNAL.PRINT_TO_UI.emit(text=f"{title} {stage_id} 设置次数不足, 跳过")
                return False

            if battle_plan_1p not in g_resources.RESOURCE_B.keys():
                SIGNAL.PRINT_TO_UI.emit(
                    text=f"{title} [1P] 无法通过UUID找到战斗方案! 您使用的全局方案&关卡方案已被删除. 请重新设置!")
                return False

            if is_group:
                if battle_plan_2p not in g_resources.RESOURCE_B.keys():
                    SIGNAL.PRINT_TO_UI.emit(
                        text=f"{title} [2P] 无法通过UUID找到战斗方案! 您使用的全局方案&关卡方案已被删除. 请重新设置!")
                    return False

            return True

        def goto_stage(need_goto_stage, need_change_card):
            """
            :param need_goto_stage:
            :param need_change_card:
            :return: result_id, need_change_card, need_goto_stage
            """
            # 初始
            result_id = 0

            # 自建房 直接返回
            if is_cu:
                return result_id, need_change_card, need_goto_stage

            # 非自建房
            if is_mt:
                # 魔塔
                if not is_group:
                    # 单人前往副本
                    faa_a.action_goto_stage(mt_wb_first_time=need_goto_stage)  # 第一次使用 mt_wb_first_time, 之后则不用
                else:
                    # 多人前往副本
                    result_id = self.goto_stage_and_invite(
                        stage_id=stage_id, mt_wb_first_time=need_goto_stage, player_a=pid_a, player_b=pid_b)
                need_change_card = True  # 魔塔显然需要重新选卡组
            elif is_wb:
                faa_a.action_goto_stage(mt_wb_first_time=need_goto_stage)  # 第一次使用 mt_wb_first_time, 之后则不用
                need_change_card = True  # 巅峰对决显然需要重新选卡组
            else:
                # 非魔塔
                if need_goto_stage:
                    if not is_group:
                        # 单人前往副本
                        faa_a.action_goto_stage()
                    else:
                        # 多人前往副本
                        result_id = self.goto_stage_and_invite(
                            stage_id=stage_id, mt_wb_first_time=False, player_a=pid_a, player_b=pid_b)

            need_goto_stage = False  # 进入后Flag变化

            return result_id, need_change_card, need_goto_stage

        def multi_round_battle():

            # 声明: 这些函数来自外部作用域, 以便进行修改
            nonlocal skip, deck, battle_plan_a, battle_plan_b, senior_setting

            # 标记是否需要进入副本
            need_goto_stage = True
            need_change_card = True

            battle_count = 0  # 记录成功的次数
            result_list = []  # 记录成功场次的战斗结果记录

            # 轮次作战
            while battle_count < max_times:

                result_id, need_change_card, need_goto_stage = goto_stage(
                    need_goto_stage=need_goto_stage, need_change_card=need_change_card)

                # 再次加载全局关卡方案, goto_stage 过程中 可能检测到子集关卡
                skip, deck, battle_plan_a, battle_plan_b, senior_setting = load_g_plan(
                    skip_=skip,
                    deck_=deck,
                    battle_plan_1p_=battle_plan_1p,
                    battle_plan_2p_=battle_plan_2p,
                    senior_setting_=senior_setting,
                    stage_id_=None,
                )

                # 将战斗方案加载至FAA
                faa_a.set_battle_plan(battle_plan_uuid=battle_plan_a)
                if is_group:
                    faa_b.set_battle_plan(battle_plan_uuid=battle_plan_b)

                # SIGNAL.PRINT_TO_UI.emit(
                #     text=f"{title} [{faa_a.player}P] 房主, "
                #          f"方案: {EXTRA.BATTLE_PLAN_UUID_TO_PATH[battle_plan_a].split("\\")[-1].split(".")[0]}")
                # if is_group:
                #     SIGNAL.PRINT_TO_UI.emit(
                #         text=f"{title} [{faa_b.player}P] 队友, "
                #              f"方案: {EXTRA.BATTLE_PLAN_UUID_TO_PATH[battle_plan_b].split("\\")[-1].split(".")[0]}")

                if result_id == 2:
                    # 跳过本次 计数+1
                    battle_count += 1
                    # 进入异常, 跳过
                    need_goto_stage = True
                    # 结束提示文本
                    SIGNAL.PRINT_TO_UI.emit(text=f"{title}第{battle_count}次, 创建房间多次异常, 重启跳过")
                    # 根据角色数刷新
                    self.batch_reload_game(player=player)

                SIGNAL.PRINT_TO_UI.emit(text=f"{title}第{battle_count + 1}次, 开始")

                # 开始战斗循环
                result_id, result_drop, result_spend_time = self.battle(
                    player_a=pid_a,
                    player_b=pid_b,
                    change_card=need_change_card,
                    senior_setting=senior_setting)

                if result_id == 0:

                    # 战斗成功 计数+1
                    battle_count += 1

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
                    is_used_key = faa_a.is_used_key

                    # 加入结果统计列表
                    result_list.append({
                        "time_spend": result_spend_time,
                        "is_used_key": is_used_key,
                        "loot_dict_list": result_drop  # result_loot_dict_list = [{a掉落}, {b掉落}]
                    })

                    # 时间
                    SIGNAL.PRINT_TO_UI.emit(
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

                    # 成功的战斗 之后不需要选择卡组
                    need_change_card = False

                if result_id == 1:

                    # 重试本次

                    if is_cu:
                        # 进入异常 但是自定义
                        self.n_battle_customize_battle_error_print(success_battle_time=battle_count)
                        break

                    # 进入异常, 重启再来
                    need_goto_stage = True

                    # 结束提示文本
                    SIGNAL.PRINT_TO_UI.emit(text=f"{title}第{battle_count + 1}次, 流程出现错误, 重启再来")

                    self.batch_reload_game(player=player)

                    # 重新进入 因此需要重新选卡组
                    need_change_card = True

                if result_id == 2:

                    # 进入异常, 跳过

                    if is_cu:
                        # 进入异常 但是自定义
                        self.n_battle_customize_battle_error_print(success_battle_time=battle_count)
                        break

                    # 跳过本次 计数+1
                    battle_count += 1

                    # 刷新了 需要重新进入关卡初始位置
                    need_goto_stage = True

                    # 结束提示文本
                    SIGNAL.PRINT_TO_UI.emit(text=f"{title}第{battle_count}次, 流程出现错误, 重启跳过")

                    self.batch_reload_game(player=player)

                    # 重新进入 因此需要重新选卡组
                    need_change_card = True

                if result_id == 3:
                    # 放弃所有次数
                    # 自动选卡 但没有对应的卡片! 最严重的报错!
                    SIGNAL.PRINT_TO_UI.emit(
                        text=f"{title} 自动选卡失败! 放弃本关全部作战! 您是否拥有对应绑定卡?")

                    self.batch_reload_game(player=player)

                    break

            return result_list

        def end_statistic_print(result_list):
            """
            结束后进行 本次 多本轮战的 战利品 统计和输出, 由于其统计为本次多本轮战, 故不能改变其位置
            """

            CUS_LOGGER.debug("战斗数据, 最终统计: ")
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

            SIGNAL.PRINT_TO_UI.emit(
                text="正常场次:{}次 使用钥匙:{}次 总耗时:{}分{}秒  场均耗时:{}分{}秒".format(
                    valid_total_count,
                    count_used_key,
                    *divmod(int(sum_time_spend), 60),
                    *divmod(int(average_time_spend), 60)
                ))

            if len(player) == 1:
                # 单人
                self.output_player_loot(player_id=pid_a, result_list=result_list)
            else:
                # 多人
                self.output_player_loot(player_id=1, result_list=result_list)
                self.output_player_loot(player_id=2, result_list=result_list)

        def main():

            SIGNAL.PRINT_TO_UI.emit(text=f"{title}{stage_id} {max_times}次 开始", color_level=5)

            opt_ad = self.opt["advanced_settings"]
            c_a_c_c_deck = opt_ad["cus_auto_carry_card_value"] if opt_ad["cus_auto_carry_card_active"] else 6

            # 填入战斗方案和关卡信息, 之后会大量动作和更改类属性, 所以需要判断是否组队
            faa_a.set_config_for_battle(
                is_main=True,
                is_group=is_group,
                need_key=need_key,
                deck=c_a_c_c_deck if deck == 0 else deck,
                auto_carry_card=deck == 0,
                quest_card=quest_card,
                ban_card_list=ban_card_list,
                max_card_num=max_card_num,
                stage_id=stage_id,
                is_cu=is_cu)

            if is_group:
                faa_b.set_config_for_battle(
                    is_main=False,
                    is_group=is_group,
                    need_key=need_key,
                    deck=c_a_c_c_deck if deck == 0 else deck,
                    auto_carry_card=deck == 0,
                    quest_card=quest_card,
                    ban_card_list=ban_card_list,
                    max_card_num=max_card_num,
                    stage_id=stage_id,
                    is_cu=is_cu)

            # 基本参数检测
            check_result = check_skip()
            if not check_result:
                return False

            # 进行 1本n次 返回 成功的每次战斗结果组成的list
            result_list = multi_round_battle()

            # 根据多次战斗结果组成的list 打印 1本n次 的汇总结果
            end_statistic_print(result_list=result_list)

            SIGNAL.PRINT_TO_UI.emit(text=f"{title}{stage_id} {max_times}次 完成 ", color_level=5)

            return True

        return main()

    def output_player_loot(self, player_id, result_list):
        """
        根据战斗的最终结果, 打印玩家战利品信息
        :param player_id:  player_a, player_b int 1 2
        :param result_list: [{一场战斗的信息}, ...]
        :return:
        关于 result_list
        """

        # 输入为
        count_dict = {"loots": {}, "chests": {}}  # 汇总每个物品的总掉落
        count_match_success_dict = {"loots": [], "chests": []}

        # 计数正确场次
        for _, a_battle_data in enumerate(result_list):
            for drop_type in ["loots", "chests"]:

                data = a_battle_data["loot_dict_list"][player_id][drop_type]
                # 如果标记为识别失败
                if data is None:
                    count_match_success_dict[drop_type].append(False)
                    continue
                count_match_success_dict[drop_type].append(True)

                for key, value in data.items():
                    if key in count_dict[drop_type].keys():
                        count_dict[drop_type][key] += value
                    else:
                        count_dict[drop_type][key] = value

        # 根据有向无环图的ranking_list 重新排序key

        def ranking_reorder_dict(count_dict, ranking_list):
            """
            根据 ranking_list 对 count_dict 中的元素进行重新排序。

            :param count_dict: 需要重新排序的字典
            :param ranking_list: 排序依据的列表
            :return: 重新排序后的字典
            """
            # 创建一个字典来存储排序后的结果
            sorted_dict = {}

            # 遍历 ranking_list 中的元素
            for key in ranking_list:
                if key in count_dict:
                    sorted_dict[key] = count_dict[key]

            # 将 count_dict 中不在 ranking_list 中的元素添加到排序后的字典中
            for key in count_dict:
                if key not in sorted_dict:
                    sorted_dict[key] = count_dict[key]

            return sorted_dict

        json_path = PATHS["logs"] + "\\item_ranking_dag_graph.json"
        ranking_list = ranking_read_data(json_path=json_path)["ranking"]
        for drop_type in ["loots", "chests"]:
            count_dict[drop_type] = ranking_reorder_dict(
                count_dict=count_dict[drop_type], ranking_list=ranking_list)

        # 生成图片
        text = "[{}P] 战利品合计掉落, 识别有效场次:{}".format(player_id, sum(count_match_success_dict["loots"]))
        SIGNAL.PRINT_TO_UI.emit(text=text, time=False)
        SIGNAL.IMAGE_TO_UI.emit(image=create_drops_image(count_dict=count_dict["loots"]))

        text = "[{}P] 宝箱合计掉落, 识别有效场次:{}".format(player_id, sum(count_match_success_dict["chests"]))
        SIGNAL.PRINT_TO_UI.emit(text=text, time=False)
        SIGNAL.IMAGE_TO_UI.emit(image=create_drops_image(count_dict=count_dict["chests"]))

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
            SIGNAL.PRINT_TO_UI.emit(text=f"[双线程单人] {self.todo_id}P已开始任务! 进行自锁!", color_level=3)
            self.my_lock = True

        SIGNAL.PRINT_TO_UI.emit(text=f"{title}开始...", color_level=3)

        # 遍历完成每一个任务
        for i in range(len(quest_list)):

            quest = quest_list[i]

            # 处理允许缺失的值
            quest_card = quest.get("quest_card", None)
            ban_card_list = quest.get("ban_card_list", None)
            max_card_num = quest.get("max_card_num", None)
            is_cu = quest.get("is_cu", False)

            text_parts = [
                "{}事项{}".format(
                    title,
                    quest["battle_id"] if "battle_id" in quest else (i + 1)),
                "开始",
                "组队" if len(quest["player"]) == 2 else "单人",
                f"{quest["stage_id"]}",
                f"{quest["max_times"]}次",
            ]
            if quest_card:
                text_parts.append("带卡:{}".format(quest_card))
            if ban_card_list:
                text_parts.append("禁卡:{}".format(ban_card_list))
            if max_card_num:
                text_parts.append("限数:{}".format(max_card_num))
            if is_cu:
                text_parts.append("自建房:{}".format(is_cu))

            SIGNAL.PRINT_TO_UI.emit(text=",".join(text_parts), color_level=4)

            self.battle_1_1_n(
                stage_id=quest["stage_id"],
                player=quest["player"],
                need_key=quest["need_key"],
                max_times=quest["max_times"],
                dict_exit=quest["dict_exit"],
                global_plan_active=quest["global_plan_active"],
                deck=quest["deck"],
                battle_plan_1p=quest["battle_plan_1p"],
                battle_plan_2p=quest["battle_plan_2p"],
                quest_card=quest_card,
                ban_card_list=ban_card_list,
                max_card_num=max_card_num,
                title_text=extra_title,
                is_cu=quest.get("is_cu", False)
            )

            SIGNAL.PRINT_TO_UI.emit(
                text="{}事项{}, 完成".format(
                    title,
                    quest["battle_id"] if "battle_id" in quest else (i + 1)
                ),
                color_level=4
            )

        SIGNAL.PRINT_TO_UI.emit(text=f"{title}完成", color_level=3)

        if need_lock:
            SIGNAL.PRINT_TO_UI.emit(
                text=f"双线程单人功能中, {self.todo_id}P已完成所有任务! 已解锁另一线程!",
                color_level=3
            )

            # 为另一个todo解锁
            self.signal_todo_lock.emit(False)
            # 如果自身是主线程, 且未被解锁, 循环等待
            if self.todo_id == 1:
                while self.my_lock:
                    sleep(1)

    """使用battle_1_n_n为核心的变种 [单线程][单人或双人]"""

    def easy_battle(
            self, text_, stage_id, player, max_times,
            global_plan_active, deck, battle_plan_1p, battle_plan_2p, dict_exit, is_cu=False
    ):
        """仅调用 n_battle的简易作战"""
        self.model_start_print(text=text_)

        player = self.check_player(title="通用战斗", player=player)

        if player == [1] and "MT-2-" in stage_id:
            SIGNAL.PRINT_TO_UI.emit(text="[通用战斗] 单人无法进行魔塔双人战! 即将强制跳过本步骤!", color_level=1)
            self.model_end_print(text=text_)
            return

        quest_list = [
            {
                "stage_id": stage_id,
                "max_times": max_times,
                "need_key": True,
                "player": player,
                "global_plan_active": global_plan_active,
                "deck": deck,
                "battle_plan_1p": battle_plan_1p,
                "battle_plan_2p": battle_plan_2p,
                "dict_exit": dict_exit,
                "is_cu": is_cu
            }]
        self.battle_1_n_n(quest_list=quest_list)

        self.model_end_print(text=text_)

    def offer_reward(self, text_, max_times_1, max_times_2, max_times_3, max_times_4,
                     global_plan_active, deck, battle_plan_1p, battle_plan_2p):

        self.model_start_print(text=text_)

        if self.faa_dict[1].channel == self.faa_dict[2].channel:
            SIGNAL.PRINT_TO_UI.emit(text=f"[{text_}] 仅有一位角色, 即将强制跳过本步骤!", color_level=1)
            self.model_end_print(text=text_)
            return

        SIGNAL.PRINT_TO_UI.emit(text=f"[{text_}] 开始[多本轮战]...")

        quest_list = []
        for i in range(4):
            quest_list.append({
                "player": [2, 1],
                "need_key": True,
                "global_plan_active": global_plan_active,
                "deck": deck,
                "battle_plan_1p": battle_plan_1p,
                "battle_plan_2p": battle_plan_2p,
                "stage_id": "OR-0-" + str(i + 1),
                "max_times": [max_times_1, max_times_2, max_times_3, max_times_4][i],
                "dict_exit": {
                    "other_time_player_a": [],
                    "other_time_player_b": [],
                    "last_time_player_a": ["竞技岛"],
                    "last_time_player_b": ["竞技岛"]}
            })

        self.battle_1_n_n(quest_list=quest_list)

        # 领取奖励
        self.faa_dict[1].action_receive_quest_rewards(mode="悬赏任务")
        self.faa_dict[2].action_receive_quest_rewards(mode="悬赏任务")

        self.model_end_print(text=text_)

    def guild_or_spouse_quest(self, text_, quest_mode,
                              global_plan_active, deck, battle_plan_1p, battle_plan_2p, stage=False):
        """完成公会or情侣任务"""

        self.model_start_print(text=text_)

        if self.faa_dict[1].channel == self.faa_dict[2].channel:
            SIGNAL.PRINT_TO_UI.emit(text=f"[{text_}] 仅有一位角色, 即将强制跳过本步骤!", color_level=1)
            self.model_end_print(text=text_)
            return

        # 激活删除物品高危功能(可选) + 领取奖励一次
        if quest_mode == "公会任务":
            self.batch_level_2_action(dark_crystal=False)
        SIGNAL.PRINT_TO_UI.emit(text=f"[{text_}] 检查领取奖励...")
        self.faa_dict[1].action_receive_quest_rewards(mode=quest_mode)
        self.faa_dict[2].action_receive_quest_rewards(mode=quest_mode)

        # 获取任务
        SIGNAL.PRINT_TO_UI.emit(text=f"[{text_}] 获取任务列表...")
        quest_list_1 = self.faa_dict[1].match_quests(mode=quest_mode, qg_cs=stage)
        quest_list_2 = self.faa_dict[2].match_quests(mode=quest_mode, qg_cs=stage)
        quest_list = quest_list_1 + [i for i in quest_list_2 if i not in quest_list_1]

        for i in quest_list:
            text_parts = [f"副本:{i["stage_id"]}"]
            quest_card = i.get("quest_card", None)
            ban_card_list = i.get("ban_card_list", None)
            max_card_num = i.get("max_card_num", None)
            if quest_card:
                text_parts.append("带卡:{}".format(quest_card))
            if ban_card_list:
                text_parts.append("禁卡:{}".format(ban_card_list))
            if max_card_num:
                text_parts.append("限数:{}".format(max_card_num))
            text = ",".join(text_parts)
            SIGNAL.PRINT_TO_UI.emit(text=text)

        for i in range(len(quest_list)):
            quest_list[i]["global_plan_active"] = global_plan_active
            quest_list[i]["deck"] = deck
            quest_list[i]["battle_plan_1p"] = battle_plan_1p
            quest_list[i]["battle_plan_2p"] = battle_plan_2p

        # 完成任务
        self.battle_1_n_n(quest_list=quest_list)

        # 激活删除物品高危功能(可选) + 领取奖励一次 + 领取普通任务奖励(公会点)一次
        quests = [quest_mode]
        if quest_mode == "公会任务":
            quests.append("普通任务")
            self.batch_level_2_action(dark_crystal=False)

        SIGNAL.PRINT_TO_UI.emit(text=f"[{text_}] 检查领取奖励中...")
        self.batch_receive_all_quest_rewards(player=[1, 2], quests=quests)

        self.model_end_print(text=text_)

    def guild_dungeon(self, text_, global_plan_active, deck, battle_plan_1p, battle_plan_2p):

        self.model_start_print(text=text_)
        if self.faa_dict[1].channel == self.faa_dict[2].channel:
            SIGNAL.PRINT_TO_UI.emit(text=f"[{text_}] 仅有一位角色, 即将强制跳过本步骤!", color_level=1)
            self.model_end_print(text=text_)
            return

        SIGNAL.PRINT_TO_UI.emit(text=f"[{text_}] 开始[多本轮战]...")

        quest_list = []

        for i in range(3):
            quest_list.append({
                "deck": deck,
                "player": [2, 1],
                "need_key": True,
                "global_plan_active": global_plan_active,
                "battle_plan_1p": battle_plan_1p,
                "battle_plan_2p": battle_plan_2p,
                "stage_id": "GD-0-" + str(i + 1),
                "max_times": 3,
                "dict_exit": {
                    "other_time_player_a": [],
                    "other_time_player_b": [],
                    "last_time_player_a": ["竞技岛"],
                    "last_time_player_b": ["竞技岛"]}
            })

        self.battle_1_n_n(quest_list=quest_list)

        self.model_end_print(text=text_)

    """高级模式"""

    def task_sequence(self, text_, task_begin_id: int, task_sequence_index: int):
        """
        自定义任务序列
        :param text_: 其实是title
        :param task_begin_id: 从第几号任务开始
        :param task_sequence_index: 任务序列的索引号(暂未使用uuid)
        :return:
        """

        def merge_continuous_battle_task(task_sequence: list):
            """将任务序列中, 连续的独立战斗事项完整合并"""
            task_list = []
            battle_dict = {
                "task_type": "战斗",
                "task_args": []
            }
            for task in task_sequence:
                if task["task_type"] == "战斗":
                    task["task_args"]["battle_id"] = task["task_id"]
                    battle_dict["task_args"].append(task["task_args"])
                else:
                    # 出现非战斗事项
                    if battle_dict["task_args"]:
                        task_list.append(battle_dict)
                        battle_dict = {
                            "task_type": "战斗",
                            "task_args": []
                        }
                    task_list.append(task)
            # 保存末位战斗
            if battle_dict["task_args"]:
                task_list.append(battle_dict)

            return task_list

        def normal_battle_task_to_d_thread(task_sequence):
            """
            将自定义任务序列中完成合并的 连续的 战斗任务, 智能拆分组合 为连续的多线程单人 或 单线程 战斗任务
            原则: 连续且仅有1p2p单独参与的任务, 将被智能分配到多线程单人. 且 无视12p之间的前后任务顺序!
            :param task_sequence:
            :return:
            """

            def to_double_thread_args(quest_info_list):
                solo_quests_1 = []
                solo_quests_2 = []
                for quest_info_solo in quest_info_list:
                    if quest_info_solo["player"] == [1]:
                        solo_quests_1.append(quest_info_solo)
                    if quest_info_solo["player"] == [2]:
                        solo_quests_2.append(quest_info_solo)
                return {
                    "solo_quests_1": solo_quests_1,
                    "solo_quests_2": solo_quests_2
                }

            new_task_list = []
            for task in task_sequence:
                # 非战斗任务事项不变
                if task["task_type"] != "战斗":
                    new_task_list.append(task)
                else:
                    p1_active = False
                    p2_active = False
                    thread_1_task_list = []
                    thread_2_task_list = []
                    unknown_task_list = []

                    new_task_list = []
                    for quest_info in task["task_args"]:
                        if len(quest_info["player"]) == 2:
                            if thread_2_task_list:
                                new_task_list.append({
                                    "task_type": "战斗-多线程",
                                    "task_args": to_double_thread_args(quest_info_list=thread_2_task_list)
                                })
                                thread_2_task_list = []
                            thread_1_task_list += unknown_task_list
                            thread_1_task_list.append(quest_info)
                            unknown_task_list = []
                            p1_active = False
                            p2_active = False

                        if len(quest_info["player"]) == 1:
                            if quest_info["player"] == [1]:
                                p1_active = True
                            if quest_info["player"] == [2]:
                                p2_active = True
                            if p1_active and p2_active:
                                if thread_1_task_list:
                                    new_task_list.append({
                                        "task_type": "战斗",
                                        "task_args": thread_1_task_list
                                    })
                                    thread_1_task_list = []
                                thread_2_task_list += unknown_task_list
                                thread_2_task_list.append(quest_info)
                                unknown_task_list = []
                            else:
                                unknown_task_list.append(quest_info)
                    # 收尾工作
                    if unknown_task_list:
                        new_task_list.append({
                            "task_type": "战斗",
                            "task_args": thread_1_task_list + unknown_task_list
                        })
                    else:
                        if thread_1_task_list:
                            new_task_list.append({
                                "task_type": "战斗",
                                "task_args": thread_1_task_list
                            })
                        if thread_2_task_list:
                            new_task_list.append({
                                "task_type": "战斗-多线程",
                                "task_args": to_double_thread_args(quest_info_list=thread_2_task_list)
                            })

            return new_task_list

        def read_json_to_task_sequence():
            task_sequence_list = get_task_sequence_list(with_extension=True)
            task_sequence_path = "{}\\{}".format(
                PATHS["task_sequence"],
                task_sequence_list[task_sequence_index]
            )

            with EXTRA.FILE_LOCK:
                with open(file=task_sequence_path, mode="r", encoding="UTF-8") as file:
                    data = json.load(file)

            return data

        def main():
            self.model_start_print(text=text_)

            # 读取json文件
            task_sequence = read_json_to_task_sequence()

            # 获取最大task_id
            max_tid = 1
            for quest in task_sequence:
                max_tid = max(max_tid, quest["task_id"])

            if task_begin_id > max_tid:
                SIGNAL.PRINT_TO_UI.emit(text=f"[{text_}] 开始事项id > 该方案最高id! 将直接跳过!")
                return

            # 由于任务id从1开始, 故需要减1
            # 去除序号小于stage_begin的任务
            task_sequence = [task for task in task_sequence if task["task_id"] >= task_begin_id]

            # 根据战斗和其他事项拆分 让战斗事项的参数构成 n本 n次 为一组的汇总
            task_sequence = merge_continuous_battle_task(task_sequence=task_sequence)

            # 让战斗事项按 多线程单人 和 单线程常规 拆分
            task_sequence = normal_battle_task_to_d_thread(task_sequence=task_sequence)

            CUS_LOGGER.debug(f"自定义任务序列, 已完成全部处理, 结果: {task_sequence}")

            for task in task_sequence:

                match task["task_type"]:

                    case "战斗":
                        self.battle_1_n_n(
                            quest_list=task["task_args"],
                            extra_title=text_
                        )
                    case "战斗-多线程":
                        self.signal_start_todo_2_battle.emit({
                            "quest_list": task["task_args"]["solo_quests_2"],
                            "extra_title": f"{text_}] [多线程单人",
                            "need_lock": True
                        })
                        self.battle_1_n_n(
                            quest_list=task["task_args"]["solo_quests_1"],
                            extra_title=f"{text_}] [多线程单人",
                            need_lock=True)

                    case "双暴卡":
                        self.batch_use_items_double_card(
                            player=task["task_args"]["player"],
                            max_times=task["task_args"]["max_times"]
                        )

                    case "刷新游戏":
                        self.batch_reload_game(
                            player=task["task_args"]["player"],
                        )

                    case "清背包":
                        self.batch_level_2_action(
                            player=task["task_args"]["player"],
                            dark_crystal=False
                        )

                    case "领取任务奖励":
                        all_quests = {
                            "normal": "普通任务",
                            "guild": "公会任务",
                            "spouse": "情侣任务",
                            "offer_reward": "悬赏任务",
                            "food_competition": "美食大赛",
                            "monopoly": "大富翁",
                            "camp": "营地任务"
                        }
                        self.batch_receive_all_quest_rewards(
                            player=task["task_args"]["player"],
                            quests=[v for k, v in all_quests.items() if task["task_args"][k]]
                        )

            # 战斗结束
            self.model_end_print(text=text_)

        return main()

    def auto_food(self):

        def a_round():
            """
            一轮美食大赛战斗
            :return: 是否还有任务在美食大赛中
            """

            # 两个号分别读取任务
            quest_list_1 = self.faa_dict[1].match_quests(mode="美食大赛-新")
            quest_list_2 = self.faa_dict[2].match_quests(mode="美食大赛-新")
            quest_list = quest_list_1 + quest_list_2

            if not quest_list:
                return False

            # 去重两边都一毛一样的双人任务
            unique_data = []
            for quest in quest_list:
                if quest not in unique_data:
                    unique_data.append(quest)
            quest_list = unique_data

            # 初始化尝试次数记录
            for quest in quest_list:
                quest_key = (str(quest["player"]), quest["quest_text"])
                if quest_key not in self.auto_food_stage_ban_dict.keys():
                    self.auto_food_stage_ban_dict[quest_key] = 0

            # 去除尝试过多的任务
            quest_list_will_do = []
            for quest in quest_list:
                if self.auto_food_stage_ban_dict[(str(quest["player"]), quest["quest_text"])] < 3:
                    quest_list_will_do.append(quest)
                else:
                    quest["tag"] = "禁用, 尝试过多"

            CUS_LOGGER.debug(self.auto_food_stage_ban_dict)
            CUS_LOGGER.debug("[全自动大赛] 去除 **多次尝试禁用** 任务后, 列表如下:")
            CUS_LOGGER.debug(quest_list_will_do)

            # 全部单人任务
            solo_quests = [quest for quest in quest_list_will_do if len(quest["player"]) == 1]
            # 全部双人任务
            multi_player_quests = [quest for quest in quest_list_will_do if len(quest["player"]) > 1]

            if solo_quests:
                quest_list_will_do = solo_quests if solo_quests else multi_player_quests
                for quest in multi_player_quests:
                    quest["tag"] = "暂时跳过, 先做单人任务"
            else:
                if multi_player_quests:
                    quest_list_will_do = multi_player_quests
                    # 找到 stage_id 最小的任务, 并只执行该关卡对应的双人任务, 以减少次数
                    min_stage_id = quest_list_will_do[0]["stage_id"]
                    quest_list_min_stage_id = [
                        quest for quest in quest_list_will_do if quest["stage_id"] == min_stage_id]
                    # 找到限制条件最多的任务, 以减少次数
                    quest_list_min_stage_id = [max(
                        quest_list_min_stage_id, key=lambda x: len(x["ban_card_list"]) if x["ban_card_list"] else 0)]
                    # 关卡id更大的任务打tag 先不做它
                    for quest in quest_list_will_do:
                        if quest not in quest_list_min_stage_id:
                            quest["tag"] = "暂时跳过, 先做关卡id小的任务"
                    quest_list_will_do = quest_list_min_stage_id
                else:
                    return False

            # 记录 尝试次数
            for quest in quest_list_will_do:
                quest_key = (str(quest["player"]), quest["quest_text"])
                self.auto_food_stage_ban_dict[quest_key] += 1

            # 生成输出的文本
            texts_list = []
            for i in range(len(quest_list)):
                quest = quest_list[i]

                if len(quest["player"]) == 2:
                    player_text = "组队"
                else:
                    player_text = f"单人{quest["player"][0]}P"

                text_parts = [
                    f"[全自动大赛] 事项{i + 1}",
                    f"{player_text}",
                    f"{quest["stage_id"]}",
                    "用钥匙" if quest["need_key"] else "无钥匙",
                    f"{quest["max_times"]}次",
                ]

                quest_card = quest.get("quest_card", None)
                if quest_card:
                    text_parts.append(f"带卡:{quest_card}")

                ban_card_list = quest.get("ban_card_list", None)
                if ban_card_list:
                    text_parts.append(f"禁卡:{ban_card_list}")

                max_card_num = quest.get("max_card_num", None)
                if max_card_num:
                    text_parts.append(f"限数:{max_card_num}")

                quest_tag = quest.get("tag", "即将执行")
                if "暂时跳过" not in quest_tag:
                    # 输出尝试次数
                    quest_try_times = self.auto_food_stage_ban_dict[(str(quest["player"]), quest["quest_text"])]
                    text_parts.append(f"尝试次数:{quest_try_times}/3")
                text_parts.append(f"{quest_tag}")

                text = ",".join(text_parts)
                texts_list.append(text)

            # 输出识别结果
            SIGNAL.PRINT_TO_UI.emit(text="[全自动大赛] 步骤: 识别任务目标, 已完成, 结果如下:", color_level=2)
            for text in texts_list:
                SIGNAL.PRINT_TO_UI.emit(text=text, color_level=2)

            # 双线程单人 or 单线程双人启动
            if solo_quests:

                solo_quests_1 = [quest for quest in quest_list_will_do if 1 in quest.get('player', [])]
                solo_quests_2 = [quest for quest in quest_list_will_do if 2 in quest.get('player', [])]

                if solo_quests_1 and solo_quests_2:
                    self.signal_start_todo_2_battle.emit({
                        "quest_list": solo_quests_2,
                        "extra_title": "多线程单人] [2P",
                        "need_lock": True
                    })
                    self.battle_1_n_n(
                        quest_list=solo_quests_1,
                        extra_title="多线程单人] [1P",
                        need_lock=True)
                else:
                    self.battle_1_n_n(quest_list=quest_list_will_do)

            else:
                self.battle_1_n_n(quest_list=quest_list_will_do)

            return True

        def auto_food_main():
            text_ = "全自动大赛"
            self.model_start_print(text=text_)

            # 先领一下已经完成的大赛任务
            self.faa_dict[1].action_receive_quest_rewards(mode="美食大赛")
            self.faa_dict[2].action_receive_quest_rewards(mode="美食大赛")

            # 重置美食大赛任务 ban dict
            # 用于防止缺乏钥匙/次数时无限重复某些关卡, key: (player: int, quest_text: str), value: int
            self.auto_food_stage_ban_dict = {}

            i = 0
            while True:
                i += 1
                SIGNAL.PRINT_TO_UI.emit(text=f"[{text_}] 第{i}次循环，开始", color_level=1)

                round_result = a_round()

                SIGNAL.PRINT_TO_UI.emit(text=f"[{text_}] 第{i}次循环，结束", color_level=1)
                if not round_result:
                    break

            SIGNAL.PRINT_TO_UI.emit(text=f"[{text_}] 所有被记录的任务已完成!", color_level=1)

            self.model_end_print(text=text_)

        auto_food_main()

    """使用battle_1_n_n为核心的变种 [双线程][单人]"""

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
                        global_plan_active=my_opt["global_plan_active"],
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
                        "global_plan_active": my_opt["global_plan_active"],
                        "deck": my_opt["deck"],
                        "battle_plan_1p": my_opt["battle_plan_1p"],
                        "battle_plan_2p": my_opt["battle_plan_1p"],
                        "stage_id": "MT-1-" + str(my_opt["stage"]),
                        "max_times": int(my_opt["max_times"]),
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
                "extra_title": "多线程单人] [2P",
                "need_lock": True
            })
            self.battle_1_n_n(
                quest_list=quest_lists[1],
                extra_title="多线程单人] [1P",
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
                                "global_plan_active": my_opt["global_plan_active"],
                                "deck": my_opt["deck"],
                                "battle_plan_1p": my_opt["battle_plan_1p"],
                                "battle_plan_2p": my_opt["battle_plan_1p"],
                                "stage_id": stage,
                                "max_times": 1,
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
                            "global_plan_active": my_opt["global_plan_active"],
                            "deck": my_opt["deck"],
                            "battle_plan_1p": my_opt["battle_plan_1p"],
                            "battle_plan_2p": my_opt["battle_plan_1p"],
                            "stage_id": stage,
                            "max_times": 1,
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
                "extra_title": "多线程单人] [2P",
                "need_lock": True})
            self.battle_1_n_n(
                quest_list=quest_lists[1],
                extra_title="多线程单人] [1P",
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
                        global_plan_active=my_opt["global_plan_active"],
                        deck=my_opt["deck"],
                        battle_plan_1p=my_opt["battle_plan_1p"],
                        battle_plan_2p=my_opt["battle_plan_1p"],
                        dict_exit={
                            "other_time_player_a": [],
                            "other_time_player_b": [],
                            "last_time_player_a": ["回到上一级", "普通红叉"],
                            "last_time_player_b": ["回到上一级", "普通红叉"]
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
                        "global_plan_active": my_opt["global_plan_active"],
                        "deck": my_opt["deck"],
                        "battle_plan_1p": my_opt["battle_plan_1p"],
                        "battle_plan_2p": my_opt["battle_plan_1p"],
                        "stage_id": "PT-0-" + str(my_opt["stage"]),
                        "max_times": 1,
                        "dict_exit": {
                            "other_time_player_a": [],
                            "other_time_player_b": [],
                            "last_time_player_a": ["回到上一级", "普通红叉"],  # "回到上一级","普通红叉" 但之后刷新 所以空
                            "last_time_player_b": ["回到上一级", "普通红叉"],
                        }
                    }
                ]

            # 信号无法使用 具名参数
            self.signal_start_todo_2_battle.emit({
                "quest_list": quest_lists[2],
                "extra_title": "多线程单人] [2P",
                "need_lock": True
            })
            self.battle_1_n_n(
                quest_list=quest_lists[1],
                extra_title="多线程单人] [1P",
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

    """天知强卡器"""

    def tce(self, player: str):
        """
        :param player: "1P" or "2P"
        :return:
        """

        if (not self.opt["tce"]["enhance_card_active"]) and (not self.opt["tce"]["decompose_gem_active"]):
            SIGNAL.PRINT_TO_UI.emit(text="[天知强卡器] 未开启任何功能 不启动!", color_level=1)
            return

        SIGNAL.PRINT_TO_UI.emit(text="尝试召唤天知强卡器, 与FAA签订契约, 成为魔法少女吧!", color_level=1)

        # 启动TCE命名管道线程
        tce_pipe_thread = TCEPipeCommunicationThread()
        tce_pipe_thread.start()

        # 尝试启动强卡器
        path = self.opt["tce"]["tce_path"]
        if not path:
            SIGNAL.DIALOG.emit(
                "前面的功能, 以后再来探索吧!",
                "你还没有天知强卡器哦, 所以说你没有资格呐!\n深渊桑: 没有设置路径! 请在进阶设置完成!")
            return

        tce_sub_process = subprocess.Popen(path, cwd=os.path.dirname(path))
        tce_start_time = datetime.datetime.now()

        # 等待强卡器连接，最多等待三十秒
        for _ in range(30):
            time.sleep(1)
            if tce_pipe_thread.running:
                break
        else:
            # 强卡器连接失败，关掉管道线程
            SIGNAL.DIALOG.emit(
                "天知强卡器召唤失败T_T",
                "和天知强卡器的羁绊还不够!\n深渊桑: 30s内未能建立连接! 请使用v0.4.0+版本的天知强卡器!")
            tce_pipe_thread.stop()

        if player:
            handle = self.faa_dict[1].handle
        else:
            handle = self.faa_dict[2].handle

        if self.opt["tce"]["enhance_card_active"]:
            SIGNAL.PRINT_TO_UI.emit(text="[天知强卡器] 卡片强化开始", color_level=1)
            tce_pipe_thread.enhance_card(handle)
            SIGNAL.PRINT_TO_UI.emit(text="[天知强卡器] 卡片强化完成", color_level=1)

        if self.opt["tce"]["decompose_gem_active"]:
            SIGNAL.PRINT_TO_UI.emit(text="[天知强卡器] 宝石分解开始", color_level=1)
            tce_pipe_thread.decompose_gem(handle)
            SIGNAL.PRINT_TO_UI.emit(text="[天知强卡器] 宝石分解完成", color_level=1)

        # 关闭TCE命名管道线程
        tce_pipe_thread.stop()

        time_passed = datetime.datetime.now() - tce_start_time

        def trans_time_to_str(time_passed):
            # 将时间差转换为天、小时、分钟和秒
            days = time_passed.days
            hours, remainder = divmod(time_passed.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            # 根据时间差的不同部分构建输出字符串
            if days > 0:
                time_str = "{}天{}小时{}分钟{}秒".format(days, hours, minutes, seconds)
            elif hours > 0:
                time_str = "{}小时{}分钟{}秒".format(hours, minutes, seconds)
            elif minutes > 0:
                time_str = "{}分钟{}秒".format(minutes, seconds)
            else:
                time_str = "{}秒".format(seconds)

            return time_str

        time_str = trans_time_to_str(time_passed)

        SIGNAL.PRINT_TO_UI.emit(
            text=f"[天知强卡器] 再见了天知强卡器，希望你喜欢这{time_str}来属于你的戏份",
            color_level=1)

        # 杀死天知强卡器
        parent = psutil.Process(tce_sub_process.pid)
        for child in parent.children(recursive=True):
            child.terminate()
        parent.terminate()
        parent.wait(timeout=5)  # 等待进程终止，超时时间为5秒

    """主要线程"""

    def set_extra_opt_and_start(self, extra_opt):
        self.extra_opt = extra_opt
        self.start()

    def run(self):

        if self.todo_id == 1:
            self.run_1()
        if self.todo_id == 2:
            self.run_2()
        # except Exception as e:
        #     SIGNAL.PRINT_TO_UI.emit(text=f"[Todo] 运行时发生错误! 内容:{e}", color_level=1)
        #     CUS_LOGGER.error(f"[Todo] 运行时发生错误!")

    def run_1(self):
        """配置检查"""

        # 尝试启动360游戏大厅和对应的小号
        self.start_360()

        # 基础参数是否输入正确 输出错误直接当场夹
        if not self.test_args():
            return False

        """单线程作战"""

        # current todo plan option
        c_opt = self.opt_todo_plans

        SIGNAL.PRINT_TO_UI.emit("每一个大类的任务开始前均会重启游戏以防止bug...")

        self.remove_outdated_log_images()

        """主要任务"""

        main_task_1p_active = False
        main_task_1p_active = main_task_1p_active or c_opt["sign_in"]["active"]
        main_task_1p_active = main_task_1p_active or c_opt["fed_and_watered"]["active"]
        main_task_1p_active = main_task_1p_active or c_opt["use_double_card"]["active"]
        main_task_1p_active = main_task_1p_active or c_opt["warrior"]["active"]
        main_task_2p_active = False
        main_task_2p_active = main_task_2p_active or c_opt["customize"]["active"]
        main_task_2p_active = main_task_2p_active or c_opt["normal_battle"]["active"]
        main_task_2p_active = main_task_2p_active or c_opt["offer_reward"]["active"]
        main_task_2p_active = main_task_2p_active or c_opt["cross_server"]["active"]
        main_task_3p_active = False
        main_task_3p_active = main_task_3p_active or c_opt["quest_guild"]["active"]
        main_task_3p_active = main_task_3p_active or c_opt["guild_dungeon"]["active"]
        main_task_3p_active = main_task_3p_active or c_opt["quest_spouse"]["active"]
        main_task_3p_active = main_task_3p_active or c_opt["relic"]["active"]
        main_task_4p_active = False
        main_task_4p_active = main_task_4p_active or c_opt["magic_tower_alone_1"]["active"]
        main_task_4p_active = main_task_4p_active or c_opt["magic_tower_alone_2"]["active"]
        main_task_4p_active = main_task_4p_active or c_opt["magic_tower_prison_1"]["active"]
        main_task_4p_active = main_task_4p_active or c_opt["magic_tower_prison_2"]["active"]
        main_task_4p_active = main_task_4p_active or c_opt["magic_tower_double"]["active"]
        main_task_4p_active = main_task_4p_active or c_opt["pet_temple_1"]["active"]
        main_task_4p_active = main_task_4p_active or c_opt["pet_temple_2"]["active"]
        main_task_active = main_task_1p_active or main_task_2p_active or main_task_3p_active or main_task_4p_active

        if main_task_active:
            SIGNAL.PRINT_TO_UI.emit("", is_line=True, line_type="bottom")
            SIGNAL.PRINT_TO_UI.emit(text="[主要任务] 开始!", color_level=1)
            SIGNAL.PRINT_TO_UI.emit("", is_line=True, line_type="top")
            start_time = datetime.datetime.now()

        if main_task_1p_active:
            self.batch_reload_game()

            my_opt = c_opt["sign_in"]
            if my_opt["active"]:
                player = [1, 2] if my_opt["is_group"] else [1]
                # 删除物品高危功能(可选) + 领取奖励一次
                self.batch_level_2_action(dark_crystal=False)
                # 领取温馨礼包
                self.batch_get_warm_gift(player=player)
                # 日氪
                self.batch_top_up_money(player=player)
                # 常规日常签到
                self.batch_sign_in(player=player)

            my_opt = c_opt["fed_and_watered"]
            if my_opt["active"]:
                self.batch_fed_and_watered(
                    player=[1, 2] if my_opt["is_group"] else [1]
                )

            my_opt = c_opt["use_double_card"]
            if my_opt["active"]:
                self.batch_use_items_double_card(
                    player=[1, 2] if my_opt["is_group"] else [1],
                    max_times=my_opt["max_times"],
                )

            my_opt = c_opt["warrior"]
            if my_opt["active"]:
                self.easy_battle(
                    text_="勇士挑战",
                    stage_id=f"WA-0-{my_opt["stage"]}",
                    player=[2, 1] if my_opt["is_group"] else [1],
                    max_times=int(my_opt["max_times"]),
                    global_plan_active=my_opt["global_plan_active"],
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

        if main_task_2p_active:
            self.batch_reload_game()

            my_opt = c_opt["customize"]
            if my_opt["active"]:
                self.task_sequence(
                    text_="自定义任务序列",
                    task_begin_id=my_opt["stage"],
                    task_sequence_index=my_opt["battle_plan_1p"])

            my_opt = c_opt["normal_battle"]
            if my_opt["active"]:
                self.easy_battle(
                    text_="常规刷本",
                    stage_id=my_opt["stage"],
                    player=[2, 1] if my_opt["is_group"] else [1],
                    max_times=int(my_opt["max_times"]),
                    global_plan_active=my_opt["global_plan_active"],
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
                    global_plan_active=my_opt["global_plan_active"],
                    deck=my_opt["deck"],
                    max_times_1=my_opt["max_times_1"],
                    max_times_2=my_opt["max_times_2"],
                    max_times_3=my_opt["max_times_3"],
                    max_times_4=my_opt["max_times_4"],
                    battle_plan_1p=my_opt["battle_plan_1p"],
                    battle_plan_2p=my_opt["battle_plan_2p"])

            my_opt = c_opt["cross_server"]
            if my_opt["active"]:
                self.easy_battle(
                    text_="跨服副本",
                    stage_id=my_opt["stage"],
                    player=[1, 2] if my_opt["is_group"] else [1],
                    max_times=int(my_opt["max_times"]),
                    global_plan_active=my_opt["global_plan_active"],
                    deck=my_opt["deck"],
                    battle_plan_1p=my_opt["battle_plan_1p"],
                    battle_plan_2p=my_opt["battle_plan_2p"],
                    dict_exit={
                        "other_time_player_a": [],
                        "other_time_player_b": [],
                        "last_time_player_a": ["竞技岛"],
                        "last_time_player_b": ["竞技岛"]
                    })

        if main_task_3p_active:
            self.batch_reload_game()

            if c_opt["quest_guild"]["active"]:
                self.guild_or_spouse_quest(
                    text_="公会任务",
                    quest_mode="公会任务",
                    global_plan_active=c_opt["quest_guild"]["global_plan_active"],
                    deck=c_opt["quest_guild"]["deck"],
                    battle_plan_1p=c_opt["quest_guild"]["battle_plan_1p"],
                    battle_plan_2p=c_opt["quest_guild"]["battle_plan_2p"],
                    stage=c_opt["quest_guild"]["stage"])

            if c_opt["guild_dungeon"]["active"]:
                self.guild_dungeon(
                    text_="公会副本",
                    global_plan_active=c_opt["quest_guild"]["global_plan_active"],
                    deck=c_opt["quest_guild"]["deck"],
                    battle_plan_1p=c_opt["quest_guild"]["battle_plan_1p"],
                    battle_plan_2p=c_opt["quest_guild"]["battle_plan_2p"])

            if c_opt["quest_spouse"]["active"]:
                self.guild_or_spouse_quest(
                    text_="情侣任务",
                    quest_mode="情侣任务",
                    global_plan_active=c_opt["quest_guild"]["global_plan_active"],
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
                    global_plan_active=my_opt["global_plan_active"],
                    deck=my_opt["deck"],
                    battle_plan_1p=my_opt["battle_plan_1p"],
                    battle_plan_2p=my_opt["battle_plan_2p"],
                    dict_exit={
                        "other_time_player_a": [],
                        "other_time_player_b": [],
                        "last_time_player_a": ["竞技岛"],
                        "last_time_player_b": ["竞技岛"]
                    })

        if main_task_4p_active:
            self.batch_reload_game()

            self.alone_magic_tower()

            self.alone_magic_tower_prison()

            self.pet_temple()

            my_opt = c_opt["magic_tower_double"]
            if my_opt["active"]:
                self.easy_battle(
                    text_="魔塔双人",
                    stage_id="MT-2-" + str(my_opt["stage"]),
                    player=[2, 1],
                    max_times=int(my_opt["max_times"]),
                    global_plan_active=my_opt["global_plan_active"],
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

        if main_task_active:
            SIGNAL.PRINT_TO_UI.emit(text="", is_line=True, line_type="bottom")
            SIGNAL.PRINT_TO_UI.emit(
                text=f"[主要任务] 全部完成! 耗时:{str(datetime.datetime.now() - start_time).split('.')[0]}",
                color_level=1)
            SIGNAL.PRINT_TO_UI.emit(text="", is_line=True, line_type="top")

        """额外任务"""

        extra_active = False
        extra_active = extra_active or c_opt["receive_awards"]["active"]
        extra_active = extra_active or c_opt["use_items"]["active"]
        extra_active = extra_active or c_opt["auto_food"]["active"]
        # 循环任务
        extra_active = extra_active or c_opt["tce"]["active"]
        extra_active = extra_active or c_opt["loop_cross_server"]["active"]

        if extra_active:
            SIGNAL.PRINT_TO_UI.emit(text="", is_line=True, line_type="bottom")
            SIGNAL.PRINT_TO_UI.emit(text=f"[额外任务] 开始!", color_level=1)
            SIGNAL.PRINT_TO_UI.emit(text="", is_line=True, line_type="top")

        if extra_active:
            self.batch_reload_game()
            start_time = datetime.datetime.now()

        my_opt = c_opt["receive_awards"]
        if my_opt["active"]:
            # 扫描公会
            self.batch_scan_guild_info()

            # 删除物品高危功能
            self.batch_level_2_action(dark_crystal=True)

            # 主要函数
            self.batch_receive_all_quest_rewards(
                player=[1, 2] if my_opt["is_group"] else [1],
                quests=["普通任务", "美食大赛", "大富翁"],
            )

        my_opt = c_opt["use_items"]
        if my_opt["active"]:
            self.batch_use_items_consumables(
                player=[1, 2] if my_opt["is_group"] else [1],
            )

        my_opt = c_opt["auto_food"]
        if my_opt["active"]:
            self.auto_food()

        my_opt = c_opt["loop_cross_server"]
        if my_opt["active"]:
            self.batch_loop_cross_server(
                player=[1, 2] if my_opt["is_group"] else [1],
                deck=c_opt["quest_guild"]["deck"])

        my_opt = c_opt["tce"]
        if my_opt["active"]:
            self.tce(
                player=my_opt["player"]
            )

        if extra_active:
            SIGNAL.PRINT_TO_UI.emit(text="", is_line=True, line_type="bottom")
            SIGNAL.PRINT_TO_UI.emit(
                text=f"[额外任务] 全部完成! 耗时:{str(datetime.datetime.now() - start_time).split('.')[0]}",
                color_level=1)
            SIGNAL.PRINT_TO_UI.emit(text="", is_line=True, line_type="top")

        """自建房战斗"""

        active_singleton = False
        active_singleton = active_singleton or c_opt["customize_battle"]["active"]

        if active_singleton:
            SIGNAL.PRINT_TO_UI.emit("", is_line=True, line_type="bottom")
            SIGNAL.PRINT_TO_UI.emit(text="[自建房战斗] 开始!", color_level=1)
            SIGNAL.PRINT_TO_UI.emit("", is_line=True, line_type="top")
            SIGNAL.PRINT_TO_UI.emit(text="如出现错误, 务必确保该功能是单独启动的!")
            start_time = datetime.datetime.now()

        my_opt = c_opt["customize_battle"]
        if my_opt["active"]:
            self.easy_battle(
                text_="自建房战斗",
                stage_id=my_opt["stage"],
                player=[[1, 2], [2, 1], [1], [2]][my_opt["is_group"]],
                max_times=int(my_opt["max_times"]),
                global_plan_active=my_opt["global_plan_active"],
                deck=my_opt["deck"],
                battle_plan_1p=my_opt["battle_plan_1p"],
                battle_plan_2p=my_opt["battle_plan_2p"],
                dict_exit={
                    "other_time_player_a": [],
                    "other_time_player_b": [],
                    "last_time_player_a": [],
                    "last_time_player_b": []
                },
                is_cu=True
            )

        if active_singleton:
            SIGNAL.PRINT_TO_UI.emit(text="", is_line=True, line_type="bottom")
            SIGNAL.PRINT_TO_UI.emit(
                text=f"[自建房战斗] 全部完成! 耗时:{str(datetime.datetime.now() - start_time).split('.')[0]}",
                color_level=1)
            SIGNAL.PRINT_TO_UI.emit(text="", is_line=True, line_type="top")

        """完成FAA的任务列表后，开始执行插件脚本"""
        name_1p = self.opt["base_settings"]["name_1p"]
        if name_1p == '':
            name_1p = self.opt['base_settings']['game_name']
        else:
            name_1p = name_1p + ' | ' + self.opt['base_settings']['game_name']

        name_2p = self.opt["base_settings"]["name_2p"]
        if name_2p == '':
            name_2p = self.opt['base_settings']['game_name']
        else:
            name_2p = name_2p + ' | ' + self.opt['base_settings']['game_name']

        scripts = self.opt["extension"]["scripts"]
        # 这块本来就是多线程执行的，所以不需要再用线程，不会阻塞FAA的
        for script in scripts:
            SIGNAL.PRINT_TO_UI.emit(text=f"开始执行插件脚本 {script['name']}: {script['path']}", color_level=2)
            player = script['player']

            if player == 1:
                for _ in range(script['repeat']):
                    execute(name_1p, script['path'])
            elif player == 2:
                for _ in range(script['repeat']):
                    execute(name_2p, script['path'])
            elif player == 3:
                for _ in range(script['repeat']):
                    execute(name_1p, script['path'])
                for _ in range(script['repeat']):
                    execute(name_2p, script['path'])

            SIGNAL.PRINT_TO_UI.emit(text=f"插件脚本 {script['name']}: {script['path']} 执行结束", color_level=2)

        SIGNAL.PRINT_TO_UI.emit(text=f"所有插件脚本均已执行结束", color_level=1)

        """全部完成"""

        if main_task_active or extra_active:
            if self.opt["login_settings"]["login_close_settings"]:
                SIGNAL.PRINT_TO_UI.emit(
                    text="[开关游戏大厅] 任务全部完成, 关闭360游戏大厅对应窗口, 降低系统负载.",
                    color_level=1
                )
                self.close_360()
            else:
                if self.opt["advanced_settings"]["end_exit_game"]:
                    SIGNAL.PRINT_TO_UI.emit(text="任务全部完成, 刷新返回登录界面, 降低系统负载.", color_level=1)
                    self.batch_click_final_refresh_btn()
                else:
                    SIGNAL.PRINT_TO_UI.emit(
                        text="[推荐] 进阶功能中, 可设置完成所有任务后, 关闭360游戏大厅对应窗口 or 返回登录页, 降低系统负载.",
                        color_level=1)
        else:
            if active_singleton:
                SIGNAL.PRINT_TO_UI.emit(
                    text="您启动了完成后操作, 但仅运行了自建房对战, 故不进行任何操作",
                    color_level=1)
            else:
                SIGNAL.PRINT_TO_UI.emit(text="您启动了完成后操作, 但并未运行任务, 故不进行任何操作", color_level=1)

        # 全部完成了发个信号
        SIGNAL.END.emit()

        return True

    def start_360(self):

        handles = {
            1: faa_get_handle(channel=self.faa_dict[1].channel, mode="360"),
            2: faa_get_handle(channel=self.faa_dict[2].channel, mode="360")
        }

        def start_one(pid, game_id, account_id, executable_path, wait_sleep_time):

            if not ((handles[pid] is None) or (handles[pid] == 0)):
                return

            if account_id == 0:
                return

            args = ["-action:opengame", f"-gid:{game_id}", f"-gaid:{account_id}"]
            start_software_with_args(executable_path, *args)
            self.sleep(wait_sleep_time)

            SIGNAL.PRINT_TO_UI.emit(text=f"[控制游戏大厅] {pid}P游戏大厅已启动.", color_level=1)

        if not self.opt["login_settings"]["login_open_settings"]:
            return

        only_one_role = (
                self.opt["login_settings"]["first_num"] == self.opt["login_settings"]["second_num"] or
                self.opt["base_settings"]["name_1p"] == self.opt["base_settings"]["name_2p"]
        )

        # 所有需要开启的窗口都已经开启
        if (handles[1] is not None) and (handles[1] != 0):
            if not only_one_role:
                if (handles[2] is not None) and (handles[2] != 0):
                    SIGNAL.PRINT_TO_UI.emit(
                        text="[控制游戏大厅] 已激活本功能, 但检测到所有窗口均已开启, 跳过步骤~",
                        color_level=1
                    )
                    return False

        SIGNAL.PRINT_TO_UI.emit(
            text="[控制游戏大厅] 已激活本功能, 且有若干小号窗口未开启, 开始执行...",
            color_level=1
        )

        start_one(
            pid=1,
            game_id=1,
            account_id=self.opt["login_settings"]["first_num"],
            executable_path=self.opt["login_settings"]["login_path"],
            wait_sleep_time=1
        )

        if only_one_role:
            # 只有一个小号
            return

        start_one(
            pid=2,
            game_id=1,
            account_id=self.opt["login_settings"]["second_num"],
            executable_path=self.opt["login_settings"]["login_path"],
            wait_sleep_time=5
        )

    def close_360(self):

        for faa in self.faa_dict.values():
            # 关闭所有小号窗口
            window_title = faa.channel
            CUS_LOGGER.debug(f"[操作游戏大厅] 关闭名称为: [{window_title}] 的窗口, 开始")
            close_software_by_title(window_title=window_title)
            time.sleep(1)
            CUS_LOGGER.debug(f"[操作游戏大厅] 关闭名称为: [{window_title}] 的窗口, 成功")

        _, sub_window_titles = get_path_and_sub_titles()

        if len(sub_window_titles) == 1 and sub_window_titles[0] == "360游戏大厅":
            # 只有一个360大厅主窗口, 鲨了它
            window_title = "360游戏大厅"
            CUS_LOGGER.debug(f"[操作游戏大厅] 关闭名称为: [{window_title}] 的窗口, 开始")
            close_software_by_title("360游戏大厅")
            CUS_LOGGER.debug(f"[操作游戏大厅] 关闭名称为: [{window_title}] 的窗口, 成功")
            # 等待悄悄打开的360后台 准备一网打尽
            time.sleep(2)

        if len(sub_window_titles) == 0:
            # 不再有窗口了, 可以直接根据软件名称把后台杀干净
            software_name = "360Game.exe"
            CUS_LOGGER.debug(f"[操作游戏大厅] 关闭名称为: [{software_name}] 的应用程序下的所有窗口, 开始")
            close_all_software_by_name(software_name=software_name)
            CUS_LOGGER.debug(f"[操作游戏大厅] 关闭名称为: [{software_name}] 的应用程序下的所有窗口, 成功")

    def test_args(self):
        """防呆测试"""
        handles = {
            1: faa_get_handle(channel=self.faa_dict[1].channel, mode="360"),
            2: faa_get_handle(channel=self.faa_dict[2].channel, mode="360")}
        for player, handle in handles.items():
            if handle is None or handle == 0:
                # 报错弹窗
                SIGNAL.DIALOG.emit(
                    "出错！(╬◣д◢)",
                    f"{player}P存在错误的窗口名或游戏名称, 请在基础设定处重新拖拽至游戏窗口后保存重启.")
                # 强制夹断
                return False
        SIGNAL.PRINT_TO_UI.emit(text=f"[检测重要参数] 所有小号窗口已开启, 继续进行...", color_level=1)
        return True

    def run_2(self):
        """多线程作战时的第二线程, 负责2P"""

        self.battle_1_n_n(
            quest_list=self.extra_opt["quest_list"],
            extra_title=self.extra_opt["extra_title"],
            need_lock=self.extra_opt["need_lock"])
        self.extra_opt = None
