# coding:utf-8
import json
import multiprocessing
from time import sleep, strftime, localtime

from cv2 import imwrite, vconcat

from function.common.background_mouse import mouse_left_click
from function.common.background_screenshot import capture_picture_png
from function.common.background_screenshot_and_compare_picture import loop_find_p_in_p_ml_click, find_p_in_p
from function.get_root_path import get_root_path
from function.script.common import FAA


def battle_a_round(
        faa: object,
        stage_name: str,
        is_master: bool = False,
        is_main: bool = True,
        task_card: int = 0,
        battle_mode: int = 1):
    """
    一轮战斗
    Args:
        faa: 账号实例
        stage_name: 要打的关卡名称
        is_master: 是房主 房主要晚一点点开始
        is_main: 是否是主要角色(并非房主) 只有主要角色会使用 火炉 海星等卡片；非主要角色只会摆木盘棉花糖和任务卡片
        task_card: 任务要求卡片的序号。默认0即为没有。
        battle_mode: 战斗模式 0 cd模式 或 1遍历模式
    Returns:
    """

    # 提取handle
    handle = faa.handle

    # 提取一些常用变量
    dpi = faa.dpi
    path_p_common = faa.path_p_common
    path_logs = faa.path_logs

    # 刷新ui: 状态文本
    print("寻找开始或准备按钮")

    # 循环查找开始按键
    my_path = path_p_common + "\\BattleBefore_ReadyCheckStart.png"
    loop_find_p_in_p_ml_click(handle=handle, target=my_path, change_per=dpi, sleep_time=0.3, click=False)

    # 选择卡组
    print("选择卡组")
    mouse_left_click(handle, int(848 * dpi), int(121 * dpi), sleep_time=0.5)

    # 房主晚点开始
    if is_master:
        sleep(1.5)

    # 点击开始
    my_path = path_p_common + "\\BattleBefore_ReadyCheckStart.png"
    loop_find_p_in_p_ml_click(handle=handle, target=my_path, change_per=dpi, sleep_time=0.3)

    # 防止被没有带xx卡卡住
    my_path = path_p_common + "\\BattleBefore_NoMatCardEnter.png"
    if find_p_in_p(handle=handle, target_path=my_path):
        mouse_left_click(handle, int(427 * dpi), int(353 * dpi))

    # 刷新ui: 状态文本
    print("等待进入战斗")

    # 循环查找火苗图标 找到战斗开始
    my_path = path_p_common + "\\Battle_FireElement.png"
    loop_find_p_in_p_ml_click(handle=handle, target=my_path, change_per=dpi, click=False)

    # 刷新ui: 状态文本
    print("战斗进行中...")
    sleep(0.5)

    # 战斗循环
    faa.battle_normal(stage_name=stage_name, is_main=is_main, task_card=task_card, battle_mode=battle_mode)

    # 刷新ui: 状态文本
    print("战斗结束 记录战利品")

    # 记录战利品
    img = []
    mouse_left_click(handle, int(708 * dpi), int(484 * dpi), 0.05, 0.05)
    mouse_left_click(handle, int(708 * dpi), int(484 * dpi), 0.05, 0.3)
    img.append(capture_picture_png(handle)[453:551, 209:698])  # Y_min:Y_max,X_min:X_max
    sleep(0.5)
    mouse_left_click(handle, int(708 * dpi), int(510 * dpi), 0.05, 0.05)
    mouse_left_click(handle, int(708 * dpi), int(510 * dpi), 0.05, 0.3)
    img.append(capture_picture_png(handle)[453:552, 209:698])  # Y_min:Y_max,X_min:X_max
    sleep(0.5)
    mouse_left_click(handle, int(708 * dpi), int(527 * dpi), 0.05, 0.05)
    mouse_left_click(handle, int(708 * dpi), int(527 * dpi), 0.05, 0.3)
    img.append(capture_picture_png(handle)[503:552, 209:698])  # Y_min:Y_max,X_min:X_max
    # 垂直拼接
    img = vconcat(img)
    # 保存图片
    imwrite("{}\\{}_{}.png".format(path_logs, stage_name, strftime('%Y-%m-%d_%Hh%Mm', localtime())), img)

    # 刷新ui: 状态文本
    print("战斗结算中...")

    # 循环查找战利品字样
    my_path = path_p_common + "\\BattleEnd_Chest.png"
    loop_find_p_in_p_ml_click(handle=handle, target=my_path, change_per=dpi, click=False)

    # 刷新ui: 状态文本
    print("翻牌中...")

    # 开始翻牌
    mouse_left_click(handle, int(708 * dpi), int(502 * dpi), 0.05, 4)
    # 翻牌
    mouse_left_click(handle, int(708 * dpi), int(370 * dpi), 0.05, 0.25)
    mouse_left_click(handle, int(708 * dpi), int(170 * dpi), 0.05, 0.25)
    # 结束翻牌
    mouse_left_click(handle, int(708 * dpi), int(502 * dpi), 0.05, 3)

    # 刷新ui: 状态文本
    print("战斗结束!")

    # 战斗结束休息
    sleep(2)


def invite(faa_1: object, faa_2: object):
    """号1邀请号2到房间 需要在同一个区"""
    dpi = faa_1.dpi
    # 点邀请
    mouse_left_click(faa_1.handle, int(410 * dpi), int(546 * dpi))
    sleep(0.5)
    # 点好友
    mouse_left_click(faa_1.handle, int(528 * dpi), int(130 * dpi))
    sleep(0.5)
    # 获取好友id位置并邀请
    # [x, y] = find_p_in_p(faa_1.handle, faa_1.path_p_common + "\\P2_name.png")
    # mouse_left_click(faa_1.handle, int((x + 100) * dpi), int(y * dpi))
    # 直接邀请
    mouse_left_click(faa_1.handle, int(601 * dpi), int(157 * dpi))
    sleep(0.5)
    # p2接受邀请
    loop_find_p_in_p_ml_click(
        handle=faa_2.handle,
        target=faa_1.path_p_common + "\\BattleBefore_BeInvitedEnter.png",
        change_per=dpi,
        sleep_time=2.0
    )


class AutoCompleteToDoList:

    def __init__(self):
        # 读取项目根目录的.json文件
        with open(get_root_path() + "//todo.json", "r", encoding="UTF-8") as file:
            self.my_opt = json.load(file)

        self.game_name = self.my_opt["360游戏大厅中 你给游戏取的名字"]
        self.name_2p = self.my_opt["你2P角色的名字"]
        self.dpi = float(self.my_opt["你的windows缩放倍率(1代表100%)"])

        self.Player_1 = {
            "activation": True,  # 是否激活该角色
            "channel": self.game_name,
            "use_key": True,  # boolean 是否使用钥匙 做任务必须选择 是
            "auto_battle": True,  # boolean 是否使用自动战斗 做任务必须选择 是
        }
        self.Player2 = {
            "activation": True,  # 是否激活该角色
            "channel": self.name_2p + " | " + self.game_name,
            "use_key": True,  # boolean 是否使用钥匙 做任务必须选择 是
            "auto_battle": True,  # boolean 是否使用自动战斗 做任务必须选择 是
        }
        self.faa_1 = FAA(channel=self.Player_1["channel"],
                         dpi=self.dpi,
                         use_key=self.Player_1["use_key"],
                         auto_battle=self.Player_1["auto_battle"])
        self.faa_2 = FAA(channel=self.Player2["channel"],
                         dpi=self.dpi,
                         use_key=self.Player2["use_key"],
                         auto_battle=self.Player2["auto_battle"])
        # 打包exe后多线程必备
        multiprocessing.freeze_support()

    def guild_task_double(self):
        faa_1 = self.faa_1
        faa_2 = self.faa_2

        print("开始获取任务列表")
        task_list = self.faa_1.get_guild_task()
        print("已取得任务列表, 开始作战")

        for i in range(len(task_list)):

            task = task_list[i]

            # 不打跨服任务
            if i == 4:
                print("任务{},目标地点{},额外带卡序号{},跳过跨服".format(i + 1, task[0], task[1]))
                continue
            else:
                print("任务{},目标地点{},额外带卡序号{},即将开始".format(i + 1, task[0], task[1]))

            faa_1.goto_stage(stage=task[0], main_character=False)
            faa_2.goto_stage(stage=task[0], main_character=True)

            # 邀请组队
            sleep(3)
            invite(faa_2, faa_1)

            # 创建战斗进程 开始进程
            p1 = multiprocessing.Process(target=battle_a_round, args=[faa_1, task[0], False, True, int(task[1]), 1])
            p2 = multiprocessing.Process(target=battle_a_round, args=[faa_2, task[0], True, False, int(task[1]), 1])
            p1.start()
            p2.start()

            # 阻塞进程 让进程执行完再继续本循环函数
            p1.join()
            p2.join()

            # 打完出本
            faa_1.click_exit(exit_mode=1)
            faa_2.click_exit(exit_mode=1)

            print("任务{},完成".format(i + 1))

        print("太棒了！任务全部完成！")

    def magic_tower_alone(self, stage_name: int = 125, max_times: int = 5):
        faa = self.faa_1
        stage_name = "MT-1-" + str(stage_name)
        print("单人魔塔, Link Start!")

        # 轮次作战
        for i in range(max_times):

            print("第{}次, 开始".format(i + 1))

            # 第一次的进入方式不同
            if i == 0:
                faa.goto_stage(stage=stage_name, main_character=True, mt_first_time=True)
            else:
                faa.goto_stage(stage=stage_name, main_character=True)

            # 创建战斗进程 开始进程
            p1 = multiprocessing.Process(target=battle_a_round, args=[faa, stage_name, False, True, 0, 1])

            p1.start()

            # 阻塞进程 让进程执行完再继续本循环函数
            p1.join()

            # 最后一次的退出方式不同
            if i + 1 == max_times:
                faa.click_exit(exit_mode=2)
            else:
                faa.click_exit(exit_mode=0)

            print("第{}次, 结束".format(i + 1))

        print("单人魔塔, Completed!")

    def magic_tower_double(self, stage_name: int = 0, max_times: int = 5):
        faa_1 = self.faa_1
        faa_2 = self.faa_2
        stage_name = "MT-2-" + str(stage_name)

        print("双人魔塔, Link Start!")

        # 轮次作战
        for i in range(max_times):

            print("第{}次, 开始".format(i + 1))

            # 第一次的进入方式不同
            if i == 0:
                faa_1.goto_stage(stage=stage_name, main_character=False, mt_first_time=True)
                faa_2.goto_stage(stage=stage_name, main_character=True, mt_first_time=True)
            else:
                faa_2.goto_stage(stage=stage_name, main_character=True)

            # 邀请组队
            sleep(3)
            invite(faa_2, faa_1)

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
                faa_1.click_exit(exit_mode=1)
                faa_2.click_exit(exit_mode=2)
            else:
                # 其他次数
                faa_1.click_exit(exit_mode=1)
                faa_2.click_exit(exit_mode=0)

            print("任务{},完成".format(i + 1))
            print("第{}次, 结束".format(i + 1))
        print("双人魔塔, Completed!")

    def magic_tower_prison_alone(self):
        faa = self.faa_1
        stage_list = ["MT-3-1", "MT-3-2", "MT-3-3", "MT-3-4"]

        print("通刷魔塔密室, Link Start!")

        # 轮次作战
        for stage_name in stage_list:

            # 第一次的进入方式不同
            if stage_name == "MT-3-1":
                faa.goto_stage(stage="MT-3-1", main_character=True, mt_first_time=True)
            else:
                faa.goto_stage(stage=stage_name, main_character=True)

            print("开始关卡:{}".format(stage_name))

            # 创建战斗进程 开始进程
            p1 = multiprocessing.Process(target=battle_a_round, args=[faa, stage_name, False, True, 0, 1])
            p1.start()

            # 阻塞进程 让进程执行完再继续本循环函数
            p1.join()

            # 最后一次的退出方式不同
            if stage_name == "MT-3-4":
                faa.click_exit(exit_mode=2)
            else:
                faa.click_exit(exit_mode=0)

        print("通刷魔塔密室, Completed!")

    def cross_server_alone(self, stage_name: str = "CS-5-4", max_times: int = 10):
        faa = self.faa_1

        print("单人跨服, Link Start!")

        # 前往副本
        faa.goto_stage(stage=stage_name, main_character=True, lock_p2=True)

        # 轮次战斗
        for i in range(max_times):

            print("第{}次, 开始".format(i + 1))

            # 创建战斗进程 开始进程
            p1 = multiprocessing.Process(target=battle_a_round, args=[faa, stage_name, False, True, 0, 1])
            p1.start()

            # 阻塞进程 让进程执行完再继续本循环函数
            p1.join()

            # 最后一次的退出方式不同
            if i + 1 == max_times:
                faa.click_exit(exit_mode=3)
            else:
                faa.click_exit(exit_mode=0)

            print("第{}次, 结束".format(i + 1))

        print("单人跨服, Completed!")

    def normal_battle_alone(self, stage_name: str, max_times: int):
        faa = self.faa_1

        print("单人刷本, Link Start!")

        # 前往副本
        faa.goto_stage(stage=stage_name, main_character=True)

        # 轮次作战
        for i in range(max_times):

            print("第{}次, 开始".format(i + 1))

            # 创建战斗进程 开始进程
            p1 = multiprocessing.Process(target=battle_a_round, args=[faa, stage_name, False, True, 0, 1])
            p1.start()

            # 阻塞进程 让进程执行完再继续本循环函数
            p1.join()

            # 最后一次的退出方式不同
            if i + 1 == max_times:
                faa.click_exit(exit_mode=3)
            else:
                faa.click_exit(exit_mode=0)

            print("第{}次, 结束".format(i + 1))
        print("单人刷本, Completed!")

    def normal_battle_double(self, stage_name: str, max_times: int):
        faa_1 = self.faa_1
        faa_2 = self.faa_2

        print("双人刷本, Link Start!")

        # 前往副本
        faa_1.goto_stage(stage=stage_name, main_character=False)
        faa_2.goto_stage(stage=stage_name, main_character=True)

        # 邀请组队
        sleep(3)
        invite(faa_2, faa_1)

        # 轮次战斗
        for i in range(max_times):

            print("第{}次, 开始".format(i + 1))

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
                faa_1.click_exit(exit_mode=3)
                faa_2.click_exit(exit_mode=3)
            else:
                faa_1.click_exit(exit_mode=0)
                faa_2.click_exit(exit_mode=0)

            print("第{}次, 结束".format(i + 1))

        print("双人刷本, Completed!")

    def main(self):
        task_opt = self.my_opt["执行的任务"]

        opt = task_opt["公会任务6连"]
        if opt["Active"] == "True":
            self.guild_task_double()

        opt = task_opt["单人魔塔5连"]
        if opt["Active"] == "True":
            self.magic_tower_alone(stage_name=opt["Stage"], max_times=int(opt["MaxTimes"]))

        opt = task_opt["双人魔塔5连"]
        if opt["Active"] == "True":
            self.magic_tower_double(stage_name=opt["Stage"], max_times=int(opt["MaxTimes"]))

        opt = task_opt["单人魔塔密室4连"]
        if opt["Active"] == "True":
            self.magic_tower_prison_alone()

        opt = task_opt["单人跨服10连"]
        if opt["Active"] == "True":
            self.cross_server_alone(stage_name=opt["Stage"], max_times=int(opt["MaxTimes"]))

        opt = task_opt["单人勇士本10连"]
        if opt["Active"] == "True":
            self.normal_battle_alone(stage_name="NO-2-17", max_times=int(opt["MaxTimes"]))

        opt = task_opt["单人火山遗迹5连"]
        if opt["Active"] == "True":
            self.normal_battle_alone(stage_name="NO-3-6", max_times=int(opt["MaxTimes"]))

        opt = task_opt["双人悬赏三连"]
        if opt["Active"] == "True":
            self.normal_battle_double(stage_name="OR-1-0", max_times=1)
            self.normal_battle_double(stage_name="OR-2-0", max_times=1)
            self.normal_battle_double(stage_name="OR-3-0", max_times=1)

        opt = task_opt["双人单本连刷"]
        if opt["Active"] == "True":
            self.normal_battle_double(stage_name="NO-1-14", max_times=int(opt["MaxTimes"]))


if __name__ == '__main__':
    print("wow")
