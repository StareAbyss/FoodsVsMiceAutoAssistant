import copy
import json
import os
import time

import numpy as np
from cv2 import imread, vconcat, imwrite

from function.common.bg_keyboard import key_down_up
from function.common.bg_mouse import mouse_left_click, mouse_left_moveto
from function.common.bg_p_compare import find_p_in_w, loop_find_p_in_w, loop_find_ps_in_w, find_ps_in_w
from function.common.bg_p_screenshot import capture_picture_png
from function.get_paths import paths
from function.script.scattered.gat_handle import faa_get_handle
from function.script.scattered.get_list_battle_plan import get_list_battle_plan
from function.script.scattered.get_list_card_battle import get_list_card_battle
from function.script.scattered.get_list_card_room import get_list_card_room
from function.script.scattered.print_grade import print_g
from function.script.scattered.read_json_to_stage_info import read_json_to_stage_info
from function.tools.analyzer_of_loot_logs import matchImage
from function.tools.get_battle_coordinates import create_battle_coordinates


class FAA:
    def __init__(self, channel="锑食", zoom=1.0, player=1, character_level=1,
                 is_use_key=True, is_auto_battle=True, is_auto_pickup=False):

        # 获取窗口句柄
        self.channel = channel
        self.handle = faa_get_handle(channel=self.channel, mode="flash")
        self.handle_browser = faa_get_handle(channel=self.channel, mode="browser")
        self.handle_360 = faa_get_handle(channel=self.channel, mode="360")

        # 缩放
        self.zoom = zoom  # float 1.0 即百分百

        # 角色|等级|是否使用钥匙|卡片|收集战利品
        self.player = player
        self.character_level = character_level
        self.is_use_key = is_use_key
        self.is_auto_battle = is_auto_battle
        self.is_auto_pickup = is_auto_pickup

        # 每次战斗都不一样的参数 使用内部函数调用更改
        self.stage_info = None
        self.is_group = None
        self.deck = None
        self.quest_card = None
        self.ban_card_list = None
        self.battle_plan = None
        self.battle_mode = None

        # 部分文件夹文件名 list
        self.card_recorded_battle = get_list_card_battle(with_extension=False)
        self.card_recorded_room = get_list_card_room(with_extension=False)

        # 调用战斗中 卡牌 和 格子位置 字典
        # bp -> battle position
        self.bp_card, self.bp_cell = create_battle_coordinates(zoom)

    """通用对flash界面的基础操作"""

    def action_exit(self, mode: str = "None", raw_range=None):
        """
        游戏中的各种退出操作
        "普通红叉"
        "回到上一级"
        "竞技岛"
        "关闭悬赏窗口"
        "美食大赛领取"
        "游戏内退出"
        """

        if raw_range is None:
            raw_range = [0, 0, 950, 600]

        handle = self.handle
        zoom = self.zoom

        if mode == "回到上一级":
            self.action_bottom_menu(mode="后退")

        if mode == "普通红叉":
            find = loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=raw_range,
                target_path=paths["picture"]["common"] + "\\退出.png",
                target_failed_check=5,
                target_sleep=1.5,
                click=True,
                click_zoom=zoom)
            if not find:
                find = loop_find_p_in_w(
                    raw_w_handle=handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=paths["picture"]["common"] + "\\退出_被选中.png",
                    target_failed_check=5,
                    target_sleep=1.5,
                    click=True,
                    click_zoom=zoom)
                if not find:
                    print_g(text="未能成功找到右上红叉以退出!前面的步骤有致命错误!", player=self.player, garde=3)

        if mode == "竞技岛":
            self.action_bottom_menu(mode="跳转_竞技场")

        if mode == "关闭悬赏窗口":
            loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=raw_range,
                target_path=paths["picture"]["common"] + "\\悬赏任务_退出.png",
                target_tolerance=0.99,
                target_failed_check=100,
                target_sleep=1.5,
                click=True,
                click_zoom=zoom)

        if mode == "美食大赛领取":
            # 领取奖励
            self.action_quest_receive_rewards(mode="美食大赛")

        if mode == "游戏内退出":
            # 游戏内退出
            mouse_left_click(
                handle=self.handle,
                x=int(925 * self.zoom),
                y=int(580 * self.zoom),
                sleep_time=0.1)

            # 确定游戏内退出
            mouse_left_click(
                handle=self.handle,
                x=int(455 * self.zoom),
                y=int(385 * self.zoom),
                sleep_time=0.1)

    def action_top_menu(self, mode: str):
        """
        点击上方菜单栏, 包含:
        VIP签到|X年活动|塔罗寻宝|大地图|大富翁|欢乐假期|每日签到|美食大赛|美食活动|萌宠神殿|跨服远征
        其中跨服会跳转到二区
        :return bool 是否进入成功
        """

        failed_time = 0
        l_id = 1
        while True:
            self.change_activity_list(serial_num=l_id)
            find = loop_find_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[250, 0, 925, 110],
                target_path=paths["picture"]["common"] + "\\顶部菜单\\" + mode + ".png",
                target_tolerance=0.95,
                target_failed_check=3,
                target_sleep=1.5,
                click=True,
                click_zoom=self.zoom)
            if find:
                print_g(text="[顶部菜单] [{}] 3s内跳转成功".format(mode), player=self.player, garde=1)
                break
            else:
                l_id = 1 if l_id == 2 else 2
                failed_time += 1

            if failed_time == 5:
                print_g(text="[顶部菜单] [{}] 3s内跳转失败".format(mode), player=self.player, garde=2)
                break

        if mode == "跨服远征":
            # 选2区人少
            mouse_left_click(
                handle=self.handle,
                x=int(785 * self.zoom),
                y=int(30 * self.zoom),
                sleep_time=0.5)
            mouse_left_click(
                handle=self.handle,
                x=int(785 * self.zoom),
                y=int(85 * self.zoom),
                sleep_time=0.5)

        return find

    def action_bottom_menu(self, mode: str):
        """点击下方菜单栏, 包含:任务/后退/背包/跳转_公会任务/跳转_公会副本/跳转_情侣任务/跳转_竞技场"""

        find = False

        if mode == "任务" or mode == "后退" or mode == "背包" or mode == "公会":
            find = loop_find_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[520, 530, 950, 600],
                target_path=paths["picture"]["common"] + "\\底部菜单\\" + mode + ".png",
                target_failed_check=3,
                target_sleep=1,
                click=True,
                click_zoom=self.zoom)

        if mode == "跳转_公会任务" or mode == "跳转_公会副本" or mode == "跳转_情侣任务" or mode == "跳转_竞技场":
            loop_find_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[520, 530, 950, 600],
                target_path=paths["picture"]["common"] + "\\底部菜单\\跳转.png",
                target_failed_check=3,
                target_sleep=0.5,
                click=True,
                click_zoom=self.zoom)
            find = loop_find_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[520, 170, 950, 600],
                target_path=paths["picture"]["common"] + "\\底部菜单\\" + mode + ".png",
                target_failed_check=3,
                target_sleep=2,
                click=True,
                click_zoom=self.zoom)

        if not find:
            print_g(text="[底部菜单] [{}] 3s内跳转失败".format(mode), player=self.player, garde=2)

        return find

    def change_activity_list(self, serial_num: int):
        """检测顶部的活动清单, 1为第一页, 2为第二页(有举报图标的一页)"""

        find = find_p_in_w(
            raw_w_handle=self.handle,
            raw_range=[0, 0, 950, 600],
            target_path=paths["picture"]["common"] + "\\顶部菜单\\举报.png")

        if serial_num == 1:
            if find:
                mouse_left_click(
                    handle=self.handle,
                    x=int(785 * self.zoom),
                    y=int(30 * self.zoom),
                    sleep_time=0.5)

        if serial_num == 2:
            if not find:
                mouse_left_click(
                    handle=self.handle,
                    x=int(785 * self.zoom),
                    y=int(30 * self.zoom),
                    sleep_time=0.5)

    def action_get_stage_name(self):
        """在关卡备战界面 获得关卡名字"""
        stage_id = "Unknown"  # 默认名称
        img1 = capture_picture_png(handle=self.handle, raw_range=[0, 0, 950, 600])[468:484, 383:492, :3]
        # 关卡名称集 从资源文件夹自动获取, 资源文件命名格式：关卡名称.png
        stage_text_in_ready_check = []
        for i in os.listdir(paths["picture"]["ready_check_stage"]):
            if i.find(".png") != -1:
                stage_text_in_ready_check.append(i.split(".")[0])
        for i in stage_text_in_ready_check:
            if np.all(img1 == imread(paths["picture"]["ready_check_stage"] + "\\" + i + ".png", 1)):
                stage_id = i
                break
        return stage_id

    def action_get_quest(self, mode: str):
        """
        获取公会任务列表
        :param mode:
        :return: [
            {
                "stage_id":str,
                "max_times":,
                "quest_card":str,
                "ban_card":None
            },
        ]
        """
        # 跳转到对应界面
        if mode == "公会任务":
            self.action_bottom_menu(mode="跳转_公会任务")
            # 点一下 让左边的选中任务颜色消失
            loop_find_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["quest_guild"] + "\\ui_quest_list.png",
                target_sleep=0.2,
                click=True,
                click_zoom=self.zoom)
        if mode == "情侣任务":
            self.action_bottom_menu(mode="跳转_情侣任务")

        # 读取
        quest_list = []
        # 公会任务 guild
        if mode == "公会任务":
            path = paths["picture"]["quest_guild"]
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
                        quest_card = "None"
                        # 去除.png
                        j = j.split(".")[0]
                        # 处理解析字符串
                        num_of_line = j.count("_")
                        if num_of_line == 0:
                            stage_id = j
                        else:
                            my_list = j.split("_")
                            stage_id = my_list[0]
                            if num_of_line == 1:
                                if not my_list[1].isdigit():
                                    quest_card = my_list[1]
                            elif num_of_line == 2:
                                quest_card = my_list[2]
                        # 添加到任务列表
                        quest_list.append(
                            {
                                "player": [2, 1],
                                "stage_id": stage_id,
                                "max_times": 1,
                                "quest_card": quest_card,
                                "list_ban_card": [],
                                "dict_exit": {
                                    "other_time_player_a": [],
                                    "other_time_player_b": [],
                                    "last_time_player_a": ["竞技岛"],
                                    "last_time_player_b": ["竞技岛"]
                                }
                            }
                        )

        # 情侣任务 spouse
        if mode == "情侣任务":
            path = paths["picture"]["quest_spouse"]
            for i in ["1", "2", "3"]:
                # 任务未完成
                find_p = find_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path="{}\\NO-{}.png".format(path, i),
                    target_tolerance=0.999)
                if find_p:
                    # 遍历任务
                    for j in os.listdir("{}\\{}\\".format(path, i)):
                        # 找到任务 加入任务列表
                        find_p = find_p_in_w(
                            raw_w_handle=self.handle,
                            raw_range=[0, 0, 950, 600],
                            target_path="{}\\{}\\{}".format(path, i, j),
                            target_tolerance=0.999)
                        if find_p:
                            quest_list.append(
                                {
                                    "player": [2, 1],
                                    "stage_id": j.split(".")[0],
                                    "max_times": 1,
                                    "quest_card": "None",
                                    "list_ban_card": [],
                                    "dict_exit": {
                                        "other_time_player_a": ["none"],
                                        "other_time_player_b": ["none"],
                                        "last_time_player_a": ["竞技岛"],
                                        "last_time_player_b": ["竞技岛"]
                                    }
                                }
                            )

        # 关闭公会任务列表(红X)
        self.action_exit(mode="普通红叉")

        return quest_list

    def action_goto_map(self, map_id):
        """
        用于前往各地图,0.美味阵,1.美味岛,2.火山岛,3.火山遗迹,4.浮空岛,5.海底,6.营地
        """

        # 点击世界地图
        self.action_top_menu(mode="大地图")

        # 点击对应的地图
        my_path = paths["picture"]["map"] + "\\" + str(map_id) + ".png"
        find = loop_find_p_in_w(
            raw_w_handle=self.handle,
            raw_range=[0, 0, 950, 600],
            target_path=my_path,
            target_tolerance=0.99,
            target_failed_check=5,
            target_sleep=2,
            click=True,
            click_zoom=self.zoom,
        )
        return find

    def action_goto_stage(self, room_creator: bool = True, mt_first_time: bool = False):
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

        def click_set_password():
            """设置进队密码"""
            mouse_left_click(
                handle=self.handle,
                x=int(491 * self.zoom),
                y=int(453 * self.zoom),
                sleep_time=0.5)
            mouse_left_click(
                handle=self.handle,
                x=int(600 * self.zoom),
                y=int(453 * self.zoom),
                sleep_time=0.5)
            key_down_up(
                handle=self.handle,
                key="backspace")
            key_down_up(
                handle=self.handle,
                key="1")
            time.sleep(1)

        def change_to_region(region_id: int = 2):
            mouse_left_click(
                handle=self.handle,
                x=int(820 * self.zoom),
                y=int(85 * self.zoom),
                sleep_time=0.5)

            my_list = [85, 110, 135, 160, 185, 210, 235, 260, 285, 310, 335]
            mouse_left_click(
                handle=self.handle,
                x=int(779 * self.zoom),
                y=int(my_list[region_id - 1] * self.zoom),
                sleep_time=2)

        def main_no():
            # 进入对应地图
            self.action_goto_map(map_id=stage_1)

            # 切区
            my_dict = {"1": 8, "2": 2, "3": 1, "4": 2, "5": 2}
            change_to_region(region_id=my_dict[stage_1])

            # 仅限主角色创建关卡
            if room_creator:
                # 防止被活动列表遮住
                self.change_activity_list(serial_num=2)

                # 选择关卡
                loop_find_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=paths["picture"]["stage"] + "\\" + self.stage_info["id"] + ".png",
                    click_zoom=self.zoom,
                    target_tolerance=0.995,
                    target_sleep=1,
                    click=True)

                # 设置密码
                click_set_password()

                # 创建队伍
                loop_find_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=paths["picture"]["common"] + "\\战斗\\战斗前_创建房间.png",
                    click_zoom=self.zoom,
                    target_sleep=1,
                    click=True)

        def main_mt():
            if mt_first_time:
                # 防止被活动列表遮住
                self.change_activity_list(2)

                # 前往海底
                self.action_goto_map(map_id=5)

                # 选区
                change_to_region(region_id=2)

            if room_creator and mt_first_time:
                # 进入魔塔
                loop_find_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=paths["picture"]["stage"] + "\\MT.png",
                    target_failed_check=5,
                    target_sleep=2,
                    click=True,
                    click_zoom=self.zoom
                )

                # 根据模式进行选择
                my_dict = {"1": 46, "2": 115, "3": 188}
                mouse_left_click(
                    handle=self.handle,
                    x=int(my_dict[stage_1] * self.zoom),
                    y=int(66 * self.zoom),
                    sleep_time=0.5)

            if room_creator:
                # 选择了密室
                if stage_1 == "3":
                    loop_find_p_in_w(
                        raw_w_handle=self.handle,
                        raw_range=[0, 0, 950, 600],
                        target_path=paths["picture"]["stage"] + "\\" + self.stage_info["id"] + ".png",
                        click_zoom=self.zoom,
                        target_sleep=0.3,
                        click=True)
                # 选择了单双人爬塔
                else:
                    # 等于0则为爬塔模式 即选择最高层 从下到上遍历所有层数
                    if stage_2 == "0":
                        # 到魔塔最低一层
                        mouse_left_click(
                            handle=self.handle,
                            x=int(47 * self.zoom),
                            y=int(579 * self.zoom),
                            sleep_time=0.3)

                        for i in range(11):
                            # 下一页
                            mouse_left_click(
                                handle=self.handle,
                                x=int(152 * self.zoom),
                                y=int(577 * self.zoom),
                                sleep_time=0.1)

                            for j in range(15):
                                mouse_left_click(
                                    handle=self.handle,
                                    x=int(110 * self.zoom),
                                    y=int(int(542 - (30.8 * j)) * self.zoom),
                                    sleep_time=0.1)

                    else:
                        # 到魔塔最低一层
                        mouse_left_click(
                            handle=self.handle,
                            x=int(47 * self.zoom),
                            y=int(579 * self.zoom),
                            sleep_time=0.3)
                        # 向右到对应位置
                        my_left = int((int(stage_2) - 1) / 15)
                        for i in range(my_left):
                            mouse_left_click(
                                handle=self.handle,
                                x=int(152 * self.zoom),
                                y=int(577 * self.zoom),
                                sleep_time=0.3)
                        # 点击对应层数
                        mouse_left_click(
                            handle=self.handle,
                            x=int(110 * self.zoom),
                            y=int(int(542 - (30.8 * (int(stage_2) - my_left * 15 - 1))) * self.zoom),
                            sleep_time=0.3)

                # 进入关卡

                loop_find_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=paths["picture"]["common"] + "\\战斗\\战斗前_魔塔_创建房间.png",
                    click_zoom=self.zoom,
                    target_sleep=1,
                    click=True)

        def main_cs():
            # 进入跨服远征界面
            self.action_top_menu(mode="跨服远征")

            if room_creator:
                # 创建房间
                mouse_left_click(
                    handle=self.handle,
                    x=int(853 * self.zoom),
                    y=int(553 * self.zoom),
                    sleep_time=0.5)

                # 选择地图
                my_x = int(stage_1) * 101 - 36
                mouse_left_click(
                    handle=self.handle,
                    x=int(my_x * self.zoom),
                    y=int(70 * self.zoom),
                    sleep_time=1)

                # 选择关卡
                my_dict = {
                    "1": [124, 248], "2": [349, 248], "3": [576, 248], "4": [803, 248],
                    "5": [124, 469], "6": [349, 469], "7": [576, 469], "8": [803, 469]}
                mouse_left_click(
                    handle=self.handle,
                    x=int(my_dict[stage_2][0] * self.zoom),
                    y=int(my_dict[stage_2][1] * self.zoom),
                    sleep_time=0.5)

                # 选择密码输入框
                my_dict = {
                    "1": [194, 248], "2": [419, 248], "3": [646, 248], "4": [873, 248],
                    "5": [194, 467], "6": [419, 467], "7": [646, 467], "8": [873, 467]}
                mouse_left_click(
                    handle=self.handle,
                    x=int(my_dict[stage_2][0] * self.zoom),
                    y=int(my_dict[stage_2][1] * self.zoom),
                    sleep_time=0.5)

                # 输入密码
                key_down_up(
                    handle=self.handle,
                    key="1",
                    sleep_time=0.5)

                # 创建关卡
                my_dict = {  # X+225 Y+221
                    "1": [176, 286], "2": [401, 286], "3": [629, 286], "4": [855, 286],
                    "5": [176, 507], "6": [401, 507], "7": [629, 507], "8": [855, 507]}
                mouse_left_click(
                    handle=self.handle,
                    x=int(my_dict[stage_2][0] * self.zoom),
                    y=int(my_dict[stage_2][1] * self.zoom),
                    sleep_time=0.5)
            else:
                # 刷新
                mouse_left_click(
                    handle=self.handle,
                    x=int(895 * self.zoom),
                    y=int(80 * self.zoom),
                    sleep_time=3)

                # 复位
                mouse_left_click(
                    handle=self.handle,
                    x=int(602 * self.zoom),
                    y=int(490 * self.zoom),
                    sleep_time=0.2)

                for i in range(20):
                    find = loop_find_p_in_w(
                        raw_w_handle=self.handle,
                        raw_range=[0, 0, 950, 600],
                        target_path=paths["picture"]["common"] + "\\用户自截\\跨服远征_1p.png",
                        click_zoom=self.zoom,
                        click=True,
                        target_sleep=1.0,
                        target_failed_check=1.0)
                    if find:
                        break
                    else:
                        mouse_left_click(
                            handle=self.handle,
                            x=int(700 * self.zoom),
                            y=int(490 * self.zoom),
                            sleep_time=0.2)
                        # 下一页

                # 点击密码框 输入密码 确定进入
                mouse_left_click(
                    handle=self.handle,
                    x=int(490 * self.zoom),
                    y=int(300 * self.zoom),
                    sleep_time=0.5)

                key_down_up(
                    handle=self.handle,
                    key="1",
                    sleep_time=0.5)

                mouse_left_click(
                    handle=self.handle,
                    x=int(490 * self.zoom),
                    y=int(360 * self.zoom),
                    sleep_time=0.5)

        def main_or():
            # 进入X年活动界面
            self.action_top_menu(mode="X年活动")

            # 选择关卡
            loop_find_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["stage"] + "\\" + self.stage_info["id"] + ".png",
                click_zoom=self.zoom,
                target_tolerance=0.95,
                target_sleep=1,
                click=True)

            # 切区
            my_dict = {
                "1": 8,
                "2": 2,
                "3": 2}
            change_to_region(region_id=my_dict[stage_1])

            # 仅限创房间的人
            if room_creator:
                # 设置密码
                click_set_password()
                # 创建队伍
                mouse_left_click(
                    handle=self.handle,
                    x=int(583 * self.zoom),
                    y=int(500 * self.zoom),
                    sleep_time=0.5)

        def main_ex():
            # 防止被活动列表遮住
            self.change_activity_list(2)

            # 进入对应地图
            self.action_goto_map(map_id=6)

            # 不是营地
            if stage_1 != "1":
                # 找船
                loop_find_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path="{}\\EX-Ship.png".format(paths["picture"]["stage"]),
                    click_zoom=self.zoom,
                    target_sleep=1.5,
                    click=True)

                # 找地图图标
                loop_find_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path="{}\\EX-{}.png".format(paths["picture"]["stage"], stage_1),
                    click_zoom=self.zoom,
                    target_sleep=1.5,
                    click=True)

            # 切区
            change_to_region(region_id=2)

            # 仅限主角色创建关卡
            if room_creator:
                # 选择关卡
                my_path = "{}\\{}.png".format(paths["picture"]["stage"], self.stage_info["id"])
                loop_find_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=my_path,
                    click_zoom=self.zoom,
                    target_sleep=0.5,
                    click=True)

                # 设置密码
                click_set_password()

                # 创建队伍
                my_path = "{}\\战斗\\战斗前_创建房间.png".format(paths["picture"]["common"])
                loop_find_p_in_w(
                    raw_w_handle=self.handle,
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
            print_g(
                text="请输入正确的关卡名称！",
                player=self.player,
                garde=3)

    """其他基础函数"""

    def check_level(self):
        """检测角色等级和关卡等级(调用于输入关卡信息之后)"""
        if self.character_level < self.stage_info["level"]:
            return False
        else:
            return True

    """领取任务奖励"""

    def AQRR_normal(self):
        """领取普通任务奖励"""
        handle = self.handle
        zoom = self.zoom

        while True:
            # 点任务
            find = self.action_bottom_menu(mode="任务")

            if find:
                # 复位滑块
                mouse_left_click(
                    handle=handle,
                    x=int(413 * zoom),
                    y=int(155 * zoom),
                    sleep_time=0.25)

                for i in range(8):

                    # 不是第一次滑块向下移动3次
                    if i != 0:
                        for j in range(3):
                            mouse_left_click(
                                handle=handle,
                                x=int(413 * zoom),
                                y=int(524 * zoom),
                                sleep_time=0.05)

                    # 找到就点一下, 找不到就跳过
                    while True:
                        find = loop_find_p_in_w(
                            raw_w_handle=handle,
                            raw_range=[335, 120, 420, 545],
                            target_path=paths["picture"]["common"] + "\\任务_完成.png",
                            target_tolerance=0.95,
                            target_failed_check=1,
                            target_sleep=0.5,
                            click_zoom=zoom,
                            click=True)
                        if find:
                            # 领取奖励
                            mouse_left_click(
                                handle=handle,
                                x=int(643 * zoom),
                                y=int(534 * zoom),
                                sleep_time=0.2)
                        else:
                            break

                self.action_exit(mode="普通红叉")
                break

    def AQRR_guild(self):
        # 跳转到任务界面
        self.action_bottom_menu(mode="跳转_公会任务")
        # 循环遍历点击完成
        while True:
            # 点一下 让左边的选中任务颜色消失
            loop_find_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["quest_guild"] + "\\ui_quest_list.png",
                target_sleep=0.5,
                click=True,
                click_zoom=self.zoom)
            result = loop_find_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["quest_guild"] + "\\completed.png",
                target_tolerance=0.99,
                click_zoom=self.zoom,
                click=True,
                target_failed_check=5,  # 1+4s 因为偶尔会弹出美食大赛完成动画4s 需要充足时间！这个确实脑瘫...
                target_sleep=0.5)
            if result:
                loop_find_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=paths["picture"]["quest_guild"] + "\\gather.png",
                    target_tolerance=0.99,
                    click_zoom=self.zoom,
                    click=True,
                    target_failed_check=2,
                    target_sleep=2)  # 2s 完成任务有显眼动画
            else:
                break
        # 退出任务界面
        self.action_exit(mode="普通红叉")

    def AQRR_spouse(self):
        # 跳转到任务界面
        self.action_bottom_menu(mode="跳转_情侣任务")
        # 循环遍历点击完成
        while True:
            result = loop_find_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["quest_spouse"] + "\\completed.png",
                target_tolerance=0.99,
                click_zoom=self.zoom,
                click=True,
                target_failed_check=2,
                target_sleep=2)  # 2s 完成任务有显眼动画)
            if not result:
                break
        # 退出任务界面
        self.action_exit(mode="普通红叉")

    def AQRR_offer_reward(self):

        # 进入X年活动界面
        self.action_top_menu(mode="X年活动")

        # 循环遍历点击完成
        while True:
            result = loop_find_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["common"] + "\\悬赏任务_领取奖励.png",
                target_tolerance=0.99,
                target_failed_check=2,
                click_zoom=self.zoom,
                click=True,
                target_sleep=2)
            if not result:
                break

        # 退出任务界面
        self.action_exit(mode="exit_offer_reward")

    def AQRR_food_competition(self):

        handle = self.handle
        zoom = self.zoom
        found_flag = False  # 记录是否有完成任何一次任务

        # 进入美食大赛界面
        find = self.action_top_menu(mode="美食大赛")

        if find:

            my_dict = {0: 362, 1: 405, 2: 448, 3: 491, 4: 534, 5: 570}
            for i in range(6):
                # 先移动一次位置
                mouse_left_click(handle=handle, x=int(536 * zoom), y=int(my_dict[i] * zoom), sleep_time=0.1)
                # 找到就点一下领取, 1s内找不到就跳过
                while True:
                    find = loop_find_p_in_w(
                        raw_w_handle=handle,
                        raw_range=[0, 0, 950, 600],
                        target_path=paths["picture"]["common"] + "\\美食大赛_领取.png",
                        target_tolerance=0.95,
                        target_failed_check=1,
                        target_sleep=0.5,
                        click_zoom=zoom,
                        click=True)
                    if find:
                        # 领取升级有动画
                        print_g(text="[收取奖励] [美食大赛] 完成1个任务", player=self.player, garde=1)
                        time.sleep(6)
                        # 更新是否找到flag
                        found_flag = True
                    else:
                        break

            # 退出美食大赛界面
            mouse_left_click(
                handle=handle,
                x=int(888 * zoom),
                y=int(53 * zoom),
                sleep_time=0.5)

        else:
            print_g(text="[领取奖励] [美食大赛] 未打开界面, 可能大赛未刷新", player=self.player, garde=2)

        if not found_flag:
            print_g(text="[领取奖励] [美食大赛] 未完成任意任务", player=self.player, garde=1)

    def AQRR_monopoly(self):

        handle = self.handle
        zoom = self.zoom

        # 进入对应地图
        find = self.action_top_menu(mode="大富翁")

        if find:

            y_dict = {
                0: 167,
                1: 217,
                2: 266,
                3: 320,
                4: 366,
                5: 417
            }

            for i in range(3):

                if i > 0:
                    # 下一页
                    mouse_left_click(
                        handle=handle,
                        x=int(878 * zoom),
                        y=int(458 * zoom),
                        sleep_time=0.5)

                # 点击每一个有效位置
                for j in range(6):
                    mouse_left_click(
                        handle=handle,
                        x=int(768 * zoom),
                        y=int(y_dict[j] * zoom),
                        sleep_time=0.1)

            # 退出界面
            mouse_left_click(
                handle=handle,
                x=int(928 * zoom),
                y=int(16 * zoom),
                sleep_time=0.5)

    def action_quest_receive_rewards(self, mode: str):
        """
        领取奖励
        :param mode: 普通任务/公会任务/情侣任务/悬赏任务/美食大赛/大富翁
        :return:None
        """

        print_g(text="[领取奖励] [{}] 开始".format(mode), player=self.player, garde=1)

        if mode == "普通任务":
            self.AQRR_normal()
        if mode == "公会任务":
            self.AQRR_guild()
        if mode == "情侣任务":
            self.AQRR_spouse()
        if mode == "悬赏任务":
            self.AQRR_offer_reward()
        if mode == "美食大赛":
            self.AQRR_food_competition()
        if mode == "大富翁":
            self.AQRR_monopoly()

        print_g(text="[领取奖励] [{}] 结束".format(mode), player=self.player, garde=1)

    """调用输入关卡配置和战斗配置, 在战斗前必须进行该操作"""

    def set_config_for_battle(
            self,
            stage_id="NO-1-1", is_group=False,
            deck=1, quest_card="None", ban_card_list=None,
            battle_plan_index=0, battle_mode=0):
        """
        :param battle_mode:
        :param is_group: 是否组队
        :param deck:
        :param quest_card:
        :param ban_card_list:
        :param battle_plan_index: 战斗方案的索引
        :param stage_id: 关卡的id
        :return:
        """

        if ban_card_list is None:
            ban_card_list = []

        self.battle_mode = battle_mode
        self.is_group = is_group
        self.deck = deck
        self.quest_card = quest_card
        self.ban_card_list = ban_card_list

        def read_json_to_battle_plan():
            battle_plan_list = get_list_battle_plan(with_extension=True)
            battle_plan_path = "{}\\{}".format(
                paths["battle_plan"],
                battle_plan_list[battle_plan_index]
            )
            with open(battle_plan_path, "r", encoding="UTF-8") as file:
                return json.load(file)

        self.battle_plan = read_json_to_battle_plan()
        self.stage_info = read_json_to_stage_info(stage_id)

    """战斗函数"""

    def calculation_cell_all_card(self, mat_card_position):
        """
        计算所有卡片的部署方案
        Return:卡片的部署方案字典
            example = [
                {

                    来自配置文件
                    "name": str,  名称 用于ban卡
                    "id": int, 卡片从哪取 代号 (卡片在战斗中, 在卡组的的从左到右序号 )
                    "location": ["x-y","x-y"...] ,  卡片放到哪 代号
                    "ergodic": True,  放卡模式 遍历
                    "queue": True,  放卡模式 队列

                    函数计算得出
                    "location_from": [x:int, y:int]  卡片从哪取 坐标
                    "location_to": [[x:int, y:int],[x:int, y:int],[x:int, y:int],...] 卡片放到哪 坐标

                },
                ...
            ]
        """

        """调用类参数"""
        player = self.player
        is_group = self.is_group
        bp_cell = copy.deepcopy(self.bp_cell)
        bp_card = copy.deepcopy(self.bp_card)

        """调用类参数-战斗前生成"""
        quest_card = copy.deepcopy(self.quest_card)
        ban_card_list = copy.deepcopy(self.ban_card_list)
        stage_info = copy.deepcopy(self.stage_info)
        battle_plan = copy.deepcopy(self.battle_plan)

        def calculation_card_quest(list_cell_all):
            """计算步骤一 加入任务卡的摆放坐标"""

            # 任务卡 大号小号开始位置不同 任务卡id = 0 则为没有
            locations = ["6-1", "6-2", "6-3", "6-4", "6-5", "6-6", "6-7"]

            if quest_card == "None":
                return list_cell_all

            else:

                # 遍历删除 主要卡中 占用了任务卡摆放的坐标
                new_list = []
                for card in list_cell_all:
                    card["location"] = list(filter(lambda x: x not in locations, card["location"]))
                    new_list.append(card)

                # 计算任务卡的id
                card_id_list = []
                for card in list_cell_all:
                    card_id_list.append(card["id"])
                quest_card_id = max(card_id_list) + 1  # 取其中最大的卡片id + 1

                # 设定任务卡dict
                dict_quest = {
                    "name": quest_card,
                    "id": quest_card_id,
                    "location": locations,
                    "ergodic": True,
                    "queue": True,
                    "location_from": [],
                    "location_to": []
                }

                # 加入数组
                new_list.append(dict_quest)
                return new_list

        def calculation_card_mat(list_cell_all):
            """步骤二 2张承载卡"""

            location = stage_info["mat_cell"]  # 深拷贝 防止对配置文件数据更改

            # p1p2分别摆一半
            if is_group:
                if player == 1:
                    location = location[::2]  # 奇数
                else:
                    location = location[1::2]  # 偶数
            # 根据不同垫子数量 再分
            num_mat_card = len(mat_card_position)

            for i in range(num_mat_card):
                dict_mat = {
                    "name": "承载卡",
                    "id": 1,
                    "location": location[i::num_mat_card],
                    "ergodic": True,
                    "queue": True,
                    "location_from": mat_card_position[i],
                    "location_to": []}
                list_cell_all.append(dict_mat)

            return list_cell_all

        def calculation_card_ban(list_cell_all):
            """步骤三 ban掉某些卡, 依据[卡组信息中的name字段] 和 ban卡信息中的字符串 是否重复"""

            list_new = []
            for card in list_cell_all:
                if not (card["name"] in ban_card_list):
                    list_new.append(card)

            # 遍历更改删卡后的位置
            for card in list_new:
                cum_card_left = 0
                for ban_card in ban_card_list:
                    for c_card in list_cell_all:
                        if c_card["name"] == ban_card:
                            if card["id"] > c_card["id"]:
                                cum_card_left += 1
                card["id"] -= cum_card_left

            return list_new

        def calculation_obstacle(list_cell_all):
            """去除有障碍的位置的放卡"""

            # 预设中 该关卡有障碍物
            for card in list_cell_all:
                for location in card["location"]:
                    if location in stage_info["obstacle"]:
                        card["location"].remove(location)

            # 如果location完全不存在 就去掉它
            new_list = []
            for card in list_cell_all:
                if card["location"]:
                    new_list.append(card)

            return new_list

        def calculation_alt_transformer(list_cell_all):
            """[非]1P, 队列模式, 就颠倒坐标数组, [非]队列模式代表着优先级很重要的卡片, 所以不颠倒"""
            if player == 2:
                for i in range(len(list_cell_all)):
                    if list_cell_all[i]["queue"]:
                        list_cell_all[i]["location"] = list_cell_all[i]["location"][::-1]
            return list_cell_all

        def calculation_shovel():
            """铲子位置 """
            list_shovel = stage_info["shovel"]
            return list_shovel

        def transform_code_to_coordinate(list_cell_all, list_shovel):
            """
            如果没有后者
            将 id:int 变为 location_from:[x:int,y:int]
            将 location:str 变为 location_to:[[x:int,y:int],...]"""

            # 注意 bp_cell 和 bp_card 已经根据缩放转化过坐标了
            # 不要二次转化

            # 为每个字典添加未预设字段
            for card in list_cell_all:
                if "location_from" not in card:
                    card["location_from"] = []
                if "location_to" not in card:
                    card["location_to"] = []

            # 根据字段值, 判断是否完成写入, 并进行转换
            for card in list_cell_all:
                if not card["location_from"]:
                    coordinate = copy.deepcopy(bp_card[card["id"]])
                    coordinate = [coordinate[0], coordinate[1]]
                    card["location_from"] = coordinate

                if not card["location_to"]:
                    new_list = []
                    for location in card["location"]:
                        coordinate = copy.deepcopy(bp_cell[location])
                        new_list.append([coordinate[0], coordinate[1]])
                    card["location_to"] = copy.deepcopy(new_list)

            new_list = []
            for location in list_shovel:
                coordinate = bp_cell[location]
                new_list.append([coordinate[0], coordinate[1]])
            list_shovel = copy.deepcopy(new_list)  # 因为重新注册list容器了, 可以不用深拷贝 但为了方便理解用一下

            return list_cell_all, list_shovel

        def main():
            # 初始化数组 + 复制一份全新的 battle_plan
            list_cell_all = battle_plan["card"]

            # 调用计算任务卡
            list_cell_all = calculation_card_quest(list_cell_all=list_cell_all)

            # 调用计算承载卡
            list_cell_all = calculation_card_mat(list_cell_all=list_cell_all)

            # 调用ban掉某些卡(不使用该卡)
            list_cell_all = calculation_card_ban(list_cell_all=list_cell_all)

            # 调用去掉障碍位置
            list_cell_all = calculation_obstacle(list_cell_all=list_cell_all)

            # 调用计算铲子卡
            list_shovel = calculation_shovel()

            # 统一以坐标直接表示位置, 防止重复计算
            list_cell_all, list_shovel = transform_code_to_coordinate(
                list_cell_all=list_cell_all,
                list_shovel=list_shovel)

            # 调试print 打包前务必注释!
            # print("调试info: 你的战斗放卡opt如下")
            # pprint(list_cell_all)

            return list_cell_all, list_shovel

        return main()

    def get_mat_card_position(self):

        stage_info = copy.deepcopy(self.stage_info)
        handle = self.handle
        zoom = self.zoom
        mat_card_list = ["木盘子", "棉花糖", "苏打气泡", "麦芽糖", "魔法软糖"]

        # 筛选出 对应关卡可用的卡片
        for mat_card in mat_card_list:
            if mat_card not in stage_info["mat_card"]:
                mat_card_list.remove(mat_card)

        # 筛选出 被记录的卡片变种
        new_list = []
        for mat_card in mat_card_list:
            for i in range(10):
                new_card = "{}-{}".format(mat_card, i)
                if new_card in self.card_recorded_battle:
                    new_list.append(new_card)

        mat_card_list = new_list

        position_list = []
        find_list = []

        # 查找对应卡片坐标 重复3次
        for i in range(3):
            for mat_card in mat_card_list:
                # 需要使用0.99相似度参数 相似度阈值过低可能导致一张图片被识别为两张卡
                find = find_p_in_w(
                    raw_w_handle=handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=paths["picture"]["card"] + "\\战斗\\" + mat_card + ".png",
                    target_tolerance=0.99)
                if find:
                    position_list.append([int(find[0] * zoom), int(find[1] * zoom)])
                    find_list.append(mat_card)
            mat_card_list = list(filter(lambda x: x not in find_list, mat_card_list))
            time.sleep(0.1)

        return position_list

    def action_in_battle(self):
        """
        :return: None
        """

        """调用类参数"""
        zoom = self.zoom
        handle = self.handle
        player = self.player
        is_auto_battle = self.is_auto_battle
        is_auto_pickup = self.is_auto_pickup
        is_use_key = self.is_use_key
        bp_cell = self.bp_cell
        bp_card = self.bp_card

        """调用类参数-战斗前生成"""
        battle_mode = self.battle_mode
        battle_plan = self.battle_plan

        """其他手动内部参数"""
        # 战斗中, [检测战斗结束]和[检测继续战斗]的时间间隔, 不建议大于1s(因为检测只在放完一张卡后完成 遍历会耗时)
        check_invite = 1.0
        # 每次点击时 按下和抬起之间的间隔
        click_interval = 0.025
        # 每次点击时 按下和抬起之间的间隔
        click_sleep = 0.025

        # the locations of cell easy touch the use-key UI by mistake
        warning_cell = ["4-4", "4-5", "5-4", "5-5"]
        auto_collect_cells = [
            "1-1", "2-1", "8-1", "9-1",
            "1-2", "2-2", "8-2", "9-2",
            "1-3", "2-3", "8-3", "9-3",
            "1-4", "2-4", "8-4", "9-4",
            "1-5", "2-5", "8-5", "9-5",
            "1-6", "2-6", "8-6", "9-6",
            "1-7", "2-7", "8-7", "9-7"
        ]
        auto_collect_cells = [i for i in auto_collect_cells if i not in warning_cell]

        auto_collect_cells_coordinate = []
        for i in auto_collect_cells:
            auto_collect_cells_coordinate.append(bp_cell[i])

        """ 战斗内的子函数 """

        def use_player(num_cell):
            mouse_left_click(
                handle=handle,
                x=bp_cell[num_cell][0],
                y=bp_cell[num_cell][1],
                interval_time=click_interval,
                sleep_time=click_sleep)

        def use_shovel(positions: list = None):
            """
            用铲子
            Args:
                positions: 放哪些格子
            """
            if positions is None:
                positions = []

            for position in positions:
                key_down_up(
                    handle=handle,
                    key="1")
                mouse_left_click(
                    handle=handle,
                    x=position[0],
                    y=position[1],
                    interval_time=click_interval,
                    sleep_time=click_sleep)

        def use_key(mode: int = 0):
            """
            使用钥匙的函数,
            :param mode:
                the mode of use key.
                0: click on the location of "next UI".
                1: if you find the picture of "next UI", click it.
            :return:
                None
            """
            if is_use_key:
                if mode == 0:
                    mouse_left_click(
                        handle=handle,
                        interval_time=click_interval,
                        sleep_time=click_sleep,
                        x=int(427 * zoom),
                        y=int(360 * zoom))
                if mode == 1:
                    if find_p_in_w(
                            raw_w_handle=handle,
                            raw_range=[0, 0, 950, 600],
                            target_path=paths["picture"]["common"] + "\\战斗\\战斗中_继续作战.png"):
                        mouse_left_click(
                            handle=handle,
                            interval_time=click_interval,
                            sleep_time=click_sleep,
                            x=int(427 * zoom),
                            y=int(360 * zoom))

        def use_key_and_check_end():
            # 找到战利品字样(被黑色透明物遮挡,会看不到)
            use_key(mode=0)
            return find_ps_in_w(
                raw_w_handle=handle,
                target_opts=[
                    {
                        "raw_range": [202, 419, 306, 461],
                        "target_path": paths["picture"]["common"] + "\\战斗\\战斗后_1_战利品.png",
                        "target_tolerance": 0.999
                    },
                    {
                        "raw_range": [202, 419, 306, 461],
                        "target_path": paths["picture"]["common"] + "\\战斗\\战斗后_2_战利品阴影版.png",
                        "target_tolerance": 0.999
                    },
                    {
                        "raw_range": [400, 47, 550, 88],
                        "target_path": paths["picture"]["common"] + "\\战斗\\战斗后_3_战斗结算.png",
                        "target_tolerance": 0.999
                    },
                    {
                        "raw_range": [400, 35, 550, 75],
                        "target_path": paths["picture"]["common"] + "\\战斗\\战斗后_4_翻宝箱.png",
                        "target_tolerance": 0.999
                    },
                    {
                        "raw_range": [796, 413, 950, 485],
                        "target_path": paths["picture"]["common"] + "\\战斗\\战斗前_开始按钮.png",
                        "target_tolerance": 0.999
                    }
                ],
                return_mode="or")

        def use_card_once(num_card: int, num_cell: str, click_space=True):
            """
            Args:
                num_card: 使用的卡片的序号
                num_cell: 使用的卡片对应的格子 从左上开始 "1-1" to "9-7"
                click_space:  是否点一下空白地区防卡住
            """
            # 注 美食大战老鼠中 放卡动作 需要按下一下 然后拖动 然后按下并松开 才能完成 整个动作
            mouse_left_click(
                handle=handle,
                x=bp_card[num_card][0],
                y=bp_card[num_card][1],
                interval_time=click_interval,
                sleep_time=click_sleep)

            mouse_left_click(
                handle=handle,
                x=bp_card[num_cell][0],
                y=bp_card[num_cell][1],
                interval_time=click_interval,
                sleep_time=click_sleep)

            # 点一下空白
            if click_space:
                mouse_left_moveto(
                    handle=handle,
                    x=int(200 * zoom),
                    y=int(350 * zoom))
                mouse_left_click(
                    handle=handle,
                    x=int(200 * zoom),
                    y=int(350 * zoom),
                    interval_time=click_interval,
                    sleep_time=click_sleep)

        def use_weapon_skill():
            """使用武器技能"""
            mouse_left_click(
                handle=handle,
                x=int(23 * zoom),
                y=int(200 * zoom),
                interval_time=click_interval,
                sleep_time=click_sleep)
            mouse_left_click(
                handle=handle,
                x=int(23 * zoom),
                y=int(250 * zoom),
                interval_time=click_interval,
                sleep_time=click_sleep)
            mouse_left_click(
                handle=handle,
                x=int(23 * zoom),
                y=int(297 * zoom),
                interval_time=click_interval,
                sleep_time=click_sleep)

        def auto_pickup():
            if is_auto_pickup:
                for coordinate in auto_collect_cells_coordinate:
                    mouse_left_moveto(
                        handle=handle,
                        x=coordinate[0],
                        y=coordinate[1])
                    time.sleep(click_sleep)

        """(循环)放卡函数"""

        def use_card_loop_0(list_cell_all):
            """
            !!!最重要的函数!!!
            本项目的精髓, 性能开销最大的函数, 为了性能, [可读性]和[低耦合]已牺牲...
            循环方式:
            每一个卡都先在其对应的全部的位置放一次,再放下一张(每轮开始位置+1)
            """

            # 计算一轮最长时间(防止一轮太短, 导致某些卡cd转不好就尝试点它也就是空转)
            max_len_position_in_opt = 0
            for i in list_cell_all:
                max_len_position_in_opt = max(max_len_position_in_opt, len(i["location_to"]))
            round_max_time = (click_interval + click_sleep) * max_len_position_in_opt + 7.3

            end_flag = False  # 用flag值来停止循环
            check_last_one_time = time.time()  # 记录上一次检测的时间

            while True:

                time_round_begin = time.time()  # 每一轮开始的时间

                for card in list_cell_all:
                    """遍历每一张卡"""

                    if is_auto_battle:  # 启动了自动战斗

                        # 点击 选中卡片
                        mouse_left_click(
                            handle=handle,
                            interval_time=click_interval,
                            sleep_time=click_sleep,
                            x=card["location_from"][0],
                            y=card["location_from"][1]
                        )

                        if card["ergodic"]:

                            """遍历模式: True 遍历该卡每一个可以放的位置"""
                            for j in range(len(card["location"])):

                                """安全放一张卡"""

                                # 防止误触
                                if card["location"][j] in warning_cell:
                                    use_key(mode=1)

                                # 点击 放下卡片
                                mouse_left_click(
                                    handle=handle,
                                    interval_time=click_interval,
                                    sleep_time=click_sleep,
                                    x=card["location_to"][j][0],
                                    y=card["location_to"][j][1]
                                )

                        else:
                            """遍历模式: False"""
                            """安全放一张卡"""

                            # 防止误触
                            if card["location"][0] in warning_cell:
                                use_key(mode=1)

                            # 点击 放下卡片
                            mouse_left_click(
                                handle=handle,
                                interval_time=click_interval,
                                sleep_time=click_sleep,
                                x=card["location_to"][0][0],
                                y=card["location_to"][0][1]
                            )

                        """放卡后点一下空白"""
                        mouse_left_moveto(handle=handle, x=200, y=350)
                        mouse_left_click(
                            handle=handle,
                            x=int(200 * zoom),
                            y=int(350 * zoom),
                            interval_time=click_interval,
                            sleep_time=click_sleep)

                    """每放完一张卡片的所有位置 检查时间设定间隔 检测战斗间隔"""
                    if time.time() - check_last_one_time > check_invite:

                        # 测试用时
                        # print("[{}][放卡间进行了战斗结束检测] {:.2f}s".format(player, time.time()- check_last_one_time))

                        # 更新上次检测时间 + 更新flag + 中止休息循环
                        check_last_one_time = time.time()
                        if use_key_and_check_end():
                            end_flag = True
                            break

                if end_flag:
                    break  # 根据flag 跳出外层循环

                # 放完一轮卡后 在位置数组里 将每个卡的 第一个位置移到最后
                for i in range(len(list_cell_all)):
                    if list_cell_all[i]["queue"]:
                        list_cell_all[i]["location"].append(list_cell_all[i]["location"][0])
                        list_cell_all[i]["location"].remove(list_cell_all[i]["location"][0])
                        list_cell_all[i]["location_to"].append(list_cell_all[i]["location_to"][0])
                        list_cell_all[i]["location_to"].remove(list_cell_all[i]["location_to"][0])

                # 武器技能 + 自动收集
                use_weapon_skill()
                auto_pickup()

                """一轮不到7s+点7*9个位置需要的时间, 休息到该时间, 期间每[check_invite]秒检测一次"""
                time_spend_a_round = time.time() - time_round_begin
                if time_spend_a_round < round_max_time:
                    for i in range(int((round_max_time - time_spend_a_round) // check_invite)):

                        """检查时间设定间隔 检测战斗间隔"""
                        if time.time() - check_last_one_time > check_invite:

                            # 测试用时
                            # print("[{}][休息期战斗结束检测] {:.2f}s".format(player,time() - check_last_one_time))

                            # 更新上次检测时间 + 更新flag + 中止休息循环
                            check_last_one_time = time.time()
                            if use_key_and_check_end():
                                end_flag = True
                                break
                        time.sleep(check_invite)
                    time.sleep((round_max_time - time_spend_a_round) % check_invite)  # 补充余数
                else:
                    """一轮放卡循环>7s 检查时间设定间隔 检测战斗间隔"""
                    if time.time() - check_last_one_time > check_invite:

                        # 测试用时
                        # print("[{}][补战斗结束检测] {:.2f}s".format(player, time.time()- check_last_one_time))  # 测试用时

                        # 更新上次检测时间 + 更新flag + 中止休息循环
                        check_last_one_time = time.time()

                        if use_key_and_check_end():
                            break

                if end_flag:
                    break  # 根据flag 跳出外层循环

        def use_card_loop_1(list_cell_all):
            """循环方式 每一个卡都先在其对应的全部的位置放一次,再放下一张(每轮开始位置+1)"""
            print_g(
                text="测试方法, 啥都没有",
                player=self.player,
                garde=1)
            return False

        def use_card_loop_skill():
            # 放人
            use_player("5-4")

            # 计算目标位置 1-14
            cell_list = []
            for i in range(2):
                for j in range(9):
                    cell_list.append(str(j + 1) + "-" + str(i + 2))

            # 常规放卡
            for k in range(13):
                use_card_once(
                    num_card=k + 1,
                    num_cell=cell_list[k],
                    click_space=False)
                time.sleep(0.07)

            # 叠加放卡
            # for k in range(3):
            #     faa.battle_use_card(k*2 + 1 + 8, cell_list[k + 8], click_space=False)
            #     sleep(0.15)
            #     faa.battle_use_card(k*2 + 2 + 8, cell_list[k + 8], click_space=False)
            #     sleep(0.05)

            # 退出关卡
            self.action_exit(mode="游戏内退出")

        """主函数"""

        def main():
            mat_card_position = self.get_mat_card_position()

            list_cell_all, list_shovel = self.calculation_cell_all_card(mat_card_position=mat_card_position)

            # 放人物
            for i in battle_plan["player"]:
                use_player(i)

            time.sleep(1)

            # 铲自带的卡
            if player == 1:
                use_shovel(positions=list_shovel)

            time.sleep(1)

            # 战斗循环
            if battle_mode == 0:
                use_card_loop_0(list_cell_all=list_cell_all)

            elif battle_mode == 1:
                use_card_loop_1(list_cell_all=list_cell_all)

            elif battle_mode == 3:
                use_card_loop_skill()

            else:
                print(list_cell_all, list_shovel)
                print("不战斗 用于测试战斗数组的计算")

        main()

    def action_round_of_battle_before(self):

        """
        房间内战前准备
        :return: 0-正常结束 1-重启本次 2-跳过本次
        """

        """调用类参数"""
        zoom = self.zoom
        handle = self.handle
        player = self.player

        """调用类参数-战斗前生成"""
        deck = self.deck
        quest_card = self.quest_card
        ban_card_list = self.ban_card_list

        def action_add_quest_card():
            # 由于公会任务的卡组特性, 当任务卡为[苏打气泡]时, 不需要额外选择带卡.
            my_bool = False
            my_bool = my_bool or quest_card == "None"
            my_bool = my_bool or quest_card == "苏打气泡-0"
            my_bool = my_bool or quest_card == "苏打气泡-1"
            my_bool = my_bool or quest_card == "苏打气泡"
            if my_bool:
                print_g(text="不需要额外带卡,跳过", player=player, garde=1)
            else:
                print_g(text="寻找任务卡, 开始", player=player, garde=1)

                # 对于名称带-的卡, 就对应的写入, 如果不带-, 就查找其所有变种
                quest_card_s = []
                if "-" in quest_card:
                    quest_card_s.append("{}".format(quest_card))
                else:
                    for i in range(9):  # i代表一张卡能有的最高变种 姑且认为是3*3 = 9
                        quest_card_s.append("{}-{}".format(quest_card, i))

                # 读取所有记录了的卡的图片名, 只携带被记录图片的卡
                my_list = []
                for quest_card_n in quest_card_s:
                    if quest_card_n in self.card_recorded_room:
                        my_list.append(quest_card_n)
                quest_card_s = my_list

                flag_find_quest_card = False

                for quest_card_n in quest_card_s:
                    # 复位滑块
                    mouse_left_click(
                        handle=handle,
                        x=int(931 * zoom),
                        y=int(209 * zoom),
                        sleep_time=0.25)

                    # 最多向下点3*7次滑块
                    for i in range(7):

                        # 找到就点一下, 任何一次寻找成功 中断循环
                        if not flag_find_quest_card:

                            find = loop_find_p_in_w(
                                raw_w_handle=handle,
                                raw_range=[380, 175, 925, 420],
                                target_path=paths["picture"]["card"] + "\\房间\\" + quest_card_n + ".png",
                                target_tolerance=0.95,
                                target_failed_check=0.4,
                                target_sleep=0.2,
                                click_zoom=zoom,
                                click=True)
                            if find:
                                flag_find_quest_card = True
                                break

                            # 滑块向下移动3次
                            for j in range(3):
                                mouse_left_click(
                                    handle=handle,
                                    x=int(931 * zoom),
                                    y=int(400 * zoom),
                                    sleep_time=0.05)

                    if flag_find_quest_card:
                        break

                print_g(
                    text="寻找任务卡, 完成, 结果:{}".format("成功" if flag_find_quest_card else "失败"),
                    player=player,
                    garde=1)

        def action_remove_ban_card():
            """寻找并移除需要ban的卡, 暂不支持跨页ban, 只从前11张ban"""
            # 只有ban卡数组非空, 继续进行
            if ban_card_list:
                ban_card_s = []

                # 处理需要ban的卡片,
                for ban_card in ban_card_list:
                    # 对于名称带-的卡, 就对应的写入, 如果不带-, 就查找其所有变种
                    if "-" in ban_card:
                        ban_card_s.append("{}".format(ban_card))
                    else:
                        for i in range(9):  # i代表一张卡能有的最高变种 姑且认为是3*3 = 9
                            ban_card_s.append("{}-{}".format(ban_card, i))

                # 读取所有已记录的卡片文件名, 并去除没有记录的卡片
                my_list = []
                for ban_card_n in ban_card_s:
                    if ban_card_n in self.card_recorded_room:
                        my_list.append(ban_card_n)
                ban_card_s = my_list

                for ban_card_n in ban_card_s:
                    # 只ban被记录了图片的变种卡
                    loop_find_p_in_w(
                        raw_w_handle=handle,
                        raw_range=[380, 40, 915, 105],
                        target_path=paths["picture"]["card"] + "\\房间\\" + ban_card_n + ".png",
                        target_tolerance=0.95,
                        target_interval=0.2,
                        target_failed_check=1,
                        target_sleep=1,
                        click=True,
                        click_zoom=zoom)
                # 休息1s
                time.sleep(1)

        def main():
            # 循环查找开始按键
            print_g(text="寻找开始或准备按钮", player=player, garde=1)
            find = loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=[796, 413, 950, 485],
                target_path=paths["picture"]["common"] + "\\战斗\\战斗前_开始按钮.png",
                target_interval=1,
                target_failed_check=10,
                target_sleep=0.3,
                click=False)
            if not find:
                print_g(text="创建房间后, 10s找不到[开始/准备]字样! 创建房间可能失败!", player=player, garde=2)
                # 可能是由于: 服务器抽风无法创建房间 or 点击被吞 or 次数用尽
                return 2  # 2-跳过本次

            # 选择卡组
            print_g(text="选择卡组, 并开始加入新卡和ban卡", player=player, garde=1)
            mouse_left_click(
                handle=handle,
                x=int({1: 425, 2: 523, 3: 588, 4: 666, 5: 756, 6: 837}[deck] * zoom),
                y=int(121 * zoom),
                sleep_time=0.7)

            """寻找并添加任务所需卡片"""
            action_add_quest_card()
            action_remove_ban_card()

            """点击开始"""

            # 点击开始
            find = loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=[796, 413, 950, 485],
                target_path=paths["picture"]["common"] + "\\战斗\\战斗前_开始按钮.png",
                target_tolerance=0.95,
                target_interval=1,
                target_failed_check=10,
                target_sleep=1,
                click=True,
                click_zoom=zoom)
            if not find:
                print_g(text="选择卡组后, 10s找不到[开始/准备]字样! 创建房间可能失败!", player=player, garde=2)
                return 1  # 1-重启本次

            # 防止被 [没有带xx卡] or []包已满 卡住
            find = find_p_in_w(
                raw_w_handle=handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["common"] + "\\战斗\\战斗前_系统提示.png",
                target_tolerance=0.98)
            if find:
                mouse_left_click(handle=handle, x=int(427 * zoom), y=int(353 * zoom))

            return 0  # 0-一切顺利

        return main()

    def action_round_of_battle_self(self):

        """
        关卡内战斗过程
        返回值 0-正常结束 1-重启本次 2-跳过本次
        """

        handle = self.handle
        zoom = self.zoom
        player = self.player

        def screen_loot_logs():
            """
            :return: 捕获的战利品dict
            """
            # 是否还在战利品ui界面
            find = find_ps_in_w(
                raw_w_handle=handle,
                target_opts=[
                    {
                        "raw_range": [202, 419, 306, 461],
                        "target_path": paths["picture"]["common"] + "\\战斗\\战斗后_1_战利品.png",
                        "target_tolerance": 0.999},
                    {
                        "raw_range": [202, 419, 306, 461],
                        "target_path": paths["picture"]["common"] + "\\战斗\\战斗后_2_战利品阴影版.png",
                        "target_tolerance": 0.999
                    }
                ],
                return_mode="or")
            if find:
                print_g(text="[战利品UI] 正常结束, 尝试捕获战利品截图", player=player, garde=1)

                def screen():
                    # 记录战利品 tip 一张图49x49 是完美规整的
                    image = []
                    mouse_left_click(
                        handle=handle,
                        x=int(708 * zoom),
                        y=int(484 * zoom),
                        interval_time=0.05,
                        sleep_time=0.3)
                    image.append(
                        capture_picture_png(
                            handle=handle,
                            raw_range=[209, 454, 699, 552]))
                    time.sleep(0.5)

                    mouse_left_click(
                        handle=handle,
                        x=int(708 * zoom),
                        y=int(510 * zoom),
                        interval_time=0.05,
                        sleep_time=0.3)
                    image.append(
                        capture_picture_png(
                            handle=handle,
                            raw_range=[209, 456, 699, 505]))
                    time.sleep(0.5)

                    mouse_left_click(
                        handle=handle,
                        x=int(708 * zoom),
                        y=int(529 * zoom),
                        interval_time=0.05,
                        sleep_time=0.3)
                    image.append(
                        capture_picture_png(
                            handle=handle,
                            raw_range=[209, 454, 699, 552]))

                    # 垂直拼接
                    image = vconcat(image)

                    return image

                # 定义保存路径和文件名格式
                my_path = "{}\\{}_{}P_{}.png".format(
                    paths["logs"] + "\\loot_picture",
                    self.stage_info["id"],
                    player,
                    time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime())
                )

                # 截图并保存
                screen = screen()
                imwrite(my_path, screen)

                # 分析图片，获取战利品字典
                drop_dict = matchImage(imagePath=my_path)
                print_g(text="[战利品UI] 战利品已 捕获/识别/保存, 如下:".format(drop_dict), player=player, garde=1)
                print(drop_dict)

                def statistics():

                    # 分P，在目录下保存战利品字典。
                    file_path = "{}\\loot_json\\{}P掉落汇总.json".format(paths["logs"], player)
                    stage_name = self.stage_info["id"]

                    if os.path.exists(file_path):
                        # 尝试读取现有的JSON文件
                        with open(file_path, "r", encoding="utf-8") as json_file:
                            json_data = json.load(json_file)
                    else:
                        # 如果文件不存在，初始化
                        json_data = {}

                    if stage_name in json_data:
                        # 更新现有数据
                        for item_str, count in drop_dict.items():
                            if item_str in json_data[stage_name]["loots"]:
                                json_data[stage_name]["loots"][item_str] += count  # 更新数量
                            else:
                                json_data[stage_name]["loots"][item_str] = count  # 新增道具

                        json_data[stage_name]["times"] += 1  # 更新次数

                    else:
                        # 初始化新数据
                        json_data[stage_name] = {
                            "loots": drop_dict,
                            "times": 1
                        }

                    # 保存或更新后的战利品字典到JSON文件
                    with open(file_path, "w", encoding="utf-8") as json_file:
                        json.dump(json_data, json_file, ensure_ascii=False, indent=4)

                def detail():

                    # 分P，在目录下保存战利品字典。
                    file_path = "{}\\loot_json\\{}P掉落明细.json".format(paths["logs"], player)
                    stage_name = self.stage_info["id"]

                    if os.path.exists(file_path):
                        # 读取现有的JSON文件
                        with open(file_path, "r", encoding="utf-8") as json_file:
                            json_data = json.load(json_file)
                    else:
                        # 如果文件不存在，初始化
                        json_data = {"data": []}

                    json_data["data"].append({
                        "timestamp": time.time(),
                        "stage": stage_name,
                        "loots": drop_dict,
                    })

                    # 保存或更新后的战利品字典到JSON文件
                    with open(file_path, "w", encoding="utf-8") as json_file:
                        json.dump(json_data, json_file, ensure_ascii=False, indent=4)

                statistics()
                detail()

                return drop_dict

            else:
                print_g(text="[非战利品UI] 正常结束, 可能由于延迟未能捕获战利品, 继续流程", player=player, garde=1)

                return None

        def action_flip_treasure_chest():
            find = loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=[400, 35, 550, 75],
                target_path=paths["picture"]["common"] + "\\战斗\\战斗后_4_翻宝箱.png",
                target_failed_check=15,
                target_sleep=2,
                click=False,
                click_zoom=zoom
            )
            if find:
                print_g(text="[翻宝箱UI] 捕获到正确标志, 翻牌并退出...", player=player, garde=1)
                # 开始洗牌
                mouse_left_click(
                    handle=handle,
                    x=int(708 * zoom),
                    y=int(502 * zoom),
                    interval_time=0.05,
                    sleep_time=6)
                # 翻牌 1+2
                mouse_left_click(
                    handle=handle,
                    x=int(550 * zoom),
                    y=int(170 * zoom),
                    interval_time=0.05,
                    sleep_time=0.5)
                mouse_left_click(
                    handle=handle,
                    x=int(708 * zoom),
                    y=int(170 * zoom),
                    interval_time=0.05,
                    sleep_time=0.5)

                # 组队2P慢点结束翻牌 保证双人魔塔后自己是房主
                if self.is_group and player == 2:
                    time.sleep(2)

                # 结束翻牌
                mouse_left_click(
                    handle=handle,
                    x=int(708 * zoom),
                    y=int(502 * zoom),
                    interval_time=0.05,
                    sleep_time=3)

            else:
                print_g(text="[翻宝箱UI] 15s未能捕获正确标志, 出问题了!", player=player, garde=2)

        def main():

            # 刷新ui: 状态文本
            print_g(text="查找火苗标识物, 等待进入战斗, 限时30s", player=player, garde=1)

            # 循环查找火苗图标 找到战斗开始
            find = loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["common"] + "\\战斗\\战斗中_火苗能量.png",
                target_interval=0.5,
                target_failed_check=30,
                target_sleep=0.1,
                click=False,
                click_zoom=zoom)

            # 刷新ui: 状态文本
            if find:
                print_g(text="找到火苗标识物, 战斗进行中...", player=player, garde=1)

                # 非1P晚一点点开始 这是必须的!!!! 否则人物都放不下来
                time.sleep(0 if player == 1 else 0.33333)

                # 战斗循环
                self.action_in_battle()

                print_g(text="识别到五种战斗结束标志之一, 进行收尾工作", player=player, garde=1)

                """战斗结束后, 一般流程为 (潜在的任务完成黑屏) -> 战利品 -> 战斗结算 -> 翻宝箱, 之后会回到房间, 魔塔会回到其他界面"""

                # 战利品部分
                loot_dict = screen_loot_logs()

                # 战斗结算部分, 等待跳过就好了

                # 翻宝箱部分, 循环查找, 确认是否可以安全翻牌
                action_flip_treasure_chest()

            else:
                print_g(text="未能找到火苗标识物, 进入战斗失败, 可能是次数不足或服务器卡顿", player=player, garde=2)
                return 2, None  # 2-跳过本次

            return 0, loot_dict  # 0-正常结束

        return main()

    def action_round_of_battle_after(self):

        """
        房间内或其他地方 战斗结束
        :return: 0-正常结束 1-重启本次 2-跳过本次
        """

        handle = self.handle
        player = self.player

        # 查找战斗结束 来兜底正确完成了战斗
        print_g(text="[开始/准备/魔塔蛋糕UI] 尝试捕获正确标志, 以完成战斗流程.", player=player, garde=1)
        find = loop_find_ps_in_w(
            raw_w_handle=handle,
            target_opts=[
                {
                    "raw_range": [796, 413, 950, 485],
                    "target_path": paths["picture"]["common"] + "\\战斗\\战斗前_开始按钮.png",
                    "target_tolerance": 0.99},
                {
                    "raw_range": [200, 0, 750, 100],
                    "target_path": paths["picture"]["common"] + "\\魔塔蛋糕_ui.png",
                    "target_tolerance": 0.99
                }],
            target_return_mode="or",
            target_failed_check=10,
            target_interval=0.2)
        if find:
            print_g(text="成功捕获[开始/准备/魔塔蛋糕UI], 完成战斗流程.", player=player, garde=1)
            return 0  # 0-正常结束
        else:
            print_g(text="10s没能捕获[开始/准备/魔塔蛋糕UI], 出现意外错误, 直接跳过本次", player=player, garde=3)
            return 2  # 2-跳过本次

    """其他非战斗功能"""

    def reload_to_login_ui(self):
        zoom = self.zoom
        handle = self.handle_360

        # 点击刷新按钮 该按钮在360窗口上
        find = loop_find_p_in_w(
            raw_w_handle=handle,
            raw_range=[0, 0, 400, 100],
            target_path=paths["picture"]["common"] + "\\登录\\0_刷新.png",
            target_tolerance=0.9,
            target_sleep=3,
            click=True,
            click_zoom=zoom)

        if not find:
            find = loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=[0, 0, 400, 100],
                target_path=paths["picture"]["common"] + "\\登录\\0_刷新_被选中.png",
                target_tolerance=0.98,
                target_sleep=3,
                click=True,
                click_zoom=zoom)

            if not find:
                print_g(text="未找到360大厅刷新游戏按钮, 可能导致一系列问题", player=self.player, garde=2)

    def reload_game(self):
        zoom = self.zoom
        while True:

            # 点击刷新按钮 该按钮在360窗口上
            self.reload_to_login_ui()

            # 是否在 选择服务器界面 - 判断是否存在 最近玩过的服务器ui(4399 or qq空间)
            result = loop_find_ps_in_w(
                raw_w_handle=self.handle_browser,
                target_opts=[
                    {
                        "raw_range": [0, 0, 2000, 2000],
                        "target_path": paths["picture"]["common"] + "\\登录\\1_我最近玩过的服务器_4399.png",
                        "target_tolerance": 0.9,
                    }, {
                        "raw_range": [0, 0, 2000, 2000],
                        "target_path": paths["picture"]["common"] + "\\登录\\1_我最近玩过的服务器_qq.png",
                        "target_tolerance": 0.9,
                    }
                ],
                target_return_mode="or")

            if not result:
                print_g(text="未找到进入输入服务器, 可能进入未知界面, 或QQ空间需重新登录", player=self.player, garde=1)
                result = loop_find_p_in_w(
                    raw_w_handle=self.handle_browser,
                    raw_range=[0, 0, 2000, 2000],
                    target_path=paths["picture"]["common"] + "\\用户自截\\空间服登录界面_{}P.png".format(self.player),
                    target_tolerance=0.95,
                    target_interval=0.5,
                    target_failed_check=5,
                    target_sleep=5,
                    click=True,
                    click_zoom=zoom)
                if result:
                    print_g(text="找到qq空间服一键登录, 正在登录", player=self.player, garde=0)
                else:
                    print_g(text="未找到qq空间服一键登录, 非qq服或其他原因", player=self.player, garde=1)

                continue

            else:
                """尝试根据QQ空间或4399的不同ui 进入最近进入的服务器"""
                # 4399
                result = find_p_in_w(
                    raw_w_handle=self.handle_browser,
                    raw_range=[0, 0, 2000, 2000],
                    target_path=paths["picture"]["common"] + "\\登录\\1_我最近玩过的服务器_4399.png",
                    target_tolerance=0.9
                )
                if result:
                    # 点击进入服务器
                    mouse_left_click(
                        handle=self.handle_browser,
                        x=int(result[0] * zoom),
                        y=int((result[1] + 30) * zoom),
                        sleep_time=0.5)

                # QQ空间
                result = find_p_in_w(
                    raw_w_handle=self.handle_browser,
                    raw_range=[0, 0, 2000, 2000],
                    target_path=paths["picture"]["common"] + "\\登录\\1_我最近玩过的服务器_qq.png",
                    target_tolerance=0.9
                )
                if result:
                    # 点击进入服务器
                    mouse_left_click(
                        handle=self.handle_browser,
                        x=int(result[0] * zoom),
                        y=int((result[1] + 30) * zoom),
                        sleep_time=0.5)

                """查找 - 关闭 健康游戏公告"""
                # 查找健康游戏公告
                result = loop_find_p_in_w(
                    raw_w_handle=self.handle_browser,
                    raw_range=[0, 0, 2000, 2000],
                    target_path=paths["picture"]["common"] + "\\登录\\2_健康游戏公告.png",
                    target_tolerance=0.97,
                    target_failed_check=30,
                    target_sleep=0.5,
                    click=False)
                if not result:
                    print_g(text="未找到健康游戏公告, 重新刷新", player=self.player, garde=2)
                    continue
                else:
                    # 重新获取句柄, 此时游戏界面的句柄已经改变
                    self.handle = faa_get_handle(channel=self.channel, mode="flash")

                    # 关闭健康游戏公告
                    loop_find_p_in_w(
                        raw_w_handle=self.handle,
                        raw_range=[0, 0, 950, 600],
                        target_path=paths["picture"]["common"] + "\\登录\\3_健康游戏公告_确定.png",
                        target_tolerance=0.97,
                        target_failed_check=15,
                        click=True,
                        click_zoom=zoom)

                    # [可能发生] 每日必充界面关闭
                    loop_find_p_in_w(
                        raw_w_handle=self.handle,
                        raw_range=[0, 0, 950, 600],
                        target_path=paths["picture"]["common"] + "\\登录\\4_退出每日必充.png",
                        target_tolerance=0.99,
                        target_failed_check=2,
                        click=True,
                        click_zoom=zoom)

                    break

    def sign_in(self):

        handle = self.handle
        zoom = self.zoom

        def sign_in_vip():
            """VIP签到"""
            self.action_top_menu(mode="VIP签到")

            mouse_left_click(
                handle=handle,
                x=int(740 * zoom),
                y=int(190 * zoom),
                sleep_time=0.5)

            mouse_left_click(
                handle=handle,
                x=int(225 * zoom),
                y=int(280 * zoom),
                sleep_time=0.5)

            self.action_exit(mode="普通红叉")

        def sign_in_everyday():
            """每日签到"""
            self.action_top_menu(mode="每日签到")

            loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["common"] + "\\签到\\每日签到_确定.png",
                target_tolerance=0.99,
                target_failed_check=1,
                target_sleep=1,
                click=True,
                click_zoom=zoom)

            self.action_exit(mode="普通红叉")

        def sign_in_food_activity():
            """美食活动"""

            self.action_top_menu(mode="美食活动")

            loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["common"] + "\\签到\\美食活动_确定.png",
                target_tolerance=0.99,
                target_failed_check=1,
                target_sleep=1,
                click=True,
                click_zoom=zoom)

            self.action_exit(mode="普通红叉")

        def sign_in_tarot():
            """塔罗寻宝"""
            self.action_top_menu(mode="塔罗寻宝")

            loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["common"] + "\\签到\\塔罗寻宝_确定.png",
                target_tolerance=0.99,
                target_failed_check=1,
                target_sleep=1,
                click=True,
                click_zoom=zoom)

            loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["common"] + "\\签到\\塔罗寻宝_退出.png",
                target_tolerance=0.99,
                target_failed_check=1,
                target_sleep=1,
                click=True,
                click_zoom=zoom)

        def sign_in_pharaoh():
            """法老宝藏"""
            self.action_top_menu(mode="法老宝藏")

            find = loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["common"] + "\\签到\\法老宝藏_确定.png",
                target_tolerance=0.99,
                target_failed_check=1,
                target_sleep=1,
                click=False)

            if find:
                mouse_left_click(
                    handle=handle,
                    x=int(300 * zoom),
                    y=int(250 * zoom),
                    sleep_time=1)

            mouse_left_click(
                handle=handle,
                x=int(791 * zoom),
                y=int(98 * zoom),
                sleep_time=1)

        def sign_in_release_quest_guild():
            """会长发布任务"""
            self.action_bottom_menu(mode="跳转_公会任务")

            find = loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=[73, 31, 173, 78],
                target_path=paths["picture"]["common"] + "\\签到\\公会会长_发布任务.png",
                target_tolerance=0.99,
                target_failed_check=1,
                target_sleep=1,
                click=False,
                click_zoom=zoom)
            if find:
                loop_find_p_in_w(
                    raw_w_handle=handle,
                    raw_range=[422, 415, 544, 463],
                    target_path=paths["picture"]["common"] + "\\签到\\公会会长_发布任务_确定.png",
                    target_tolerance=0.99,
                    target_failed_check=1,
                    target_sleep=3,
                    click=False,
                    click_zoom=zoom)
                # 关闭抽奖(红X)
                self.action_exit(mode="普通红叉", raw_range=[616, 172, 660, 228])

            # 关闭任务列表(红X)
            self.action_exit(mode="普通红叉", raw_range=[834, 35, 876, 83])

        def sign_in_camp_key():
            """领取营地钥匙"""
            # 进入界面
            find = self.action_goto_map(map_id=6)

            if find:
                # 领取钥匙
                mouse_left_click(
                    handle=handle,
                    x=int(400 * zoom),
                    y=int(445 * zoom),
                    sleep_time=0.5)

        def main():
            sign_in_vip()
            sign_in_everyday()
            sign_in_food_activity()
            sign_in_tarot()
            sign_in_pharaoh()
            sign_in_release_quest_guild()
            sign_in_camp_key()

        main()

    def fed_and_watered(self):
        """公会施肥浇水功能"""
        # 暂存常用变量
        handle = self.handle
        zoom = self.zoom

        def from_guild_to_quest_guild():
            """进入任务界面, 正确进入就跳出循环"""
            while True:
                mouse_left_click(
                    handle=self.handle,
                    x=int(745 * self.zoom),
                    y=int(430 * self.zoom),
                    sleep_time=0.001
                )
                mouse_left_click(
                    handle=self.handle,
                    x=int(700 * self.zoom),
                    y=int(350 * self.zoom),
                    sleep_time=2
                )
                find = loop_find_p_in_w(
                    raw_w_handle=handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=paths["picture"]["quest_guild"] + "\\ui_quest_list.png",
                    target_tolerance=0.95,
                    target_failed_check=1,
                    target_sleep=0.5,
                    click_zoom=zoom,
                    click=True
                )
                if find:
                    break

        def from_guild_to_guild_garden():
            """进入施肥界面, 正确进入就跳出循环"""
            while True:
                mouse_left_click(
                    handle=self.handle,
                    x=int(745 * self.zoom),
                    y=int(430 * self.zoom),
                    sleep_time=0.001
                )
                mouse_left_click(
                    handle=self.handle,
                    x=int(800 * self.zoom),
                    y=int(350 * self.zoom),
                    sleep_time=2
                )
                find = loop_find_p_in_w(
                    raw_w_handle=handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=paths["picture"]["quest_guild"] + "\\ui_fed.png",
                    target_tolerance=0.95,
                    target_failed_check=1,
                    target_sleep=0.5,
                    click_zoom=zoom,
                    click=True
                )
                if find:
                    break

        def switch_guild_garden_by_try_times(try_time):
            """根据目前尝试次数, 到达不同的公会"""
            if try_time != 0:

                # 点击全部工会
                mouse_left_click(
                    handle=self.handle,
                    x=int(798 * self.zoom),
                    y=int(123 * self.zoom),
                    sleep_time=0.5
                )

                # 跳转到最后
                mouse_left_click(
                    handle=self.handle,
                    x=int(843 * self.zoom),
                    y=int(305 * self.zoom),
                    sleep_time=0.5
                )

                # 以倒数第二页从上到下为1-4, 第二页为5-8次尝试对应的公会 以此类推
                for i in range((try_time - 1) // 4 + 1):
                    # 向上翻的页数
                    mouse_left_click(
                        handle=self.handle,
                        x=int(843 * self.zoom),
                        y=int(194 * self.zoom),
                        sleep_time=0.5)

                # 点第几个
                my_dict = {1: 217, 2: 244, 3: 271, 4: 300}
                mouse_left_click(
                    handle=self.handle,
                    x=int(810 * self.zoom),
                    y=int(my_dict[(try_time - 1) % 4 + 1] * self.zoom),
                    sleep_time=0.5)

        def do_something_and_exit(try_time):
            """完成素质三连并退出公会花园界面"""
            # 采摘一次
            mouse_left_click(
                handle=self.handle,
                x=int(785 * self.zoom),
                y=int(471 * self.zoom),
                sleep_time=1
            )
            # 浇水一次
            mouse_left_click(
                handle=self.handle,
                x=int(785 * self.zoom),
                y=int(362 * self.zoom),
                sleep_time=1
            )
            # 等待一下 确保没有完成的黑屏
            loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["common"] + "\\退出.png",
                target_tolerance=0.95,
                target_failed_check=7,
                target_sleep=1,
                click=False
            )
            print_g(
                text="{}次尝试, 浇水后, 已确认无任务完成黑屏".format(try_time + 1),
                player=self.player,
                garde=1)

            # 施肥一次
            mouse_left_click(
                handle=self.handle,
                x=int(785 * self.zoom),
                y=int(418 * self.zoom),
                sleep_time=1
            )
            # 等待一下 确保没有完成的黑屏
            loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["common"] + "\\退出.png",
                target_tolerance=0.95,
                target_failed_check=7,
                target_sleep=1,
                click=False)
            print_g(
                text="{}次尝试, 施肥后, 已确认无任务完成黑屏".format(try_time + 1),
                player=self.player,
                garde=1)

            # 点X回退一次
            mouse_left_click(
                handle=self.handle,
                x=int(854 * self.zoom),
                y=int(55 * self.zoom),
                sleep_time=1.5)

        def fed_and_watered_one_action(try_time):
            """
            :return: bool completed True else False
            """
            # 进入任务界面, 正确进入就跳出循环
            from_guild_to_quest_guild()

            # 检测施肥任务完成情况 任务是进行中的话为True
            find = loop_find_ps_in_w(
                raw_w_handle=handle,
                target_opts=[
                    {
                        "raw_range": [75, 80, 430, 560],
                        "target_path": paths["picture"]["quest_guild"] + "\\fed_0.png",
                        "target_tolerance": 0.98
                    }, {
                        "raw_range": [75, 80, 430, 560],
                        "target_path": paths["picture"]["quest_guild"] + "\\fed_1.png",
                        "target_tolerance": 0.98
                    }, {
                        "raw_range": [75, 80, 430, 560],
                        "target_path": paths["picture"]["quest_guild"] + "\\fed_2.png",
                        "target_tolerance": 0.98,
                    }, {
                        "raw_range": [75, 80, 430, 560],
                        "target_path": paths["picture"]["quest_guild"] + "\\fed_3.png",
                        "target_tolerance": 0.98,
                    }
                ],
                target_return_mode="or",
                target_failed_check=2)

            # 退出任务界面
            mouse_left_click(
                handle=self.handle,
                x=int(854 * self.zoom),
                y=int(55 * self.zoom),
                sleep_time=0.5
            )

            if not find:
                print_g(
                    text="已完成公会浇水施肥, 尝试次数:{}".format(try_time),
                    player=self.player,
                    garde=1)
                return True
            else:
                # 进入施肥界面, 正确进入就跳出循环
                from_guild_to_guild_garden()

                # 根据目前尝试次数, 到达不同的公会
                switch_guild_garden_by_try_times(try_time=try_time)

                # 完成素质三连并退出公会花园界面
                do_something_and_exit(try_time=try_time)

                return False

        def fed_and_watered_main():
            print_g(
                text="开始公会浇水施肥",
                player=self.player,
                garde=1)

            # 进入公会
            self.action_bottom_menu(mode="公会")

            # 循环到任务完成
            try_time = 0
            while True:
                completed_flag = fed_and_watered_one_action(try_time)
                try_time += 1
                if completed_flag:
                    break

            # 退出工会
            self.action_exit(mode="普通红叉")

        fed_and_watered_main()
        self.action_quest_receive_rewards(mode="公会任务")

    def use_item(self):

        handle = self.handle
        zoom = self.zoom
        # 获取所有图片资源
        my_list = os.listdir(paths["picture"]["item"] + "\\背包\\")
        print_g(text="开启使用物品功能", player=self.player, garde=1)

        # 打开背包
        print_g(text="打开背包", player=self.player, garde=1)
        self.action_bottom_menu(mode="背包")

        # 升到最顶, 不需要, 打开背包会自动重置

        # 四次循环查找所有正确图标
        for i in range(4):

            print_g(text="第{}页物品".format(i + 1), player=self.player, garde=1)

            # 第一次以外, 下滑4*5次
            if i != 0:
                for j in range(5):
                    mouse_left_click(
                        handle=handle,
                        x=int(920 * zoom),
                        y=int(422 * zoom),
                        sleep_time=0.2)

            for item in my_list:

                while True:

                    # 在限定范围内 找红叉点掉
                    loop_find_p_in_w(
                        raw_w_handle=handle,
                        raw_range=[0, 0, 750, 300],
                        target_path=paths["picture"]["common"] + "\\退出.png",
                        target_tolerance=0.95,
                        target_interval=0.2,
                        target_failed_check=1,
                        target_sleep=0.5,
                        click=True,
                        click_zoom=zoom)

                    # 在限定范围内 找物品
                    find = loop_find_p_in_w(
                        raw_w_handle=handle,
                        raw_range=[466, 86, 891, 435],
                        target_path=paths["picture"]["item"] + "\\背包\\" + item,
                        target_tolerance=0.95,
                        target_interval=0.2,
                        target_failed_check=1,
                        target_sleep=0.5,
                        click=True,
                        click_zoom=zoom)

                    if find:
                        # 在限定范围内 找到并点击物品 使用它
                        find = loop_find_p_in_w(
                            raw_w_handle=handle,
                            raw_range=[466, 86, 950, 500],
                            target_path=paths["picture"]["item"] + "\\背包\\使用.png",
                            target_tolerance=0.95,
                            target_interval=0.2,
                            target_failed_check=1,
                            target_sleep=0.5,
                            click=True,
                            click_zoom=zoom)

                        # 鼠标选中 使用按钮 会有色差, 第一次找不到则再来一次
                        if not find:
                            loop_find_p_in_w(
                                raw_w_handle=handle,
                                raw_range=[466, 86, 950, 500],
                                target_path=paths["picture"]["item"] + "\\背包\\使用_被选中.png",
                                target_tolerance=0.95,
                                target_interval=0.2,
                                target_failed_check=1,
                                target_sleep=0.5,
                                click=True,
                                click_zoom=zoom)

                    else:
                        # 没有找到对应物品 skip
                        print_g(text="物品:{}本页已全部找到".format(item), player=self.player, garde=1)
                        break

        # 关闭背包
        self.action_exit(mode="普通红叉")

    def cross_server_reputation(self, deck):

        zoom = self.zoom
        player = self.player
        handle = self.handle

        first_time = True

        while True:

            if first_time:
                # 进入界面
                self.action_top_menu(mode="跨服远征")
                first_time = False

            # 创建房间-右下角
            mouse_left_click(
                handle=handle,
                x=int(853 * zoom),
                y=int(553 * zoom),
                sleep_time=0.5)

            # 选择地图-巫毒
            mouse_left_click(
                handle=handle,
                x=int(65 * zoom),
                y=int(470 * zoom),
                sleep_time=0.5)

            # 选择关卡-第二关
            mouse_left_click(
                handle=handle,
                x=int(401 * zoom),
                y=int(286 * zoom),
                sleep_time=0.5)

            # 随便公会任务卡组
            mouse_left_click(
                handle=handle,
                x=int({1: 425, 2: 523, 3: 588, 4: 666, 5: 756, 6: 837}[deck] * zoom),
                y=int(121 * zoom),
                sleep_time=0.2)

            # 点击开始
            find = loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=[796, 413, 950, 485],
                target_path=paths["picture"]["common"] + "\\战斗\\战斗前_开始按钮.png",
                target_tolerance=0.95,
                target_interval=1,
                target_failed_check=30,
                target_sleep=0.2,
                click=True,
                click_zoom=zoom)
            if not find:
                print_g(
                    text="30s找不到[开始/准备]字样! 创建房间可能失败! 直接reload游戏防止卡死",
                    player=player,
                    garde=2
                )
                self.reload_game()
                first_time = True
                handle = self.handle
                continue

            # 防止被 [没有带xx卡] or 包满 的提示卡死
            find = find_p_in_w(
                raw_w_handle=handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["common"] + "\\战斗\\战斗前_系统提示.png",
                target_tolerance=0.98)
            if find:
                mouse_left_click(
                    handle=handle,
                    x=int(427 * zoom),
                    y=int(353 * zoom))

            # 刷新ui: 状态文本
            print_g(
                text="查找火苗标识物, 等待loading完成",
                player=player,
                garde=1)

            # 循环查找火苗图标 找到战斗开始
            find = loop_find_p_in_w(
                raw_w_handle=handle,
                raw_range=[0, 0, 950, 600],
                target_path=paths["picture"]["common"] + "\\战斗\\战斗中_火苗能量.png",
                target_interval=1,
                target_failed_check=30,
                target_sleep=1,
                click=False,
                click_zoom=zoom)
            if find:
                print_g(
                    text="找到[火苗标识物], 战斗进行中...",
                    player=player,
                    garde=1)
            else:
                print_g(
                    text="30s找不到[火苗标识物]! 进入游戏! 直接reload游戏防止卡死",
                    player=player,
                    garde=2)
                self.reload_game()
                first_time = True
                handle = self.handle
                continue

            # 放人物
            mouse_left_click(
                handle=handle,
                x=int(333 * zoom),
                y=int(333 * zoom))

            # 休息60.5s 等待完成
            time.sleep(59.5)

            # 游戏内退出
            self.action_exit(mode="游戏内退出")


if __name__ == '__main__':
    def f_main():
        faa = FAA(channel="锑食", zoom=1)
        # faa = FAA(channel="深渊之下 | 锑食", zoom=1.25)
        faa.set_config_for_battle(is_group=False, battle_plan_index=0, stage_id="NO-5-1")


    f_main()
