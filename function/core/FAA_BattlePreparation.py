import copy
import json
import os
import re
import time

import cv2

from function.common.bg_img_match import loop_match_ps_in_w, loop_match_p_in_w, match_p_in_w
from function.common.bg_img_screenshot import capture_image_png
from function.common.overlay_images import overlay_images
from function.core.analyzer_of_loot_logs import match_items_from_image_and_save
from function.globals import SIGNAL
from function.globals.g_resources import RESOURCE_P
from function.globals.get_paths import PATHS
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.match_ocr_text.get_stage_name_by_ocr import screen_get_stage_name
from function.scattered.read_json_to_stage_info import read_json_to_stage_info


class BattlePreparation:

    def __init__(self, faa):
        # __init__中捕获了的外部类属性值, 那么捕获的是那一刻的值, 后续对类属性的修改不会影响已经捕获的值
        # 但只捕获这个类本身, 在函数里调用的类属性, 则是实时值 √
        self.faa = faa

        file_name = os.path.join(PATHS["config"], "card_type.json")
        with open(file=file_name, mode='r', encoding='utf-8') as file:
            data = json.load(file)

        self.card_types = data

    """战前整备部分"""

    def _card_name_to_tar_list(self, card_name):
        """
        卡片标识名称 可以为 合法类名 模糊名(初始名称) 精准名(初始名称-转职数字)
        转化为对应的查找优先级列表
        """

        targets_0 = []
        """匹配 有效承载 保留字段"""
        if card_name == "有效承载":
            targets_0 += copy.deepcopy(self.faa.stage_info["mat_card"])
        else:
            """匹配合法类名"""
            # 仅匹配中文字符 (去除所有abc之类的同类卡后缀) 并参照已设定的类 是否有成功的匹配
            card_name_only_chinese = ''.join(re.compile(r'[\u4e00-\u9fff]+').findall(card_name))
            match_one = False
            for card_type in self.card_types:
                for card_type_key in card_type["key"]:
                    if card_type_key == card_name_only_chinese:
                        for card in card_type["value"]:
                            targets_0.append(card)
                        match_one = True

            # 不属于任何类型 直接加入targets
            if not match_one:
                targets_0.append(card_name_only_chinese)

        """第二 匹配转职"""
        targets_1 = []
        for card in targets_0:
            # 精准匹配
            if "-" in card:
                targets_1.append(card)
            # 模糊匹配 允许任意变种
            else:
                targets_1 += [f"{card}-{i}" for i in range(3, -1, -1)]

        # 只携带被记录图片的卡
        targets_1 = [card for card in targets_1 if (card + ".png") in RESOURCE_P["card"]["准备房间+"]]

        return targets_1

    def _scan_card(self, all_cards_precise_names):
        """
        战备选卡阶段 - 扫描所有卡片 找到符合标准的卡片中等级最高者
        :param all_cards_precise_names: 二维
        第0维代表卡组 其中每个值都代表标识名确立的一张卡片
        第1维代表标识名确立的一张卡片  其中每个值都代表精准名确立的一张卡片 不含.png后缀
        :return:
        """

        handle = self.faa.handle
        handle_360 = self.faa.handle_360

        # 强制要求全部走完, 防止12P的同步出问题
        # 老板本 一共20点击到底部, 向下点 10轮 x 2次 = 20 次滑块, 识别11次
        # 但仍然会出现识别不到的问题(我的背包太大啦), 故直接改成了最细的粒度, 希望能解决该问题.

        # 复位滑块
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=931, y=209)
        time.sleep(0.5)

        match_img_result_dict = {}

        # 以所有卡牌名称(不重复)为键, 识别结果为值的字典
        for card_precise_names in all_cards_precise_names:
            for card_precise_name in card_precise_names:
                if card_precise_name not in match_img_result_dict.keys():
                    match_img_result_dict[card_precise_name] = {"found": False, "position": 0}

        for i in range(21):

            for target in match_img_result_dict.keys():

                # 未找到
                if not match_img_result_dict[target]["found"]:
                    img_tar = overlay_images(
                        img_background=RESOURCE_P["card"]["准备房间+"][f"{target}.png"],
                        img_overlay=RESOURCE_P["card"]["卡片-房间-绑定角标.png"],
                        test_show=False)
                    find = loop_match_p_in_w(
                        source_handle=handle,
                        source_root_handle=handle_360,
                        source_range=[380, 175, 925, 415],
                        template=img_tar,
                        template_mask=RESOURCE_P["card"]["卡片-房间-掩模-绑定.png"],
                        match_tolerance=0.97,
                        match_failed_check=0,
                        match_interval=0.01,
                        after_sleep=0,
                        click=False)
                    if find:
                        match_img_result_dict[target]["found"] = True
                        match_img_result_dict[target]["position"] = copy.deepcopy(i)

            if i == 20:
                break
            # 仅还没找到继续下滑
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=931, y=400)
            # 需要刷新游戏帧数
            time.sleep(0.1)

        # 根据结果重新生成一个list 包含了每一个 标识名称 对应的 精准名称 找到的 最高等级的卡, 如果没找到 则为None
        scan_card_result_list = []
        scan_card_position_list = []
        for card_precise_names in all_cards_precise_names:
            for card_precise_name in card_precise_names:
                # 成功查找
                if match_img_result_dict[card_precise_name]["found"]:
                    scan_card_result_list.append(card_precise_name)
                    scan_card_position_list.append(match_img_result_dict[card_precise_name]["position"])
                    match_img_result_dict[card_precise_name]["found"] = False
                    break
            else:
                # 没有找到
                scan_card_result_list.append(None)
                scan_card_position_list.append(None)

        return scan_card_result_list, scan_card_position_list

    def _add_card(self, card_name, tar_position=None) -> bool:
        """
        战备选卡阶段 - 选中添加一张卡到卡组
        :param tar_position: 预扫描在第几次下拉找到了对应卡片, 如果有该值 直达
        :param card_name: 卡片标识名称 可以为 合法类名 模糊名(初始名称) 精准名(初始名称-转职数字)
        :return:
        """

        handle = self.faa.handle
        handle_360 = self.faa.handle_360

        if tar_position is None:
            targets = self._card_name_to_tar_list(card_name=card_name)
        else:
            # 有预扫描步骤 一步到位
            targets = [card_name]

        found_card = False

        # 强制要求全部走完, 防止12P的同步出问题
        # 老板本 一共20点击到底部, 向下点 10轮 x 2次 = 20 次滑块, 识别11次
        # 但仍然会出现识别不到的问题(我的背包太大啦), 故直接改成了最细的粒度, 希望能解决该问题.
        for target in targets:

            # 复位滑块
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=931, y=209)
            time.sleep(0.1)

            for i in range(21):
                if tar_position is None or i >= tar_position:
                    # 需要刷新游戏帧数
                    img_tar = overlay_images(
                        img_background=RESOURCE_P["card"]["准备房间+"][f"{target}.png"],
                        img_overlay=RESOURCE_P["card"]["卡片-房间-绑定角标.png"],
                        test_show=False)
                    find = loop_match_p_in_w(
                        source_handle=handle,
                        source_root_handle=handle_360,
                        source_range=[380, 175, 925, 415],
                        template=img_tar,
                        template_mask=RESOURCE_P["card"]["卡片-房间-掩模-绑定.png"],
                        match_tolerance=0.97,
                        match_failed_check=0.15,
                        match_interval=0.05,
                        after_sleep=0,
                        click=True)
                    if find:
                        found_card = True
                        break
                else:
                    if i == 20:
                        break
                    # 仅还没找到继续下滑
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=931, y=400)
                    time.sleep(0.1)

            if found_card:
                return True

        return False

    def _add_cards(self, card_name_list: list, can_failed_list: list):
        """
        战备选卡阶段 - 按顺序选中若干张卡添加到卡组
        :param card_name_list: list [str, ...] 包含若干卡片 标识名称(Identifier Name)
        可以为 合法类名(Valid Class Name) 模糊名称(Fuzzy Name, 卡片不转职名称) 精准名称(Precise Name, 模糊名-转职数字)
        最终都可以拓展为若干个 精准名称
        :param can_failed_list: 和card_name_list 一一对应 每一张卡是否允许失败
        :return: 是否成功选卡每一张
        """
        self.faa.print_debug(text="[选取卡片] 开始, 总计: {}张".format(len(card_name_list)))

        # 先展开 战斗方案中 带卡的 标识名称 为 精确名称 包含.png后缀
        # 一个标识名称 应对多个精准名
        all_cards_precise_names = []
        for card_name in card_name_list:
            precise_names = self._card_name_to_tar_list(card_name=card_name)
            all_cards_precise_names.append(precise_names)

        # 一轮识别 识别同一张卡的所有精准名称中 哪一个是实际存在且优先级最高的
        scan_card_name_list, scan_card_position_list = self._scan_card(
            all_cards_precise_names=all_cards_precise_names)
        self.faa.print_debug(text="[选取卡片] 经识别将查找以下有效卡片: {}, 位置: {}".format(
            scan_card_name_list, scan_card_position_list))

        # 如果不允许失败 提前检查
        for index in range(len(can_failed_list)):
            if (scan_card_name_list[index] is None) and (not can_failed_list[index]):
                self.faa.print_debug(text="[选取卡片] 结束, 结果: 因查找失败中断")
                return False

        for index in range(len(scan_card_name_list)):
            card_name = scan_card_name_list[index]
            tar_position = scan_card_position_list[index]
            if card_name is None:
                continue
            # 理论上 经过了筛查 选卡失败基本上仅是因为 和其他卡片有冲突 这只会出现在非必要承载卡 可以忽视
            result = self._add_card(card_name=card_name, tar_position=tar_position)
            self.faa.print_debug(text="[选取卡片] [{}]完成, 结果: {}".format(card_name, "成功" if result else "失败"))

        return True

    def _add_quest_card(self):

        quest_card = copy.deepcopy(self.faa.quest_card)

        not_need_add = False
        not_need_add = not_need_add or quest_card == "None"
        not_need_add = not_need_add or quest_card is None

        if not_need_add:
            self.faa.print_debug(text=f"[添加任务卡] 不需要,跳过")
            return
        else:
            self.faa.print_debug(text=f"[添加任务卡] 开始, 目标:{quest_card}")

        # 调用选卡
        found_card = self._add_card(card_name=quest_card)

        if not found_card:
            # 如果没有找到 类属性 战斗方案 需要调整为None, 防止在战斗中使用对应卡片的动作序列出现
            self.faa.quest_card = "None"

        self.faa.print_debug(text="[添加任务卡] 完成, 结果:{}".format("成功" if found_card else "失败"))

    def _remove_ban_card(self):
        """寻找并移除需要ban的卡, 现已支持跨页ban"""

        handle = self.faa.handle
        ban_card_list = copy.deepcopy(self.faa.ban_card_list)
        print_debug = self.faa.print_debug

        if ban_card_list:
            print_debug(text=f"[移除卡片] 开始, 目标:{ban_card_list}")
        else:
            print_debug(text=f"[移除卡片] 不需要,跳过")
            return

        # 由于ban卡的特性, 要先将所有ban卡的变种都加入列表中, 再进行ban
        my_list = []
        for ban_card in ban_card_list:
            if "-" in ban_card:
                # 对于名称带-的卡, 就对应的写入, 如果不带-, 就查找其所有变种
                my_list.append(f"{ban_card}.png")
            else:
                # 对于不包含"-"的ban_card，添加其所有21种变种到列表中
                my_list.extend([f"{ban_card}-{i}.png" for i in range(21)])
        ban_card_list = my_list

        # 读取所有已记录的卡片文件名, 并去除没有记录的卡片
        ban_card_list = [ban_card for ban_card in ban_card_list if ban_card in RESOURCE_P["card"]["准备房间-"]]

        # 翻页回第一页
        for i in range(5):
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=930, y=55)
            time.sleep(0.05)

        # 第一页
        self._screen_ban_card_loop_a_round(ban_card_s=ban_card_list)

        # 翻页到第二页
        for i in range(5):
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=930, y=85)
            time.sleep(0.05)

        # 第二页
        self._screen_ban_card_loop_a_round(ban_card_s=ban_card_list)

    def _check_stage_name(self, stage_name):
        """
        根据检测出的关卡名，改变faa当前的stage_info
        """

        # 原有的关卡id
        stage_id = self.faa.stage_info["id"]

        # 特殊关卡列表占位符
        happy_holiday_list = []
        reward_list = []
        roaming_list = []

        special_stage = True
        match stage_name:
            case _ if "魔塔蛋糕" in stage_name:
                level = stage_name.replace("魔塔蛋糕第", "").replace("层", "")
                self.faa.stage_info = read_json_to_stage_info(
                    stage_id=stage_id,
                    stage_id_for_battle=f"MT-1-{level}"
                )

            case _ if "双人魔塔" in stage_name:
                level = stage_name.replace("双人魔塔第", "").replace("层", "")
                self.faa.stage_info = read_json_to_stage_info(
                    stage_id=stage_id,
                    stage_id_for_battle=f"MT-2-{level}")

            case _ if "萌宠神殿" in stage_name:
                level = stage_name.replace("萌宠神殿第", "").replace("层", "")
                self.faa.stage_info = read_json_to_stage_info(
                    stage_id=stage_id,
                    stage_id_for_battle=f"PT-0-{level}"
                )

            case _ if stage_name in happy_holiday_list:
                pass

            case _ if stage_name in reward_list:
                pass

            case _ if stage_name in roaming_list:
                pass

            case _:
                special_stage = False

        if special_stage:
            SIGNAL.PRINT_TO_UI.emit(f"检测到特殊关卡：{stage_name}，已为你启用对应关卡方案", 7)

    def _screen_ban_card_loop_a_round(self, ban_card_s):

        handle = self.faa.handle
        handle_360 = self.faa.handle_360

        for card in ban_card_s:
            img_tar = overlay_images(
                img_background=RESOURCE_P["card"]["准备房间-"][card],
                img_overlay=RESOURCE_P["card"]["卡片-房间-绑定角标.png"],
                test_show=False)

            # 只ban被记录了图片的变种卡
            loop_match_p_in_w(
                source_handle=handle,
                source_root_handle=handle_360,
                source_range=[380, 40, 915, 105],
                template=img_tar,
                template_mask=RESOURCE_P["card"]["卡片-房间-掩模-绑定.png"],
                match_tolerance=0.98,
                match_interval=0.2,
                match_failed_check=0.6,
                after_sleep=1,
                click=True)

    def _get_card_name_list_from_battle_plan(self):

        mats = copy.deepcopy(self.faa.stage_info["mat_card"])

        # 和 card_list 一一对应 顺序一致 代表这张卡是否允许被跳过
        plan = copy.deepcopy(self.faa.battle_plan)

        my_dict = {}

        # 先取默认中
        for card in plan["card"]["default"]:
            if card["id"] not in my_dict.keys():
                my_dict[card["id"]] = card["name"]

        # 再取变阵中
        for wave_plan in plan["card"]["wave"].values():
            for card in wave_plan:
                if card["id"] not in my_dict.keys():
                    my_dict[card["id"]] = card["name"]

        # 增承载卡
        # 根据id 排序 并取其中的value为list
        sorted_list = list(dict(sorted(my_dict.items())).values())
        can_failed_list = [False for _ in sorted_list]

        # 如果需要任意承载卡 第一张卡设定为 字段 有效承载
        if len(mats) >= 1:
            sorted_list += ["有效承载"]
            can_failed_list += [False]

        # 添加冰沙 复制类
        sorted_list += ["冰淇淋-2", "创造神", "幻幻鸡"]
        can_failed_list += [True, True, True]

        # 如果有效承载数量 >= 2
        if len(mats) >= 2:
            for _ in range(len(mats) - 1):
                sorted_list += ["有效承载"]
                can_failed_list += [True]

        return sorted_list, can_failed_list

    def check_create_room_success(self):
        """
        战前准备 确定进入房间
        :return: 0-正常结束 1-重启本次 2-跳过本次 3-跳过所有次数
        """

        # 循环查找开始按键
        self.faa.print_debug(text="寻找开始或准备按钮")
        find = loop_match_p_in_w(
            source_handle=self.faa.handle,
            source_root_handle=self.faa.handle_360,
            source_range=[796, 413, 950, 485],
            template=RESOURCE_P["common"]["战斗"]["战斗前_开始按钮.png"],
            match_interval=1,
            match_failed_check=10,
            after_sleep=0.3,
            click=False)
        if not find:
            self.faa.print_warning(text="创建房间后, 10s找不到[开始/准备]字样! 创建房间可能失败!")
            # 2-跳过本次 可能是由于: 服务器抽风无法创建房间 or 点击被吞 or 次数用尽
            return 2
        return 0

    def change_deck(self):
        """
        战前准备 修改卡组
        :return: 0-正常结束 1-重启本次 2-跳过本次 3-跳过所有次数
        """
        # 识别出当前关卡名称
        stage_name = screen_get_stage_name(self.faa.handle, self.faa.handle_360)
        self.faa.print_debug(text=f"当前关卡:{stage_name}")

        # 检测关卡名变种，如果符合特定关卡，则修改当前战斗的关卡信息
        self._check_stage_name(stage_name)

        # 选择卡组
        self.faa.print_debug(text="选择卡组, 并开始加入新卡和ban卡")

        T_ACTION_QUEUE_TIMER.add_click_to_queue(
            handle=self.faa.handle,
            x={1: 425, 2: 523, 3: 588, 4: 666, 5: 756, 6: 837}[self.faa.deck],
            y=121)
        time.sleep(0.7)

        """寻找并卡片, 包括自动带卡 / 任务要求的带卡和禁卡"""

        if self.faa.auto_carry_card:

            card_name_list, can_failed_list = self._get_card_name_list_from_battle_plan()
            success = self._add_cards(card_name_list=card_name_list, can_failed_list=can_failed_list)
            # 失败就会直接跳过本关卡全部场次！
            if not success:
                return 3

        else:
            #  任务需求的带卡 在自动带卡中会自动处理, 此处是无自动带卡时的处理
            self._add_quest_card()

        self._remove_ban_card()

        return 0

    def start_and_ensure_entry(self):
        """开始并确保进入成功"""

        # 点击开始
        find = loop_match_p_in_w(
            source_handle=self.faa.handle,
            source_root_handle=self.faa.handle_360,
            source_range=[796, 413, 950, 485],
            template=RESOURCE_P["common"]["战斗"]["战斗前_开始按钮.png"],
            match_tolerance=0.95,
            match_interval=1,
            match_failed_check=10,
            after_sleep=1,
            click=True)
        if not find:
            self.faa.print_warning(text="选择卡组后, 10s找不到[开始/准备]字样! 创建房间可能失败!")
            return 1  # 1-重启本次

        # 防止被 [没有带xx卡] or []包已满 卡住
        find = match_p_in_w(
            source_handle=self.faa.handle,
            source_root_handle=self.faa.handle_360,
            source_range=[0, 0, 950, 600],
            template=RESOURCE_P["common"]["战斗"]["战斗前_系统提示.png"],
            match_tolerance=0.98)
        if find:
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.faa.handle, x=427, y=353)
            time.sleep(0.05)

        # 刷新ui: 状态文本
        self.faa.print_debug(text="查找火苗标识物, 等待进入战斗, 限时30s")

        # 循环查找火苗图标 找到战斗开始
        find = loop_match_p_in_w(
            source_handle=self.faa.handle,
            source_root_handle=self.faa.handle_360,
            source_range=[0, 0, 950, 600],
            template=RESOURCE_P["common"]["战斗"]["战斗中_火苗能量.png"],
            match_interval=0.5,
            match_failed_check=30,
            after_sleep=0.1,
            click=False)

        # 刷新ui: 状态文本
        if find:
            self.faa.print_debug(text="找到火苗标识物, 战斗进行中...")
            return 0  # 0-一切顺利
        else:
            self.faa.print_warning(text="未能找到火苗标识物, 进入战斗失败, 可能是次数不足或服务器卡顿")
            return 2  # 2-跳过本次

    """初始化战斗方案部分"""

    # 在FAA中实现 需要修改FAA的类属性

    """战斗结束战利品的领取和捕获图片并识别部分"""

    def action_and_capture_loots(self):
        """
        :return: 捕获的战利品dict
        """

        handle = self.faa.handle
        handle_360 = self.faa.handle_360

        # 记录战利品 tip 一张图49x49 是完美规整的
        images = []

        # 防止 已有选中的卡片, 先点击空白
        T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=handle, x=200, y=350)
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=200, y=350)
        time.sleep(0.025)

        # 1 2 行
        for i in range(3):
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=708, y=484)
            time.sleep(0.05)
        time.sleep(0.25)
        images.append(capture_image_png(handle=handle, raw_range=[209, 454, 699, 552], root_handle=handle_360))
        time.sleep(0.25)

        # 3 4 行 取3行
        for i in range(3):
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=708, y=510)
            time.sleep(0.05)
        time.sleep(0.25)
        images.append(capture_image_png(handle=handle, raw_range=[209, 456, 699, 505], root_handle=handle_360))
        time.sleep(0.25)

        # 4 5 行
        for i in range(3):
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=708, y=529)
            time.sleep(0.05)
        time.sleep(0.25)
        images.append(capture_image_png(handle=handle, raw_range=[209, 454, 699, 552], root_handle=handle_360))
        time.sleep(0.25)

        # 垂直拼接
        image = cv2.vconcat(images)

        return image

    def capture_and_match_loots(self) -> list:
        """
        :return: 捕获的战利品dict
        """

        handle = self.faa.handle
        handle_360 = self.faa.handle_360
        print_info = self.faa.print_info
        player = self.faa.player
        stage_info = self.faa.stage_info

        # 是否在战利品ui界面
        find = loop_match_p_in_w(
            source_handle=handle,
            source_root_handle=handle_360,
            source_range=[202, 419, 306, 461],
            template=RESOURCE_P["common"]["战斗"]["战斗后_1_战利品.png"],
            match_failed_check=2,
            match_tolerance=0.99,
            click=False)

        if find:
            print_info(text="[战利品UI] 正常结束, 尝试捕获战利品截图")

            # 让2P总在1P后开始运行该功能, 防止1P清空了2P的动作操作
            if player == 2:
                time.sleep(0.666)

            # 清空队列
            if player == 1:
                T_ACTION_QUEUE_TIMER.action_queue.queue.clear()
                print_info(text="战斗结束, 成功清空所有点击队列残留!")

            # 点击一下空白区域以确保指针位置的卡片图像不会影响到战利品截图
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=50, y=50)
            time.sleep(0.05)

            # 定义保存路径和文件名格式
            img_path = "{}\\{}_{}P_{}.png".format(
                PATHS["logs"] + "\\loots_image",
                stage_info["id"],
                player,
                time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime())
            )

            # 捕获战利品截图 动作+拼接
            img = self.action_and_capture_loots()

            # 分析图片，获取战利品字典
            drop_list = match_items_from_image_and_save(
                img_save_path=img_path,
                image=img,
                mode='loots',
                test_print=True)
            print_info(text="[捕获战利品] 处在战利品UI 战利品已 捕获/识别/保存".format(drop_list))

            return drop_list

        else:
            print_info(text="[捕获战利品] 未在战利品UI 可能由于延迟未能捕获战利品, 继续流程")

            return []

    def capture_and_match_treasure_chests(self) -> list:

        handle = self.faa.handle
        handle_360 = self.faa.handle_360
        stage_info = self.faa.stage_info
        player = self.faa.player
        is_group = self.faa.is_group
        print_info = self.faa.print_info
        print_warning = self.faa.print_warning

        find = loop_match_p_in_w(
            source_handle=handle,
            source_root_handle=handle_360,
            source_range=[400, 35, 550, 75],
            template=RESOURCE_P["common"]["战斗"]["战斗后_4_翻宝箱.png"],
            match_failed_check=15,
            after_sleep=2,
            click=False
        )
        if find:
            print_info(text="[翻宝箱UI] 捕获到正确标志, 翻牌并退出...")
            # 开始洗牌
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=708, y=502)
            time.sleep(6)

            # 翻牌 1+2
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=550, y=170)
            time.sleep(0.5)
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=708, y=170)
            time.sleep(1.5)

            img = [
                capture_image_png(
                    handle=handle,
                    raw_range=[249, 89, 293, 133],
                    root_handle=handle_360),
                capture_image_png(
                    handle=handle,
                    raw_range=[317, 89, 361, 133],
                    root_handle=handle_360),
            ]

            img = cv2.hconcat(img)

            # 定义保存路径和文件名格式
            img_path = "{}\\{}_{}P_{}.png".format(
                PATHS["logs"] + "\\chests_image",
                stage_info["id"],
                player,
                time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime())
            )

            # 分析图片，获取战利品字典
            drop_list = match_items_from_image_and_save(
                img_save_path=img_path,
                image=img
                , mode="chests",
                test_print=True)
            print_info(text="[翻宝箱UI] 宝箱已 捕获/识别/保存".format(drop_list))

            # 组队2P慢点结束翻牌 保证双人魔塔后自己是房主
            if is_group and player == 2:
                time.sleep(2)

            # 结束翻牌
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=708, y=502)
            time.sleep(3)

            return drop_list

        else:
            print_warning(text="[翻宝箱UI] 15s未能捕获正确标志, 出问题了!")
            return []

    def perform_action_capture_match_for_loots_and_chests(self):
        """
        战斗结束后, 完成下述流程: 潜在的任务完成黑屏-> 战利品 -> 战斗结算 -> 翻宝箱 -> 回到房间/魔塔会回到其他界面
        :return: int 状态码; None或dict, {"loots": [], "chests": []}
        """

        print_debug = self.faa.print_debug
        screen_check_server_boom = self.faa.screen_check_server_boom
        print_warning = self.faa.print_warning

        print_debug(text="识别到多种战斗结束标志之一, 进行收尾工作")

        # 战利品部分, 会先检测是否在对应界面
        loots_list = self.capture_and_match_loots()

        # 翻宝箱部分, 会先检测是否在对应界面
        chests_list = self.capture_and_match_treasure_chests()

        # 重整化 loots_dict 和 chests_dict 一定是dict()
        result_loot = {"loots": loots_list, "chests": chests_list}

        if screen_check_server_boom():
            print_warning(text="检测到 断开连接 or 登录超时 or Flash爆炸, 炸服了")
            return 1, None  # 1-重启本次

        else:
            return 0, result_loot

    """补充一个用于确保正确完成了战斗的Check点"""

    def wrap_up(self):

        """
        房间内或其他地方 战斗结束
        :return: 0-正常结束 1-重启本次 2-跳过本次
        """

        handle = self.faa.handle
        handle_360 = self.faa.handle_360
        print_debug = self.faa.print_debug
        print_error = self.faa.print_error

        print_debug(text="[开始/准备/魔塔蛋糕UI] 尝试捕获正确标志, 以完成战斗流程.")
        find = loop_match_ps_in_w(
            source_handle=handle,
            source_root_handle=handle_360,
            template_opts=[
                {
                    "source_range": [796, 413, 950, 485],
                    "template": RESOURCE_P["common"]["战斗"]["战斗前_开始按钮.png"],
                    "match_tolerance": 0.99},
                {
                    "source_range": [200, 0, 750, 100],
                    "template": RESOURCE_P["common"]["魔塔蛋糕_ui.png"],
                    "match_tolerance": 0.99
                }],
            return_mode="or",
            match_failed_check=10,
            match_interval=0.2)
        if find:
            print_debug(text="成功捕获[开始/准备/魔塔蛋糕UI], 完成战斗流程.")
            return 0  # 0-正常结束
        else:
            print_error(text="10s没能捕获[开始/准备/魔塔蛋糕UI], 出现意外错误, 直接跳过本次")
            return 2  # 2-跳过本次