import json
import sys
from time import sleep

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication

from function.common.thread_with_exception import ThreadWithException
from function.script.scattered.get_channel_name import get_channel_name
from function.script.service.common import FAA
from function.script.service.common_multiplayer import invite
from function.script.ui.ui_1_load_opt import MyMainWindow1


class Todo(QThread):
    # 初始化向外发射信号
    sin_out = pyqtSignal(str)
    sin_out_completed = pyqtSignal()

    def __init__(self, faa_1, faa_2, opt):
        super().__init__()
        self.faa_1 = faa_1
        self.faa_2 = faa_2
        self.opt = opt
        self.thread_1p = None
        self.thread_2p = None

    def n_battle(
            self, is_group,
            stage_id, max_times,
            deck, battle_plan_1p, battle_plan_2p,
            task_card, list_ban_card, dict_exit):
        """[单本轮战]1次 副本外 → 副本内n次战斗 → 副本外"""

        self.sin_out.emit("[单本轮战]目标副本:{}".format(stage_id))

        # 填入战斗方案和关卡信息
        self.faa_1.get_config_for_battle(is_group=is_group, battle_plan_index=battle_plan_1p, stage_id=stage_id)
        if is_group:
            self.faa_2.get_config_for_battle(is_group=is_group, battle_plan_index=battle_plan_2p, stage_id=stage_id)

        # 检查人物等级 不组队检查1P 组队还额外检查2P
        if not self.faa_1.check_level():
            self.sin_out.emit("[单本轮战]1P等级不足, 跳过")
            return False
        if is_group:
            if not self.faa_2.check_level():
                self.sin_out.emit("[单本轮战]2P等级不足, 跳过")
                return False

        if not is_group:
            # 单人前往副本
            self.faa_1.action_goto_stage(room_creator=True)
        else:
            # 多人前往副本
            while True:
                self.faa_1.action_goto_stage(room_creator=False)
                self.faa_2.action_goto_stage(room_creator=True)
                sleep(3)
                if invite(self.faa_2, self.faa_1):
                    break
                else:
                    self.sin_out.emit("[单本轮战]服务器抽风,进入竞技岛,重新邀请...")
                    self.faa_1.action_exit(exit_mode=3)
                    self.faa_2.action_exit(exit_mode=3)

        # 轮次作战
        for i in range(max_times):
            self.sin_out.emit("[单本轮战]第{}次,开始".format(i + 1))

            # 创建战斗进程 -> 开始进程
            self.thread_1p = ThreadWithException(target=self.faa_1.action_round_of_game,
                                                 name="1P Thread",
                                                 kwargs={
                                                     "delay_start": False,
                                                     "battle_mode": 0,
                                                     "task_card": task_card,
                                                     "list_ban_card": list_ban_card,
                                                     "deck": deck
                                                 })
            self.thread_1p.start()
            if is_group:
                self.thread_2p = ThreadWithException(target=self.faa_2.action_round_of_game,
                                                     name="2P Thread",
                                                     kwargs={
                                                         "delay_start": True,
                                                         "battle_mode": 0,
                                                         "task_card": task_card,
                                                         "list_ban_card": list_ban_card,
                                                         "deck": deck
                                                     })
                self.thread_2p.start()

            # 阻塞进程让进程执行完再继续本循环函数
            self.thread_1p.join()
            if is_group:
                self.thread_2p.join()

            # 最后一次的退出方式不同
            if i + 1 == max_times:
                for j in dict_exit["last_time"]:
                    self.faa_1.action_exit(exit_mode=j)
                    if is_group:
                        self.faa_2.action_exit(exit_mode=j)
            else:
                for j in dict_exit["other_time"]:
                    self.faa_1.action_exit(exit_mode=j)
                    if is_group:
                        self.faa_2.action_exit(exit_mode=j)

            self.sin_out.emit("[单本轮战] 第{}次, 结束\n".format(i + 1))

    def n_n_battle(
            self, task_list, list_type):
        """
        [多本战斗]n次 副本外→副本内n次战斗→副本外
        :param task_list: 任务清单
        :param list_type: 打哪些类型的副本 比如 ["NO","CS"]
        """
        # 遍历完成每一个任务
        for i in range(len(task_list)):
            task = task_list[i]
            # 判断不打的任务
            if task["stage_id"].split("-")[0] in list_type:
                self.sin_out.emit(
                    "[多本轮战]任务{},组队:{},目标地点:{},次数:{},额外带卡:{},Ban卡:{}".format(
                        i + 1,
                        "是" if task["battle_plan_2p"] else "否",
                        task["stage_id"],
                        task["max_times"],
                        task["task_card"],
                        task["list_ban_card"]))

                self.n_battle(
                    stage_id=task["stage_id"],
                    max_times=task["max_times"],
                    deck=task["deck"],
                    is_group=task["is_group"],
                    battle_plan_1p=task["battle_plan_1p"],
                    battle_plan_2p=task["battle_plan_2p"],
                    task_card=task["task_card"],
                    list_ban_card=task["list_ban_card"],
                    dict_exit=task["dict_exit"])
            else:
                self.sin_out.emit(
                    "[多本轮战]任务{},组队:{},目标地点:{},次数:{},额外带卡:{},Ban卡:{},不打的地图类型,skip\n".format(
                        i + 1,
                        "是" if task["battle_plan_2p"] else "否",
                        task["stage_id"],
                        task["max_times"],
                        task["task_card"],
                        task["list_ban_card"]))
                continue

    def double_task(
            self, text_, task_type,
            deck, battle_plan_1p, battle_plan_2p, ):
        """完成公会or情侣任务"""

        self.sin_out.emit("{}Link Start!\n".format(text_))

        self.sin_out.emit("{}检查领取奖励中...\n".format(text_))
        self.faa_1.action_task_receive_rewards(task_type=task_type)
        self.faa_2.action_task_receive_rewards(task_type=task_type)

        self.sin_out.emit("{}开始获取任务列表".format(text_))
        task_list = self.faa_1.action_get_task(target=task_type)

        for i in task_list:
            self.sin_out.emit("副本:{},额外带卡:{}".format(i["stage_id"], i["task_card"]))

        for i in range(len(task_list)):
            task_list[i]["deck"] = deck
            task_list[i]["battle_plan_1p"] = battle_plan_1p
            task_list[i]["battle_plan_2p"] = battle_plan_2p

        self.sin_out.emit("{}已取得任务,开始[多本轮战]...".format(text_))
        self.n_n_battle(task_list=task_list, list_type=["NO"])

        self.sin_out.emit("{}检查领取奖励中...\n".format(text_))
        self.faa_1.action_task_receive_rewards(task_type=task_type)
        self.faa_2.action_task_receive_rewards(task_type=task_type)

        self.sin_out.emit("{}Completed!\n".format(text_))

    def double_offer_reward(
            self, text_,
            deck, battle_plan_1p, battle_plan_2p):
        self.sin_out.emit("{}Link Start!\n".format(text_))
        # 战斗开始
        self.sin_out.emit("{}开始[多本轮战]...".format(text_))
        task_list = [
            {
                "deck": deck,
                "is_group": True,
                "battle_plan_1p": battle_plan_1p,
                "battle_plan_2p": battle_plan_2p,
                "stage_id": "OR-1-0",
                "max_times": 1,
                "task_card": "None",
                "list_ban_card": [],
                "dict_exit": {"other_time": [0], "last_time": [3]}
            }, {
                "deck": deck,
                "is_group": True,
                "battle_plan_1p": battle_plan_1p,
                "battle_plan_2p": battle_plan_2p,
                "stage_id": "OR-2-0",
                "max_times": 1,
                "task_card": "None",
                "list_ban_card": [],
                "dict_exit": {"other_time": [0], "last_time": [3]}
            }, {
                "deck": deck,
                "is_group": True,
                "battle_plan_1p": battle_plan_1p,
                "battle_plan_2p": battle_plan_2p,
                "stage_id": "OR-3-0",
                "max_times": 1,
                "task_card": "None",
                "list_ban_card": [],
                "dict_exit": {"other_time": [0], "last_time": [3]}
            }]
        self.n_n_battle(task_list=task_list, list_type=["OR"])
        # 领取奖励
        self.faa_1.action_task_receive_rewards(task_type="offer_reward")
        self.faa_2.action_task_receive_rewards(task_type="offer_reward")
        # 战斗结束
        self.sin_out.emit("{}Completed!\n".format(text_))

    def double_magic_tower(
            self, text_,
            floor, max_times,
            deck, battle_plan_1p, battle_plan_2p):
        self.sin_out.emit("{} Link Start!\n".format(text_))

        # 填入战斗方案和关卡信息
        stage_id = "MT-2-" + str(floor)
        self.faa_1.get_config_for_battle(is_group=True, battle_plan_index=battle_plan_1p, stage_id=stage_id)
        self.faa_2.get_config_for_battle(is_group=True, battle_plan_index=battle_plan_2p, stage_id=stage_id)

        # 轮次作战
        for i in range(max_times):
            self.sin_out.emit("{} 第{}次, 开始".format(text_, i + 1))
            flag_invite_failed = False

            # 前往副本
            while True:
                # 第一次 或 邀请失败后 进入方式不同
                if i == 0 or flag_invite_failed:
                    self.faa_1.action_goto_stage(room_creator=False, mt_first_time=True)
                    self.faa_2.action_goto_stage(room_creator=True, mt_first_time=True)
                else:
                    self.faa_2.action_goto_stage(room_creator=True)

                sleep(3)
                # 尝试要求 如果成功就结束循环 如果失败 退出到竞技岛尝试重新邀请
                if invite(self.faa_2, self.faa_1):
                    break
                else:
                    flag_invite_failed = True
                    self.sin_out.emit("服务器抽风, 尝试进入竞技岛, 并重新进行邀请...")
                    self.faa_2.action_exit(exit_mode=3)
                    self.faa_1.action_exit(exit_mode=3)

            # 创建战斗进程 -> 开始进程 -> 阻塞进程让进程执行完再继续本循环函数
            self.thread_1p = ThreadWithException(target=self.faa_1.action_round_of_game,
                                                 name="1P Thread",
                                                 kwargs={
                                                     "delay_start": False,
                                                     "battle_mode": 0,
                                                     "task_card": "None",
                                                     "list_ban_card": [],
                                                     "deck": deck
                                                 })

            self.thread_2p = ThreadWithException(target=self.faa_2.action_round_of_game,
                                                 name="2P Thread",
                                                 kwargs={
                                                     "delay_start": True,
                                                     "battle_mode": 0,
                                                     "task_card": "None",
                                                     "list_ban_card": [],
                                                     "deck": deck
                                                 })
            self.thread_1p.start()
            self.thread_2p.start()
            self.thread_1p.join()
            self.thread_2p.join()

            # 打完出本
            if i + 1 == max_times:
                # 最后一把
                self.faa_1.action_exit(exit_mode=1)
                self.faa_2.action_exit(exit_mode=2)
            else:
                # 其他次数
                self.faa_1.action_exit(exit_mode=1)
                self.faa_2.action_exit(exit_mode=0)

            self.sin_out.emit("{} 第{}次, 结束\n".format(text_, i + 1))

        self.sin_out.emit("{} Completed!\n".format(text_))

    def alone_magic_tower(
            self, text_,
            floor, max_times,
            deck, battle_plan_1p):
        self.sin_out.emit("{} Link Start!\n".format(text_))

        stage_id = "MT-1-" + str(floor)
        self.faa_1.get_config_for_battle(is_group=False, battle_plan_index=battle_plan_1p, stage_id=stage_id)

        # 轮次作战
        for count_times in range(max_times):

            self.sin_out.emit("{} 第{}次, 开始".format(text_, count_times + 1))

            # 第一次的进入方式不同
            if count_times == 0:
                self.faa_1.action_goto_stage(room_creator=True, mt_first_time=True)
            else:
                self.faa_1.action_goto_stage(room_creator=True)

            # 创建战斗进程 -> 开始进程 -> 阻塞进程让进程执行完再继续本循环函数
            self.thread_1p = ThreadWithException(target=self.faa_1.action_round_of_game,
                                                 name="1P Thread",
                                                 kwargs={
                                                     "deck": deck,
                                                     "delay_start": False,
                                                     "battle_mode": 0,
                                                     "task_card": "None",
                                                     "list_ban_card": []
                                                 })
            self.thread_1p.start()
            self.thread_1p.join()

            # 最后一次的退出方式不同
            if count_times + 1 == max_times:
                self.faa_1.action_exit(exit_mode=2)
            else:
                self.faa_1.action_exit(exit_mode=0)

            self.sin_out.emit("{} 第{}次, 结束\n".format(text_, count_times + 1))

        self.sin_out.emit("{} Completed!\n".format(text_))

    def alone_magic_tower_prison(
            self, text_, sutra_pavilion,
            deck, battle_plan_1p):

        self.sin_out.emit("{} Link Start!\n".format(text_))

        if sutra_pavilion:
            stage_list = ["MT-3-1", "MT-3-2", "MT-3-3", "MT-3-4"]
        else:
            stage_list = ["MT-3-1", "MT-3-3", "MT-3-4"]

        # 轮次作战
        for stage_id in stage_list:

            self.faa_1.get_config_for_battle(is_group=False, battle_plan_index=battle_plan_1p, stage_id=stage_id)

            # 第一次的进入方式不同
            if stage_id == "MT-3-1":
                self.faa_1.action_goto_stage(room_creator=True, mt_first_time=True)
            else:
                self.faa_1.action_goto_stage(room_creator=True)

            self.sin_out.emit("{} 开始关卡:{}".format(text_, stage_id))

            # 创建战斗进程 -> 开始进程 -> 阻塞进程让进程执行完再继续本循环函数
            self.thread_1p = ThreadWithException(target=self.faa_1.action_round_of_game,
                                                 name="1P Thread",
                                                 kwargs={
                                                     "deck": deck,
                                                     "delay_start": False,
                                                     "battle_mode": 0,
                                                     "task_card": "None",
                                                     "list_ban_card": []
                                                 })
            self.thread_1p.start()
            self.thread_1p.join()

            self.sin_out.emit("{}  战斗结束:{}".format(text_, stage_id))

            # 最后一次的退出方式不同
            if stage_id == "MT-3-4":
                self.faa_1.action_exit(exit_mode=2)
            else:
                self.faa_1.action_exit(exit_mode=0)

        self.sin_out.emit("{} Completed!\n".format(text_))

    def cross_server(
            self, text_, is_group,
            stage_id, max_times,
            deck, battle_plan_1p, battle_plan_2p):
        self.sin_out.emit("{} Link Start!\n".format(text_))

        # 填入战斗方案和关卡信息
        self.faa_1.get_config_for_battle(is_group=True, battle_plan_index=battle_plan_1p, stage_id=stage_id)
        if is_group:
            self.faa_2.get_config_for_battle(is_group=True, battle_plan_index=battle_plan_2p, stage_id=stage_id)

        self.faa_1.action_goto_stage(room_creator=True)
        if is_group:
            self.faa_2.action_goto_stage(room_creator=False)

        sleep(3)

        # 轮次作战
        for i in range(max_times):
            self.sin_out.emit("{} 第{}次, 开始".format(text_, i + 1))
            # 创建战斗进程 -> 开始进程 -> 阻塞进程让进程执行完再继续本循环函数
            self.thread_1p = ThreadWithException(target=self.faa_1.action_round_of_game,
                                                 name="1P Thread",
                                                 kwargs={"delay_start": True,
                                                         "battle_mode": 0,
                                                         "task_card": "None",
                                                         "list_ban_card": [],
                                                         "deck": deck
                                                         })
            if is_group:
                self.thread_2p = ThreadWithException(target=self.faa_2.action_round_of_game,
                                                     name="2P Thread",
                                                     kwargs={
                                                         "delay_start": False,
                                                         "battle_mode": 0,
                                                         "task_card": "None",
                                                         "list_ban_card": [],
                                                         "deck": deck
                                                     })
            self.thread_1p.start()
            if is_group:
                self.thread_2p.start()
            self.thread_1p.join()
            if is_group:
                self.thread_2p.join()

            # 打完出本
            if i + 1 == max_times:
                # 最后一把 打完回竞技岛
                self.faa_1.action_exit(exit_mode=3)
                if is_group:
                    self.faa_2.action_exit(exit_mode=3)
            else:
                # 其他次数 打完按兵不动
                self.faa_1.action_exit(exit_mode=0)
                if is_group:
                    self.faa_2.action_exit(exit_mode=0)

            self.sin_out.emit("{} 第{}次, 结束\n".format(text_, i + 1))

        self.sin_out.emit("{} Completed!\n".format(text_))

    def easy_battle(
            self, text_, stage_id, max_times,
            deck, is_group, battle_plan_1p, battle_plan_2p,
            dict_exit):
        """仅调用 n_battle"""
        # 战斗开始
        self.sin_out.emit("{} Link Start!\n".format(text_))
        # 战斗开始
        self.sin_out.emit("{}开始[多本轮战]...".format(text_))
        task_list = [
            {
                "stage_id": stage_id,
                "max_times": max_times,
                "deck": deck,
                "is_group": is_group,
                "battle_plan_1p": battle_plan_1p,
                "battle_plan_2p": battle_plan_2p,
                "task_card": "None",
                "list_ban_card": [],
                "dict_exit": dict_exit
            }]
        self.n_n_battle(task_list=task_list, list_type=["NO", "OR", "CS", "EX"])
        # 战斗结束
        self.sin_out.emit("{} Completed!\n".format(text_))

    def customize_battle(self, text_: str):
        # 开始链接
        self.sin_out.emit("{} Link Start!\n".format(text_))
        # 战斗开始
        self.sin_out.emit("{}开始[多本轮战]...".format(text_))

        with open(self.faa_1.paths["config"] + "//opt_customize_todo.json", "r", encoding="UTF-8") as file:
            task_list = json.load(file)

        self.n_n_battle(task_list=task_list, list_type=["NO"])

        # 战斗结束
        self.sin_out.emit("{} Completed!\n".format(text_))

    def run(self):

        my_opt = self.opt["MagicTowerAlone"]
        if my_opt["Active"]:
            self.alone_magic_tower(
                text_="[魔塔单人]",
                floor=int(my_opt["Stage"]),
                max_times=int(my_opt["MaxTimes"]),
                deck=my_opt["Deck"],
                battle_plan_1p=my_opt["BattlePlan1P"])

        my_opt = self.opt["MagicTowerPrison"]
        if my_opt["Active"]:
            self.alone_magic_tower_prison(
                text_="[魔塔密室]",
                sutra_pavilion=my_opt["Extra"],
                deck=my_opt["Deck"],
                battle_plan_1p=my_opt["BattlePlan1P"])

        my_opt = self.opt["MagicTowerDouble"]
        if my_opt["Active"]:
            self.double_magic_tower(
                text_="[魔塔双人]",
                floor=int(my_opt["Stage"]),
                max_times=int(my_opt["MaxTimes"]),
                deck=my_opt["Deck"],
                battle_plan_1p=my_opt["BattlePlan1P"],
                battle_plan_2p=my_opt["BattlePlan2P"])

        my_opt = self.opt["Relic"]
        if my_opt["Active"]:
            self.easy_battle(
                text_="[火山遗迹]",
                stage_id=my_opt["Stage"],
                max_times=int(my_opt["MaxTimes"]),
                deck=my_opt["Deck"],
                is_group=my_opt["IsGroup"],
                battle_plan_1p=my_opt["BattlePlan1P"],
                battle_plan_2p=my_opt["BattlePlan2P"],
                dict_exit={"other_time": [0], "last_time": [3]})

        my_opt = self.opt["CrossServer"]
        if my_opt["Active"]:
            self.cross_server(
                text_="[跨服副本]",
                is_group=my_opt["IsGroup"],
                max_times=int(my_opt["MaxTimes"]),
                stage_id=my_opt["Stage"],
                deck=my_opt["Deck"],
                battle_plan_1p=my_opt["BattlePlan1P"],
                battle_plan_2p=my_opt["BattlePlan2P"])

        my_opt = self.opt["Warrior"]
        if my_opt["Active"]:
            self.easy_battle(
                text_="[勇士挑战]",
                stage_id="NO-2-17",
                max_times=int(my_opt["MaxTimes"]),
                deck=my_opt["Deck"],
                is_group=my_opt["IsGroup"],
                battle_plan_1p=my_opt["BattlePlan1P"],
                battle_plan_2p=my_opt["BattlePlan2P"],
                dict_exit={"other_time": [0], "last_time": [3, 2]})

        my_opt = self.opt["GuildTask"]
        if my_opt["Active"]:
            self.double_task(
                text_="[公会任务]",
                task_type="guild",
                deck=my_opt["Deck"],
                battle_plan_1p=my_opt["BattlePlan1P"],
                battle_plan_2p=my_opt["BattlePlan2P"])

        my_opt = self.opt["SpouseTask"]
        if my_opt["Active"]:
            self.double_task(
                text_="[情侣任务]",
                task_type="spouse",
                deck=my_opt["Deck"],
                battle_plan_1p=my_opt["BattlePlan1P"],
                battle_plan_2p=my_opt["BattlePlan2P"])

        my_opt = self.opt["OfferReward"]
        if my_opt["Active"]:
            self.double_offer_reward(
                text_="[悬赏任务]",
                deck=my_opt["Deck"],
                battle_plan_1p=my_opt["BattlePlan1P"],
                battle_plan_2p=my_opt["BattlePlan2P"])

        my_opt = self.opt["NormalBattle"]
        if my_opt["Active"]:
            self.easy_battle(
                text_="[常规刷本]",
                stage_id=my_opt["Stage"],
                max_times=int(my_opt["MaxTimes"]),
                deck=my_opt["Deck"],
                is_group=my_opt["IsGroup"],
                battle_plan_1p=my_opt["BattlePlan1P"],
                battle_plan_2p=my_opt["BattlePlan2P"],
                dict_exit={"other_time": [0], "last_time": [3]})

        my_opt = self.opt["Customize"]
        if my_opt["Active"]:
            self.customize_battle(text_="[高级自定义]")

        # 全部完成了? 发个信号
        self.sin_out_completed.emit()


class MyMainWindow2(MyMainWindow1):

    def __init__(self):
        # 继承父类构造方法
        super().__init__()
        self.thread_todo = None
        self.reply = None
        self.faa_1 = None
        self.faa_2 = None
        # 线程激活即为True
        self.thread_states = False

    def todo_completed(self):
        # 设置按钮文本
        self.Button_Start.setText("开始\nLink Start")
        # 设置进程状态文本
        self.printf("\n>>> 全任务完成 线程关闭 <<<\n")
        # 设置flag
        self.thread_states = False

    def click_btn_start(self):
        """战斗开始函数"""
        # 线程没有激活
        if not self.thread_states:
            self.ui_to_opt()
            game_name = self.opt["GameName"]
            name_1p = self.opt["Name1P"]
            name_2p = self.opt["Name2P"]
            channel_1p, channel_2p = get_channel_name(game_name, name_1p, name_2p)

            # 把索引变值 需要注意的是 battle_plan均为索引 需要在FAA类中处理
            zoom_ratio = {0: 1.00, 1: 1.25, 2: 1.50, 3: 1.75, 4: 2.00, 5: 2.25, 6: 2.50}
            zoom_ratio = zoom_ratio[self.opt["ZoomRatio"]]

            faa_1 = FAA(channel=channel_1p,
                        dpi=zoom_ratio,
                        player="1P",
                        character_level=self.opt["Level1P"],
                        is_use_key=True,  # boolean 是否使用钥匙 做任务必须选择 是
                        is_auto_battle=self.opt["AutoUseCard"],  # boolean 是否使用自动战斗 做任务必须选择 是
                        is_auto_collect=False)

            faa_2 = FAA(channel=channel_2p,
                        dpi=zoom_ratio,
                        player="2P",
                        character_level=self.opt["Level2P"],
                        is_use_key=True,
                        is_auto_battle=self.opt["AutoUseCard"],
                        is_auto_collect=True)

            # 设置按钮文本
            self.Button_Start.setText("终止\nEnd")
            # 设置flag
            self.thread_states = True

            # Link Start!
            self.TextBrowser.clear()
            self.printf(">>> 链接开始 线程开启 <<<")
            self.printf(">>> 务必有二级密码, 且未输入以以兜底 <<<")
            self.printf("")

            self.thread_todo = Todo(faa_1=faa_1, faa_2=faa_2, opt=self.opt)
            # 绑定手动结束线程
            self.thread_todo.sin_out_completed.connect(self.todo_completed)
            # 绑定文本输出
            self.thread_todo.sin_out.connect(self.printf)
            # 开始线程
            self.thread_todo.start()

        # 线程已经激活
        else:
            # 中断内部战斗线程 (ThreadWithException) join用于等待进程确实中断
            for thread in [self.thread_todo.thread_1p, self.thread_todo.thread_2p]:
                if thread is not None:
                    thread.stop()
                    thread.join()
            # 中断 任务线程 (QThread)
            self.thread_todo.quit()
            self.thread_todo.wait()
            # 结束线程后的ui处理
            self.todo_completed()


def main():
    # 实例化 PyQt后台管理
    app = QApplication(sys.argv)

    # 实例化 主窗口
    window = MyMainWindow2()

    # 建立槽连接 注意 多线程中 槽连接必须写在主函数
    # 注册函数：开始/结束按钮
    window.Button_Start.clicked.connect(lambda: window.click_btn_start())
    window.Button_Save.clicked.connect(lambda: window.click_btn_save())
    # 主窗口 实现
    window.show()

    # 运行主循环，必须调用此函数才可以开始事件处理
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
