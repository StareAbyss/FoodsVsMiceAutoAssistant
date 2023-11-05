from time import sleep, time

from function.common.bg_keyboard import key_down_up
from function.common.bg_mouse import mouse_left_click, mouse_move_to
from function.common.bg_screenshot_and_compare import find_ps_in_w, find_p_in_w
from function.script.service.in_battle.round_of_battle_calculation_arrange import calculation_cell_all_card
from function.tools.create_battle_coordinates import create_battle_coordinates


class RoundOfBattle:

    def __init__(self,
                 handle, zoom, player, is_use_key, is_auto_battle, is_auto_collect,
                 path_p_common, stage_info, battle_plan, is_group):

        # 其他手动内部参数
        self.click_interval = 0.025
        self.click_sleep = 0.025
        self.battle_card, self.battle_cell = create_battle_coordinates(zoom)  # 计算关卡内的卡牌 和 格子位置

        # FAA主类中调用函数获取 - 生成类时获取
        self.handle = handle
        self.zoom = zoom
        self.player = player
        self.is_use_key = is_use_key
        self.is_auto_battle = is_auto_battle
        self.is_auto_collect = is_auto_collect
        self.path_p_common = path_p_common

        # FAA主类中调用函数获取 - 战斗前生成
        self.stage_info = stage_info
        self.battle_plan = battle_plan
        self.is_group = is_group

    """ Layer0 - 在FAA类中复写 以直接被调用 """

    def action_battle_normal(self, battle_mode: int, task_card: str, list_ban_card: list):
        """
        战斗中放卡的函数
        Args:
            :param battle_mode: 0 常规模式 1 试验模式
            :param task_card:
            :param list_ban_card:
        """

        list_cell_all, list_shovel = calculation_cell_all_card(stage_info=self.stage_info,
                                                               is_group=self.is_group,
                                                               player=self.player,
                                                               battle_plan=self.battle_plan["card"],
                                                               task_card=task_card,
                                                               list_ban_card=list_ban_card)
        # 放人物
        for i in self.battle_plan["player"]:
            self.use_player(i)

        # 铲自带的卡
        if self.player == "1P":
            self.use_shovel(position=list_shovel)

        # 战斗循环
        if battle_mode == 0:
            # 0 多线程遍历模式 布阵慢 补阵快 性能开销略大 是遍历模式的优化
            self.use_card_loop_0(list_cell_all=list_cell_all)
        elif battle_mode == 1:
            # 1 备用拓展
            self.use_card_loop_1(list_cell_all=list_cell_all)
        else:
            print(list_cell_all, list_shovel)
            print("不战斗 用于测试战斗数组的计算")

    def action_battle_skill(self):
        # 放人
        self.use_player("5-4")

        # 计算目标位置 1-14
        cell_list = []
        for i in range(2):
            for j in range(9):
                cell_list.append(str(j + 1) + "-" + str(i + 2))

        # 常规放卡
        for k in range(13):
            self.use_card_once(num_card=k + 1, num_cell=cell_list[k], click_space=False)
            sleep(0.07)

        # 叠加放卡
        # for k in range(3):
        #     msdzls.battle_use_card(k*2 + 1 + 8, cell_list[k + 8], click_space=False)
        #     sleep(0.15)
        #     msdzls.battle_use_card(k*2 + 2 + 8, cell_list[k + 8], click_space=False)
        #     sleep(0.05)

        # 退出关卡
        mouse_left_click(handle=self.handle,
                         x=int(920 * self.zoom),
                         y=int(580 * self.zoom),
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

        mouse_left_click(handle=self.handle,
                         x=int(920 * self.zoom),
                         y=int(580 * self.zoom),
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

        # 确定退出
        mouse_left_click(handle=self.handle,
                         x=int(449 * self.zoom),
                         y=int(382 * self.zoom),
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

    """ Layer1 - 被Layer0调用 """

    def use_player(self, num_cell):
        mouse_left_click(handle=self.handle,
                         x=self.battle_cell[num_cell][0],
                         y=self.battle_cell[num_cell][1],
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

    def use_shovel(self, position: list = None):
        """
        用铲子
        Args:
            position: 放哪些格子
        """
        if position is None:
            position = []

        for target in position:
            key_down_up(handle=self.handle, key="1")
            mouse_left_click(handle=self.handle,
                             x=self.battle_cell[target][0],
                             y=self.battle_cell[target][1],
                             interval_time=self.click_interval,
                             sleep_time=self.click_sleep)

    def use_card_loop_0(self, list_cell_all):
        """循环方式 每一个卡都先在其对应的全部的位置放一次,再放下一张(每轮开始位置+1)"""
        # 计算一轮最长时间(防止空转)
        max_len_position_in_opt = 0
        for i in list_cell_all:
            max_len_position_in_opt = max(max_len_position_in_opt, len(i["location"]))
        round_max_time = self.click_interval * max_len_position_in_opt + 7.3

        end_flag = False  # 用flag值来停止循环
        check_invite = 3.0  # 检测间隔(根据时间)
        check_last_one_time = time()  # 记录上一次检测的时间

        while True:
            time_round_begin = time()  # 每一轮开始的时间
            for i in range(len(list_cell_all)):  # 遍历每一张卡
                if self.is_auto_battle:  # 启动了自动战斗
                    # 点击 选中卡片
                    mouse_left_click(handle=self.handle,
                                     x=self.battle_card[list_cell_all[i]["id"]][0],
                                     y=self.battle_card[list_cell_all[i]["id"]][1],
                                     interval_time=self.click_interval,
                                     sleep_time=self.click_sleep)
                    if list_cell_all[i]["ergodic"]:
                        # 遍历该卡每一个可以放的位置
                        for j in list_cell_all[i]["location"]:
                            self.use_card_somewhere(j=j)
                    else:
                        # 只放一下
                        j = list_cell_all[i]["location"][0]
                        self.use_card_somewhere(j=j)
                    self.click_space()  # 放卡后点一下
                # 每放完一轮卡片 根据设定间隔 检测一下
                if time() - check_last_one_time > check_invite:
                    # 更新上次检测时间 + 更新flag + 中止休息循环
                    check_last_one_time = time()
                    if self.check_end():
                        end_flag = True
                        break

            if end_flag:
                break  # 根据flag 跳出外层循环

            # 放完一轮卡后 在位置数组里 将每个卡的 第一个位置移到最后
            for i in range(len(list_cell_all)):
                if list_cell_all[i]["queue"]:
                    list_cell_all[i]["location"].append(list_cell_all[i]["location"][0])
                    list_cell_all[i]["location"].remove(list_cell_all[i]["location"][0])

            self.use_weapon_skill()  # 武器技能
            self.auto_collect()  # 自动收集

            # 一轮不到7s+点7*9个位置需要的时间, 休息到该时间, 期间每[check_invite]秒检测一次
            time_spend_a_round = time() - time_round_begin
            if time_spend_a_round < round_max_time:
                for i in range(int((round_max_time - time_spend_a_round) // check_invite)):
                    if time() - check_last_one_time > check_invite:
                        # 更新上次检测时间 + 更新flag + 中止休息循环
                        check_last_one_time = time()
                        if self.check_end():
                            end_flag = True
                            break
                    sleep(check_invite)
                sleep((round_max_time - time_spend_a_round) % check_invite)  # 补充余数
            else:
                # 一轮放卡循环够长 补一次检测
                if time() - check_last_one_time > check_invite:
                    # 更新上次检测时间 + 更新flag + 中止休息循环
                    check_last_one_time = time()
                    if self.check_end():
                        break

            if end_flag:
                break  # 根据flag 跳出外层循环

    def use_card_loop_1(self, list_cell_all):
        """循环方式 每一个卡都先在其对应的全部的位置放一次,再放下一张(每轮开始位置+1)"""
        print("测试方法, 啥都没有")
        print(list_cell_all)
        print(self.handle)
        return False

    def use_card_once(self, num_card: int, num_cell: str, click_space=True):
        """
        Args:
            num_card: 使用的卡片的序号
            num_cell: 使用的卡片对应的格子 从左上开始 "1-1" to "9-7"
            click_space:  是否点一下空白地区防卡住
        """
        # 注 美食大战老鼠中 放卡动作 需要按下一下 然后拖动 然后按下并松开 才能完成 整个动作
        mouse_left_click(handle=self.handle,
                         x=self.battle_card[num_card][0],
                         y=self.battle_card[num_card][1],
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

        mouse_left_click(handle=self.handle,
                         x=self.battle_cell[num_cell][0],
                         y=self.battle_cell[num_cell][1],
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

        # 点一下空白
        if click_space:
            self.click_space()

    """ Layer2 - 被Layer1调用 """

    def click_space(self):
        """战斗中点空白"""
        mouse_move_to(handle=self.handle,
                      x=200,
                      y=350)
        mouse_left_click(handle=self.handle,
                         x=200,
                         y=350,
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

    def use_card_somewhere(self, j):
        """
        防误触的使用一张卡
        :param j: 卡片坐标str 例如 "1-3"
        """

        def use_key():
            if self.is_use_key:
                if find_p_in_w(handle=self.handle,
                               target_path=self.path_p_common + "\\battle_next_need.png"):
                    mouse_left_click(handle=self.handle,
                                     x=int(427 * self.zoom),
                                     y=int(360 * self.zoom),
                                     interval_time=self.click_interval,
                                     sleep_time=self.click_sleep)

        # 防止误触
        if j == "4-4" or j == "4-5" or j == "5-4" or j == "5-4":
            use_key()
        # 点击 放下卡片
        mouse_left_click(handle=self.handle,
                         x=self.battle_cell[j][0],
                         y=self.battle_cell[j][1],
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

    def use_weapon_skill(self):
        mouse_left_click(handle=self.handle,
                         x=int(23 * self.zoom),
                         y=int(200 * self.zoom),
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)
        mouse_left_click(handle=self.handle,
                         x=int(23 * self.zoom),
                         y=int(250 * self.zoom),
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)
        mouse_left_click(handle=self.handle,
                         x=int(23 * self.zoom),
                         y=int(297 * self.zoom),
                         interval_time=self.click_interval,
                         sleep_time=self.click_sleep)

    def check_end(self):
        # 找到战利品字样(被黑色透明物遮挡,会看不到)
        return find_ps_in_w(handle=self.handle,
                            target_opts=[
                                {
                                    "target_path": self.path_p_common + "\\battle_end_1_loot.png",
                                    "tolerance": 0.999
                                },
                                {
                                    "target_path": self.path_p_common + "\\battle_end_2_loot.png",
                                    "tolerance": 0.999
                                },
                                {
                                    "target_path": self.path_p_common + "\\battle_end_3_summarize.png",
                                    "tolerance": 0.999
                                },
                                {
                                    "target_path": self.path_p_common + "\\battle_end_4_chest.png",
                                    "tolerance": 0.999
                                },
                                {
                                    "target_path": self.path_p_common + "\\battle_before_ready_check_start.png",
                                    "tolerance": 0.999
                                }
                            ],
                            return_mode="or")

    def auto_collect(self):
        if self.is_auto_collect:
            coordinates = ["1-1", "2-1", "3-1", "4-1", "5-1", "6-1", "7-1", "8-1", "9-1",
                           "1-2", "2-2", "3-2", "4-2", "5-2", "6-2", "7-2", "8-2", "9-2",
                           "1-3", "2-3", "3-3", "4-3", "5-3", "6-3", "7-3", "8-3", "9-3",
                           "1-4", "2-4", "3-4", "4-4", "5-4", "6-4", "7-4", "8-4", "9-4",
                           "1-5", "2-5", "3-5", "4-5", "5-5", "6-5", "7-5", "8-5", "9-5",
                           "1-6", "2-6", "3-6", "4-6", "5-6", "6-6", "7-6", "8-6", "9-6",
                           "1-7", "2-7", "3-7", "4-7", "5-7", "6-7", "7-7", "8-7", "9-7"]

            for coordinate in coordinates:
                mouse_move_to(handle=self.handle,
                              x=self.battle_cell[coordinate][0],
                              y=self.battle_cell[coordinate][1])
                sleep(self.click_sleep)

    """ 暂时废弃 """


