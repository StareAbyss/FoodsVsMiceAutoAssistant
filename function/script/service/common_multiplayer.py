from function.common.bg_mouse import mouse_left_click
from function.common.bg_screenshot_and_compare import loop_find_p_in_w

"""包含 需要多个角色异步完成的操作"""


def invite(
        faa_1: object,
        faa_2: object):
    """
    号1邀请号2到房间 需要在同一个区
    :param faa_1: 号1
    :param faa_2: 号2
    :return: bool 是否最终找到了图片
    """
    zoom = faa_1.zoom
    if not loop_find_p_in_w(handle=faa_1.handle,
                            target_path=faa_1.paths["picture"]["common"] + "\\battle_before_ready_check_start.png",
                            click_zoom=zoom,
                            target_sleep=0.3,
                            click=False,
                            target_failed_check=2.0):
        print("2s找不到开始游戏! 土豆服务器问题, 创建房间可能失败!")
        return False
    # 点击[房间ui-邀请按钮]
    mouse_left_click(handle=faa_1.handle, x=int(410 * zoom), y=int(546 * zoom), sleep_time=0.5)

    # 点击[房间ui-邀请ui-公会按钮]
    mouse_left_click(handle=faa_1.handle, x=int(600 * zoom), y=int(130 * zoom), sleep_time=0.5)

    """直接邀请"""
    # mouse_left_click(handle=faa_1.handle, x=int(601 * zoom), y=int(157 * zoom), sleep_time=0.5)

    """p2接受邀请"""
    if not loop_find_p_in_w(handle=faa_2.handle,
                            target_path=faa_1.paths["picture"]["common"] + "\\battle_before_be_invited_enter.png",
                            click_zoom=zoom,
                            target_sleep=2.0,
                            target_failed_check=2.0):
        print("2s没能组队? 土豆服务器问题, 尝试解决ing...")
        return False

    # p1关闭邀请窗口
    mouse_left_click(handle=faa_1.handle, x=int(590 * zoom), y=int(491 * zoom), sleep_time=1.5)

    return True

