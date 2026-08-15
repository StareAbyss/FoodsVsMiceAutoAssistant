import copy
import os
import re
import time
from typing import TYPE_CHECKING

import cv2
import numpy as np

from function.common.bg_img_match import loop_match_ps_in_w, loop_match_p_in_w, match_p_in_w
from function.common.bg_img_screenshot import capture_image_png
from function.common.image_processing.overlay_images import overlay_images
from function.core.analyzer_of_loot_logs import match_items_from_image_and_save
from function.core.faa.card_limit import (
    get_manual_card_slots_to_remove,
    get_required_manual_mat_slot,
    get_retained_plan_card_count,
)
from function.core.faa.battle_card_roles import (
    ROLE_CREATOR_GOD,
    ROLE_IKUN,
    ROLE_PLAN,
    ROLE_PRIMARY_MAT,
    ROLE_QUEST,
    ROLE_SECONDARY_MAT,
    ROLE_SMOOTHIE,
    ROLE_TIMER,
    apply_removed_slots,
    assign_successful_slot,
    attach_quest_role,
    make_card_requirement,
    retain_cards_by_role,
)
from function.core.faa.tweak_plan import (
    get_auto_card_target_names,
    get_auto_timer_target_names,
)
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
        if "-" in card_name:
            targets_1.append(card_name)  # 真：精确匹配
        else:
            for card in targets_0:
                # 精准匹配
                if "-" in card:
                    targets_1.append(card)
                # 模糊匹配 允许任意变种
                else:
                    resource_prefix = f"{card}-"
                    available_targets = []
                    for resource_name in RESOURCE_P["card"]["准备房间"]:
                        if not resource_name.startswith(resource_prefix) or not resource_name.endswith(".png"):
                            continue
                        precise_name = resource_name[:-4]
                        stage_text = precise_name.rsplit("-", 1)[-1]
                        if stage_text.isdigit():
                            available_targets.append((int(stage_text), precise_name))
                    targets_1 += [
                        precise_name
                        for _, precise_name in sorted(available_targets, reverse=True)
                    ]

        # 只携带被记录图片的卡
        targets_1 = [card for card in targets_1 if (card + ".png") in RESOURCE_P["card"]["准备房间"]]

        return targets_1

    def _scan_card(self: "FAA", required_cards_list):
        """
        战备选卡阶段 - 扫描所有卡片 找到符合标准的卡片中等级最高者
        :param required_cards_list: 二维
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

        # 初始化 以所有卡牌名称为键(去重)
        # 识别结果为值的字典
        for card in required_cards_list:
            for card_name in card['names']:
                if card_name not in match_img_result_dict.keys():
                    match_img_result_dict[card_name] = {"found": False, "position": 0}

        # 先处理叠加图片
        resource_p = {}
        for target in match_img_result_dict.keys():
            img_tar = overlay_images(
                img_background=RESOURCE_P["card"]["准备房间"][f"{target}.png"],
                img_overlay=RESOURCE_P["card"]["卡片-房间-绑定角标.png"],
                test_show=False)
            resource_p[target] = img_tar

        for i in range(21):

            # 设定保底时间, 图像刷新 ≠ 控件刷新
            time.sleep(0.1)

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
        for cards in required_cards_list:
            for card_name in cards['names']:
                # 成功查找
                if match_img_result_dict[card_name]["found"]:
                    # 添加结果
                    cards['result_name'] = card_name
                    cards['result_position'] = match_img_result_dict[card_name]["position"]
                    # 将所有名称相同(不含转职的 -X)的卡片都设置为 未找到 防止重复
                    card_name_without_id = card_name.split("-")[0]
                    for i in [0, 1, 2, 3]:
                        if match_img_result_dict.get(f"{card_name_without_id}-{i}"):
                            match_img_result_dict[f"{card_name_without_id}-{i}"]["found"] = False
                    break
            else:
                # 没有找到
                cards['result_name'] = None
                cards['result_position'] = None

        return required_cards_list

    def _add_card(self: "FAA", card_name, tar_page_num=None) -> bool:
        """
        战备选卡阶段 - 选中添加一张卡到卡组
        :param tar_page_num: 预扫描在第几次下拉找到了对应卡片, 如果有该值 直达
        :param card_name: 卡片标识名称 可以为 合法类名 模糊名(初始名称) 精准名(初始名称-转职数字)
        :return:
        """

        handle = self.handle
        handle_360 = self.handle_360

        if tar_page_num is None:
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
            time.sleep(0.5)

            for i in range(21):
                if tar_page_num is None or i >= tar_page_num:

                    # 等一下实际的游戏控件刷新，并在选卡点击前额外留出响应时间
                    time.sleep(0.4)

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
                        after_sleep=0.35,
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

    def _auto_carry_card_add_cards(self: "FAA"):
        """
        战备选卡阶段 - 按顺序选中若干张卡添加到卡组
        :return: 选卡是不是全部成功
        """

        # required_cards_list = list:[dict{"card_name": str, "can_failed": bool},...]
        # card_name str 为卡片的标识名称(Identifier Name) 可以为:
        # 合法类名(Valid Class Name)
        # 模糊名称(Fuzzy Name, 卡片不转职名称)
        # 精准名称(Precise Name, 模糊名-转职数字)
        # 最终都可以拓展为 list [str:精准名称,...]
        required_cards_list = self._auto_carry_card_get_card_name_list_from_battle_plan()
        self.print_debug(text="[选取卡片] 开始, 总计: {}张".format(len(required_cards_list)))

        # 先展开 战斗方案中 带卡的 str标识名称 为 list精确名称
        # 一个标识名称 应对多个精准名
        for card in required_cards_list:
            card["names"] = self._card_name_to_tar_list(card_name=card["name"])

        # 自动带卡版本的 任务卡添加
        self._auto_carry_card_add_quest_card(required_cards_list=required_cards_list)

        # 自动带卡只在生成清单时少带卡；它和下方手动卡组的按槽删除是两条独立操作路径。
        # 两者仅通过相同的保留优先级获得一致的最终卡组。
        required_cards_list = self._auto_carry_card_apply_limit(required_cards_list)

        # 一轮识别 识别同一张卡的所有精准名称中 哪一个是实际存在且优先级最高的
        self.print_debug(text="[选取卡片] 将尝试查找以下卡片(组)")
        for required_card in required_cards_list:
            self.print_debug(text=f"[选取卡片] {required_card}")

        required_cards_list = self._scan_card(required_cards_list=required_cards_list)

        self.print_debug(text="[选取卡片] 经识别，有效卡片如下")
        for required_card in required_cards_list:
            self.print_debug(text=f"[选取卡片] {required_card}")

        # 如果不允许失败 提前检查
        failed_card_list = []
        for required_card in required_cards_list:
            if (not required_card['can_failed']) and (required_card['result_name'] is None):
                failed_card_list.append(required_card['name'])
                self.print_debug(
                    text=f"[缺失卡片] 卡片名称: {required_card['name']}; 展开卡片列表: {required_card['names']}")
        if failed_card_list:
            self.print_debug(text="[选取卡片] 结束, 结果: 因查找失败中断")
            SIGNAL.PRINT_TO_UI.emit(text=f"[{self.player}P] 缺失必要绑定卡片: {', '.join(failed_card_list)}")
            return False

        successful_cards = []
        next_slot_id = 1
        for card in required_cards_list:

            # 压根就找不到这张卡 跳过跳过
            if card['result_name'] is None:
                continue

            # 理论上 经过了筛查 选卡失败基本上仅是因为 和其他卡片有冲突 这只会出现在非必要承载卡 可以忽视
            result = self._add_card(
                card_name=card['result_name'],
                tar_page_num=card['result_position'])

            self.print_debug(text="[选取卡片] 完成, 卡片初始名称:{}, 卡片最终名称:{}, 结果: {}".format(
                card['name'], card['result_name'], "成功" if result else "失败"))

            if result:
                assign_successful_slot(
                    card=card,
                    slot_id=next_slot_id,
                    precise_name=card["result_name"],
                )
                successful_cards.append(card)
                next_slot_id += 1
            elif not card["can_failed"]:
                SIGNAL.PRINT_TO_UI.emit(
                    text=f"[{self.player}P] 必要卡片“{card['name']}”点击添加失败，已中断本场战斗"
                )
                return False

        # 战备阶段到此才真正知道自动带卡的物理顺序。
        # 后续战斗解析只消费这份 plan_id / slot_id 映射；承载和辅助角色仍可由开场识图补充。
        self.battle_card_plan = successful_cards
        self.battle_card_plan_ready = True

        return True

    def _auto_carry_card_add_quest_card(self: "FAA", required_cards_list: list) -> None:
        """
        将任务卡合并到自动带卡清单。

        方案卡、承载或自动辅助卡只要可以解析为任务卡，就直接在同一实体卡上增加任务角色并收窄候选。
        任务角色会在限卡时提升该卡的保留优先级，因而不需要再制造一张同名任务卡。

        Args:
            required_cards_list: 已展开精准名称、尚未执行限卡筛选的自动带卡清单。
        """

        if self.quest_card in (None, "None"):
            return

        quest_card_name = copy.deepcopy(self.quest_card)
        quest_card_precise_names = self._card_name_to_tar_list(card_name=quest_card_name)
        quest_owner = attach_quest_role(
            cards=required_cards_list,
            quest_precise_names=quest_card_precise_names,
        )
        if quest_owner is not None:
            self.print_debug(
                text=(
                    f"[任务卡] “{quest_owner['name']}”承担任务卡“{quest_card_name}”，"
                    f"角色为{quest_owner['roles']}，候选限制为：{quest_owner['names']}"
                )
            )
            return

        # 任务卡需要手动添加

        # 自动带卡的物理顺序必须与玩家手动卡组约定一致：方案卡之后紧接任务卡预留位，
        # 然后才是承载和其他自动卡；这样任务卡的实际 ID 永远是“当前保留方案卡数量 + 1”。
        plan_card_count = sum(
            ROLE_PLAN in card.get("roles", [])
            for card in required_cards_list
        )
        quest_requirement = make_card_requirement(
            name=quest_card_name,
            roles=[ROLE_QUEST],
            plan_id=None,
            can_failed=False,
            source="quest",
        )
        quest_requirement["names"] = quest_card_precise_names
        required_cards_list.insert(
            plan_card_count,
            quest_requirement,
        )

    def _auto_carry_card_apply_limit(self: "FAA", required_cards_list: list) -> list:
        """
        在自动带卡清单中落实限卡优先级，但不改变最终物理排列。

        第一张承载是关卡地形前提，任务承担者是任务前提，之后才按方案 ID 从小到大保留。
        任务角色可以和任意已有角色共存，同一实体卡只占一个限卡名额；
        剩余名额再按原清单顺序留给其他自动附加卡。
        """
        if self.max_card_num is None:
            return required_cards_list

        result = retain_cards_by_role(
            cards=required_cards_list,
            max_card_num=self.max_card_num,
        )

        self.print_debug(
            text=(
                f"[自动带卡] 最大卡片数量限制为{self.max_card_num}张，"
                "已按必要承载、任务卡、方案卡顺序保留，并Ban掉咖啡粉"
            )
        )
        if not self.ban_card_list:
            self.ban_card_list = ["咖啡粉"]
        elif "咖啡粉" not in self.ban_card_list:
            self.ban_card_list += ["咖啡粉"]
        return result

    def _manual_carry_add_quest_card(self: "FAA") -> bool | None:
        """
        尝试把任务卡加入手动卡组预留空位。

        手动卡组的方案卡名称和实际卡片没有一一对应关系，因此无法在战备阶段判断任务卡是否已经存在。添加失败时不再抹掉任务要求，
        而是假定卡片可能因已在卡组中而呈灰色；FAA 会继续本场战斗，
        并在开场识图时尝试补全其真实槽位。

        Returns:
            ``True`` 表示成功加入；``False`` 表示按已在卡组中处理；没有任务卡要求时返回 ``None``。
        """

        quest_card = copy.deepcopy(self.quest_card)

        not_need_add = False
        not_need_add = not_need_add or quest_card == "None"
        not_need_add = not_need_add or quest_card is None

        if not_need_add:
            self.print_debug(text=f"[添加任务卡] 不需要,跳过")
            return None
        else:
            self.print_debug(text=f"[添加任务卡] 开始, 目标:{quest_card}")

        # 调用选卡
        found_card = self._add_card(card_name=quest_card)

        if not found_card:
            SIGNAL.PRINT_TO_UI.emit(
                text=(
                    f"[{self.player}P] 手动带卡未能从背包添加任务卡“{quest_card}”。"
                    "该卡可能已在当前卡组中而显示为灰色，FAA仍会尝试本场战斗；"
                    "若卡组实际没有该卡，本次任务可能无法完成。"
                ),
                color_level=2,
            )

        self.print_debug(text="[添加任务卡] 完成, 结果:{}".format("成功" if found_card else "失败"))
        return found_card

    def _manual_carry_remove_cards_for_card_num_limit(self: "FAA") -> None:
        """
        手动卡组限卡路径：按固定槽位从 21 向前移除所有非保留位置。

        手动卡组约定为“方案卡 + 任务卡空位 + 木盘子 + 麦芽糖 + 其他”。
        倒序点击可避免删卡导致后续卡片左移后破坏尚未处理的低位槽。
        该函数不参与自动带卡；自动带卡会在生成清单时直接少带对应卡片。
        """
        if self.max_card_num is None:
            return

        has_quest_card = self.quest_card not in (None, "None")
        slots_to_remove = get_manual_card_slots_to_remove(
            plan_card_count=len(self.battle_plan.get("cards", [])),
            max_card_num=self.max_card_num,
            stage_info=self.stage_info,
            has_quest_card=has_quest_card,
        )
        if not slots_to_remove:
            return

        # 卡组最左页固定显示 1..11，最右页固定显示 11..21；
        # 槽位 11 是两页重叠项。这里统一在最右页处理 11，回到最左页只处理 10..1。
        second_page_slots = [slot for slot in slots_to_remove if slot >= 11]
        first_page_slots = [slot for slot in slots_to_remove if slot <= 10]

        def remove_visible_slot(page_slot_id: int) -> None:
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=self.handle,
                x=410 + (page_slot_id - 1) * 48,
                y=73,
            )
            time.sleep(0.1)

        if second_page_slots:
            for _ in range(6):
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=930,
                    y=85,
                )
                time.sleep(0.1)
            for slot_id in second_page_slots:
                remove_visible_slot(slot_id - 10)

        if first_page_slots:
            for _ in range(6):
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=930,
                    y=55,
                )
                time.sleep(0.1)
            for slot_id in first_page_slots:
                remove_visible_slot(slot_id)

    def _build_manual_battle_card_plan(self: "FAA", quest_add_result: bool | None) -> None:
        """
        建立手动卡组的方案 ID、已知槽位和任务状态。

        手动卡组只保证方案 ID 与前部物理槽一一对应，名称可以完全不同。
        承载和辅助卡的位置保持未知，进入战斗后继续通过识图补全。
        任务卡成功加入时位于保留方案卡之后；添加失败时保留一个未知槽位的任务占位，供战斗开场扫描尝试绑定。

        Args:
            quest_add_result: ``_add_quest_card`` 的结果。
        """
        has_quest_requirement = self.quest_card not in (None, "None")
        retained_plan_count = get_retained_plan_card_count(
            plan_card_count=len(self.battle_plan.get("cards", [])),
            max_card_num=self.max_card_num,
            stage_info=self.stage_info,
            has_quest_card=has_quest_requirement,
        )

        cards = []
        for plan_card in sorted(
            self.battle_plan.get("cards", []),
            key=lambda item: item["card_id"],
        )[:retained_plan_count]:
            card = make_card_requirement(
                name=plan_card["name"],
                roles=[ROLE_PLAN],
                plan_id=plan_card["card_id"],
                can_failed=False,
                source="battle_plan",
            )
            # 手动卡组规范要求方案 ID 与开头的物理槽一一对应。
            card["slot_id"] = plan_card["card_id"]
            cards.append(card)

        if has_quest_requirement:
            quest_card = make_card_requirement(
                name=self.quest_card,
                roles=[ROLE_QUEST],
                plan_id=None,
                can_failed=quest_add_result is False,
                source="quest",
            )
            if quest_add_result:
                quest_card["slot_id"] = retained_plan_count + 1
            else:
                quest_card["assumed_existing"] = True
            cards.append(quest_card)

        self.battle_card_plan = cards
        self.battle_card_plan_ready = True
        self.manual_quest_card_assumed = quest_add_result is False

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

    def _change_stage_bid(self: "FAA", new_stage_id):
        """
        根据检测出的关卡ID或关卡名，改变faa当前的stage_info
        """

        # 原有的关卡id
        old_stage_id = copy.deepcopy(self.stage_info["id"])

        self.stage_info = read_json_to_stage_info(
            stage_id=old_stage_id,
            stage_id_for_battle=new_stage_id
        )

        stage_name = self.stage_info["name"]
        SIGNAL.PRINT_TO_UI.emit(f"检测到特殊关卡：{stage_name}，已为你启用对应关卡信息(铲卡/承载)", 7)

    def _get_stage_info_from_battle_name(self: "FAA", stage_name):

        # 原有的关卡id
        old_stage_id = copy.deepcopy(self.stage_info["id"])
        special_stage = True

        # 特殊关卡列表占位符
        happy_holiday_list = []
        reward_list = []
        roaming_list = []

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
                stage_name = "UnKnown"

        if special_stage:
            SIGNAL.PRINT_TO_UI.emit(f"检测到特殊关卡：{stage_name}，已为你启用对应关卡信息(铲卡/承载)", 7)

    def _auto_carry_card_get_card_name_list_from_battle_plan(self: "FAA"):
        """
        根据战斗方案和微调方案生成自动带卡清单。

        微调方案 v0.3 使用正向开关控制自动辅助卡片与承载卡功能；
        同一状态还会在战斗初始化阶段关闭对应的智能使用功能。

        最终物理顺序保持为：方案卡、独立任务卡、第一承载、其他辅助卡、第二张及后续承载。
        任务卡若由已有卡承担，就只给该实体卡追加角色，不会额外占据一个物理槽位。

        Returns:
            按卡片优先级排列的自动带卡要求列表。
        """
        target_mat_list, target_smoothie_list, target_kun_list = get_auto_card_target_names(
            stage_mat_card_names=self.stage_info["mat_card"],
            battle_plan_tweak=self.battle_plan_tweak,
            battle_plan=self.battle_plan,
            card_types=self.card_types,
        )

        required_cards_list = []
        # JSON 中的 card_id 只作为稳定的方案身份保存为 plan_id；
        # 真实卡槽要等自动带卡点击成功后，按实际加入顺序写入 slot_id。
        for card in sorted(
            self.battle_plan["cards"],
            key=lambda item: item["card_id"],
        ):
            required_cards_list.append(make_card_requirement(
                name=card["name"],
                roles=[ROLE_PLAN],
                plan_id=card["card_id"],
                can_failed=False,
                source="battle_plan",
            ))

        # 任务卡稍后由 _auto_carry_card_add_quest_card 插入此处；
        # 之后按用户的固定卡组约定加入承载，避免承载抢占方案卡或任务卡的 ID。
        if target_mat_list:
            primary_mat_name = "有效承载"
            if self.max_card_num is not None:
                # 限卡时自动带卡必须和手动固定卡组保留同一种标准承载。
                # 其他高优先级承载仍可在不限卡时使用；限卡时只有木盘子和麦芽糖参与固定槽选择。
                primary_mat_name = {
                    "wood": "木盘子",
                    "malt": "麦芽糖",
                }.get(get_required_manual_mat_slot(self.stage_info), "有效承载")
            required_cards_list.append(make_card_requirement(
                name=primary_mat_name,
                roles=[ROLE_PRIMARY_MAT],
                plan_id=None,
                can_failed=False,
                source="mat",
            ))

        # 一般辅助卡位于第一承载之后、后续承载之前。它们允许找不到；
        # 如果同时承担任务角色，任务解析会自动将 can_failed 提升为 False。
        if get_auto_timer_target_names(
            battle_plan_tweak=self.battle_plan_tweak,
            battle_plan=self.battle_plan,
            card_types=self.card_types,
        ):
            required_cards_list.append(
                make_card_requirement(
                    name="美味计时器",
                    roles=[ROLE_TIMER],
                    plan_id=None,
                    can_failed=True,
                    source="extra",
                )
            )
        if target_smoothie_list:
            required_cards_list.append(
                make_card_requirement(
                    name="冰激凌-2",
                    roles=[ROLE_SMOOTHIE],
                    plan_id=None,
                    can_failed=True,
                    source="extra",
                )
            )
        if "创造神" in target_kun_list:
            required_cards_list.append(
                make_card_requirement(
                    name="创造神",
                    roles=[ROLE_CREATOR_GOD],
                    plan_id=None,
                    can_failed=True,
                    source="extra",
                )
            )
        if "幻幻鸡" in target_kun_list:
            required_cards_list.append(
                make_card_requirement(
                    name="幻幻鸡",
                    roles=[ROLE_IKUN],
                    plan_id=None,
                    can_failed=True,
                    source="extra",
                )
            )

        # 后续承载仍使用“有效承载”候选和扫描去重来寻找不同实体卡；
        # 槽位到战斗开场后由图像识别复核，因此这里不推算具体承载名称。
        for _ in range(max(0, len(target_mat_list) - 1)):
            required_cards_list.append(
                make_card_requirement(
                    name="有效承载",
                    roles=[ROLE_SECONDARY_MAT],
                    plan_id=None,
                    can_failed=True,
                    source="extra",
                )
            )

        return required_cards_list

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

    def battle_preparation_change_deck(self: "FAA") -> bool:
        """
        战前准备 修改卡组
        :return: 是否成功找卡
        """

        # 选择卡组
        self.print_debug(text=f"选择卡组编号-{self.deck}, 并开始加入新卡和ban卡")

        T_ACTION_QUEUE_TIMER.add_click_to_queue(
            handle=self.handle,
            x={1: 425, 2: 523, 3: 588, 4: 666, 5: 756, 6: 837}[self.deck],
            y=121)
        time.sleep(1.0)

        """寻找卡片, 包括自动带卡 / 任务要求的带卡和禁卡"""

        # 自动带卡
        if self.auto_carry_card:
            if not self._auto_carry_card_add_cards():
                return False

        # 手动带卡
        else:
            # 任务需求的带卡
            # 在自动带卡中会自动处理该流程, 此处是手动带卡时对任务要求的处理
            quest_add_result = self._manual_carry_add_quest_card()

            # 手动带卡只按用户固定卡组的物理槽位执行倒序删除。
            # 不要复用自动带卡的清单生成与筛选流程。
            self._manual_carry_remove_cards_for_card_num_limit()
            self._build_manual_battle_card_plan(quest_add_result=quest_add_result)

        # 移除被禁用的卡牌
        self._remove_ban_card()

        # 根据遭到移除的卡片情报 重排卡片的槽位信息
        apply_removed_slots(cards=self.battle_card_plan, removed_slots=self.banned_card_index)
        return True

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
            accelerate_result = self.click_accelerate_btn(mode="normal")
            if not accelerate_result:
                return 0  # 0-一切顺利
            time.sleep(duration / 1000)
            self.click_accelerate_btn(mode="normal")
            # 检查已经关闭加速
            self.click_accelerate_btn(mode="stop")

        return 0  # 0-一切顺利

    """初始化战斗方案部分"""

    # 在FAA中实现
    # 需要修改FAA的类属性

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
            img_path = os.path.join(
                PATHS["logs"],
                "loots_image",
                "{}_{}P_{}.png".format(
                    stage_info["id"],  # 注意 此处一定要使用内部一定正确的id! b_id可能是用户随笔输入的
                    player,
                    time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime()))
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
        accelerate_true = False

        if EXTRA.ACCELERATE_SETTLEMENT_VALUE:
            print_info(text="[翻宝箱UI] 开始加速...")
            accelerate_true = self.click_accelerate_btn(mode="normal")

        # 休息一会再识图 如果加速成功, 少休息一会
        time.sleep(7 / EXTRA.ACCELERATE_SETTLEMENT_VALUE if accelerate_true else 7)

        find = loop_match_p_in_w(
            source_handle=handle,
            source_root_handle=handle_360,
            source_range=[400, 35, 550, 75],
            template=RESOURCE_P["common"]["战斗"]["战斗后_4_翻宝箱.png"],
            match_interval=0.05,
            match_failed_check=10,
            after_sleep=0.05,
            click=False
        )
        if not find:
            print_warning(text="[翻宝箱UI] 10s未能捕获正确标志, 出问题了!")
            return []

        if EXTRA.ACCELERATE_SETTLEMENT_VALUE:
            print_info(text="[翻宝箱UI] 捕获到正确标志, 停止加速...")
            self.click_accelerate_btn(mode="stop")
        else:
            print_info(text="[翻宝箱UI] 捕获到正确标志, 继续...")

        print_info(text=f"[翻宝箱UI] 即将翻牌, 翻牌数: {EXTRA.FLOP_TIMES}")

        # 翻牌 1+2 bug法
        click_positions = [
            {'x': 550, 'y': 265},
            {'x': 550 + 158, 'y': 265},
            {'x': 550 + 158 * 2, 'y': 265},
            {'x': 550, 'y': 265 + 200},
            {'x': 550 + 158, 'y': 265 + 200},
            {'x': 550 + 158 * 2, 'y': 265 + 200}
        ]
        for i in range(EXTRA.FLOP_TIMES):
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=click_positions[i]['x'], y=click_positions[i]['y'])
            time.sleep(0.2)
        time.sleep(1)
        print_info(text="[翻宝箱UI] 翻牌完成, 即将记录图像...")

        capture_ranges = [
            {
                'x1': 249,
                'y1': 89,
                'x2': 249 + 44,
                'y2': 89 + 44
            }, {
                'x1': 249 + 68,
                'y1': 89,
                'x2': 249 + 68 + 44,
                'y2': 89 + 44
            }, {
                'x1': 249 + 68 * 2,
                'y1': 89,
                'x2': 249 + 68 * 2 + 44,
                'y2': 89 + 44
            }, {
                'x1': 249,
                'y1': 89 + 54,
                'x2': 249 + 44,
                'y2': 89 + 54 + 44
            }, {
                'x1': 249 + 68,
                'y1': 89 + 54,
                'x2': 249 + 68 + 44,
                'y2': 89 + 54 + 44
            }, {
                'x1': 249 + 68 * 2,
                'y1': 89 + 54,
                'x2': 249 + 68 * 2 + 44,
                'y2': 89 + 54 + 44
            },
        ]
        chest_image = capture_image_png(handle=handle, root_handle=handle_360, raw_range=[0, 0, 950, 600])
        chest_images = []
        for capture_range in capture_ranges:
            chest_images.append(
                chest_image[capture_range['y1']:capture_range['y2'], capture_range['x1']:capture_range['x2']])
        chest_items_image = cv2.hconcat(chest_images)

        # 定义保存路径和文件名格式
        img_path = os.path.join(
            PATHS["logs"],
            "chests_image",
            "{}_{}P_{}.png".format(
                stage_info["id"],
                player,
                time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime()))
        )

        # 分析图片，获取战利品字典
        drop_list = match_items_from_image_and_save(
            img_save_path=img_path,
            image=chest_items_image,
            mode="chests",
            test_print=True)
        print_info(text="[翻宝箱UI] 宝箱已 捕获/识别/保存".format(drop_list))

        # 组队2P慢点结束翻牌 保证双人魔塔后自己是房主
        time.sleep(0.3)
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
