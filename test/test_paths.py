import time

from function.get_paths import get_paths_faa_new, get_paths_faa_old


def function_1():
    time_start = time.time()  # 记录开始时间

    for i in range(10000):
        get_paths_faa_new()

    time_end = time.time()  # 记录结束时间
    time_sum = time_end - time_start  # 计算的时间差为程序的执行时间，单位为秒/s
    print(time_sum)


def function_2():
    time_start = time.time()  # 记录开始时间

    for i in range(10000):
        get_paths_faa_old()

    time_end = time.time()  # 记录结束时间
    time_sum = time_end - time_start  # 计算的时间差为程序的执行时间，单位为秒/s
    print(time_sum)


if __name__ == '__main__':
    function_1()
    function_2()
    """结论, 全局变量方法可以防止重复创建数组 效率超翻倍"""
