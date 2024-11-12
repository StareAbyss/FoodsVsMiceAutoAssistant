import copy
import time

from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER


def loop_battle(self):
    """
    (循环)放卡函数
    旧版战斗循环 已被新版的战斗方案(v3)彻底取代
    :return: None
    """

    def use_card_loop_0():
        """
           !!! Important !!!
           该函数是本项目的精髓, 性能开销最大的函数, 为了性能, [可读性]和 [低耦合]已牺牲...
           循环方式:
           每一个卡都先在其对应的全部的位置放一次,再放下一张(每轮开始位置+1)，根据遍历或队列，有不同的效果
           2024/4/22 已废弃 被战斗方案v3取代
       """

        # 以防万一 深拷贝一下 以免对其造成更改
        card_plan = copy.deepcopy(self.battle_plan_card)

        def use_card_once(a_card):
            if self.is_auto_battle:  # 启动了自动战斗

                # 点击 选中卡片
                T_ACTION_QUEUE_TIMER.add_click_to_queue(
                    handle=self.handle,
                    x=a_card["location_from"][0],
                    y=a_card["location_from"][1])
                time.sleep(click_sleep)

                if a_card["ergodic"]:
                    # 遍历模式: True 遍历该卡每一个可以放的位置
                    my_len = len(a_card["location"])
                else:
                    # 遍历模式: False 只放第一张
                    my_len = 1

                for j in range(my_len):
                    # 防止误触
                    # if a_card["location"][j] in self.faa_battle.warning_cell:
                    #     self.faa_battle.use_key(mode=1)

                    # 点击 放下卡片
                    T_ACTION_QUEUE_TIMER.add_click_to_queue(
                        handle=self.handle,
                        x=a_card["location_to"][j][0],
                        y=a_card["location_to"][j][1])
                    time.sleep(click_sleep)

                """放卡后点一下空白"""
                T_ACTION_QUEUE_TIMER.add_move_to_queue(handle=self.handle, x=200, y=350)
                T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=self.handle, x=200, y=350)
                time.sleep(click_sleep)

        # 读取点击相关部分参数
        click_interval = self.faa_battle.click_interval
        click_sleep = self.faa_battle.click_sleep

        # 战斗中, [检测战斗结束]和[检测继续战斗]的时间间隔, 不建议大于1s(因为检测只在放完一张卡后完成 遍历会耗时)
        check_invite = 1.0

        # 计算一轮最长时间(防止一轮太短, 导致某些卡cd转不好就尝试点它也就是空转)
        max_len_position_in_opt = 0
        for i in card_plan:
            max_len_position_in_opt = max(max_len_position_in_opt, len(i["location_to"]))
        round_max_time = (click_interval + click_sleep) * max_len_position_in_opt + 7.3

        end_flag = False  # 用flag值来停止循环
        check_last_one_time = time.time()  # 记录上一次检测的时间

        """战斗主循环"""
        while True:

            time_round_begin = time.time()  # 每一轮开始的时间

            for card in card_plan:
                """遍历每一张卡"""

                use_card_once(a_card=card)

                """每放完一张卡片的所有位置 检查时间设定间隔 检测战斗间隔"""
                if time.time() - check_last_one_time > check_invite:

                    # 更新上次检测时间 + 更新flag + 中止休息循环
                    check_last_one_time = time.time()
                    if self.faa_battle.use_key_and_check_end():
                        end_flag = True
                        break

            if end_flag:
                break  # 根据flag 跳出外层循环

            # 放完一轮卡后 在位置数组里 将每个卡的 第一个位置移到最后
            for i in range(len(card_plan)):
                if card_plan[i]["queue"]:
                    card_plan[i]["location"].append(card_plan[i]["location"][0])
                    card_plan[i]["location"].remove(card_plan[i]["location"][0])
                    card_plan[i]["location_to"].append(card_plan[i]["location_to"][0])
                    card_plan[i]["location_to"].remove(card_plan[i]["location_to"][0])

            # 武器技能 + 自动收集
            self.faa_battle.use_weapon_skill()
            self.faa_battle.auto_pickup()

            """一轮不到7s+点7*9个位置需要的时间, 休息到该时间, 期间每[check_invite]秒检测一次"""
            time_spend_a_round = time.time() - time_round_begin
            if time_spend_a_round < round_max_time:
                for i in range(int((round_max_time - time_spend_a_round) // check_invite)):

                    """检查时间设定间隔 检测战斗间隔"""
                    if time.time() - check_last_one_time > check_invite:

                        # 测试用时
                        # print("[{}][休息期战斗结束检测] {:.2f}s".format(player,time() - check_last_one_time))

                        # 更新上次检测时间 + 更新flag + 中止休息循环
                        check_last_one_time = time.time()
                        if self.faa_battle.use_key_and_check_end():
                            end_flag = True
                            break
                    time.sleep(check_invite)
                time.sleep((round_max_time - time_spend_a_round) % check_invite)  # 补充余数
            else:
                # 一轮放卡循环>7s 检查时间设定间隔 检测战斗间隔
                if time.time() - check_last_one_time > check_invite:

                    # 测试用时
                    # print("[{}][补战斗结束检测] {:.2f}s".format(player, time.time()- check_last_one_time))  # 测试用时

                    # 更新上次检测时间 + 更新flag + 中止休息循环
                    check_last_one_time = time.time()

                    if self.faa_battle.use_key_and_check_end():
                        end_flag = True
                        break

            if end_flag:
                break  # 根据flag 跳出外层循环

    def use_card_loop_skill():
        # 放人
        # self.faa_battle.use_player_all("5-4")

        # 计算目标位置 1-14
        cell_list = []
        for i in range(2):
            for j in range(9):
                cell_list.append(str(j + 1) + "-" + str(i + 2))

        # 常规放卡
        for k in range(13):
            self.battle_plan_0.use_card_once(
                num_card=k + 1,
                num_cell=cell_list[k],
                click_space=False)
            time.sleep(0.07)

        # 叠加放卡
        # for k in range(3):
        #     faa.battle_use_card(k*2 + 1 + 8, cell_list[k + 8], click_space=False)
        #     sleep(0.15)
        #     faa.battle_use_card(k*2 + 2 + 8, cell_list[k + 8], click_space=False)
        #     sleep(0.05)

        # 退出关卡
        self.action_exit(mode="游戏内退出")

    if self.battle_mode == 0:
        use_card_loop_0()

    elif self.battle_mode == 3:
        use_card_loop_skill()

    else:
        self.print_debug(text="不战斗 输出 self.battle_plan_card")
        self.print_debug(text=self.battle_plan_card)