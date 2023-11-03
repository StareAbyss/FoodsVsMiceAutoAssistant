import json
import os
import re
from time import sleep, time

import numpy as np
from cv2 import imread

from function.common.bg_keyboard import key_down_up
from function.common.bg_mouse import mouse_move_to, mouse_left_click
from function.common.bg_screenshot import capture_picture_png
from function.common.bg_screenshot_and_compare_picture import find_picture_in_window, \
    loop_find_picture_in_window_ml_click, find_pictures_in_window
from function.get_root_path import get_root_path
from function.tools.create_battle_coordinates import create_battle_coordinates
from function.tools.gat_handle import faa_get_handle
from function.tools.get_battle_plan_list import get_battle_plan_list

"""计算卡片的部署方案相关的函数"""


def solve_card_task(list_cell_all, task_card):
    """计算步骤一 加入任务卡的摆放坐标"""
    # 任务卡 大号小号开始位置不同 任务卡id = 0 则为没有
    locations = ["6-2", "6-3", "6-4", "6-5", "6-6"]
    if task_card != "None":
        # 遍历删除 主要卡中 占用了任务卡摆放的坐标
        new_list = []
        for card in list_cell_all:
            for location in card["location"]:
                if location in locations:
                    card["location"].remove(location)
            new_list.append(card)
        # 设定任务卡dict
        dict_task = {"id": 2 + len(new_list) + 1,
                     "name": task_card,
                     "ergodic": True,
                     "queue": True,
                     "location": locations}
        # 加入数组
        new_list.append(dict_task)
        return new_list
    else:
        return list_cell_all


def solve_card_mat(list_cell_all, stage_info, player, is_group):
    """步骤二 2张承载卡"""
    # 预设中该关卡无垫子
    if stage_info["mat_card"] == 0:
        return list_cell_all

    # 分辨不同的垫子卡
    elif stage_info["mat_card"] == 1:
        # 木盘子会被毁 队列 + 遍历
        mat_name = "Wooden plate"
        ergodic = True
        queue = True
    else:
        # 麦芽糖坏不掉 所以只队列 不遍历
        mat_name = "Maltose"
        ergodic = False
        queue = True
    # 预设中该关卡有垫子 或采用了默认的没有垫子
    dict_mat = {"id": stage_info["mat_card"],
                "name": mat_name,
                "ergodic": ergodic,
                "queue": queue,
                "location": stage_info["mat_cell"]}
    # p1p2分别摆一半加入数组
    if is_group:
        if player == "1P":
            dict_mat["location"] = dict_mat["location"][::2]  # 奇数
        else:
            dict_mat["location"] = dict_mat["location"][1::2]  # 偶数
    list_cell_all.append(dict_mat)

    return list_cell_all


def solve_card_ban(list_cell_all, list_ban_card):
    """步骤三 ban掉某些卡"""
    list_new = []
    for i in list_cell_all:
        if not (i["name"] in list_ban_card):
            list_new.append(i)
    return list_new


def solve_obstacle(list_cell_all, stage_info):
    """去除有障碍的位置的放卡"""
    # 预设中 该关卡有障碍物
    new_list_1 = []
    for i in list_cell_all:
        for location in i["location"]:
            if location in stage_info["obstacle"]:
                i["location"].remove(location)
        new_list_1.append(i)
    # 如果location被删完了 就去掉它
    new_list_2 = []
    for i in new_list_1:
        if i["location"]:
            new_list_2.append(i)
    return new_list_2


def solve_alt_transformer(list_cell_all, player):
    """[非]1P, 队列模式, 就颠倒坐标数组, [非]队列模式代表着优先级很重要的卡片, 所以不颠倒"""
    if player == "2P":
        for i in range(len(list_cell_all)):
            if list_cell_all[i]["queue"]:
                list_cell_all[i]["location"] = list_cell_all[i]["location"][::-1]
    return list_cell_all


def solve_shovel(stage_info):
    """铲子位置 """
    list_shovel = stage_info["shovel"]
    return list_shovel


def one_card(option):
    """
    计算卡片部署方案
    Args:
        option: 部署参数
            example = {"begin": [int 开始点x, int 开始点y],"end": [int 结束点x, int 结束点y]}
    Returns: 卡片的部署方案字典 (输出后 多个该字典存入数组 进行循环)
        example = ["x-y","x-y","x-y",...]
    """
    my_list = []
    for i in range(option["begin"][0], option["end"][0] + 1):
        for j in range(option["begin"][1], option["end"][1] + 1):
            my_list.append(str(str(i) + "-" + str(j)))
    return my_list


def mat_card(cell_need_mat, cell_all_dict):
    """
    计算承载卡的部署方案 - 通过其他需要部署的卡 和此处option定义的区域的 [交集] 来计算
    Args:
        cell_need_mat: 需要垫子的部署位数组
        cell_all_dict: 其他所有卡片的部署方案字典
    Returns:
        承载卡的部署方案字典 同上
    """
    # 其他卡 部署位置
    cell_all_card = []
    for i in cell_all_dict:
        cell_all_card = cell_all_card + cell_all_dict[i]["location"]

    # 计算重复的部分
    cell_2 = []
    for i in cell_need_mat:
        for j in cell_all_card:
            if i == j:
                cell_2.append(i)
                break

    # 输出
    return cell_2


def solve_cell_all_card(stage_info, battle_plan, player, is_group, task_card, list_ban_card):
    """
    计算所有卡片的部署方案
    Return:卡片的部署方案字典
        example = [
            {
                "id": int,
                "location": ["x-y","x-y","x-y",...]
            },
            ...
        ]
    """

    # 初始化数组 + 调用战斗卡
    list_cell_all = battle_plan

    # 调用计算任务卡
    list_cell_all = solve_card_task(list_cell_all=list_cell_all, task_card=task_card)

    # 调用计算承载卡
    list_cell_all = solve_card_mat(list_cell_all=list_cell_all, stage_info=stage_info, player=player, is_group=is_group)

    # 调用ban掉某些卡(不使用该卡)
    list_cell_all = solve_card_ban(list_cell_all=list_cell_all, list_ban_card=list_ban_card)

    # 调用去掉障碍位置
    list_cell_all = solve_obstacle(list_cell_all=list_cell_all, stage_info=stage_info)

    # 颠倒2P的放置顺序
    # list_cell_all = solve_alt_transformer(list_cell_all=list_cell_all, player=player)

    # 调用计算铲子卡
    list_shovel = solve_shovel(stage_info=stage_info)
    return list_cell_all, list_shovel


class FAA:
    def __init__(self, channel="锑食", dpi=1.5, player="1P", character_level=1,
                 is_use_key=True, is_auto_battle=True, is_auto_collect=False):

        # 获取窗口句柄
        self.handle = faa_get_handle(channel=channel, mode="game")

        # DPI
        self.dpi = dpi  # float 1.0 即百分百

        # 角色|等级|是否使用钥匙|卡片|收集战利品
        self.player = player
        self.character_level = character_level
        self.is_use_key = is_use_key
        self.is_auto_battle = is_auto_battle
        self.is_auto_collect = is_auto_collect

        # 资源文件路径
        self.path_root = get_root_path()
        self.path_logs = self.path_root + "\\logs"
        self.path_config = self.path_root + "\\config"

        self.path_p = self.path_root + "\\resource\\picture"

        self.path_p_common = self.path_p + "\\common"
        self.path_p_card = self.path_p + "\\card"
        self.path_p_stage = self.path_p + "\\stage"
        self.path_p_guild_task = self.path_p + "\\task_guild"
        self.path_p_spouse_task = self.path_p + "\\task_spouse"
        self.path_p_ready_check_stage = self.path_p + "\\stage_ready_check"

        # 计算关卡内的卡牌 和 格子位置
        self.battle_card, self.battle_cell = create_battle_coordinates(self.dpi)

        # 每个副本的战斗都不一样的参数 使用内部函数调用更改
        self.is_group = False
        self.battle_plan = None
        self.stage_info = None

        # 其他手动内部参数
        self.click_interval = 0.025
        self.click_sleep = 0.025

    """输入关卡配置和默认配置"""

    def get_config_for_battle(self, is_group=False, battle_plan_index=0, stage_id="NO-1-1"):
        """
        :param is_group: 是否组队
        :param battle_plan_index: 战斗方案的索引
        :param stage_id: 关卡的id
        :return:
        """

        self.is_group = is_group

        def read_json_to_battle_plan():
            battle_plan_list = get_battle_plan_list(with_extension=True)
            battle_plan_path = "{}\\battle_plan\\{}".format(self.path_config, battle_plan_list[battle_plan_index])
            with open(battle_plan_path, "r", encoding="UTF-8") as file:
                return json.load(file)

        def read_json_to_stage_info():
            """读取文件中是否存在预设"""
            with open(self.path_config + "//opt_stage_info.json", "r", encoding="UTF-8") as file:
                f_my_dict = json.load(file)
            # 初始化
            stage_info = f_my_dict["default"]
            stage_info["id"] = stage_id
            # 拆分关卡名称
            stage_list = stage_id.split("-")
            stage_0 = stage_list[0]  # type
            stage_1 = stage_list[1]  # map
            stage_2 = stage_list[2]  # stage
            # 如果找到预设
            if stage_0 in f_my_dict.keys():
                if stage_1 in f_my_dict[stage_0].keys():
                    if stage_2 in f_my_dict[stage_0][stage_1].keys():
                        # 用设定里有的键值对覆盖已有的 并填写关卡名称(没有则保持默认)
                        f_stage_info_1 = f_my_dict[stage_0][stage_1][stage_2]

                        stage_info = {**stage_info, **f_stage_info_1}
            return stage_info

        self.battle_plan = read_json_to_battle_plan()
        self.stage_info = read_json_to_stage_info()

    """封装好的对窗口的动作"""

    def action_get_stage_name(self):
        """在关卡备战界面 获得关卡名字"""
        stage_id = "Unknown"  # 默认名称
        img1 = capture_picture_png(self.handle)[468:484, 383:492, :3]
        # 关卡名称集 从资源文件夹自动获取, 资源文件命名格式：关卡名称.png
        stage_text_in_ready_check = []
        for i in os.listdir(self.path_p_ready_check_stage):
            if i.find(".png") != -1:
                stage_text_in_ready_check.append(i.split(".")[0])
        for i in stage_text_in_ready_check:
            if np.all(img1 == imread(self.path_p_ready_check_stage + "\\" + i + ".png", 1)):
                stage_id = i
                break
        return stage_id

    def action_get_task(self, target: str):
        """
        获取公会任务列表
        :param target:
        :return: [{
            "stage_id":str,
            "max_times":,
            "task_card":str,
            "ban_card":None
            },
            ...
        ]
        """
        # 点跳转
        mouse_left_click(handle=self.handle, x=int(870 * self.dpi), y=int(560 * self.dpi), sleep_time=1)

        # 点任务
        if target == "guild":
            # 公会任务 guild
            mouse_left_click(handle=self.handle, x=int(870 * self.dpi), y=int(263 * self.dpi), sleep_time=1.5)
            # 点一下 让左边的选中任务颜色消失
            mouse_left_click(handle=self.handle, x=int(650 * self.dpi), y=int(300 * self.dpi), sleep_time=1.5)
        if target == "spouse":
            # 情侣任务 spouse
            mouse_left_click(handle=self.handle, x=int(870 * self.dpi), y=int(300 * self.dpi), sleep_time=1.5)

        # 读取
        task_list = []
        # 公会任务 guild
        if target == "guild":
            path = self.path_p_guild_task
            for i in range(7):
                # 遍历任务
                for j in os.listdir("{}\\{}\\".format(path, str(i + 1))):
                    # 找到任务 加入任务列表
                    find_p = find_picture_in_window(handle=self.handle,
                                                    target_path="{}\\{}\\{}".format(path, str(i + 1), j),
                                                    tolerance=0.999)
                    if find_p:
                        # 任务携带卡片默认为None
                        task_card = "None"
                        # 去除.png
                        j = j.split(".")[0]
                        # 当任务名称带有 _,
                        if j.find("_"):
                            stage_id = j.split("_")[0]
                            # _ 中分割的部分 包含纯英文(卡片名称) 时
                            for k in j.split("_"):
                                if re.match("^[A-Za-z]+$", k):
                                    # 任务携带卡片变化
                                    task_card = k
                        else:
                            stage_id = j
                        task_list.append({"is_group": True,
                                          "stage_id": stage_id,
                                          "max_times": 1,
                                          "task_card": task_card,
                                          "list_ban_card": [],
                                          "dict_exit": {"other_time": [0], "last_time": [3]}})

        # 情侣任务 spouse
        if target == "spouse":
            path = self.path_p_spouse_task
            for i in ["1", "2", "3"]:
                # 任务未完成
                find_p = find_picture_in_window(handle=self.handle,
                                                target_path="{}\\NO-{}.png".format(path, i),
                                                tolerance=0.999)
                if find_p:
                    # 遍历任务
                    for j in os.listdir("{}\\{}\\".format(path, i)):
                        # 找到任务 加入任务列表
                        print("{}\\{}\\{}".format(path, i, j))
                        find_p = find_picture_in_window(handle=self.handle,
                                                        target_path="{}\\{}\\{}".format(path, i, j),
                                                        tolerance=0.999)
                        if find_p:
                            task_list.append({"is_group": True,
                                              "stage_id": j.split(".")[0],
                                              "max_times": 1,
                                              "task_card": "None",
                                              "list_ban_card": [],
                                              "dict_exit": {"other_time": [0], "last_time": [3]}})

        # 关闭公会任务列表(红X)
        self.action_goto_exit(exit_mode=2)

        return task_list

    def action_completed_task(self, target: str):
        print("[收取任务奖励] 开始收取")

        # 点跳转
        mouse_left_click(handle=self.handle, x=int(870 * self.dpi), y=int(560 * self.dpi), sleep_time=1)

        if target == "guild":
            # 点任务
            mouse_left_click(handle=self.handle, x=int(870 * self.dpi), y=int(263 * self.dpi), sleep_time=1.5)
            # 循环遍历点击完成
            while True:
                # 点一下 让左边的选中任务颜色消失
                mouse_left_click(handle=self.handle, x=int(650 * self.dpi), y=int(300 * self.dpi), sleep_time=0.5)
                result = loop_find_picture_in_window_ml_click(handle=self.handle,
                                                              target_path=self.path_p_guild_task + "\\completed.png",
                                                              tolerance=0.99,
                                                              change_per=self.dpi,
                                                              click=True,
                                                              failed_check_time=7,  # 7s 因为偶尔会弹出美食大赛完成 需要充足时间！这个确实脑瘫...
                                                              sleep_time=0.5)
                if result:
                    loop_find_picture_in_window_ml_click(handle=self.handle,
                                                         target_path=self.path_p_guild_task + "\\gather.png",
                                                         tolerance=0.99,
                                                         change_per=self.dpi,
                                                         click=True,
                                                         failed_check_time=2,
                                                         sleep_time=2)  # 2s 完成任务有显眼动画
                else:
                    break
        if target == "spouse":
            # 点任务
            mouse_left_click(handle=self.handle, x=int(870 * self.dpi), y=int(300 * self.dpi), sleep_time=1.5)
            # 循环遍历点击完成
            while True:
                result = loop_find_picture_in_window_ml_click(handle=self.handle,
                                                              target_path=self.path_p_spouse_task + "\\completed.png",
                                                              tolerance=0.99,
                                                              change_per=self.dpi,
                                                              click=True,
                                                              failed_check_time=2,
                                                              sleep_time=2)  # 2s 完成任务有显眼动画)
                if not result:
                    break

        # 退出任务界面
        self.action_goto_exit(2)
        print("[收取任务奖励] 已全部领取")

    def check_level(self):
        if self.character_level < self.stage_info["level"]:
            return False
        else:
            return True

    def action_goto_stage(self, room_creator=True, mt_first_time=False):
        """
        只要右上能看到地球 就可以到目标关卡
        Args:
            room_creator: 是房主；仅房主创建关卡；
            mt_first_time: 魔塔关卡下 是否是第一次打(第一次塔需要进塔 第二次只需要选关卡序号)
        """

        # 拆成数组["关卡类型","地图id","关卡id"]
        stage_list = self.stage_info["id"].split("-")
        stage_0 = stage_list[0]  # type
        stage_1 = stage_list[1]  # map
        stage_2 = stage_list[2]  # stage

        def click_world_map():
            if not loop_find_picture_in_window_ml_click(handle=self.handle,
                                                        target_path=self.path_p_common + "\\Above_Map.png",
                                                        change_per=self.dpi,
                                                        sleep_time=1,
                                                        click=True,
                                                        failed_check_time=10):
                print("10s没有找到右上大地图...请找个符合要求的位置重启脚本...")

        def click_set_password():
            """设置进队密码"""
            mouse_left_click(handle=self.handle,
                             x=int(491 * self.dpi),
                             y=int(453 * self.dpi),
                             sleep_time=0.5)
            mouse_left_click(handle=self.handle,
                             x=int(600 * self.dpi),
                             y=int(453 * self.dpi),
                             sleep_time=0.5)
            key_down_up(handle=self.handle,
                        key="backspace")
            key_down_up(handle=self.handle,
                        key="1")

        def change_activity_list(serial_num: int):
            if serial_num == 1:
                if find_picture_in_window(handle=self.handle,
                                          target_path=self.path_p_common + "\\Above_JuBao.png"):
                    mouse_left_click(handle=self.handle,
                                     x=int(785 * self.dpi),
                                     y=int(30 * self.dpi),
                                     sleep_time=0.5)

            if serial_num == 2:
                if not find_picture_in_window(handle=self.handle,
                                              target_path=self.path_p_common + "\\Above_JuBao.png"):
                    mouse_left_click(handle=self.handle,
                                     x=int(785 * self.dpi),
                                     y=int(30 * self.dpi),
                                     sleep_time=0.5)

        def change_to_region(region_id: int = 2):
            mouse_left_click(handle=self.handle,
                             x=int(820 * self.dpi),
                             y=int(85 * self.dpi),
                             sleep_time=0.5)

            my_list = [85, 110, 135, 160, 185, 210, 235, 260, 285, 310, 335]
            mouse_left_click(handle=self.handle,
                             x=int(779 * self.dpi),
                             y=int(my_list[region_id - 1] * self.dpi),
                             sleep_time=2)

        def main_no():
            # 防止被活动列表遮住
            change_activity_list(2)

            # 点击世界地图
            click_world_map()

            # 点击对应的地图
            my_path = self.path_p_stage + "\\NO-" + stage_1 + ".png"
            loop_find_picture_in_window_ml_click(handle=self.handle,
                                                 target_path=my_path,
                                                 tolerance=0.995,
                                                 change_per=self.dpi,
                                                 sleep_time=2,
                                                 click=True)

            # 切区
            my_dict = {"1": 8, "2": 2, "3": 1, "4": 2, "5": 2}
            change_to_region(region_id=my_dict[stage_1])

            # 仅限主角色创建关卡
            if room_creator:
                # 选择关卡
                my_path = self.path_p_stage + "\\" + self.stage_info["id"] + ".png"
                loop_find_picture_in_window_ml_click(handle=self.handle,
                                                     target_path=my_path,
                                                     tolerance=0.995,
                                                     change_per=self.dpi,
                                                     sleep_time=0.5,
                                                     click=True)

                # 设置密码
                click_set_password()

                # 创建队伍
                my_path = self.path_p_common + "\\" + "BattleBefore_CreateStage.png"
                loop_find_picture_in_window_ml_click(handle=self.handle,
                                                     target_path=my_path,
                                                     change_per=self.dpi,
                                                     sleep_time=0.5,
                                                     click=True)

        def main_mt():
            if mt_first_time:
                # 防止被活动列表遮住
                change_activity_list(2)

                # 点击世界地图
                click_world_map()

                # 点击前往火山岛
                my_path = self.path_p_stage + "\\NO-2.png"
                loop_find_picture_in_window_ml_click(handle=self.handle,
                                                     target_path=my_path,
                                                     change_per=self.dpi,
                                                     sleep_time=2,
                                                     click=True)

                # 选区
                change_to_region(region_id=2)

            if room_creator and mt_first_time:
                # 进入魔塔
                my_path = self.path_p_stage + "\\MT.png"
                loop_find_picture_in_window_ml_click(handle=self.handle,
                                                     target_path=my_path,
                                                     change_per=self.dpi,
                                                     sleep_time=2,
                                                     click=True)

                # 根据模式进行选择
                my_dict = {"1": 46, "2": 115, "3": 188}
                mouse_left_click(self.handle, int(my_dict[stage_1] * self.dpi), int(66 * self.dpi), sleep_time=0.5)

            if room_creator:
                # 选择了密室
                if stage_1 == "3":
                    my_path = self.path_p_stage + "\\" + self.stage_info["id"] + ".png"
                    loop_find_picture_in_window_ml_click(handle=self.handle,
                                                         target_path=my_path,
                                                         change_per=self.dpi,
                                                         sleep_time=0.3,
                                                         click=True)
                # 选择了单双人爬塔
                else:
                    # 等于0则为爬塔模式 即选择最高层
                    if stage_2 != 0:
                        # 到魔塔最低一层
                        mouse_left_click(self.handle, int(47 * self.dpi), int(579 * self.dpi), sleep_time=0.3)
                        # 向右到对应位置
                        my_left = int((int(stage_2) - int(stage_2) % 15) / 15)
                        for i in range(my_left):
                            mouse_left_click(self.handle, int(152 * self.dpi), int(577 * self.dpi), sleep_time=0.3)
                        # 点击对应层数
                        my_up = int(stage_2) % 15
                        my_y = int(572 - (30.8 * my_up))
                        mouse_left_click(self.handle, int(110 * self.dpi), int(my_y * self.dpi), sleep_time=0.3)

                # 进入关卡
                my_path = self.path_p_common + "\\" + "BattleBefore_SelectStage_MagicTower_Start.png"
                loop_find_picture_in_window_ml_click(handle=self.handle,
                                                     target_path=my_path,
                                                     change_per=self.dpi,
                                                     sleep_time=1,
                                                     click=True)

        def main_cs():
            if not room_creator:
                print("跨服仅支持单人！")
            else:
                # 防止活动列表不在
                change_activity_list(1)

                # 点击进入跨服副本界面
                my_path = self.path_p_stage + "\\CS.png"
                loop_find_picture_in_window_ml_click(handle=self.handle,
                                                     target_path=my_path,
                                                     change_per=self.dpi,
                                                     sleep_time=2,
                                                     click=True)

                # 创建房间
                mouse_left_click(self.handle, int(853 * self.dpi), int(553 * self.dpi), sleep_time=0.5)

                # 选择地图
                my_x = int(stage_1) * 101 - 36
                mouse_left_click(self.handle, int(my_x * self.dpi), int(70 * self.dpi), sleep_time=1)

                # 选择关卡 设置勾选密码 并创建房间
                my_dict = {
                    "1": [124, 248], "2": [349, 248], "3": [576, 248], "4": [803, 248],
                    "5": [124, 469], "6": [349, 469], "7": [576, 469], "8": [803, 469]}
                mouse_left_click(
                    self.handle,
                    int(my_dict[stage_2][0] * self.dpi),
                    int(my_dict[stage_2][1] * self.dpi),
                    sleep_time=0.5)

                # 选择密码输入框
                my_dict = {
                    "1": [194, 248], "2": [419, 248], "3": [646, 248], "4": [873, 248],
                    "5": [194, 467], "6": [419, 467], "7": [646, 467], "8": [873, 467]}
                mouse_left_click(
                    self.handle,
                    int(my_dict[stage_2][0] * self.dpi),
                    int(my_dict[stage_2][1] * self.dpi),
                    sleep_time=0.5)

                # 输入密码
                key_down_up(self.handle, "1")

                # 创建关卡
                my_dict = {  # X+225 Y+221
                    "1": [176, 286], "2": [401, 286], "3": [629, 286], "4": [855, 286],
                    "5": [176, 507], "6": [401, 507], "7": [629, 507], "8": [855, 507]}
                mouse_left_click(
                    self.handle,
                    int(my_dict[stage_2][0] * self.dpi),
                    int(my_dict[stage_2][1] * self.dpi),
                    sleep_time=1)

        def main_or():
            # 防止活动列表不在
            change_activity_list(1)

            # 点击进入悬赏副本
            my_path = self.path_p_stage + "\\OR.png"
            loop_find_picture_in_window_ml_click(handle=self.handle,
                                                 target_path=my_path,
                                                 change_per=self.dpi,
                                                 sleep_time=2,
                                                 click=True)

            # 根据模式进行选择
            my_dict = {"1": 260, "2": 475, "3": 710}
            mouse_left_click(handle=self.handle,
                             x=int(my_dict[stage_1] * self.dpi),
                             y=int(411 * self.dpi),
                             sleep_time=2)

            # 切区
            my_dict = {"1": 8, "2": 2, "3": 2}
            change_to_region(region_id=my_dict[stage_1])

            # 仅限创房间的人
            if room_creator:
                # 设置密码
                click_set_password()
                # 创建队伍
                mouse_left_click(handle=self.handle,
                                 x=int(583 * self.dpi),
                                 y=int(500 * self.dpi),
                                 sleep_time=0.5)

        def main_ex():
            # 防止被活动列表遮住
            change_activity_list(2)

            # 点击世界地图
            click_world_map()

            # 点击对应的地图
            loop_find_picture_in_window_ml_click(handle=self.handle,
                                                 target_path="{}\\EX-1.png".format(self.path_p_stage),
                                                 change_per=self.dpi,
                                                 sleep_time=2,
                                                 click=True)
            # 不是营地
            if stage_1 != "1":
                # 找船
                loop_find_picture_in_window_ml_click(handle=self.handle,
                                                     target_path="{}\\EX-Ship.png".format(self.path_p_stage),
                                                     change_per=self.dpi,
                                                     sleep_time=1.5,
                                                     click=True)
                # 找地图图标
                loop_find_picture_in_window_ml_click(handle=self.handle,
                                                     target_path="{}\\EX-{}.png".format(self.path_p_stage, stage_1),
                                                     change_per=self.dpi,
                                                     sleep_time=1.5,
                                                     click=True)

            # 切区
            change_to_region(region_id=2)

            # 仅限主角色创建关卡
            if room_creator:
                # 选择关卡
                my_path = "{}\\{}.png".format(self.path_p_stage, self.stage_info["id"])
                loop_find_picture_in_window_ml_click(handle=self.handle,
                                                     target_path=my_path,
                                                     change_per=self.dpi,
                                                     sleep_time=0.5,
                                                     click=True)

                # 设置密码
                click_set_password()

                # 创建队伍
                my_path = "{}\\BattleBefore_CreateStage.png".format(self.path_p_common)
                loop_find_picture_in_window_ml_click(handle=self.handle,
                                                     target_path=my_path,
                                                     change_per=self.dpi,
                                                     sleep_time=0.5,
                                                     click=True)

        if stage_0 == "NO":
            main_no()
        elif stage_0 == "MT":
            main_mt()
        elif stage_0 == "CS":
            main_cs()
        elif stage_0 == "OR":
            main_or()
        elif stage_0 == "EX":
            main_ex()
        else:
            print("请输入正确的关卡名称！")

    def action_goto_exit(self, exit_mode: int):
        """打完后是否退出 0-不退出  1-右下回退到上一级  2-右上红叉  3-直接到竞技岛"""
        if exit_mode == 1:
            mouse_left_click(handle=self.handle,
                             x=int(918 * self.dpi),
                             y=int(558 * self.dpi),
                             sleep_time=1)

        if exit_mode == 2:
            my_path = self.path_p_common + "\\BattleBefore_Exit_X.png"
            loop_find_picture_in_window_ml_click(handle=self.handle,
                                                 target_path=my_path,
                                                 change_per=self.dpi,
                                                 sleep_time=1,
                                                 click=True)

        if exit_mode == 3:
            mouse_left_click(handle=self.handle,
                             x=int(871 * self.dpi),
                             y=int(558 * self.dpi),
                             sleep_time=0.3)
            mouse_left_click(handle=self.handle,
                             x=int(871 * self.dpi),
                             y=int(386 * self.dpi),
                             sleep_time=0.7)

    def action_battle_normal(self, battle_mode: int, task_card: str, list_ban_card: list):
        """
        战斗中放卡的函数
        Args:
            :param battle_mode: 0 常规模式 1 试验模式
            :param task_card:
            :param list_ban_card:
        """

        list_cell_all, list_shovel = solve_cell_all_card(stage_info=self.stage_info,
                                                         is_group=self.is_group,
                                                         player=self.player,
                                                         battle_plan=self.battle_plan["card"],
                                                         task_card=task_card,
                                                         list_ban_card=list_ban_card)
        # 放人物
        for i in self.battle_plan["player"]:
            self.battle_use_player(i)

        # 铲自带的卡
        if self.player == "1P":
            self.battle_use_shovel(position=list_shovel)

        # 战斗循环
        if battle_mode == 0:
            # 0 多线程遍历模式 布阵慢 补阵快 性能开销略大 是遍历模式的优化
            self.battle_use_card_loop_0(list_cell_all=list_cell_all)
        elif battle_mode == 1:
            # 1 备用拓展
            self.battle_use_card_loop_1(list_cell_all=list_cell_all)
        else:
            print(list_cell_all, list_shovel)
            print("不战斗 用于测试战斗数组的计算")

    def action_battle_skill(self):
        # 放人
        self.battle_use_player("5-4")

        # 计算目标位置 1-14
        cell_list = []
        for i in range(2):
            for j in range(9):
                cell_list.append(str(j + 1) + "-" + str(i + 2))

        # 常规放卡
        for k in range(13):
            self.battle_use_card_once(num_card=k + 1, num_cell=cell_list[k], click_space=False)
            sleep(0.07)

        # 叠加放卡
        # for k in range(3):
        #     msdzls.battle_use_card(k*2 + 1 + 8, cell_list[k + 8], click_space=False)
        #     sleep(0.15)
        #     msdzls.battle_use_card(k*2 + 2 + 8, cell_list[k + 8], click_space=False)
        #     sleep(0.05)

        # 退出关卡
        mouse_left_click(handle=self.handle,
                         x=int(920 * self.dpi),
                         y=int(580 * self.dpi),
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

        mouse_left_click(handle=self.handle,
                         x=int(920 * self.dpi),
                         y=int(580 * self.dpi),
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

        # 确定退出
        mouse_left_click(handle=self.handle,
                         x=int(449 * self.dpi),
                         y=int(382 * self.dpi),
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

    """战斗中函数"""

    def battle_use_player(self, num_cell):
        mouse_left_click(handle=self.handle,
                         x=self.battle_cell[num_cell][0],
                         y=self.battle_cell[num_cell][1],
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

    def battle_use_card_once(self, num_card: int, num_cell: str, click_space=True):
        """
        Args:
            num_card: 使用的卡片的序号
            num_cell: 使用的卡片对应的格子 从左上开始 "1-1" to "9-7"
            click_space:  是否点一下空白地区防卡住
        """
        # 注 美食大战老鼠中 放卡动作 需要按下一下 然后拖动 然后按下并松开 才能完成 整个动作
        mouse_left_click(handle=self.handle,
                         x=self.battle_card[num_card][0],
                         y=self.battle_card[num_card][1],
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

        mouse_left_click(handle=self.handle,
                         x=self.battle_cell[num_cell][0],
                         y=self.battle_cell[num_cell][1],
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

        # 点一下空白
        if click_space:
            self.battle_click_space()

    def battle_click_space(self):
        """战斗中点空白"""
        mouse_move_to(handle=self.handle,
                      x=200,
                      y=350)
        mouse_left_click(handle=self.handle,
                         x=200,
                         y=350,
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

    def battle_use_shovel(self, position: list = None):
        """
        用铲子
        Args:
            position: 放哪些格子
        """
        if position is None:
            position = []

        for target in position:
            key_down_up(handle=self.handle, key="1")
            mouse_left_click(handle=self.handle,
                             x=self.battle_cell[target][0],
                             y=self.battle_cell[target][1],
                             interval_time=self.click_interval,
                             sleep_time=self.click_sleep)

    def battle_use_key(self):
        if self.is_use_key:
            if find_picture_in_window(handle=self.handle,
                                      target_path=self.path_p_common + "\\Battle_NextNeed.png"):
                mouse_left_click(handle=self.handle,
                                 x=int(427 * self.dpi),
                                 y=int(360 * self.dpi),
                                 interval_time=self.click_interval,
                                 sleep_time=self.click_sleep)

    def battle_end_check(self):
        # 找到战利品字样(被黑色透明物遮挡,会看不到)
        return find_pictures_in_window(handle=self.handle,
                                       opts=[{"target_path": self.path_p_common + "\\BattleEnd_1_Loot.png",
                                              "tolerance": 0.999},
                                             {"target_path": self.path_p_common + "\\BattleEnd_2_Loot.png",
                                              "tolerance": 0.999},
                                             {"target_path": self.path_p_common + "\\BattleEnd_3_Summarize.png",
                                              "tolerance": 0.999},
                                             {"target_path": self.path_p_common + "\\BattleEnd_4_Chest.png",
                                              "tolerance": 0.999},
                                             {"target_path": self.path_p_common + "\\BattleBefore_ReadyCheckStart.png",
                                              "tolerance": 0.999}],
                                       mode="or")

    def battle_auto_collect(self):
        if self.is_auto_collect:
            coordinates = ["1-1", "2-1", "3-1", "4-1", "5-1", "6-1", "7-1", "8-1", "9-1",
                           "8-2", "9-2",
                           "8-3", "9-3",
                           "8-4", "9-4",
                           "8-5", "9-5",
                           "8-6", "9-6",
                           "1-7", "2-7", "3-7", "4-7", "5-7", "6-7", "7-7", "8-7", "9-7"]

            for coordinate in coordinates:
                mouse_move_to(handle=self.handle,
                              x=self.battle_cell[coordinate][0],
                              y=self.battle_cell[coordinate][1])
                sleep(self.click_sleep)

    def battle_use_card_somewhere(self, j):
        """
        防误触的使用一张卡
        :param j: 卡片坐标str 例如 "1-3"
        """
        # 防止误触
        if j == "4-4" or j == "4-5" or j == "5-4" or j == "5-4":
            self.battle_use_key()
        # 点击 放下卡片
        mouse_left_click(handle=self.handle,
                         x=self.battle_cell[j][0],
                         y=self.battle_cell[j][1],
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

    def use_weapon_skill(self):
        mouse_left_click(handle=self.handle,
                         x=int(23 * self.dpi),
                         y=int(200 * self.dpi),
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)
        mouse_left_click(handle=self.handle,
                         x=int(23 * self.dpi),
                         y=int(250 * self.dpi),
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)
        mouse_left_click(handle=self.handle,
                         x=int(23 * self.dpi),
                         y=int(297 * self.dpi),
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

    def battle_use_card_loop_0(self, list_cell_all):
        """循环方式 每一个卡都先在其对应的全部的位置放一次,再放下一张(每轮开始位置+1)"""
        # 用flag值来停止循环
        battle_flag = True

        while battle_flag:
            # 尝试使用一下钥匙 和检测战斗结束
            self.battle_use_key()
            if self.battle_end_check():
                break

            # 计时每轮开始的时间
            time_round_begin = time()

            # 遍历每一张卡
            for i in range(len(list_cell_all)):
                # 启动了自动战斗
                if self.is_auto_battle:
                    # 点击 选中卡片
                    mouse_left_click(handle=self.handle,
                                     x=self.battle_card[list_cell_all[i]["id"]][0],
                                     y=self.battle_card[list_cell_all[i]["id"]][1],
                                     interval_time=self.click_interval,
                                     sleep_time=self.click_sleep)

                    if list_cell_all[i]["ergodic"]:
                        # 遍历该卡每一个可以放的位置
                        for j in list_cell_all[i]["location"]:
                            self.battle_use_card_somewhere(j=j)
                    else:
                        # 只放一下
                        j = list_cell_all[i]["location"][0]
                        self.battle_use_card_somewhere(j=j)

                    self.battle_click_space()  # 放卡后点一下

                # 尝试使用一下钥匙 和检测战斗结束
                self.battle_use_key()
                if self.battle_end_check():  # 尝试找到战斗结束的迹象 来改变flag 并中断放卡循环
                    battle_flag = False
                    break

            # 放完一轮卡后 在位置数组里 将每个卡的 第一个位置移到最后
            for i in range(len(list_cell_all)):
                if list_cell_all[i]["queue"]:
                    list_cell_all[i]["location"].append(list_cell_all[i]["location"][0])
                    list_cell_all[i]["location"].remove(list_cell_all[i]["location"][0])

            # 武器技能
            self.use_weapon_skill()

            # 自动收集
            self.battle_auto_collect()

            # 计算一下
            time_spend = time() - time_round_begin

            # 仅调试
            # print(self.player, time_spend)

            # 如果一轮间隔不到3.5s 休息到3.5s 尝试使用钥匙和结束战斗, 再休息到7.0s
            if time_spend < 3.5:
                sleep(3.5 - time_spend)
                self.battle_use_key()
                if self.battle_end_check():
                    break
                sleep(3.5)
            # 如果一轮间隔3.5-7.0s之间 那就休息到7.0s
            elif time_spend < 7.0:
                sleep(7.0 - time_spend)

    def battle_use_card_loop_1(self, list_cell_all):
        """循环方式 每一个卡都先在其对应的全部的位置放一次,再放下一张(每轮开始位置+1)"""
        # 用flag值来停止循环
        battle_flag = True

        while battle_flag:
            # 尝试使用一下钥匙 和检测战斗结束
            self.battle_use_key()
            if self.battle_end_check():
                break

            # 计时每轮开始的时间
            time_round_begin = time()

            # 遍历每一张卡
            for i in range(len(list_cell_all)):
                # 启动了自动战斗
                if self.is_auto_battle:
                    # 点击 选中卡片
                    mouse_left_click(handle=self.handle,
                                     x=self.battle_card[list_cell_all[i]["id"]][0],
                                     y=self.battle_card[list_cell_all[i]["id"]][1],
                                     interval_time=0.03,
                                     sleep_time=0.03)

                    if list_cell_all[i]["ergodic"]:
                        # 遍历该卡每一个可以放的位置
                        for j in list_cell_all[i]["location"]:
                            self.battle_use_card_somewhere(j=j)
                    else:
                        # 只放一下
                        j = list_cell_all[i]["location"][0]
                        self.battle_use_card_somewhere(j=j)

                    self.battle_click_space()  # 放卡后点一下

                # 尝试使用一下钥匙 和检测战斗结束
                self.battle_use_key()
                if self.battle_end_check():  # 尝试找到战斗结束的迹象 来改变flag 并中断放卡循环
                    battle_flag = False
                    break

            # 放完一轮卡后 在位置数组里 将每个卡的 第一个位置移到最后
            for i in range(len(list_cell_all)):
                if list_cell_all[i]["queue"]:
                    list_cell_all[i]["location"].append(list_cell_all[i]["location"][0])
                    list_cell_all[i]["location"].remove(list_cell_all[i]["location"][0])

            # 自动收集
            self.battle_auto_collect()

            # 如果一轮间隔不到3.5s 休息到3.5s 尝试使用钥匙和结束战斗, 再休息到7.0s
            time_spend = time() - time_round_begin

            if time_spend < 3.5:
                sleep(3.5 - time_spend)
                self.battle_use_key()
                if self.battle_end_check():
                    break
                sleep(3.5)
            # 如果一轮间隔3.5-7.0s之间 那就休息到7.0s
            elif time_spend < 7.0:
                sleep(7.0 - time_spend)


if __name__ == '__main__':
    def main():
        faa = FAA()
        faa.get_config_for_battle(True, 1, "NO-5-3")
        list_cell_all, list_shovel = solve_cell_all_card(stage_info=faa.stage_info,
                                                         is_group=faa.is_group,
                                                         battle_plan=faa.battle_plan["card"],
                                                         player="2P",
                                                         task_card="None",
                                                         list_ban_card=[])
        print(list_cell_all)


    main()
