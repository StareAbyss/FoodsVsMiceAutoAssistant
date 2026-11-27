import datetime
import glob
import json
import os
import time
from typing import TYPE_CHECKING

import cv2

from function.common.bg_img_match import loop_match_p_in_w, match_p_in_w
from function.common.bg_img_screenshot import capture_image_png
from function.core.qmw_task_plan_editor import init_db
from function.globals import SIGNAL
from function.globals.g_resources import RESOURCE_P
from function.globals.get_paths import PATHS
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.split_task import detect_horizontal_edges, load_tasks_from_db_and_create_puzzle, split_edge

if TYPE_CHECKING:
    from function.core.faa.faa_mix import FAA


class FAAActionReceiveQuestRewards:
    """
    领取各种任务奖励的动作
    """

    @staticmethod
    def _quest_reward_click_result(count: int) -> str:
        """按发出的领取点击汇报可多次领奖的任务。"""
        return f"已点击领取 {count} 项奖励"

    def _click_quest_reward_match(self: "FAA", source_range, template, match_tolerance=0.95) -> bool:
        """从当前窗口截图定位目标，找到后将点击加入队列。"""
        _, point = match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=source_range,
            template=template,
            match_tolerance=match_tolerance,
        )
        if point is None:
            return False
        T_ACTION_QUEUE_TIMER.add_click_to_queue(
            handle=self.handle, x=source_range[0] + point[0], y=source_range[1] + point[1],
        )
        return True

    def action_receive_quest_rewards_normal(self: "FAA"):
        """领取普通任务奖励"""

        player = self.player

        claimed = 0

        def scan_one_page(first_time):
            """扫描一页"""
            nonlocal claimed

            # 最大尝试次数
            max_attempts = 30

            # 循环遍历点击完成
            for try_count in range(max_attempts):
                find = self._click_quest_reward_match(
                    source_range=[335, 120, 420, 545],
                    template=RESOURCE_P["common"]["任务_完成.png"],
                )
                if find:
                    # 等右侧详情切换到刚选中的任务，再点击领取。
                    time.sleep(0.5)
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=643, y=534)
                    claimed += 1
                    time.sleep(0.2)
                else:
                    break

            # 如果达到了最大尝试次数
            if try_count == max_attempts - 1 and first_time:
                first_time = False
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                SIGNAL.DIALOG.emit(
                    title="背包满了！(╬◣д◢)",
                    text=f"{player}P因背包爆满, 导致 [领取普通任务奖励] 失败!\n"
                    f"出错时间:{current_time}, 尝试次数:{max_attempts}")
            return first_time

        if not self.action_bottom_menu(mode="任务"):
            return "未找到普通任务入口"

        # 复位滑块
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=413, y=155)
        time.sleep(0.25)
        first_time=True
        for i in range(8):

            # 不是第一次滑块向下移动3次
            if i != 0:
                for j in range(3):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=413, y=524)
                    time.sleep(0.05)

            first_time=scan_one_page(first_time)

        self.action_exit(mode="普通红叉")
        return self._quest_reward_click_result(claimed)

    def action_get_task_menus_normal(self: "FAA"):
        """扫描普通任务图片"""

        player = self.player

        def scan_one_page():
            """扫描一页"""

            image = capture_image_png(
                handle=self.handle,
                raw_range=[100, 128, 350, 532],
                root_handle=self.handle_360)
            if image is not None:
                detect_horizontal_edges(image)
            else:
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                SIGNAL.DIALOG.emit(
                    title="未截图成功！！！",
                    text=f"{player}P图片不存在, 导致 [扫描任务列表] 失败!\n"
                    f"出错时间:{current_time}")

        def scan_task_description(file_count, now_count):

            for try_count in range(now_count, file_count + 1):
                find = loop_match_p_in_w(
                    source_handle=self.handle,
                    source_root_handle=self.handle_360,
                    source_range=[100, 128, 350, 532],
                    template=os.path.join(PATHS["image"]["task"]["chaos"], f"{try_count}.png"),
                    match_tolerance=0.99,
                    match_failed_check=1,
                    after_sleep=0.5,
                    click=True)
                if find:
                    # 截图任务描述
                    image = capture_image_png(
                        handle=self.handle,
                        raw_range=[432, 93, 850, 360],
                        root_handle=self.handle_360)
                    output_path = os.path.join(PATHS["image"]["task"]["desc"], f"{try_count}.png")
                    cv2.imwrite(output_path, image)
                    time.sleep(0.2)
                else:
                    return try_count
            return file_count

        self.action_bottom_menu(mode="任务")
        target_dir = PATHS["image"]["task"]["chaos"]
        os.makedirs(target_dir, exist_ok=True)  # 确保目录存在
        os.makedirs(PATHS["image"]["task"]["desc"], exist_ok=True)  # 确保目录存在
        existing_files = glob.glob(os.path.join(target_dir, "*.png"))
        old_count = len(existing_files)
        # 复位滑块
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=413, y=155)
        time.sleep(0.25)

        for i in range(12):

            # 改为滑动2次，滑动12轮，避免漏掉任务
            if i != 0:
                for j in range(2):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=413, y=524)
                    time.sleep(0.05)
            time.sleep(0.25)
            scan_one_page()

        # 复位滑块
        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=413, y=155)
        time.sleep(0.25)

        existing_files = glob.glob(os.path.join(target_dir, "*.png"))
        file_count = len(existing_files)
        if file_count > old_count:
            now_count = old_count + 1
        else:
            now_count = old_count
        for i in range(12):

            # 改为滑动2次，滑动12轮，避免漏掉任务
            if i != 0:
                for j in range(2):
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=413, y=524)
                    time.sleep(0.05)
            time.sleep(0.25)
            now_count = scan_task_description(file_count, now_count)

        self.action_exit(mode="普通红叉")

    def action_battle_task_menus_normal(self: "FAA"):
        """执行先扫描存在的任务，后根据任务刷关刷关"""

        def _get_all_tasks_from_db(db_conn):
            """从数据库获取所有任务信息"""
            cursor = db_conn.cursor()
            cursor.execute("SELECT id, task_name, task_type, parameters, stage_param FROM tasks")
            return cursor.fetchall()

        # 1. 从数据库读取拼图
        db_conn = init_db(os.path.join(PATHS["db"], 'tasks.db'))
        task_battle_quest = []
        try:
            # 2. 加载任务数据并创建拼图
            puzzle_image = load_tasks_from_db_and_create_puzzle(db_conn)
            tasks = _get_all_tasks_from_db(db_conn)
            db_conn.close()

            # 3. 扫描任务界面
            self.action_bottom_menu(mode="任务")

            # 复位滑块
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=413, y=155)
            time.sleep(0.25)

            # 滑动扫描
            for i in range(12):
                if i != 0:
                    for j in range(2):
                        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=413, y=524)
                        time.sleep(0.05)
                time.sleep(0.25)

                # 执行任务扫描
                self._scan_and_process_tasks(
                    puzzle_image=puzzle_image,
                    tasks=tasks,
                    task_battle_quest=task_battle_quest
                )

        finally:
            # 退出任务界面
            self.action_exit(mode="普通红叉")
            quest_list = []
            task_names = []
            goto_information = False
            for task in task_battle_quest:
                task_id, task_name, task_type, parameters, stage_param = task
                parameters = json.loads(parameters)
                if task_type == "刷关":
                    if parameters.get("skip", False):
                        self.print_debug(text=f"[扫描普通任务]跳过任务{task_name}")
                        continue
                    if parameters.get("is_two_players", False):
                        player = [2, 1]
                    elif parameters.get("is_single_player", False):
                        player = [self.player]
                    else:
                        player = [2, 1]  # 没说单人的一律默认双人
                    quest_item = {
                        "stage_id": stage_param or "NO-1-1",  # 默认参数曲奇岛
                        "player": player,
                        "need_key": parameters.get("use_key", True),  # 默认使用钥匙
                        "max_times": parameters.get("times", 1),  # 刷关次数
                        "dict_exit": {
                            "other_time_player_a": [],
                            "other_time_player_b": [],
                            "last_time_player_a": ['竞技岛'],
                            "last_time_player_b": ['竞技岛']
                        },
                        "global_plan_active": parameters.get("use_global_plan", True),  # 默认使用全局方案
                        "deck": parameters.get("deck", 0) or 0,  # 卡组选择
                        "battle_plan_1p": parameters.get("battle_plan_1p") or "00000000-0000-0000-0000-000000000000",  # battle_plan_1p 从参数或默认值获取
                        "battle_plan_2p": parameters.get("battle_plan_2p") or "00000000-0000-0000-0000-000000000001",  # battle_plan_2p 从参数或默认值获取
                        "battle_plan_tweak": parameters.get("battle_plan_tweak") or "00000000-0000-0000-0000-000000000001",  # 微调方案
                        "max_card_num": None if parameters.get("banned_card_count", 0) == 0 else parameters.get("banned_card_count", None)  # 限制卡片最大数量
                    }
                    if parameters.get("card_name") not in (None, ''):
                        quest_item["quest_card"] = parameters.get("card_name") + "-0"  # 携带卡片
                    if parameters.get("banned_card") not in (None, ''):
                        quest_item["ban_card_list"] = parameters.get("banned_card").split(',')  # 禁用卡片
                    quest_list.append(quest_item)
                    task_names.append(task_name)
                elif task_type == "情报":
                    goto_information = True
            if goto_information:
                self.action_goto_information_island_and_click()
            # print(f"即将刷取{quest_list}")
            return [quest_list, task_names]

    def _scan_and_process_tasks(self, puzzle_image, tasks, task_battle_quest):
        """扫描并处理单页任务"""
        # 获取任务列表区域截图
        task_list_image = capture_image_png(
            handle=self.handle,
            raw_range=[100, 128, 350, 532],  # 原始任务列表区域
            root_handle=self.handle_360
        )

        if task_list_image is None:
            # print("任务列表截图失败")
            return task_battle_quest
        task_images = split_edge(task_list_image)  # 注意：需要调整函数返回值以支持返回分割后的图像列表
        # 处理每个任务项
        for task_index, task_image in enumerate(task_images):
            status_code, point = match_p_in_w(
                template=task_image,
                source_img=puzzle_image,
                match_tolerance=0.985,
                test_print=True
            )

            if status_code == 2:
                # 使用分割索引作为数据库索引
                db_index = point[1] // 29

                # 验证索引有效性
                if 0 <= db_index < len(tasks):
                    task_id, task_name, task_type, parameters, stage_param = tasks[db_index]
                    task_battle_quest.append(tasks[db_index])

                    # 打印完整任务信息
                    task_info = {
                        "id": task_id,
                        "名称": task_name,
                        "类型": task_type,
                        "参数": json.loads(parameters) if parameters else {},
                        "关卡": stage_param
                    }

                    # print(f"数据库索引{db_index}对应任务信息：{task_info}")

        return task_battle_quest

    def action_receive_quest_rewards_guild(self: "FAA"):

        # 跳转到任务界面
        if not self.action_bottom_menu(mode="跳转_公会任务"):
            return "未找到公会任务入口"
        claimed = 0
        found_completed = False

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
                match_failed_check=5,  # 美食大赛任务完成动画可能遮住任务列表约 4 秒。
                after_sleep=0.5,
                click=True,
            )
            if not result:
                break
            found_completed = True

            # 等选中的任务详情显示后，重新截图定位领取按钮。
            if loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["quest_guild"]["gather.png"],
                match_tolerance=0.99,
                match_failed_check=2,
                after_sleep=2,
                click=True,
            ):
                claimed += 1

        # 如果达到了最大尝试次数
        if try_count == max_attempts - 1:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            SIGNAL.DIALOG.emit(
                title="背包满了！(╬◣д◢)",
                text=f"{self.player}P因背包爆满, 导致 [领取公会任务奖励] 失败!\n"
                f"出错时间:{current_time}, 尝试次数:{max_attempts}")

        # 退出任务界面
        self.action_exit(mode="普通红叉")
        if found_completed and not claimed:
            return "找到已完成任务，未识别到领取按钮"
        return self._quest_reward_click_result(claimed)

    def action_receive_quest_rewards_spouse(self: "FAA"):

        # 跳转到任务界面
        if not self.action_bottom_menu(mode="跳转_情侣任务"):
            return "未找到情侣任务入口"
        claimed = 0

        # 最大尝试次数
        max_attempts = 10

        # 循环遍历点击完成
        for try_count in range(max_attempts):

            result = loop_match_p_in_w(
                source_handle=self.handle,
                source_root_handle=self.handle_360,
                source_range=[0, 0, 950, 600],
                template=RESOURCE_P["quest_spouse"]["completed.png"],
                match_tolerance=0.99,
                click=True,
                match_failed_check=2,
                after_sleep=2)  # 2s 完成任务有显眼动画)

            if not result:
                break
            claimed += 1

        # 如果达到了最大尝试次数
        if try_count == max_attempts - 1:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            SIGNAL.DIALOG.emit(
                title="背包满了！(╬◣д◢)",
                text=f"{self.player}P因背包爆满, 导致 [领取情侣任务奖励] 失败!\n"
                f"出错时间:{current_time}, 尝试次数:{max_attempts}")

        # 点两下右下角的领取
        for _ in range(2):
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=795, y=525)
            time.sleep(0.1)

        # 退出任务界面
        self.action_exit(mode="普通红叉")
        return self._quest_reward_click_result(claimed)

    def action_receive_quest_rewards_offer_reward(self: "FAA"):
        """
        领取悬赏任务奖励
        """

        # 进入X年活动界面
        if not self.action_top_menu(mode="X年活动"):
            return "未找到悬赏任务入口"
        claimed = 0

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
            claimed += 1

        # 如果达到了最大尝试次数
        if try_count == max_attempts - 1:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            SIGNAL.DIALOG.emit(
                title="背包满了！(╬◣д◢)",
                text=f"{self.player}P因背包爆满, 导致 [领取悬赏任务奖励]失败!\n"
                f"出错时间:{current_time}, 尝试次数:{max_attempts}")

        # 退出任务界面
        self.action_exit(mode="关闭悬赏窗口")
        return self._quest_reward_click_result(claimed)

    def action_receive_quest_rewards_food_competition(self: "FAA"):

        claimed = 0

        # 进入美食大赛界面
        find = self.action_top_menu(mode="美食大赛")

        if find:

            for click_y in [359, 390, 420, 450, 480, 510, 540, 570]:

                # 先移动一次位置
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=536, y=click_y)
                time.sleep(0.2)

                # 最大尝试次数
                max_attempts = 10

                # 循环遍历点击完成
                for try_count in range(max_attempts):
                    find = loop_match_p_in_w(
                        source_handle=self.handle,
                        source_root_handle=self.handle_360,
                        source_range=[0, 0, 950, 600],
                        template=RESOURCE_P["common"]["美食大赛_领取.png"],
                        match_tolerance=0.95,
                        match_failed_check=0.2,
                        after_sleep=0.05,
                        click=True)
                    if find:
                        # 领取升级有动画
                        self.print_debug(text="[收取奖励] [美食大赛] 完成1个任务")
                        time.sleep(6)
                        claimed += 1
                    else:
                        break

                # 如果达到了最大尝试次数
                if try_count == max_attempts - 1:
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    SIGNAL.DIALOG.emit(
                        title="背包满了！(╬◣д◢)",
                        text=f"{self.player}P因背包爆满, 导致 [领取美食大赛积分]失败!\n"
                             f"出错时间:{current_time}, 尝试次数:{max_attempts}")

            # 退出美食大赛界面
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=888, y=53)
            time.sleep(0.5)

        else:
            self.print_warning(text="[领取奖励] [美食大赛] 未打开界面, 可能大赛未刷新")
            return "未找到美食大赛入口"

        if not claimed:
            self.print_debug(text="[领取奖励] [美食大赛] 未完成任意任务")
        return self._quest_reward_click_result(claimed)

    def action_receive_quest_rewards_monopoly(self: "FAA"):
        """按页领取大富翁骰子奖励，统计已点击的领取项。"""
        if not self.action_top_menu(mode="大富翁"):
            return "未找到大富翁入口"

        templates = RESOURCE_P["common"]["大富翁奖励"]
        source = {"source_handle": self.handle, "source_root_handle": self.handle_360}

        def wait_for_page(page):
            """等待页码更新后再处理奖励按钮。"""
            return loop_match_p_in_w(
                **source, source_range=[806, 437, 867, 477],
                template=templates[f"第{page}页.png"], match_tolerance=0.99,
                match_failed_check=2, click=False,
            )

        claimed = 0
        # 活动入口的点击回执早于界面加载。页码出现后才允许操作奖励栏。
        if not wait_for_page(1):
            return "未找到大富翁奖励第一页"

        try:
            for page, row_count in enumerate((6, 6, 2), start=1):
                if page > 1:
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=875, y=457)
                    if not wait_for_page(page):
                        return f"{self._quest_reward_click_result(claimed)}，未能翻到第 {page} 页"

                for row in range(row_count):
                    y = 167 + 50 * row
                    button = {
                        **source, "source_range": [734, y - 23, 797, y + 23],
                        "template": templates["领取_灰色.png"], "match_tolerance": 0.98,
                    }
                    status, _ = match_p_in_w(**button)
                    if status != 1:
                        continue

                    # 当前页的任务行确实存在；灰色按钮表示不可领。
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=765, y=y)
                    claimed += 1
        finally:
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=932, y=16)
            time.sleep(0.5)

        return self._quest_reward_click_result(claimed)

    def action_goto_information_island_and_click(self: "FAA"):

        # 进入界面
        find = self.action_goto_map(map_id=1)

        if find:
            while True:
                find_island = loop_match_p_in_w(
                    source_handle=self.handle,
                    source_root_handle=self.handle_360,
                    source_range=[709, 72, 764, 122],
                    template=os.path.join(PATHS["image"]["stage"], 'inforation_island.png'),
                    match_tolerance=0.95,
                    match_failed_check=1,
                    after_sleep=0.5,
                    click=True)
                if find_island:
                    point = [54, 110, 450, 540]
                    grid_config = {
                        4: (4, 4),  # i=4时4x4网格
                        2: (3, 2),  # i=2时2x3网格
                        3: (3, 3)  # i=3时3x3网格
                    }

                    for i in [4, 2, 3]:
                        rows, cols = grid_config[i]
                        # 计算网格步长
                        x_step = (point[2] - point[0]) / cols
                        y_step = (point[3] - point[1]) / rows
                        if i == 4:
                            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=110, y=80)
                        elif i == 2:
                            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=250, y=80)
                        elif i == 3:
                            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=400, y=80)
                        time.sleep(0.05)
                        # 复位滑块
                        T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=460, y=155)
                        time.sleep(0.25)

                        for k in range(12):
                            if k != 0:
                                for j in range(2):
                                    for col in range(cols):
                                        for row in range(rows):
                                            x = point[0] + x_step / 2 + x_step * col
                                            y = point[1] + y_step / 2 + y_step * row
                                            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                                                handle=self.handle,
                                                x=int(x),
                                                y=int(y)
                                            )
                                            time.sleep(0.05)
                                    T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=460, y=530)
                                    time.sleep(0.05)

                            time.sleep(0.25)
                    # 退出任务界面
                    self.action_exit(mode="普通红叉")
                    break
                time.sleep(1)
                # 防顶栏活动遮挡
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=784, y=28)

    def action_receive_quest_rewards_camp(self: "FAA"):

        # 进入界面
        find = self.action_goto_map(map_id=10)

        if find:
            for _ in range(10):
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=175, y=325)
                time.sleep(0.2)
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=175, y=365)
                time.sleep(0.2)
            return "已执行营地领取"
        return "未能进入营地"

    def action_receive_quest_rewards_magic_tower(self: "FAA") -> str:
        """领取双人魔塔的每周威望排名奖励。"""
        if not self.action_goto_magic_tower(mode="2"):
            return "未能进入双人魔塔"

        clicked = loop_match_p_in_w(
            source_handle=self.handle,
            source_root_handle=self.handle_360,
            source_range=[873, 447, 938, 492],
            template=RESOURCE_P["common"]["魔塔_威望领取.png"],
            match_failed_check=2,
            after_sleep=0.8,
            click=True,
        )
        self.action_exit(mode="普通红叉", raw_range=[906, 12, 950, 54])
        return "已点击领取" if clicked else "未找到可领取项"

    def action_receive_quest_rewards(self: "FAA", mode) -> None:
        """
        领取任务奖励, 从任意地图界面开始, 从任意地图界面结束
        :param mode: "普通任务" "公会任务" "情侣任务" "悬赏任务" "美食大赛" "大富翁" "营地任务" "魔塔"
        :return: None
        """

        handlers = {
            "普通任务": self.action_receive_quest_rewards_normal,
            "公会任务": self.action_receive_quest_rewards_guild,
            "情侣任务": self.action_receive_quest_rewards_spouse,
            "悬赏任务": self.action_receive_quest_rewards_offer_reward,
            "美食大赛": self.action_receive_quest_rewards_food_competition,
            "大富翁": self.action_receive_quest_rewards_monopoly,
            "营地任务": self.action_receive_quest_rewards_camp,
            "魔塔": self.action_receive_quest_rewards_magic_tower,
        }

        if action := handlers.get(mode):
            result = action()
            if SIGNAL.PRINT_TO_UI is not None:
                SIGNAL.PRINT_TO_UI.emit(text=f"[领取奖励] [{mode}] [{self.player}P] {result}")

    def action_scan_task_type(self: "FAA", mode):
        """
        扫描任务列表
        :param mode
        :return quest
        """
        pack = None
        self.print_debug(text="[领取奖励] [{}] 开始".format(mode))
        if mode == "扫描":
            self.action_get_task_menus_normal()
        elif mode == "刷关":
            pack = self.action_battle_task_menus_normal()

        self.print_debug(text="[领取奖励] [{}] 结束".format(mode))
        return pack
