import cProfile

from function.common.bg_img_match import match_p_in_w
from function.globals.get_paths import PATHS
from function.scattered.gat_handle import faa_get_handle


def f_test():
    handle = faa_get_handle(channel="锑食-微端", mode="flash")
    template = PATHS["root"] + "\\resource_other\\原始资源\\2\\1级四叶草.png"  # 44x44

    # for i in range(100):
    result = match_p_in_w(
        source_handle=handle,
        source_range=[0, 0, 950, 600],
        template=template,
        match_tolerance=0.95,
        is_test=True
    )
    print(result)


cProfile.run("f_test()")

"""
下述测试条件
source_img 900x600
target_img 44x44
times 1000次
1. 裁剪source_img(即使被裁剪部分是一片黑这种完全和模板对不上号的部分) 也能按裁剪像素比例[极大]提高性能表现, 模板匹配没有某种粗中止方法
2. 减少template_img通道数, 即使被减少的是alpha通道, 也能[极大]提高性能表现
3. 预加载图像文件, 能[略微]提高性能表现 38s->37s
4. 不使用掩模,即使掩模范围很小,也能[极大]提高性能表现 (匹配耗时减半)
"""
