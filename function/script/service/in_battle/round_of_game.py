from time import sleep

from function.common.bg_mouse import mouse_left_click
from function.common.bg_p_compare import loop_find_p_in_w, loop_find_ps_in_w, find_ps_in_w
from function.tools.screen_loot_logs import screen_loot_logs


def round_of_game(  # 从FAA类中直接获取
        handle,
        zoom,
        paths,
        player,
        stage_info_id,
        action_battle_normal,
        deck: int,
        delay_start: bool,
        battle_mode: int,
        task_card: str,
        list_ban_card: list
):
    """
    一轮战斗
    Args:
        :param handle: 来自FAA类 variable
        :param zoom: 来自FAA类 variable
        :param paths: 来自FAA类 variable
        :param player: 来自FAA类 variable
        :param stage_info_id: 来自FAA类 variable
        :param action_battle_normal: 来自FAA类 function
        :param delay_start: 是房主 房主要晚一点点开始
        :param battle_mode: 战斗模式 0 cd模式 或 1遍历模式
        :param task_card: 任务要求卡片的序号。默认0即为没有。
        :param list_ban_card: ban卡列表
        :param deck: 卡组序号(1-6)
    """

    # 对齐线程
    sleep(0.3)

    # 刷新ui: 状态文本
    print("=" * 50)
    print("[{}] 寻找开始或准备按钮".format(player))

    # 循环查找开始按键
    my_path = paths["picture"]["common"] + "\\battle_before_ready_check_start.png"
    if not loop_find_p_in_w(raw_w_handle=handle,
                            raw_range=[0, 0, 950, 600],
                            target_path=my_path,
                            click_zoom=zoom,
                            target_interval=1,
                            target_sleep=0.3,
                            click=False,
                            target_failed_check=10):
        print("[{}] 找不到开始游戏! 创建房间可能失败!".format(player))

    # 房主延时
    if delay_start:
        sleep(0.5)
    # 选择卡组
    print("[{}] 选择卡组".format(player))
    mouse_left_click(handle=handle,
                     x=int({1: 425, 2: 523, 3: 588, 4: 666, 5: 756, 6: 837}[deck] * zoom),
                     y=int(121 * zoom),
                     sleep_time=0.5)

    """开始寻找并添加任务所需卡片"""
    if task_card == "None" or task_card == "Bubble":
        print("[{}] 不需要额外带卡,跳过".format(player))
    else:
        # 房主晚点开始
        if delay_start:
            sleep(6)
        print("[{}] 开始寻找任务卡".format(player))
        # 复位滑块
        mouse_left_click(handle, int(931 * zoom), int(209 * zoom), sleep_time=0.25)
        flag_find_task_card = False
        for i in range(7):
            # 找到就点一下
            if not flag_find_task_card:
                find = loop_find_p_in_w(
                    raw_w_handle=handle,
                    raw_range=[0, 0, 950, 600],
                    target_path=paths["picture"]["card"] + "\\" + task_card + ".png",
                    target_tolerance=0.95,
                    click_zoom=zoom,
                    click=True,
                    target_failed_check=1
                )
                if find:
                    flag_find_task_card = True
            # 滑块向下移动3次
            for j in range(3):
                mouse_left_click(handle, int(931 * zoom), int(400 * zoom), sleep_time=0.05)
        # 双方都完成循环 以保证同步
        print("[{}] 完成任务卡查找 大概.?".format(player))

    # 房主延时
    if delay_start:
        sleep(0.5)
    # 点击开始
    find = loop_find_p_in_w(
        raw_w_handle=handle,
        raw_range=[0, 0, 950, 600],
        target_path=paths["picture"]["common"] + "\\battle_before_ready_check_start.png",
        click_zoom=zoom,
        target_interval=1,
        target_sleep=0.3,
        click=True,
        target_failed_check=10
    )
    if not find:
        print("[{}] 10s找不到[开始/准备]字样! 创建房间可能失败!".format(player))

    # 防止被没有带xx卡卡住
    # my_path = paths["picture"]["common"] + "\\battle_before_no_mat_card_enter.png"
    # if find_p_in_w(handle=handle, target_path=my_path):
    #     mouse_left_click(handle, int(427 * zoom), int(353 * zoom))

    # 刷新ui: 状态文本
    print("[{}] 查找火苗标识物, 等待进入战斗".format(player))

    # 循环查找火苗图标 找到战斗开始
    loop_find_p_in_w(
        raw_w_handle=handle,
        raw_range=[0, 0, 950, 600],
        target_path=paths["picture"]["common"] + "\\battle_fire_element.png",
        click_zoom=zoom,
        target_interval=1,
        target_sleep=1,
        click=False,
        target_failed_check=86400
    )

    # 刷新ui: 状态文本
    print("[{}] 战斗进行中...".format(player))
    sleep(1)

    # 房主晚点放下人物
    if delay_start:
        sleep(0.5)

    # 战斗循环
    action_battle_normal(battle_mode=battle_mode, task_card=task_card, list_ban_card=list_ban_card)

    print("[{}] 完成战斗, 准备进行收尾工作".format(player))

    # 理想情况下,此处应该是[战利品]界面
    find = find_ps_in_w(
        raw_w_handle=handle,
        raw_range=[0, 0, 950, 600],
        target_opts=[{"target_path": paths["picture"]["common"] + "\\battle_end_1_loot.png",
                      "target_tolerance": 0.999},
                     {"target_path": paths["picture"]["common"] + "\\battle_end_2_loot.png",
                      "target_tolerance": 0.999}],
        return_mode="or"
    )
    if find:
        print("[{}] [Safe]正常结束, 尝试捕获战利品截图".format(player))
        screen_loot_logs(handle=handle, zoom=zoom, save_log=paths["logs"], stage_id=stage_info_id, player=player)

    # 循环查找[翻宝箱], 确认是否可以安全翻牌
    find = loop_find_p_in_w(
        raw_w_handle=handle,
        raw_range=[0, 0, 950, 600],
        target_path=paths["picture"]["common"] + "\\battle_end_4_chest.png",
        target_failed_check=15,
        target_sleep=2,
        click=False,
        click_zoom=zoom
    )
    if find:
        # 刷新ui: 状态文本
        print("[{}] [Safe]捕获到[翻宝箱]字样, 翻牌中...".format(player))
        # 开始翻牌
        sleep(1.5)
        mouse_left_click(handle, int(708 * zoom), int(502 * zoom), 0.05, 6)
        # 翻牌 1+2
        mouse_left_click(handle, int(550 * zoom), int(170 * zoom), 0.05, 1)
        mouse_left_click(handle, int(708 * zoom), int(170 * zoom), 0.05, 1)
        # 结束翻牌
        mouse_left_click(handle, int(708 * zoom), int(502 * zoom), 0.05, 1)
        print("[{}] [Safe]战斗结束!".format(player))
    else:
        print("=" * 50)
        print("[{}] [Warning]15s未能捕获[翻宝箱], 出问题了!".format(player))
        print("=" * 50)

    # 查找战斗结束 来兜底正确完成了战斗
    print("[{}] [Safe]尝试捕获[开始/准备/魔塔蛋糕UI], 以完成战斗流程.".format(player))

    find = loop_find_ps_in_w(raw_w_handle=handle,
                             raw_range=[0, 0, 950, 600],
                             target_opts=[
                                 {"target_path": paths["picture"][
                                                     "common"] + "\\battle_before_ready_check_start.png",
                                  "target_tolerance": 0.99},
                                 {"target_path": paths["picture"]["common"] + "\\mage_tower_ui.png",
                                  "target_tolerance": 0.99}],
                             target_return_mode="or",
                             target_failed_check=10,
                             target_interval=0.2)

    if find:
        print("[{}] [Safe]成功捕获[开始/准备/魔塔蛋糕UI], 完成战斗流程.".format(player))
        sleep(3)
    else:
        print("=" * 50)
        print("[{}] [Error]没能捕获[开始/准备/魔塔蛋糕UI], 超长时间sleep, 请中止脚本!!!".format(player))
        print("=" * 50)
        sleep(999999)

    # 休息3s 来让线程对齐 防止未知bug
    sleep(3)


