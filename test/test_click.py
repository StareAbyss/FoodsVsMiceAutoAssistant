import cProfile

from function.common.bg_mouse import mouse_left_click
from function.scattered.gat_handle import faa_get_handle


def f_test():
    zoom = 1.5
    click_interval = 0
    click_sleep = 0
    handle = faa_get_handle(channel="深渊之下 | 锑食", mode="flash")
    for i in range(1000):
        mouse_left_click(handle=handle,
                         x=int(10 * zoom),
                         y=int(10 * zoom),
                         interval_time=click_interval,
                         sleep_time=click_sleep)


cProfile.run("f_test()")

"""
结论:
如果只是点击本身
0.043s / 1000t (i9-13900HX) ≈ 无耗时
"""
