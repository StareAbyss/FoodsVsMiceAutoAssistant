import copy
import json
import os
import time

import cv2
import numpy as np

from function.battle.get_position_in_battle import get_position_card_deck_in_battle, get_position_card_cell_in_battle
from function.common.bg_p_match import match_p_in_w, loop_match_p_in_w, loop_match_ps_in_w
from function.common.bg_p_screenshot import capture_picture_png
from function.core.FAAActionInterfaceJump import FAAActionInterfaceJump
from function.core.FAAActionQuestReceiveRewards import FAAActionQuestReceiveRewards
from function.core.FAABattle import Battle
from function.core.analyzer_of_loot_logs import matchImage
from function.globals.get_paths import PATHS
from function.globals.init_resources import RESOURCE_P
from function.globals.log import CUS_LOGGER
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.gat_handle import faa_get_handle
from function.scattered.get_list_battle_plan import get_list_battle_plan
from function.scattered.read_json_to_stage_info import read_json_to_stage_info


class FAA:
    """
    FAA类是项目的核心类
    用于封装 [所有对单个游戏窗口进行执行的操作]
    """

    def __init__(self, channel="锑食", player=1, character_level=1,
                 is_auto_battle=True, is_auto_pickup=False, random_seed=0,
                 signal_dict=None):

        # 获取窗口句柄

        self.channel = channel
        self.handle = faa_get_handle(channel=self.channel, mode="flash")
        self.handle_browser = faa_get_handle(channel=self.channel, mode="browser")
        self.handle_360 = faa_get_handle(channel=self.channel, mode="360")

        # 好用的信号
        self.signal_dict = signal_dict
        self.signal_print_to_ui = self.signal_dict["print_to_ui"]
        self.signal_dialog = self.signal_dict["dialog"]
        self.signal_end = self.signal_dict["end"]

        # 随机种子
        self.random_seed = random_seed

        # 角色|等级|是否使用钥匙|卡片|收集战利品
        self.player = player
        self.character_level = character_level
        self.is_auto_battle = is_auto_battle
        self.is_auto_pickup = is_auto_pickup

        # 每次战斗都不一样的参数 使用内部函数调用更改
        self.stage_info = None
        self.is_main = None
        self.is_group = None
        self.is_use_key = None
        self.deck = None
        self.quest_card = None
        self.ban_card_list = None
        self.battle_plan_0 = None  # 读取自json的初始战斗方案
        self.battle_mode = None

        # 初始化战斗中 卡片位置 字典 bp -> battle position
        self.bp_card = None

        # 调用战斗中 格子位置 字典 bp -> battle position
        self.bp_cell = get_position_card_cell_in_battle()

        # 经过处理后的战斗方案, 由战斗类相关动作函数直接调用, 其中的各种操作都包含坐标
        self.battle_plan_1 = {}

        # 承载卡/冰沙/坤的位置
        self.mat_card_positions = None  # list [{},{},...]
        self.smoothie_position = None  # dict {}
        self.kun_position = None  # dict {} 也用于标记本场战斗是否需需要激活坤函数

        """被拆分为子实例的模块"""

        # 战斗实例 其中绝大多数方法需要在set_config_for_battle后使用
        self.faa_battle = Battle(faa=self)

        # 领取奖励实例 基本只调用一个main方法
        self.object_action_quest_receive_rewards = FAAActionQuestReceiveRewards(faa=self)

        # 界面跳转实例 用于实现
        self.object_action_interface_jump = FAAActionInterfaceJump(faa=self)

    def print_debug(self, text, player=None):
        if not player:
            player = self.player
        CUS_LOGGER.debug("[{}P] {}".format(player, text))

    def print_info(self, text, player=None):
        if not player:
            player = self.player
        CUS_LOGGER.info("[{}P] {}".format(player, text))

    def print_warning(self, text, player=None):
        if not player:
            player = self.player
        CUS_LOGGER.warning("[{}P] {}".format(player, text))

    def print_error(self, text, player=None):
        if not player:
            player = self.player
        CUS_LOGGER.error("[{}P] {}".format(player, text))

    """界面跳转动作的接口"""

    def action_exit(self, mode: str = "None", raw_range=None):
        return self.object_action_interface_jump.exit(mode=mode, raw_range=raw_range)

    def action_top_menu(self, mode: str):
        return self.object_action_interface_jump.top_menu(mode=mode)

    def action_bottom_menu(self, mode: str):
        return self.object_action_interface_jump.bottom_menu(mode=mode)

    def action_change_activity_list(self, serial_num: int):
        return self.object_action_interface_jump.change_activity_list(serial_num=serial_num)

    def action_goto_map(self, map_id):
        return self.object_action_interface_jump.goto_map(map_id=map_id)

    def action_goto_stage(self, mt_first_time: bool = False):
        return self.object_action_interface_jump.goto_stage(mt_first_time=mt_first_time)

    """"对flash游戏界面或自身参数的最基础 [检测]"""

    def check_level(self):
        """检测角色等级和关卡等级(调用于输入关卡信息之后)"""
        if self.character_level < self.stage_info["level"]:
            return False
        else:
            return True

    def screen_check_server_boom(self):
        """
        检测是不是炸服了
        :return: bool 炸了 True 没炸 False
        """
        find = loop_match_ps_in_w(
            raw_w_handle=self.handle,
            target_opts=[
                {
                    "raw_range": [350, 275, 600, 360],
                    "target_path": RESOURCE_P["error"]["登录超时.png"],
                    "target_tolerance": 0.999
                },
                {
                    "raw_range": [350, 275, 600, 360],
                    "target_path": RESOURCE_P["error"]["断开连接.png"],
                    "target_tolerance": 0.999
                },
                {
                    "raw_range": [350, 275, 600, 360],
                    "target_path": RESOURCE_P["error"]["Flash爆炸.png"],
                    "target_tolerance": 0.999
                }
            ],
            target_return_mode="or",
            target_failed_check=1,
            target_interval=0.2)

        return find

    def screen_get_stage_name(self):
        """
        在关卡备战界面 获得关卡名字 该函数未完工
        """
        stage_id = "Unknown"  # 默认名称
        img1 = capture_picture_png(handle=self.handle, raw_range=[0, 0, 950, 600])[468:484, 383:492, :3]
        # 关卡名称集 从资源文件夹自动获取, 资源文件命名格式：关卡名称.png
        stage_text_in_ready_check = []

        for key, img in RESOURCE_P["ready_check_stage"].items():
            stage_text_in_ready_check.append(key.split(".")[0])

        for i in stage_text_in_ready_check:
            img_tar = RESOURCE_P["ready_check_stage"]["{}.png".format(i)]
            if np.all(img1 == img_tar):
                # 图片完全一致
                stage_id = i
                break

        return stage_id

    """调用输入关卡配置和战斗配置, 在战斗前必须进行该操作"""

    def set_config_for_battle(
            self,
            stage_id="NO-1-1", is_group=False, is_main=True, is_use_key=True,
            deck=1, quest_card="None", ban_card_list=None,
            battle_plan_index=0):
        """
        :param is_group: 是否组队
        :param is_main: 是否是主要账号(单人为True 双人房主为True)
        :param is_use_key: 是否使用钥匙
        :param deck:
        :param quest_card:
        :param ban_card_list:
        :param battle_plan_index: 战斗方案的索引
        :param stage_id: 关卡的id
        :return:
        """

        if ban_card_list is None:
            ban_card_list = []

        self.is_main = is_main
        self.is_group = is_group
        self.is_use_key = is_use_key
        self.deck = deck
        self.quest_card = quest_card
        self.ban_card_list = ban_card_list

        def read_json_to_battle_plan():
            battle_plan_list = get_list_battle_plan(with_extension=True)
            battle_plan_path = "{}\\{}".format(
                PATHS["battle_plan"],
                battle_plan_list[battle_plan_index]
            )
            with open(battle_plan_path, "r", encoding="UTF-8") as file:
                return json.load(file)

        self.battle_plan_0 = read_json_to_battle_plan()
        self.stage_info = read_json_to_stage_info(stage_id)

    """战斗开始时的初始化函数"""

    def init_mat_card_position(self):
        """
        根据关卡名称和可用承载卡，以及游戏内识图到的承载卡取交集，返回承载卡的x-y坐标
        :return: [[x1, y1], [x2, y2],...]
        """
        stage_info = copy.deepcopy(self.stage_info)

        # 本关可用的所有承载卡
        mat_available_list = stage_info["mat_card"]

        # 筛选出所有有图片资源的卡片包含变种
        mat_resource_exist_list = []
        for mat_card in mat_available_list:
            for i in range(6):
                new_card = f"{mat_card}-{i}.png"
                if new_card in RESOURCE_P["card"]["战斗"].keys():
                    mat_resource_exist_list.append(new_card)

        position_list = []

        # 查找对应卡片坐标 重复3次
        for i in range(3):

            for mat_card in mat_resource_exist_list:
                # 需要使用0.99相似度参数 相似度阈值过低可能导致一张图片被识别为两张卡
                find = match_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=RESOURCE_P["card"]["战斗"][mat_card],
                    target_tolerance=0.99)
                if find:
                    position_list.append([int(find[0]), int(find[1])])
                    # 从资源中去除已经找到的卡片
                    mat_resource_exist_list.remove(mat_card)

            # 防止卡片正好被某些特效遮挡, 所以等待一下
            time.sleep(0.1)

        # 根据坐标位置，判断对应的卡id
        mat_card_list = []
        for position in position_list:
            for card_id, card_xy_list in self.bp_card.items():
                x1 = card_xy_list[0] - 45
                y1 = card_xy_list[1] - 64
                x2 = card_xy_list[0] + 8
                y2 = card_xy_list[1] + 6
                if x1 <= position[0] <= x2 and y1 <= position[1] <= y2:
                    mat_card_list.append({"id": card_id, "location_from": position})
                    break

        # 输出
        self.mat_card_positions = mat_card_list

    def init_smoothie_card_position(self):

        self.print_debug(text="战斗中识图查找冰沙位置, 开始")

        # 初始化为None
        self.smoothie_position = None

        position = None
        # 查找对应卡片坐标 重复3次
        for i in range(3):
            for j in ["2", "5"]:
                # 需要使用0.99相似度参数 相似度阈值过低可能导致一张图片被识别为两张卡
                find = match_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=RESOURCE_P["card"]["战斗"][f"冰淇淋-{j}.png"],
                    target_tolerance=0.99)
                if find:
                    position = [int(find[0]), int(find[1])]
                    break
            # 防止卡片正好被某些特效遮挡, 所以等待一下
            time.sleep(0.1)

        # 根据坐标位置，判断对应的卡id
        if position:
            for card_id, card_xy_list in self.bp_card.items():
                x1 = card_xy_list[0] - 45
                y1 = card_xy_list[1] - 64
                x2 = card_xy_list[0] + 8
                y2 = card_xy_list[1] + 6
                if x1 <= position[0] <= x2 and y1 <= position[1] <= y2:
                    self.smoothie_position = {"id": card_id, "location_from": position}
                    break

        self.print_debug(text="战斗中识图查找冰沙位置, 结果：{}".format(self.smoothie_position))

    def init_kun_card_position(self):

        self.print_debug(text="战斗中识图查找幻幻鸡位置, 开始")

        # 初始化为None
        self.kun_position = None

        position = None
        # 查找对应卡片坐标 重复3次
        for i in range(3):
            for j in range(6):
                # 需要使用0.99相似度参数 相似度阈值过低可能导致一张图片被识别为两张卡
                find = match_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=RESOURCE_P["card"]["战斗"][f"幻幻鸡-{j}.png"],
                    target_tolerance=0.99)
                if find:
                    position = [int(find[0]), int(find[1])]
                    break
                # 防止卡片正好被某些特效遮挡, 所以等待一下
                time.sleep(0.1)

        # 根据坐标位置，判断对应的卡id
        if position:
            for card_id, card_xy_list in self.bp_card.items():
                x1 = card_xy_list[0] - 45
                y1 = card_xy_list[1] - 64
                x2 = card_xy_list[0] + 8
                y2 = card_xy_list[1] + 6
                if x1 <= position[0] <= x2 and y1 <= position[1] <= y2:
                    self.kun_position = {"id": card_id, "location_from": position}
                    break

        self.print_debug(text="战斗中识图查找幻幻鸡位置, 结果：{}".format(self.kun_position))

    def init_battle_plan_1(self):
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
        is_group = self.is_group
        bp_cell = copy.deepcopy(self.bp_cell)
        bp_card = copy.deepcopy(self.bp_card)

        """调用类参数-战斗前生成"""
        quest_card = copy.deepcopy(self.quest_card)
        ban_card_list = copy.deepcopy(self.ban_card_list)
        stage_info = copy.deepcopy(self.stage_info)
        battle_plan = copy.deepcopy(self.battle_plan_0)
        mat_card_position = copy.deepcopy(self.mat_card_positions)
        smoothie_position = copy.deepcopy(self.smoothie_position)

        def calculation_card_quest(list_cell_all):
            """计算步骤一 加入任务卡的摆放坐标"""

            # 任务卡 大号小号开始位置不同 任务卡id = 0 则为没有
            quest_card_locations = ["6-1", "6-2", "6-3", "6-4", "6-5", "6-6", "6-7"]

            if quest_card == "None":
                return list_cell_all

            else:

                # 遍历删除 方案的放卡中 占用了任务卡摆放的棋盘位置
                list_cell_all = [
                    {**card, "location": list(filter(lambda x: x not in quest_card_locations, card["location"]))}
                    for card in list_cell_all
                ]

                # 计算任务卡的id 最大的卡片id + 1
                quest_card_id = max(card["id"] for card in list_cell_all) + 1

                # 设定任务卡dict
                dict_quest = {
                    "name": quest_card,
                    "id": quest_card_id,
                    "location": quest_card_locations,
                    "ergodic": True,
                    "queue": True,
                    "location_from": [],
                    "location_to": []
                }

                # 首位插入
                list_cell_all.insert(0, dict_quest)
                return list_cell_all

        def calculation_card_mat(list_cell_all):
            """步骤二 承载卡"""

            location = stage_info["mat_cell"]  # 深拷贝 防止对配置文件数据更改

            # p1p2分别摆一半
            if is_group:
                if self.is_main:
                    location = location[::2]  # 奇数
                else:
                    location = location[1::2]  # 偶数
            # 根据不同垫子数量 再分
            num_mat_card = len(mat_card_position)

            for i in range(num_mat_card):
                dict_mat = {
                    "name": "承载卡",
                    "id": mat_card_position[i]["id"],
                    "location": location[i::num_mat_card],
                    "ergodic": True,
                    "queue": True,
                    "location_from": mat_card_position[i]["location_from"],
                    "location_to": []}
                # 首位插入
                list_cell_all.insert(0, dict_mat)

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

        def calculation_card_extra(list_cell_all):

            if smoothie_position:
                # 仅该卡确定存在后执行添加
                card_dict = {
                    "name": "极寒冰沙",
                    "id": smoothie_position["id"],
                    "location": ["1-1"],
                    "ergodic": True,
                    "queue": True,
                    "location_from": smoothie_position["location_from"],
                    "location_to": []
                }
                list_cell_all.append(card_dict)

            if self.kun_position:
                # 确认卡片在卡组 且 有至少一个kun参数设定
                kun_already_set = False
                for card in list_cell_all:
                    # 遍历已有卡片
                    if "kun" in card.keys():
                        kun_already_set = True
                        break
                if not kun_already_set:
                    # 没有设置 那么也视坤位置标记不存在
                    self.kun_position = None

            # 为没有kun参数的方案 默认添加0
            for card in list_cell_all:
                if "kun" not in card.keys():
                    card["kun"] = 0

            return list_cell_all

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

        def calculation_shovel():
            """铲子位置 """
            list_shovel = stage_info["shovel"]
            return list_shovel

        def transform_code_to_coordinate(list_cell_all, list_shovel):
            """
            如果没有后者
            将 id:int 变为 location_from:[x:int,y:int]
            将 location:str 变为 location_to:[[x:int,y:int],...]"""

            for card in list_cell_all:
                # 为每个字典添加未预设字段
                card["location_from"] = []
                card["location_to"] = []

                # 根据字段值, 判断是否完成写入, 并进行转换
                coordinate = copy.deepcopy(bp_card[card["id"]])
                coordinate = [coordinate[0], coordinate[1]]
                card["location_from"] = [coordinate[0], coordinate[1]]

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

            # 为幻鸡单独转化
            # 根据字段值, 判断是否完成写入, 并进行转换
            if self.kun_position:
                coordinate = copy.deepcopy(bp_card[self.kun_position["id"]])
                coordinate = [coordinate[0], coordinate[1]]
                self.kun_position["location_from"] = [coordinate[0], coordinate[1]]

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

            # 调用冰沙和坤函数
            list_cell_all = calculation_card_extra(list_cell_all=list_cell_all)

            # 调用去掉障碍位置
            list_cell_all = calculation_obstacle(list_cell_all=list_cell_all)

            # 调用计算铲子卡
            list_shovel = calculation_shovel()

            # 统一以坐标直接表示位置, 防止重复计算 (添加location_from, location_to)
            list_cell_all, list_shovel = transform_code_to_coordinate(
                list_cell_all=list_cell_all,
                list_shovel=list_shovel)

            # 不常用调试print
            self.print_debug(text="你的战斗放卡opt如下:")
            self.print_debug(text=list_cell_all)

            self.battle_plan_1 = {"card": list_cell_all, "shovel": list_shovel}

        return main()

    """战斗完整的过程中的任务函数"""

    def action_round_of_battle_before(self):

        """
        房间内战前准备
        :return: 0-正常结束 1-重启本次 2-跳过本次
        """

        def action_add_quest_card():
            # 由于公会任务的卡组特性, 当任务卡为[苏打气泡]时, 不需要额外选择带卡.
            my_bool = False
            my_bool = my_bool or self.quest_card == "None"
            my_bool = my_bool or self.quest_card == "苏打气泡-0"
            my_bool = my_bool or self.quest_card == "苏打气泡-1"
            my_bool = my_bool or self.quest_card == "苏打气泡"

            if my_bool:
                self.print_debug(text="不需要额外带卡,跳过")
            else:
                self.print_debug(text="寻找任务卡, 开始")

                """处理ban卡列表"""

                # 对于名称带-的卡, 就对应的写入, 如果不带-, 就查找其所有变种
                quest_card_list = []
                if "-" in self.quest_card:
                    quest_card_list.append("{}.png".format(self.quest_card))
                else:
                    for i in range(9):  # i代表一张卡能有的最高变种 姑且认为是3*3 = 9
                        quest_card_list.append("{}-{}.png".format(self.quest_card, i))

                # 读取所有记录了的卡的图片名, 只携带被记录图片的卡
                my_list = []
                for quest_card in quest_card_list:
                    if quest_card in RESOURCE_P["card"]["房间"].keys():
                        my_list.append(quest_card)
                quest_card_list = my_list

                """选卡动作"""
                already_find = False

                # 复位滑块
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=931, y=209)
                time.sleep(0.25)

                # 向下点3*7次滑块 强制要求全部走完, 防止12P的同步出问题
                for i in range(7):

                    for quest_card in quest_card_list:

                        if already_find:
                            # 如果已经刚找到了 就直接休息一下
                            time.sleep(0.4)
                        else:
                            # 如果还没找到 就试试查找点击 添加卡片
                            find = loop_match_p_in_w(
                                raw_w_handle=self.handle,
                                raw_range=[380, 175, 925, 420],
                                target_path=RESOURCE_P["card"]["房间"][quest_card],
                                target_tolerance=0.95,
                                target_failed_check=0.4,
                                target_interval=0.2,
                                target_sleep=0.4,  # 和总计检测时间一致 以同步时间
                                click=True)
                            if find:
                                already_find = True

                    # 滑块向下移动3次
                    for j in range(3):
                        if not already_find:
                            # 仅还没找到继续下滑
                            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=931, y=400)
                        # 找没找到都要休息一下以同步时间
                        time.sleep(0.05)

                if not already_find:
                    # 如果没有找到 战斗方案也就不需要对应调整了 修改一下
                    self.quest_card = "None"

                self.print_debug(text="寻找任务卡, 完成, 结果:{}".format("成功" if already_find else "失败"))

        def screen_ban_card_loop_a_round(ban_card_s):

            for card in ban_card_s:
                # 只ban被记录了图片的变种卡
                loop_match_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[380, 40, 915, 105],
                    target_path=RESOURCE_P["card"]["房间"][card],
                    target_tolerance=0.95,
                    target_interval=0.2,
                    target_failed_check=0.6,
                    target_sleep=1,
                    click=True)

        def action_remove_ban_card():
            """寻找并移除需要ban的卡, 现已支持跨页ban"""

            # 只有ban卡数组非空, 继续进行
            if self.ban_card_list:

                # 处理需要ban的卡片,
                ban_card_list = []
                for ban_card in self.ban_card_list:
                    # 对于名称带-的卡, 就对应的写入, 如果不带-, 就查找其所有变种
                    if "-" in ban_card:
                        ban_card_list.append("{}.png".format(ban_card))
                    else:
                        for i in range(21):  # i代表一张卡能有的最高变种 姑且认为是3*7 = 21
                            ban_card_list.append("{}-{}.png".format(ban_card, i))

                # 读取所有已记录的卡片文件名, 并去除没有记录的卡片
                my_list = []
                for ban_card in ban_card_list:
                    if ban_card in RESOURCE_P["card"]["房间"].keys():
                        my_list.append(ban_card)
                ban_card_list = my_list

                # 翻页回第一页
                for i in range(5):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=930, y=55)
                    time.sleep(0.05)

                # 第一页
                screen_ban_card_loop_a_round(ban_card_s=ban_card_list)

                # 翻页到第二页
                for i in range(5):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=930, y=85)
                    time.sleep(0.05)

                # 第二页
                screen_ban_card_loop_a_round(ban_card_s=ban_card_list)

        def main():
            # 循环查找开始按键
            self.print_debug(text="寻找开始或准备按钮")
            find = loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[796, 413, 950, 485],
                target_path=RESOURCE_P["common"]["战斗"]["战斗前_开始按钮.png"],
                target_interval=1,
                target_failed_check=10,
                target_sleep=0.3,
                click=False)
            if not find:
                self.print_warning(text="创建房间后, 10s找不到[开始/准备]字样! 创建房间可能失败!")
                # 可能是由于: 服务器抽风无法创建房间 or 点击被吞 or 次数用尽
                return 2  # 2-跳过本次

            # 选择卡组
            self.print_debug(text="选择卡组, 并开始加入新卡和ban卡")
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=self.handle,
                x={1: 425, 2: 523, 3: 588, 4: 666, 5: 756, 6: 837}[self.deck],
                y=121)
            time.sleep(0.7)

            """寻找并添加任务所需卡片"""
            action_add_quest_card()
            action_remove_ban_card()

            """点击开始"""

            # 点击开始
            find = loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[796, 413, 950, 485],
                target_path=RESOURCE_P["common"]["战斗"]["战斗前_开始按钮.png"],
                target_tolerance=0.95,
                target_interval=1,
                target_failed_check=10,
                target_sleep=1,
                click=True)
            if not find:
                self.print_warning(text="选择卡组后, 10s找不到[开始/准备]字样! 创建房间可能失败!")
                return 1  # 1-重启本次

            # 防止被 [没有带xx卡] or []包已满 卡住
            find = match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=RESOURCE_P["common"]["战斗"]["战斗前_系统提示.png"],
                target_tolerance=0.98)
            if find:
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=427,
                    y=353)
                time.sleep(0.05)

            # 刷新ui: 状态文本
            self.print_debug(text="查找火苗标识物, 等待进入战斗, 限时30s")

            # 循环查找火苗图标 找到战斗开始
            find = loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=RESOURCE_P["common"]["战斗"]["战斗中_火苗能量.png"],
                target_interval=0.5,
                target_failed_check=30,
                target_sleep=0.1,
                click=False)

            # 刷新ui: 状态文本
            if find:
                self.print_debug(text="找到火苗标识物, 战斗进行中...")

            else:
                self.print_warning(text="未能找到火苗标识物, 进入战斗失败, 可能是次数不足或服务器卡顿")
                return 2  # 2-跳过本次

            return 0  # 0-一切顺利

        return main()

    def action_round_of_battle_self(self):
        """
        关卡内战斗过程
        """
        # 0.刷新faa_battle实例的部分属性
        self.faa_battle.re_init()

        # 1.把人物放下来
        time.sleep(0.333)
        if not self.is_main:
            time.sleep(0.666)

        self.faa_battle.use_player_all()

        # 2.识图卡片数量，确定卡片在deck中的位置
        self.bp_card = get_position_card_deck_in_battle(handle=self.handle)

        # 3.识图各种卡参数
        self.init_mat_card_position()
        self.init_smoothie_card_position()
        self.init_kun_card_position()

        # 4.计算所有坐标
        self.init_battle_plan_1()

        # 5.铲卡
        if self.is_main:
            self.faa_battle.use_shovel_all()  # 因为有点击序列，所以同时操作是可行的

    def action_round_of_battle_screen(self):
        """
        战斗结束后, 完成下述流程: 潜在的任务完成黑屏-> 战利品 -> 战斗结算 -> 翻宝箱 -> 回到房间/魔塔会回到其他界面
        """

        def screen_loots():
            """
            :return: 捕获的战利品dict
            """

            # 记录战利品 tip 一张图49x49 是完美规整的
            images = []

            # 防止 已有选中的卡片, 先点击空白
            T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=200, y=350)
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=200, y=350)
            time.sleep(0.025)

            # 1 2 行
            for i in range(3):
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=708, y=484)
                time.sleep(0.05)
            time.sleep(0.25)
            images.append(capture_picture_png(handle=self.handle, raw_range=[209, 454, 699, 552]))
            time.sleep(0.25)

            # 3 4 行 取3行
            for i in range(3):
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=708, y=510)
                time.sleep(0.05)
            time.sleep(0.25)
            images.append(capture_picture_png(handle=self.handle, raw_range=[209, 456, 699, 505]))
            time.sleep(0.25)

            # 4 5 行
            for i in range(3):
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=708, y=529)
                time.sleep(0.05)
            time.sleep(0.25)
            images.append(capture_picture_png(handle=self.handle, raw_range=[209, 454, 699, 552]))
            time.sleep(0.25)

            # 垂直拼接
            image = cv2.vconcat(images)

            return image

        def screen_loot_logs():
            """
            :return: 捕获的战利品dict
            """
            # 是否在战利品ui界面
            find = loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[202, 419, 306, 461],
                target_path=RESOURCE_P["common"]["战斗"]["战斗后_1_战利品.png"],
                target_failed_check=2,
                target_tolerance=0.99,
                click=False)

            if find:
                self.print_debug(text="[战利品UI] 正常结束, 尝试捕获战利品截图")

                # 错开一下, 避免卡住
                if self.player == 2:
                    time.sleep(0.333)

                # 定义保存路径和文件名格式
                img_path = "{}\\{}_{}P_{}.png".format(
                    PATHS["logs"] + "\\loots_picture",
                    self.stage_info["id"],
                    self.player,
                    time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime())
                )

                # 截图并保存
                img = screen_loots()

                # 分析图片，获取战利品字典
                drop_dict = matchImage(img_path=img_path, img=img, test_print=True)
                self.print_debug(text="[捕获战利品] 处在战利品UI 战利品已 捕获/识别/保存".format(drop_dict))

                return drop_dict

            else:
                self.print_debug(text="[捕获战利品] 未在战利品UI 可能由于延迟未能捕获战利品, 继续流程")

                return None

        def action_flip_treasure_chest():
            find = loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[400, 35, 550, 75],
                target_path=RESOURCE_P["common"]["战斗"]["战斗后_4_翻宝箱.png"],
                target_failed_check=15,
                target_sleep=2,
                click=False
            )
            if find:
                self.print_debug(text="[翻宝箱UI] 捕获到正确标志, 翻牌并退出...")
                # 开始洗牌
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=708, y=502)
                time.sleep(6)

                # 翻牌 1+2
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=550, y=170)
                time.sleep(0.5)
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=708, y=170)
                time.sleep(1.5)

                img = [
                    capture_picture_png(
                        handle=self.handle,
                        raw_range=[249, 89, 293, 133]),
                    capture_picture_png(
                        handle=self.handle,
                        raw_range=[317, 89, 361, 133])
                ]

                img = cv2.hconcat(img)

                # 定义保存路径和文件名格式
                img_path = "{}\\{}_{}P_{}.png".format(
                    PATHS["logs"] + "\\chests_picture",
                    self.stage_info["id"],
                    self.player,
                    time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime())
                )

                # 分析图片，获取战利品字典
                drop_dict = matchImage(img_path=img_path, img=img, mode="chests", test_print=True)
                self.print_debug(text="[翻宝箱] 宝箱已 捕获/识别/保存".format(drop_dict))

                # 组队2P慢点结束翻牌 保证双人魔塔后自己是房主
                if self.is_group and self.player == 2:
                    time.sleep(2)

                # 结束翻牌
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=708, y=502)
                time.sleep(3)

                return drop_dict

            else:
                self.print_warning(text="[翻宝箱UI] 15s未能捕获正确标志, 出问题了!")
                return {}

        def log_loots_statistics_to_json(loots_dict, chests_dict):
            """
            保存战利品汇总.json
            """

            file_path = "{}\\result_json\\{}P掉落汇总.json".format(PATHS["logs"], self.player)
            stage_name = self.stage_info["id"]

            # 获取本次战斗是否使用了钥匙
            if self.faa_battle.is_used_key:
                used_key_str = "is_used_key"
            else:
                used_key_str = "is_not_used_key"

            if os.path.exists(file_path):
                # 尝试读取现有的JSON文件
                with open(file_path, "r", encoding="utf-8") as json_file:
                    json_data = json.load(json_file)
            else:
                # 如果文件不存在，初始化
                json_data = {}

            # 检查键 不存在添加
            json_data_stage = json_data.setdefault(stage_name, {})
            json_data_used_key = json_data_stage.setdefault(used_key_str, {})
            json_data_loots = json_data_used_key.setdefault("loots", {})
            json_data_chests = json_data_used_key.setdefault("chests", {})
            json_data_count = json_data_used_key.setdefault("count", 0)

            # 更新现有数据
            for item_str, count in loots_dict.items():
                json_data_loots[item_str] = json_data_loots.get(item_str, 0) + count
            for item_str, count in chests_dict.items():
                json_data_chests[item_str] = json_data_loots.get(item_str, 0) + count
            json_data_count += 1  # 更新次数

            # 保存或更新后的战利品字典到JSON文件
            with open(file_path, "w", encoding="utf-8") as json_file:
                json.dump(json_data, json_file, ensure_ascii=False, indent=4)

        def log_loots_detail_to_json(loots_dict, chests_dict):
            """分P，在目录下保存战利品字典"""
            file_path = "{}\\result_json\\{}P掉落明细.json".format(PATHS["logs"], self.player)
            stage_name = self.stage_info["id"]

            if os.path.exists(file_path):
                # 读取现有的JSON文件
                with open(file_path, "r", encoding="utf-8") as json_file:
                    json_data = json.load(json_file)
            else:
                # 如果文件不存在，初始化
                json_data = {}

            # 检查"data"字段是否存在
            json_data.setdefault("data", [])

            json_data["data"].append({
                "timestamp": time.time(),
                "stage": stage_name,
                "is_used_key": self.faa_battle.is_used_key,
                "loots": loots_dict,
                "chests": chests_dict
            })

            # 保存或更新后的战利品字典到JSON文件
            with open(file_path, "w", encoding="utf-8") as json_file:
                json.dump(json_data, json_file, ensure_ascii=False, indent=4)

        def main():
            self.print_debug(text="识别到多种战斗结束标志之一, 进行收尾工作")

            # 战利品部分, 会先检测是否在对应界面
            loots_dict = screen_loot_logs()

            # 翻宝箱部分, 会先检测是否在对应界面
            chests_dict = action_flip_treasure_chest()

            result_loot = {"loots": loots_dict, "chests": chests_dict}

            if (loots_dict is not None) and (chests_dict is not None):
                log_loots_statistics_to_json(loots_dict=loots_dict, chests_dict=chests_dict)
                log_loots_detail_to_json(loots_dict=loots_dict, chests_dict=chests_dict)

            if self.screen_check_server_boom():
                self.print_warning(text="检测到 断开连接 or 登录超时 or Flash爆炸, 炸服了")
                return 1, None  # 1-重启本次
            else:
                return 0, result_loot

        return main()

    def action_round_of_battle_after(self):

        """
        房间内或其他地方 战斗结束
        :return: 0-正常结束 1-重启本次 2-跳过本次
        """

        # 查找战斗结束 来兜底正确完成了战斗
        self.print_debug(text="[开始/准备/魔塔蛋糕UI] 尝试捕获正确标志, 以完成战斗流程.")
        find = loop_match_ps_in_w(
            raw_w_handle=self.handle,
            target_opts=[
                {
                    "raw_range": [796, 413, 950, 485],
                    "target_path": RESOURCE_P["common"]["战斗"]["战斗前_开始按钮.png"],
                    "target_tolerance": 0.99},
                {
                    "raw_range": [200, 0, 750, 100],
                    "target_path": RESOURCE_P["common"]["魔塔蛋糕_ui.png"],
                    "target_tolerance": 0.99
                }],
            target_return_mode="or",
            target_failed_check=10,
            target_interval=0.2)
        if find:
            self.print_debug(text="成功捕获[开始/准备/魔塔蛋糕UI], 完成战斗流程.")
            return 0  # 0-正常结束
        else:
            self.print_error(text="10s没能捕获[开始/准备/魔塔蛋糕UI], 出现意外错误, 直接跳过本次")
            return 2  # 2-跳过本次

    """其他非战斗功能"""

    def action_quest_receive_rewards(self,mode:str):
        return self.object_action_quest_receive_rewards.main(mode=mode)

    def get_quests(self, mode: str, qg_cs=False):
        """
        获取公会任务列表
        :param mode:
        :param qg_cs: 公会任务模式下 是否需要跨服
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
            loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=RESOURCE_P["quest_guild"]["ui_quest_list.png"],
                target_sleep=0.2,
                click=True)
        if mode == "情侣任务":
            self.action_bottom_menu(mode="跳转_情侣任务")
        if mode == "美食大赛":
            self.action_top_menu(mode="美食大赛")

        # 读取
        quest_list = []
        if mode == "公会任务":

            for i in [1, 2, 3, 4, 5, 6, 7]:
                for quest, img in RESOURCE_P["quest_guild"][str(i)].items():
                    # 找到任务 加入任务列表
                    find_p = match_p_in_w(
                        raw_w_handle=self.handle,
                        raw_range=[0, 0, 950, 600],
                        target_path=img,
                        target_tolerance=0.999)
                    if find_p:

                        quest_card = "None"  # 任务携带卡片默认为None

                        # 处理解析字符串
                        quest = quest.split(".")[0]  # 去除.png
                        num_of_line = quest.count("_")  # 分割
                        if num_of_line == 0:
                            stage_id = quest
                        else:
                            my_list = quest.split("_")
                            stage_id = my_list[0]
                            if num_of_line == 1:
                                if not my_list[1].isdigit():
                                    quest_card = my_list[1]
                            elif num_of_line == 2:
                                quest_card = my_list[2]

                        # 如果不打 跳过
                        if stage_id.split("-")[0] == "CS" and (not qg_cs):
                            continue

                        # 添加到任务列表
                        quest_list.append(
                            {
                                "player": [2, 1],
                                "stage_id": stage_id,
                                "quest_card": quest_card
                            }
                        )
        if mode == "情侣任务":

            for i in ["1", "2", "3"]:
                # 任务未完成
                find_p = match_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=RESOURCE_P["quest_spouse"]["NO-{}.png".format(i)],
                    target_tolerance=0.999)
                if find_p:
                    # 遍历任务
                    for quest, img in RESOURCE_P["quest_spouse"][i].items():
                        # 找到任务 加入任务列表
                        find_p = match_p_in_w(
                            raw_w_handle=self.handle,
                            raw_range=[0, 0, 950, 600],
                            target_path=img,
                            target_tolerance=0.999)
                        if find_p:
                            quest_list.append(
                                {
                                    "player": [2, 1],
                                    "stage_id": quest.split(".")[0],
                                    "quest_card": "None"
                                }
                            )
        if mode == "美食大赛":
            y_dict = {0: 362, 1: 405, 2: 448, 3: 491, 4: 534, 5: 570}
            for i in range(6):
                # 先移动到新的一页
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=536, y=y_dict[i])
                time.sleep(0.1)
                for quest, img in RESOURCE_P["quest_food"].items():
                    find_p = match_p_in_w(
                        raw_w_handle=self.handle,
                        raw_range=[0, 0, 950, 600],
                        target_path=img,
                        target_tolerance=0.999)

                    if find_p:
                        # 处理解析字符串
                        quest = quest.split(".")[0]  # 去除.png
                        battle_sets = quest.split("_")
                        quest_list.append(
                            {
                                "stage_id": battle_sets[0],
                                "player": [self.player] if battle_sets[1] == "1" else [2, 1],  # 1 单人 2 组队
                                "is_use_key": bool(battle_sets[2]),  # 注意类型转化
                                "max_times": 1,
                                "quest_card": battle_sets[3],
                                "list_ban_card": battle_sets[4].split(","),
                                "dict_exit": {
                                    "other_time_player_a": [],
                                    "other_time_player_b": [],
                                    "last_time_player_a": ["竞技岛", "美食大赛领取"],
                                    "last_time_player_b": ["竞技岛", "美食大赛领取"]
                                }
                            }
                        )

        # 关闭公会任务列表(红X)
        if mode == "公会任务" or mode == "情侣任务":
            self.action_exit(mode="普通红叉")
        if mode == "美食大赛":
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=888, y=53)
            time.sleep(0.5)

        return quest_list

    def reload_to_login_ui(self):

        # 点击刷新按钮 该按钮在360窗口上
        find = loop_match_p_in_w(
            raw_w_handle=self.handle_360,
            raw_range=[0, 0, 400, 100],
            target_path=RESOURCE_P["common"]["登录"]["0_刷新.png"],
            target_tolerance=0.9,
            target_sleep=3,
            click=True)

        if not find:
            find = loop_match_p_in_w(
                raw_w_handle=self.handle_360,
                raw_range=[0, 0, 400, 100],
                target_path=RESOURCE_P["common"]["登录"]["0_刷新_被选中.png"],
                target_tolerance=0.98,
                target_sleep=3,
                click=True)

            if not find:

                find = loop_match_p_in_w(
                    raw_w_handle=self.handle_360,
                    raw_range=[0, 0, 400, 100],
                    target_path=RESOURCE_P["common"]["登录"]["0_刷新_被点击.png"],
                    target_tolerance=0.98,
                    target_sleep=3,
                    click=True)

                if not find:
                    self.print_error(text="未找到360大厅刷新游戏按钮, 可能导致一系列问题...")

    def reload_game(self):

        def try_enter_server_4399():
            # 4399 进入服务器
            my_result = match_p_in_w(
                raw_w_handle=self.handle_browser,
                raw_range=[0, 0, 2000, 2000],
                target_path=RESOURCE_P["common"]["登录"]["1_我最近玩过的服务器_4399.png"],
                target_tolerance=0.9
            )
            if my_result:
                # 点击进入服务器
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle_browser,
                    x=my_result[0],
                    y=my_result[1] + 30)
                return True
            return False

        def try_enter_server_qq_space():
            # QQ空间 进入服务器
            my_result = match_p_in_w(
                raw_w_handle=self.handle_browser,
                raw_range=[0, 0, 2000, 2000],
                target_path=RESOURCE_P["common"]["登录"]["1_我最近玩过的服务器_QQ空间.png"],
                target_tolerance=0.9
            )
            if my_result:
                # 点击进入服务器
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle_browser,
                    x=my_result[0] + 20,
                    y=my_result[1] + 30)
                return True
            return False

        def try_enter_server_qq_game_hall():
            # QQ游戏大厅 进入服务器
            my_result = match_p_in_w(
                raw_w_handle=self.handle_browser,
                raw_range=[0, 0, 2000, 2000],
                target_path=RESOURCE_P["common"]["登录"]["1_我最近玩过的服务器_QQ游戏大厅.png"],
                target_tolerance=0.9
            )
            if my_result:
                # 点击进入服务器
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle_browser,
                    x=my_result[0],
                    y=my_result[1] + 30)
                return True
            return False

        while True:

            # 点击刷新按钮 该按钮在360窗口上
            self.print_debug(text="[刷新游戏] 点击刷新按钮...")
            self.reload_to_login_ui()

            # 是否在 选择服务器界面 - 判断是否存在 最近玩过的服务器ui(4399 or qq空间) 或 开始游戏(qq游戏大厅) 并进入
            result = False

            self.print_debug(text="[刷新游戏] 判定4399平台...")
            result = result or try_enter_server_4399()

            self.print_debug(text="[刷新游戏] 判定QQ空间平台...")
            result = result or try_enter_server_qq_space()

            self.print_debug(text="[刷新游戏] 判定QQ游戏大厅平台...")
            result = result or try_enter_server_qq_game_hall()

            # 如果未找到进入服务器，从头再来
            if not result:
                self.print_debug(text="[刷新游戏] 未找到进入服务器, 可能 1.QQ空间需重新登录 2.360X4399微端 3.意外情况")

                result = loop_match_p_in_w(
                    raw_w_handle=self.handle_browser,
                    raw_range=[0, 0, 2000, 2000],
                    target_path=RESOURCE_P["common"]["用户自截"]["空间服登录界面_{}P.png".format(self.player)],
                    target_tolerance=0.95,
                    target_interval=0.5,
                    target_failed_check=5,
                    target_sleep=5,
                    click=True)
                if result:
                    self.print_debug(text="[刷新游戏] 找到QQ空间服一键登录, 正在登录")
                else:
                    self.print_debug(text="[刷新游戏] 未找到QQ空间服一键登录, 可能 1.360X4399微端 2.意外情况, 继续")

            """查找大地图确认进入游戏"""
            self.print_debug(text="[刷新游戏] 循环识图中, 以确认进入游戏...")
            # 更严格的匹配 防止登录界面有相似图案组合
            result = loop_match_ps_in_w(
                raw_w_handle=self.handle_browser,
                target_opts=[
                    {
                        "raw_range": [840, 525, 2000, 2000],
                        "target_path": RESOURCE_P["common"]["底部菜单"]["跳转.png"],
                        "target_tolerance": 0.98,
                    }, {
                        "raw_range": [610, 525, 2000, 2000],
                        "target_path": RESOURCE_P["common"]["底部菜单"]["任务.png"],
                        "target_tolerance": 0.98,
                    }, {
                        "raw_range": [890, 525, 2000, 2000],
                        "target_path": RESOURCE_P["common"]["底部菜单"]["后退.png"],
                        "target_tolerance": 0.98,
                    }
                ],
                target_return_mode="and",
                target_failed_check=30,
                target_interval=1
            )

            if result:
                self.print_debug(text="[刷新游戏] 循环识图成功, 确认进入游戏! 即将刷新Flash句柄")

                # 重新获取句柄, 此时游戏界面的句柄已经改变
                self.handle = faa_get_handle(channel=self.channel, mode="flash")

                # [4399] [QQ空间]关闭健康游戏公告
                self.print_debug(text="[刷新游戏] [4399] [QQ空间] 尝试关闭健康游戏公告")
                loop_match_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=RESOURCE_P["common"]["登录"]["3_健康游戏公告_确定.png"],
                    target_tolerance=0.97,
                    target_failed_check=5,
                    target_sleep=1,
                    click=True)

                self.print_debug(text="[刷新游戏] 尝试关闭每日必充界面")
                # [每天第一次登陆] 每日必充界面关闭
                loop_match_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=RESOURCE_P["common"]["登录"]["4_退出每日必充.png"],
                    target_tolerance=0.99,
                    target_failed_check=3,
                    target_sleep=1,
                    click=True)
                self.random_seed += 1

                self.print_debug(text="[刷新游戏] 已完成")

                return
            else:
                self.print_warning(text="[刷新游戏] 查找大地图失败, 点击服务器后未能成功进入游戏, 刷新重来")

    def sign_in(self):

        def sign_in_vip():
            """VIP签到"""
            self.action_top_menu(mode="VIP签到")

            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=740, y=190)
            time.sleep(0.5)

            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=225, y=280)
            time.sleep(0.5)

            self.action_exit(mode="普通红叉")

        def sign_in_everyday():
            """每日签到"""
            self.action_top_menu(mode="每日签到")

            loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=RESOURCE_P["common"]["签到"]["每日签到_确定.png"],
                target_tolerance=0.99,
                target_failed_check=1,
                target_sleep=1,
                click=True)

            self.action_exit(mode="普通红叉")

        def sign_in_food_activity():
            """美食活动"""

            self.action_top_menu(mode="美食活动")

            loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=RESOURCE_P["common"]["签到"]["美食活动_确定.png"],
                target_tolerance=0.99,
                target_failed_check=1,
                target_sleep=1,
                click=True)

            self.action_exit(mode="普通红叉")

        def sign_in_tarot():
            """塔罗寻宝"""
            self.action_top_menu(mode="塔罗寻宝")

            loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=RESOURCE_P["common"]["签到"]["塔罗寻宝_确定.png"],
                target_tolerance=0.99,
                target_failed_check=1,
                target_sleep=1,
                click=True)

            loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=RESOURCE_P["common"]["签到"]["塔罗寻宝_退出.png"],
                target_tolerance=0.99,
                target_failed_check=1,
                target_sleep=1,
                click=True)

        def sign_in_pharaoh():
            """法老宝藏"""
            self.action_top_menu(mode="法老宝藏")

            find = loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=RESOURCE_P["common"]["签到"]["法老宝藏_确定.png"],
                target_tolerance=0.99,
                target_failed_check=1,
                target_sleep=1,
                click=False)

            if find:
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=300, y=250)
                time.sleep(1)

            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=791, y=98)
            time.sleep(1)

        def sign_in_release_quest_guild():
            """会长发布任务"""
            self.action_bottom_menu(mode="跳转_公会任务")

            find = loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[73, 31, 173, 78],
                target_path=RESOURCE_P["common"]["签到"]["公会会长_发布任务.png"],
                target_tolerance=0.99,
                target_failed_check=1,
                target_sleep=1,
                click=True)
            if find:
                loop_match_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[422, 415, 544, 463],
                    target_path=RESOURCE_P["common"]["签到"]["公会会长_发布任务_确定.png"],
                    target_tolerance=0.99,
                    target_failed_check=1,
                    target_sleep=3,
                    click=True)
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
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=400, y=445)
                time.sleep(0.5)

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

        def from_guild_to_quest_guild():
            """进入任务界面, 正确进入就跳出循环"""
            while True:

                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=745, y=430)
                time.sleep(0.001)

                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=700, y=350)
                time.sleep(2)

                find = loop_match_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=RESOURCE_P["quest_guild"]["ui_quest_list.png"],
                    target_tolerance=0.95,
                    target_failed_check=1,
                    target_sleep=0.5,
                    click=True
                )
                if find:
                    break

        def from_guild_to_guild_garden():
            """进入施肥界面, 正确进入就跳出循环"""
            while True:

                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=745, y=430)
                time.sleep(0.001)

                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=800, y=350)
                time.sleep(2)

                find = loop_match_p_in_w(
                    raw_w_handle=self.handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=RESOURCE_P["quest_guild"]["ui_fed.png"],
                    target_tolerance=0.95,
                    target_failed_check=1,
                    target_sleep=0.5,
                    click=True
                )
                if find:
                    break

        def switch_guild_garden_by_try_times(try_time):
            """根据目前尝试次数, 到达不同的公会"""
            if try_time != 0:

                # 点击全部工会
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=798, y=123)
                time.sleep(0.5)

                # 跳转到最后
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=843, y=305)
                time.sleep(0.5)

                # 以倒数第二页从上到下为1-4, 第二页为5-8次尝试对应的公会 以此类推
                for i in range((try_time - 1) // 4 + 1):
                    # 向上翻的页数
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=843, y=194)
                    time.sleep(0.5)

                # 点第几个
                my_dict = {1: 217, 2: 244, 3: 271, 4: 300}
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=810,
                    y=my_dict[(try_time - 1) % 4 + 1])
                time.sleep(0.5)

        def do_something_and_exit(try_time):
            """完成素质三连并退出公会花园界面"""
            # 采摘一次
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=785, y=471)
            time.sleep(1)

            # 浇水一次
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=785, y=362)
            time.sleep(1)

            # 等待一下 确保没有完成的黑屏
            loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=RESOURCE_P["common"]["退出.png"],
                target_tolerance=0.95,
                target_failed_check=7,
                target_sleep=1,
                click=False
            )
            self.print_debug(text="{}次尝试, 浇水后, 已确认无任务完成黑屏".format(try_time + 1))

            # 施肥一次
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=785, y=418)
            time.sleep(1)

            # 等待一下 确保没有完成的黑屏
            loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=RESOURCE_P["common"]["退出.png"],
                target_tolerance=0.95,
                target_failed_check=7,
                target_sleep=1,
                click=False)
            self.print_debug(text="{}次尝试, 施肥后, 已确认无任务完成黑屏".format(try_time + 1))

            # 点X回退一次
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=854, y=55)
            time.sleep(1.5)

        def fed_and_watered_one_action(try_time):
            """
            :return: bool completed True else False
            """
            # 进入任务界面, 正确进入就跳出循环
            from_guild_to_quest_guild()

            # 检测施肥任务完成情况 任务是进行中的话为True
            find = loop_match_ps_in_w(
                raw_w_handle=self.handle,
                target_opts=[
                    {
                        "raw_range": [75, 80, 430, 560],
                        "target_path": RESOURCE_P["quest_guild"]["fed_0.png"],
                        "target_tolerance": 0.98
                    }, {
                        "raw_range": [75, 80, 430, 560],
                        "target_path": RESOURCE_P["quest_guild"]["fed_1.png"],
                        "target_tolerance": 0.98
                    }, {
                        "raw_range": [75, 80, 430, 560],
                        "target_path": RESOURCE_P["quest_guild"]["fed_2.png"],
                        "target_tolerance": 0.98,
                    }, {
                        "raw_range": [75, 80, 430, 560],
                        "target_path": RESOURCE_P["quest_guild"]["fed_3.png"],
                        "target_tolerance": 0.98,
                    }
                ],
                target_return_mode="or",
                target_failed_check=2)

            # 退出任务界面
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=854, y=55)
            time.sleep(0.5)

            if not find:
                self.print_debug(text="已完成公会浇水施肥, 尝试次数:{}".format(try_time))
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
            self.print_debug(text="开始公会浇水施肥")

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
        self.object_action_quest_receive_rewards.main(mode="公会任务")

    def use_item(self):
        # 获取所有图片资源
        self.print_debug(text="开启使用物品功能")

        # 打开背包
        self.print_debug(text="打开背包")
        self.action_bottom_menu(mode="背包")

        # 升到最顶, 不需要, 打开背包会自动重置

        # 四次循环查找所有正确图标
        for i in range(4):

            self.print_debug(text="第{}页物品".format(i + 1))

            # 第一次以外, 下滑4*5次
            if i != 0:
                for j in range(5):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=920, y=422)
                    time.sleep(0.2)

            for item_name, item_image in RESOURCE_P["item"]["背包"].items():

                while True:

                    # 在限定范围内 找红叉点掉
                    loop_match_p_in_w(
                        raw_w_handle=self.handle,
                        raw_range=[0, 0, 750, 300],
                        target_path=RESOURCE_P["common"]["退出.png"],
                        target_tolerance=0.95,
                        target_interval=0.2,
                        target_failed_check=1,
                        target_sleep=0.5,
                        click=True)

                    # 在限定范围内 找物品
                    find = loop_match_p_in_w(
                        raw_w_handle=self.handle,
                        raw_range=[466, 86, 891, 435],
                        target_path=item_image,
                        target_tolerance=0.90,
                        target_interval=0.2,
                        target_failed_check=0.2,
                        target_sleep=0.05,
                        click=True)

                    if find:
                        # 在限定范围内 找到并点击物品 使用它
                        find = loop_match_p_in_w(
                            raw_w_handle=self.handle,
                            raw_range=[466, 86, 950, 500],
                            target_path=RESOURCE_P["item"]["背包_使用.png"],
                            target_tolerance=0.90,
                            target_interval=0.2,
                            target_failed_check=1,
                            target_sleep=0.5,
                            click=True)

                        # 鼠标选中 使用按钮 会有色差, 第一次找不到则再来一次
                        if not find:
                            loop_match_p_in_w(
                                raw_w_handle=self.handle,
                                raw_range=[466, 86, 950, 500],
                                target_path=RESOURCE_P["item"]["背包_使用_被选中.png"],
                                target_tolerance=0.90,
                                target_interval=0.2,
                                target_failed_check=1,
                                target_sleep=0.5,
                                click=True)

                    else:
                        # 没有找到对应物品 skip
                        self.print_debug(text="物品:{}本页已全部找到".format(item_name))
                        break

        # 关闭背包
        self.action_exit(mode="普通红叉")

    def loop_cross_server(self, deck):

        first_time = True

        while True:

            if first_time:
                # 进入界面
                self.action_top_menu(mode="跨服远征")
                first_time = False

            # 创建房间-右下角
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=853, y=553)
            time.sleep(0.5)

            # 选择地图-巫毒
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=469, y=70)
            time.sleep(0.5)

            # 选择关卡-第二关
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=401, y=286)
            time.sleep(0.5)

            # 随便公会任务卡组
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=self.handle,
                x={1: 425, 2: 523, 3: 588, 4: 666, 5: 756, 6: 837}[deck],
                y=121)
            time.sleep(0.2)

            # 点击开始
            find = loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[796, 413, 950, 485],
                target_path=RESOURCE_P["common"]["战斗"]["战斗前_开始按钮.png"],
                target_tolerance=0.95,
                target_interval=1,
                target_failed_check=30,
                target_sleep=0.2,
                click=True)
            if not find:
                self.print_warning(text="30s找不到[开始/准备]字样! 创建房间可能失败! 直接reload游戏防止卡死")
                self.reload_game()
                first_time = True
                continue

            # 防止被 [没有带xx卡] or 包满 的提示卡死
            find = match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=RESOURCE_P["common"]["战斗"]["战斗前_系统提示.png"],
                target_tolerance=0.98)
            if find:
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=427, y=353)
                time.sleep(0.5)

            # 刷新ui: 状态文本
            self.print_debug(text="查找火苗标识物, 等待loading完成")

            # 循环查找火苗图标 找到战斗开始
            find = loop_match_p_in_w(
                raw_w_handle=self.handle,
                raw_range=[0, 0, 950, 600],
                target_path=RESOURCE_P["common"]["战斗"]["战斗中_火苗能量.png"],
                target_interval=1,
                target_failed_check=30,
                target_sleep=1,
                click=False)
            if find:
                self.print_debug(text="找到[火苗标识物], 战斗进行中...")
            else:
                self.print_warning(text="30s找不到[火苗标识物]! 进入游戏! 直接reload游戏防止卡死")
                self.reload_game()
                first_time = True
                continue

            # 放人物
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=333, y=333)
            time.sleep(0.05)

            # 休息60s 等待完成
            for i in range(60):
                time.sleep(1)

            # 游戏内退出
            self.action_exit(mode="游戏内退出")


if __name__ == '__main__':
    def f_main():
        faa = FAA(channel="锑食")
        faa.set_config_for_battle(
            stage_id="NO-1-14",
            is_group=False,
            battle_plan_index=0)


    f_main()
