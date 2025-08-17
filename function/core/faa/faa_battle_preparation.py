import copy
import re
import time
from typing import TYPE_CHECKING

import cv2
import numpy as np

from function.common.bg_img_match import loop_match_ps_in_w, loop_match_p_in_w, match_p_in_w
from function.common.bg_img_screenshot import capture_image_png
from function.common.overlay_images import overlay_images
from function.core.analyzer_of_loot_logs import match_items_from_image_and_save
from function.globals import SIGNAL, EXTRA
from function.globals.g_resources import RESOURCE_P
from function.globals.get_paths import PATHS
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.gat_handle import faa_get_handle
from function.scattered.read_json_to_stage_info import read_json_to_stage_info

if TYPE_CHECKING:
    from function.core.faa.faa_mix import FAA

scan_card_x_list = [
    [386, 426],
    [435, 475],
    [484, 524],
    [533, 573],
    [582, 622],
    [631, 671],
    [680, 720],
    [729, 769],
    [778, 818],
    [827, 867],
    [876, 916]
]


def crop_and_concat_columns(img, y1=179, y2=409):
    """
    按列裁剪并横向拼接图像
    :param img: 原始屏幕截图(numpy数组格式)
    :param y1: 纵向起始坐标
    :param y2: 纵向结束坐标
    :return: 拼接后的新图像
    """
    # 纵向裁剪公共区域
    common_area = img[y1:y2, :]

    # 横向裁剪各列
    columns = []
    for x_range in scan_card_x_list:
        x_start, x_end = x_range
        # 防止超出图像边界
        x_end = min(x_end, common_area.shape[1])
        columns.append(common_area[:, x_start:x_end])

    # 横向拼接所有列
    return cv2.hconcat(columns)


def generate_mask_and_crop(img, y1=179, y2=409):
    """
    生成索引区域掩码并裁剪图像
    :param img: 原始图像 (numpy数组)
    :param y1: 纵向起始坐标
    :param y2: 纵向结束坐标
    :return: (掩码图像, 裁剪后的图像)
    """
    # 计算裁剪范围
    x1 = min([x[0] for x in scan_card_x_list])  # 最小的起始x坐标
    x2 = max([x[1] for x in scan_card_x_list])  # 最大的结束x坐标

    # 裁剪图像到索引区域
    cropped = img[y1:y2, x1:x2]

    # 创建全黑掩码（单通道）
    mask = np.zeros(cropped.shape[:2], dtype=np.uint8)

    # 绘制有效列区域
    for x_range in scan_card_x_list:
        start = x_range[0] - x1  # 转换为相对坐标
        end = x_range[1] - x1  # 转换为相对坐标
        mask[:, start:end] = 255  # 将对应区域设为白色（值为255）

    return mask, cropped


def scan_card(handle, handle_360, template, click=False):
    for x in scan_card_x_list:

        # 需要优化

        find = loop_match_p_in_w(
            source_handle=handle,
            source_root_handle=handle_360,
            source_range=[x[0], 175, x[1], 415],
            template=template,
            template_mask=RESOURCE_P["card"]["卡片-房间-掩模-绑定.png"],
            match_tolerance=0.998,
            match_failed_check=0,
            match_interval=0,
            after_sleep=0,
            click=click)
        if find:
            return True
    return False


class BattlePreparation:
    """
    封装了战斗前的准备工作和战斗后收尾工作的类
    即: 进入房间 -> 开始战斗 + 战斗结束收尾

    包括:
    1. 检测是否成功进入房间
    2. 战斗前的选卡/禁卡 包括对任务卡的处理
    3. 点击开始 并检测是否成功开始
    4. 战斗后的战利品扫描/翻牌动作+扫描
    5. 战斗结束后成功回房检测
    """

    """战前整备部分"""

    def _card_name_to_tar_list(self: "FAA", card_name):
        """
        卡片标识名称 可以为 合法类名 模糊名(初始名称) 精准名(初始名称-转职数字)
        转化为对应的查找优先级列表
        """

        targets_0 = []
        """匹配 有效承载 保留字段"""
        if card_name == "有效承载":
            targets_0 += copy.deepcopy(self.stage_info["mat_card"])
        else:
            # 仅匹配中文字符 (去除所有abc之类的同类卡后缀) 并参照已设定的类 是否有成功的匹配
            match = re.match(r'^(.*[\u4e00-\u9fff])', card_name)
            card_name_only_chinese = match.group(1) if match else ""
            match_one = False

            """匹配合法类名"""
            for card_type in self.card_types:
                for card_type_key in card_type["key"]:
                    if card_type_key == card_name_only_chinese:
                        for card in card_type["value"]:
                            targets_0.append(card)
                        match_one = True

            """不属于任何类型"""
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
        targets_1 = [card for card in targets_1 if (card + ".png") in RESOURCE_P["card"]["准备房间"]]

        return targets_1

    def _scan_card(self: "FAA", all_cards_precise_names):
        """
        战备选卡阶段 - 扫描所有卡片 找到符合标准的卡片中等级最高者
        :param all_cards_precise_names: 二维
        第0维代表卡组 其中每个值都代表标识名确立的一张卡片
        第1维代表标识名确立的一张卡片  其中每个值都代表精准名确立的一张卡片 不含.png后缀
        :return:
        """

        handle = self.handle
        handle_360 = self.handle_360

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

        # 先处理叠加图片
        resource_p = {}
        for target in match_img_result_dict.keys():
            img_tar = overlay_images(
                img_background=RESOURCE_P["card"]["准备房间"][f"{target}.png"],
                img_overlay=RESOURCE_P["card"]["卡片-房间-绑定角标.png"],
                test_show=False)
            resource_p[target] = img_tar

        for i in range(21):

            # 截图复用
            img = capture_image_png(
                handle=handle,
                raw_range=[0, 0, 950, 600],
                root_handle=handle_360)
            # 去除无效像素
            img = crop_and_concat_columns(img=img)
            # 获得图像哈希
            img_hash = hash(img.tobytes())

            for target in match_img_result_dict.keys():

                # 未找到
                if not match_img_result_dict[target]["found"]:

                    _, result = match_p_in_w(
                        source_img=img,
                        template=resource_p[target],
                        mask=RESOURCE_P["card"]["卡片-房间-掩模-绑定.png"],
                        match_tolerance=0.998,
                    )
                    if result:
                        match_img_result_dict[target]["found"] = True
                        match_img_result_dict[target]["position"] = copy.deepcopy(i)

            if i == 20:
                break
            # 仅还没找到继续下滑
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=931, y=400)
            # 动态确认滑成功
            for _ in range(20):
                current_img = capture_image_png(
                    handle=handle,
                    raw_range=[0, 0, 950, 600],
                    root_handle=handle_360)
                # 去除无效像素
                current_img = crop_and_concat_columns(img=current_img)
                # 获得图像哈希
                current_img_hash = hash(current_img.tobytes())
                if current_img_hash != img_hash:
                    break
                time.sleep(0.03)

        # 根据结果重新生成一个list 包含了每一个 标识名称 对应的 精准名称 找到的 最高等级的卡, 如果没找到 则为None
        scan_card_result_list = []
        scan_card_position_list = []
        for card_precise_names in all_cards_precise_names:
            for card_precise_name in card_precise_names:
                # 成功查找
                if match_img_result_dict[card_precise_name]["found"]:
                    scan_card_result_list.append(card_precise_name)
                    scan_card_position_list.append(match_img_result_dict[card_precise_name]["position"])
                    card_name_without_id = card_precise_name.split("-")[0]
                    # 将所有名称相同(不含转职的 -X)的卡片都设置为 未找到
                    for i in [0, 1, 2, 3]:
                        card_be_used = match_img_result_dict.get(f"{card_name_without_id}-{i}")
                        if card_be_used:
                            card_be_used["found"] = False
                    break
            else:
                # 没有找到
                scan_card_result_list.append(None)
                scan_card_position_list.append(None)

        return scan_card_result_list, scan_card_position_list

    def _add_card(self: "FAA", card_name, tar_position=None) -> bool:
        """
        战备选卡阶段 - 选中添加一张卡到卡组
        :param tar_position: 预扫描在第几次下拉找到了对应卡片, 如果有该值 直达
        :param card_name: 卡片标识名称 可以为 合法类名 模糊名(初始名称) 精准名(初始名称-转职数字)
        :return:
        """

        handle = self.handle
        handle_360 = self.handle_360

        if tar_position is None:
            targets = self._card_name_to_tar_list(card_name=card_name)
        else:
            # 有预扫描步骤 一步到位
            targets = [card_name]

        found_card = False

        # 先叠加图片 储存
        resource_p = {}
        for target in targets:
            img_tar = overlay_images(
                img_background=RESOURCE_P["card"]["准备房间"][f"{target}.png"],
                img_overlay=RESOURCE_P["card"]["卡片-房间-绑定角标.png"],
                test_show=False)
            resource_p[target] = img_tar

        # 强制要求全部走完, 防止12P的同步出问题
        # 老板本 一共20点击到底部, 向下点 10轮 x 2次 = 20 次滑块, 识别11次
        # 但仍然会出现识别不到的问题(我的背包太大啦), 故直接改成了最细的粒度, 希望能解决该问题.
        # 大大降低了操作速度 防止卡顿造成选卡失败~
        for target in targets:

            # 复位滑块
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=931, y=209)
            time.sleep(0.25)

            for i in range(21):
                if tar_position is None or i >= tar_position:

                    # 到达了对应位置, 先等一下实际的游戏控件刷新, 画面刷新 ≠ 控件刷新
                    time.sleep(0.2)

                    # 需要刷新游戏帧数
                    find = loop_match_p_in_w(
                        source_handle=handle,
                        source_root_handle=handle_360,
                        source_range=[380, 175, 925, 415],
                        template=resource_p[target],
                        template_mask=RESOURCE_P["card"]["卡片-房间-掩模-绑定.png"],
                        match_tolerance=0.998,
                        match_failed_check=0.2,
                        match_interval=0.1,
                        after_sleep=0.25,
                        click=True)
                    if find:
                        found_card = True
                        break

                if i == 20:
                    break

                # 仅还没找到继续下滑
                img = capture_image_png(
                    handle=handle,
                    raw_range=[0, 0, 950, 600],
                    root_handle=handle_360)
                img = crop_and_concat_columns(img=img)
                img_hash = hash(img.tobytes())

                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=931, y=400)

                # 动态等待图像刷新
                for _ in range(20):
                    current_img = capture_image_png(
                        handle=handle,
                        raw_range=[0, 0, 950, 600],
                        root_handle=handle_360)
                    current_img = crop_and_concat_columns(img=current_img)
                    current_img_hash = hash(current_img.tobytes())
                    if current_img_hash != img_hash:
                        break
                    time.sleep(0.03)

            if found_card:
                return True

        return False

    def _add_cards(self: "FAA", card_name_list: list, can_failed_list: list):
        """
        战备选卡阶段 - 按顺序选中若干张卡添加到卡组
        :param card_name_list: list [str, ...] 包含若干卡片 标识名称(Identifier Name)
        可以为 合法类名(Valid Class Name) 模糊名称(Fuzzy Name, 卡片不转职名称) 精准名称(Precise Name, 模糊名-转职数字)
        最终都可以拓展为若干个 精准名称
        :param can_failed_list: 和card_name_list 一一对应 每一张卡是否允许失败
        :return: 是否成功选卡每一张
        """
        self.print_debug(text="[选取卡片] 开始, 总计: {}张".format(len(card_name_list)))

        # 先展开 战斗方案中 带卡的 标识名称 为 精确名称 包含.png后缀
        # 一个标识名称 应对多个精准名
        all_cards_precise_names = []
        for card_name in card_name_list:
            precise_names = self._card_name_to_tar_list(card_name=card_name)
            all_cards_precise_names.append(precise_names)

        def add_quest_card():
            """
            再展开 任务卡 查看任务卡是否已经存在于卡组中
            如果在 则将faa的任务卡变回None 并修改可用的精准名称 确保携带正确的变种卡片
            如果不在 则添加这张卡 并要求带卡必须成功
            这里的逻辑还有一些极端状态下的小问题 但应该不影响使用
            """

            # 使用的上级变量包括
            # all_cards_precise_names
            # can_failed_list

            if self.quest_card is None or self.quest_card == "None":
                return

            qc_precise_names = self._card_name_to_tar_list(card_name=copy.deepcopy(self.quest_card))
            qc_precise_in_plan_names = []
            for precise_names in all_cards_precise_names:
                for precise_name in precise_names:
                    if precise_name in qc_precise_names:
                        self.quest_card = None
                        qc_precise_in_plan_names.append(precise_name)

            for i, precise_names in enumerate(all_cards_precise_names):
                # 如果一张卡有精准名称属于任务卡的要求 那么 这张卡仅保留符合任务要求的精准名称
                if any(item in precise_names for item in qc_precise_in_plan_names):
                    all_cards_precise_names[i] = [pn for pn in precise_names if pn in qc_precise_in_plan_names]

            # 任务卡在战斗方案带卡中找到了~ 结束
            if qc_precise_in_plan_names:
                return

            # 根据战斗方案 插入到方案末位
            battle_plan = copy.deepcopy(self.battle_plan)
            card_ids = [card["card_id"] for card in battle_plan["cards"]]
            max_card_id = max(card_ids)

            # 插入卡片
            all_cards_precise_names.insert(max_card_id, qc_precise_names)
            card_name_list.insert(max_card_id, qc_precise_names[-1])
            # 不允许失败
            can_failed_list.insert(max_card_id, False)

        # 自动带卡版本的 任务卡添加
        add_quest_card()

        # 一轮识别 识别同一张卡的所有精准名称中 哪一个是实际存在且优先级最高的
        self.print_debug(text="[选取卡片] 将尝试查找以下卡片(组): {}, 是否允许失败: {}".format(
            all_cards_precise_names, can_failed_list))

        scan_card_name_list, scan_card_position_list = self._scan_card(
            all_cards_precise_names=all_cards_precise_names)

        self.print_debug(text="[选取卡片] 经识别将查找以下有效卡片: {}, 位置: {}".format(
            scan_card_name_list, scan_card_position_list))

        # 如果不允许失败 提前检查
        failed_card_list = []
        for index in range(len(can_failed_list)):
            if (scan_card_name_list[index] is None) and (not can_failed_list[index]):
                failed_card_list.append(card_name_list[index])
                self.print_debug(text="[缺失卡片] 卡片列表: {}, 缺失索引: {}".format(card_name_list, index))

        if failed_card_list:
            self.print_debug(text="[选取卡片] 结束, 结果: 因查找失败中断")
            SIGNAL.PRINT_TO_UI.emit(text=f"[{self.player}P] 缺失必要绑定卡片: {', '.join(failed_card_list)}")
            return False

        for index in range(len(scan_card_name_list)):
            card_name = scan_card_name_list[index]
            tar_position = scan_card_position_list[index]
            if card_name is None:
                continue
            # 理论上 经过了筛查 选卡失败基本上仅是因为 和其他卡片有冲突 这只会出现在非必要承载卡 可以忽视
            result = self._add_card(card_name=card_name, tar_position=tar_position)
            self.print_debug(text="[选取卡片] [{}]完成, 结果: {}".format(card_name, "成功" if result else "失败"))

        return True

    def _add_quest_card(self: "FAA"):

        quest_card = copy.deepcopy(self.quest_card)

        not_need_add = False
        not_need_add = not_need_add or quest_card == "None"
        not_need_add = not_need_add or quest_card is None

        if not_need_add:
            self.print_debug(text=f"[添加任务卡] 不需要,跳过")
            return
        else:
            self.print_debug(text=f"[添加任务卡] 开始, 目标:{quest_card}")

        # 调用选卡
        found_card = self._add_card(card_name=quest_card)

        if not found_card:
            # 如果没有找到 类属性 战斗方案 需要调整为None, 防止在战斗中使用对应卡片的动作序列出现
            self.quest_card = "None"

        self.print_debug(text="[添加任务卡] 完成, 结果:{}".format("成功" if found_card else "失败"))

    def _remove_ban_card(self: "FAA"):
        """寻找并移除需要ban的卡, 现已支持跨页ban"""

        handle = self.handle
        handle_360 = self.handle_360
        ban_card_list = copy.deepcopy(self.ban_card_list)
        print_debug = self.print_debug

        # 初始化 成功ban掉的卡片列表
        self.banned_card_index = None

        if ban_card_list:
            print_debug(text=f"[移除卡片] 开始, 目标:{ban_card_list}")
        else:
            print_debug(text=f"[移除卡片] 不需要,跳过")
            return

        # 将 card 解析为 可能的多重目标
        ban_card_targets_list = []
        for card_name in ban_card_list:
            targets = self._card_name_to_tar_list(card_name=card_name)
            ban_card_targets_list += targets

        # 去重
        new_list = []
        for i in ban_card_targets_list:
            if i not in new_list:
                new_list.append(i)
        ban_card_targets_list = new_list

        # 叠加图片
        ban_card_images = []
        for card in ban_card_targets_list:
            img_tar = overlay_images(
                img_background=RESOURCE_P["card"]["准备房间"][f"{card}.png"],
                img_overlay=RESOURCE_P["card"]["卡片-房间-绑定角标.png"],
                test_show=False)
            ban_card_images.append(img_tar)

        # 标志变量，记录哪些卡已经找到
        found_cards = []
        banned_card_index = []

        for page in [1, 2]:
            if page == 1:
                # 翻页回第一页 找1-10 格
                for _ in range(6):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=930, y=55)
                    time.sleep(0.1)

                for c_id in range(1, 11):
                    x_start = 390 + (c_id - 1) * 48
                    x_end = x_start + 40
                    y_start = 48
                    y_end = 98  # y_start+50
                    source_range = [x_start, y_start, x_end, y_end]

                    for index in range(len(ban_card_images)):
                        image = ban_card_images[index]
                        if index in found_cards:
                            continue

                        find = loop_match_p_in_w(
                            source_handle=handle,
                            source_root_handle=handle_360,
                            source_range=source_range,
                            template=image,
                            template_mask=RESOURCE_P["card"]["卡片-房间-掩模-绑定.png"],
                            match_tolerance=0.998,
                            match_interval=0.01,
                            match_failed_check=0.03,
                            after_sleep=0,
                            click=True)
                        if find:
                            found_cards.append(index)
                            banned_card_index.append(c_id)
                            time.sleep(0.1)

            if page == 2:
                # 翻页到第二页 找11-21 格
                for _ in range(6):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=930, y=85)
                    time.sleep(0.1)

                for c_id in range(1, 12):
                    x_start = 390 + (c_id - 1) * 48
                    x_end = x_start + 40
                    y_start = 48
                    y_end = 98  # y_start+50
                    source_range = [x_start, y_start, x_end, y_end]

                    for index in range(len(ban_card_images)):
                        image = ban_card_images[index]
                        if index in found_cards:
                            continue

                        find = loop_match_p_in_w(
                            source_handle=handle,
                            source_root_handle=handle_360,
                            source_range=source_range,
                            template=image,
                            template_mask=RESOURCE_P["card"]["卡片-房间-掩模-绑定.png"],
                            match_tolerance=0.998,
                            match_interval=0.01,
                            match_failed_check=0.03,
                            after_sleep=0,
                            click=True)
                        if find:
                            found_cards.append(index)
                            banned_card_index.append(10 + c_id)
                            time.sleep(0.1)

        if not banned_card_index:
            self.banned_card_index = None
        else:
            # 排序
            banned_card_index = sorted(banned_card_index)
            self.banned_card_index = banned_card_index

    def _check_stage_name(self: "FAA", text, t_type="id"):
        """
        :param text str 对应的值
        :param t_type str "id" or "name"
        根据检测出的关卡ID或关卡名，改变faa当前的stage_info
        """

        # 原有的关卡id
        old_stage_id = copy.deepcopy(self.stage_info["id"])

        # 特殊关卡列表占位符
        happy_holiday_list = []
        reward_list = []
        roaming_list = []

        special_stage = False

        if t_type == "id":

            self.stage_info = read_json_to_stage_info(
                stage_id=old_stage_id,
                stage_id_for_battle=text
            )
            special_stage = True
            stage_name = self.stage_info["name"]

        elif t_type == "name":

            stage_name = text
            special_stage = True

            match stage_name:
                case _ if "魔塔蛋糕" in stage_name:
                    level = stage_name.replace("魔塔蛋糕第", "").replace("层", "")
                    self.stage_info = read_json_to_stage_info(
                        stage_id=old_stage_id,
                        stage_id_for_battle=f"MT-1-{level}"
                    )

                case _ if "双人魔塔" in stage_name:
                    level = stage_name.replace("双人魔塔第", "").replace("层", "")
                    self.stage_info = read_json_to_stage_info(
                        stage_id=old_stage_id,
                        stage_id_for_battle=f"MT-2-{level}")

                case _ if "萌宠神殿" in stage_name:
                    level = stage_name.replace("萌宠神殿第", "").replace("层", "")
                    self.stage_info = read_json_to_stage_info(
                        stage_id=old_stage_id,
                        stage_id_for_battle=f"PT-0-{level}"
                    )

                case _ if stage_name in happy_holiday_list:
                    pass

                case _ if stage_name in reward_list:
                    pass

                case _ if stage_name in roaming_list:
                    pass

                case _:
                    # 查找失败
                    special_stage = False

        else:
            stage_name = "UnKnown"

        if special_stage:
            SIGNAL.PRINT_TO_UI.emit(f"检测到特殊关卡：{stage_name}，已为你启用对应关卡方案", 7)

    def _get_card_name_list_from_battle_plan(self: "FAA"):


        my_dict = {}
        mats = copy.deepcopy(self.stage_info["mat_card"])

        # 直接从cards 中获取 顺带保险排序一下
        for card in self.battle_plan["cards"]:
            my_dict[card["card_id"]] = card["name"]

        # 根据id 排序 并取其中的value为list
        sorted_list = list(dict(sorted(my_dict.items())).values())
        # 和 card_list 一一对应 顺序一致 代表这张卡是否允许被跳过
        can_failed_list = [False for _ in sorted_list]

        # 如果需要任意承载卡 第一张卡设定为 有效承载 置于末位
        if len(mats) >= 1:
            sorted_list += ["有效承载"]
            can_failed_list += [False]

        # 添加冰沙 复制类 置于末位 允许找不到
        sorted_list += ["冰激凌-2", "创造神", "幻幻鸡"]
        can_failed_list += [True, True, True]

        # 如果有效承载数量 >= 2 置于末位 允许找不到
        if len(mats) >= 2:
            for _ in range(len(mats) - 1):
                sorted_list += ["有效承载"]
                can_failed_list += [True]

        # 根据最大卡片数量限制 移除卡片
        if self.max_card_num is not None:
            self.print_debug(text=f"[自动带卡] 最大卡片数量限制为{self.max_card_num}张, 激活自动剔除, 并Ban掉咖啡粉")
            sorted_list = sorted_list[:self.max_card_num]
            can_failed_list = can_failed_list[:self.max_card_num]

            # 只要有禁用 就把咖啡粉顺手ban了.
            if not self.ban_card_list:
                self.ban_card_list = ["咖啡粉"]
            else:
                self.ban_card_list += ["咖啡粉"]

        return sorted_list, can_failed_list

    def check_create_room_success(self: "FAA"):
        """
        战前准备 确定进入房间
        :return: 0-正常结束 1-重启本次 2-跳过本次 3-跳过所有次数
        """

        # 循环查找开始按键
        self.print_debug(text="寻找开始或准备按钮")
        find = loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=[796, 413, 950, 485],
            template=RESOURCE_P["common"]["战斗"]["战斗前_开始按钮.png"],
            match_interval=1,
            match_failed_check=10,
            after_sleep=0.3,
            click=False)
        if not find:
            self.print_warning(text="创建房间后, 10s找不到[开始/准备]字样! 创建房间可能失败!")
            # 2-跳过本次 可能是由于: 服务器抽风无法创建房间 or 点击被吞 or 次数用尽
            return 2
        return 0

    def battle_preparation_change_deck(self: "FAA") -> int:
        """
        战前准备 修改卡组
        :return: 0-正常结束 1-重启本次 2-跳过本次 3-跳过所有次数
        """

        # 选择卡组
        self.print_debug(text=f"选择卡组编号-{self.deck}, 并开始加入新卡和ban卡")

        T_ACTION_QUEUE_TIMER.add_click_to_queue(
            handle=self.handle,
            x={1: 425, 2: 523, 3: 588, 4: 666, 5: 756, 6: 837}[self.deck],
            y=121)
        time.sleep(1.0)

        """寻找并卡片, 包括自动带卡 / 任务要求的带卡和禁卡"""

        if self.auto_carry_card:

            card_name_list, can_failed_list = self._get_card_name_list_from_battle_plan()
            success = self._add_cards(card_name_list=card_name_list, can_failed_list=can_failed_list)
            # 失败就会直接跳过本关卡全部场次！
            if not success:
                return 3

        else:
            # 任务需求的带卡
            # 在自动带卡中会自动处理该流程, 此处是手动带卡时对任务要求的处理
            self._add_quest_card()

        self._remove_ban_card()

        return 0

    def start_and_ensure_entry(self: "FAA"):
        """开始并确保进入成功"""

        # 复核 确定加速已经关掉了
        self.click_accelerate_btn(mode="stop")

        # 点击开始
        find = loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=[796, 413, 950, 485],
            template=RESOURCE_P["common"]["战斗"]["战斗前_开始按钮.png"],
            match_tolerance=0.95,
            match_interval=1,
            match_failed_check=10,
            after_sleep=0.25,
            click=True)
        if not find:
            self.print_warning(text="选择卡组后, 10s找不到[开始/准备]字样! 创建房间可能失败!")
            return 1  # 1-重启本次

        # 防止被 [没有带对策卡] or [背包已满] or [经验已刷满] 卡住
        for i in range(10):
            _, tar = match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[300, 180, 650, 420],
                template=RESOURCE_P["common"]["战斗"]["战斗前_系统提示.png"],
                match_tolerance=0.98)
            if not tar:
                break
            else:
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=427, y=353)
                time.sleep(0.25)

        # 刷新ui: 状态文本
        self.print_debug(text="查找火苗标识物, 等待进入战斗, 限时30s")

        # 循环查找火苗图标 找到战斗开始
        find = loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=[110, 0, 220, 100],
            template=RESOURCE_P["common"]["战斗"]["战斗中_火苗能量.png"],
            match_interval=0.05,
            match_failed_check=30,
            after_sleep=0.01,
            click=False)

        # 刷新ui: 状态文本
        if find:
            self.print_debug(text="找到火苗标识物, 战斗进行中...")
            return 0  # 0-一切顺利
        else:
            self.print_warning(text="未能找到火苗标识物, 进入战斗失败, 可能是次数不足或服务器卡顿")
            return 2  # 2-跳过本次

    def accelerate(self: "FAA"):
        """加速游戏!!!"""
        # duration is ms
        duration = EXTRA.ACCELERATE_START_UP_VALUE
        if duration > 0:
            self.click_accelerate_btn(mode="normal")
            time.sleep(duration / 1000)
            self.click_accelerate_btn(mode="normal")
            # 检查已经关闭加速
            self.click_accelerate_btn(mode="stop")

        return 0  # 0-一切顺利

    """初始化战斗方案部分"""

    # 在FAA中实现 需要修改FAA的类属性

    """战斗结束战利品的领取和捕获图片并识别部分"""

    def action_and_capture_loots(self: "FAA"):
        """
        :return: 捕获的战利品dict
        """

        handle = self.handle
        handle_360 = self.handle_360

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

    def capture_and_match_loots(self: "FAA") -> list:
        """
        :return: 捕获的战利品dict
        """

        handle = self.handle
        handle_360 = self.handle_360
        print_info = self.print_info
        player = self.player
        stage_info = self.stage_info

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
                stage_info["id"],  # 注意 此处一定要使用内部一定正确的id! b_id可能是用户随笔输入的
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
            print_info(text="[捕获战利品] 处在战利品UI 战利品已 捕获/识别".format(drop_list))

            return drop_list

        else:
            print_info(text="[捕获战利品] 未在战利品UI 可能由于延迟未能捕获战利品, 继续流程")

            return []

    def capture_and_match_treasure_chests(self: "FAA") -> list:

        handle = self.handle
        handle_360 = self.handle_360
        stage_info = self.stage_info
        player = self.player
        is_main = self.is_main
        is_group = self.is_group
        print_info = self.print_info
        print_warning = self.print_warning

        if EXTRA.ACCELERATE_SETTLEMENT_VALUE:
            print_info(text="[翻宝箱UI] 开始加速...")
            self.click_accelerate_btn(mode="normal")

        # 休息一会再识图 如果有加速, 少休息一会
        time.sleep(7 / (EXTRA.ACCELERATE_SETTLEMENT_VALUE if EXTRA.ACCELERATE_SETTLEMENT_VALUE != 0 else 1))

        find = loop_match_p_in_w(
            source_handle=handle,
            source_root_handle=handle_360,
            source_range=[400, 35, 550, 75],
            template=RESOURCE_P["common"]["战斗"]["战斗后_4_翻宝箱.png"],
            match_interval=0.1,
            match_failed_check=15,
            after_sleep=1,
            click=False
        )
        if not find:
            print_warning(text="[翻宝箱UI] 10s未能捕获正确标志, 出问题了!")
            return []

        print_info(text="[翻宝箱UI] 捕获到正确标志, 翻牌并退出...")

        if EXTRA.ACCELERATE_SETTLEMENT_VALUE:
            print_info(text="[翻宝箱UI] 停止加速...")
            self.click_accelerate_btn(mode="normal")
            # 检查已经关闭加速
            self.click_accelerate_btn(mode="stop")

        # 翻牌 1+2 bug法
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=550, y=265)
        time.sleep(0.1)
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=708, y=265)
        time.sleep(1.0)

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
            image=img,
            mode="chests",
            test_print=True)
        print_info(text="[翻宝箱UI] 宝箱已 捕获/识别/保存".format(drop_list))

        # 组队2P慢点结束翻牌 保证双人魔塔后自己是房主
        if is_group and is_main:
            time.sleep(1.0)

        # 开始洗牌
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=708, y=502)
        time.sleep(0.25)
        # 结束翻牌
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=708, y=502)
        time.sleep(1.0)

        return drop_list

    def perform_action_capture_match_for_loots_and_chests(self: "FAA"):
        """
        战斗结束后, 完成下述流程: 潜在的任务完成黑屏-> 战利品 -> 战斗结算 -> 翻宝箱 -> 回到房间/魔塔会回到其他界面
        已模块化到外部实现
        :return:
        输出1 int, 状态码, 0-正常结束 1-重启本次 2-跳过本次,
        输出2 None或者dict, 战利品识别结果 {"loots": [], "chests": []}
        """

        print_debug = self.print_debug
        screen_check_server_boom = self.screen_check_server_boom
        print_warning = self.print_warning

        print_debug(text="识别到多种战斗结束标志之一, 进行收尾工作")

        # 战利品部分, 会先检测是否在对应界面
        loots_list = self.capture_and_match_loots()

        # 翻宝箱部分, 会先检测是否在对应界面 如果不在则会进行加速
        chests_list = self.capture_and_match_treasure_chests()

        # 重整化 loots_list 和 chests_list 为识别到的物品的有序排列
        result_loot = {"loots": loots_list, "chests": chests_list}

        if screen_check_server_boom():
            print_warning(text="检测到 断开连接 or 登录超时 or Flash爆炸, 炸服了")
            return 1, None  # 1-重启本次

        else:
            return 0, result_loot

    """补充一个用于确保正确完成了战斗的Check点"""

    def battle_a_round_warp_up(self: "FAA"):

        """
        房间内或其他地方 战斗结束
        :return: 0-正常结束 1-重启本次 2-跳过本次
        """

        handle = self.handle
        handle_360 = self.handle_360
        print_debug = self.print_debug
        print_error = self.print_error

        print_debug(text="[结束校验] 尝试捕获正确标志, 以完成战斗流程. 标志包括: 开始/准备/魔塔蛋糕UI/巅峰对决UI")
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
                },
                {
                    "source_range": [0, 0, 260, 70],
                    "template": RESOURCE_P["common"]["巅峰对决_ui.png"],
                    "match_tolerance": 0.99
                }
            ],
            return_mode="or",
            match_failed_check=10,
            match_interval=0.2)
        if find:
            print_debug(text="[结束校验] 成功捕获任意标志, 完成战斗流程.")
            return 0  # 0-正常结束
        else:
            print_error(text="[结束校验] 10s没能捕获任意标志, 出现意外错误, 直接跳过本次")
            return 2  # 2-跳过本次


if __name__ == '__main__':
    def test_scan_card_one():
        """
        原始方法  15.05 = 1000次 15ms/次
        优化过快了50倍方法！ 28.30 = 1000次 28ms/次
        """
        target = "10周年烟花-0"
        img_tar = overlay_images(
            img_background=RESOURCE_P["card"]["准备房间"][f"{target}.png"],
            img_overlay=RESOURCE_P["card"]["卡片-房间-绑定角标.png"],
            test_show=False)

        channel = "锑食"
        handle = faa_get_handle(channel=channel, mode="flash")
        handle_browser = faa_get_handle(channel=channel, mode="browser")
        handle_360 = faa_get_handle(channel=channel, mode="360")

        start_time = time.time()

        for i in range(1000):
            img = capture_image_png(
                handle=handle,
                raw_range=[0, 0, 950, 600],
                root_handle=handle_360)
            img = crop_and_concat_columns(img=img)
            _, result = match_p_in_w(
                source_img=img,
                template=img_tar,
                mask=RESOURCE_P["card"]["卡片-房间-掩模-绑定.png"],
                match_tolerance=0.998,
            )

        used_time = time.time() - start_time
        print("used_time: ", used_time)


    test_scan_card_one()
