import os
import time

import cv2
import numpy as np

from function.common.bg_img_screenshot import capture_image_png
from function.globals import g_extra
from function.globals.g_resources import RESOURCE_P
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from function.globals.position_card_cell_in_battle import POSITION_CARD_CELL_IN_BATTLE
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER


def compare_pixels(img_source, img_template):
    """
    :param img_source: 目标图像 三维numpy数组 不能包含Alpha
    :param img_template: 模板图像 三维numpy数组 不能包含Alpha

    上半: 0-35 共计36像素 下半: 36-84 共计49像素
    正确的标准:
    对应位置的两个像素 RGB三通道 的 颜色差的绝对值 之和 小于15
    需要注意 颜色数组是int8类型, 所以需要转成int32类型以做减法
    """
    if img_source is None:
        return False

    if img_template is None:
        return False

    # 将图片的数字转化为int32 而非int8 防止做减法溢出
    img_source = img_source.astype(np.int32)

    # 将图片的数字转化为int32 而非int8 防止做减法溢出
    img_template = img_template.astype(np.int32)

    return check_pixel_similarity(img_source, img_template, 0, 36)


def check_pixel_similarity(img_source, img_template, start, end, threshold=16):
    """
    检查在指定水平区域内，两幅高度仅1的图像是否有80%像素点的差异在阈值以内.
    需要注意 颜色数组是int8类型, 所以需要转成int32类型以做减法
    """
    total_pixels = end - start
    required_pixels = int(total_pixels * 0.8)

    count = 0
    for x in range(start, end):
        if np.sum(abs(img_source[0, x] - img_template[0, x])) <= threshold:
            count += 1
            if count >= required_pixels:
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
        self.handle_360 = self.faa.handle_360
        self.need_key = self.faa.need_key
        self.is_auto_battle = self.faa.is_auto_battle
        self.faa_battle = self.faa.faa_battle
        self.player = self.faa.player

        """从 FAA类 的 battle_plan_parsed 中读取的属性"""
        # 根据优先级（也是在战斗方案中的index）直接读取faa
        self.name = self.faa.battle_plan_parsed["card"][priority]["name"]
        self.id = self.faa.battle_plan_parsed["card"][priority]["id"]

        self.ergodic = self.faa.battle_plan_parsed["card"][priority]["ergodic"]
        self.queue = self.faa.battle_plan_parsed["card"][priority]["queue"]

        # 卡片放置的位置 - 代号 list["1-1",...]
        self.location = self.faa.battle_plan_parsed["card"][priority]["location"]

        # 卡片放置的位置 - 坐标 list[[x,y],....]
        self.location_to = self.faa.battle_plan_parsed["card"][priority]["location_to"]

        # 卡片拿取的位置 - 坐标 list[x,y]
        self.location_from = self.faa.battle_plan_parsed["card"][priority]["location_from"]

        # 坤优先级
        self.kun = self.faa.battle_plan_parsed["card"][priority]["kun"]

        # 坤卡的实例
        self.card_kun = None

        """用于完成放卡的额外类属性"""
        # 该卡片不同状态下对应的状态图片
        self.state_images = {
            "冷却": None,  # 战斗需要
            "可用": None,  # 战斗需要
            "不可用": None,  # 遇到新图片则保存下来以便初始判断, 也用于判断是否遇到了新的状态图片
        }

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

    def choice_card(self):
        """
        取卡操作
        """
        T_ACTION_QUEUE_TIMER.add_click_to_queue(
            handle=self.handle,
            x=self.location_from[0] + 25,
            y=self.location_from[1] + 35)

    def put_card(self):
        """
        在取卡后, 放下一张卡并更改内部数组的全套操作
        """

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
        if self.queue and len(self.location) > 0 and len(self.location_to) > 0:
            if self.location:
                self.location.append(self.location[0])
                self.location.remove(self.location[0])
                self.location_to.append(self.location_to[0])
                self.location_to.remove(self.location_to[0])

    def get_card_current_img(self, game_image=None):
        """
        获取用于 判定 卡片状态 的图像
        :param game_image: 可选, 是否从已有的完成游戏图像中拆解, 不截图
        :return:
        """
        x1 = self.location_from[0]
        x2 = x1 + 53
        y1 = self.location_from[1]
        y2 = y1 + 70

        if game_image is None:
            img = capture_image_png(handle=self.handle, raw_range=[x1, y1, x2, y2], root_handle=self.handle_360)
        else:
            img = game_image[y1:y2, x1:x2]

        # img的格式[y1:y2,x1:x2,bgra] 注意不是 r g b α 而是 b g r α
        pixels_top_left = img[0:1, 2:20, :3]  # 18个像素图片 (1, 18, 3)
        pixels_top_right = img[0:1, 33:51, :3]  # 18个像素图片 (1, 18, 3)
        pixels_all = np.hstack((pixels_top_left, pixels_top_right))  # 36个像素图片 (1, 36, 3)

        return pixels_all

    def fresh_status(self, game_image=None):
        """
        判断游戏图像, 来确认卡片自身 冷却 和 可用 两项属性
        """

        current_img = self.get_card_current_img(game_image=game_image)

        self.status_usable = compare_pixels(
            img_source=current_img,
            img_template=self.state_images["可用"])

        self.status_cd = compare_pixels(
            img_source=current_img,
            img_template=self.state_images["冷却"]
        )

    def try_get_card_states_img(self):
        """
        检测目标状态图像是否已经获取
        :return: 0 获取失败 1 直接获取成功或已经获取过 2 靠试卡获取成功
        """
        if self.state_images["冷却"] is not None:
            # 状态已经获取好了 直接开溜
            return 1

        # 尝试直接从已有状态匹配
        current_img = self.get_card_current_img()
        for _, state_images_group in RESOURCE_P["card"]["状态判定"].items():
            for _, state_image in state_images_group.items():
                if np.array_equal(state_image, current_img):
                    self.state_images["冷却"] = state_images_group["冷却.png"]
                    self.state_images["可用"] = state_images_group["可用.png"]
                    if g_extra.GLOBAL_EXTRA.extra_log_battle:
                        CUS_LOGGER.info(f"[战斗执行器] [{self.player}P] [{self.name}] 成功从已保存状态获取")
                    return 1

        # 包含点击操作 上锁
        with self.faa.battle_lock:

            # 点击 选中卡片 移动到空白位置
            self.choice_card()
            time.sleep(0.1)
            T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=200, y=350)
            time.sleep(0.5)

            current_img_clicked = self.get_card_current_img()
            if np.array_equal(current_img, current_img_clicked):
                # 如果什么都没有改变, 意味着该颜色是 不可用 无法试色
                if g_extra.GLOBAL_EXTRA.extra_log_battle:
                    CUS_LOGGER.info(f"[战斗执行器] [{self.player}P] [{self.name}] 点击前后颜色相同, 试色失败")
                return 0

            # 发生了改变, 意味着旧的颜色是 可用 新的颜色是 不可用
            self.state_images["可用"] = current_img
            self.state_images["不可用"] = current_img_clicked

            # 放下这张卡
            self.put_card()
            time.sleep(0.5)

        # 放卡后, 获取到的第三种颜色必须不同于另外两种, 才记录为cd色, 否则可能由于冰沙冷却效果导致录入可用为cd色.
        current_img_after_put = self.get_card_current_img()

        if np.array_equal(current_img_after_put, current_img_clicked):
            if g_extra.GLOBAL_EXTRA.extra_log_battle:
                CUS_LOGGER.info(f"[战斗执行器] [{self.player}P] [{self.name}]  获取到的cd色和其他状态冲突, 试色失败")
            return 2

        if np.array_equal(current_img_after_put, current_img):
            if g_extra.GLOBAL_EXTRA.extra_log_battle:
                CUS_LOGGER.info(f"[战斗执行器] [{self.player}P] [{self.name}] 获取到的cd色和其他状态冲突, 试色失败")
            return 2

        self.state_images["冷却"] = current_img_after_put
        if g_extra.GLOBAL_EXTRA.extra_log_battle:
            CUS_LOGGER.info(f"[战斗执行器] [{self.player}P] [{self.name}] 试色成功")
        return 2

    def use_card(self):

        # 未启动自动战斗
        if not self.is_auto_battle:
            return

        # 自身是冰沙但不符合使用条件
        if self.is_smoothie:
            if not self.faa_battle.fire_elemental_1000:
                return
            if g_extra.GLOBAL_EXTRA.smoothie_lock_time > 0:
                return
            g_extra.GLOBAL_EXTRA.smoothie_lock_time = 7

        # 线程放瓜皮时不巧撞上了正在计算炸弹类或者计算完成后炸弹需要该瓜皮
        if not self.can_use:
            return

        # 输出
        # if g_extra.GLOBAL_EXTRA.extra_log_battle and self.faa.player == 1:
        #     CUS_LOGGER.debug(f"[战斗执行器] [{self.player}P] 使用卡片：{self.name}")

        # 战斗放卡锁，用于防止与特殊放卡放置冲突，点击队列不连贯
        with self.faa.battle_lock:

            # 如果不可用状态 放弃本次用卡
            if not self.status_usable:
                return

            # 点击 选中卡片
            self.choice_card()
            time.sleep(self.click_sleep)

            # 放卡
            self.put_card()
            time.sleep(0.1)
            self.fresh_status()  # 如果放卡后还可用,自ban 若干s

            if self.status_usable and (self.name not in self.ban_white_list):
                # 放满了 如果不在白名单 就自ban
                self.status_ban = 10
                # if self.player == 1:
                #     CUS_LOGGER.debug(f"[1P] {self.name} 因使用后仍可用进行了自ban")
                #     T_ACTION_QUEUE_TIMER.print_queue_statue()
                return

            # 放置成功 如果是坤目标, 复制自身放卡的逻辑
            if not self.is_kun_target:
                return

            # 坤-如果不可用状态 放弃本次用卡
            if not self.card_kun.status_usable:
                return

            # 坤-点击 选中卡片
            self.card_kun.choice_card()
            time.sleep(self.click_sleep)

            # 坤-放卡
            self.put_card()
            time.sleep(0.1)
            self.card_kun.fresh_status()

    def destroy(self):
        """中止运行时释放内存, 顺带如果遇到了全新的状态图片保存一下"""
        self.faa = None
        self.priority = None
        self.card_kun = None

        # 需要
        # 1. 额外储存了不可用状态图片
        # 2. CD状态也被正确的保存下来(防止整把都因为冰沙整蛊了)
        # 3. 该图片是全新的(一批如果有两张一样的图会重复)
        if (self.state_images["不可用"] is not None) and (self.state_images["冷却"] is not None):

            # 使用读写全局锁 避免冲突
            with g_extra.GLOBAL_EXTRA.file_lock:

                for _, new_state_image in self.state_images.items():

                    for _, state_images_group in RESOURCE_P["card"]["状态判定"].items():
                        for _, state_image in state_images_group.items():

                            if np.array_equal(new_state_image, state_image):
                                CUS_LOGGER.debug(
                                    f"[战斗执行器] [{self.player}P] 成功获取到行的卡片状态图片! 但和已有图片冲突而保存失败!")
                                return

                new_state_group_id = len(RESOURCE_P["card"]["状态判定"])
                path_images_group = PATHS["picture"]["card"] + "\\状态判定\\" + str(new_state_group_id)
                if not os.path.exists(path_images_group):
                    # 创建文件夹
                    os.makedirs(path_images_group)
                RESOURCE_P["card"]["状态判定"][new_state_group_id] = {}
                for state_name in ["冷却", "可用", "不可用"]:
                    # 保存到内存中
                    RESOURCE_P["card"]["状态判定"][new_state_group_id][f"{state_name}.png"] = self.state_images[
                        state_name]
                    # 保存到本地
                    path = f"{path_images_group}\\{state_name}.png"
                    cv2.imencode(ext=".png", img=self.state_images[state_name])[1].tofile(path)
                CUS_LOGGER.debug(f"[战斗执行器] [{self.player}P] 成功获取到行的卡片状态图片! 保存成功!")


class CardKun(Card):
    def __init__(self, priority, faa):
        super().__init__(priority, faa)

        """直接从FAA类读取的属性"""
        # 坐标 [x,y] 和普通卡片不同 需要复写
        self.location_from = self.faa.kun_position["location_from"]

    def use_card(self):
        """
        坤卡没有使用卡片函数, 仅依附于其他卡片进行使用
        :return:
        """
        pass

    def put_card(self):
        """
        坤卡没有使用卡片函数, 仅依附于其他卡片进行使用
        :return:
        """
        pass


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
        self.huzhao = None  # 建立特殊卡护罩与常规卡护罩之间的连接

    def use_card(self, pos):

        if not self.is_auto_battle:
            return
        if self.is_smoothie:
            if not self.faa_battle.fire_elemental_1000:
                return
            if g_extra.GLOBAL_EXTRA.smoothie_lock_time > 0:
                return
            g_extra.GLOBAL_EXTRA.smoothie_lock_time = 7

        # 根据玩家上互斥锁，保证放卡点击序列不会乱掉（因为多次点击还多线程操作很容易出事）
        with self.faa.battle_lock:

            # 无默认坐标即为冰桶类或草扇
            if pos is None:

                # 铲子的调用
                T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=self.faa.handle, key="1")
                time.sleep(self.click_sleep)  # 必须的间隔

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
                            x=mat["location_from"][0] + 5,
                            y=mat["location_from"][1] + 5)
                        time.sleep(self.click_sleep)  # 必须的间隔

                        # 点击 放下卡片
                        T_ACTION_QUEUE_TIMER.add_click_to_queue(
                            handle=self.handle,
                            x=self.location_to[0][0],
                            y=self.location_to[0][1])
                        time.sleep(self.click_sleep)  # 必须的间隔

                # 点击 选中卡片
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=self.location_from[0] + 5,
                    y=self.location_from[1] + 5)
                time.sleep(self.click_sleep)  # 必须的间隔

                # 点击 放下卡片
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=self.location_to[0][0],
                    y=self.location_to[0][1])
                time.sleep(self.click_sleep)  # 必须的间隔

                # 放卡后点一下空白
                T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=200, y=350)
                time.sleep(self.click_sleep)  # 必须的间隔
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=200, y=350)
                time.sleep(self.click_sleep)  # 必须的间隔

                if self.need_shovel:  # 是否要秒铲
                    T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=self.faa.handle, key="1")
                    time.sleep(self.click_sleep)  # 必须的间隔

                    T_ACTION_QUEUE_TIMER.add_click_to_queue(
                        handle=self.faa.handle,
                        x=self.location_to[0][0],
                        y=self.location_to[0][1])
                    time.sleep(self.click_sleep)

                time.sleep(0.2)

            # 有默认坐标传入，意味着是炸弹类卡片
            else:
                # 铲子的调用
                T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=self.faa.handle, key="1")
                time.sleep(self.click_sleep)  # 必须的间隔

                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.faa.handle,
                    x=POSITION_CARD_CELL_IN_BATTLE[f"{pos[0]}-{pos[1]}"][0],
                    y=POSITION_CARD_CELL_IN_BATTLE[f"{pos[0]}-{pos[1]}"][1])
                time.sleep(0.5)

                # 加一个垫子的判断
                if f"{pos[0]}-{pos[1]}" in self.faa.battle_plan_parsed["mat"]:  # 点位要放垫子
                    for mat in self.faa.mat_card_positions:
                        T_ACTION_QUEUE_TIMER.add_click_to_queue(
                            handle=self.handle,
                            x=mat["location_from"][0] + 5,
                            y=mat["location_from"][1] + 5)
                        time.sleep(self.click_sleep)  # 必须的间隔

                        T_ACTION_QUEUE_TIMER.add_click_to_queue(
                            handle=self.faa.handle,
                            x=POSITION_CARD_CELL_IN_BATTLE[f"{pos[0]}-{pos[1]}"][0],
                            y=POSITION_CARD_CELL_IN_BATTLE[f"{pos[0]}-{pos[1]}"][1])

                # 点击 选中卡片
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=self.location_from[0] + 5,
                    y=self.location_from[1] + 5)

                # 点击 放下卡片
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.faa.handle,
                    x=POSITION_CARD_CELL_IN_BATTLE[f"{pos[0]}-{pos[1]}"][0],
                    y=POSITION_CARD_CELL_IN_BATTLE[f"{pos[0]}-{pos[1]}"][1])

                # 放卡后点一下空白
                T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=200, y=350)
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=200, y=350)
                if self.need_shovel:  # 是否要秒铲

                    T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=self.faa.handle, key="1")
                    time.sleep(self.click_sleep / 2)  # 必须的间隔

                    T_ACTION_QUEUE_TIMER.add_click_to_queue(
                        handle=self.faa.handle,
                        x=POSITION_CARD_CELL_IN_BATTLE[f"{pos[0]}-{pos[1]}"][0],
                        y=POSITION_CARD_CELL_IN_BATTLE[f"{pos[0]}-{pos[1]}"][1])
                    time.sleep(self.click_sleep)

                if self.huzhao is not None:
                    # 特殊卡用完当护罩得给他改回常驻卡可用状态
                    self.huzhao.can_use = True

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
