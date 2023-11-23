import json
import os
import re
from time import sleep

import numpy as np
from cv2 import imread

from function.common.bg_keyboard import key_down_up
from function.common.bg_mouse import mouse_left_click
from function.common.bg_p_compare import find_p_in_w, loop_find_p_in_w
from function.common.bg_p_screenshot import capture_picture_png
from function.get_paths import get_paths_faa_new
from function.script.scattered.gat_handle import faa_get_handle
from function.script.scattered.get_battle_plan_list import get_battle_plan_list
from function.script.service.in_battle.round_of_battle import RoundOfBattle
from function.script.service.in_battle.round_of_game import round_of_game


class FAA:
    def __init__(
            self,
            channel="锑食", zoom=1, serve_id="1", player="1P", character_level=1,
            is_use_key=True, is_auto_battle=True, is_auto_collect=False
    ):

        # 获取窗口句柄
        self.handle = faa_get_handle(channel=channel, mode="game")
        self.handle_browser = faa_get_handle(channel=channel, mode="browser")
        self.handle_360 = faa_get_handle(channel=channel, mode="360")

        # 缩放
        self.zoom = zoom  # float 1.0 即百分百
        self.serve_id = serve_id

        # 角色|等级|是否使用钥匙|卡片|收集战利品
        self.player = player
        self.character_level = character_level
        self.is_use_key = is_use_key
        self.is_auto_battle = is_auto_battle
        self.is_auto_collect = is_auto_collect

        # 资源文件路径
        self.paths = get_paths_faa_new()

        # 每个副本的战斗都不一样的参数 使用内部函数调用更改
        self.is_group = False
        self.battle_plan = None
        self.stage_info = None

    """调用输入关卡配置和战斗配置, 在战斗前进行该操作"""

    def get_config_for_battle(
            self, is_group=False, battle_plan_index=0, stage_id="NO-1-1"
    ):
        """
        :param is_group: 是否组队
        :param battle_plan_index: 战斗方案的索引
        :param stage_id: 关卡的id
        :return:
        """

        self.is_group = is_group

        def read_json_to_battle_plan():
            battle_plan_list = get_battle_plan_list(with_extension=True)
            battle_plan_path = "{}\\battle_plan\\{}".format(
                self.paths["config"],
                battle_plan_list[battle_plan_index]
            )
            with open(battle_plan_path, "r", encoding="UTF-8") as file:
                return json.load(file)

        def read_json_to_stage_info():
            """读取文件中是否存在预设"""
            with open(self.paths["config"] + "//opt_stage_info.json", "r", encoding="UTF-8") as file:
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

    def action_get_stage_name(
            self
    ):
        """在关卡备战界面 获得关卡名字"""
        stage_id = "Unknown"  # 默认名称
        img1 = capture_picture_png(handle=self.handle, raw_range=[0, 0, 950, 600])[468:484, 383:492, :3]
        # 关卡名称集 从资源文件夹自动获取, 资源文件命名格式：关卡名称.png
        stage_text_in_ready_check = []
        for i in os.listdir(self.paths["picture"]["ready_check_stage"]):
            if i.find(".png") != -1:
                stage_text_in_ready_check.append(i.split(".")[0])
        for i in stage_text_in_ready_check:
            if np.all(img1 == imread(self.paths["picture"]["ready_check_stage"] + "\\" + i + ".png", 1)):
                stage_id = i
                break
        return stage_id

    def action_get_task(
            self, target: str
    ):
        """
        获取公会任务列表
        :param target:
        :return: [
            {
                "stage_id":str,
                "max_times":,
                "task_card":str,
                "ban_card":None
            },
        ]
        """
        # 点跳转
        loop_find_p_in_w(raw_w_handle=self.handle,
                         raw_range=[0, 0, 950, 600],
                         target_path=self.paths["picture"]["common"] + "\\bottom_menu_goto.png",
                         target_sleep=1,
                         click=True,
                         click_zoom=self.zoom)

        # 点任务
        if target == "guild":
            # 公会任务 guild
            loop_find_p_in_w(raw_w_handle=self.handle,
                             raw_range=[0, 0, 950, 600],
                             target_path=self.paths["picture"]["common"] + "\\bottom_menu_goto_guild_task.png",
                             target_sleep=1,
                             click=True,
                             click_zoom=self.zoom)
            # 点一下 让左边的选中任务颜色消失
            loop_find_p_in_w(raw_w_handle=self.handle,
                             raw_range=[0, 0, 950, 600],
                             target_path=self.paths["picture"]["guild_task"] + "\\ui.png",
                             target_sleep=0.5,
                             click=True,
                             click_zoom=self.zoom)
        if target == "spouse":
            # 情侣任务 spouse
            loop_find_p_in_w(raw_w_handle=self.handle,
                             raw_range=[0, 0, 950, 600],
                             target_path=self.paths["picture"]["common"] + "\\bottom_menu_goto_spouse_task.png",
                             target_sleep=1,
                             click=True,
                             click_zoom=self.zoom)

        # 读取
        task_list = []
        # 公会任务 guild
        if target == "guild":
            path = self.paths["picture"]["guild_task"]
            for i in range(7):
                # 遍历任务
                for j in os.listdir("{}\\{}\\".format(path, str(i + 1))):
                    # 找到任务 加入任务列表
                    find_p = find_p_in_w(raw_w_handle=self.handle,
                                         raw_range=[0, 0, 950, 600],
                                         target_path="{}\\{}\\{}".format(path, str(i + 1), j),
                                         target_tolerance=0.999)
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
            path = self.paths["picture"]["spouse_task"]
            for i in ["1", "2", "3"]:
                # 任务未完成
                find_p = find_p_in_w(raw_w_handle=self.handle,
                                     raw_range=[0, 0, 950, 600],
                                     target_path="{}\\NO-{}.png".format(path, i),
                                     target_tolerance=0.999)
                if find_p:
                    # 遍历任务
                    for j in os.listdir("{}\\{}\\".format(path, i)):
                        # 找到任务 加入任务列表
                        find_p = find_p_in_w(raw_w_handle=self.handle,
                                             raw_range=[0, 0, 950, 600],
                                             target_path="{}\\{}\\{}".format(path, i, j),
                                             target_tolerance=0.999)
                        if find_p:
                            task_list.append({"is_group": True,
                                              "stage_id": j.split(".")[0],
                                              "max_times": 1,
                                              "task_card": "None",
                                              "list_ban_card": [],
                                              "dict_exit": {"other_time": [0], "last_time": [3]}})

        # 关闭公会任务列表(红X)
        self.action_exit(exit_mode=2)

        return task_list

    """receive task reward"""

    def action_task_guild(
            self
    ):
        # 点跳转
        loop_find_p_in_w(raw_w_handle=self.handle,
                         raw_range=[0, 0, 950, 600],
                         target_path=self.paths["picture"]["common"] + "\\bottom_menu_goto.png",
                         target_sleep=1,
                         click=True,
                         click_zoom=self.zoom)
        # 点任务
        loop_find_p_in_w(raw_w_handle=self.handle,
                         raw_range=[0, 0, 950, 600],
                         target_path=self.paths["picture"]["common"] + "\\bottom_menu_goto_guild_task.png",
                         target_sleep=1,
                         click=True,
                         click_zoom=self.zoom)
        # 循环遍历点击完成
        while True:
            # 点一下 让左边的选中任务颜色消失
            loop_find_p_in_w(raw_w_handle=self.handle,
                             raw_range=[0, 0, 950, 600],
                             target_path=self.paths["picture"]["guild_task"] + "\\ui.png",
                             target_sleep=0.5,
                             click=True,
                             click_zoom=self.zoom)
            result = loop_find_p_in_w(raw_w_handle=self.handle,
                                      raw_range=[0, 0, 950, 600],
                                      target_path=self.paths["picture"]["guild_task"] + "\\completed.png",
                                      target_tolerance=0.99,
                                      click_zoom=self.zoom,
                                      click=True,
                                      target_failed_check=7,  # 7s 因为偶尔会弹出美食大赛完成 需要充足时间！这个确实脑瘫...
                                      target_sleep=0.5)
            if result:
                loop_find_p_in_w(raw_w_handle=self.handle,
                                 raw_range=[0, 0, 950, 600],
                                 target_path=self.paths["picture"]["guild_task"] + "\\gather.png",
                                 target_tolerance=0.99,
                                 click_zoom=self.zoom,
                                 click=True,
                                 target_failed_check=2,
                                 target_sleep=2)  # 2s 完成任务有显眼动画
            else:
                break
        # 退出任务界面
        self.action_exit(exit_mode=2)

    def action_task_spouse(
            self
    ):
        # 点跳转
        loop_find_p_in_w(raw_w_handle=self.handle,
                         raw_range=[0, 0, 950, 600],
                         target_path=self.paths["picture"]["common"] + "\\bottom_menu_goto.png",
                         target_sleep=1,
                         click=True,
                         click_zoom=self.zoom)
        # 点任务
        # 点任务
        loop_find_p_in_w(raw_w_handle=self.handle,
                         raw_range=[0, 0, 950, 600],
                         target_path=self.paths["picture"]["common"] + "\\bottom_menu_goto_spouse_task.png",
                         target_sleep=1,
                         click=True,
                         click_zoom=self.zoom)
        # 循环遍历点击完成
        while True:
            result = loop_find_p_in_w(raw_w_handle=self.handle,
                                      raw_range=[0, 0, 950, 600],
                                      target_path=self.paths["picture"]["spouse_task"] + "\\completed.png",
                                      target_tolerance=0.99,
                                      click_zoom=self.zoom,
                                      click=True,
                                      target_failed_check=2,
                                      target_sleep=2)  # 2s 完成任务有显眼动画)
            if not result:
                break
        # 退出任务界面
        self.action_exit(exit_mode=2)

    def action_task_offer_reward(
            self
    ):
        # 防止活动列表不在
        self.change_activity_list(1)

        # 点击进入OR界面
        loop_find_p_in_w(raw_w_handle=self.handle,
                         raw_range=[0, 0, 950, 600],
                         target_path=self.paths["picture"]["stage"] + "\\OR.png",
                         target_sleep=2,
                         click=True,
                         click_zoom=self.zoom)

        # 循环遍历点击完成
        while True:
            result = loop_find_p_in_w(raw_w_handle=self.handle,
                                      raw_range=[0, 0, 950, 600],
                                      target_path=self.paths["picture"]["common"] + "\\offer_reward_get_loot.png",
                                      target_tolerance=0.99,
                                      click_zoom=self.zoom,
                                      click=True,
                                      target_failed_check=2,
                                      target_sleep=2)
            if not result:
                break

        # 退出任务界面
        self.action_exit(exit_mode=2)

    def action_task_receive_rewards(
            self, task_type: str
    ):
        """
        收取任务奖励
        :param task_type: "guild" or "spouse" or "offer_reward"
        :return:
        """
        print("[{}][收取任务奖励][{}] 开始收取".format(self.player, task_type))

        if task_type == "guild":
            self.action_task_guild()
        if task_type == "spouse":
            self.action_task_spouse()
        if task_type == "offer_reward":
            self.action_task_offer_reward()

        print("[{}][收取任务奖励][{}] 已全部领取".format(self.player, task_type))

    def change_activity_list(
            self, serial_num: int
    ):
        """检测顶部的活动清单, 1为第一页, 2为第二页(有举报图标的一页)"""

        target = find_p_in_w(raw_w_handle=self.handle,
                             raw_range=[0, 0, 950, 600],
                             target_path=self.paths["picture"]["common"] + "\\above_report.png")

        if serial_num == 1:
            if target:
                mouse_left_click(handle=self.handle,
                                 x=int(785 * self.zoom),
                                 y=int(30 * self.zoom),
                                 sleep_time=0.5)

        if serial_num == 2:
            if not target:
                mouse_left_click(handle=self.handle,
                                 x=int(785 * self.zoom),
                                 y=int(30 * self.zoom),
                                 sleep_time=0.5)

    """battle enter / in combat / exit"""

    def check_level(
            self
    ):
        """检测角色等级和关卡等级(调用于输入关卡信息之后)"""
        if self.character_level < self.stage_info["level"]:
            return False
        else:
            return True

    def action_goto_stage(
            self,
            room_creator: bool = True,
            mt_first_time: bool = False
    ):
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
            if not loop_find_p_in_w(raw_w_handle=self.handle,
                                    raw_range=[0, 0, 950, 600],
                                    target_path=self.paths["picture"]["common"] + "\\above_map.png",
                                    click_zoom=self.zoom,
                                    target_sleep=1,
                                    click=True,
                                    target_failed_check=10):
                print("10s没有找到右上大地图...请找个符合要求的位置重启脚本...")

        def click_set_password():
            """设置进队密码"""
            mouse_left_click(handle=self.handle,
                             x=int(491 * self.zoom),
                             y=int(453 * self.zoom),
                             sleep_time=0.5)
            mouse_left_click(handle=self.handle,
                             x=int(600 * self.zoom),
                             y=int(453 * self.zoom),
                             sleep_time=0.5)
            key_down_up(handle=self.handle,
                        key="backspace")
            key_down_up(handle=self.handle,
                        key="1")
            sleep(1)

        def change_to_region(region_id: int = 2):
            mouse_left_click(handle=self.handle,
                             x=int(820 * self.zoom),
                             y=int(85 * self.zoom),
                             sleep_time=0.5)

            my_list = [85, 110, 135, 160, 185, 210, 235, 260, 285, 310, 335]
            mouse_left_click(handle=self.handle,
                             x=int(779 * self.zoom),
                             y=int(my_list[region_id - 1] * self.zoom),
                             sleep_time=2)

        def main_no():
            # 防止被活动列表遮住
            self.change_activity_list(2)

            # 点击世界地图
            click_world_map()

            # 点击对应的地图
            my_path = self.paths["picture"]["stage"] + "\\NO-" + stage_1 + ".png"
            loop_find_p_in_w(raw_w_handle=self.handle,
                             raw_range=[0, 0, 950, 600],
                             target_path=my_path,
                             target_tolerance=0.995,
                             click_zoom=self.zoom,
                             target_sleep=2,
                             click=True)

            # 切区
            my_dict = {"1": 8, "2": 2, "3": 1, "4": 2, "5": 2}
            change_to_region(region_id=my_dict[stage_1])

            # 仅限主角色创建关卡
            if room_creator:
                # 选择关卡
                my_path = self.paths["picture"]["stage"] + "\\" + self.stage_info["id"] + ".png"
                loop_find_p_in_w(raw_w_handle=self.handle,
                                 raw_range=[0, 0, 950, 600],
                                 target_path=my_path,
                                 click_zoom=self.zoom,
                                 target_tolerance=0.995,
                                 target_sleep=1, click=True)

                # 设置密码
                click_set_password()

                # 创建队伍
                my_path = self.paths["picture"]["common"] + "\\" + "battle_before_create_stage.png"
                loop_find_p_in_w(raw_w_handle=self.handle,
                                 raw_range=[0, 0, 950, 600],
                                 target_path=my_path,
                                 click_zoom=self.zoom,
                                 target_sleep=1, click=True)

        def main_mt():
            if mt_first_time:
                # 防止被活动列表遮住
                self.change_activity_list(2)

                # 点击世界地图
                click_world_map()

                # 点击前往海底
                my_path = self.paths["picture"]["stage"] + "\\NO-5.png"
                loop_find_p_in_w(raw_w_handle=self.handle,
                                 raw_range=[0, 0, 950, 600],
                                 target_path=my_path,
                                 click_zoom=self.zoom,
                                 target_sleep=2,
                                 click=True)

                # 选区
                change_to_region(region_id=2)

            if room_creator and mt_first_time:
                # 进入魔塔
                my_path = self.paths["picture"]["stage"] + "\\MT.png"
                loop_find_p_in_w(raw_w_handle=self.handle,
                                 raw_range=[0, 0, 950, 600],
                                 target_path=my_path,
                                 click_zoom=self.zoom,
                                 target_sleep=2,
                                 click=True)

                # 根据模式进行选择
                my_dict = {"1": 46, "2": 115, "3": 188}
                mouse_left_click(self.handle, int(my_dict[stage_1] * self.zoom), int(66 * self.zoom), sleep_time=0.5)

            if room_creator:
                # 选择了密室
                if stage_1 == "3":
                    my_path = self.paths["picture"]["stage"] + "\\" + self.stage_info["id"] + ".png"
                    loop_find_p_in_w(raw_w_handle=self.handle,
                                     raw_range=[0, 0, 950, 600],
                                     target_path=my_path,
                                     click_zoom=self.zoom,
                                     target_sleep=0.3,
                                     click=True)
                # 选择了单双人爬塔
                else:
                    # 等于0则为爬塔模式 即选择最高层
                    if stage_2 != 0:
                        # 到魔塔最低一层
                        mouse_left_click(self.handle, int(47 * self.zoom), int(579 * self.zoom), sleep_time=0.3)
                        # 向右到对应位置
                        my_left = int((int(stage_2) - 1) / 15)
                        for i in range(my_left):
                            mouse_left_click(self.handle, int(152 * self.zoom), int(577 * self.zoom), sleep_time=0.3)
                        # 点击对应层数
                        my_y = int(542 - (30.8 * (int(stage_2) - my_left * 15 - 1)))
                        mouse_left_click(self.handle, int(110 * self.zoom), int(my_y * self.zoom), sleep_time=0.3)

                # 进入关卡
                my_path = self.paths["picture"]["common"] + "\\" + "battle_before_select_stage_magic_tower_start.png"
                loop_find_p_in_w(raw_w_handle=self.handle,
                                 raw_range=[0, 0, 950, 600],
                                 target_path=my_path,
                                 click_zoom=self.zoom,
                                 target_sleep=1,
                                 click=True)

        def main_cs():
            # 防止活动列表不在
            self.change_activity_list(1)

            # 点击进入跨服副本界面
            loop_find_p_in_w(raw_w_handle=self.handle,
                             raw_range=[0, 0, 950, 600],
                             target_path=self.paths["picture"]["stage"] + "\\CS.png",
                             target_sleep=2,
                             click=True,
                             click_zoom=self.zoom)

            if room_creator:
                # 创建房间
                mouse_left_click(self.handle, int(853 * self.zoom), int(553 * self.zoom), sleep_time=0.5)

                # 选择地图
                my_x = int(stage_1) * 101 - 36
                mouse_left_click(self.handle, int(my_x * self.zoom), int(70 * self.zoom), sleep_time=1)

                # 选择关卡 设置勾选密码 并创建房间
                my_dict = {
                    "1": [124, 248], "2": [349, 248], "3": [576, 248], "4": [803, 248],
                    "5": [124, 469], "6": [349, 469], "7": [576, 469], "8": [803, 469]}
                mouse_left_click(
                    self.handle,
                    int(my_dict[stage_2][0] * self.zoom),
                    int(my_dict[stage_2][1] * self.zoom),
                    sleep_time=0.5)

                # 选择密码输入框
                my_dict = {
                    "1": [194, 248], "2": [419, 248], "3": [646, 248], "4": [873, 248],
                    "5": [194, 467], "6": [419, 467], "7": [646, 467], "8": [873, 467]}
                mouse_left_click(
                    self.handle,
                    int(my_dict[stage_2][0] * self.zoom),
                    int(my_dict[stage_2][1] * self.zoom),
                    sleep_time=0.5)

                # 输入密码
                key_down_up(self.handle, "1")

                # 创建关卡
                my_dict = {  # X+225 Y+221
                    "1": [176, 286], "2": [401, 286], "3": [629, 286], "4": [855, 286],
                    "5": [176, 507], "6": [401, 507], "7": [629, 507], "8": [855, 507]}
                mouse_left_click(
                    self.handle,
                    int(my_dict[stage_2][0] * self.zoom),
                    int(my_dict[stage_2][1] * self.zoom),
                    sleep_time=1)
            else:
                # 刷新
                mouse_left_click(self.handle, int(895 * self.zoom), int(80 * self.zoom), sleep_time=3)
                # 复位
                mouse_left_click(self.handle, int(602 * self.zoom), int(490 * self.zoom), sleep_time=0.1)
                for i in range(20):
                    find = loop_find_p_in_w(raw_w_handle=self.handle,
                                            raw_range=[0, 0, 950, 600],
                                            target_path=self.paths["picture"]["common"] + "\\cross_server_1p.png",
                                            click_zoom=self.zoom,
                                            click=True,
                                            target_sleep=2.0,
                                            target_failed_check=1.0)
                    if find:
                        break
                    else:
                        mouse_left_click(self.handle, int(700 * self.zoom), int(490 * self.zoom), sleep_time=0.1)
                        # 下一页

                # 输入密码 确定进入
                key_down_up(handle=self.handle, key="1")
                mouse_left_click(self.handle, int(490 * self.zoom), int(360 * self.zoom), sleep_time=0.1)

        def main_or():
            # 防止活动列表不在
            self.change_activity_list(1)

            # 点击进入悬赏副本
            my_path = self.paths["picture"]["stage"] + "\\OR.png"
            loop_find_p_in_w(raw_w_handle=self.handle,
                             raw_range=[0, 0, 950, 600],
                             target_path=my_path,
                             click_zoom=self.zoom,
                             target_sleep=2, click=True)

            # 根据模式进行选择
            my_dict = {"1": 260, "2": 475, "3": 710}
            mouse_left_click(handle=self.handle,
                             x=int(my_dict[stage_1] * self.zoom),
                             y=int(411 * self.zoom),
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
                                 x=int(583 * self.zoom),
                                 y=int(500 * self.zoom),
                                 sleep_time=0.5)

        def main_ex():
            # 防止被活动列表遮住
            self.change_activity_list(2)

            # 点击世界地图
            click_world_map()

            # 点击对应的地图
            loop_find_p_in_w(raw_w_handle=self.handle,
                             raw_range=[0, 0, 950, 600],
                             target_path="{}\\EX-1.png".format(self.paths["picture"]["stage"]),
                             click_zoom=self.zoom,
                             target_sleep=2,
                             click=True)
            # 不是营地
            if stage_1 != "1":
                # 找船
                loop_find_p_in_w(raw_w_handle=self.handle,
                                 raw_range=[0, 0, 950, 600],
                                 target_path="{}\\EX-Ship.png".format(self.paths["picture"]["stage"]),
                                 click_zoom=self.zoom,
                                 target_sleep=1.5,
                                 click=True)
                # 找地图图标
                loop_find_p_in_w(raw_w_handle=self.handle,
                                 raw_range=[0, 0, 950, 600],
                                 target_path="{}\\EX-{}.png".format(self.paths["picture"]["stage"], stage_1),
                                 click_zoom=self.zoom,
                                 target_sleep=1.5,
                                 click=True)

            # 切区
            change_to_region(region_id=2)

            # 仅限主角色创建关卡
            if room_creator:
                # 选择关卡
                my_path = "{}\\{}.png".format(self.paths["picture"]["stage"], self.stage_info["id"])
                loop_find_p_in_w(raw_w_handle=self.handle,
                                 raw_range=[0, 0, 950, 600],
                                 target_path=my_path,
                                 click_zoom=self.zoom,
                                 target_sleep=0.5,
                                 click=True)

                # 设置密码
                click_set_password()

                # 创建队伍
                my_path = "{}\\battle_before_create_stage.png".format(self.paths["picture"]["common"])
                loop_find_p_in_w(raw_w_handle=self.handle,
                                 raw_range=[0, 0, 950, 600],
                                 target_path=my_path,
                                 click_zoom=self.zoom,
                                 target_sleep=0.5,
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

    def action_battle_normal(
            self,
            battle_mode: int,
            task_card: str,
            list_ban_card: list
    ):
        """从类中继承主要方法 方便被调用"""

        # 调用 InBattle 类 生成实例, 从self中填充数据
        round_of_battle = RoundOfBattle(
            handle=self.handle,
            zoom=self.zoom,
            player=self.player,
            is_use_key=self.is_use_key,
            is_auto_battle=self.is_auto_battle,
            is_auto_collect=self.is_auto_collect,
            path_p_common=self.paths["picture"]["common"],
            stage_info=self.stage_info,
            battle_plan=self.battle_plan,
            is_group=self.is_group
        )

        round_of_battle.action_battle_normal(
            battle_mode=battle_mode,
            task_card=task_card,
            list_ban_card=list_ban_card
        )

    def action_round_of_game(
            self,
            deck: int,
            delay_start: bool,
            battle_mode: int,
            task_card: str,
            list_ban_card: list
    ):
        """调用主要方法 低耦合 方便被调用"""
        round_of_game(
            handle=self.handle,
            zoom=self.zoom,
            paths=self.paths,
            player=self.player,
            stage_info_id=self.stage_info["id"],
            action_battle_normal=self.action_battle_normal,
            deck=deck,
            delay_start=delay_start,
            battle_mode=battle_mode,
            task_card=task_card,
            list_ban_card=list_ban_card
        )

    def action_exit(
            self,
            exit_mode: int
    ):
        """退出 0-不退出  1-右下回退到上一级  2-右上红叉  3-直接到竞技岛 4-悬赏"""
        if exit_mode == 1:
            loop_find_p_in_w(raw_w_handle=self.handle,
                             raw_range=[0, 0, 950, 600],
                             target_path=self.paths["picture"]["common"] + "\\bottom_menu_back.png",
                             target_failed_check=100,
                             target_sleep=1.5,
                             click=True,
                             click_zoom=self.zoom)

        if exit_mode == 2:
            loop_find_p_in_w(raw_w_handle=self.handle,
                             raw_range=[0, 0, 950, 600],
                             target_path=self.paths["picture"]["common"] + "\\battle_before_exit_x.png",
                             target_failed_check=100,
                             target_sleep=1.5,
                             click=True,
                             click_zoom=self.zoom)

        if exit_mode == 3:
            loop_find_p_in_w(raw_w_handle=self.handle,
                             raw_range=[0, 0, 950, 600],
                             target_path=self.paths["picture"]["common"] + "\\bottom_menu_goto.png",
                             target_tolerance=0.99,
                             target_failed_check=100,
                             target_sleep=1.5,
                             click=True,
                             click_zoom=self.zoom)

            loop_find_p_in_w(raw_w_handle=self.handle,
                             raw_range=[0, 0, 950, 600],
                             target_path=self.paths["picture"]["common"] + "\\bottom_menu_goto_arena.png",
                             target_tolerance=0.99,
                             target_failed_check=100,
                             target_sleep=1.5,
                             click=True,
                             click_zoom=self.zoom)

        if exit_mode == 4:
            loop_find_p_in_w(raw_w_handle=self.handle,
                             raw_range=[0, 0, 950, 600],
                             target_path=self.paths["picture"]["common"] + "\\offer_reward_exit.png",
                             target_tolerance=0.99,
                             target_failed_check=100,
                             target_sleep=1.5,
                             click=True,
                             click_zoom=self.zoom)

    """reload game"""

    def reload_game(self):
        while True:
            # 点击刷新按钮 该按钮在360窗口上
            target_path = self.paths["picture"]["common"] + "\\login_refresh.png"
            loop_find_p_in_w(raw_w_handle=self.handle_360,
                             raw_range=[0, 0, 2000, 2000],
                             target_path=target_path,
                             target_tolerance=0.99,
                             target_sleep=5,
                             click=True,
                             click_zoom=self.zoom)

            # 检测是否有 输入服务器id字样
            target_path = self.paths["picture"]["common"] + "\\login_input_server_id.png"
            result = loop_find_p_in_w(raw_w_handle=self.handle_browser,
                                      raw_range=[0, 0, 2000, 2000],
                                      target_path=target_path,
                                      target_tolerance=0.99,
                                      click=False)
            if not result:
                print("[{}] 未找到进入输入服务器, 可能随机进入了未知界面, 刷新".format(self.player))
                continue

            else:
                # 点击两次右边的输入框 并输入服务器号
                target_path = self.paths["picture"]["common"] + "\\login_input_server_id.png"
                x, y = find_p_in_w(raw_w_handle=self.handle_browser,
                                   raw_range=[0, 0, 2000, 2000],
                                   target_path=target_path,
                                   target_tolerance=0.99)
                mouse_left_click(handle=self.handle_browser,
                                 x=int(x + 64) * self.zoom,
                                 y=int(y * self.zoom),
                                 interval_time=0.05,
                                 sleep_time=0.2)
                mouse_left_click(handle=self.handle_browser,
                                 x=int(x + 64) * self.zoom,
                                 y=int(y * self.zoom),
                                 interval_time=0.05,
                                 sleep_time=0.2)

                for key in self.serve_id:
                    key_down_up(handle=self.handle_browser, key=key, sleep_time=0.1)
                sleep(1)

                target_path = self.paths["picture"]["common"] + "\\login_input_server_enter.png"
                result = loop_find_p_in_w(raw_w_handle=self.handle_browser,
                                          raw_range=[0, 0, 2000, 2000],
                                          target_path=target_path,
                                          target_tolerance=0.95,  # 有轻微色差
                                          click=True,
                                          click_zoom=self.zoom)
                if not result:
                    print("[{}] 未找到进入输入服务器 + 进入服务器, 刷新".format(self.player))
                    continue

                target_path = self.paths["picture"]["common"] + "\\login_health_game_advice.png"
                result = loop_find_p_in_w(raw_w_handle=self.handle_browser,
                                          raw_range=[0, 0, 2000, 2000],
                                          target_path=target_path,
                                          target_tolerance=0.99,
                                          click=False)
                if not result:
                    print("[{}] 未找到健康游戏公告, 刷新".format(self.player))
                    continue
                else:
                    target_path = self.paths["picture"]["common"] + "\\login_health_game_advice_enter.png"
                    loop_find_p_in_w(raw_w_handle=self.handle_browser,
                                     raw_range=[0, 0, 2000, 2000],
                                     target_path=target_path,
                                     target_tolerance=0.99,
                                     click=True,
                                     click_zoom=self.zoom)

                    # 每日必充界面可能弹出 但没有影响
                    break


if __name__ == '__main__':
    def main():
        faa = FAA()
        faa.reload_game()


    main()
