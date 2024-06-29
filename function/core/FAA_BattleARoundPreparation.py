import time

import cv2

from function.common.bg_img_match import loop_match_ps_in_w, loop_match_p_in_w, match_p_in_w
from function.common.bg_img_screenshot import capture_image_png
from function.common.overlay_images import overlay_images
from function.core.analyzer_of_loot_logs import match_items_from_image
from function.globals.get_paths import PATHS
from function.globals.init_resources import RESOURCE_P
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER


class BattleARoundPreparation:

    def __init__(self, faa):
        # __init__中捕获了的外部类属性值, 那么捕获的是那一刻的值, 后续对类属性的修改不会影响已经捕获的值
        # 但只捕获这个类本身, 在函数里调用的类属性, 则是实时值 √
        self.faa = faa

    """战前整备部分"""

    def add_quest_card(self):

        handle = self.faa.handle
        handle_360 = self.faa.handle_360
        quest_card = self.faa.quest_card
        print_debug = self.faa.print_debug

        # 由于公会任务的卡组特性, 当任务卡为[苏打气泡]时, 不需要额外选择带卡.
        need_add = False
        need_add = need_add or quest_card == "None"
        need_add = need_add or quest_card == "苏打气泡-0"
        need_add = need_add or quest_card == "苏打气泡-1"
        need_add = need_add or quest_card == "苏打气泡"

        if need_add:
            print_debug(text=f"[添加任务卡] 不需要,跳过")
            return
        else:
            print_debug(text=f"[添加任务卡] 开始, 目标:{quest_card}")

        """处理ban卡列表"""

        # 对于名称带-的卡, 就对应的写入, 如果不带-, 就查找其所有变种
        if "-" in quest_card:
            quest_card_list = [f"{quest_card}.png"]
        else:
            # i代表一张卡能有的最高变种 姑且认为是3*7 = 21
            quest_card_list = [f"{quest_card}-{i}.png" for i in range(21)]

        # 读取所有记录了的卡的图片名, 只携带被记录图片的卡
        quest_card_list = [card for card in quest_card_list if card in RESOURCE_P["card"]["准备房间"]]

        """选卡动作"""
        already_found = False

        # 复位滑块
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=931, y=209)
        time.sleep(0.5)

        # 向下点3*7次滑块 强制要求全部走完, 防止12P的同步出问题
        for i in range(7):

            for quest_card in quest_card_list:

                if already_found:
                    # 如果已经刚找到了 就直接休息一下
                    time.sleep(0.4)
                else:
                    # 如果还没找到 就试试查找点击 添加卡片
                    img_tar = overlay_images(
                        img_background=RESOURCE_P["card"]["准备房间"][quest_card],
                        img_overlay=RESOURCE_P["card"]["卡片-房间-绑定角标.png"],
                        test_show=False)

                    find = loop_match_p_in_w(
                        source_handle=handle,
                        source_root_handle=handle_360,
                        source_range=[380, 175, 925, 420],
                        template=img_tar,
                        template_mask=RESOURCE_P["card"]["卡片-房间-掩模-绑定.png"],
                        match_tolerance=0.95,
                        match_failed_check=0.4,
                        match_interval=0.2,
                        after_sleep=0.4,  # 和总计检测时间一致 以同步时间
                        click=True)
                    if find:
                        already_found = True

            # 滑块向下移动3次
            for j in range(3):
                if not already_found:
                    # 仅还没找到继续下滑
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=931, y=400)
                # 找没找到都要休息一下以同步时间
                time.sleep(0.05)

        if not already_found:
            # 如果没有找到 类属性 战斗方案 需要调整为None, 防止在战斗中使用对应卡片的动作序列出现
            self.faa.quest_card = "None"

        print_debug(text=" [添加任务卡] 完成, 结果:{}".format("成功" if already_found else "失败"))

    def remove_ban_card(self):
        """寻找并移除需要ban的卡, 现已支持跨页ban"""

        handle = self.faa.handle
        ban_card_list = self.faa.ban_card_list
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
        ban_card_list = [ban_card for ban_card in ban_card_list if ban_card in RESOURCE_P["card"]["准备房间"]]

        # 翻页回第一页
        for i in range(5):
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=930, y=55)
            time.sleep(0.05)

        # 第一页
        self.screen_ban_card_loop_a_round(ban_card_s=ban_card_list)

        # 翻页到第二页
        for i in range(5):
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=930, y=85)
            time.sleep(0.05)

        # 第二页
        self.screen_ban_card_loop_a_round(ban_card_s=ban_card_list)

    def screen_ban_card_loop_a_round(self, ban_card_s):

        handle = self.faa.handle
        handle_360 = self.faa.handle_360

        for card in ban_card_s:
            img_tar = overlay_images(
                img_background=RESOURCE_P["card"]["准备房间"][card],
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

    def before(self):
        """
        房间内战前准备
        :return: 0-正常结束 1-重启本次 2-跳过本次
        """
        handle = self.faa.handle
        handle_360 = self.faa.handle_360
        deck = self.faa.deck
        print_debug = self.faa.print_debug
        print_warning = self.faa.print_warning

        # 循环查找开始按键
        print_debug(text="寻找开始或准备按钮")
        find = loop_match_p_in_w(
            source_handle=handle,
            source_root_handle=handle_360,
            source_range=[796, 413, 950, 485],
            template=RESOURCE_P["common"]["战斗"]["战斗前_开始按钮.png"],
            match_interval=1,
            match_failed_check=10,
            after_sleep=0.3,
            click=False)
        if not find:
            print_warning(text="创建房间后, 10s找不到[开始/准备]字样! 创建房间可能失败!")
            # 2-跳过本次 可能是由于: 服务器抽风无法创建房间 or 点击被吞 or 次数用尽
            return 2

        # 选择卡组
        print_debug(text="选择卡组, 并开始加入新卡和ban卡")
        T_ACTION_QUEUE_TIMER.add_click_to_queue(
            handle=handle,
            x={1: 425, 2: 523, 3: 588, 4: 666, 5: 756, 6: 837}[deck],
            y=121)
        time.sleep(0.7)

        """寻找并添加任务所需卡片"""
        self.add_quest_card()
        self.remove_ban_card()

        """点击开始"""

        # 点击开始
        find = loop_match_p_in_w(
            source_handle=handle,
            source_root_handle=handle_360,
            source_range=[796, 413, 950, 485],
            template=RESOURCE_P["common"]["战斗"]["战斗前_开始按钮.png"],
            match_tolerance=0.95,
            match_interval=1,
            match_failed_check=10,
            after_sleep=1,
            click=True)
        if not find:
            print_warning(text="选择卡组后, 10s找不到[开始/准备]字样! 创建房间可能失败!")
            return 1  # 1-重启本次

        # 防止被 [没有带xx卡] or []包已满 卡住
        find = match_p_in_w(
            source_handle=handle,
            source_root_handle=handle_360,
            source_range=[0, 0, 950, 600],
            template=RESOURCE_P["common"]["战斗"]["战斗前_系统提示.png"],
            match_tolerance=0.98)
        if find:
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=handle,
                x=427,
                y=353)
            time.sleep(0.05)

        # 刷新ui: 状态文本
        print_debug(text="查找火苗标识物, 等待进入战斗, 限时30s")

        # 循环查找火苗图标 找到战斗开始
        find = loop_match_p_in_w(
            source_handle=handle,
            source_root_handle=handle_360,
            source_range=[0, 0, 950, 600],
            template=RESOURCE_P["common"]["战斗"]["战斗中_火苗能量.png"],
            match_interval=0.5,
            match_failed_check=30,
            after_sleep=0.1,
            click=False)

        # 刷新ui: 状态文本
        if find:
            print_debug(text="找到火苗标识物, 战斗进行中...")

        else:
            print_warning(text="未能找到火苗标识物, 进入战斗失败, 可能是次数不足或服务器卡顿")
            return 2  # 2-跳过本次

        return 0  # 0-一切顺利

    """初始化战斗方案部分"""

    # 在FAA中实现 需要修改FAA的类属性

    """战斗结束战利品的领取和捕获图片并识别部分"""

    def action_and_capture_loots(self):
        """
        :return: 捕获的战利品dict
        """

        handle = self.faa.handle

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
        images.append(capture_image_png(handle=handle, raw_range=[209, 454, 699, 552]))
        time.sleep(0.25)

        # 3 4 行 取3行
        for i in range(3):
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=708, y=510)
            time.sleep(0.05)
        time.sleep(0.25)
        images.append(capture_image_png(handle=handle, raw_range=[209, 456, 699, 505]))
        time.sleep(0.25)

        # 4 5 行
        for i in range(3):
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=708, y=529)
            time.sleep(0.05)
        time.sleep(0.25)
        images.append(capture_image_png(handle=handle, raw_range=[209, 454, 699, 552]))
        time.sleep(0.25)

        # 垂直拼接
        image = cv2.vconcat(images)

        return image

    def capture_and_match_loots(self) -> dict:
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

            # 定义保存路径和文件名格式
            img_path = "{}\\{}_{}P_{}.png".format(
                PATHS["logs"] + "\\loots_picture",
                stage_info["id"],
                player,
                time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime())
            )

            # 捕获战利品截图 动作+拼接
            img = self.action_and_capture_loots()

            # 分析图片，获取战利品字典
            drop_dict = match_items_from_image(img_save_path=img_path, image=img, mode='loots', test_print=True)
            print_info(text="[捕获战利品] 处在战利品UI 战利品已 捕获/识别/保存".format(drop_dict))

            return drop_dict

        else:
            print_info(text="[捕获战利品] 未在战利品UI 可能由于延迟未能捕获战利品, 继续流程")

            return {}

    def capture_and_match_treasure_chests(self) -> dict:

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
                    raw_range=[249, 89, 293, 133]),
                capture_image_png(
                    handle=handle,
                    raw_range=[317, 89, 361, 133])
            ]

            img = cv2.hconcat(img)

            # 定义保存路径和文件名格式
            img_path = "{}\\{}_{}P_{}.png".format(
                PATHS["logs"] + "\\chests_picture",
                stage_info["id"],
                player,
                time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime())
            )

            # 分析图片，获取战利品字典
            drop_dict = match_items_from_image(img_save_path=img_path, image=img, mode="chests", test_print=True)
            print_info(text="[翻宝箱UI] 宝箱已 捕获/识别/保存".format(drop_dict))

            # 组队2P慢点结束翻牌 保证双人魔塔后自己是房主
            if is_group and player == 2:
                time.sleep(2)

            # 结束翻牌
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=708, y=502)
            time.sleep(3)

            return drop_dict

        else:
            print_warning(text="[翻宝箱UI] 15s未能捕获正确标志, 出问题了!")
            return {}

    def perform_action_capture_match_for_loots_and_chests(self):
        """
        战斗结束后, 完成下述流程: 潜在的任务完成黑屏-> 战利品 -> 战斗结算 -> 翻宝箱 -> 回到房间/魔塔会回到其他界面
        :return: int 状态码; None或dict, 该dict格式一定是 {"loots": {...}, "chests": {...}}
        """

        print_debug = self.faa.print_debug
        screen_check_server_boom = self.faa.screen_check_server_boom
        print_warning = self.faa.print_warning

        print_debug(text="识别到多种战斗结束标志之一, 进行收尾工作")

        # 战利品部分, 会先检测是否在对应界面
        loots_dict = self.capture_and_match_loots()

        # 翻宝箱部分, 会先检测是否在对应界面
        chests_dict = self.capture_and_match_treasure_chests()

        # 重整化 loots_dict 和 chests_dict 一定是dict()
        result_loot = {"loots": loots_dict, "chests": chests_dict}

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
