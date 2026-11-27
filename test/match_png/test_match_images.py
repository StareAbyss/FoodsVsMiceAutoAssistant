from function.common.bg_img_match import match_ps_in_w
from function.globals.g_resources import RESOURCE_P
from function.scattered.gat_handle import faa_get_handle


def f_test():
    handle = faa_get_handle(channel="锑食", mode="flash")

    source_range = [558, 89, 903, 532]
    gem_ps = RESOURCE_P["synthesis"]["可分解宝石"]
    result = match_ps_in_w(
        source_handle=handle,
        template_opts=[
            {"template": gem_ps["攻击宝石.png"], "source_range": source_range, "match_tolerance": 0.95},
            {"template": gem_ps["绿宝石.png"], "source_range": source_range, "match_tolerance": 0.95},
            {"template": gem_ps["对战雾宝石.png"], "source_range": source_range, "match_tolerance": 0.95},
            {"template": gem_ps["对战轰炸宝石.png"], "source_range": source_range, "match_tolerance": 0.95},
            {"template": gem_ps["神圣宝石.png"], "source_range": source_range, "match_tolerance": 0.95},
            {"template": gem_ps["轰炸宝石.png"], "source_range": source_range, "match_tolerance": 0.95},
            {"template": gem_ps["冰冻宝石.png"], "source_range": source_range, "match_tolerance": 0.95},
            {"template": gem_ps["激光宝石.png"], "source_range": source_range, "match_tolerance": 0.95},
            {"template": gem_ps["猫眼宝石.png"], "source_range": source_range, "match_tolerance": 0.95},
        ],
        return_mode='or',
        quick_mode=True
    )


f_test()

# cProfile.run("f_test()")

"""
从原始图像[950- x 600-] x 找目标图像[113 x 45] x 3图 x 1000次

一次裁剪X 二次裁剪X 103.2s
一次裁剪√ 二次裁剪X 103.2s
一次裁剪X 二次裁剪√ 11.4s
一次裁剪√ 二次裁剪√ 11.4s

结论1 速度只取决于最终需要比对的数量
结论2 范围过大超出截获区域的部分, 不会影响性能(切片操作可以超出索引)
"""
