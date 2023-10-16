import os
import json
from time import sleep, time

import numpy as np
from cv2 import imread
from win32gui import FindWindowEx, FindWindow

from function.common.bg_keyboard import key_down_up
from function.common.bg_mouse import mouse_move_to, mouse_left_click
from function.common.bg_screenshot import capture_picture_png
from function.common.bg_screenshot_and_compare_picture import find_p_in_p, loop_find_p_in_p_ml_click
from function.get_root_path import get_root_path


def faa_get_handle(channel):
    """
    解析频道名称 获取句柄, 仅支持360游戏大厅,
    号1：输入你为游戏命名 例如'锑食‘
    号2：输入你命名的角色名 + 空格 + | + 空格 游戏命名。例如：'深渊之下 | 锑食'
    """

    handle = FindWindow("DUIWindow", channel)
    handle = FindWindowEx(handle, None, "TabContentWnd", "")
    handle = FindWindowEx(handle, None, "CefBrowserWindow", "")
    handle = FindWindowEx(handle, None, "Chrome_WidgetWin_0", "")
    handle = FindWindowEx(handle, None, "WrapperNativeWindowClass", "")
    handle = FindWindowEx(handle, None, "NativeWindowClass", "")

    return handle


def create_coordinates(dpi):
    """创建战斗中的 选卡槽和部署位→映射坐标"""
    # 创建卡片位→坐标的映射
    # 为方便理解 使用的卡槽序列号 以及坐标 均为 1 开始
    card_dict = {
        1: [int(224 * dpi), int(50 * dpi)],
        2: [int(277 * dpi), int(50 * dpi)],
        3: [int(330 * dpi), int(50 * dpi)],
        4: [int(383 * dpi), int(50 * dpi)],
        5: [int(436 * dpi), int(50 * dpi)],
        6: [int(489 * dpi), int(50 * dpi)],
        7: [int(542 * dpi), int(50 * dpi)],
        8: [int(595 * dpi), int(50 * dpi)],
        9: [int(648 * dpi), int(50 * dpi)],
        10: [int(701 * dpi), int(50 * dpi)],
        11: [int(754 * dpi), int(50 * dpi)],
        12: [int(807 * dpi), int(50 * dpi)],
        13: [int(860 * dpi), int(50 * dpi)],
        14: [int(913 * dpi), int(50 * dpi)],
        15: [int(913 * dpi), int(118 * dpi)],
        16: [int(913 * dpi), int(186 * dpi)],
        17: [int(913 * dpi), int(254 * dpi)],
    }
    # 坐标是左上为1-1 往右-往下
    cell_dict = {
        '1-1': [int(327 * dpi), int(138 * dpi)],
        '1-2': [int(327 * dpi), int(204 * dpi)],
        '1-3': [int(327 * dpi), int(270 * dpi)],
        '1-4': [int(327 * dpi), int(336 * dpi)],
        '1-5': [int(327 * dpi), int(402 * dpi)],
        '1-6': [int(327 * dpi), int(468 * dpi)],
        '1-7': [int(327 * dpi), int(534 * dpi)],
        '2-1': [int(388 * dpi), int(138 * dpi)],
        '2-2': [int(388 * dpi), int(204 * dpi)],
        '2-3': [int(388 * dpi), int(270 * dpi)],
        '2-4': [int(388 * dpi), int(336 * dpi)],
        '2-5': [int(388 * dpi), int(402 * dpi)],
        '2-6': [int(388 * dpi), int(468 * dpi)],
        '2-7': [int(388 * dpi), int(534 * dpi)],
        '3-1': [int(449 * dpi), int(138 * dpi)],
        '3-2': [int(449 * dpi), int(204 * dpi)],
        '3-3': [int(449 * dpi), int(270 * dpi)],
        '3-4': [int(449 * dpi), int(336 * dpi)],
        '3-5': [int(449 * dpi), int(402 * dpi)],
        '3-6': [int(449 * dpi), int(468 * dpi)],
        '3-7': [int(449 * dpi), int(534 * dpi)],
        '4-1': [int(510 * dpi), int(138 * dpi)],
        '4-2': [int(510 * dpi), int(204 * dpi)],
        '4-3': [int(510 * dpi), int(270 * dpi)],
        '4-4': [int(510 * dpi), int(336 * dpi)],
        '4-5': [int(510 * dpi), int(402 * dpi)],
        '4-6': [int(510 * dpi), int(468 * dpi)],
        '4-7': [int(510 * dpi), int(534 * dpi)],
        '5-1': [int(571 * dpi), int(138 * dpi)],
        '5-2': [int(571 * dpi), int(204 * dpi)],
        '5-3': [int(571 * dpi), int(270 * dpi)],
        '5-4': [int(571 * dpi), int(336 * dpi)],
        '5-5': [int(571 * dpi), int(402 * dpi)],
        '5-6': [int(571 * dpi), int(468 * dpi)],
        '5-7': [int(571 * dpi), int(534 * dpi)],
        '6-1': [int(632 * dpi), int(138 * dpi)],
        '6-2': [int(632 * dpi), int(204 * dpi)],
        '6-3': [int(632 * dpi), int(270 * dpi)],
        '6-4': [int(632 * dpi), int(336 * dpi)],
        '6-5': [int(632 * dpi), int(402 * dpi)],
        '6-6': [int(632 * dpi), int(468 * dpi)],
        '6-7': [int(632 * dpi), int(534 * dpi)],
        '7-1': [int(693 * dpi), int(138 * dpi)],
        '7-2': [int(693 * dpi), int(204 * dpi)],
        '7-3': [int(693 * dpi), int(270 * dpi)],
        '7-4': [int(693 * dpi), int(336 * dpi)],
        '7-5': [int(693 * dpi), int(402 * dpi)],
        '7-6': [int(693 * dpi), int(468 * dpi)],
        '7-7': [int(693 * dpi), int(534 * dpi)],
        '8-1': [int(754 * dpi), int(138 * dpi)],
        '8-2': [int(754 * dpi), int(204 * dpi)],
        '8-3': [int(754 * dpi), int(270 * dpi)],
        '8-4': [int(754 * dpi), int(336 * dpi)],
        '8-5': [int(754 * dpi), int(402 * dpi)],
        '8-6': [int(754 * dpi), int(468 * dpi)],
        '8-7': [int(754 * dpi), int(534 * dpi)],
        '9-1': [int(815 * dpi), int(138 * dpi)],
        '9-2': [int(815 * dpi), int(204 * dpi)],
        '9-3': [int(815 * dpi), int(270 * dpi)],
        '9-4': [int(815 * dpi), int(336 * dpi)],
        '9-5': [int(815 * dpi), int(402 * dpi)],
        '9-6': [int(815 * dpi), int(468 * dpi)],
        '9-7': [int(815 * dpi), int(534 * dpi)],
    }
    return card_dict, cell_dict


class FAA:
    def __init__(self, channel="锑食", dpi=1.5, is_use_key=True, is_auto_battle=True):

        # 获取窗口句柄
        self.handle = faa_get_handle(channel)

        # DPI
        self.dpi = dpi  # float 1.0 即百分百

        # 是否使用钥匙和卡片
        self.is_use_key = is_use_key
        self.is_auto_battle = is_auto_battle

        # 资源文件路径
        self.path_root = get_root_path()

        self.path_logs = self.path_root + "\\logs"
        self.path_p = self.path_root + "\\resource\\picture"

        self.path_p_common = self.path_p + "\\common"
        self.path_p_stage = self.path_p + "\\stage"
        self.path_p_guild_task = self.path_p + "\\task_guild"
        self.path_p_spouse_task = self.path_p + "\\task_spouse"
        self.path_p_ready_check_stage = self.path_p + "\\stage_ready_check"

        # 关卡名称集 从资源文件夹自动获取, 资源文件命名格式：关卡名称.png
        self.ready_check_stage = []
        for i in os.listdir(self.path_p_ready_check_stage):
            if i.find(".png") != -1:
                self.ready_check_stage.append(i.split(".")[0])

        # 计算关卡内的卡牌 和 格子位置
        self.battle_card, self.battle_cell = create_coordinates(self.dpi)

    def get_stage_name(self):
        stage_id = "Unknown"  # 默认名称
        img1 = capture_picture_png(self.handle)[468:484, 383:492, :3]
        for i in self.ready_check_stage:
            if np.all(img1 == imread(self.path_p_ready_check_stage + "\\" + i + ".png", 1)):
                stage_id = i
                break
        return stage_id

    def get_task(self, target: str):
        """获取公会任务列表 [["地图1","带卡1"],...]"""
        # 点跳转
        mouse_left_click(self.handle, int(870 * self.dpi), int(560 * self.dpi), sleep_time=1)

        # 点任务
        if target == "guild":
            # 公会任务 guild
            mouse_left_click(self.handle, int(870 * self.dpi), int(263 * self.dpi), sleep_time=1)
        else:
            # 情侣任务 spouse
            mouse_left_click(self.handle, int(870 * self.dpi), int(300 * self.dpi), sleep_time=1)

        # 读取
        task_list = []
        if target == "guild":
            # 公会任务 guild
            path = self.path_p_guild_task
            for i in range(7):
                for j in os.listdir(path + "\\" + str(i + 1) + "\\"):
                    find_p = find_p_in_p(handle=self.handle,
                                         target_path=path + "\\" + str(i + 1) + "\\" + j,
                                         tolerance=0.999)
                    if find_p:
                        task_list.append([j.split("_")[0], j.split("_")[2].split(".")[0]])
        else:
            # 情侣任务 spouse
            path = self.path_p_spouse_task
            for j in os.listdir(path + "\\"):
                if find_p_in_p(self.handle, path + "\\" + j):
                    task_list.append([j.split(".")[0]])

        # 关闭公会任务列表(红X)
        self.goto_exit(exit_mode=2)

        return task_list

    def goto_stage(self, stage: str, main_character: bool, mt_first_time: bool = False, lock_p2: bool = False):
        """
        只要右上能看到地球 就可以到目标关卡
        Args:
            stage: 关卡代号 详情见资源文件中的 地图名称 格式说明.md
            main_character: 主要角色。单角色时 为真；双角色时 创建房间的角色为真；
            mt_first_time: 魔塔关卡下 是否是第一次打(第一次塔需要进塔 第二次只需要选关卡序号)
            lock_p2: 是否锁住p2位置
        """
        # 拆成数组["关卡类型","地图id","关卡id"]
        s_type = stage.split('-')[0]
        s_map = stage.split('-')[1]
        s_stage = stage.split('-')[2]

        def click_world_map():
            if not loop_find_p_in_p_ml_click(handle=self.handle,
                                             target=self.path_p_common + "\\Above_Map.png",
                                             change_per=self.dpi,
                                             sleep_time=1,
                                             click=True,
                                             failed_check_time=10):
                print("10s没有找到右上大地图...请找个符合要求的位置重启脚本...")

        def change_activity_list(serial_num: int):
            if serial_num == 1:
                if find_p_in_p(self.handle, self.path_p_common + "\\Above_JuBao.png"):
                    mouse_left_click(self.handle, int(785 * self.dpi), int(30 * self.dpi), sleep_time=0.5)

            if serial_num == 2:
                if not find_p_in_p(self.handle, self.path_p_common + "\\Above_JuBao.png"):
                    mouse_left_click(self.handle, int(785 * self.dpi), int(30 * self.dpi), sleep_time=0.5)

        def change_to_region():
            mouse_left_click(self.handle, int(820 * self.dpi), int(85 * self.dpi), sleep_time=0.5)
            # 一 区
            mouse_left_click(self.handle, int(720 * self.dpi), int(85 * self.dpi), sleep_time=0.5)
            # 二 区
            # mouse_left_click(self.handle, int(720 * self.dpi), int(108 * self.dpi), sleep_time=1)

        def main_no():
            # 防止被活动列表遮住
            change_activity_list(2)

            # 点击世界地图
            click_world_map()

            # 点击对应的地图
            my_path = self.path_p_stage + "\\NO-" + s_map + ".png"
            loop_find_p_in_p_ml_click(handle=self.handle,
                                      target=my_path,
                                      change_per=self.dpi,
                                      sleep_time=2,
                                      click=True)

            # 切换到一号区
            change_to_region()

            # 仅限主角色创建关卡
            if main_character:
                # 选择关卡
                my_path = self.path_p_stage + "\\" + stage + ".png"
                loop_find_p_in_p_ml_click(handle=self.handle,
                                          target=my_path,
                                          change_per=self.dpi,
                                          sleep_time=0.5,
                                          click=True)

                # 创建队伍
                my_path = self.path_p_common + "\\" + "BattleBefore_CreateStage.png"
                loop_find_p_in_p_ml_click(handle=self.handle,
                                          target=my_path,
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
                loop_find_p_in_p_ml_click(handle=self.handle,
                                          target=my_path,
                                          change_per=self.dpi,
                                          sleep_time=2,
                                          click=True)

                # 选择二号区
                change_to_region()

            if main_character and mt_first_time:
                # 进入魔塔
                my_path = self.path_p_stage + "\\MT.png"
                loop_find_p_in_p_ml_click(handle=self.handle,
                                          target=my_path,
                                          change_per=self.dpi,
                                          sleep_time=2,
                                          click=True)

                # 根据模式进行选择
                my_dict = {"1": 46, "2": 115, "3": 188}
                mouse_left_click(self.handle, int(my_dict[s_map] * self.dpi), int(66 * self.dpi), sleep_time=0.5)

            if main_character:
                # 选择了密室
                if s_map == "3":
                    my_path = self.path_p_stage + "\\" + stage + ".png"
                    loop_find_p_in_p_ml_click(handle=self.handle,
                                              target=my_path,
                                              change_per=self.dpi,
                                              sleep_time=0.3,
                                              click=True)
                # 选择了单双人爬塔
                else:
                    # 等于0则为爬塔模式 即选择最高层
                    if s_stage != 0:
                        # 到魔塔最低一层
                        mouse_left_click(self.handle, int(47 * self.dpi), int(579 * self.dpi), sleep_time=0.3)
                        # 向右到对应位置
                        my_left = int((int(s_stage) - int(s_stage) % 15) / 15)
                        for i in range(my_left):
                            mouse_left_click(self.handle, int(152 * self.dpi), int(577 * self.dpi), sleep_time=0.3)
                        # 点击对应层数
                        my_up = int(s_stage) % 15
                        my_y = int(572 - (30.8 * my_up))
                        mouse_left_click(self.handle, int(110 * self.dpi), int(my_y * self.dpi), sleep_time=0.3)

                # 进入关卡
                my_path = self.path_p_common + "\\" + "BattleBefore_SelectStage_MagicTower_Start.png"
                loop_find_p_in_p_ml_click(handle=self.handle,
                                          target=my_path,
                                          change_per=self.dpi,
                                          sleep_time=1,
                                          click=True)

        def main_cs():
            if not main_character:
                print("跨服仅支持单人！")
            else:
                # 防止活动列表不在
                change_activity_list(1)

                # 点击进入跨服副本界面
                my_path = self.path_p_stage + "\\CS.png"
                loop_find_p_in_p_ml_click(handle=self.handle,
                                          target=my_path,
                                          change_per=self.dpi,
                                          sleep_time=2,
                                          click=True)

                # 创建房间
                mouse_left_click(self.handle, int(853 * self.dpi), int(553 * self.dpi), sleep_time=0.5)

                # 选择地图
                my_x = int(s_map) * 101 - 36
                mouse_left_click(self.handle, int(my_x * self.dpi), int(70 * self.dpi), sleep_time=1)

                # 选择关卡并创建房间
                my_dict = {
                    "1": [176, 286],
                    "2": [401, 286],
                    "3": [629, 286],
                    "4": [855, 286],
                    "5": [176, 507],
                    "6": [401, 507],
                    "7": [629, 507],
                    "8": [855, 507]}
                mouse_left_click(
                    self.handle,
                    int(my_dict[s_stage][0] * self.dpi),
                    int(my_dict[s_stage][1] * self.dpi),
                    sleep_time=1)

        def main_or():
            # 防止活动列表不在
            change_activity_list(1)

            # 点击进入悬赏副本
            my_path = self.path_p_stage + "\\OR.png"
            loop_find_p_in_p_ml_click(handle=self.handle,
                                      target=my_path,
                                      change_per=self.dpi,
                                      sleep_time=2,
                                      click=True)

            # 根据模式进行选择
            my_dict = {"1": 260, "2": 475, "3": 710}
            mouse_left_click(self.handle, int(my_dict[s_map] * self.dpi), int(411 * self.dpi), sleep_time=2)

            # 切换到一号区
            change_to_region()

            # 仅限主角色
            if main_character:
                # 创建队伍
                mouse_left_click(self.handle, int(583 * self.dpi), int(500 * self.dpi), sleep_time=0.5)

        def main_all():
            if s_type == "NO":
                main_no()
            elif s_type == "MT":
                main_mt()
            elif s_type == "CS":
                main_cs()
            elif s_type == "OR":
                main_or()
            else:
                print("请输入正确的关卡名称！")
            if lock_p2:
                mouse_left_click(self.handle, int(270 * self.dpi), int(150 * self.dpi), sleep_time=0.5)

        main_all()

    def goto_exit(self, exit_mode: int):
        """打完后是否退出 0-不退出  1-右下回退到上一级  2-右上红叉  3-直接到竞技岛"""
        if exit_mode == 1:
            mouse_left_click(self.handle, int(918 * self.dpi), int(558 * self.dpi), sleep_time=1)

        if exit_mode == 2:
            my_path = self.path_p_common + "\\BattleBefore_Exit_X.png"
            loop_find_p_in_p_ml_click(handle=self.handle, target=my_path, change_per=self.dpi, sleep_time=1, click=True)

        if exit_mode == 3:
            mouse_left_click(self.handle, int(871 * self.dpi), int(558 * self.dpi), sleep_time=0.3)
            mouse_left_click(self.handle, int(871 * self.dpi), int(386 * self.dpi), sleep_time=0.7)

    # 战斗中函数
    def solve_cell_all_card(self, stage_name: str, is_main: bool = True, task_card: int = 0):
        """计算所有卡片的部署方案"""

        def get_stage_info_from_json(f_stage_name):
            """读取文件中是否存在预设"""
            with open(self.path_p + "//dict_stage.json", "r", encoding="UTF-8") as file:
                f_stage_s = f_stage_name.split("-")
                f_my_dict = json.load(file)
                # 初始化
                f_stage_info = {"name": " ",
                                "mat_card": 1,
                                "mat_cell": ["1-1", "1-2", "1-3", "1-4", "1-5", "1-6", "1-7",
                                             "2-1", "2-2", "2-3", "2-4", "2-5", "2-6", "2-7",
                                             "3-1", "3-2", "3-3", "3-4", "3-5", "3-6", "3-7",
                                             "4-1", "4-2", "4-3", "4-4", "4-5", "4-6", "4-7",
                                             "5-1", "5-2", "5-3", "5-4", "5-5", "5-6", "5-7",
                                             "6-1", "6-2", "6-3", "6-4", "6-5", "6-6", "6-7",
                                             "7-1", "7-2", "7-3", "7-4", "7-5", "7-6", "7-7",
                                             "8-1", "8-2", "8-3", "8-4", "8-5", "8-6", "8-7",
                                             "9-1", "9-2", "9-3", "9-4", "9-5", "9-6", "9-7"],
                                "shovel": []}
                # 如果找到预设
                if f_stage_s[0] in f_my_dict.keys():
                    if f_stage_s[1] in f_my_dict[f_stage_s[0]].keys():
                        if f_stage_s[2] in f_my_dict[f_stage_s[0]][f_stage_s[1]].keys():
                            f_stage_info = f_my_dict[f_stage_s[0]][f_stage_s[1]][f_stage_s[2]]
            return f_stage_info

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

        def solve_one_card_main(dic_cell_all, f_task_card, f_is_main):
            """计算 主要战斗卡 仅大号携带 6张"""
            f_dic_cell_main = {

                3: {  # 生产卡
                    "location": ["2-1", "2-2", "2-3", "2-5", "2-6", "2-7",
                                 "4-1", "4-2", "4-3", "4-4", "4-5", "4-6", "4-7"],
                    "cooldown": 7.0,
                    "last_use_time": 0,
                    "last_use_one": 0
                },
                5: {  # 海星
                    "location": ["5-4", "5-3", "5-5", "5-2", "5-6", "5-1", "5-7",
                                 "1-4",
                                 "7-1", "7-4", "7-7",
                                 "8-4", "8-3", "8-5", "8-2", "8-6", "8-1", "8-7",
                                 "9-4", "9-3", "9-5", "9-2", "9-6", "9-1", "9-7"],
                    "cooldown": 7.0,
                    "last_use_time": 0,
                    "last_use_one": 0
                },
                4: {  # 布丁
                    "location": ["1-1", "1-2", "1-3", "2-4", "1-5", "1-6", "1-7"],
                    "cooldown": 10.0,
                    "last_use_time": 0,
                    "last_use_one": 0
                },
                6: {  # 糖葫芦
                    "location": ["3-1", "3-2", "3-3", "3-4", "3-5", "3-6", "3-7"],
                    "cooldown": 7.0,
                    "last_use_time": 0,
                    "last_use_one": 0
                },
                7: {  # 狮子座
                    "location": ["7-3", "7-5", "7-2", "7-6"],
                    "cooldown": 35.0,
                    "last_use_time": 0,
                    "last_use_one": 0
                },
                8: {  # 瓜皮
                    "location": ["9-1", "9-2", "9-3", "9-4", "9-5", "9-6", "9-7"],
                    "cooldown": 15.0,
                    "last_use_time": 0,
                    "last_use_one": 0
                },
                11: {  # 油灯
                    "location": ["6-7"],
                    "cooldown": 15.0,
                    "last_use_time": 0,
                    "last_use_one": 0
                }
            }

            # 如果没有任务卡 多一行小火
            if f_task_card == 0:
                f_dic_cell_main[3]["location"] = ["2-1", "2-2", "2-3", "2-5", "2-6", "2-7",
                                                  "4-1", "4-2", "4-3", "4-4", "4-5", "4-6", "4-7",
                                                  "6-1", "6-2", "6-3", "6-4", "6-5", "6-6"]

            # 仅主要角色 放战斗卡
            if f_is_main:
                dic_cell_all = {**dic_cell_all, **f_dic_cell_main}
            return dic_cell_all, f_dic_cell_main

        def solve_one_card_mat(dic_cell_all, stage_info, f_is_main):
            """承载卡 2张"""
            if stage_info["mat_card"] != 0:
                # 预设中 该关卡有垫子 或采用了默认
                dic_cell_mat = {  # 使用对应卡 并用其预设范围和其他卡的交集铺场
                    stage_info["mat_card"]: {  # 承载卡
                        "location": stage_info["mat_cell"],
                        "cooldown": 7.0,
                        "last_use_time": 0,
                        "last_use_one": 0
                    }
                }
                # 不是主要角色 就颠倒数组
                if not f_is_main:
                    dic_cell_mat[stage_info["mat_card"]]["location"] = dic_cell_mat[stage_info["mat_card"]]["location"][::-1]
            else:
                # 预设中 该关卡无垫子
                dic_cell_mat = {}
            # 加入数组
            dic_cell_all = {**dic_cell_all, **dic_cell_mat}
            return dic_cell_all

        def solve_one_card_task(dic_cell_all, f_task_card):
            # 任务卡 大号小号开始位置不同 任务卡id = 0 则为没有
            if f_task_card > 0:
                task_card_id = 2 + f_task_card
                if is_main:
                    task_card_id = 8 + f_task_card
                dic_cell_task = {
                    task_card_id: {
                        "location": ["6-1", "6-2", "6-3", "6-4", "6-5", "6-6"],
                        "cooldown": 7.0,
                        "last_use_time": 0,
                        "last_use_one": 0
                    }
                }
                # 加入数组
                dic_cell_all = {**dic_cell_all, **dic_cell_task}

            return dic_cell_all

        def solve_shovel(stage_info):
            """铲子位置 """
            list_shovel = stage_info["shovel"]
            return list_shovel

        def solve_f_main():
            """
            Return:卡片的部署方案字典
                example = {
                    卡格序数 int: {
                        "location": ["x-y","x-y","x-y",...],
                        "cooldown": float,
                        "last_use_time": float 记录上次使用卡的时间 配合cd来限制放卡间隔,
                        "last_use_one": int 标记循环时该卡放到了哪个位置。
                    },
                }
            """
            # 是否存在配置数组
            stage_info = get_stage_info_from_json(f_stage_name=stage_name)
            # 初始化字典
            dic_cell_all = {}
            # 调用计算战斗卡
            dic_cell_all, dic_cell_main = solve_one_card_main(dic_cell_all=dic_cell_all,
                                                              f_task_card=task_card,
                                                              f_is_main=is_main)
            # 调用计算承载卡
            dic_cell_all = solve_one_card_mat(dic_cell_all=dic_cell_all,
                                              stage_info=stage_info,
                                              f_is_main=is_main)
            # 调用计算任务卡
            dic_cell_all = solve_one_card_task(dic_cell_all=dic_cell_all,
                                               f_task_card=task_card)
            # 调用计算铲子卡
            list_shovel = solve_shovel(stage_info=stage_info)
            return dic_cell_all, list_shovel

        return solve_f_main()

    def battle_use_player(self, num_cell):
        mouse_left_click(self.handle, self.battle_cell[num_cell][0], self.battle_cell[num_cell][1])

    def battle_use_player_sometimes(self):
        for i in ["2-4", "3-4", "4-4", "5-4", "4-1", "4-2", "4-3"]:
            self.battle_use_player(i)

    def battle_use_card(self, num_card: int, num_cell: str, click_space=True):
        """
        Args:
            num_card: 使用的卡片的序号
            num_cell: 使用的卡片对应的格子 从左上开始 "1-1" to "9-7"
            click_space:  是否点一下空白地区防卡住
        """
        # 注 美食大战老鼠中 放卡动作 需要按下一下 然后拖动 然后按下并松开 才能完成 整个动作
        mouse_left_click(self.handle, self.battle_card[num_card][0], self.battle_card[num_card][1],
                         interval_time=0.005, sleep_time=0.005)
        mouse_left_click(self.handle, self.battle_cell[num_cell][0], self.battle_cell[num_cell][1],
                         interval_time=0.005, sleep_time=0.005)
        # 点一下空白
        if click_space:
            self.battle_click_space()

    def battle_click_space(self):
        """战斗中点空白"""
        mouse_move_to(self.handle, 200, 200)
        mouse_left_click(self.handle, 200, 200, interval_time=0.03, sleep_time=0.05)

    def battle_use_shovel(self, position: list = None):
        """
        用铲子
        Args:
            position: 放哪些格子
        """
        if position is None:
            position = []
        for target in position:
            key_down_up(self.handle, "1")
            mouse_left_click(self.handle, self.battle_cell[target][0], self.battle_cell[target][1])

    def battle_use_key(self):
        if self.is_use_key:
            if find_p_in_p(self.handle, self.path_p_common + "\\Battle_NextNeed.png"):
                mouse_left_click(self.handle, int(427 * self.dpi), int(360 * self.dpi))

    def battle_use_card_loop_0(self, opt_battle, opt_screen_shoot):
        """循环方式0 根据每个卡的cd依次放置"""

        # 遍历 按冷却是否完成 依照预订位置 放卡
        while True:

            # 仅在确定要自动战斗后使用
            if self.is_auto_battle:

                # 遍历每一张卡
                for i in opt_battle:

                    # 使用间隔>该卡cd
                    if time() - opt_battle[i]["last_use_time"] > opt_battle[i]["cooldown"]:

                        # 读取本次要放的卡片位置
                        my_card_str = opt_battle[i]["location"][opt_battle[i]["last_use_one"]]

                        # 防止误触
                        if my_card_str == "2-4" or my_card_str == "2-5" or my_card_str == "2-6" or my_card_str == "2-7":
                            self.battle_use_key()

                        # 完整放卡动作
                        self.battle_use_card(num_card=i, num_cell=my_card_str, click_space=True)

                        # 计时 + 记住已到达的序列位置
                        opt_battle[i]["last_use_time"] = time()
                        opt_battle[i]["last_use_one"] += 1

                        # 位置到了最后 回到最开始
                        if opt_battle[i]["last_use_one"] == len(opt_battle[i]["location"]):
                            opt_battle[i]["last_use_one"] = 0

            # 每隔一段时间 尝试使用钥匙继续战斗
            if time() - opt_screen_shoot["last_use_time"] > opt_screen_shoot["cooldown"]:

                # 尝试使用钥匙继续战斗
                self.battle_use_key()

                # 寻找战斗结束字样结束战斗循环
                if find_p_in_p(self.handle, self.path_p_common + "\\BattleEnd_Loot.png"):
                    break

                # 计时
                opt_screen_shoot["last_use_time"] = time()

            # 遍历间隔
            sleep(0.1)

    def battle_use_card_loop_1(self, opt_battle):
        """循环方式1 每一个卡都先在其对应的全部的位置放一次,再放下一张(每轮开始位置+1)"""
        # 用flag值来停止循环
        battle_flag = True

        while battle_flag:

            # 计时每轮开始的时间
            time_round_begin = time()

            # 遍历每一张卡
            for i in opt_battle:

                # 启动了自动战斗
                if self.is_auto_battle:
                    # 点击 选中卡片
                    mouse_left_click(self.handle,
                                     self.battle_card[i][0],
                                     self.battle_card[i][1],
                                     interval_time=0.03,
                                     sleep_time=0.03)

                    # 遍历该卡每一个可以放的位置
                    for j in opt_battle[i]["location"]:

                        # 防止误触
                        if j == "2-4" or j == "2-5" or j == "2-6" or j == "2-7":
                            self.battle_use_key()

                        # 点击 放下卡片
                        mouse_left_click(self.handle,
                                         self.battle_cell[j][0],
                                         self.battle_cell[j][1],
                                         interval_time=0.03,
                                         sleep_time=0.03)

                    # 放完一张卡后 在位置数组里 将第一个要放的移到最后
                    opt_battle[i]["location"].append(opt_battle[i]["location"][0])
                    opt_battle[i]["location"].remove(opt_battle[i]["location"][0])

                    # 放卡后点一下
                    self.battle_click_space()

                # 尝试使用一下钥匙
                self.battle_use_key()

                # 尝试找到战斗结束的迹象 来改变flag 并中断放卡循环
                if find_p_in_p(self.handle, self.path_p_common + "\\BattleEnd_Loot.png"):
                    battle_flag = False
                    break

            time_spend = time() - time_round_begin

            # 如果一轮间隔不到7.3s 休息一下等待常规冷却
            if time_spend < 7.1:

                # 休息一下
                sleep(7.1 - time_spend)

                # 尝试使用一下钥匙
                self.battle_use_key()

                # 尝试找到战斗结束的迹象 来改变flag
                if find_p_in_p(self.handle, self.path_p_common + "\\BattleEnd_Loot.png"):
                    battle_flag = False

    def battle_normal(self, stage_name: str, is_main: bool = True, task_card: int = 0, battle_mode: int = 1):
        """
        战斗中放卡的函数
        Args:
            stage_name: 关卡名称 用于适配对应的承载卡
            is_main:
            task_card:
            battle_mode: 0 cd模式;1 遍历模式
        """

        opt_screen_shoot = {"cooldown": 0.5, "last_use_time": 0.0, }
        opt_battle, list_shovel = self.solve_cell_all_card(stage_name=stage_name, is_main=is_main, task_card=task_card)

        # 放人物
        self.battle_use_player_sometimes()

        # 铲自带的卡
        self.battle_use_shovel(position=list_shovel)

        # 战斗循环
        if battle_mode == 0:
            # 0 cd模式 按照cd顺序放卡 布阵快 补阵慢 容错低 易出现脑瘫操作
            self.battle_use_card_loop_0(opt_battle=opt_battle, opt_screen_shoot=opt_screen_shoot)
        else:
            # 1 遍历模式 布阵慢 补阵快 性能开销略大
            self.battle_use_card_loop_1(opt_battle=opt_battle)

    def battle_skill(self):
        # 放人
        self.battle_use_player("5-4")

        # 计算目标位置 1-14
        cell_list = []
        for i in range(2):
            for j in range(9):
                cell_list.append(str(j + 1) + "-" + str(i + 2))

        # 常规放卡
        for k in range(13):
            self.battle_use_card(k + 1, cell_list[k], click_space=False)
            sleep(0.07)

        # 叠加放卡
        # for k in range(3):
        #     msdzls.battle_use_card(k*2 + 1 + 8, cell_list[k + 8], click_space=False)
        #     sleep(0.15)
        #     msdzls.battle_use_card(k*2 + 2 + 8, cell_list[k + 8], click_space=False)
        #     sleep(0.05)

        # 退出关卡
        mouse_left_click(self.handle, int(920 * self.dpi), int(580 * self.dpi), 0.01, 0.05)
        mouse_left_click(self.handle, int(920 * self.dpi), int(580 * self.dpi), 0.01, 0.05)
        # 确定退出
        mouse_left_click(self.handle, int(449 * self.dpi), int(382 * self.dpi), 0.01, 0.2)


if __name__ == '__main__':
    # 游戏[固定]分辨率 950* 596 大约16:10
    # 截图[不会]缩放, 点击位置[需要]缩放, 这为制作脚本提供了极大便利

    def main():
        faa = FAA()
        faa.goto_stage("OR-3-0", True)


    main()
