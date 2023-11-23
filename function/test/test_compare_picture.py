import cProfile

from function.common.bg_p_compare import find_p_in_w
from function.get_paths import paths
from function.script.scattered.gat_handle import faa_get_handle


def f_test():
    handle = faa_get_handle(channel="深渊之下 | 锑食", mode="game")
    target_path = paths["picture"]["common"] + "\\goto_arena.png"
    for i in range(100):
        find_p_in_w(
            raw_w_handle=handle,
            # raw_range=[0, 0, 2000, 2000],
            raw_range=[0, 0, 950, 600],
            target_path=target_path,
            target_tolerance=0.95
        )


cProfile.run("f_test()")

"""
裁剪与否的性能提升:
完全不裁剪, 从[1425 x 894]找[113 x 45]
4通道每次耗时 68s/1000t
3通道每次耗时 56s/1000t

进行裁剪, 从[900 x 600]找[113 x 45]
4通道每次耗时 34s/1000t
3通道每次耗时 28s/1000t

计算方法:
不考虑函数调用的内部耗时 差距为 像素量相除 差距大约2.5倍
考虑函数调用的内部耗时 实际差距为 2倍
"""