import os
import time

import cv2
import numpy as np

from function.common.bg_img_screenshot import capture_image_png
from function.globals import EXTRA
from function.globals.g_resources import RESOURCE_P
from function.globals.get_paths import PATHS
from function.globals.location_card_cell_in_battle import COORDINATE_CARD_CELL_IN_BATTLE
from function.globals.log import CUS_LOGGER
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER

"""
重要提醒：
FAA 的 放卡位置 的变量有两种
location 为格子 str 格式 例如 "1-1","3-7" 
coordinate 为坐标 list[x:int,y:int] 格式 例如 [500,600], [300,200]
"""


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

    def __init__(self, set_priority, faa):
        # 直接塞进来一个faa的实例地址, 直接从该实例中拉取方法和属性作为参数~
        self.faa = faa
        # 用于直接从战斗方案中读取卡片信息 战斗方案中的index
        self.set_priority = set_priority

        """直接从FAA类读取的属性"""
        self.handle = self.faa.handle
        self.handle_360 = self.faa.handle_360
        self.need_key = self.faa.need_key
        self.is_auto_battle = self.faa.is_auto_battle
        self.faa_battle = self.faa.faa_battle
        self.player = self.faa.player

        """从 FAA类 的 battle_plan_card 中读取的属性"""
        plan = self.faa.battle_plan_card
        plan_by_priority = plan[set_priority] if 0 <= set_priority < len(plan) else {}  # 处理默认值, 方便坤卡继承

        # 根据优先级（也是在战斗方案中的index）直接读取faa
        self.name = plan_by_priority.get("name", "错误")
        self.ergodic = plan_by_priority.get("ergodic", True)
        self.queue = plan_by_priority.get("queue", True)

        # 卡片拿去的位置 - 代号 int 和 坐标 list[x,y]
        self.c_id = plan_by_priority.get("id", 1)
        self.coordinate_from = plan_by_priority.get("coordinate_from", [10, 10])

        # 卡片放置的位置 - 代号 list["1-1",...] 和 坐标 list[[x,y],....]
        self.location = plan_by_priority.get("location", [])
        self.coordinate_to = plan_by_priority.get("coordinate_to", [])

        # 坤优先级
        self.kun = plan_by_priority.get("kun", 0)

        # 坤卡的实例
        self.kun_cards = None

        """用于完成放卡的额外类属性"""
        # 该卡片不同状态下对应的状态图片
        self.state_images = {
            "冷却": None,  # 战斗需要
            "可用": None,  # 战斗需要
            "不可用": None,  # 遇到新图片则保存下来以便初始判断, 也用于判断是否遇到了新的状态图片
        }

        # 放卡间隔
        self.click_sleep = self.faa_battle.click_sleep

        # 游戏最低帧间隔
        self.frame_interval = 1 / EXTRA.LOWEST_FPS

        # 状态
        self.status_cd = False  # 冷却完成 默认已完成
        self.status_usable = False  # 可用
        self.status_ban = 0  # 被ban时间 放卡，但已摆满, 导致放卡后立刻检测到可用，则进入该ban状态8s

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
            x=self.coordinate_from[0] + 25,
            y=self.coordinate_from[1] + 35)

    def put_card(self):
        """
        在取卡后, 放下一张卡并更改内部数组的全套操作
        """

        # 遍历模式: True 遍历该卡每一个可以放的位置
        # 遍历模式: False 只放第一张, 为保证放下去, 同一个位置点两次
        put_to_index_list = range(len(self.coordinate_to)) if self.ergodic else [0, 0]
        for j in put_to_index_list:
            # 点击 放下卡片
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=self.handle,
                x=self.coordinate_to[j][0],
                y=self.coordinate_to[j][1])
            time.sleep(self.click_sleep)

        # 放卡后点一下空白
        T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=295, y=485)  # 曾 200, 350
        time.sleep(self.click_sleep)
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=295, y=485)
        time.sleep(self.click_sleep)

        # 如果启动队列模式放卡参数, 使用一次后, 第一个目标位置移动到末位
        if self.queue and len(self.location) > 0 and len(self.coordinate_to) > 0:
            if self.coordinate_to:
                self.location.append(self.location[0])
                self.location.remove(self.location[0])
                self.coordinate_to.append(self.coordinate_to[0])
                self.coordinate_to.remove(self.coordinate_to[0])

        # 放完卡后强制自ban 1s 这游戏似乎没有cd更短的卡片了!
        self.status_ban = 1

    def get_card_current_img(self, game_image=None):
        """
        获取用于 判定 卡片状态 的图像
        :param game_image: 可选, 是否从已有的完成游戏图像中拆解, 不截图
        :return:
        """
        x1 = self.coordinate_from[0]
        x2 = x1 + 53
        y1 = self.coordinate_from[1]
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

    def try_get_img_for_check_card_states(self):
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
                    if EXTRA.EXTRA_LOG_BATTLE:
                        CUS_LOGGER.info(f"[战斗执行器] [{self.player}P] [{self.name}] 成功从已保存状态获取")
                    return 1

        # 包含点击操作 上锁
        with self.faa.battle_lock:

            # 点击 选中卡片 移动到空白位置
            self.try_get_img_for_check_card_states_choice_card()

            # 等待游戏画面刷新, 这里的值为 FAA 可以正常运行识别的游戏最低FPS对应的帧间隔
            time.sleep(self.frame_interval)

            T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=200, y=350)

            # 等待游戏画面刷新, * 5 以确保稳定运行
            time.sleep(self.frame_interval * 5)

            current_img_clicked = self.get_card_current_img()
            if np.array_equal(current_img, current_img_clicked):
                # 如果什么都没有改变, 意味着该颜色是 不可用 无法试色
                if EXTRA.EXTRA_LOG_BATTLE:
                    CUS_LOGGER.info(f"[战斗执行器] [{self.player}P] [{self.name}] 点击前后颜色相同, 试色失败")
                return 0

            # 发生了改变, 意味着旧的颜色是 可用 新的颜色是 不可用
            self.state_images["可用"] = current_img
            self.state_images["不可用"] = current_img_clicked

            # 放下这张卡
            self.try_get_img_for_check_card_states_put_card()

            # 等待游戏画面刷新, * 5 以确保CD较长的卡片也完成了一像素高度的冷却动画
            time.sleep(self.frame_interval * 5)

        # 放卡后, 获取到的第三种颜色必须不同于另外两种, 才记录为cd色, 否则可能由于冰沙冷却效果导致录入可用为cd色.
        current_img_after_put = self.get_card_current_img()

        if np.array_equal(current_img_after_put, current_img_clicked):
            if EXTRA.EXTRA_LOG_BATTLE:
                CUS_LOGGER.info(f"[战斗执行器] [{self.player}P] [{self.name}]  获取到的cd色和其他状态冲突, 试色失败")
            return 2

        if np.array_equal(current_img_after_put, current_img):
            if EXTRA.EXTRA_LOG_BATTLE:
                CUS_LOGGER.info(f"[战斗执行器] [{self.player}P] [{self.name}] 获取到的cd色和其他状态冲突, 试色失败")
            return 2

        self.state_images["冷却"] = current_img_after_put
        if EXTRA.EXTRA_LOG_BATTLE:
            CUS_LOGGER.info(f"[战斗执行器] [{self.player}P] [{self.name}] 试色成功")
        return 2

    def try_get_img_for_check_card_states_choice_card(self):
        """预留接口, 让高级放卡可以仅覆写这一小部分"""
        self.choice_card()

    def try_get_img_for_check_card_states_put_card(self):
        """预留接口, 让高级放卡可以仅覆写这一小部分"""
        self.put_card()

    def use_card(self):

        # 未启动自动战斗
        if not self.is_auto_battle:
            return

        # 自身是冰沙但不符合使用条件
        if self.is_smoothie:
            if not self.faa_battle.fire_elemental_1000:
                return
            if EXTRA.SMOOTHIE_LOCK_TIME > 0:
                return
            EXTRA.SMOOTHIE_LOCK_TIME = 7

        # 线程放瓜皮时不巧撞上了正在计算炸弹类或者计算完成后炸弹需要该瓜皮
        if not self.can_use:
            return

        # 输出
        # if EXTRA.EXTRA_LOG_BATTLE and self.faa.player == 1:
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

            # 等待游戏画面刷新
            time.sleep(self.frame_interval)

            self.fresh_status()  # 如果放卡后还可用,自ban 若干s

            if self.status_usable and (self.name not in self.ban_white_list):
                # 放满了 如果不在白名单 就自ban
                self.status_ban = 7
                # if self.player == 1:
                #     CUS_LOGGER.debug(f"[1P] {self.name} 因使用后仍可用进行了自ban")
                #     T_ACTION_QUEUE_TIMER.print_queue_statue()
                return

            # 放置成功 如果是坤目标, 复制自身放卡的逻辑
            if not self.is_kun_target:
                return

            # 坤-如果不可用状态 放弃本次用卡
            kun_count = 0
            for kun_card in self.kun_cards:

                if not kun_card.status_usable:
                    continue

                # 防止多坤撞车
                if kun_count >= 1:
                    time.sleep(0.5)

                # 坤-点击 选中卡片
                kun_card.choice_card()
                time.sleep(self.click_sleep)

                # 坤-放卡
                self.put_card()

                # 等待游戏画面刷新
                time.sleep(self.frame_interval)

                kun_card.fresh_status()

                kun_count += 1

    def destroy(self):
        """中止运行时释放内存, 顺带如果遇到了全新的状态图片保存一下"""
        self.faa = None
        self.kun_cards = None

        # 需要
        # 1. 额外储存了不可用状态图片
        # 2. CD状态也被正确的保存下来(防止整把都因为冰沙整蛊了)
        # 3. 该图片是全新的(一批如果有两张一样的图会重复)
        if (self.state_images["不可用"] is not None) and (self.state_images["冷却"] is not None):

            # 使用读写全局锁 避免冲突
            with EXTRA.FILE_LOCK:

                for _, new_state_image in self.state_images.items():

                    for _, state_images_group in RESOURCE_P["card"]["状态判定"].items():
                        for _, state_image in state_images_group.items():

                            if np.array_equal(new_state_image, state_image):
                                CUS_LOGGER.debug(
                                    f"[战斗执行器] [{self.player}P] 成功获取到行的卡片状态图片! 但和已有图片冲突而保存失败!")
                                return

                new_state_group_id = len(RESOURCE_P["card"]["状态判定"])
                path_images_group = PATHS["image"]["card"] + "\\状态判定\\" + str(new_state_group_id)
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
    def __init__(self, faa, name, c_id, coordinate_from):
        # 继承父类初始化
        super().__init__(faa=faa, set_priority=0)

        """直接从FAA类读取的属性"""
        # 覆写 不存在于战斗方案 故手动指定
        self.name = name
        self.c_id = c_id
        self.coordinate_from = coordinate_from

    def use_card(self):
        """
        坤卡没有使用卡片函数, 仅依附于其他卡片进行使用
        :return:
        """
        pass

    def put_card(self):
        """
        坤卡没有使用卡片函数, 仅依附于其他卡片进行使用
        但在罕见情况下 坤类卡片需要重新获取状态, 所以需要强行为其进行一场全屏遍历.
        :return:
        """
        for _, coordinate in COORDINATE_CARD_CELL_IN_BATTLE.items():
            # 点击 放下卡片
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=self.handle,
                x=coordinate[0],
                y=coordinate[1])
            time.sleep(self.click_sleep)

        # 放卡后点一下空白
        T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=295, y=485)  # 曾 200, 350
        time.sleep(self.click_sleep)

        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=295, y=485)
        time.sleep(self.click_sleep)


class SpecialCard(Card):
    def __init__(self, faa, set_priority, card_type, energy=None, rows=None, cols=None, n_card=None):

        # 继承父类初始化
        super().__init__(faa=faa, set_priority=set_priority)

        self.energy = energy  # 特殊卡的初始能量值

        # 是否需要咖啡粉唤醒 算了不想写相关逻辑了，等有缘人补充吧
        # self.need_coffee = self.name in ["冰桶炸弹", "开水壶炸弹"]

        self.card_type = card_type  # 11冰桶 12护罩 14草扇 其他炸弹

        # 要秒铲的有草扇跟护罩炸弹
        self.need_shovel = self.card_type == 12 or self.card_type == 14

        # 炸弹类卡的自我属性
        self.rows = rows
        self.cols = cols

        # 建立特殊卡护罩(炸弹护罩) 与 常规卡护罩 之间的连接 以暂时屏蔽其可用性
        self.n_card = n_card

        # 卡片自身的location 是空的 保存到模板
        # 卡片放置的位置 - 代号 list["1-1",...]
        self.location = []
        self.location_template = self.faa.battle_plan_card[self.set_priority]["location"]

        # 卡片放置的位置 - 坐标 list[[x,y],....]
        self.coordinate_to = []
        self.coordinate_to_template = self.faa.battle_plan_card[self.set_priority]["coordinate_to"]

        # 卡片拿取的位置 - 坐标 list[x,y]
        self.coordinate_from = self.faa.battle_plan_card[self.set_priority]["coordinate_from"]

    def try_get_img_for_check_card_states_choice_card(self):
        """预留接口, 让高级放卡可以仅覆写这一小部分"""
        self.use_card_before()
        self.choice_card()

    def try_get_img_for_check_card_states_put_card(self):
        """预留接口, 让高级放卡可以仅覆写这一小部分"""
        self.put_card()
        self.use_card_after()

    def use_mat_card(self):

        # 加一个垫子的判断 点位要放承载卡
        if self.location[0] in self.faa.stage_info["mat_cell"]:

            for mat in self.faa.mat_cards_info:
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=mat["coordinate_from"][0] + 5,
                    y=mat["coordinate_from"][1] + 5)
                time.sleep(self.click_sleep)

                # 点击 放下卡片
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle, x=self.coordinate_to[0][0], y=self.coordinate_to[0][1])
        time.sleep(self.click_sleep)

    def use_card(self):

        if not self.is_auto_battle:
            return

        # 根据玩家上互斥锁，保证放卡点击序列不会乱掉（因为多次点击还多线程操作很容易出事）
        with self.faa.battle_lock:
            self.use_card_before()
            time.sleep(0.5)  # 真的是必要的间隔，不然会发现铲是铲了，但是把当前正在放的卡铲了（
            # 点击 选中卡片
            self.choice_card()
            time.sleep(self.click_sleep)

            # 选中 放下卡片自身
            self.put_card()

            self.use_card_after()

    def use_card_before(self):

        # 铲子的调用
        self.faa_battle.use_shovel(x=self.coordinate_to[0][0], y=self.coordinate_to[0][1])

        # 加一个垫子的判断 点位要放承载卡
        self.use_mat_card()

    def use_card_after(self):

        if self.need_shovel:  # 是否要秒铲
            self.faa_battle.use_shovel(x=self.coordinate_to[0][0], y=self.coordinate_to[0][1])

        if self.n_card:
            # 特殊卡用完当护罩得给他改回常驻卡可用状态
            self.n_card.can_use = True
