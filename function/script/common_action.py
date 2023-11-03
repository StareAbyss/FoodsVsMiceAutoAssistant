from time import sleep, strftime, localtime

from cv2 import vconcat, imwrite

from function.common.bg_mouse import mouse_left_click
from function.common.bg_screenshot import capture_picture_png
from function.common.bg_screenshot_and_compare_picture import loop_find_picture_in_window_ml_click, find_picture_in_window


def battle_a_round(faa: object,
                   deck: int,
                   delay_start: bool,
                   battle_mode: int,
                   task_card: str,
                   list_ban_card: list):
    """
    一轮战斗
    Args:
        :param faa: 账号实例
        :param delay_start: 是房主 房主要晚一点点开始
        :param battle_mode: 战斗模式 0 cd模式 或 1遍历模式
        :param task_card: 任务要求卡片的序号。默认0即为没有。
        :param list_ban_card: ban卡列表
        :param deck: 卡组序号(1-6)
    """

    # 提取handle
    handle = faa.handle

    # 提取一些常用变量
    dpi = faa.dpi
    path_p_common = faa.path_p_common
    path_p_card = faa.path_p_card
    path_logs = faa.path_logs
    player = faa.player

    # 刷新ui: 状态文本
    print("{} 寻找开始或准备按钮".format(player))

    # 循环查找开始按键
    my_path = path_p_common + "\\BattleBefore_ReadyCheckStart.png"
    if not loop_find_picture_in_window_ml_click(handle=handle,
                                                target_path=my_path,
                                                change_per=dpi,
                                                l_i_time=1,
                                                sleep_time=0.3,
                                                click=False,
                                                failed_check_time=10):
        print("{} 找不到开始游戏! 创建房间可能失败!".format(player))

    # 房主晚点开始
    if delay_start:
        sleep(0.5)

    # 选择卡组
    print("{} 选择卡组".format(player))
    mouse_left_click(handle=handle,
                     x=int({1: 425, 2: 523, 3: 588, 4: 666, 5: 756, 6: 837}[deck] * dpi),
                     y=int(121 * dpi),
                     sleep_time=0.5)

    # 开始寻找并添加任务所需卡片
    if task_card == "None" or task_card == "Bubble":
        print("{} 不需要额外带卡,跳过".format(player))
    else:
        # 房主晚点开始
        if delay_start:
            sleep(6)
        print("{} 开始寻找任务卡".format(player))
        # 复位滑块
        mouse_left_click(handle, int(931 * dpi), int(209 * dpi), sleep_time=0.25)
        flag_find_task_card = False
        for i in range(7):
            # 找到就点一下
            if not flag_find_task_card:
                if loop_find_picture_in_window_ml_click(handle=handle,
                                                        target_path=path_p_card + "\\" + task_card + ".png",
                                                        tolerance=0.97,
                                                        change_per=dpi,
                                                        click=True,
                                                        failed_check_time=1):
                    flag_find_task_card = True
            # 滑块向下移动3次
            for j in range(3):
                mouse_left_click(handle, int(931 * dpi), int(400 * dpi), sleep_time=0.05)
        # 双方都完成循环 以保证同步
        print("{} 完成任务卡查找 大概.?".format(player))

    # 点击开始
    if not loop_find_picture_in_window_ml_click(handle=handle,
                                                target_path=path_p_common + "\\BattleBefore_ReadyCheckStart.png",
                                                change_per=dpi,
                                                l_i_time=1,
                                                sleep_time=0.3,
                                                click=True,
                                                failed_check_time=10):
        print("{} 10s找不到开始游戏! 创建房间可能失败!".format(player))

    # 防止被没有带xx卡卡住
    my_path = path_p_common + "\\BattleBefore_NoMatCardEnter.png"
    if find_picture_in_window(handle=handle, target_path=my_path):
        mouse_left_click(handle, int(427 * dpi), int(353 * dpi))

    # 刷新ui: 状态文本
    print("{} 等待进入战斗".format(player))

    # 循环查找火苗图标 找到战斗开始
    my_path = path_p_common + "\\Battle_FireElement.png"
    if not loop_find_picture_in_window_ml_click(handle=handle,
                                                target_path=my_path,
                                                change_per=dpi,
                                                l_i_time=1,
                                                sleep_time=1,
                                                click=False,
                                                failed_check_time=20):
        print("{} 20s没能进入游戏...可能卡住了...".format(player))

    # 刷新ui: 状态文本
    print("{} 战斗进行中...".format(player))
    sleep(1)

    # 房主晚点开始
    if delay_start:
        sleep(1.5)

    # 战斗循环
    faa.action_battle_normal(battle_mode=battle_mode, task_card=task_card, list_ban_card=list_ban_card)

    print("{} 战斗结束".format(player))

    f1 = find_picture_in_window(handle=handle,
                                target_path=path_p_common + "\\BattleEnd_1_Loot.png",
                                tolerance=0.999)
    f2 = find_picture_in_window(handle=handle,
                                target_path=path_p_common + "\\BattleEnd_2_Loot.png",
                                tolerance=0.999)
    if f1 or f2:
        print("{} [Safe]正常结束, 尝试捕获战利品截图".format(player))
        # 记录战利品
        img = []
        mouse_left_click(handle, int(708 * dpi), int(484 * dpi), 0.05, 0.05)
        mouse_left_click(handle, int(708 * dpi), int(484 * dpi), 0.05, 0.3)
        img.append(capture_picture_png(handle)[453:551, 209:698])  # Y_min:Y_max,X_min:X_max
        sleep(0.5)
        mouse_left_click(handle, int(708 * dpi), int(510 * dpi), 0.05, 0.05)
        mouse_left_click(handle, int(708 * dpi), int(510 * dpi), 0.05, 0.3)
        img.append(capture_picture_png(handle)[453:552, 209:698])  # Y_min:Y_max,X_min:X_max
        sleep(0.5)
        mouse_left_click(handle, int(708 * dpi), int(527 * dpi), 0.05, 0.05)
        mouse_left_click(handle, int(708 * dpi), int(527 * dpi), 0.05, 0.3)
        img.append(capture_picture_png(handle)[503:552, 209:698])  # Y_min:Y_max,X_min:X_max
        # 垂直拼接
        img = vconcat(img)
        # 保存图片
        title = "{}\\{}_{}_{}.png".format(path_logs, faa.stage_info["id"],
                                          strftime('%Y-%m-%d_%Hh%Mm%Ss', localtime()), player)
        imwrite(title, img)

    # 循环查找战利品字样
    find = loop_find_picture_in_window_ml_click(handle=handle,
                                                target_path=path_p_common + "\\BattleEnd_4_Chest.png",
                                                change_per=dpi,
                                                click=False,
                                                failed_check_time=10)
    if find:
        # 刷新ui: 状态文本
        print("{} [Safe]捕获到战利品字样, 翻牌中...".format(player))
        # 开始翻牌
        mouse_left_click(handle, int(708 * dpi), int(502 * dpi), 0.05, 4)
        # 翻牌 1+2
        mouse_left_click(handle, int(550 * dpi), int(170 * dpi), 0.05, 0.25)
        mouse_left_click(handle, int(708 * dpi), int(170 * dpi), 0.05, 0.25)
        # 结束翻牌
        mouse_left_click(handle, int(708 * dpi), int(502 * dpi), 0.05, 3)
        print("{} [Safe]战斗结束!".format(player))
    else:
        print("{} [Warning]10s未能捕获[战利品字样].尝试捕获[战斗开始字样].".format(player))
        find = loop_find_picture_in_window_ml_click(handle=handle,
                                                    target_path=path_p_common + "\\BattleBefore_ReadyCheckStart.png",
                                                    change_per=dpi,
                                                    click=False,
                                                    failed_check_time=5)
        if find:
            print("{} [Warning]成功捕获[战斗开始字样], 结束战斗流程.".format(player))
        else:
            print("{} [Error]5s未能捕获[战斗开始字样], 结束战斗流程.".format(player))

    # 战斗结束休息
    sleep(3)


def invite(faa_1: object, faa_2: object):
    """
    号1邀请号2到房间 需要在同一个区
    :param faa_1: 号1
    :param faa_2: 号2
    :return: bool 是否最终找到了图片
    """
    dpi = faa_1.dpi
    if not loop_find_picture_in_window_ml_click(handle=faa_1.handle,
                                                target_path=faa_1.path_p_common + "\\BattleBefore_ReadyCheckStart.png",
                                                change_per=dpi,
                                                sleep_time=0.3,
                                                click=False,
                                                failed_check_time=2.0):
        print("2s找不到开始游戏! 土豆服务器问题, 创建房间可能失败!")
        return False
    # 点邀请
    mouse_left_click(faa_1.handle, int(410 * dpi), int(546 * dpi))
    sleep(0.5)
    # 点好友
    mouse_left_click(faa_1.handle, int(528 * dpi), int(130 * dpi))
    sleep(0.5)
    # 获取好友id位置并邀请
    # [x, y] = find_p_in_p(faa_1.handle, faa_1.path_p_common + "\\P2_name.png")
    # mouse_left_click(faa_1.handle, int((x + 100) * dpi), int(y * dpi))
    # 直接邀请
    mouse_left_click(faa_1.handle, int(601 * dpi), int(157 * dpi))
    sleep(0.5)
    # p2接受邀请
    if not loop_find_picture_in_window_ml_click(handle=faa_2.handle,
                                                target_path=faa_1.path_p_common + "\\BattleBefore_BeInvitedEnter.png",
                                                change_per=dpi,
                                                sleep_time=2.0,
                                                failed_check_time=2.0):
        print("2s没能组队? 土豆服务器问题, 尝试解决ing...")
        return False
    # p1关闭邀请窗口
    mouse_left_click(faa_1.handle, int(590 * dpi), int(491 * dpi), sleep_time=1.5)
    return True
