# coding:utf-8
from function.common.bg_mouse import mouse_left_click
from function.common.bg_screenshot_and_compare_picture import find_p_in_p
from function.common.loop_timer_and_counter import loop_timer_and_counter
from function.script.common import FAA


def f_proficiency(channel, dpi):
    fvm = FAA(channel=channel, dpi=dpi)
    dpi = fvm.dpi
    path_common = fvm.path_p_common
    handle = fvm.handle
    print("自动获取分辨率句柄：", handle)
    print("自动获取分辨率系数：", dpi)

    def f_loop(*args):
        while True:
            # 进入关卡(遗迹)
            a = find_p_in_p(handle, path_common + "\\SelectStage_HeiTiCongLin.png")
            if a:
                mouse_left_click(handle, int(a[0] * dpi), int(a[1] * dpi), 0.01, 0.3)
                mouse_left_click(handle, int(582 * dpi), int(498 * dpi), 0.01, 0.3)
                break

        # 选第五个卡组
        mouse_left_click(handle, int(760 * dpi), int(123 * dpi), 0.01, 0.1)

        # 进入关卡
        mouse_left_click(handle, int(873 * dpi), int(480 * dpi), 0.01, 0.01)

        # 检测读条完成
        while True:
            a = find_p_in_p(handle, path_common + "\\Battle_FireElement.png")
            if a:
                break
        # 战斗并退出
        fvm.battle_skill()

    loop_timer_and_counter(10000, f_loop)


if __name__ == '__main__':
    def main():
        print("开始运行")
        f_proficiency("锑食", 1.5)


    main()
