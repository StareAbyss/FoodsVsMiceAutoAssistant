# coding:utf-8
import json
import multiprocessing
from time import sleep

from function.get_root_path import get_root_path
from function.script.common import FAA
from function.script.common_action import invite, battle_a_round


class AutoCompleteToDoList:

    def __init__(self):
        # 读取项目根目录的.json文件
        with open(get_root_path() + "//todo.json", "r", encoding="UTF-8") as file:
            self.my_opt = json.load(file)

        self.game_name = self.my_opt["360游戏大厅中 你给游戏取的名字"]
        self.name_1p = self.my_opt["你游戏窗口上1P角色的名字"]
        self.name_2p = self.my_opt["你游戏窗口上2P角色的名字"]
        self.dpi = float(self.my_opt["你的windows缩放倍率(1代表100%)"])

        if self.name_1p == "":
            self.channel_1p = self.game_name
        else:
            self.channel_1p = self.name_1p + " | " + self.game_name

        if self.name_2p == "":
            self.channel_2p = self.game_name
        else:
            self.channel_2p = self.name_2p + " | " + self.game_name

        self.Player_1 = {
            "activation": True,  # 是否激活该角色
            "channel": self.channel_1p,
            "is_use_key": True,  # boolean 是否使用钥匙 做任务必须选择 是
            "is_auto_battle": True,  # boolean 是否使用自动战斗 做任务必须选择 是
        }
        self.Player_2 = {
            "activation": True,  # 是否激活该角色
            "channel": self.channel_2p,
            "is_use_key": True,  # boolean 是否使用钥匙 做任务必须选择 是
            "is_auto_battle": True,  # boolean 是否使用自动战斗 做任务必须选择 是
        }
        self.faa_1 = FAA(channel=self.Player_1["channel"],
                         dpi=self.dpi,
                         is_use_key=self.Player_1["is_use_key"],
                         is_auto_battle=self.Player_1["is_auto_battle"])
        self.faa_2 = FAA(channel=self.Player_2["channel"],
                         dpi=self.dpi,
                         is_use_key=self.Player_2["is_use_key"],
                         is_auto_battle=self.Player_2["is_auto_battle"])
        # 打包exe后多线程必备
        multiprocessing.freeze_support()

    def task_guild_double(self):
        text_ = "[公会任务]"
        faa_1 = self.faa_1
        faa_2 = self.faa_2

        print("{} Link Start!".format(text_))

        print("{} 开始获取任务列表".format(text_))
        task_list = self.faa_1.action_get_task(target="guild")
        print(task_list)
        print("{} 已取得任务, 开始作战".format(text_))

        for i in range(len(task_list)):

            task = task_list[i]

            # 不打跨服任务
            if task[0].split("-")[0] == "CS":
                print("{} 任务{},目标地点{},额外带卡序号{},跳过跨服".format(text_, i + 1, task[0], task[1]))
                continue
            else:
                print("{} 任务{},目标地点{},额外带卡序号{},即将开始".format(text_, i + 1, task[0], task[1]))

            while True:
                faa_1.action_goto_stage(stage_name=task[0], room_creator=False)
                faa_2.action_goto_stage(stage_name=task[0], room_creator=True)
                sleep(3)
                if invite(faa_2, faa_1):
                    break
                else:
                    print("尝试进入竞技岛 并重新进行邀请")
                    faa_1.action_goto_exit(3)
                    faa_2.action_goto_exit(3)

            # 创建战斗进程 开始进程
            p1 = multiprocessing.Process(target=battle_a_round, args=[faa_1, task[0], False, True, int(task[1]), 1])
            p2 = multiprocessing.Process(target=battle_a_round, args=[faa_2, task[0], True, False, int(task[1]), 1])
            p1.start()
            p2.start()

            # 阻塞进程 让进程执行完再继续本循环函数
            p1.join()
            p2.join()

            # 打完出本
            faa_1.action_goto_exit(exit_mode=1)
            faa_2.action_goto_exit(exit_mode=1)

            print("{} 任务{},完成\n".format(text_, i + 1))

        print("{} Completed!\n".format(text_))

    def task_spouse_double(self):
        text_ = "[情侣任务]"
        faa_1 = self.faa_1
        faa_2 = self.faa_2

        print("{} Link Start!".format(text_))
        print("{} 开始获取任务列表".format(text_))
        task_list = self.faa_1.action_get_task(target="spouse")
        print(task_list)
        print("{} 已取得任务列表, 开始作战".format(text_))

        for i in range(len(task_list)):
            task = task_list[i]

            print("{} 任务{},目标地点{},即将开始".format(text_, i + 1, task[0]))

            while True:
                faa_1.action_goto_stage(stage_name=task[0], room_creator=False)
                faa_2.action_goto_stage(stage_name=task[0], room_creator=True)
                sleep(3)
                if invite(faa_2, faa_1):
                    break
                else:
                    print("尝试进入竞技岛 并重新进行邀请")
                    faa_1.action_goto_exit(3)
                    faa_2.action_goto_exit(3)

            # 创建战斗进程 开始进程
            p1 = multiprocessing.Process(target=battle_a_round, args=[faa_1, task[0], False, True, 0, 1])
            p2 = multiprocessing.Process(target=battle_a_round, args=[faa_2, task[0], True, False, 0, 1])
            p1.start()
            p2.start()

            # 阻塞进程 让进程执行完再继续本循环函数
            p1.join()
            p2.join()

            # 打完出本
            faa_1.action_goto_exit(exit_mode=1)
            faa_2.action_goto_exit(exit_mode=1)

            print("{} 任务{},完成\n".format(text_, i + 1))

        print("{} Completed!\n".format(text_))

    def magic_tower_alone(self, stage_name: int = 125, max_times: int = 5):
        text_ = "[单人魔塔]"
        faa = self.faa_1
        stage_name = "MT-1-" + str(stage_name)

        print("{} Link Start!".format(text_))

        # 轮次作战
        for i in range(max_times):

            print("{} 第{}次, 开始".format(text_, i + 1))

            # 第一次的进入方式不同
            if i == 0:
                faa.action_goto_stage(stage_name=stage_name, room_creator=True, mt_first_time=True)
            else:
                faa.action_goto_stage(stage_name=stage_name, room_creator=True)

            # 创建战斗进程 开始进程
            p1 = multiprocessing.Process(target=battle_a_round, args=[faa, stage_name, False, True, 0, 1])

            p1.start()

            # 阻塞进程 让进程执行完再继续本循环函数
            p1.join()

            # 最后一次的退出方式不同
            if i + 1 == max_times:
                faa.action_goto_exit(exit_mode=2)
            else:
                faa.action_goto_exit(exit_mode=0)

            print("{} 第{}次, 结束\n".format(text_, i + 1))

        print("{} Completed!\n".format(text_))

    def magic_tower_double(self, stage_name: int = 0, max_times: int = 5):
        text_ = "[双人魔塔]"
        faa_1 = self.faa_1
        faa_2 = self.faa_2
        stage_name = "MT-2-" + str(stage_name)

        print("{} Link Start!".format(text_))

        # 轮次作战
        for i in range(max_times):

            print("{} 第{}次, 开始".format(text_, i + 1))

            flag_invite_failed = False

            # 前往副本
            while True:
                # 第一次 或 邀请失败后 进入方式不同
                if i == 0 or flag_invite_failed:
                    faa_1.action_goto_stage(stage_name=stage_name, room_creator=False, mt_first_time=True)
                    faa_2.action_goto_stage(stage_name=stage_name, room_creator=True, mt_first_time=True)
                else:
                    faa_2.action_goto_stage(stage_name=stage_name, room_creator=True)

                sleep(3)
                # 尝试要求 如果成功就结束循环 如果失败 退出到竞技岛尝试重新邀请
                if invite(faa_2, faa_1):
                    break
                else:
                    flag_invite_failed = True
                    print("尝试进入竞技岛 并重新进行邀请")
                    faa_1.action_goto_exit(3)
                    faa_2.action_goto_exit(3)

            # 创建战斗进程 开始进程
            p1 = multiprocessing.Process(target=battle_a_round, args=[faa_1, stage_name, False, True, 0, 1])
            p2 = multiprocessing.Process(target=battle_a_round, args=[faa_2, stage_name, True, False, 0, 1])
            p1.start()
            p2.start()

            # 阻塞进程 让进程执行完再继续本循环函数
            p1.join()
            p2.join()

            # 打完出本
            if i + 1 == max_times:
                # 最后一把
                faa_1.action_goto_exit(exit_mode=1)
                faa_2.action_goto_exit(exit_mode=2)
            else:
                # 其他次数
                faa_1.action_goto_exit(exit_mode=1)
                faa_2.action_goto_exit(exit_mode=0)

            print("{} 第{}次, 结束\n".format(text_, i + 1))

        print("{} Completed!\n".format(text_))

    def magic_tower_prison_alone(self, sutra_pavilion: bool = False):
        text_ = "[单人魔塔密室]"
        faa = self.faa_1

        if sutra_pavilion:
            stage_list = ["MT-3-1", "MT-3-2", "MT-3-3", "MT-3-4"]
        else:
            stage_list = ["MT-3-1", "MT-3-3", "MT-3-4"]

        print(text_, "Link Start!")

        # 轮次作战
        for stage_name in stage_list:

            # 第一次的进入方式不同
            if stage_name == "MT-3-1":
                faa.action_goto_stage(stage_name="MT-3-1", room_creator=True, mt_first_time=True)
            else:
                faa.action_goto_stage(stage_name=stage_name, room_creator=True)

            print("开始关卡:{}".format(stage_name))

            # 创建战斗进程 开始进程
            p1 = multiprocessing.Process(target=battle_a_round, args=[faa, stage_name, False, True, 0, 1])
            p1.start()

            # 阻塞进程 让进程执行完再继续本循环函数
            p1.join()

            # 最后一次的退出方式不同
            if stage_name == "MT-3-4":
                faa.action_goto_exit(exit_mode=2)
            else:
                faa.action_goto_exit(exit_mode=0)

        print(text_, "Completed!\n")

    def cross_server_alone(self, stage_name: str = "CS-5-4", max_times: int = 10):
        text_ = "[单人跨服]"
        faa = self.faa_1

        print("{} Link Start!".format(text_))

        # 前往副本
        faa.action_goto_stage(stage_name=stage_name, room_creator=True, lock_p2=True)

        # 轮次战斗
        for i in range(max_times):

            print("{} 第{}次, 开始".format(text_, i + 1))

            # 创建战斗进程 开始进程
            p1 = multiprocessing.Process(target=battle_a_round, args=[faa, stage_name, False, True, 0, 1])
            p1.start()

            # 阻塞进程 让进程执行完再继续本循环函数
            p1.join()

            # 最后一次的退出方式不同
            if i + 1 == max_times:
                faa.action_goto_exit(exit_mode=3)
            else:
                faa.action_goto_exit(exit_mode=0)

            print("{} 第{}次, 结束\n".format(text_, i + 1))

        print("{} Completed!\n".format(text_))

    def normal_battle_alone(self, stage_name: str, max_times: int, exit_dict=None):
        text_ = "[单人刷本]"
        if exit_dict is None:
            exit_dict = {"other_time": [0], "last_time": [1]}
        faa = self.faa_1

        print("{} Link Start!".format(text_))
        print("{} 目标副本: {}".format(text_, stage_name))
        # 前往副本
        faa.action_goto_stage(stage_name=stage_name, room_creator=True)

        # 轮次作战
        for i in range(max_times):

            print("{} 第{}次, 开始".format(text_, i + 1))

            # 创建战斗进程 开始进程
            p1 = multiprocessing.Process(target=battle_a_round, args=[faa, stage_name, False, True, 0, 1])
            p1.start()

            # 阻塞进程 让进程执行完再继续本循环函数
            p1.join()

            # 最后一次的退出方式不同
            if i + 1 == max_times:
                for j in exit_dict["last_time"]:
                    faa.action_goto_exit(exit_mode=j)
            else:
                for j in exit_dict["other_time"]:
                    faa.action_goto_exit(exit_mode=j)

            print("{} 第{}次, 结束\n".format(text_, i + 1))

        print("{} Completed!\n".format(text_))

    def normal_battle_double(self, stage_name: str, max_times: int):
        text_ = "[双人刷本]"
        faa_1 = self.faa_1
        faa_2 = self.faa_2

        print("{} Link Start!".format(text_))

        # 前往副本
        while True:
            faa_1.action_goto_stage(stage_name=stage_name, room_creator=False)
            faa_2.action_goto_stage(stage_name=stage_name, room_creator=True)
            sleep(3)
            if invite(faa_2, faa_1):
                break
            else:
                print("尝试进入竞技岛 并重新进行邀请")
                faa_1.action_goto_exit(3)
                faa_2.action_goto_exit(3)

        # 轮次战斗
        for i in range(max_times):

            print("{} 第{}次, 开始".format(text_, i + 1))

            # 创建战斗进程 开始进程
            p1 = multiprocessing.Process(target=battle_a_round, args=[faa_1, stage_name, False, True, 0, 1])
            p2 = multiprocessing.Process(target=battle_a_round, args=[faa_2, stage_name, True, False, 0, 1])
            p1.start()
            p2.start()

            # 阻塞进程 让进程执行完再继续本循环函数
            p1.join()
            p2.join()

            # 最后一次的退出方式不同
            if i + 1 == max_times:
                faa_1.action_goto_exit(exit_mode=3)
                faa_2.action_goto_exit(exit_mode=3)
            else:
                faa_1.action_goto_exit(exit_mode=0)
                faa_2.action_goto_exit(exit_mode=0)

            print("{} 第{}次, 结束\n".format(text_, i + 1))

        print("{} Completed!\n".format(text_))

    def main(self):
        task_opt = self.my_opt["执行的任务"]

        # 日常 - 双人

        opt = task_opt["[双人][公会任务][6连]"]
        if opt["Active"] == "True":
            self.task_guild_double()

        opt = task_opt["[双人][情侣任务][3连]"]
        if opt["Active"] == "True":
            self.task_spouse_double()

        opt = task_opt["[双人][悬赏][3连]"]
        if opt["Active"] == "True":
            self.normal_battle_double(stage_name="OR-1-0", max_times=1)
            self.normal_battle_double(stage_name="OR-2-0", max_times=1)
            self.normal_battle_double(stage_name="OR-3-0", max_times=1)

        opt = task_opt["[双人][魔塔]"]
        if opt["Active"] == "True":
            self.magic_tower_double(stage_name=opt["Stage"],
                                    max_times=int(opt["MaxTimes"]))

        # 日常 - 单人

        opt = task_opt["[单人][魔塔]"]
        if opt["Active"] == "True":
            self.magic_tower_alone(stage_name=opt["Stage"],
                                   max_times=int(opt["MaxTimes"]))

        opt = task_opt["[单人][魔塔密室][4连]"]
        if opt["Active"] == "True":
            if opt["SutraPavilion"] == "True":
                self.magic_tower_prison_alone(sutra_pavilion=True)
            else:
                self.magic_tower_prison_alone(sutra_pavilion=False)

        opt = task_opt["[单人][跨服]"]
        if opt["Active"] == "True":
            self.cross_server_alone(stage_name=opt["Stage"],
                                    max_times=int(opt["MaxTimes"]))

        opt = task_opt["[单人][火山遗迹]"]
        if opt["Active"] == "True":
            self.normal_battle_alone(stage_name=opt["Stage"],
                                     max_times=int(opt["MaxTimes"]))

        opt = task_opt["[单人][勇士本]"]
        if opt["Active"] == "True":
            self.normal_battle_alone(stage_name="NO-2-17",
                                     max_times=int(opt["MaxTimes"]),
                                     exit_dict={"other_time": [0], "last_time": [2, 2]})

        # 非日常

        opt = task_opt["[双人][单本连刷]"]
        if opt["Active"] == "True":
            self.normal_battle_double(stage_name=opt["Stage"],
                                      max_times=int(opt["MaxTimes"]))


if __name__ == '__main__':
    print("wow")
