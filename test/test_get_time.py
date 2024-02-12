import cProfile
import time


def f_test():
    interval = 0.00001
    last_check_time = time.time()
    for i in range(1000000):
        if time.time() - last_check_time > interval:
            last_check_time = time.time()


cProfile.run("f_test()")

"""
结论:
获取系统时钟几乎也耗时
0.028s / 1M t (i9-13900HX) ≈ 无耗时
time.time() 甚至比注册变量后调用还快...
所以需要time() 就无脑用吧!
"""
