import os
import time

import numpy as np

from function.common.bg_img_screenshot import capture_image_png
from function.core_battle.get_position_in_battle import get_position_card_cell_in_battle
from function.globals.extra import EXTRA_GLOBALS
from function.globals.get_paths import PATHS
from function.globals.init_resources import RESOURCE_P
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER

# 在文件的开始位置获取位置坐标字典，深渊写的太低内聚了，我不想再套娃好几层传参了
position_dict = get_position_card_cell_in_battle()


def compare_pixels(img_source, img_template, mode="top"):
    """
    :param mode: 模式, 检测图片的哪些部分 "top" "bottom" "all"
    :param img_source: 目标图像 三维numpy数组 不能包含Alpha
    :param img_template: 模板图像 三维numpy数组 不能包含Alpha

    为抵消游戏蒙版色，导致的差距，用于对比识别目标像素和标准像素的函数, 只要上半和下半均有一个像素颜色正确就视为True
    上半: 0-35 共计36像素 下半: 36-84 共计49像素
    正确的标准:
    对应位置的两个像素 RGB三通道 的 颜色差的绝对值 之和 小于15
    需要注意 颜色数组是int8类型, 所以需要转成int32类型以做减法
    """

    # 将图片的数字转化为int32 而非int8 防止做减法溢出
    img_source = img_source.astype(np.int32)

    # 将图片的数字转化为int32 而非int8 防止做减法溢出
    img_template = img_template.astype(np.int32)

    return_bool = True
    if mode in ["top", "all"]:
        return_bool = return_bool and check_pixel_similarity(img_source, img_template, 0, 36)
    if mode in ["bottom", "all"]:
        return_bool = return_bool and check_pixel_similarity(img_source, img_template, 36, 85)

    return return_bool


def check_pixel_similarity(img_source, img_template, start, end, threshold=16):
    """
    检查在指定水平区域内，两幅高度仅1的图像是否有至少一个像素点的差异在阈值以内。
    """
    for x in range(start, end):
        if np.sum(abs(img_source[0, x] - img_template[0, x])) <= threshold:
            return True
    return False


class Card:

    def __init__(self, priority, faa):
        # 直接塞进来一个faa的实例地址, 直接从该实例中拉取方法和属性作为参数~
        self.faa = faa
        # 优先级 index
        self.priority = priority

        """直接从FAA类读取的属性"""
        self.handle = self.faa.handle
        self.need_key = self.faa.need_key
        self.is_auto_battle = self.faa.is_auto_battle
        self.faa_battle = self.faa.faa_battle
        self.player = self.faa.player

        """从 FAA类 的 battle_plan_parsed 中读取的属性"""
        # 根据优先级（也是在战斗方案中的index）直接读取faa
        self.name = self.faa.battle_plan_parsed["card"][priority]["name"]
        self.id = self.faa.battle_plan_parsed["card"][priority]["id"]
        self.location = self.faa.battle_plan_parsed["card"][priority]["location"]
        self.ergodic = self.faa.battle_plan_parsed["card"][priority]["ergodic"]
        self.queue = self.faa.battle_plan_parsed["card"][priority]["queue"]
        # 坐标 [x,y]
        self.location_from = self.faa.battle_plan_parsed["card"][priority]["location_from"]
        # dict {"1-1": [x,y],....}
        self.location_to = self.faa.battle_plan_parsed["card"][priority]["location_to"]
        # 坤优先级
        self.kun = self.faa.battle_plan_parsed["card"][priority]["kun"]
        # 卡坤的实例
        self.card_kun = None

        """用于完成放卡的额外类属性"""
        # 放卡间隔
        self.click_sleep = self.faa_battle.click_sleep
        # 状态 冷却完成 默认已完成
        self.status_cd = False
        # 状态 可用
        self.status_usable = False
        # 状态 被ban时间 当放卡，但已完成所有指定位置的放卡导致放卡后立刻检测到冷却完成，则进入该ban状态8s
        self.status_ban = 0
        # 是否是当前角色的坤目标
        self.is_kun_target = False
        # 判定自身是不是极寒冰沙
        self.is_smoothie = self.name in ["极寒冰沙", "冰沙"]
        # 不进入放满自ban的 白名单
        self.ban_white_list = ["极寒冰沙", "冰沙"]
        # 是否可以放卡（主要是瓜皮类）
        self.can_use = True

    def use_card(self):

        # 未启动自动战斗
        if not self.is_auto_battle:
            return

        # 自身是冰沙但不符合使用条件
        if self.is_smoothie:
            if not self.faa_battle.fire_elemental_1000:
                return
            if EXTRA_GLOBALS.smoothie_lock_time != 0:
                return
            EXTRA_GLOBALS.smoothie_lock_time = 7

        # 线程放瓜皮时不巧撞上了正在计算炸弹类或者计算完成后炸弹需要该瓜皮
        if not self.can_use:
            return

        # 战斗放卡锁，用于防止与特殊放卡放置冲突，点击队列不连贯
        with self.faa.battle_lock:

            # 点击 选中卡片
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=self.handle,
                x=self.location_from[0],
                y=self.location_from[1])

            if self.ergodic:
                # 遍历模式: True 遍历该卡每一个可以放的位置
                my_to_list = range(len(self.location))
            else:
                # 遍历模式: False 只放第一张, 为保证放下去, 同一个位置点两次
                my_to_list = [0, 0]

            # 初始化 j 为 0
            j = 0

            for j in my_to_list:
                # 点击 放下卡片
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=self.location_to[j][0],
                    y=self.location_to[j][1])

            # 放卡后点一下空白
            T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=200, y=350)
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=200, y=350)

            # 天知又双叒叕把时间sleep操作改成了聚合的 这是否会导致问题呢... 这会需要进一步测试
            time.sleep(self.click_sleep * (j + 3))

            # 如果启动队列模式放卡参数, 使用一次后, 第一个目标位置移动到末位
            if self.queue:
                self.location.append(self.location[0])
                self.location.remove(self.location[0])
                self.location_to.append(self.location_to[0])
                self.location_to.remove(self.location_to[0])

            # 额外时延
            time.sleep(0.2)

            # 如果放卡后还可用,自ban 若干s
            # 判断可用 如果不知道其还可用。会导致不自ban，导致无意义点击出现，后果更小。1轮扫描后纠正。
            # 判断冷却 如果不知道其进入了冷却。会导致错误的额外的自ban，导致放卡逻辑错乱。ban描述后纠正。
            self.fresh_status()

            if self.status_usable and (self.name not in self.ban_white_list):
                # 放置失败 说明放满了 如果不在白名单 就自ban
                self.status_ban = 10
            else:
                # and是短路计算，左边算过不满足右边就不会算，所以如果一个卡是坤标，那坤实例一定不为None
                # 放置成功 如果是坤目标, 复制自身放卡的逻辑,并且坤不在征用计算中或者计算完没有使用坤
                if self.is_kun_target and not self.card_kun.is_using:

                    # 点击 选中卡片 但坤
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(
                        handle=self.handle,
                        x=self.faa.kun_position["location_from"][0],
                        y=self.faa.kun_position["location_from"][1])
                    time.sleep(self.click_sleep)

                    if self.ergodic:
                        # 遍历模式: True 遍历该卡每一个可以放的位置
                        my_to_list = range(len(self.location))
                    else:
                        # 遍历模式: False 只放第一张, 为保证放下去, 同一个位置点两次
                        my_to_list = [0, 0]

                    for j in my_to_list:
                        # 点击 放下卡片
                        T_ACTION_QUEUE_TIMER.add_click_to_queue(
                            handle=self.handle,
                            x=self.location_to[j][0],
                            y=self.location_to[j][1])
                        time.sleep(self.click_sleep)

                    # 放卡后点一下空白
                    T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=200, y=350)
                    time.sleep(self.click_sleep)
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=200, y=350)
                    time.sleep(self.click_sleep)

                    # 如果启动队列模式放卡参数, 使用一次后, 第一个目标位置移动到末位
                    if self.queue:
                        self.location.append(self.location[0])
                        self.location.remove(self.location[0])
                        self.location_to.append(self.location_to[0])
                        self.location_to.remove(self.location_to[0])

                    # 额外时延
                    time.sleep(0.1)

    def fresh_status(self):
        """判断颜色来更改自身冷却和可用属性"""
        img = capture_image_png(
            handle=self.handle,
            raw_range=[
                self.location_from[0] - 45,
                self.location_from[1] - 64,
                self.location_from[0] + 8,
                self.location_from[1] + 6]
        )

        # 注意 y x bgr 和 rgb是翻过来的！
        # 将三维数组转换为二维数组
        pixels_top_left = np.squeeze(img[0:1, 2:20, :3])  # 18个像素
        pixels_top_right = np.squeeze(img[0:1, 33:51, :3])  # 18个像素
        pixels_bottom = np.squeeze(img[69:70, 2:51, :3])  # 49个像素

        pixels_all = [[]]
        for axis_0 in [pixels_top_left, pixels_top_right, pixels_bottom]:
            for pixel in axis_0:
                pixels_all[0].append(pixel)
        pixels_all = np.array(pixels_all)

        self.status_usable = (
                compare_pixels(
                    img_source=pixels_all,
                    img_template=RESOURCE_P["card"]["状态判定"]["可用状态_0.png"][:, :, :3],
                    mode='top') or
                compare_pixels(
                    img_source=pixels_all,
                    img_template=RESOURCE_P["card"]["状态判定"]["可用状态_1.png"][:, :, :3],
                    mode='top') or
                compare_pixels(
                    img_source=pixels_all,
                    img_template=RESOURCE_P["card"]["状态判定"]["可用状态_2.png"][:, :, :3],
                    mode='top') or
                compare_pixels(
                    img_source=pixels_all,
                    img_template=RESOURCE_P["card"]["状态判定"]["可用状态_3.png"][:, :, :3],
                    mode='top')
        )

        self.status_cd = (
                compare_pixels(
                    img_source=pixels_all,
                    img_template=RESOURCE_P["card"]["状态判定"]["冷却状态_0.png"][:, :, :3],
                    mode='top') or
                compare_pixels(
                    img_source=pixels_all,
                    img_template=RESOURCE_P["card"]["状态判定"]["冷却状态_1.png"][:, :, :3],
                    mode='top') or
                compare_pixels(
                    img_source=pixels_all,
                    img_template=RESOURCE_P["card"]["状态判定"]["冷却状态_2.png"][:, :, :3],
                    mode='top') or
                compare_pixels(
                    img_source=pixels_all,
                    img_template=RESOURCE_P["card"]["状态判定"]["冷却状态_3.png"][:, :, :3],
                    mode='top')
        )

    def destroy(self):
        self.faa = None
        self.priority = None
        self.card_kun = None


class CardKun:
    def __init__(self, faa):
        # 直接塞进来一个faa的实例地址, 直接从该实例中拉取方法和属性作为参数~
        self.faa = faa

        """直接从FAA类读取的属性"""
        self.handle = self.faa.handle

        # 坐标 [x,y]
        self.location_from = self.faa.kun_position["location_from"]

        """用于完成放卡的额外类属性"""
        # 状态 可用
        self.status_usable = False
        # 是否被征用计算
        self.is_using = False

    def fresh_status(self):
        """判断颜色来更改自身冷却和可用属性"""
        img = capture_image_png(
            handle=self.handle,
            raw_range=[
                self.location_from[0] - 45,
                self.location_from[1] - 64,
                self.location_from[0] + 8,
                self.location_from[1] + 6]
        )

        # 注意 y x bgr 和 rgb是翻过来的！
        # 将三维数组转换为二维数组
        pixels_top_left = np.squeeze(img[0:1, 2:20, :3])  # 18个像素
        pixels_top_right = np.squeeze(img[0:1, 33:51, :3])  # 18个像素
        pixels_bottom = np.squeeze(img[69:70, 2:51, :3])  # 49个像素

        pixels_all = [[]]
        for axis_0 in [pixels_top_left, pixels_top_right, pixels_bottom]:
            for pixel in axis_0:
                pixels_all[0].append(pixel)
        pixels_all = np.array(pixels_all)

        self.status_usable = (compare_pixels(pixels_all, RESOURCE_P["card"]["状态判定"]["可用状态_0.png"][:, :, :3]) or
                              compare_pixels(pixels_all, RESOURCE_P["card"]["状态判定"]["可用状态_2.png"][:, :, :3]))

    def destroy(self):
        self.faa = None


class SpecialCard(Card):
    def __init__(self, energy, card_type, rows=None, cols=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.energy = energy  # 特殊卡的初始能量值
        # 是否需要咖啡粉唤醒 算了不想写相关逻辑了，等有缘人补充吧
        self.need_coffee = self.name in ["冰桶炸弹", "开水壶炸弹"]
        self.card_type = card_type
        self.need_shovel = self.card_type == 12 or self.card_type == 14  # 要秒铲的有草扇跟护罩炸弹
        self.rows = rows
        self.cols = cols

    def use_card(self, pos):

        if not self.is_auto_battle:
            return
        if self.is_smoothie:
            if not self.faa_battle.fire_elemental_1000:
                return
            if EXTRA_GLOBALS.smoothie_lock_time != 0:
                return
            EXTRA_GLOBALS.smoothie_lock_time = 7

        # 根据玩家上互斥锁，保证放卡点击序列不会乱掉（因为多次点击还多线程操作很容易出事）
        with self.faa.battle_lock:
            # 无默认坐标即为冰桶类或草扇
            if pos is None:

                # 铲子的调用
                T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=self.faa.handle, key="1")
                time.sleep(self.click_sleep / 2)  # 必须的间隔

                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.faa.handle,
                    x=self.location_to[0][0],
                    y=self.location_to[0][1])
                time.sleep(0.5)

                # 加一个垫子的判断 点位要放承载卡
                if self.location[0] in self.faa.battle_plan_parsed["mat"]:
                    for mat in self.faa.mat_card_positions:
                        T_ACTION_QUEUE_TIMER.add_click_to_queue(
                            handle=self.handle,
                            x=mat["location_from"][0],
                            y=mat["location_from"][1])
                        # 点击 放下卡片
                        T_ACTION_QUEUE_TIMER.add_click_to_queue(
                            handle=self.handle,
                            x=self.location_to[0][0],
                            y=self.location_to[0][1])

                # 点击 选中卡片
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=self.location_from[0],
                    y=self.location_from[1])

                # 点击 放下卡片
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=self.location_to[0][0],
                    y=self.location_to[0][1])

                # 放卡后点一下空白
                T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=200, y=350)
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=200, y=350)
                if self.need_shovel:  # 是否要秒铲
                    T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=self.faa.handle, key="1")
                    time.sleep(self.click_sleep / 2)  # 必须的间隔
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(
                        handle=self.faa.handle,
                        x=self.location_to[0][0],
                        y=self.location_to[0][1])
                    time.sleep(self.click_sleep)
                # 天知又双叒叕把时间sleep操作改成了聚合的 这是否会导致问题呢... 这会需要进一步测试
                # time.sleep(self.click_sleep * 4)
                time.sleep(0.2)

            # 有默认坐标传入，意味着是炸弹类卡片
            else:
                # 铲子的调用
                T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=self.faa.handle, key="1")
                time.sleep(self.click_sleep / 2)  # 必须的间隔

                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.faa.handle,
                    x=position_dict[f"{pos[0]}-{pos[1]}"][0],
                    y=position_dict[f"{pos[0]}-{pos[1]}"][1])
                time.sleep(0.5)

                # 加一个垫子的判断
                if f"{pos[0]}-{pos[1]}" in self.faa.battle_plan_parsed["mat"]:  # 点位要放垫子
                    for mat in self.faa.mat_card_positions:

                        T_ACTION_QUEUE_TIMER.add_click_to_queue(
                            handle=self.handle,
                            x=mat["location_from"][0],
                            y=mat["location_from"][1])
                        T_ACTION_QUEUE_TIMER.add_click_to_queue(
                            handle=self.faa.handle,
                            x=position_dict[f"{pos[0]}-{pos[1]}"][0],
                            y=position_dict[f"{pos[0]}-{pos[1]}"][1])

                # 点击 选中卡片
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=self.location_from[0],
                    y=self.location_from[1])

                # 点击 放下卡片
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.faa.handle,
                    x=position_dict[f"{pos[0]}-{pos[1]}"][0],
                    y=position_dict[f"{pos[0]}-{pos[1]}"][1])

                # 放卡后点一下空白
                T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=200, y=350)
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=200, y=350)
                if self.need_shovel:  # 是否要秒铲

                    T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=self.faa.handle, key="1")
                    time.sleep(self.click_sleep / 2)  # 必须的间隔

                    T_ACTION_QUEUE_TIMER.add_click_to_queue(
                        handle=self.faa.handle,
                        x=position_dict[f"{pos[0]}-{pos[1]}"][0],
                        y=position_dict[f"{pos[0]}-{pos[1]}"][1])
                    time.sleep(self.click_sleep)

                # 天知又双叒叕把时间sleep操作改成了聚合的 这是否会导致问题呢... 这会需要进一步测试
                # time.sleep(self.click_sleep * 4)
                time.sleep(0.2)


def is_special_card(card_name):
    """判断是否为特殊卡，并返回匹配文件所在子目录的名称"""
    base_path = PATHS["picture"]["card"] + "\\特殊对策卡"
    card_name = os.path.splitext(card_name)[0]  # 移除传入名字的扩展名

    # 遍历目录及其子目录
    for root, dirs, files in os.walk(base_path):
        for file in files:
            # 解析文件名并移除扩展名
            base_name = os.path.splitext(file)[0]
            energy = None
            rows = None
            cols = None
            if '_' in base_name:
                parts = base_name.split('_')
                base_name = parts[0]
                card_type = parts[1]
                if len(parts) > 2:
                    energy = int(parts[2])
                if len(parts) > 3:
                    cols = int(parts[3])
                if len(parts) > 4:  # 目前只有大十字
                    rows = int(parts[4])

            # 检查是否匹配
            if base_name == card_name:
                # 计算子目录的名称
                subdir_name = os.path.relpath(root, base_path)
                return {
                    "found": True,
                    "subdir_name": subdir_name,
                    "energy": energy,
                    "card_type": int(card_type),
                    "rows": rows,
                    "cols": cols}
                # 返回匹配状态和匹配文件所在子目录的名称

    # 如果没有找到匹配的文件，返回匹配状态为False
    return {"found": False}

# # 示例使用
# card_name = "电音镭射喵"
# result = is_special_card(card_name)
#
# if result["found"]:
#     print(f"{card_name} 是特殊卡，位于子目录：{result['subdir_name']},耗能为{result['energy']},类型为{result['card_type']}")
# else:
#     print(f"{card_name} 不是特殊卡，未找到匹配文件。")
