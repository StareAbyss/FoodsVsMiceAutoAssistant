import copy
import json
import time
from datetime import datetime

import numpy as np
import pytz

from function.common.bg_img_match import match_p_in_w, loop_match_p_in_w, loop_match_ps_in_w
from function.common.bg_img_screenshot import capture_image_png
from function.common.overlay_images import overlay_images
from function.core.FAA_ActionInterfaceJump import FAAActionInterfaceJump
from function.core.FAA_ActionQuestReceiveRewards import FAAActionQuestReceiveRewards
from function.core.FAA_Battle import Battle
from function.core.FAA_BattleARoundPreparation import BattleARoundPreparation
from function.core_battle.get_position_in_battle import get_position_card_deck_in_battle, \
    get_position_card_cell_in_battle
from function.globals.extra import EXTRA_GLOBALS
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
    其中部分较麻烦的模块的实现被分散在了其他的类里, 此处只留下了接口以供调用
    """

    def __init__(self, channel="锑食", player=1,
                 character_level=1, is_auto_battle=True, is_auto_pickup=False, random_seed=0,
                 signal_dict=None):

        # 获取窗口句柄
        self.channel = channel  # 在刷新窗口后会需要再重新获取flash的句柄, 故保留
        self.handle = faa_get_handle(channel=self.channel, mode="flash")
        self.handle_browser = faa_get_handle(channel=self.channel, mode="browser")
        self.handle_360 = faa_get_handle(channel=self.channel, mode="360")

        # 外部信号集 用于根据窗口逻辑, 控制UI和整体的Todo类, 做出相应改变
        self.signal_dict = signal_dict
        # 为了单例调试可用
        if self.signal_dict:
            self.signal_print_to_ui = self.signal_dict["print_to_ui"]
            self.signal_dialog = self.signal_dict["dialog"]
            self.signal_todo_end = self.signal_dict["end"]

        # 随机种子
        self.random_seed = random_seed

        """每次战斗中都保持一致的参数"""
        # 角色的index int 1 or 2
        self.player = player
        # 角色的等级 int 1 to 60
        self.character_level = character_level
        # 是否自动战斗 bool
        self.is_auto_battle = is_auto_battle
        # 是否鼠标模拟收集战利品 bool
        self.is_auto_pickup = is_auto_pickup

        """每次战斗都不一样的参数 使用内部函数调用更改"""
        self.stage_info = None
        self.is_main = None
        self.is_group = None
        self.need_key = None
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
        self.object_action_receive_quest_rewards = FAAActionQuestReceiveRewards(faa=self)

        # 界面跳转实例
        self.object_action_interface_jump = FAAActionInterfaceJump(faa=self)

        # 战前战后实例 用于实现战斗前的ban卡, 战斗后的战利品图像截取识别 和 判断战斗正确结束
        self.object_battle_a_round_preparation = BattleARoundPreparation(faa=self)

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

    def check_level(self) -> bool:
        """检测角色等级和关卡等级(调用于输入关卡信息之后)"""
        if self.character_level < self.stage_info["level"]:
            return False
        else:
            return True

    def screen_check_server_boom(self) -> bool:
        """
        检测是不是炸服了
        :return: bool 炸了 True 没炸 False
        """
        find = loop_match_ps_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            template_opts=[
                {
                    "source_range": [350, 275, 600, 360],
                    "template": RESOURCE_P["error"]["登录超时.png"],
                    "match_tolerance": 0.999
                },
                {
                    "source_range": [350, 275, 600, 360],
                    "template": RESOURCE_P["error"]["断开连接.png"],
                    "match_tolerance": 0.999
                },
                {
                    "source_range": [350, 275, 600, 360],
                    "template": RESOURCE_P["error"]["Flash爆炸.png"],
                    "match_tolerance": 0.999
                }
            ],
            return_mode="or",
            match_failed_check=1,
            match_interval=0.2)

        return find

    def screen_get_stage_name(self) -> str:
        """
        在关卡备战界面 获得关卡名字 该函数未完工
        """
        stage_id = "Unknown"  # 默认名称
        img1 = capture_image_png(handle=self.handle, raw_range=[0, 0, 950, 600])[468:484, 383:492, :3]
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
            self, stage_id="NO-1-1", is_group=False, is_main=True, need_key=True,
            deck=1, quest_card="None", ban_card_list=None,
            battle_plan_index=0) -> None:
        """
        :param is_group: 是否组队
        :param is_main: 是否是主要账号(单人为True 双人房主为True)
        :param need_key: 是否使用钥匙
        :param deck:
        :param quest_card:
        :param ban_card_list:
        :param battle_plan_index: 战斗方案的索引
        :param stage_id: 关卡的id
        :return:
        """

        if (ban_card_list is None) or (ban_card_list is ["None"]):
            ban_card_list = []

        self.is_main = is_main
        self.is_group = is_group
        self.need_key = need_key
        self.deck = deck
        self.quest_card = quest_card
        self.ban_card_list = ban_card_list

        # 一旦存在ban卡追加ban掉这几位
        if self.ban_card_list:
            self.ban_card_list.append("冰淇淋")
            self.ban_card_list.append("幻幻鸡")

        # 双倍ban承载 ban软糖
        if "木盘子" in self.ban_card_list:
            self.ban_card_list.append("魔法软糖")
        if "麦芽糖" in self.ban_card_list:
            self.ban_card_list.append("魔法软糖")
        if "苏打气泡" in self.ban_card_list:
            self.ban_card_list.append("魔法软糖")

        def read_json_to_battle_plan():
            battle_plan_list = get_list_battle_plan(with_extension=True)
            battle_plan_path = "{}\\{}".format(
                PATHS["battle_plan"],
                battle_plan_list[battle_plan_index]
            )

            # 自旋锁读写, 防止多线程读写问题
            while EXTRA_GLOBALS.file_is_reading_or_writing:
                time.sleep(0.1)
            EXTRA_GLOBALS.file_is_reading_or_writing = True  # 文件被访问
            with open(file=battle_plan_path, mode="r", encoding="UTF-8") as file:
                data = json.load(file)
            EXTRA_GLOBALS.file_is_reading_or_writing = False  # 文件已解锁
            return data

        self.battle_plan_0 = read_json_to_battle_plan()

        self.stage_info = read_json_to_stage_info(stage_id)

    """战斗开始时的初始化函数"""

    def init_mat_card_position(self) -> None:
        """
        根据关卡名称和可用承载卡，以及游戏内识图到的承载卡取交集，返回承载卡的x-y坐标
        :return: [[x1, y1], [x2, y2],...]
        """

        self.print_info("战斗中识图查找承载卡位置, 开始")

        stage_info = copy.deepcopy(self.stage_info)

        # 本关可用的所有承载卡
        mat_available_list = stage_info["mat_card"]

        # 筛选出所有 有图片资源的卡片 包含变种
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
                    source_handle=self.handle,
                    source_root_handle=self.handle_360,
                    source_range=[150, 0, 950, 600],
                    template=RESOURCE_P["card"]["战斗"][mat_card],
                    match_tolerance=0.99)
                if find:
                    position_list.append([int(150 + find[0]), int(find[1])])
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

        self.print_info("战斗中识图查找承载卡位置, 结果: {}".format(mat_card_list))

    def init_smoothie_card_position(self) -> None:

        self.print_info(text="战斗中识图查找冰沙位置, 开始")

        # 初始化为None
        self.smoothie_position = None

        position = None
        # 查找对应卡片坐标 重复3次
        for i in range(3):
            for j in ["2", "5"]:
                # 需要使用0.99相似度参数 相似度阈值过低可能导致一张图片被识别为两张卡
                find = match_p_in_w(
                    source_handle=self.handle,
                    source_root_handle=self.handle_360,
                    source_range=[150, 0, 950, 600],
                    template=RESOURCE_P["card"]["战斗"][f"冰淇淋-{j}.png"],
                    match_tolerance=0.99)
                if find:
                    position = [150 + int(find[0]), int(find[1])]
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

        self.print_info(text="战斗中识图查找冰沙位置, 结果：{}".format(self.smoothie_position))

    def init_kun_card_position(self) -> None:

        self.print_info(text="战斗中识图查找幻幻鸡位置, 开始")

        # 重新初始化为None
        self.kun_position = None

        # 查找对应卡片坐标 重复3次
        def action_find_card():

            # 筛选出所有 有图片资源的卡片 包含变种
            resource_exist_list = []
            for i in range(20):
                new_card = f"幻幻鸡-{i}.png"
                if new_card in RESOURCE_P["card"]["战斗"].keys():
                    resource_exist_list.append(new_card)

            for try_time in range(3):

                for img_card in resource_exist_list:
                    # 需要使用0.99相似度参数 相似度阈值过低可能导致一张图片被识别为两张卡
                    find = match_p_in_w(
                        source_handle=self.handle,
                        source_root_handle=self.handle_360,
                        source_range=[150, 0, 950, 600],
                        template=RESOURCE_P["card"]["战斗"][img_card],
                        match_tolerance=0.99)
                    if find:
                        return [int(150 + find[0]), int(find[1])]

                # 防止卡片正好被某些特效遮挡, 所以等待一下
                time.sleep(0.1)

            return None

        position = action_find_card()

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

        self.print_info(text="战斗中识图查找幻幻鸡位置, 结果：{}".format(self.kun_position))

    def init_battle_plan_1(self) -> None:
        """
        战斗方案解析器 - 用于根据战斗方案的json和关卡等多种信息, 解析计算为卡片的部署方案 供战斗方案执行器执行
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

            if quest_card != "None":

                # 任务卡 位置
                quest_card_locations = ["6-1", "6-2", "6-3", "6-4", "6-5", "6-6", "6-7"]

                # 遍历删除 方案的放卡中 占用了任务卡摆放的棋盘位置
                list_cell_all = [
                    {**card, "location": list(filter(lambda x: x not in quest_card_locations, card["location"]))}
                    for card in list_cell_all
                ]

                # 计算任务卡的id 最大的卡片id + 1 注意判空!!!
                if list_cell_all:
                    quest_card_id = max(card["id"] for card in list_cell_all) + 1
                else:
                    quest_card_id = 1

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

                # 可能是空列表 即花瓶
                if len(list_cell_all) == 0:
                    # 首位插入
                    list_cell_all.insert(0, dict_quest)
                else:
                    # 第二位插入
                    list_cell_all.insert(1, dict_quest)

            return list_cell_all

        def calculation_card_ban(list_cell_all):
            """步骤二 ban掉某些卡, 依据[卡组信息中的name字段] 和 ban卡信息中的字符串 是否重复"""

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

        def calculation_card_mat(list_cell_all):
            """步骤三 承载卡"""

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

                # 可能是空列表 即花瓶
                if len(list_cell_all) == 0:
                    # 首位插入
                    list_cell_all.insert(0, dict_mat)
                else:
                    # 第二位插入
                    list_cell_all.insert(1, dict_mat)

            return list_cell_all

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

            # 调用ban掉某些卡(不使用该卡)
            list_cell_all = calculation_card_ban(list_cell_all=list_cell_all)

            # 调用计算承载卡 - 因为是直接识别的战斗中的位置, 所以应该放在后面
            list_cell_all = calculation_card_mat(list_cell_all=list_cell_all)

            # 调用冰沙和坤函数 - 因为是直接识别的战斗中的位置, 所以应该放在后面
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

    def battle_a_round_room_preparatory(self):

        """
        房间内战前准备 包括ban卡和选任务卡
        已模块化到外部实现
        :return: 0-正常结束 1-重启本次 2-跳过本次
        """
        return self.object_battle_a_round_preparation.before()

    def battle_a_round_init_battle_plan(self):
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
        self.bp_card = get_position_card_deck_in_battle(handle=self.handle, handle_360=self.handle_360)

        # 3.识图各种卡参数
        self.init_mat_card_position()
        self.init_smoothie_card_position()
        self.init_kun_card_position()

        # 4.计算所有坐标
        self.init_battle_plan_1()

        # 5.铲卡
        if self.is_main:
            self.faa_battle.use_shovel_all()  # 因为有点击序列，所以同时操作是可行的

    def battle_a_round_loots(self):
        """
        战斗结束后, 完成下述流程: 潜在的任务完成黑屏-> 战利品 -> 战斗结算 -> 翻宝箱 -> 回到房间/魔塔会回到其他界面
        已模块化到外部实现
        :return: 输出1 int, 状态码, 0-正常结束 1-重启本次 2-跳过本次, 输出2 None或者dict, 战利品识别结果
        """

        return self.object_battle_a_round_preparation.perform_action_capture_match_for_loots_and_chests()

    def battle_a_round_warp_up(self):

        """
        房间内或其他地方 战斗结束
        :return: 0-正常结束 1-重启本次 2-跳过本次
        """

        return self.object_battle_a_round_preparation.wrap_up()

    """其他非战斗功能"""

    def receive_quest_rewards(self, mode: str) -> None:
        """
        领取任务奖励, 从当前界面开始, 从当前界面结束
        :param mode: "普通任务" "公会任务" "情侣任务" "悬赏任务" "美食大赛" "大富翁"
        :return: None
        """
        return self.object_action_receive_quest_rewards.main(mode=mode)

    def match_quests(self, mode: str, qg_cs=False) -> list:
        """
        获取任务列表 -> 需要的完成的关卡步骤
        :param mode: "公会任务" "情侣任务" "美食大赛"
        :param qg_cs: 公会任务模式下 是否需要跨服
        :return: [{"stage_id":str, "max_times":int, "quest_card":str, "ban_card":None},...]
        """
        # 跳转到对应界面
        if mode == "公会任务":
            self.action_bottom_menu(mode="跳转_公会任务")
            # 点一下 让左边的选中任务颜色消失
            loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["quest_guild"]["ui_quest_list.png"],
                after_sleep=0.2,
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
                        source_handle=self.handle,
                        source_root_handle=self.handle_360,
                        source_range=[100, 125, 410, 500],
                        template=img,
                        match_tolerance=0.995)
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
                                "stage_id": stage_id,
                                "player": [2, 1],
                                "need_key": True,
                                "max_times": 1,
                                "dict_exit": {
                                    "other_time_player_a": [],
                                    "other_time_player_b": [],
                                    "last_time_player_a": ["竞技岛"],
                                    "last_time_player_b": ["竞技岛"]
                                },
                                "deck": None,  # 外部输入
                                "quest_card": quest_card,
                                "ban_card_list": [],
                                "battle_plan_1p": None,  # 外部输入
                                "battle_plan_2p": None,  # 外部输入
                            }
                        )

        if mode == "情侣任务":

            for i in ["1", "2", "3"]:
                # 任务未完成
                find_p = match_p_in_w(
                    source_handle=self.handle,
                    source_root_handle=self.handle_360,
                    source_range=[0, 0, 950, 600],
                    template=RESOURCE_P["quest_spouse"]["NO-{}.png".format(i)],
                    match_tolerance=0.999)
                if find_p:
                    # 遍历任务
                    for quest, img in RESOURCE_P["quest_spouse"][i].items():
                        # 找到任务 加入任务列表
                        find_p = match_p_in_w(
                            source_handle=self.handle,
                            source_root_handle=self.handle_360,
                            source_range=[0, 0, 950, 600],
                            template=img,
                            match_tolerance=0.999)
                        if find_p:
                            quest_list.append(
                                {
                                    "stage_id": quest.split(".")[0],  # 去掉.png
                                    "player": [2, 1],
                                    "need_key": True,
                                    "max_times": 1,
                                    "dict_exit": {
                                        "other_time_player_a": [],
                                        "other_time_player_b": [],
                                        "last_time_player_a": ["竞技岛"],
                                        "last_time_player_b": ["竞技岛"]
                                    },
                                    "deck": None,  # 外部输入
                                    "quest_card": "None",
                                    "ban_card_list": [],
                                    "battle_plan_1p": None,  # 外部输入
                                    "battle_plan_2p": None,  # 外部输入
                                }
                            )

        if mode == "美食大赛":
            y_dict = {0: 359, 1: 405, 2: 448, 3: 491, 4: 534, 5: 570}
            for i in range(6):
                # 先移动到新的一页
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=536, y=y_dict[i])
                time.sleep(0.1)
                for quest, img in RESOURCE_P["quest_food"].items():
                    find_p = match_p_in_w(
                        source_handle=self.handle,
                        source_root_handle=self.handle_360,
                        source_range=[130, 350, 470, 585],
                        template=img,
                        match_tolerance=0.999)

                    if find_p:
                        # 处理解析字符串 格式
                        quest = quest.split(".")[0]  # 去除.png
                        battle_sets = quest.split("_")  # 根据_符号 拆成list

                        # 打什么关卡 文件中: 关卡名称
                        stage_id = battle_sets[0]

                        # 是否组队 文件中: 1 单人 2 组队
                        player = [self.player] if battle_sets[1] == "1" else [2, 1]

                        # 是否使用钥匙 文件中: 0 or 1 -> bool
                        need_key = bool(battle_sets[2])

                        # 任务卡: "None" or 其他
                        quest_card = battle_sets[3]

                        # Ban卡表: "None" or 其他, 多个值用逗号分割
                        ban_card_list = battle_sets[4].split(",")
                        # 如果 ['None'] -> []
                        if ban_card_list == ['None']:
                            ban_card_list = []

                        quest_list.append(
                            {
                                "stage_id": stage_id,
                                "player": player,
                                "need_key": need_key,  # 注意类型转化
                                "max_times": 1,
                                "dict_exit": {
                                    "other_time_player_a": [],
                                    "other_time_player_b": [],
                                    "last_time_player_a": ["竞技岛", "美食大赛领取"],
                                    "last_time_player_b": ["竞技岛", "美食大赛领取"]
                                },
                                "deck": None,  # 外部输入
                                "quest_card": quest_card,
                                "ban_card_list": ban_card_list,
                                "battle_plan_1p": None,  # 外部输入
                                "battle_plan_2p": None,  # 外部输入
                            }
                        )

        # 关闭公会任务列表(红X)
        if mode == "公会任务" or mode == "情侣任务":
            self.action_exit(mode="普通红叉")
        if mode == "美食大赛":
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=888, y=53)
            time.sleep(0.5)

        return quest_list

    def click_refresh_btn(self) -> bool:
        """
        点击360游戏大厅的刷新游戏按钮
        :return: bool 是否成功点击
        """

        # 点击刷新按钮 该按钮在360窗口上
        find = loop_match_p_in_w(
            source_handle=self.handle_360,
            source_root_handle=self.handle_360,
            source_range=[0, 0, 400, 100],
            template=RESOURCE_P["common"]["登录"]["0_刷新.png"],
            match_tolerance=0.9,
            after_sleep=3,
            click=True)

        if not find:
            find = loop_match_p_in_w(
                source_handle=self.handle_360,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 400, 100],
                template=RESOURCE_P["common"]["登录"]["0_刷新_被选中.png"],
                match_tolerance=0.98,
                after_sleep=3,
                click=True)

            if not find:

                find = loop_match_p_in_w(
                    source_handle=self.handle_360,
                    source_root_handle=self.handle_360,
                    source_range=[0, 0, 400, 100],
                    template=RESOURCE_P["common"]["登录"]["0_刷新_被点击.png"],
                    match_tolerance=0.98,
                    after_sleep=3,
                    click=True)

                if not find:
                    self.print_error(text="未找到360大厅刷新游戏按钮, 可能导致一系列问题...")
                    return False
        return True

    def reload_game(self) -> None:

        def try_enter_server_4399():
            # 4399 进入服务器
            my_result = match_p_in_w(
                source_handle=self.handle_browser,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 2000, 2000],
                template=RESOURCE_P["common"]["登录"]["1_我最近玩过的服务器_4399.png"],
                match_tolerance=0.9
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
                source_handle=self.handle_browser,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 2000, 2000],
                template=RESOURCE_P["common"]["登录"]["1_我最近玩过的服务器_QQ空间.png"],
                match_tolerance=0.9
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
                source_handle=self.handle_browser,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 2000, 2000],
                template=RESOURCE_P["common"]["登录"]["1_我最近玩过的服务器_QQ游戏大厅.png"],
                match_tolerance=0.9
            )
            if my_result:
                # 点击进入服务器
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle_browser,
                    x=my_result[0],
                    y=my_result[1] + 30)
                return True
            return False

        def main():
            while True:

                # 点击刷新按钮 该按钮在360窗口上
                self.print_debug(text="[刷新游戏] 点击刷新按钮...")
                self.click_refresh_btn()

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
                    self.print_debug(
                        text="[刷新游戏] 未找到进入服务器, 可能 1.QQ空间需重新登录 2.360X4399微端 3.意外情况")

                    result = loop_match_p_in_w(
                        source_handle=self.handle_browser,
                        source_root_handle=self.handle_360,
                        source_range=[0, 0, 2000, 2000],
                        template=RESOURCE_P["common"]["用户自截"]["空间服登录界面_{}P.png".format(self.player)],
                        match_tolerance=0.95,
                        match_interval=0.5,
                        match_failed_check=5,
                        after_sleep=5,
                        click=True)
                    if result:
                        self.print_debug(text="[刷新游戏] 找到QQ空间服一键登录, 正在登录")
                    else:
                        self.print_debug(text="[刷新游戏] 未找到QQ空间服一键登录, 可能 1.360X4399微端 2.意外情况, 继续")

                """查找大地图确认进入游戏"""
                self.print_debug(text="[刷新游戏] 循环识图中, 以确认进入游戏...")
                # 更严格的匹配 防止登录界面有相似图案组合
                result = loop_match_ps_in_w(
                    source_handle=self.handle_browser,
                    source_root_handle=self.handle_360,
                    template_opts=[
                        {
                            "source_range": [840, 525, 2000, 2000],
                            "template": RESOURCE_P["common"]["底部菜单"]["跳转.png"],
                            "match_tolerance": 0.98,
                        }, {
                            "source_range": [610, 525, 2000, 2000],
                            "template": RESOURCE_P["common"]["底部菜单"]["任务.png"],
                            "match_tolerance": 0.98,
                        }, {
                            "source_range": [890, 525, 2000, 2000],
                            "template": RESOURCE_P["common"]["底部菜单"]["后退.png"],
                            "match_tolerance": 0.98,
                        }
                    ],
                    return_mode="and",
                    match_failed_check=30,
                    match_interval=1
                )

                if result:
                    self.print_debug(text="[刷新游戏] 循环识图成功, 确认进入游戏! 即将刷新Flash句柄")

                    # 重新获取句柄, 此时游戏界面的句柄已经改变
                    self.handle = faa_get_handle(channel=self.channel, mode="flash")

                    # [4399] [QQ空间]关闭健康游戏公告
                    self.print_debug(text="[刷新游戏] [4399] [QQ空间] 尝试关闭健康游戏公告")
                    loop_match_p_in_w(
                        source_handle=self.handle,
                        source_root_handle=self.handle_360,
                        source_range=[0, 0, 950, 600],
                        template=RESOURCE_P["common"]["登录"]["3_健康游戏公告_确定.png"],
                        match_tolerance=0.97,
                        match_failed_check=5,
                        after_sleep=1,
                        click=True)

                    self.print_debug(text="[刷新游戏] 尝试关闭每日必充界面")
                    # [每天第一次登陆] 每日必充界面关闭
                    loop_match_p_in_w(
                        source_handle=self.handle,
                        source_root_handle=self.handle_360,
                        source_range=[0, 0, 950, 600],
                        template=RESOURCE_P["common"]["登录"]["4_退出每日必充.png"],
                        match_tolerance=0.99,
                        match_failed_check=3,
                        after_sleep=1,
                        click=True)
                    self.random_seed += 1

                    self.print_debug(text="[刷新游戏] 已完成")

                    return
                else:
                    self.print_warning(text="[刷新游戏] 查找大地图失败, 点击服务器后未能成功进入游戏, 刷新重来")

        main()

    def sign_in(self) -> None:

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
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["签到"]["每日签到_确定.png"],
                match_tolerance=0.99,
                match_failed_check=1,
                after_sleep=1,
                click=True)

            self.action_exit(mode="普通红叉")

        def sign_in_food_activity():
            """美食活动"""

            self.action_top_menu(mode="美食活动")

            loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["签到"]["美食活动_确定.png"],
                match_tolerance=0.99,
                match_failed_check=1,
                after_sleep=1,
                click=True)

            self.action_exit(mode="普通红叉")

        def sign_in_tarot():
            """塔罗寻宝"""
            self.action_top_menu(mode="塔罗寻宝")

            loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["签到"]["塔罗寻宝_确定.png"],
                match_tolerance=0.99,
                match_failed_check=1,
                after_sleep=1,
                click=True)

            loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["签到"]["塔罗寻宝_退出.png"],
                match_tolerance=0.99,
                match_failed_check=1,
                after_sleep=1,
                click=True)

        def sign_in_pharaoh():
            """法老宝藏"""
            self.action_top_menu(mode="法老宝藏")

            find = loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["签到"]["法老宝藏_确定.png"],
                match_tolerance=0.99,
                match_failed_check=1,
                after_sleep=1,
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
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[73, 31, 173, 78],
                template=RESOURCE_P["common"]["签到"]["公会会长_发布任务.png"],
                match_tolerance=0.99,
                match_failed_check=1,
                after_sleep=1,
                click=True)
            if find:
                loop_match_p_in_w(
                    source_handle=self.handle,
                    source_root_handle=self.handle_360,
                    source_range=[422, 415, 544, 463],
                    template=RESOURCE_P["common"]["签到"]["公会会长_发布任务_确定.png"],
                    match_tolerance=0.99,
                    match_failed_check=1,
                    after_sleep=3,
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

        return main()

    def fed_and_watered(self) -> None:
        """公会施肥浇水功能"""

        def goto_guild_and_in_guild():
            """
            :return: 是否出现bug
            """

            self.action_bottom_menu(mode="公会")

            find = loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[760, 35, 860, 80],
                template=RESOURCE_P["quest_guild"]["ui_guild.png"],
                match_tolerance=0.95,
                match_failed_check=3,
                after_sleep=1,
                click=False)

            return not find

        def exit_to_guild_page_and_in_guild():
            """
            :return: 是否出现bug
            """

            # 点X回退一次
            self.action_exit(mode="普通红叉", raw_range=[835, 30, 875, 80])

            find = loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[760, 35, 860, 80],
                template=RESOURCE_P["quest_guild"]["ui_guild.png"],
                match_tolerance=0.95,
                match_failed_check=3,
                after_sleep=1,
                click=False)
            return not find

        def from_guild_to_quest_guild():
            """进入任务界面, 正确进入就跳出循环"""
            for count_time in range(50):

                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=745, y=430)
                time.sleep(0.001)

                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=700, y=350)
                time.sleep(2)

                find = loop_match_p_in_w(
                    source_handle=self.handle,
                    source_root_handle=self.handle_360,
                    source_range=[215, 95, 308, 133],
                    template=RESOURCE_P["quest_guild"]["ui_quest_list.png"],
                    match_tolerance=0.95,
                    match_failed_check=1,
                    after_sleep=0.5,
                    click=False
                )
                if find:
                    # 次数限制内完成 进入施肥界面
                    return True
            # 次数限制内失败 进入施肥界面
            return False

        def from_guild_to_guild_garden():
            """进入施肥界面, 正确进入就跳出循环"""
            for count_time in range(50):

                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=745, y=430)
                time.sleep(0.001)

                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=800, y=350)
                time.sleep(2)

                find = loop_match_p_in_w(
                    source_handle=self.handle,
                    source_root_handle=self.handle_360,
                    source_range=[400, 30, 585, 80],
                    template=RESOURCE_P["quest_guild"]["ui_fed.png"],
                    match_tolerance=0.95,
                    match_failed_check=2,
                    after_sleep=0.5,
                    click=False
                )
                if find:
                    # 次数限制内完成 进入施肥界面
                    return True
            # 次数限制内失败 进入施肥界面
            return False

        def switch_guild_garden_by_try_times(try_time):
            """根据目前尝试次数, 到达不同的公会"""
            if try_time != 0:

                # 点击全部工会
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=798, y=123)
                time.sleep(1)

                # 跳转到最后
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=843, y=305)
                time.sleep(1)

                # 以倒数第二页从上到下为1-4, 第二页为5-8次尝试对应的公会 以此类推
                for i in range((try_time - 1) // 4 + 1):
                    # 向上翻的页数
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=843, y=194)
                    time.sleep(1)

                # 点第几个
                my_dict = {1: 217, 2: 244, 3: 271, 4: 300}
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=810,
                    y=my_dict[(try_time - 1) % 4 + 1])
                time.sleep(1)

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
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[835, 35, 875, 75],
                template=RESOURCE_P["common"]["退出.png"],
                match_tolerance=0.95,
                match_failed_check=7,
                after_sleep=1,
                click=False
            )
            self.print_debug(text=f"{try_time + 1}/100 次尝试, 浇水后, 已确认无任务完成黑屏")

            # 施肥一次
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=785, y=418)
            time.sleep(1)

            # 等待一下 确保没有完成的黑屏
            loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[835, 35, 875, 75],
                template=RESOURCE_P["common"]["退出.png"],
                match_tolerance=0.95,
                match_failed_check=7,
                after_sleep=2,
                click=False)
            self.print_debug(text=f"{try_time + 1}/100 次尝试, 施肥后, 已确认无任务完成黑屏")

        def fed_and_watered_one_action(try_time):
            """
            :return: bool is completed  , bool is bugged
            """
            # 进入任务界面
            if not from_guild_to_quest_guild():
                return False, True

            # 检测施肥任务完成情况 任务是进行中的话为True
            find = loop_match_ps_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                template_opts=[
                    {
                        "source_range": [75, 80, 430, 500],
                        "template": RESOURCE_P["quest_guild"]["fed_0.png"],
                        "match_tolerance": 0.98
                    }, {
                        "source_range": [75, 80, 430, 500],
                        "template": RESOURCE_P["quest_guild"]["fed_1.png"],
                        "match_tolerance": 0.98
                    }, {
                        "source_range": [75, 80, 430, 500],
                        "template": RESOURCE_P["quest_guild"]["fed_2.png"],
                        "match_tolerance": 0.98,
                    }, {
                        "source_range": [75, 80, 430, 500],
                        "template": RESOURCE_P["quest_guild"]["fed_3.png"],
                        "match_tolerance": 0.98,
                    }
                ],
                return_mode="or",
                match_failed_check=2)

            # 退出任务界面
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=854, y=55)
            time.sleep(0.5)

            if not find:
                self.print_debug(text="已完成公会浇水施肥, 尝试次数: {}/100".format(try_time))
                return True, False
            else:
                # 进入施肥界面, 正确进入就跳出循环
                if not from_guild_to_guild_garden():
                    return False, True

                # 根据目前尝试次数, 到达不同的公会
                switch_guild_garden_by_try_times(try_time=try_time)

                # 完成素质三连并退出公会花园界面
                do_something_and_exit(try_time=try_time)

                if exit_to_guild_page_and_in_guild():
                    return False, True

                return False, False

        def fed_and_watered_multi_action():
            """
            :return: 完成的尝试次数, 是否是bug
            """
            # 循环到任务完成
            try_time = 0
            while True:

                completed_flag, is_bug = fed_and_watered_one_action(try_time)
                try_time += 1

                if try_time == 100 or is_bug:
                    # 次数过多, 或 遇上bug
                    return completed_flag, try_time, True

                if completed_flag:
                    return completed_flag, try_time, False

        def fed_and_watered_main():

            self.signal_print_to_ui.emit(f"[浇水 施肥 摘果 领取] [{self.player}p] 开始执行...")
            self.print_debug(text="开始公会浇水施肥")

            for reload_time in range(1, 4):

                # 进入公会
                is_bug = goto_guild_and_in_guild()
                if is_bug:
                    if reload_time != 3:
                        self.signal_print_to_ui.emit(
                            f"[浇水 施肥 摘果 领取] [{self.player}p] 锑食卡住了! 进入工会页失败... 刷新再试({reload_time}/3)")
                        self.reload_game()
                        continue
                    else:
                        self.signal_print_to_ui.emit(
                            f"[浇水 施肥 摘果 领取] [{self.player}p] 锑食卡住了! 进入工会页失败... 刷新跳过({reload_time}/3)")
                        self.reload_game()
                        break

                # 循环到任务完成或出现bug或超次数
                completed, try_time, is_bug = fed_and_watered_multi_action()

                if is_bug:
                    if reload_time != 3:
                        self.signal_print_to_ui.emit(
                            f"[浇水 施肥 摘果 领取] [{self.player}p] 锑食卡住 "
                            f"本轮循环施肥尝试:{try_time}次 刷新再试({reload_time}/3)")
                        self.reload_game()
                        continue
                    else:
                        self.signal_print_to_ui.emit(
                            f"[浇水 施肥 摘果 领取] [{self.player}p] 锑食卡住 "
                            f"本轮循环施肥尝试:{try_time}次  刷新跳过({reload_time}/3)")
                        self.reload_game()
                        break

                if try_time == 100:
                    self.signal_print_to_ui.emit(
                        f"[浇水 施肥 摘果 领取] [{self.player}p] 尝试100次, 直接刷新跳过")
                    self.reload_game()
                    break

                if completed:
                    # 正常完成
                    self.signal_print_to_ui.emit(
                        f"[浇水 施肥 摘果 领取] [{self.player}p] 正确完成 ~")
                    # 退出工会
                    self.action_exit(mode="普通红叉")
                    self.receive_quest_rewards(mode="公会任务")
                    break

        fed_and_watered_main()

    def use_items_consumables(self) -> None:
        self.print_debug(text="开启使用物品功能")

        # 打开背包
        self.print_debug(text="打开背包")
        self.action_bottom_menu(mode="背包")
        self.signal_print_to_ui.emit(text=f"[使用绑定消耗品] [{self.player}P] 背包图标可能需要加载, 等待10s")
        time.sleep(10)

        # 四次循环查找所有正确图标 不需要升到最顶, 打开背包会自动重置
        for i in range(4):

            self.print_debug(text="第{}页物品".format(i + 1))

            # 第一次以外, 下滑4*5次
            if i != 0:
                for j in range(5):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=920, y=422)
                    time.sleep(0.2)

            for item_name, item_image in RESOURCE_P["item"]["背包"].items():

                self.print_debug(text="物品:{}本页 开始查找".format(item_name))

                # 添加绑定角标
                item_image = overlay_images(
                    img_background=item_image,
                    img_overlay=RESOURCE_P["item"]["物品-绑定角标.png"])

                while True:

                    # 在限定范围内 找红叉点掉
                    loop_match_p_in_w(
                        source_handle=self.handle,
                        source_root_handle=self.handle_360,
                        source_range=[0, 0, 750, 300],
                        template=RESOURCE_P["common"]["退出.png"],
                        match_tolerance=0.98,
                        match_interval=0.2,
                        match_failed_check=0,
                        after_sleep=0.5,
                        click=True)

                    # 在限定范围内 找物品
                    find = match_p_in_w(
                        source_handle=self.handle,
                        source_range=[466, 88, 910, 435],
                        template=item_image,
                        template_name=item_name,
                        mask=RESOURCE_P["item"]["物品-掩模-不绑定.png"],
                        match_tolerance=0.99,
                        test_print=True)

                    if find:
                        # 点击物品图标 以使用
                        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=find[0] + 466, y=find[1] + 88)

                        # 在限定范围内 找到并点击物品 使用它
                        find = loop_match_p_in_w(
                            source_handle=self.handle,
                            source_root_handle=self.handle_360,
                            source_range=[466, 86, 950, 500],
                            template=RESOURCE_P["item"]["物品-背包-使用.png"],
                            match_tolerance=0.98,
                            match_interval=0.2,
                            match_failed_check=1,
                            after_sleep=0.5,
                            click=True)

                        # 鼠标选中 使用按钮 会有色差, 第一次找不到则再来一次
                        if not find:
                            loop_match_p_in_w(
                                source_handle=self.handle,
                                source_root_handle=self.handle_360,
                                source_range=[466, 86, 950, 500],
                                template=RESOURCE_P["item"]["物品-背包-使用-被选中.png"],
                                match_tolerance=0.98,
                                match_interval=0.2,
                                match_failed_check=1,
                                after_sleep=0.5,
                                click=True)

                    else:
                        # 没有找到对应物品 skip
                        break

                self.print_debug(text="物品:{}本页 已全部找到".format(item_name))

        # 关闭背包
        self.action_exit(mode="普通红叉")

    def use_items_double_card(self, max_times) -> None:

        def is_saturday_or_sunday():
            # 设置北京时区
            beijing_tz = pytz.timezone('Asia/Shanghai')

            # 获取当前的北京时间
            now_in_beijing = datetime.now(beijing_tz)

            # 获取今天是星期几（0=星期一，1=星期二，...，5=星期六，6=星期日）
            weekday = now_in_beijing.weekday()

            # 判断今天是否是星期六或星期日
            if weekday == 5:
                return True
            elif weekday == 6:
                return True
            else:
                return False

        def loop_use_double_card():
            used_success = 0

            # 四次循环查找所有正确图标 升到最顶, 不需要, 打开背包会自动重置
            for i in range(4):

                self.print_debug(text=f"[使用双暴卡] 第{i + 1}页物品 开始查找")

                # 第一次以外, 下滑4*5次
                if i != 0:
                    for j in range(5):
                        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=920, y=422)
                        time.sleep(0.2)

                while True:

                    if used_success == max_times:
                        break

                    # 在限定范围内 找物品
                    find = loop_match_p_in_w(
                        source_handle=self.handle,
                        source_root_handle=self.handle_360,
                        source_range=[466, 86, 891, 435],
                        template=RESOURCE_P["item"]["物品-双暴卡.png"],
                        match_tolerance=0.98,
                        match_interval=0.2,
                        match_failed_check=1.5,
                        after_sleep=0.05,
                        click=True)

                    if find:
                        self.print_debug(text="[使用双暴卡] 成功使用一张双暴卡")
                        used_success += 1

                        # 在限定范围内 找到并点击物品 使用它
                        find = loop_match_p_in_w(
                            source_handle=self.handle,
                            source_root_handle=self.handle_360,
                            source_range=[466, 86, 950, 500],
                            template=RESOURCE_P["item"]["物品-背包-使用.png"],
                            match_tolerance=0.95,
                            match_interval=0.2,
                            match_failed_check=1,
                            after_sleep=0.5,
                            click=True)

                        # 鼠标选中 使用按钮 会有色差, 第一次找不到则再来一次
                        if not find:
                            loop_match_p_in_w(
                                source_handle=self.handle,
                                source_root_handle=self.handle_360,
                                source_range=[466, 86, 950, 500],
                                template=RESOURCE_P["item"]["物品-背包-使用-被选中.png"],
                                match_tolerance=0.90,
                                match_interval=0.2,
                                match_failed_check=1,
                                after_sleep=0.5,
                                click=True)

                    else:
                        # 没有找到对应物品 skip
                        self.print_debug(text=f"[使用双暴卡] 第{i + 1}页物品 未找到")
                        break

                if used_success == max_times:
                    break

            if used_success == max_times:
                self.print_debug(text=f"[使用双暴卡] 成功使用{used_success}张双暴卡")
            else:
                self.print_debug(text=f"[使用双暴卡] 成功使用{used_success}张双暴卡 数量不达标")

        def main():
            self.print_debug(text="[使用双暴卡] 开始")

            if is_saturday_or_sunday():
                self.signal_print_to_ui.emit(text="[使用双暴卡] 今天是星期六 / 星期日, 跳过")
                return

            # 打开背包
            self.print_debug(text="打开背包")
            self.action_bottom_menu(mode="背包")
            self.signal_print_to_ui.emit(text="[使用双暴卡] 背包图标可能需要加载, 等待10s")
            time.sleep(10)

            loop_use_double_card()

            # 关闭背包
            self.action_exit(mode="普通红叉")

        main()

    def input_level_2_password_and_gift_flower(self, password):
        """如果背包已满 通过兑换暗晶激活二级密码就用不了了! 那么 用缘分树送花给是最稳当的!"""
        # 打开缘分树界面
        self.print_debug(text="跳转到缘分树界面")
        self.action_bottom_menu(mode="跳转_缘分树")
        time.sleep(1)

        # 点击到倒数第二页 以确保目标不会已经满魅力 为防止极端情况最后一页只有一个人且是自己的情况发生 故不选倒数第一页
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=774, y=558)
        time.sleep(1)
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=628, y=558)
        time.sleep(1)

        # 点击排名第一的人
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=500, y=300)
        time.sleep(1)

        # 点击送花按钮
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=50, y=260)
        time.sleep(1)

        # 选择礼卷
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=500, y=300)
        time.sleep(1)

        # 点击送出
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=500, y=400)
        time.sleep(1)

        # 输入二级密码
        for key in password:
            T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=self.handle, key=key)
            time.sleep(0.5)
        time.sleep(1)

        # 确定二级密码
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=435, y=388)
        time.sleep(1)

        # 选择免费送花
        # T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=350, y=300)
        # time.sleep(1)

        # 点击送出
        # T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=500, y=400)
        # time.sleep(1)

        # 退出送花
        for i in range(2):
            self.action_exit(mode="普通红叉")
            time.sleep(1)

    def get_dark_crystal(self):
        # 打开公会副本界面
        self.print_debug(text="跳转到工会副本界面")
        self.action_bottom_menu(mode="跳转_公会副本")

        # 打开暗晶商店
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=800, y=485)
        time.sleep(1)

        # 进入暗晶兑换
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=180, y=70)
        time.sleep(1)

        # 3x3次点击 确认兑换
        for i in range(3):
            for location in [[405, 190], [405, 320], [860, 190]]:
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=location[0], y=location[1])
                # 这个破商店点快了兑换不了
                time.sleep(2)

        # 退出商店界面
        for i in range(2):
            self.action_exit(mode="普通红叉")

    def delete_items(self):
        """用于删除多余的技能书类消耗品, 使用前需要输入二级或无二级密码"""

        self.print_debug(text="开启删除物品高危功能")

        # 打开背包
        self.print_debug(text="打开背包")
        self.action_bottom_menu(mode="背包")

        # 点击到物品栏目
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=777, y=65)
        time.sleep(1)

        self.signal_print_to_ui.emit(text="[删除物品] 背包图标可能需要加载, 等待10s")
        time.sleep(10)

        # 点击整理物品按钮
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=905, y=475)
        time.sleep(2)

        # 点击删除物品按钮
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=845, y=475)
        time.sleep(1)

        for i_name, i_image in RESOURCE_P["item"]["背包_道具_需删除的"].items():

            # 在限定范围内 找物品
            find = match_p_in_w(
                source_handle=self.handle,
                source_range=[466, 88, 910, 435],
                template=i_image,
                template_name=i_name,
                mask=RESOURCE_P["item"]["物品-掩模-不绑定.png"],
                match_tolerance=0.99,
                test_print=True)

            if find:
                # 点击物品图标 以删除
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=find[0] + 466, y=find[1] + 88)

                # 点击确定 删除按钮
                loop_match_p_in_w(
                    source_handle=self.handle,
                    source_root_handle=self.handle_360,
                    source_range=[425, 339, 450, 367],
                    template=RESOURCE_P["common"]["通用_确定.png"],
                    match_tolerance=0.95,
                    match_interval=0.2,
                    match_failed_check=2,
                    after_sleep=2,
                    click=True)

                # 鼠标选中 使用按钮 会有色差, 第一次找不到则再来一次
                if not find:
                    loop_match_p_in_w(
                        source_handle=self.handle,
                        source_root_handle=self.handle_360,
                        source_range=[466, 86, 950, 500],
                        template=RESOURCE_P["item"]["通用_确定_被选中.png"],
                        match_tolerance=0.95,
                        match_interval=0.2,
                        match_failed_check=2,
                        after_sleep=2,
                        click=True)

                self.print_info(f"物品:{i_name} 已确定删除该物品...")

        # 点击整理物品按钮
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=905, y=475)
        time.sleep(2)

        self.print_debug(text="第一页的指定物品已全部删除!")

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
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[796, 413, 950, 485],
                template=RESOURCE_P["common"]["战斗"]["战斗前_开始按钮.png"],
                match_tolerance=0.95,
                match_interval=1,
                match_failed_check=30,
                after_sleep=0.2,
                click=True)
            if not find:
                self.print_warning(text="30s找不到[开始/准备]字样! 创建房间可能失败! 直接reload游戏防止卡死")
                self.reload_game()
                first_time = True
                continue

            # 防止被 [没有带xx卡] or 包满 的提示卡死
            find = match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["战斗"]["战斗前_系统提示.png"],
                match_tolerance=0.98)
            if find:
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=427, y=353)
                time.sleep(0.5)

            # 刷新ui: 状态文本
            self.print_debug(text="查找火苗标识物, 等待loading完成")

            # 循环查找火苗图标 找到战斗开始
            find = loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["战斗"]["战斗中_火苗能量.png"],
                match_interval=1,
                match_failed_check=30,
                after_sleep=1,
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
        faa = FAA(channel="锑食-微端")
        faa.delete_items()


    f_main()
