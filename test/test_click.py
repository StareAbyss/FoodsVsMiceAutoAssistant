from function.common.bg_mouse import mouse_left_click
from function.scattered.gat_handle import faa_get_handle


def f_test():
    zoom = 1.0
    click_interval = 0
    click_sleep = 0

    channel = "锑食-微端"
    handle = faa_get_handle(channel=channel, mode="flash")
    handle_browser = faa_get_handle(channel=channel, mode="browser")
    handle_360 = faa_get_handle(channel=channel, mode="360")

    for i in range(1):
        mouse_left_click(
            handle=handle_browser,
            x=int(470 * zoom),
            y=int(185 * zoom),
            # interval_time=click_interval,
            sleep_time=click_sleep
        )


# cProfile.run("f_test()")
f_test()

"""
结论:
如果只是点击本身
0.043s / 1000t (i9-13900HX) ≈ 无耗时
"""
