import cProfile

from function.common.bg_p_screenshot import capture_picture_png
from function.script.scattered.gat_handle import faa_get_handle


def f_test():
    handle = faa_get_handle(channel="深渊之下 | 锑食", mode="flash")
    for i in range(1000):
        image = capture_picture_png(handle=handle, raw_range=[0, 0, 950, 600])


cProfile.run("f_test()")

"""
ncalls	表示函数调用的次数
tottime	表示指定函数的总的运行时间，除掉函数中调用子函数的运行时间
percall	(第一个percall) 等于 tottime/ncalls
cumtime	表示该函数及其所有子函数的调用运行的时间，即函数开始调用到返回的时间
percall	(第二个percall) 即函数运行一次的平均时间，等于 cumtime/ncalls
filename:lineno(function)	每个函数调用的具体信息，一般指向函数名
"""

"""
结论:
捕捉图片 [一个完整窗口]
2.5s / 1000t (i9-13900HX)

保存图片 [950 x 600 x 4 的 png]
16s / 1000t (i9-13900HX)
"""
