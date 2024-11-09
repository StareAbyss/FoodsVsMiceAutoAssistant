import datetime
import time

from function.common.bg_img_match import loop_match_p_in_w
from function.globals import SIGNAL
from function.globals.g_resources import RESOURCE_P
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER


class FAAActionQuestReceiveRewards:
    """
    领取各种任务奖励的动作
    """

    def __init__(self, faa):
        self.faa = faa

    def normal(self):
        """领取普通任务奖励"""

        handle = self.faa.handle
        handle_360 = self.faa.handle_360
        action_exit = self.faa.action_exit

        def scan_one_page():
            """扫描一页"""

            # 最大尝试次数
            max_attempts = 30

            # 循环遍历点击完成
            for try_count in range(max_attempts):
                find = loop_match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=[335, 120, 420, 545],
                    template=RESOURCE_P["common"]["任务_完成.png"],
                    match_tolerance=0.95,
                    match_failed_check=1,
                    after_sleep=0.5,
                    click=True)
                if find:
                    # 领取奖励
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=643, y=534)
                    time.sleep(0.2)
                else:
                    break

            # 如果达到了最大尝试次数
            if try_count == max_attempts - 1:
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                SIGNAL.DIALOG.emit(
                    "背包满了！(╬◣д◢)",
                    f"{self.faa.player}P因背包爆满, 导致 [领取普通任务奖励] 失败!\n"
                    f"出错时间:{current_time}, 尝试次数:{max_attempts}")

        self.faa.action_bottom_menu(mode="任务")

        # 复位滑块
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=413, y=155)
        time.sleep(0.25)

        for i in range(8):

            # 不是第一次滑块向下移动3次
            if i != 0:
                for j in range(3):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=413, y=524)
                    time.sleep(0.05)

            scan_one_page()

        action_exit(mode="普通红叉")

    def guild(self):

        handle = self.faa.handle
        handle_360 = self.faa.handle_360
        action_bottom_menu = self.faa.action_bottom_menu
        action_exit = self.faa.action_exit

        # 跳转到任务界面
        action_bottom_menu(mode="跳转_公会任务")

        # 最大尝试次数
        max_attempts = 20

        # 循环遍历点击完成
        for try_count in range(max_attempts):

            # 点一下 让左边的选中任务颜色消失
            loop_match_p_in_w(
                source_handle=handle,
                source_root_handle=handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["quest_guild"]["ui_quest_list.png"],
                after_sleep=0.5,
                click=True)

            # 检查是否有已完成的任务
            result = loop_match_p_in_w(
                source_handle=handle,
                source_root_handle=handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["quest_guild"]["completed.png"],
                match_tolerance=0.99,
                click=True,
                match_failed_check=5,  # 1+4s 因为偶尔会弹出美食大赛完成动画4s 需要充足时间！这个确实脑瘫...
                after_sleep=0.5)
            if not result:
                break

            # 点击“领取”按钮
            loop_match_p_in_w(
                source_handle=handle,
                source_root_handle=handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["quest_guild"]["gather.png"],
                match_tolerance=0.99,
                click=True,
                match_failed_check=2,
                after_sleep=2)  # 2s 完成任务有显眼动画

        # 如果达到了最大尝试次数
        if try_count == max_attempts - 1:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            SIGNAL.DIALOG.emit(
                "背包满了！(╬◣д◢)",
                f"{self.faa.player}P因背包爆满, 导致 [领取公会任务奖励] 失败!\n"
                f"出错时间:{current_time}, 尝试次数:{max_attempts}")

        # 退出任务界面
        action_exit(mode="普通红叉")

    def spouse(self):

        handle = self.faa.handle
        handle_360 = self.faa.handle_360
        action_bottom_menu = self.faa.action_bottom_menu
        action_exit = self.faa.action_exit

        # 跳转到任务界面
        action_bottom_menu(mode="跳转_情侣任务")

        # 最大尝试次数
        max_attempts = 10

        # 循环遍历点击完成
        for try_count in range(max_attempts):

            result = loop_match_p_in_w(
                source_handle=handle,
                source_root_handle=handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["quest_spouse"]["completed.png"],
                match_tolerance=0.99,
                click=True,
                match_failed_check=2,
                after_sleep=2)  # 2s 完成任务有显眼动画)

            if not result:
                break

        # 如果达到了最大尝试次数
        if try_count == max_attempts - 1:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            SIGNAL.DIALOG.emit(
                "背包满了！(╬◣д◢)",
                f"{self.faa.player}P因背包爆满, 导致 [领取情侣任务奖励] 失败!\n"
                f"出错时间:{current_time}, 尝试次数:{max_attempts}")

        # 点两下右下角的领取
        for _ in range(2):
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=795, y=525)
            time.sleep(0.1)

        # 退出任务界面
        action_exit(mode="普通红叉")

    def offer_reward(self):
        """
        领取悬赏任务奖励
        :return: None
        """

        handle = self.faa.handle
        handle_360 = self.faa.handle_360
        action_top_menu = self.faa.action_top_menu
        action_exit = self.faa.action_exit

        # 进入X年活动界面
        action_top_menu(mode="X年活动")

        # 最大尝试次数
        max_attempts = 10

        # 循环遍历点击完成
        for try_count in range(max_attempts):
            result = loop_match_p_in_w(
                source_handle=handle,
                source_root_handle=handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["悬赏任务_领取奖励.png"],
                match_tolerance=0.99,
                match_failed_check=2,
                click=True,
                after_sleep=2)
            if not result:
                break

        # 如果达到了最大尝试次数
        if try_count == max_attempts - 1:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            SIGNAL.DIALOG.emit(
                "背包满了！(╬◣д◢)",
                f"{self.faa.player}P因背包爆满, 导致 [领取悬赏任务奖励]失败!\n"
                f"出错时间:{current_time}, 尝试次数:{max_attempts}")

        # 退出任务界面
        action_exit(mode="关闭悬赏窗口")

    def food_competition(self):

        handle = self.faa.handle
        handle_360 = self.faa.handle_360
        action_top_menu = self.faa.action_top_menu
        print_debug = self.faa.print_debug
        print_warning = self.faa.print_warning

        found_flag = False  # 记录是否有完成任何一次任务

        # 进入美食大赛界面
        find = action_top_menu(mode="美食大赛")

        if find:

            my_dict = {0: 362, 1: 405, 2: 448, 3: 491, 4: 534, 5: 570}
            for i in range(6):

                # 先移动一次位置
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=536, y=my_dict[i])
                time.sleep(0.2)

                # 最大尝试次数
                max_attempts = 10

                # 循环遍历点击完成
                for try_count in range(max_attempts):
                    find = loop_match_p_in_w(
                        source_handle=handle,
                        source_root_handle=handle_360,
                        source_range=[0, 0, 950, 600],
                        template=RESOURCE_P["common"]["美食大赛_领取.png"],
                        match_tolerance=0.95,
                        match_failed_check=0.5,
                        after_sleep=0.5,
                        click=True)
                    if find:
                        # 领取升级有动画
                        print_debug(text="[收取奖励] [美食大赛] 完成1个任务")
                        time.sleep(6)
                        # 更新是否找到flag
                        found_flag = True
                    else:
                        break

                # 如果达到了最大尝试次数
                if try_count == max_attempts - 1:
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    SIGNAL.DIALOG.emit(
                        "背包满了！(╬◣д◢)",
                        f"{self.faa.player}P因背包爆满, 导致 [领取悬赏任务奖励]失败!\n"
                        f"出错时间:{current_time}, 尝试次数:{max_attempts}")

            # 退出美食大赛界面
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=888, y=53)
            time.sleep(0.5)

        else:
            print_warning(text="[领取奖励] [美食大赛] 未打开界面, 可能大赛未刷新")

        if not found_flag:
            print_debug(text="[领取奖励] [美食大赛] 未完成任意任务")

    def monopoly(self):
        handle = self.faa.handle
        action_top_menu = self.faa.action_top_menu

        # 进入对应地图
        find = action_top_menu(mode="大富翁")

        if find:

            y_dict = {
                0: 167,
                1: 217,
                2: 266,
                3: 320,
                4: 366,
                5: 417
            }

            for i in range(3):

                if i > 0:
                    # 下一页
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=878, y=458)
                    time.sleep(0.5)

                # 点击每一个有效位置
                for j in range(6):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=768, y=y_dict[j])
                    time.sleep(0.1)

            # 退出界面
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=928, y=16)
            time.sleep(0.5)

    def camp(self):

        handle = self.faa.handle

        # 进入界面
        find = self.faa.action_goto_map(map_id=10)

        if find:
            for _ in range(10):
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=175, y=325)
                time.sleep(0.2)
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=175, y=365)
                time.sleep(0.2)

    def main(self, mode) -> None:
        print_debug = self.faa.print_debug

        print_debug(text="[领取奖励] [{}] 开始".format(mode))

        if mode == "普通任务":
            self.normal()
        if mode == "公会任务":
            self.guild()
        if mode == "情侣任务":
            self.spouse()
        if mode == "悬赏任务":
            self.offer_reward()
        if mode == "美食大赛":
            self.food_competition()
        if mode == "大富翁":
            self.monopoly()
        if mode == "营地任务":
            self.camp()

        print_debug(text="[领取奖励] [{}] 结束".format(mode))
