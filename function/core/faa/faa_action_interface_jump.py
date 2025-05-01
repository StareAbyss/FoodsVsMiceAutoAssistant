import random
import time
from typing import TYPE_CHECKING

from function.common.bg_img_match import loop_match_p_in_w, match_p_in_w
from function.common.bg_img_screenshot import capture_image_png
from function.globals import g_resources, SIGNAL
from function.globals.g_resources import RESOURCE_P
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER

if TYPE_CHECKING:
    from function.core.faa.faa_mix import FAA


class FAAActionInterfaceJump:

    def action_exit(self: "FAA", mode: str = "None", raw_range=None) -> None:
        """
        游戏中的各种退出操作
        "普通红叉"
        "回到上一级"
        "竞技岛"
        "关闭悬赏窗口"
        "美食大赛领取"
        "游戏内退出"
        """
        handle = self.handle
        handle_360 = self.handle_360
        print_error = self.print_error
        receive_quest_rewards = self.action_receive_quest_rewards

        if raw_range is None:
            raw_range = [0, 0, 950, 600]

        if mode == "回到上一级":
            self.action_bottom_menu(mode="后退")

        if mode == "普通红叉":
            find = loop_match_p_in_w(
                source_handle=handle,
                source_root_handle=handle_360,
                source_range=raw_range,
                template=RESOURCE_P["common"]["退出.png"],
                match_failed_check=5,
                after_sleep=1.5,
                click=True)
            if not find:
                find = loop_match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=[0, 0, 950, 600],
                    template=RESOURCE_P["common"]["退出_被选中.png"],
                    match_failed_check=5,
                    after_sleep=1.5,
                    click=True)
                if not find:
                    print_error(text="未能成功找到右上红叉以退出!前面的步骤有致命错误!")

        if mode == "竞技岛":
            self.action_bottom_menu(mode="跳转_竞技场")

        if mode == "关闭悬赏窗口":
            # 有被选中和未选中两种图标
            result = loop_match_p_in_w(
                source_handle=handle,
                source_root_handle=handle_360,
                source_range=raw_range,
                template=RESOURCE_P["common"]["悬赏任务_退出_未选中.png"],
                match_tolerance=0.99,
                match_failed_check=3,
                after_sleep=1.5,
                click=True)
            if not result:
                loop_match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=raw_range,
                    template=RESOURCE_P["common"]["悬赏任务_退出_被选中.png"],
                    match_tolerance=0.99,
                    match_failed_check=3,
                    after_sleep=1.5,
                    click=True)

        if mode == "美食大赛领取":
            # 领取奖励
            receive_quest_rewards(mode="美食大赛")

        if mode == "游戏内退出":
            # 游戏内退出
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=925, y=580)
            time.sleep(0.1)

            # 确定游戏内退出
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=455, y=385)
            time.sleep(0.1)

        # 安全时延
        time.sleep(0.25)

    def action_top_menu(self: "FAA", mode: str) -> bool:
        """
        点击上方菜单栏, 包含:
        VIP签到|X年活动|塔罗寻宝|大地图|大富翁|欢乐假期|每日签到|美食大赛|美食活动|萌宠神殿|跨服远征|月卡福利
        其中跨服会跳转到二区
        :return bool 是否进入成功
        """

        handle = self.handle
        handle_360 = self.handle_360
        print_debug = self.print_debug
        print_warning = self.print_warning

        failed_time = 0
        tar_menu_page = 1
        while True:

            self.action_change_activity_list(serial_num=tar_menu_page)

            find = loop_match_p_in_w(
                source_handle=handle,
                source_root_handle=handle_360,
                source_range=[250, 0, 880, 110],
                template=RESOURCE_P["common"]["顶部菜单"]["{}.png".format(mode)],
                match_failed_check=3,
                after_sleep=1.5,
                click=True)
            if find:
                print_debug(text="[顶部菜单] [{}] 3s内跳转成功".format(mode))
                break
            else:
                tar_menu_page = 1 if tar_menu_page == 2 else 2
                failed_time += 1

            if failed_time == 5:
                print_warning(text="[顶部菜单] [{}] 3s内跳转失败".format(mode))
                break

        if mode == "跨服远征":

            # 确认已经跨服进房间
            find = loop_match_p_in_w(
                source_handle=handle,
                source_root_handle=handle_360,
                source_range=[0, 0, 950, 200],
                template=RESOURCE_P["common"]["跨服副本_ui.png"],
                match_failed_check=10,
                click=False,
            )

            if find:
                # 选2区人少
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=785, y=30)
                time.sleep(0.5)

                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=785, y=85)
                time.sleep(0.5)

        return find

    def action_bottom_menu(self: "FAA", mode: str) -> bool:
        """点击下方菜单栏, 包含:任务/后退/背包/跳转_公会任务/跳转_公会副本/跳转_情侣任务/跳转_竞技场/跳转_缘分树"""

        handle = self.handle
        handle_360 = self.handle_360
        print_warning = self.print_warning

        find = False

        if (
                mode == "任务" or
                mode == "后退" or
                mode == "背包" or
                mode == "公会"
        ):
            find = loop_match_p_in_w(
                source_handle=handle,
                source_root_handle=handle_360,
                source_range=[520, 570, 950, 600],
                template=RESOURCE_P["common"]["底部菜单"]["{}.png".format(mode)],
                match_tolerance=0.99,
                match_failed_check=3,
                after_sleep=1,
                click=True)

        if (
                mode == "跳转_公会任务" or
                mode == "跳转_公会副本" or
                mode == "跳转_情侣任务" or
                mode == "跳转_竞技场" or
                mode == "跳转_缘分树"
        ):
            loop_match_p_in_w(
                source_handle=handle,
                source_root_handle=handle_360,
                source_range=[520, 530, 950, 600],
                template=RESOURCE_P["common"]["底部菜单"]["跳转.png"],
                match_failed_check=3,
                after_sleep=0.5,
                click=True)
            find = loop_match_p_in_w(
                source_handle=handle,
                source_root_handle=handle_360,
                source_range=[520, 170, 950, 600],
                template=RESOURCE_P["common"]["底部菜单"]["{}.png".format(mode)],
                match_failed_check=3,
                after_sleep=0.5,
                click=True)

        if not find:
            print_warning(text="[底部菜单] [{}] 3s内跳转失败".format(mode))

        return find

    def action_change_activity_list(self: "FAA", serial_num: int) -> None:
        """检测顶部的活动清单, 1为第一页, 2为第二页(有举报图标的一页)"""

        handle = self.handle
        handle_360 = self.handle_360

        find = match_p_in_w(
            source_handle=handle,
            source_root_handle=handle_360,
            source_range=[0, 0, 950, 600],
            template=RESOURCE_P["common"]["顶部菜单"]["举报.png"])

        if serial_num == 1:
            if find:
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=785, y=30)
                time.sleep(0.5)

        if serial_num == 2:
            if not find:
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=785, y=30)
                time.sleep(0.5)

    def action_goto_map(self: "FAA", map_id) -> bool:
        """
        用于前往各地图, 0.美味阵, 1.美味岛, 2.火山岛, 3.火山遗迹, 4.浮空岛, 5.海底, 6.太空, 10.营地
        """
        handle = self.handle
        handle_360 = self.handle_360

        # 点击世界地图
        self.action_top_menu(mode="大地图")

        # 点击对应的地图
        find = loop_match_p_in_w(
            source_handle=handle,
            source_root_handle=handle_360,
            source_range=[0, 0, 950, 600],
            template=RESOURCE_P["map"]["{}.png".format(map_id)],
            match_tolerance=0.99,
            match_failed_check=5,
            after_sleep=2,
            click=True
        )
        return find

    def action_goto_stage(self: "FAA", mt_first_time: bool = False) -> None:
        """
        只要右上能看到地球 就可以到目标关卡
        Args:
            mt_first_time: 魔塔关卡下 是否是第一次打(第一次塔需要进塔 第二次只需要选关卡序号)
        """

        handle = self.handle
        handle_360 = self.handle_360

        # 拆成数组["关卡类型","地图id","关卡id"]
        stage_list = self.stage_info["id"].split("-")
        stage_0 = stage_list[0]  # type
        stage_1 = stage_list[1]  # map
        stage_2 = stage_list[2]  # stage

        def click_set_password():
            """设置进队密码"""
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=491, y=453)
            time.sleep(0.5)
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=600, y=453)
            time.sleep(0.5)
            T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=handle, key="backspace")
            time.sleep(0.5)
            T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=handle, key="1")
            time.sleep(1)

        def change_to_region(region_list):
            random.seed(self.random_seed)
            region_id = random.randint(region_list[0], region_list[1])

            time.sleep(5.0)

            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=803, y=84)
            time.sleep(1.0)

            my_list = [85, 110, 135, 160, 185, 210, 235, 260, 285, 310, 335]
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=779, y=my_list[region_id - 1])

            time.sleep(5.0)

        def main_no():
            # 进入对应地图
            self.action_goto_map(map_id=stage_1)

            # 切区
            my_dict = {"1": [3, 11], "2": [1, 2], "3": [1, 1], "4": [1, 2], "5": [1, 2], "6": [1, 2]}
            change_to_region(region_list=my_dict[stage_1])

            # 仅限主角色创建关卡
            if self.is_main:
                # 防止被活动列表遮住
                self.action_change_activity_list(serial_num=2)

                # 选择关卡
                loop_match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=[0, 0, 950, 600],
                    template=RESOURCE_P["stage"]["{}.png".format(self.stage_info["id"])],
                    match_tolerance=0.995,
                    after_sleep=1,
                    click=True)

                # 设置密码
                click_set_password()

                # 创建队伍
                loop_match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=[0, 0, 950, 600],
                    template=RESOURCE_P["common"]["战斗"]["战斗前_创建房间.png"],
                    after_sleep=1,
                    click=True)

        def main_mt():

            if mt_first_time:
                # 前往海底
                self.action_goto_map(map_id=5)

                # 选区
                change_to_region(region_list=[1, 2])

            if self.is_main and mt_first_time:
                # 进入魔塔
                loop_match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=[0, 0, 950, 600],
                    template=RESOURCE_P["stage"]["MT.png"],
                    match_failed_check=5,
                    after_sleep=2,
                    click=True
                )

                # stage_1 根据模式进行选择
                my_dict = {"1": 46, "2": 115, "3": 188}
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=my_dict[stage_1], y=66)
                time.sleep(0.5)

            # 不是房主, 不进行关卡选择和创建房间
            if not self.is_main:
                return

            # 选择了密室 直接识图找关卡
            if stage_1 == "3":
                loop_match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=[0, 0, 950, 600],
                    template=RESOURCE_P["stage"]["{}.png".format(self.stage_info["id"])],
                    after_sleep=0.3,
                    click=True)

            # 单双人爬塔 等于0则为爬塔模式 即选择最高层 从下到上遍历所有层数
            if stage_1 != "3" and stage_2 == "0":
                # 到魔塔最低一层
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=47, y=579)
                time.sleep(0.3)

                for i in range(11):
                    # 下一页
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=152, y=577)
                    time.sleep(0.1)

                    for j in range(15):
                        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=110, y=542 - 30.8 * j)
                        time.sleep(0.1)

            # 单双人爬塔 指定层数
            if stage_1 != "3" and stage_2 != "0":
                # 到魔塔最低一层
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=47, y=579)
                time.sleep(0.3)

                # 向右到对应位置
                my_left = int((int(stage_2) - 1) / 15)
                for i in range(my_left):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=152, y=577)
                    time.sleep(0.3)

                # 点击对应层数
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=handle,
                    x=110,
                    y=542 - (30.8 * (int(stage_2) - my_left * 15 - 1)))
                time.sleep(0.3)

            # 创建房间
            loop_match_p_in_w(
                source_handle=handle,
                source_root_handle=handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["common"]["战斗"]["战斗前_魔塔_创建房间.png"],
                after_sleep=1,
                click=True)

        def main_cs():

            # 进入跨服远征界面
            self.action_top_menu(mode="跨服远征")

            if self.is_main:
                # 创建房间
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=853, y=553)
                time.sleep(1.0)

                # 选择地图
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=int(stage_1) * 101 - 36, y=70)
                time.sleep(1.0)

                # 选择关卡
                my_dict = {
                    "1": [124, 248], "2": [349, 248], "3": [576, 248], "4": [803, 248],
                    "5": [124, 469], "6": [349, 469], "7": [576, 469], "8": [803, 469]}
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=handle,
                    x=my_dict[stage_2][0],
                    y=my_dict[stage_2][1])
                time.sleep(1.0)

                # 选择密码输入框
                my_dict = {
                    "1": [194, 248], "2": [419, 248], "3": [646, 248], "4": [873, 248],
                    "5": [194, 467], "6": [419, 467], "7": [646, 467], "8": [873, 467]}
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=handle,
                    x=my_dict[stage_2][0],
                    y=my_dict[stage_2][1])
                time.sleep(1.0)

                # 输入密码
                T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=handle, key="1")
                time.sleep(1.0)

                # 创建关卡
                my_dict = {  # X+225 Y+221
                    "1": [176, 286], "2": [401, 286], "3": [629, 286], "4": [855, 286],
                    "5": [176, 507], "6": [401, 507], "7": [629, 507], "8": [855, 507]}
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=handle,
                    x=my_dict[stage_2][0],
                    y=my_dict[stage_2][1])
                time.sleep(1.0)
            else:
                # 刷新
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=895, y=80)
                time.sleep(3.0)

                # 复位
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=602, y=490)
                time.sleep(1.0)

                for i in range(20):
                    find = loop_match_p_in_w(
                        source_handle=handle,
                        source_root_handle=handle_360,
                        source_range=[385, 95, 935, 390],
                        template=g_resources.RESOURCE_CP["用户自截"]["跨服远征_1p.png"],
                        click=True,
                        after_sleep=1.0,
                        match_failed_check=2.0)
                    if find:
                        break
                    else:
                        # 下一页
                        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=700, y=490)

                # 点击密码框 输入密码 确定进入
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=490, y=300)
                time.sleep(1.0)

                T_ACTION_QUEUE_TIMER.add_keyboard_up_down_to_queue(handle=handle, key="1")
                time.sleep(1.0)

                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=490, y=360)
                time.sleep(1.0)

        def main_or():

            # 进入X年活动界面
            self.action_top_menu(mode="X年活动")

            # 选择关卡
            loop_match_p_in_w(
                source_handle=handle,
                source_root_handle=handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["stage"]["{}.png".format(self.stage_info["id"])],
                match_tolerance=0.95,
                after_sleep=3,
                click=True)

            # 切区
            my_dict = {"1": [3, 11], "2": [1, 2], "3": [1, 2], "4": [1, 2]}
            change_to_region(region_list=my_dict[stage_2])

            # 仅限创房间的人
            if self.is_main:
                # 设置密码
                click_set_password()
                # 创建队伍
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=583, y=500)
                time.sleep(0.5)

        def main_ex():

            # 防止被活动列表遮住
            self.action_change_activity_list(2)

            # 进入对应地图
            self.action_goto_map(map_id=10)

            # 不是营地
            if stage_1 != "1":
                # 找船
                loop_match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=[0, 0, 950, 600],
                    template=RESOURCE_P["stage"]["EX-Ship.png"],
                    after_sleep=1.5,
                    click=True)

                # 找地图图标，需要防止因点过一次后图片放大造成的无法点击
                if not (loop_match_p_in_w(
                        source_handle=handle,
                        source_root_handle=handle_360,
                        source_range=[0, 0, 950, 600],
                        template=RESOURCE_P["stage"]["EX-{}.png".format(stage_1)],
                        after_sleep=1.5,
                        click=True)):
                    loop_match_p_in_w(
                        source_handle=handle,
                        source_root_handle=handle_360,
                        source_range=[0, 0, 950, 600],
                        template=RESOURCE_P["stage"]["EX-{}_1.png".format(stage_1)],
                        after_sleep=1.5,
                        click=True)
            # 切区
            change_to_region(region_list=[1, 2])

            # 仅限主角色创建关卡
            if self.is_main:
                # 选择关卡
                loop_match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=[0, 0, 950, 600],
                    template=RESOURCE_P["stage"]["{}.png".format(self.stage_info["id"])],
                    after_sleep=0.5,
                    click=True)

                # 设置密码
                click_set_password()

                # 创建队伍
                loop_match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=[0, 0, 950, 600],
                    template=RESOURCE_P["common"]["战斗"]["战斗前_创建房间.png"],
                    after_sleep=0.5,
                    click=True)

        def main_pt():

            # 进入海底旋涡
            self.action_goto_map(map_id=5)

            # 仅限主角色创建关卡
            if self.is_main:

                # 点击进入萌宠神殿
                self.action_top_menu(mode="萌宠神殿")

                # 到最低一层
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=192, y=579)
                time.sleep(0.3)

                # 向右到对应位置
                my_left = int((int(stage_2) - 1) / 15)
                for i in range(my_left):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=297, y=577)
                    time.sleep(0.3)

                # 点击对应层数
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=handle,
                    x=225,
                    y=int(542 - (30.8 * (int(stage_2) - my_left * 15 - 1))))
                time.sleep(0.3)

                # 创建房间
                loop_match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=[0, 0, 950, 600],
                    template=RESOURCE_P["common"]["战斗"]["战斗前_魔塔_创建房间.png"],
                    after_sleep=1,
                    click=True)

        def main_gd():
            # 进入公会副本页
            self.action_bottom_menu(mode="跳转_公会副本")

            # 给一点加载时间
            time.sleep(2)

            # 选关卡 1 2 3
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=handle,
                x={"1": 155, "2": 360, "3": 580}[stage_2],
                y=417)
            time.sleep(2)

            change_to_region(region_list=[3, 11])

            # 仅限主角色创建关卡
            if self.is_main:
                # 创建队伍
                loop_match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=[515, 477, 658, 513],
                    template=RESOURCE_P["common"]["战斗"]["战斗前_创建房间.png"],
                    after_sleep=0.05,
                    click=True)
            else:
                # 识图，寻找需要邀请目标的位置
                result = match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=[0, 0, 950, 600],
                    template=RESOURCE_P["common"]["战斗"]["房间图标_男.png"],
                    match_tolerance=0.95)
                if not result:
                    result = match_p_in_w(
                        source_handle=handle,
                        source_root_handle=handle_360,
                        source_range=[0, 0, 950, 600],
                        template=RESOURCE_P["common"]["战斗"]["房间图标_女.png"],
                        match_tolerance=0.95)
                if result:
                    # 直接进入
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(
                        handle=handle,
                        x=result[0], y=result[1])

                    time.sleep(0.5)

        def main_hh():

            # 进入美味岛并切区
            self.action_goto_map(map_id=1)
            change_to_region(region_list=[1, 11])

            # 仅限主角色创建关卡
            if self.is_main:
                # 进入欢乐假期页面
                self.action_top_menu(mode="欢乐假期")

                # 给一点加载时间
                time.sleep(2)

                # 创建队伍 - 该按钮可能需要修正位置
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=660, y=200)

        def main_wb():

            # 进入美味岛并切区
            self.action_goto_map(map_id=1)
            change_to_region(region_list=[1, 11])

            # 仅限主角色创建关卡
            if self.is_main:
                # 进入欢乐假期页面
                self.action_top_menu(mode="巅峰对决")

                # 给一点加载时间
                time.sleep(2)

                # 创建队伍 - 该按钮可能需要修正位置
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=770, y=560)

        def main_wa():

            # 进入对应地图
            self.action_goto_map(map_id="2")

            # 切区
            change_to_region(region_list=[1, 2])

            # 仅限主角色创建关卡
            if self.is_main:

                # 选择勇士关卡列表
                loop_match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=[155, 385, 225, 450],
                    template=RESOURCE_P["stage"]["WA-0-0.png"],
                    match_tolerance=0.995,
                    after_sleep=1,
                    click=True)

                # 遍历所有关卡图像 查看目前属于哪个
                img = capture_image_png(handle=handle, raw_range=[205, 385, 242, 405], root_handle=handle_360)

                for i in range(1, 24):
                    find = match_p_in_w(
                        source_img=img,
                        template=RESOURCE_P["stage"][f"WA-0-{i}.png"],
                        match_tolerance=0.995,
                    )
                    if find:
                        current_stage = i
                        break
                else:
                    # 没有匹配到任何关卡?!
                    self.print_warning("[界面跳转] 进入勇士本流程出现严重错误! 请联系开发者!")
                    return

                # 根据id 向左 155 175 向右 500 175
                add_index = int(stage_2) - current_stage
                if add_index > 0:
                    for i in range(add_index):
                        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=500, y=175)
                        time.sleep(1.5)
                elif add_index < 0:
                    for i in range(abs(add_index)):
                        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=155, y=175)
                        time.sleep(1.5)

                # 设置密码 这个模式无法设置

                # 创建队伍
                loop_match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=[370, 505, 530, 550],
                    template=RESOURCE_P["common"]["战斗"]["战斗前_创建房间.png"],
                    match_tolerance=0.99,
                    after_sleep=1,
                    click=True)

        def main_cz():

            # 进入对应地图
            my_dict = {"1": "1", "2": "2", "3": "4", "4": "6"}
            self.action_goto_map(map_id=my_dict[stage_2])

            # 切区 三岛+星际
            my_dict = {"1": [3, 11], "2": [1, 2], "3": [1, 2], "4": [1, 2]}
            change_to_region(region_list=my_dict[stage_2])

            # 仅限主角色创建关卡
            if self.is_main:
                # 防止被活动列表遮住
                self.action_change_activity_list(serial_num=2)

                # 选择关卡
                my_dict = {
                    "1": [226, 299],
                    "2": [175, 269],
                    "3": [116, 288],
                    "4": [164, 375]}
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=handle,
                    x=my_dict[stage_2][0],
                    y=my_dict[stage_2][1]
                )
                time.sleep(1)

                # 设置密码
                click_set_password()

                # 创建队伍
                loop_match_p_in_w(
                    source_handle=handle,
                    source_root_handle=handle_360,
                    source_range=[0, 0, 950, 600],
                    template=RESOURCE_P["common"]["战斗"]["战斗前_创建房间.png"],
                    after_sleep=1,
                    click=True)

        def main():
            if stage_0 == "NO":
                main_no()
            elif stage_0 == "MT":
                main_mt()
            elif stage_0 == "CS":
                main_cs()
            elif stage_0 == "OR":
                main_or()
            elif stage_0 == "EX":
                main_ex()
            elif stage_0 == "PT":
                main_pt()
            elif stage_0 == "GD":
                main_gd()
            elif stage_0 == "HH":
                main_hh()
            elif stage_0 == "WB":
                main_wb()
            elif stage_0 == "WA":
                main_wa()
            elif stage_0 == "CZ":
                main_cz()
            else:
                SIGNAL.PRINT_TO_UI.emit(text="跳转关卡失败，请检查关卡代号是否正确", color_level=1)
                SIGNAL.DIALOG.emit("ERROR", "跳转关卡失败! 请检查关卡代号是否正确")
                SIGNAL.END.emit()

        return main()
