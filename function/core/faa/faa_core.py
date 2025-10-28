import copy
import json
import os
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING

import pytz

from function.common.bg_img_match import match_p_in_w, loop_match_p_in_w, loop_match_ps_in_w, match_all_p_in_w
from function.common.bg_img_screenshot import capture_image_png, png_cropping
from function.common.get_system_dpi import get_window_position, get_system_dpi
from function.common.image_processing.overlay_images import overlay_images
from function.common.process_manager import close_software_by_title, get_path_and_sub_titles, \
    close_all_software_by_name, start_software_with_args
from function.core.my_crypto import decrypt_data
from function.core_battle.get_location_in_battle import get_location_card_deck_in_battle
from function.globals import g_resources, SIGNAL, EXTRA
from function.globals.g_resources import RESOURCE_P
from function.globals.get_paths import PATHS
from function.globals.location_card_cell_in_battle import COORDINATE_CARD_CELL_IN_BATTLE
from function.globals.log import CUS_LOGGER
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.gat_handle import faa_get_handle
from function.scattered.match_ocr_text.get_food_quest_by_ocr import food_match_ocr_text, extract_text_from_images
from function.scattered.match_ocr_text.text_to_battle_info import food_texts_to_battle_info
from function.scattered.read_json_to_stage_info import read_json_to_stage_info

if TYPE_CHECKING:
    from function.core.faa.faa_mix import FAA


class FAABase:
    """
    FAA类是项目的核心类
    用于封装 [所有对单个游戏窗口进行执行的操作]
    其中部分较麻烦的模块的实现被分散在了其他的类里, 此处只留下了接口以供调用
    """

    def __init__(self: "FAA", channel: str = "锑食", player: int = 1, character_level: int = 80,
                 is_auto_battle: bool = True, is_auto_pickup: bool = False,
                 QQ_login_info=None, extra_sleep=None,opt=None,the_360_lock=None, random_seed: int = 0):

        # 获取窗口句柄
        self.channel = channel  # 在刷新窗口后会需要再重新获取flash的句柄, 故保留
        self.handle = faa_get_handle(channel=self.channel, mode="flash")
        self.handle_browser = faa_get_handle(channel=self.channel, mode="browser")
        self.handle_360 = faa_get_handle(channel=self.channel, mode="360")
        self.QQ_login_info = QQ_login_info
        self.extra_sleep = extra_sleep  # dict 包含部分参数的包
        self.opt = opt
        self.the_360_lock = the_360_lock
        """
        每次战斗中都保持一致的参数
        """

        self.player: int = player  # 角色的index 1 or 2
        self.character_level: int = character_level  # 角色的等级 1 to 60
        self.is_auto_battle: bool = is_auto_battle  # 是否自动战斗
        self.is_auto_pickup: bool = is_auto_pickup  # 是否鼠标模拟收集战利品
        self.random_seed: int = random_seed  # 随机种子
        self.bp_cell = COORDINATE_CARD_CELL_IN_BATTLE  # 调用战斗中 格子位置 字典 bp -> battle location

        file_name = os.path.join(PATHS["config"], "card_type.json")
        with open(file=file_name, mode='r', encoding='utf-8') as file:
            self.card_types = json.load(file)

        """
        每次战斗都不一样的参数 使用内部函数调用更改
        """

        self.stage_info = None
        self.is_main = None
        self.is_group = None
        self.need_key = None
        self.auto_carry_card = None
        self.deck = None
        self.quest_card = None
        self.ban_card_list = None
        self.max_card_num = None
        self.battle_plan = None  # 读取自json的初始战斗方案
        self.battle_plan_tweak = None  # 读取自json的战斗微调方案
        self.battle_mode = None

        """
        每次战斗运行中获取的功能参数
        """

        self.banned_card_index = None  # 初始化战斗中 成功ban掉的卡片的卡组索引号 1开头和游戏对应
        self.bp_card = None  # 初始化战斗中 卡片位置 字典 bp -> battle location
        self.mat_cards_info: list[dict] | None = None  # 承载卡位置
        self.smoothie_info = None  # 冰沙位置
        self.kun_cards_info: list[dict] | None = None  # 坤位置 也用于标记本场战斗是否需要激活坤函数
        self.battle_plan_card = []  # 经过处理后的战斗方案卡片部分, 由战斗类相关动作函数直接调用, 其中的各种操作都包含坐标
        self.battle_lock = threading.Lock()  # 战斗放卡锁，保证同一时间一个号里边的特殊放卡及正常放卡只有一种放卡在操作

        # ---------- 战斗专用私有属性 - 动态 ----------

        self.is_used_key = False
        self.fire_elemental_1000 = False
        self.smoothie_usable = 1
        self.wave = 0
        self.start_time = 0
        self.player_locations = []  # 战斗开始放人物的 位置代号
        self.shovel_locations = []  # 放铲子的 位置代号
        self.shovel_coordinates = []  # 放铲子的 位置坐标

        # ---------- 战斗专用私有属性 - 静态 ----------

        self.click_sleep = 1 / EXTRA.CLICK_PER_SECOND * 2.2
        # 自动拾取的格子
        self.auto_collect_cells = [
            "1-1", "2-1", "3-1", "4-1", "5-1", "6-1", "7-1", "8-1", "9-1",
            "1-2", "2-2", "3-2", "4-2", "5-2", "6-2", "7-2", "8-2", "9-2",
            "1-3", "2-3", "3-3", "4-3", "5-3", "6-3", "7-3", "8-3", "9-3",
            "1-4", "2-4", "3-4", "4-4", "5-4", "6-4", "7-4", "8-4", "9-4",
            "1-5", "2-5", "3-5", "4-5", "5-5", "6-5", "7-5", "8-5", "9-5",
            "1-6", "2-6", "3-6", "4-6", "5-6", "6-6", "7-6", "8-6", "9-6",
            "1-7", "2-7", "3-7", "4-7", "5-7", "6-7", "7-7", "8-7", "9-7"
        ]
        # 自动拾取的坐标
        self.auto_collect_cells_coordinate = [self.bp_cell[i] for i in self.auto_collect_cells]

    def print_debug(self: "FAA", text, player=None):
        """FAA类中的 log debug 包含了player信息"""
        if not player:
            player = self.player
        CUS_LOGGER.debug("[{}P] {}".format(player, text))

    def print_info(self: "FAA", text, player=None):
        """FAA类中的 log print 包含了player信息"""
        if not player:
            player = self.player
        CUS_LOGGER.info("[{}P] {}".format(player, text))

    def print_warning(self: "FAA", text, player=None):
        """FAA类中的 log warning 包含了player信息"""
        if not player:
            player = self.player
        CUS_LOGGER.warning("[{}P] {}".format(player, text))

    def print_error(self: "FAA", text, player=None):
        """FAA类中的 log error 包含了player信息"""
        if not player:
            player = self.player
        CUS_LOGGER.error("[{}P] {}".format(player, text))

    """"对flash游戏界面或自身参数的最基础 [检测]"""

    def check_level(self: "FAA") -> bool:
        """
        检测角色等级和关卡等级
        调用于输入关卡信息之后
        """
        if self.character_level < self.stage_info["level"]:
            return False
        else:
            return True

    def check_stage_id_is_true(self: "FAA") -> bool:
        """
        检查关卡ID是否合法, id指的是 FAA内的模式标识. b_id为关卡的战斗用地图信息id.
        模式标识: 用于上传到米苏物流等用途.
        战斗标识: 默认复制自模式标识, 如果为自建房, 则来自用户的输入, 之后还会被关卡名称的OCR做二次修正.
        """

        if self.stage_info["id"] not in EXTRA.TRUE_STAGE_ID and self.stage_info["id"] != "CU-0-0":
            return False
        if self.stage_info["b_id"] not in EXTRA.TRUE_STAGE_ID:
            return False
        return True

    def check_stage_is_active(self: "FAA") -> bool:
        """关卡是否保持激活"""

        # 拆成数组["关卡类型","地图id","关卡id"]
        stage_list = self.stage_info["id"].split("-")
        stage_0 = stage_list[0]  # type

        if stage_0 == "CZ":
            # Chinese Zodiac 生肖关卡, 特殊关卡.
            # 北京时间(注意时区) 周4567的 晚上7点到7点半可以进入
            # 先不做星期检测, 只做时间段检测, 节假日比较迷惑
            beijing_tz = pytz.timezone('Asia/Shanghai')
            now = datetime.now(beijing_tz)
            return now.hour == 19 and 0 <= now.minute < 30

        if stage_0 == "WB":
            # 世界boss 每天00:05 - 23:50 开放
            beijing_tz = pytz.timezone('Asia/Shanghai')
            now = datetime.now(beijing_tz)
            if now.hour == 23 and now.minute >= 50:
                return False
            if now.hour == 00 and now.minute <= 5:
                return False
            return True

        return True

    def check_not_doing(self: "FAA",c_opt):
        """查漏补缺"""

        CUS_LOGGER.debug(f"[{self.player}] [查漏补缺] 开始")
        CUS_LOGGER.debug(f"[{self.player}] [查漏补缺] 检查签到开始")
        self.action_top_menu(mode="每日签到")

        find = loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=[0, 0, 950, 600],
            template=RESOURCE_P["common"]["签到"]["每日签到_确定.png"],
            match_tolerance=0.99,
            match_failed_check=5,
            after_sleep=1,
            click=True)

        if find:
            # 点击下面四个奖励
            CUS_LOGGER.warning(f"[{self.player}] [查漏补缺] 检查到漏签！！现已补签")
            time.sleep(1)
            find = loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["签到"]["每日签到_确定.png"],
                match_tolerance=0.99,
                match_failed_check=5,
                after_sleep=1,
                click=True)
            if find:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                SIGNAL.DIALOG.emit(
                    "查漏补缺报告",
                    f"{self.player}P因背包爆满,查漏补缺[每日签到]失败!\n"
                    f"出错时间:{current_time}")
        else:
            CUS_LOGGER.debug(f"[{self.player}] [查漏补缺] 未检查到漏签,非常好")
        CUS_LOGGER.debug(f"[{self.player}] [查漏补缺] 检查签到结束")
        self.action_exit(mode="普通红叉")
        time.sleep(1)
        CUS_LOGGER.debug(f"[{self.player}] [查漏补缺] 检查悬赏开始")
        reputation_status,reputation_now=self.check_task_of_bounty()
        CUS_LOGGER.debug(f"[{self.player}] [查漏补缺] 检查悬赏结束")
        time.sleep(1)
        # 跳转到任务界面
        CUS_LOGGER.debug(f"[{self.player}] [查漏补缺] 检查公会任务开始")
        quest_list,completed_fertilization=self.check_task_of_guild(c_opt)
        CUS_LOGGER.debug(f"[{self.player}] [查漏补缺] 检查公会任务结束")
        beijing_tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(beijing_tz)
        if now.weekday() == 2:
            SIGNAL.DIALOG.emit(
                "查漏补缺报告",
                f"今天是星期三，记得检查兑换悬赏卡包，施肥卡包\n")
        elif now.weekday() == 3:
            SIGNAL.DIALOG.emit(
                "查漏补缺报告",
                f"今天是星期四，若是悬赏更新，记得更换方案\n"
                f"若是三岛更新，记得切换当前刷关配置\n")
        if datetime.today().day == 26:
            SIGNAL.DIALOG.emit(
                "查漏补缺报告",
                f"今天是炸卡日，记得检查兑换签到卡包\n")
        CUS_LOGGER.debug(f"[{self.player}] [查漏补缺] 结束")
        return quest_list,reputation_status,reputation_now,completed_fertilization
    def check_task_of_bounty(self: "FAA"):
        # 进入X年活动界面
        self.action_top_menu(mode="X年活动")
        # 最大尝试次数
        max_attempts = 10
        # 循环遍历点击完成
        for try_count in range(max_attempts):
            result = loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["悬赏任务_领取奖励.png"],
                match_tolerance=0.99,
                match_failed_check=2,
                click=True,
                after_sleep=2)
            if not result:
                break
            else:
                CUS_LOGGER.warning(f"[{self.player}] [查漏补缺] 检查到未成功领取悬赏！！现已领取")

        # 如果达到了最大尝试次数
        if try_count == max_attempts - 1:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            SIGNAL.DIALOG.emit(
                "查漏补缺报告",
                f"{self.player}P因背包爆满, 查漏补缺[领取悬赏任务奖励]失败!\n"
                f"出错时间:{current_time}, 尝试次数:{max_attempts}")

        # 退出任务界面
        # 截取整个窗口图像
        full_image = capture_image_png(handle=self.handle, raw_range=[0, 0, 3000, 3000])

        # 裁剪出第一个区域
        reputation_all = png_cropping(image=full_image, raw_range=[612, 470, 640, 482])

        # 裁剪出第二个区域并转换为模板格式
        reputation_now = png_cropping(image=full_image, raw_range=[574, 470, 600, 482])
        # 使用match_p_in_w进行相似度比对
        reputation_status, result = match_p_in_w(
            template=reputation_now,  # 将区域2作为模板
            source_img=reputation_all,  # 在区域1中查找
            match_tolerance=0.95,
            test_show=False  # 不显示测试窗口
        )

        if reputation_status == 2:  # 匹配成功,说明声望满了
            CUS_LOGGER.debug(f"[{self.player}] 成功匹配")
        else:#声望没有满
            CUS_LOGGER.debug(f"[{self.player}] 失败匹配")

        self.action_exit(mode="关闭悬赏窗口")
        return reputation_status,reputation_now
    def check_task_of_guild(self: "FAA",c_opt):
        self.action_bottom_menu(mode="跳转_公会任务")
        qg_cs=c_opt["quest_guild"]["stage"]
        quest_not_completed=False
        # 最大尝试次数
        max_attempts = 20

        # 循环遍历点击完成
        for try_count in range(max_attempts):

            # 点一下 让左边的选中任务颜色消失
            loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["quest_guild"]["ui_quest_list.png"],
                after_sleep=5.0,
                click=True)

            # 向下拖一下
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=415, y=510)
            time.sleep(0.5)

            # 检查是否有已完成的任务
            result = loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["quest_guild"]["completed.png"],
                match_tolerance=0.99,
                click=True,
                match_failed_check=5,  # 1+4s 因为偶尔会弹出美食大赛完成动画4s 需要充足时间！这个确实脑瘫...
                after_sleep=0.5)
            if not result:
                break
            CUS_LOGGER.warning(f"[{self.player}] [查漏补缺] 检查到未成功领取公会奖励！！现已领取")
            # 点击“领取”按钮
            loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["quest_guild"]["gather.png"],
                match_tolerance=0.99,
                click=True,
                match_failed_check=2,
                after_sleep=2)  # 2s 完成任务有显眼动画

        # 如果达到了最大尝试次数
        if try_count == max_attempts - 1:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            SIGNAL.DIALOG.emit(
                "查漏补缺报告",
                f"{self.player}P因背包爆满, 查漏补缺[领取公会任务奖励] 失败!\n"
                f"出错时间:{current_time}, 尝试次数:{max_attempts}")
        code,locations=match_all_p_in_w(template=RESOURCE_P["common"]["任务_进行中.png"],
                         source_handle=self.handle,
                         source_root_handle=self.handle_360,
                         source_range=[350,180,406,532],
                         threshold=0.95,
                         test_show=False)
        quest_list = []
        if code==2:
            if locations:
                full_image = capture_image_png(handle=self.handle, raw_range=[0, 0, 3000, 3000])
                for pos in locations:
                    # 截取整个窗口图像
                    abs_x = pos[0] + 350
                    abs_y = pos[1] + 180
                    # 定义左侧搜索区域，裁小不裁多
                    name_search_range = [
                        max(0, abs_x - 220),
                        abs_y,
                        abs_x - 10,
                        abs_y + 15
                    ]
                    task_img = png_cropping(image=full_image, raw_range=name_search_range)
                    # 在左侧区域查找任务名称图像
                    found_task = False

                    for i in [1, 2, 3, 4, 5, 6, 7, 10, 11]:
                        for quest_text, img in g_resources.RESOURCE_P["quest_guild"][str(i)].items():
                            _, name_pos = match_p_in_w(
                                source_img=img,
                                template=task_img,
                                match_tolerance=0.95)

                            if name_pos:
                                # 找到任务名称，解析任务信息
                                quest_card = None
                                ban_card_list = []
                                max_card_num = None

                                # 处理解析字符串 格式 "关卡id" + "_附加词条"
                                quest_text = quest_text.split(".")[0]
                                quest_split_list = quest_text.split("_")

                                stage_id = quest_split_list[0]
                                for one_split in quest_split_list:
                                    if "带#" in one_split:
                                        quest_card = one_split.split("#")[1]
                                    if "禁#" in one_split:
                                        ban_card_list = one_split.split("#")[1].split(",")
                                    if "数#" in one_split:
                                        max_card_num = int(one_split.split("#")[1])

                                # 如果不打CS任务且是CS任务，则跳过
                                if stage_id.split("-")[0] == "CS" and (not qg_cs):
                                    continue

                                # 添加到任务列表
                                quest_list.append({
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
                                    "quest_card": quest_card,
                                    "ban_card_list": ban_card_list,
                                    "max_card_num": max_card_num,
                                    "global_plan_active": c_opt["quest_guild"]["global_plan_active"],
                                    "deck": c_opt["quest_guild"]["deck"],
                                    "battle_plan_1p": c_opt["quest_guild"]["battle_plan_1p"],
                                    "battle_plan_2p": c_opt["quest_guild"]["battle_plan_2p"],
                                })

                                found_task = True
                                break  # 找到一个任务名称即可跳出内层循环

                        if found_task:
                            break  # 找到任务后跳出外层循环
            # 检测施肥任务完成情况 任务是进行中的话为True
            quest_not_completed = loop_match_ps_in_w(
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

            if not quest_not_completed:
                CUS_LOGGER.debug(f"[{self.player}] [查漏补缺] 已完成公会浇水施肥")
        # 退出任务界面
        self.action_exit(mode="普通红叉")
        return quest_list,quest_not_completed
    def screen_check_server_boom(self: "FAA") -> bool:
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

    """调用输入关卡配置和战斗配置, 在战斗前必须进行该操作"""

    def set_config_for_battle(
            self: "FAA",
            stage_id: str = "NO-1-1",
            is_group: bool = False,
            is_main: bool = True,
            need_key: bool = True,
            quest_card=None,
            ban_card_list=None,
            max_card_num=None,
            is_cu: bool = False,
    ) -> None:
        """
        战斗相关参数的re_init
        :param is_cu: 是否为自建房, 此类战斗需要修改stage id 为 CU-0-0, 以防用户自建房随便输入StageID污染数据集!!!
        :param is_group: 是否组队
        :param is_main: 是否是主要账号(单人为True 双人房主为True)
        :param need_key: 是否使用钥匙

        :param quest_card: str 自动携带任务卡的名称
        :param ban_card_list: list[str,...] ban卡列表
        :param max_card_num: 最大卡片数 - 仅自动带卡时启用 会去除id更低的卡片, 保证完成任务要求.
        :param stage_id: 关卡的id
        :return:
        """

        if (ban_card_list is None) or (ban_card_list is ["None"]):
            ban_card_list = []

        self.is_main = is_main
        self.is_group = is_group
        self.need_key = need_key

        self.quest_card = quest_card
        self.ban_card_list = ban_card_list
        self.max_card_num = max_card_num

        if not is_cu:
            self.stage_info = read_json_to_stage_info(stage_id)
        else:
            self.stage_info = read_json_to_stage_info(stage_id="CU-0-0", stage_id_for_battle=stage_id)

    def set_battle_plan(
            self,
            deck: int,
            auto_carry_card: bool,
            battle_plan_uuid: str = "00000000-0000-0000-0000-000000000000",
            battle_plan_tweak_uuid: str = "00000000-0000-0000-0000-000000000000"

    ):
        """
        设置战斗方案
        :param deck: int 1-6 选中的卡槽数 (0值已被处理为 auto_carry_card 参数)
        :param auto_carry_card: bool 是否激活自动带卡
        :param battle_plan_uuid: 战斗方案的uuid
        :param battle_plan_tweak_uuid: 战斗微调方案的uuid
        :return:
        """

        # 设置卡组策略
        self.deck = deck
        self.auto_carry_card = auto_carry_card

        # 如果缺失, 外部的检测函数会拦下来不继续的
        self.battle_plan = g_resources.RESOURCE_B.get(battle_plan_uuid, None)
        self.battle_plan_tweak = g_resources.RESOURCE_T.get(battle_plan_tweak_uuid, None)

        # 格式校验[float, float]
        if self.battle_plan_tweak.get("meta_data", {}).get("cd_after_use_random_range", {}):
            self.battle_plan_tweak["meta_data"]["cd_after_use_random_range"] = [
                float(x) for x in self.battle_plan_tweak["meta_data"]["cd_after_use_random_range"]]

    """战斗完整的过程中的任务函数"""

    def init_mat_smoothie_kun_card_info(self: "FAA") -> None:
        """
        根据关卡名称和可用承载卡，以及游戏内识图到的承载卡取交集，返回承载卡的x-y坐标
        :return: [[x1, y1], [x2, y2],...]
        """

        self.print_info("战斗中识图查找承载卡/冰沙/坤位置, 开始")

        # 筛选出所有 有图片资源的卡片 包含变种
        mat_resource_list = [
            f"{card}-{i}.png"
            for card in copy.deepcopy(self.stage_info["mat_card"])
            for i in range(6)
            if f"{card}-{i}.png" in RESOURCE_P["card"]["战斗"]
        ]

        smoothie_resource_list = [
            f"{card}-{i}.png"
            for card in ["冰激凌"]
            for i in range(6)
            if f"{card}-{i}.png" in RESOURCE_P["card"]["战斗"]
        ]

        # 筛选出所有 有图片资源的卡片 包含变种
        kun_resource_list = [
            f"{card}-{i}.png"
            for card in ["幻幻鸡", "创造神"]
            for i in range(6)
            if f"{card}-{i}.png" in RESOURCE_P["card"]["战斗"]
        ]

        def scan(resource_list):
            return_dict = {}
            for mat_card in resource_list:

                # 需要使用0.99相似度参数 相似度阈值过低可能导致一张图片被识别为两张卡
                _, find = match_p_in_w(
                    source_img=image,
                    source_range=[190, 10, 950, 80],
                    template=RESOURCE_P["card"]["战斗"][mat_card],
                    match_tolerance=0.99)
                if find:
                    return_dict[mat_card.split("-")[0]] = [int(190 + find[0]), int(10 + find[1])]
                else:
                    _, find = match_p_in_w(
                        source_img=image,
                        source_range=[880, 80, 950, 600],
                        template=RESOURCE_P["card"]["战斗"][mat_card],
                        match_tolerance=0.99)
                    if find:
                        return_dict[mat_card.split("-")[0]] = [int(880 + find[0]), int(80 + find[1])]

            return return_dict

        # 查找对应卡片坐标 重复3次
        for i in range(3):

            image = capture_image_png(
                handle=self.handle,
                root_handle=self.handle_360,
                raw_range=[0, 0, 950, 600],
            )
            mat_card_dict = scan(resource_list=mat_resource_list)
            smoothie_card_dict = scan(resource_list=smoothie_resource_list)
            kun_card_dict = scan(resource_list=kun_resource_list)

            for resource_list, card_dict in [
                (mat_resource_list, mat_card_dict),
                (smoothie_resource_list, smoothie_card_dict),
                (kun_resource_list, kun_card_dict)
            ]:
                resource_list[:] = [item for item in resource_list if item not in card_dict]

            # 防止卡片正好被某些特效遮挡, 所以等待一下
            time.sleep(0.1)

        # 根据坐标位置，判断对应的卡id
        mat_cards_info = []
        for name, coordinate in mat_card_dict.items():
            for card_id, card_xy_list in self.bp_card.items():
                x1 = card_xy_list[0]
                y1 = card_xy_list[1]
                x2 = card_xy_list[0] + 53
                y2 = card_xy_list[1] + 70
                if x1 <= coordinate[0] <= x2 and y1 <= coordinate[1] <= y2:
                    mat_cards_info.append({'name': name, 'card_id': card_id, 'coordinate_from': card_xy_list})
        self.mat_cards_info = mat_cards_info
        self.print_info("战斗中识图查找承载卡位置, 结果: {}".format(mat_cards_info))

        # 根据坐标位置，判断对应的卡id
        smoothie_info = None
        for name, coordinate in smoothie_card_dict.items():
            for card_id, card_xy_list in self.bp_card.items():
                x1 = card_xy_list[0]
                y1 = card_xy_list[1]
                x2 = card_xy_list[0] + 53
                y2 = card_xy_list[1] + 70
                if x1 <= coordinate[0] <= x2 and y1 <= coordinate[1] <= y2:
                    smoothie_info = {'name': '极寒冰沙', "card_id": card_id}
                    break
        self.smoothie_info = smoothie_info
        self.print_info(text="战斗中识图查找冰沙位置, 结果：{}".format(self.smoothie_info))

        # 根据坐标位置，判断对应的卡id
        kun_cards_info = []
        for card_name, coordinate in kun_card_dict.items():
            for card_id, card_xy_list in self.bp_card.items():
                x1 = card_xy_list[0]
                y1 = card_xy_list[1]
                x2 = card_xy_list[0] + 53
                y2 = card_xy_list[1] + 70
                if x1 <= coordinate[0] <= x2 and y1 <= coordinate[1] <= y2:
                    kun_cards_info.append({'name': card_name, "card_id": card_id})
        self.kun_cards_info = kun_cards_info
        self.print_info(text="战斗中识图查找幻幻鸡位置, 结果：{}".format(self.kun_cards_info))

    def init_battle_plan_card(self: "FAA", wave: int) -> None:
        """
        战斗方案解析器 - 用于根据战斗方案的json和关卡等多种信息, 解析计算为卡片的部署方案 供战斗方案执行器执行
        Return: battle_plan_card 卡片的部署方案字典
            example = [
                {
                    来自配置文件
                    "card_id": int, 卡片从哪取 代号 (卡片在战斗中, 在卡组的的从左到右序号 )
                    "name": str,  名称 用于ban卡
                    "location": ["x-y","x-y"...] ,  卡片放到哪 代号
                    "ergodic": True,  放卡模式 遍历
                    "queue": True,  放卡模式 队列
                    函数计算得出
                    "coordinate_from": [x:int, y:int]  卡片从哪取 坐标
                    "coordinate_to": [[x:int, y:int],[x:int, y:int],[x:int, y:int],...] 卡片放到哪 坐标
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
        stage_info = copy.deepcopy(self.stage_info)
        battle_plan = copy.deepcopy(self.battle_plan)
        mat_card_info = copy.deepcopy(self.mat_cards_info)
        smoothie_info = copy.deepcopy(self.smoothie_info)

        # 新版战斗方案兼容
        battle_plan = next(
            (
                event["action"]["cards"] for event in battle_plan["events"] if (
                    event["trigger"]["type"] == "wave_timer" and
                    event["trigger"]["wave_id"] == int(wave) and
                    event["action"]["type"] == "loop_use_cards"
            )
            ), [])

        # 内联卡片名称
        for a_card in battle_plan:
            a_card["name"] = next(
                o_card["name"] for o_card in self.battle_plan["cards"] if o_card["card_id"] == a_card["card_id"])

        """当前波次选择"""

        def calculation_card_quest(list_cell_all):
            """计算步骤一 加入任务卡的摆放坐标"""

            if quest_card == "None" or quest_card is None:
                return list_cell_all

            quest_card_locations = [
                "6-1", "6-2", "6-3", "6-4", "6-5", "6-6", "6-7",
                "7-1", "7-2", "7-3", "7-4", "7-5", "7-6", "7-7"
            ]

            # 遍历删除 方案的放卡中 占用了任务卡摆放的棋盘位置
            list_cell_all = [
                {**card, "location": list(filter(lambda x: x not in quest_card_locations, card["location"]))}
                for card in list_cell_all
            ]

            # 计算任务卡的id 最大的卡片id + 1 注意判空!!!
            if list_cell_all:
                quest_card_id = max(card["card_id"] for card in list_cell_all) + 1
            else:
                quest_card_id = 1

            # 任务卡 位置 组队情况下分摊
            if not is_group:
                quest_card_locations = [
                    "6-1", "6-2", "6-3", "6-4", "6-5", "6-6", "6-7",
                    "7-1", "7-2", "7-3", "7-4", "7-5", "7-6", "7-7"
                ]
            else:
                if self.player == 1:
                    quest_card_locations = ["6-1", "6-2", "6-3", "6-4", "6-5", "6-6", "6-7"]
                else:
                    quest_card_locations = ["7-1", "7-2", "7-3", "7-4", "7-5", "7-6", "7-7"]

            # 设定任务卡dict
            dict_quest = {
                "card_id": quest_card_id,
                "name": quest_card,
                "location": quest_card_locations,
                "ergodic": True,
                "queue": True,
                "kun": 0
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

            if not self.banned_card_index:
                return list_cell_all

            list_new = [card for card in list_cell_all if card["card_id"] not in self.banned_card_index]

            # 遍历更改删卡后的位置
            for card in list_new:
                card["card_id"] -= sum(1 for index in self.banned_card_index if card["card_id"] > index)

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
            num_mat_card = len(mat_card_info)

            # 本关需求盘子类承载卡
            need_plate = any(card['name'] == "木盘子" for card in mat_card_info)

            for i in range(num_mat_card):

                dict_mat = {
                    "card_id": mat_card_info[i]['card_id'],
                    "name": mat_card_info[i]['name'],
                    "location": location[i::num_mat_card],
                    "ergodic": need_plate,
                    "queue": True
                }

                # 可能是空列表 即花瓶
                if len(list_cell_all) == 0:
                    # 首位插入
                    list_cell_all.insert(0, dict_mat)
                else:
                    # 第二位插入
                    list_cell_all.insert(1, dict_mat)

            return list_cell_all

        def calculation_card_extra(list_cell_all):

            if smoothie_info:
                # # 生成从 "1-1" 到 "1-7" 再到 "9-1" 到 "9-7" 的列表
                # all_locations = [f"{i}-{j}" for i in range(1, 10) for j in range(1, 8)]
                #
                # # 找到第一个不在障碍物列表中的值
                # first_available_location = next(
                #     (pos for pos in all_locations if pos not in stage_info['obstacle']), None)

                # 仅该卡确定存在后执行添加
                card_dict = {
                    'name': smoothie_info['name'],
                    'card_id': smoothie_info['card_id'],
                    'location': ["1-1", "2-1", "3-1", "4-1", "5-1", "6-1", "7-1", "8-1", "9-1"],
                    'ergodic': True,
                    'queue': False
                }
                list_cell_all.append(card_dict)

            if self.kun_cards_info:
                # 确认卡片在卡组 且 有至少一个kun参数设定
                kun_already_set = False
                for card in list_cell_all:
                    # 遍历已有卡片
                    if "kun" in card.keys():
                        kun_already_set = True
                        break
                if not kun_already_set:
                    # 没有设置 那么也视坤位置标记不存在
                    self.kun_cards_info = []

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
                # if card["location"]:
                new_list.append(card)

            return new_list

        def main():
            # 初始化数组 + 复制一份全新的 battle_plan
            list_cell_all = battle_plan

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

            # 统一以坐标直接表示位置, 防止重复计算 (添加coordinate_from, coordinate_to)
            # 将 id:int 变为 coordinate_from:[x:int,y:int]
            # 将 location:str 变为 coordinate_to:[[x:int,y:int],...]
            for card in list_cell_all:
                # 根据字段值, 判断是否完成写入, 并进行转换
                card["coordinate_from"] = copy.deepcopy(bp_card[card["card_id"]])
                card["coordinate_to"] = [copy.deepcopy(bp_cell[location]) for location in card["location"]]

            # 为幻鸡单独转化
            for kun_card_info in self.kun_cards_info:
                kun_card_info["coordinate_from"] = copy.deepcopy(bp_card[kun_card_info["card_id"]])

            # 不常用调试print
            self.print_debug(text="你的战斗放卡opt如下:")
            self.print_debug(text=list_cell_all)

            self.battle_plan_card = list_cell_all

        return main()

    def battle_a_round_init_battle_plan(self: "FAA"):
        """
        关卡内战斗过程
        """
        # 0.刷新battle相关的属性值
        self.faa_battle_re_init()

        # 1.把人物放下来
        time.sleep(0.333)
        if not self.is_main:
            time.sleep(0.666)

        self.init_battle_plan_player(locations=self.battle_plan["meta_data"]["player_position"])
        self.use_player_all()

        # 2.识图卡片数量，确定卡片在deck中的位置
        self.bp_card = get_location_card_deck_in_battle(handle=self.handle, handle_360=self.handle_360)

        # 3.识图各种卡参数
        self.init_mat_smoothie_kun_card_info()

        # 4.计算所有卡片放置坐标
        self.init_battle_plan_card(wave=0)

        # 5.铲卡
        self.init_battle_plan_shovel(locations=self.stage_info["shovel"])
        if self.is_main:
            self.use_shovel_all(need_lock=False)  # 因为有点击序列，所以同时操作是可行的

    """其他非战斗功能"""

    def match_quests(self: "FAA", mode: str, qg_cs: bool = False) -> list:
        """
        获取任务列表 -> 需要的完成的关卡步骤
        :param mode: "公会任务" "情侣任务" "美食大赛" "美食大赛-新"
        :param qg_cs: 公会任务模式下 是否需要跨服
        :return: [
            {
                "stage_id": str,
                "max_times": int,
                "quest_card": str,
                "ban_card": None,
                "quest_text": str, 仅用于标识任务原文, 仅美食大赛模块包含, 其他模式没有该字段
            },
            ...
        ]
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
                after_sleep=5.0,
                click=True)

            # 向下拖一下
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=415, y=505)
            time.sleep(1.0)

        if mode == "情侣任务":
            self.action_bottom_menu(mode="跳转_情侣任务")

        if mode == "美食大赛" or mode == "美食大赛-新":
            self.action_top_menu(mode="美食大赛")

        # 读取
        quest_list = []
        if mode == "公会任务":

            for i in [1, 2, 3, 4, 5, 6, 7, 10, 11]:
                for quest_text, img in RESOURCE_P["quest_guild"][str(i)].items():
                    # 找到任务 加入任务列表
                    _, find_p = match_p_in_w(
                        source_handle=self.handle,
                        source_root_handle=self.handle_360,
                        source_range=[125, 180, 407, 540],
                        template=img,
                        match_tolerance=0.995)
                    if find_p:

                        quest_card = None  # 任务携带卡片默认为None
                        ban_card_list = []
                        max_card_num = None
                        # 处理解析字符串 格式 "关卡id" + "_附加词条"
                        # 附加词条包括
                        # 带卡 "带#卡片名称"
                        # 禁卡 "禁#卡片1,卡片2..."
                        # 同名后缀不会被识别 "小写字母"
                        quest_text = quest_text.split(".")[0]  # 去除.png
                        quest_split_list = quest_text.split("_")  # 分割

                        # # 是否启用分支作战, 以分别进行ban卡
                        # find_ban_batch = False

                        stage_id = quest_split_list[0]
                        for one_split in quest_split_list:
                            if "带#" in one_split:
                                quest_card = one_split.split("#")[1]
                            if "禁#" in one_split:
                                ban_card_list = one_split.split("#")[1].split(",")
                            if "数#" in one_split:
                                max_card_num = int(one_split.split("#")[1])

                        # 如果不打 跳过
                        if stage_id.split("-")[0] == "CS" and (not qg_cs):
                            continue

                        # 添加到任务列表
                        # if not find_ban_batch:
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
                                "quest_card": quest_card,
                                "ban_card_list": ban_card_list,
                                "max_card_num": max_card_num,
                                "global_plan_active": None,  # 外部输入
                                "deck": None,  # 外部输入
                                "battle_plan_1p": None,  # 外部输入
                                "battle_plan_2p": None,  # 外部输入
                            }
                        )

        if mode == "情侣任务":

            for i in ["1", "2", "3"]:
                # 任务未完成
                _, find_p = match_p_in_w(
                    source_handle=self.handle,
                    source_root_handle=self.handle_360,
                    source_range=[0, 0, 950, 600],
                    template=RESOURCE_P["quest_spouse"]["NO-{}.png".format(i)],
                    match_tolerance=0.999)
                if find_p:
                    # 遍历任务
                    for quest_text, img in RESOURCE_P["quest_spouse"][i].items():
                        # 找到任务 加入任务列表
                        _, find_p = match_p_in_w(
                            source_handle=self.handle,
                            source_root_handle=self.handle_360,
                            source_range=[0, 0, 950, 600],
                            template=img,
                            match_tolerance=0.999)
                        if find_p:
                            quest_list.append(
                                {
                                    "stage_id": quest_text.split(".")[0],  # 去掉.png
                                    "player": [2, 1],
                                    "need_key": True,
                                    "max_times": 1,
                                    "dict_exit": {
                                        "other_time_player_a": [],
                                        "other_time_player_b": [],
                                        "last_time_player_a": ["竞技岛"],
                                        "last_time_player_b": ["竞技岛"]
                                    },
                                    "global_plan_active": None,  # 外部输入
                                    "deck": None,  # 外部输入
                                    "battle_plan_1p": None,  # 外部输入
                                    "battle_plan_2p": None,  # 外部输入
                                }
                            )

        if mode == "美食大赛":

            """
            ！！！！注意 该模块已经废弃！！！！
            """

            for click_y in [359, 390, 420, 450, 480, 510, 540, 570]:
                # 先移动到新的一页
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=536, y=click_y)
                time.sleep(0.25)
                for quest_text, img in RESOURCE_P["quest_food"].items():
                    _, find_p = match_p_in_w(
                        source_handle=self.handle,
                        source_root_handle=self.handle_360,
                        source_range=[130, 350, 470, 585],
                        template=img,
                        match_tolerance=0.999)

                    if find_p:
                        # 处理解析字符串 格式
                        quest_text = quest_text.split(".")[0]  # 去除.png
                        battle_sets = quest_text.split("_")  # 根据_符号 拆成list

                        # 打什么关卡 文件中: 关卡名称
                        stage_id = battle_sets[0]

                        # 是否组队 文件中: 1 单人 2 组队
                        player = [self.player] if battle_sets[1] == "1" else [2, 1]

                        # 是否使用钥匙 文件中: 0 or 1 -> bool
                        need_key = bool(battle_sets[2])

                        # 任务卡: "None" or 其他
                        quest_card = None if battle_sets[3] == "None" else battle_sets[3]

                        # Ban卡表: "None" or 其他, 多个值用逗号分割
                        ban_card_list = battle_sets[4].split(",")
                        # 如果 ['None'] -> []
                        if ban_card_list == ['None']:
                            ban_card_list = []

                        quest_list.append(
                            {
                                "stage_id": stage_id,
                                "player": player,  # [1] or [2] or [2, 1]
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

        if mode == "美食大赛-新":
            # 获取图片 list 可能包含alpha通道
            quest_imgs = food_match_ocr_text(self)

            # 提取文字
            texts = extract_text_from_images(images=quest_imgs)

            # 解析文本
            quest_list = food_texts_to_battle_info(texts=texts, self=self)

        # 关闭公会任务列表(红X)
        if mode == "公会任务" or mode == "情侣任务":
            self.action_exit(mode="普通红叉")

        if mode == "美食大赛" or mode == "美食大赛-新":
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=888, y=53)
            time.sleep(0.5)

        return quest_list

    def click_refresh_btn(self: "FAA") -> bool:
        """
        点击360游戏大厅的刷新游戏按钮
        :return: bool 是否成功点击
        """

        # 点击刷新按钮 该按钮在360窗口上
        find = loop_match_p_in_w(
            source_handle=self.handle_360,
            source_root_handle=self.handle_360,
            source_range=[0, 0, 400, 75],
            template=RESOURCE_P["common"]["登录"]["0_刷新.png"],
            match_tolerance=0.9,
            after_sleep=3,
            click=True)

        if not find:
            find = loop_match_p_in_w(
                source_handle=self.handle_360,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 400, 75],
                template=RESOURCE_P["common"]["登录"]["0_刷新_被选中.png"],
                match_tolerance=0.98,
                after_sleep=3,
                click=True)

            if not find:

                find = loop_match_p_in_w(
                    source_handle=self.handle_360,
                    source_root_handle=self.handle_360,
                    source_range=[0, 0, 400, 75],
                    template=RESOURCE_P["common"]["登录"]["0_刷新_被点击.png"],
                    match_tolerance=0.98,
                    after_sleep=3,
                    click=True)

                if not find:
                    self.print_error(text="未找到360大厅刷新游戏按钮, 可能导致一系列问题...")
                    return False
        return True

    def click_return_btn(self: "FAA") -> bool:
        """
        点击360游戏大厅的返回上一级按钮
        这用户在结束后的最终刷新前, 以保证微端也能回到选服界面
        请注意 微端 这需要再之后补一次刷新
        请注意 不要给该操作设置必须成功 因为 部分服务器没有回退按钮
        :return: bool 是否成功点击
        """

        # 点击刷新按钮 该按钮在360窗口上
        find = loop_match_p_in_w(
            source_handle=self.handle_360,
            source_root_handle=self.handle_360,
            source_range=[0, 0, 400, 75],
            template=RESOURCE_P["common"]["登录"]["0_回退.png"],
            match_tolerance=0.9,
            after_sleep=3,
            click=True)

        if not find:
            find = loop_match_p_in_w(
                source_handle=self.handle_360,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 400, 75],
                template=RESOURCE_P["common"]["登录"]["0_回退_被选中.png"],
                match_tolerance=0.98,
                after_sleep=3,
                click=True)

            if not find:

                find = loop_match_p_in_w(
                    source_handle=self.handle_360,
                    source_root_handle=self.handle_360,
                    source_range=[0, 0, 400, 75],
                    template=RESOURCE_P["common"]["登录"]["0_回退_被点击.png"],
                    match_tolerance=0.98,
                    after_sleep=3,
                    click=True)

                if not find:
                    self.print_warning(text="尝试点击360大厅回退按钮, 但失败了!")
                    return False
        return True

    def click_accelerate_btn(self: "FAA", mode: str = "normal") -> bool:
        """
        点击360游戏大厅的刷新游戏按钮
        :param mode: str 模式 包含 "normal" "stop"
        :return: bool 是否成功点击
        """

        def click_btn():

            # 点击按钮 该按钮在360窗口上
            find = loop_match_p_in_w(
                source_handle=self.handle_360,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 2000, 75],
                template=RESOURCE_P["common"]["战斗"]["变速_默认或被点击.png"],
                match_tolerance=0.99,
                match_interval=0.00001,
                match_failed_check=0.00002,
                after_sleep=0,
                click=True)

            if not find:
                find = loop_match_p_in_w(
                    source_handle=self.handle_360,
                    source_root_handle=self.handle_360,
                    source_range=[0, 0, 2000, 75],
                    template=RESOURCE_P["common"]["战斗"]["变速_被选中.png"],
                    match_tolerance=0.99,
                    match_interval=0.00001,
                    match_failed_check=0.00002,
                    after_sleep=0,
                    click=True)

                if not find:
                    self.print_error(text="未找到360大厅加速游戏按钮, 加速游戏失败了...")
                    return False
            return True

        def close():
            for i in range(10):

                # 检测是否在加速中
                not_accelerating = loop_match_p_in_w(
                    source_handle=self.handle_360,
                    source_root_handle=self.handle_360,
                    source_range=[0, 0, 2000, 75],
                    template=RESOURCE_P["common"]["战斗"]["未激活变速_默认.png"],
                    match_tolerance=0.99,
                    match_interval=0.1,
                    match_failed_check=0.2,
                    after_sleep=0,
                    click=False
                )

                if not not_accelerating:
                    not_accelerating = loop_match_p_in_w(
                        source_handle=self.handle_360,
                        source_root_handle=self.handle_360,
                        source_range=[0, 0, 2000, 75],
                        template=RESOURCE_P["common"]["战斗"]["未激活变速_被选中或被点击.png"],
                        match_tolerance=0.99,
                        match_interval=0.00001,
                        match_failed_check=0.00002,
                        after_sleep=0,
                        click=False
                    )

                if not_accelerating:
                    self.print_info(text="复核 - 停止加速, 已完成")
                    return True

                click_btn()
                time.sleep(0.5)

            self.print_error(text="关闭加速出现致命失误!!! 请通报开发者!!!")
            return False

        if mode == "normal":
            return click_btn()
        else:
            return close()

    def reload_game(self: "FAA") -> None:

        def try_close_sub_account_list() -> bool:

            # 等待一下 确保操作完成
            time.sleep(0.5)

            # 是否有小号列表
            _, my_result = match_p_in_w(
                source_handle=self.handle_360,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 300, 300],
                template=RESOURCE_P["common"]["登录"]["小号列表.png"],
                match_tolerance=0.99
            )
            if not my_result:
                return False

            # 点击关闭它
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=self.handle_360,
                x=30,
                y=55)
            # 等待一下 确保操作完成
            time.sleep(0.5)
            return True

        def try_enter_server_4399() -> bool:
            # 4399 进入服务器
            _, my_result = match_p_in_w(
                source_handle=self.handle_browser,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 2000, 2000],
                template=RESOURCE_P["common"]["登录"]["1_我最近玩过的服务器_4399.png"],
                match_tolerance=0.95
            )
            if my_result:
                # 点击进入服务器
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle_browser,
                    x=my_result[0],
                    y=my_result[1] + 30)
                return True
            return False

        def try_enter_server_4399_wd() -> bool:
            # 4399 进入服务器
            _, my_result = match_p_in_w(
                source_handle=self.handle_browser,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 2000, 2000],
                template=RESOURCE_P["common"]["登录"]["1_我最近玩过的服务器_4399微端.png"],
                match_tolerance=0.98
            )
            if my_result:
                # 点击进入服务器
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle_browser,
                    x=my_result[0],
                    y=my_result[1] + 30)
                return True
            else:
                _, my_result = match_p_in_w(
                    source_handle=self.handle_browser,
                    source_root_handle=self.handle_360,
                    source_range=[0, 0, 2000, 2000],
                    template=RESOURCE_P["common"]["登录"]["2_我最近玩过的服务器_4399微端.png"],
                    match_tolerance=0.97
                )
                if my_result:
                    # 点击进入服务器
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(
                        handle=self.handle_browser,
                        x=my_result[0],
                        y=my_result[1] + 30)
                    return True
            return False

        def try_enter_server_qq_space() -> bool:
            # QQ空间 进入服务器
            _, my_result = match_p_in_w(
                source_handle=self.handle_browser,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 2000, 2000],
                template=RESOURCE_P["common"]["登录"]["1_我最近玩过的服务器_QQ空间.png"],
                match_tolerance=0.98
            )
            if my_result:
                # 点击进入服务器
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle_browser,
                    x=my_result[0] + 20,
                    y=my_result[1] + 30)
                return True
            return False

        def try_enter_server_qq_game_hall() -> bool:
            # QQ游戏大厅 进入服务器
            _, my_result = match_p_in_w(
                source_handle=self.handle_browser,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 2000, 2000],
                template=RESOURCE_P["common"]["登录"]["1_我最近玩过的服务器_QQ游戏大厅.png"],
                match_tolerance=0.98
            )
            if my_result:
                # 点击进入服务器
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle_browser,
                    x=my_result[0],
                    y=my_result[1] + 30)
                return True
            return False

        def try_relink() -> bool:
            """
            循环判断是否处于页面无法访问网页上(刷新无用，因为那是单独的网页)
            如果是, 就点击红色按钮 + 返回上一页
            """

            # 查找 + 点击红色按钮（但点击不一定有效果!）
            my_result = loop_match_p_in_w(
                source_handle=self.handle_browser,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 2000, 2000],
                template=RESOURCE_P["error"]["retry_btn.png"],
                match_tolerance=0.95,
                click=True,
                after_sleep=3,
                match_interval=0.5,
                match_failed_check=10
            )
            if my_result:
                # 再回到上一个网页 基本上稳定可以修复
                self.click_return_btn()
                time.sleep(6)
                return True

            self.print_error(text="[刷新游戏] 循环判定断线重连失败, 请检查网络是否正常...")
            return False

        def main() -> bool:
            count=0
            while count<100:
                # 先重新获取 360 和 浏览器的句柄
                self.handle_browser = faa_get_handle(channel=self.channel, mode="browser")
                self.handle_360 = faa_get_handle(channel=self.channel, mode="360")

                # 确保关闭小号列表
                if try_close_sub_account_list():
                    self.print_debug(text="[刷新游戏] 成功关闭小号列表")
                else:
                    self.print_debug(text="[刷新游戏] 未找到小号列表, 很好...")

                # 点击刷新按钮 该按钮在360窗口上
                self.print_debug(text="[刷新游戏] 点击刷新按钮...")
                self.click_refresh_btn()

                # 根据配置判断是否要多sleep一会儿，因为QQ空间服在网络差的时候加载比较慢，会黑屏一段时间
                if self.extra_sleep["need_sleep"]:
                    time.sleep(self.extra_sleep["sleep_time"])

                    # 依次判断是否在选择服务器界面
                self.print_debug(text="[刷新游戏] 判定平台...")

                if try_enter_server_4399():
                    self.print_debug(text="[刷新游戏] 成功进入 - 4399平台")
                elif try_enter_server_4399_wd():
                    self.print_debug(text="[刷新游戏] 成功进入 - 4399微端平台")
                elif try_enter_server_qq_space():
                    self.print_debug(text="[刷新游戏] 成功进入 - QQ空间平台")
                    # 根据配置判断是否要多sleep一会儿，因为QQ空间服在网络差的时候加载比较慢，会黑屏一段时间
                    if self.extra_sleep["need_sleep"]:
                        time.sleep(self.extra_sleep["sleep_time"])

                elif try_enter_server_qq_game_hall():
                    self.print_debug(text="[刷新游戏] 成功进入 - QQ游戏大厅平台")
                else:
                    # QQ空间需重新登录
                    self.print_debug(
                        text="[刷新游戏] 未找到进入服务器按钮, 可能 1.QQ空间需重新登录 2.360X4399微端 3.需断线重连 4.意外情况")

                    if self.QQ_login_info and self.QQ_login_info["use_password"]:
                        # 密码登录模式
                        with open(self.QQ_login_info["path"] + "/QQ_account.json", "r") as json_file:
                            QQ_account = json.load(json_file)
                        username = QQ_account['{}p'.format(self.player)]['username']
                        password = QQ_account['{}p'.format(self.player)]['password']
                        password = decrypt_data(password)

                        # 2p 多等待一段时间，保证1p先完成登录，避免抢占焦点
                        if self.player == 2:
                            self.print_debug("[刷新游戏] [QQ登录] 2p正在等待")
                            time.sleep(10)
                            self.print_debug("[刷新游戏] [QQ登录] 2p等待完成")

                        # 开始进入密码登录页面
                        result = loop_match_p_in_w(
                            source_handle=self.handle_browser,
                            source_root_handle=self.handle_360,
                            source_range=[0, 0, 2000, 2000],
                            template=RESOURCE_P["common"]["登录"]["密码登录.png"],
                            match_tolerance=0.90,
                            match_interval=0.5,
                            match_failed_check=5,
                            after_sleep=2,
                            click=True)
                        if not result:
                            self.print_debug(text="进入QQ密码登录页面失败")
                            return False

                        # 进入密码登录页面成功，由于360可能记住账号，因此先要点叉号清除账号
                        loop_match_p_in_w(
                            source_handle=self.handle_browser,
                            source_root_handle=self.handle_360,
                            source_range=[0, 0, 2000, 2000],
                            template=RESOURCE_P["common"]["登录"]["叉号.png"],
                            match_tolerance=0.90,
                            match_interval=0.5,
                            match_failed_check=5,
                            after_sleep=1,
                            click=True)

                        # 点叉号清除账号成功，开始获取账号输入框的焦点
                        # 如果没成功说明不需要点击，因此也可以开始获取账号输入框的焦点
                        result = loop_match_p_in_w(
                            source_handle=self.handle_browser,
                            source_root_handle=self.handle_360,
                            source_range=[0, 0, 2000, 2000],
                            template=RESOURCE_P["common"]["登录"]["账号输入框.png"],
                            match_tolerance=0.90,
                            match_interval=0.5,
                            match_failed_check=5,
                            after_sleep=0.5,
                            click=True)
                        if not result:
                            self.print_debug(text="账号输入框获取焦点失败")
                            continue

                        # 注意这里不能 sleep ，否则容易因为抢占焦点而失败
                        # 账号输入框获取焦点成功，开始输入账号
                        for key in username:
                            T_ACTION_QUEUE_TIMER.char_input(handle=self.handle_browser, char=key)
                            time.sleep(0.1)

                        # 注意360有可能记住QQ账号，这里如果result==False就大概率是因为这个原因，所以不用输入账号
                        # (实测发现可能是由于faa获取截图的方式比较特殊，即使记住了QQ账号他也能获取到账号输入框，总之代码能跑)
                        # 输入账号完成，开始获取密码输入框的焦点
                        result = loop_match_p_in_w(
                            source_handle=self.handle_browser,
                            source_root_handle=self.handle_360,
                            source_range=[0, 0, 2000, 2000],
                            template=RESOURCE_P["common"]["登录"]["密码输入框.png"],
                            match_tolerance=0.90,
                            match_interval=0.5,
                            match_failed_check=5,
                            after_sleep=0.5,
                            click=True)
                        if not result:
                            self.print_debug(text="密码输入框获取焦点失败")
                            continue

                        # 注意这里不能 sleep ，否则容易因为抢占焦点而失败
                        # 密码输入框获取焦点成功，开始输入密码
                        for key in password:
                            T_ACTION_QUEUE_TIMER.char_input(handle=self.handle_browser, char=key)
                            time.sleep(0.1)

                        # 输入密码完成，开始点击登录按钮
                        result = loop_match_p_in_w(
                            source_handle=self.handle_browser,
                            source_root_handle=self.handle_360,
                            source_range=[0, 0, 2000, 2000],
                            template=RESOURCE_P["common"]["登录"]["登录.png"],
                            match_tolerance=0.90,
                            match_interval=0.5,
                            match_failed_check=5,
                            after_sleep=3,
                            click=True)

                        # 点击登录按钮成功，等待选服
                        # 这里不用time.sleep，直接修改上面的after_sleep参数即可

                    else:
                        # 非密码登录模式，通过点击QQ头像进行快捷登录
                        result = loop_match_p_in_w(
                            source_handle=self.handle_browser,
                            source_root_handle=self.handle_360,
                            source_range=[0, 0, 2000, 2000],
                            template=g_resources.RESOURCE_CP["用户自截"]["空间服登录界面_{}P.png".format(self.player)],
                            match_tolerance=0.95,
                            match_interval=0.5,
                            match_failed_check=5,
                            after_sleep=3,
                            click=True)

                    if result:
                        self.print_debug(text="[刷新游戏] 找到QQ空间服一键登录, 正在登录")
                        # 直接尝试登录QQ空间服务器
                        if try_enter_server_qq_space():
                            self.print_debug(text="[刷新游戏] 成功进入 - QQ空间平台")
                    else:
                        # 如果还未找到进入服务器的方式，则进行断线重连的判断
                        self.print_debug(text="[刷新游戏] 进入断线重连判断...")
                        if try_relink():
                            self.print_debug(text="[刷新游戏] 无需断线重连/成功点击断线重连")
                        else:
                            self.print_debug(text="[刷新游戏] 点不动断线重连，可能是网络爆炸/其他情况")

                """查找大地图确认进入游戏"""
                self.print_debug(text="[刷新游戏] 循环识图中, 以确认进入游戏...")
                # 更严格的匹配 防止登录界面有相似图案组合
                result = loop_match_ps_in_w(
                    source_handle=self.handle_browser,
                    source_root_handle=self.handle_360,
                    template_opts=[
                        {
                            "source_range": [850, 570, 2000, 2000],
                            "template": RESOURCE_P["common"]["底部菜单"]["跳转.png"],
                            "match_tolerance": 0.99,
                        }, {
                            "source_range": [615, 570, 2000, 2000],
                            "template": RESOURCE_P["common"]["底部菜单"]["任务.png"],
                            "match_tolerance": 0.99,
                        }, {
                            "source_range": [890, 570, 2000, 2000],
                            "template": RESOURCE_P["common"]["底部菜单"]["后退.png"],
                            "match_tolerance": 0.99,
                        }
                    ],
                    return_mode="and",
                    match_interval=1,
                    match_failed_check=30)

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
                        match_interval=0.2,
                        match_failed_check=5,
                        after_sleep=1,
                        click=True)

                    self.print_debug(text="[刷新游戏] 尝试关闭每日必充界面")
                    # [每天第一次登陆] 每日必充界面关闭
                    loop_match_p_in_w(
                        source_handle=self.handle,
                        source_root_handle=self.handle_360,
                        source_range=[0, 0, 950, 600],
                        template=RESOURCE_P["common"]["登录"]["4_退出假期特惠.png"],
                        match_tolerance=0.99,
                        match_interval=0.2,
                        match_failed_check=3,
                        after_sleep=1,
                        click=True)

                    self.print_debug(text="[刷新游戏] 已完成")
                    time.sleep(0.5)

                    return True
                else:
                    count += 1
                    CUS_LOGGER.warning(f"[刷新游戏] 查找大地图失败, 点击服务器后未能成功进入游戏, 刷新重来,当前刷新次数: {count}")
            return False
        fresh_success=main()
        if not fresh_success:
            CUS_LOGGER.warning("[刷新游戏] 刷新次数过多，可能网络爆炸了/360大厅抽风，刷新点不动,现在关闭360再逝一次")
            if not self.opt["login_settings"]["login_open_settings"]:
                CUS_LOGGER.error("[刷新游戏] 刷新次数过多，可能网络爆炸了/360大厅抽风，刷新点不动,并且未打开自动打开360")
                return
            with self.the_360_lock:
                self.close_360()
                time.sleep(1)
                self.start_360()
            main()
    def start_360(self):

        faa_get_handle(channel=self.channel, mode="360")

        def start_one(pid, game_id, account_id, executable_path, wait_sleep_time):

            if account_id == 0:
                return

            args = ["-action:opengame", f"-gid:{game_id}", f"-gaid:{account_id}"]
            start_software_with_args(executable_path, *args)
            time.sleep(wait_sleep_time)

            SIGNAL.PRINT_TO_UI.emit(text=f"[控制游戏大厅] {pid}P游戏大厅已启动.", color_level=1)

        SIGNAL.PRINT_TO_UI.emit(
            text="[控制游戏大厅] 重启大厅中...",
            color_level=1
        )
        if self.player == 1:
            start_one(
                pid=1,
                game_id=1,
                account_id=self.opt["login_settings"]["first_num"],
                executable_path=self.opt["login_settings"]["login_path"],
                wait_sleep_time=1
            )
        else:
            start_one(
                pid=2,
                game_id=1,
                account_id=self.opt["login_settings"]["second_num"],
                executable_path=self.opt["login_settings"]["login_path"],
                wait_sleep_time=5
            )

    def close_360(self):
        window_title = self.channel
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

    def sign_in(self: "FAA") -> None:

        def sign_in_vip():
            """VIP签到"""

            CUS_LOGGER.debug(f"[{self.player}] [VIP签到] 开始")
            self.action_top_menu(mode="VIP签到")

            # 增加3s等待时间 以加载
            time.sleep(3)

            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=740, y=190)
            time.sleep(0.5)

            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=225, y=280)
            time.sleep(0.5)

            self.action_exit(mode="普通红叉")
            CUS_LOGGER.debug(f"[{self.player}] [VIP签到] 结束")

        def sign_in_everyday():
            """每日签到"""

            CUS_LOGGER.debug(f"[{self.player}] [每日签到] 开始")
            self.action_top_menu(mode="每日签到")

            find = loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["签到"]["每日签到_确定.png"],
                match_tolerance=0.99,
                match_failed_check=5,
                after_sleep=1,
                click=True)

            if find:
                # 点击下面四个奖励
                for x in [460, 570, 675, 785]:
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=x, y=530)
                    time.sleep(0.1)

            self.action_exit(mode="普通红叉")
            CUS_LOGGER.debug(f"[{self.player}] [每日签到] 结束")

        def sign_in_food_activity():
            """美食活动"""

            CUS_LOGGER.debug(f"[{self.player}] [美食活动] 开始")
            self.action_top_menu(mode="美食活动")

            loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["签到"]["美食活动_确定.png"],
                match_tolerance=0.99,
                match_failed_check=5,
                after_sleep=1,
                click=True)

            self.action_exit(mode="普通红叉")
            CUS_LOGGER.debug(f"[{self.player}] [美食活动] 结束")

        def sign_in_tarot():
            """塔罗寻宝"""

            CUS_LOGGER.debug(f"[{self.player}] [塔罗寻宝] 开始")

            self.action_top_menu(mode="塔罗寻宝")

            loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["签到"]["塔罗寻宝_确定.png"],
                match_tolerance=0.99,
                match_failed_check=5,
                after_sleep=1,
                click=True)

            loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["签到"]["塔罗寻宝_退出.png"],
                match_tolerance=0.99,
                match_failed_check=5,
                after_sleep=1,
                click=True)

            CUS_LOGGER.debug(f"[{self.player}] [塔罗寻宝] 结束")

        def sign_in_pharaoh():
            """法老宝藏"""

            CUS_LOGGER.debug(f"[{self.player}] [法老宝藏] 开始")

            self.action_top_menu(mode="法老宝藏")

            find = loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["签到"]["法老宝藏_确定.png"],
                match_tolerance=0.99,
                match_failed_check=5,
                after_sleep=1,
                click=False)

            if find:
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=300, y=250)
                time.sleep(1)

            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=791, y=98)
            time.sleep(1)

            CUS_LOGGER.debug(f"[{self.player}] [法老宝藏] 结束")

        def sign_in_release_quest_guild():
            """会长发布任务"""

            CUS_LOGGER.debug(f"[{self.player}] [会长发布任务] 开始")

            self.action_bottom_menu(mode="跳转_公会任务")

            find = loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[73, 31, 173, 78],
                template=RESOURCE_P["common"]["签到"]["公会会长_发布任务.png"],
                match_tolerance=0.99,
                match_failed_check=5,
                after_sleep=1,
                click=True)
            if find:
                loop_match_p_in_w(
                    source_handle=self.handle,
                    source_root_handle=self.handle_360,
                    source_range=[422, 415, 544, 463],
                    template=RESOURCE_P["common"]["签到"]["公会会长_发布任务_确定.png"],
                    match_tolerance=0.99,
                    match_failed_check=5,
                    after_sleep=3,
                    click=True)
                # 关闭抽奖(红X)
                self.action_exit(mode="普通红叉", raw_range=[616, 172, 660, 228])

            # 关闭任务列表(红X)
            self.action_exit(mode="普通红叉", raw_range=[834, 35, 876, 83])

            CUS_LOGGER.debug(f"[{self.player}] [会长发布任务] 结束")

        def sign_in_camp_key():
            """领取营地钥匙和任务奖励"""

            CUS_LOGGER.debug(f"[{self.player}] [领取营地钥匙] 开始")
            if self.character_level <= 20:
                CUS_LOGGER.debug(f"[{self.player}] [领取营地钥匙] 放弃, 角色等级不足, 最低 21 级")
                return

            # 进入界面
            find = self.action_goto_map(map_id=10)

            if find:
                # 领取钥匙
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=400, y=445)
                time.sleep(0.5)
                # 如果还有任务
                for _ in range(10):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=175, y=325)
                    time.sleep(0.2)
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=175, y=365)
                    time.sleep(0.2)

            CUS_LOGGER.debug(f"[{self.player}] [领取营地钥匙] 结束")

        def sign_in_benefits_of_monthly_card():
            """领月卡"""

            CUS_LOGGER.debug(f"[{self.player}] [领取月卡福利] 开始")

            self.action_top_menu(mode="月卡福利")
            time.sleep(1)

            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=715, y=515)
            time.sleep(1)

            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=835, y=60)
            time.sleep(1)

            CUS_LOGGER.debug(f"[{self.player}] [领取月卡福利] 结束")

        def main():
            sign_in_vip()
            sign_in_everyday()
            sign_in_food_activity()
            sign_in_tarot()
            sign_in_pharaoh()
            sign_in_release_quest_guild()
            sign_in_camp_key()
            sign_in_benefits_of_monthly_card()

        return main()

    def sign_top_up_money(self: "FAA"):
        """日氪一元! 仅限4399 游币哦!
        为什么这么慢! 因为... 锑食太卡了!
        """

        def exit_ui():
            # 确定退出了该界面
            while True:
                find_i = loop_match_p_in_w(
                    source_handle=self.handle,
                    source_root_handle=self.handle_360,
                    source_range=[450, 145, 505, 205],
                    template=RESOURCE_P["top_up_money"]["每日必充_判定点.png"],
                    match_tolerance=0.99,
                    match_interval=0.1,
                    match_failed_check=4,
                    after_sleep=3,
                    click=False)
                if not find_i:
                    break
                else:
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=790, y=110)
                    time.sleep(2)

        # 进入充值界面
        self.action_top_menu(mode="每日充值")
        find = loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=[450, 145, 505, 205],
            template=RESOURCE_P["top_up_money"]["每日必充_判定点.png"],
            match_tolerance=0.99,
            match_interval=0.1,
            match_failed_check=4,
            after_sleep=3,
            click=False)
        if not find:
            return "本期日氪没有假期票Skip... 或进入每日必冲失败, 请联系开发者!"

        # 尝试领取 / 尝试进入充值界面 一元档
        CUS_LOGGER.debug("尝试领取 / 尝试进入充值界面...")
        source_range_1 = [660, 145, 770, 200]  # 充值/领取按钮位置
        find = loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=source_range_1,
            template=RESOURCE_P["top_up_money"]["每日必充_领取.png"],
            match_tolerance=0.99,
            match_interval=0.03,
            match_failed_check=4,
            after_sleep=3,
            click=True)
        if find:
            # 退出充值界面
            exit_ui()
            return "你今天氪过, 但未领取, 已帮忙领取, 下次别忘了哦~"

        find = loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=source_range_1,
            template=RESOURCE_P["top_up_money"]["每日必充_充值.png"],
            match_tolerance=0.99,
            match_interval=0.03,
            match_failed_check=4,
            after_sleep=3,
            click=True)
        if not find:
            # 退出充值界面
            exit_ui()
            return "今天氪过了~"
        or_rect = get_window_position(self.handle)
        browser_rect = get_window_position(self.handle_browser)
        zoom_rate = get_system_dpi() / 96
        print(or_rect, browser_rect)
        deviation = [(or_rect[0] - browser_rect[0]) // zoom_rate, (or_rect[1] - browser_rect[1]) // zoom_rate]
        # 没有完成, 进入充值界面
        CUS_LOGGER.debug("充值界面 点击切换为游币")
        source_range_2 = [150, 110, 800, 490]  # 游币兑换按钮 查找范围
        find = loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=source_range_2,
            template=RESOURCE_P["top_up_money"]["充值界面_游币兑换.png"],
            after_click_template=RESOURCE_P["top_up_money"]["充值界面_游币兑换_已选中.png"],
            match_tolerance=0.995,
            match_interval=0.03,
            match_failed_check=10,
            after_sleep=3,
            click=True,
            click_handle=self.handle_browser,
            deviation=deviation
        )
        if not find:
            return "步骤: 充值界面-点击游币兑换. 出现致命失误! 请联系开发者!"

        # 切换到游币选项, 准备输入一元开氪
        CUS_LOGGER.debug("充值界面 点击 氪金值输入框")

        # 点击请输入按钮
        find = loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=source_range_2,
            template=RESOURCE_P["top_up_money"]["充值界面_请输入.png"],
            match_tolerance=0.995,
            match_interval=0.03,
            match_failed_check=10,
            after_sleep=3,
            click=True,
            click_handle=self.handle_browser,
            deviation=deviation
        )
        if not find:
            return "步骤: 充值界面-点击-氪金值输入框. 出现致命失误! 请联系开发者!"

        CUS_LOGGER.debug("充值界面 输入1元")
        T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=self.handle_browser, key="1")
        time.sleep(1)

        # 取消输入框选中状态 并检查一元是否输入成功
        find = loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=source_range_2,
            template=RESOURCE_P["top_up_money"]["充值界面_游币兑换_已选中.png"],
            after_click_template=RESOURCE_P["top_up_money"]["充值界面_请输入_已输入.png"],
            match_tolerance=0.995,
            match_interval=0.03,
            match_failed_check=10,
            after_sleep=3,
            click=True,
            click_handle=self.handle_browser,
            deviation=deviation)
        if not find:
            return "步骤: 充值界面-复核-氪金值输入1元. 出现致命失误! 请联系开发者!"

        """点击氪金按钮 完成氪金"""
        CUS_LOGGER.debug("点击氪金按钮")
        find = loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=[150, 110, 800, 490],
            template=RESOURCE_P["top_up_money"]["充值界面_立即充值.png"],
            match_tolerance=0.99,
            match_interval=0.03,
            match_failed_check=10,
            after_sleep=3,
            click=True,
            click_handle=self.handle_browser,
            deviation=deviation)
        if not find:
            return "步骤: 充值界面-点击-立刻充值按钮. 出现致命失误! 请联系开发者!"

        # 退出到 每日充值界面
        CUS_LOGGER.debug("回到 每日必充 界面")
        find = loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=[750, 90, 815, 160],
            template=RESOURCE_P["top_up_money"]["充值界面_退出.png"],
            match_tolerance=0.99,
            match_interval=0.03,
            match_failed_check=10,
            after_sleep=3,
            click=True,
            click_handle=self.handle_browser,
            deviation=deviation)
        if not find:
            return "步骤: 充值界面-点击-退出充值界面按钮. 出现致命失误! 请联系开发者!"

        # 退出充值界面 刷新界面状态 才有领取按钮
        exit_ui()

        # 进入充值界面
        self.action_top_menu(mode="每日充值")

        # 充值成功领取
        find = loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=source_range_1,
            template=RESOURCE_P["top_up_money"]["每日必充_领取.png"],
            match_tolerance=0.99,
            match_interval=0.03,
            match_failed_check=4,
            after_sleep=3,
            click=True)

        # 退出充值界面
        exit_ui()

        if find:
            return "成功氪金并领取~"
        else:
            return "你游币用完了! 氪不了一点 orz"

    def fed_and_watered(self: "FAA") -> None:
        """
        公会施肥浇水功能
        """

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
            """
            进入施肥界面, 正确进入就跳出循环
            :return: 是否成功
            """
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

        def switch_guild_garden_by_try_times(try_times):
            """根据目前尝试次数, 到达不同的公会"""
            if try_times == 0:
                return

            # 点击全部公会
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=798, y=123)
            time.sleep(1)

            # 跳转到最后
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=843, y=305)
            time.sleep(1)

            # 1-4 即翻2页 2-8 即翻3页
            page = try_times // 4 + 1
            for i in range(page):
                # 向上翻的页数
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=843, y=194)
                time.sleep(1)

            # 点第几个
            my_dict = {1: 217, 2: 244, 3: 271, 4: 300}
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=self.handle,
                x=810,
                y=my_dict[(try_times - 1) % 4 + 1])
            time.sleep(1)

        def do_something_and_exit(try_times):
            """完成素质三连并退出公会花园界面"""
            # 采摘一次
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=785, y=471)
            time.sleep(1)

            # 浇水一次
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=785, y=362)
            time.sleep(1)

            # 等待一下 确保没有 提示任务完成黑屏
            loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[835, 35, 875, 75],
                template=RESOURCE_P["common"]["退出.png"],
                match_tolerance=0.95,
                match_failed_check=7,
                after_sleep=2,
                click=False
            )
            self.print_debug(text=f"{try_times + 1}/15 次尝试, 浇水后, 已确认无任务完成黑屏")

            # 施肥一次
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=785, y=418)
            time.sleep(1)
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=425, y=355)
            time.sleep(1)

            # 等待一下 确保没有 提示任务完成黑屏
            loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[835, 35, 875, 75],
                template=RESOURCE_P["common"]["退出.png"],
                match_tolerance=0.95,
                match_failed_check=7,
                after_sleep=2,
                click=False)
            self.print_debug(text=f"{try_times + 1}/15 次尝试, 施肥后, 已确认无任务完成黑屏")

        def check_completed_once(try_times):
            """
            :return: bool is completed  , bool is bugged
            """
            # 进入任务界面
            success = from_guild_to_quest_guild()
            if not success:
                return False, True

            # 检测施肥任务完成情况 任务是进行中的话为True
            quest_not_completed = loop_match_ps_in_w(
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

            if not quest_not_completed:
                self.print_debug(text=f"已完成公会浇水施肥, 尝试次数: {try_times}/15")
                return True, False

            return False, False

        def fed_and_watered_once(try_times):
            """
            :param try_times:
            :return: 是否出bug
            """

            # 进入施肥界面, 没有正确进入就跳出循环
            if not from_guild_to_guild_garden():
                return True

            # 根据目前尝试次数, 到达不同的公会
            switch_guild_garden_by_try_times(try_times=try_times)

            # 完成素质三连并退出公会花园界面
            do_something_and_exit(try_times=try_times)

            success = exit_to_guild_page_and_in_guild()
            if success:
                return True

            return False

        def fed_and_watered_multi_action(max_try_times):
            """
            :return: 是否完成了任务, 尝试次数, 是否是bug
            """
            # 循环到任务完成

            try_times = 0

            while True:

                is_completed, is_bug = check_completed_once(try_times=try_times)

                if is_completed:
                    return True, try_times, False
                if is_bug:
                    return False, try_times, True
                if try_times >= max_try_times:
                    return False, try_times, False

                is_bug = fed_and_watered_once(try_times=try_times)
                try_times += 1

                if is_bug:
                    return False, try_times, True

        def fed_and_watered_main():

            # 最大施肥尝试次数
            max_try_times = 20

            # 判定时间, 如果是北京时间周四的0到12点, 直接return
            beijing_tz = pytz.timezone('Asia/Shanghai')
            now = datetime.now(beijing_tz)
            if now.weekday() == 3 and 0 <= now.hour < 12:
                SIGNAL.PRINT_TO_UI.emit("[浇水 施肥 摘果 领取] 周四0-12点, 跳过本流程, 以防领取到上一期道具.")
                return

            SIGNAL.PRINT_TO_UI.emit(f"[浇水 施肥 摘果 领取] [{self.player}p] 开始执行... 最多{max_try_times}次")

            for reload_time in range(1, 4):

                # 进入公会
                is_bug = goto_guild_and_in_guild()
                if is_bug:
                    if reload_time != 3:
                        SIGNAL.PRINT_TO_UI.emit(
                            f"[浇水 施肥 摘果 领取] [{self.player}p] 锑食卡住了! 进入公会页失败... 刷新再试({reload_time}/3)")
                        self.reload_game()
                        continue
                    else:
                        SIGNAL.PRINT_TO_UI.emit(
                            f"[浇水 施肥 摘果 领取] [{self.player}p] 锑食卡住了! 进入公会页失败... 刷新跳过({reload_time}/3)")
                        self.reload_game()
                        break

                # 循环到任务完成或出现bug
                completed, try_times, is_bug = fed_and_watered_multi_action(max_try_times=max_try_times)

                if is_bug:
                    if reload_time < 3:
                        SIGNAL.PRINT_TO_UI.emit(
                            f"[浇水 施肥 摘果 领取] [{self.player}p] 锑食卡住 "
                            f"本轮循环施肥尝试:{try_times}次, 刷新, 再试, ({reload_time}/3)")
                        self.reload_game()
                        continue
                    else:
                        SIGNAL.PRINT_TO_UI.emit(
                            f"[浇水 施肥 摘果 领取] [{self.player}p] 锑食卡住 "
                            f"本轮循环施肥尝试:{try_times}次, 刷新, 跳过, ({reload_time}/3)")
                        self.reload_game()
                        break

                if completed:
                    # 正常完成
                    SIGNAL.PRINT_TO_UI.emit(
                        f"[浇水 施肥 摘果 领取] [{self.player}p] 正确完成 ~")
                    # 退出公会
                    self.action_exit(mode="普通红叉")
                    self.action_receive_quest_rewards(mode="公会任务")
                    break

                if try_times >= max_try_times:
                    SIGNAL.PRINT_TO_UI.emit(
                        f"[浇水 施肥 摘果 领取] [{self.player}p] 尝试{max_try_times}次, 肥料不够! 或全是解散公会! 刷新, 跳过 ")
                    self.reload_game()
                    break

        fed_and_watered_main()

    def use_items_consumables(self: "FAA") -> None:

        SIGNAL.PRINT_TO_UI.emit(text=f"[使用绑定消耗品] [{self.player}P] 开始.")

        # 打开背包
        self.print_debug(text="打开背包")
        self.action_bottom_menu(mode="背包")
        SIGNAL.PRINT_TO_UI.emit(text=f"[使用绑定消耗品] [{self.player}P] [装备栏] 图标需要加载, 等待10s")
        time.sleep(10)

        # 8次查找 7次下拉 查找所有正确图标 不需要升到最顶, 打开背包会自动重置
        for i in range(8):

            self.print_debug(text="第{}页物品".format(i + 1))

            # 第一次循环，点一下整理键
            if i == 0:
                # 点击整理物品按钮
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=905, y=475)
                time.sleep(2)
            # 最后一次循环，点一下整理键且回到背包最开始，尝试但大概率失败的, 处理在下层获得的物品
            elif i == 7:
                # 点击整理物品按钮
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=905, y=475)
                time.sleep(2)
                # 点击滚动条最上方以返回背包开始
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=916, y=115)
                time.sleep(2)
            # 第一次以外, 下滑3次 (一共下滑20次就到底部了)
            else:
                for j in range(3):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=920, y=422)
                    time.sleep(0.2)

            for item_name, item_image in g_resources.RESOURCE_CP["背包_装备_需使用的"].items():

                self.print_debug(text="物品:{}本页 开始查找".format(item_name))

                # 添加绑定角标
                item_image = overlay_images(
                    img_background=item_image,
                    img_overlay=RESOURCE_P["item"]["物品-绑定角标-背包.png"])  # 特别注意 背包和战利品使用的角标不一样!!!

                while True:

                    # 单一物品: 无脑点击点掉X 不再识图
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=450, y=190)
                    time.sleep(0.1)

                    # 礼包物品1: 在限定范围内 找红叉点掉 y=180-220
                    loop_match_p_in_w(
                        source_handle=self.handle,
                        source_root_handle=self.handle_360,
                        source_range=[680, 260, 720, 290],
                        template=RESOURCE_P["common"]["退出.png"],
                        match_tolerance=0.98,
                        match_interval=0.2,
                        match_failed_check=0,
                        after_sleep=0.1,
                        click=True)

                    # 礼包物品2: 在限定范围内 找红叉点掉 y=260-290
                    loop_match_p_in_w(
                        source_handle=self.handle,
                        source_root_handle=self.handle_360,
                        source_range=[680, 180, 720, 220],
                        template=RESOURCE_P["common"]["退出.png"],
                        match_tolerance=0.98,
                        match_interval=0.2,
                        match_failed_check=0,
                        after_sleep=0.1,
                        click=True)

                    # 在限定范围内 找物品
                    _, find = match_p_in_w(
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

        # 无脑点击点掉X 不再识图
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=450, y=190)
        time.sleep(0.1)
        # 在限定范围内 找红叉点掉
        loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=[425, 170, 715, 220],
            template=RESOURCE_P["common"]["退出.png"],
            match_tolerance=0.98,
            match_interval=0.2,
            match_failed_check=0,
            after_sleep=0.1,
            click=True)

        # 关闭背包
        self.action_exit(mode="普通红叉")

        SIGNAL.PRINT_TO_UI.emit(text=f"[使用绑定消耗品] [{self.player}P] 结束.")

    def use_items_double_card(self: "FAA", max_times: int) -> None:
        """
        使用双倍暴击卡的函数。

        在周六或周日不执行操作，其余时间会尝试使用指定数量的双倍暴击卡。

        :param max_times: 最大使用次数
        :return: None
        """

        def is_saturday_or_sunday():
            # 获取北京时间是星期几（0=星期一，1=星期二，...，5=星期六，6=星期日）
            weekday = datetime.now(pytz.timezone('Asia/Shanghai')).weekday()

            # 判断今天是否是星期六或星期日
            if weekday == 5 or weekday == 6:
                return True
            else:
                return False

        def loop_use_double_card():
            used_success = 0

            # 8次查找 7次下拉 不需要升到最顶,打开背包会自动重置
            for i in range(8):

                self.print_debug(text=f"[使用双暴卡] 第{i + 1}页物品 开始查找")

                # 第一次以外, 下滑3次点击 一共3*7=21次, 20次到底
                if i != 0:
                    for j in range(3):
                        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=920, y=422)
                        time.sleep(0.2)

                while True:

                    if used_success == max_times:
                        break

                    # 在限定范围内 找物品
                    find = loop_match_p_in_w(
                        source_handle=self.handle,
                        source_root_handle=self.handle_360,
                        source_range=[466, 86, 910, 435],
                        template=RESOURCE_P["item"]["物品-双暴卡.png"],
                        match_tolerance=0.98,
                        match_interval=0.2,
                        match_failed_check=2,
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
                SIGNAL.PRINT_TO_UI.emit(text="[使用双暴卡] 今天是星期六 / 星期日, 跳过")
                return

            # 打开背包
            self.print_debug(text="打开背包")
            self.action_bottom_menu(mode="背包")
            if self.player == 1:
                SIGNAL.PRINT_TO_UI.emit(text=f"[使用双暴卡] [{self.player}P] [装备栏] 图标需要加载, 等待10s")
            time.sleep(10)

            loop_use_double_card()

            # 关闭背包
            self.action_exit(mode="普通红叉")

        main()

    def input_level_2_password(self: "FAA", password: str):
        """
        输入二级密码. 通过背包内尝试拆主武器
        """

        SIGNAL.PRINT_TO_UI.emit(text=f"[输入二级密码] [{self.player}P] 开始.")

        # 打开背包
        self.action_bottom_menu(mode="背包")
        time.sleep(5)

        # 卸下主武器
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=210, y=445)
        time.sleep(1)

        # 点击输入框选中
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=440, y=300)
        time.sleep(1)

        # 输入二级密码
        for key in password:
            T_ACTION_QUEUE_TIMER.char_input(handle=self.handle, char=key)
            time.sleep(0.1)
        time.sleep(1)

        # 确定二级密码
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=435, y=388)
        time.sleep(1)

        # 关闭背包
        self.action_exit(mode="普通红叉")

        SIGNAL.PRINT_TO_UI.emit(text=f"[输入二级密码] [{self.player}P] 结束.")

    def gift_flower(self: "FAA"):
        """送免费花"""

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
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=500, y=290)
        time.sleep(1)

        # 点击送花按钮
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=50, y=260)
        time.sleep(1)

        # 选择免费花
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=350, y=300)
        time.sleep(1)

        # 点击送出
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=500, y=400)
        time.sleep(1)

        # 退出送花
        for i in range(2):
            self.action_exit(mode="普通红叉")

    def get_dark_crystal(self: "FAA"):
        """
        自动兑换暗晶的函数
        """

        SIGNAL.PRINT_TO_UI.emit(text=f"[兑换暗晶] [{self.player}P] 开始.")

        # 打开公会副本界面
        self.print_debug(text="跳转到公会副本界面")
        self.action_bottom_menu(mode="跳转_公会副本")

        # 打开暗晶商店
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=800, y=485)

        # 确保加载正确完成
        r = loop_match_p_in_w(
            source_handle=self.handle,
            source_range=[255, 15, 655, 60],
            template=RESOURCE_P["common"]["暗晶商店_ui.png"],
            match_tolerance=0.95,
            match_interval=0.2,
            match_failed_check=10,
            after_sleep=2,
            click=False
        )
        if r:
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

        if r:
            SIGNAL.PRINT_TO_UI.emit(text=f"[兑换暗晶] [{self.player}P] 执行完成.")
        else:
            SIGNAL.PRINT_TO_UI.emit(text=f"[兑换暗晶] [{self.player}P] 失败放弃. 游戏太卡")

    def delete_items(self: "FAA"):
        """用于删除多余的技能书类消耗品, 使用前需要输入二级或无二级密码"""

        self.print_debug(text="开启删除物品高危功能")

        # 打开背包
        self.print_debug(text="打开背包")
        self.action_bottom_menu(mode="背包")
        SIGNAL.PRINT_TO_UI.emit(text=f"[删除物品] [{self.player}P] [装备栏] 图标需要加载, 等待10s")
        time.sleep(10)

        # 点击到物品栏目
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=777, y=65)
        time.sleep(1)

        SIGNAL.PRINT_TO_UI.emit(text=f"[删除物品] [{self.player}P] [道具栏] 图标需要加载, 等待10s")
        time.sleep(10)

        # 点击整理物品按钮
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=905, y=475)
        time.sleep(2)

        # 下拉20次正好到底, 所以循环8次. 游戏自带复位 不需要手动复位
        for page in range(8):

            self.print_info(f"[删除物品] 背包第{page + 1}页, 将开始查找删除目标...")

            # 下拉三次每轮 慢点执行....
            if page != 0:
                for _ in range(3):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=920, y=420)
                    time.sleep(0.5)
                time.sleep(2)

            # 点击删除物品按钮
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=845, y=475)
            time.sleep(1)

            for i_name, i_image in g_resources.RESOURCE_CP["背包_道具_需删除的"].items():

                # 在限定范围内 找物品
                _, find = match_p_in_w(
                    source_handle=self.handle,
                    source_range=[466, 88, 910, 435],
                    template=i_image,
                    template_name=i_name,
                    mask=RESOURCE_P["item"]["物品-掩模-不绑定.png"],
                    match_tolerance=0.999,
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

        self.print_debug(text="指定物品已全部删除!")

        # 关闭背包
        self.action_exit(mode="普通红叉")

    def loop_cross_server(self: "FAA", deck: int):

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
            _, find = match_p_in_w(
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
