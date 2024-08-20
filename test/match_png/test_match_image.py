import cProfile

from function.common.bg_img_match import match_p_in_w
from function.globals.init_resources import RESOURCE_P
from function.scattered.gat_handle import faa_get_handle


def f_test():
    source_handle = faa_get_handle(channel="锑食-微端", mode="flash")
    source_range = [240, 190, 740, 265]
    template = RESOURCE_P["top_up_money"]["每日必充_判定点.png"]

    result = match_p_in_w(
        source_handle=source_handle,
        source_range=source_range,
        template=template,
        match_tolerance=0.99,
        test_print=True,
        test_show=True
    )
    print(result)

    # for i in range(100):
    # 匹配不绑
    # match_p_in_w(
    #     source_handle=handle,
    #     source_range=[0, 0, 950, 600],
    #     template=template,
    #     mask=RESOURCE_P["item"]["物品-掩模-不绑定.png"],
    #     match_tolerance=0.99,
    #     test_print=True,
    #     test_show=True,
    # )

    # for i in range(100):
    #     # 匹配绑定
    #     template = overlay_images(
    #         img_background=template,
    #         img_overlay=RESOURCE_P["item"]["物品-绑定角标.png"],
    #         test_show=False)
    #     match_p_in_w(
    #         source_handle=handle,
    #         source_range=[0, 0, 950, 600],
    #         template=template,
    #         template_name="炭烧海星-初级技能书",
    #         mask=RESOURCE_P["item"]["物品-掩模-绑定.png"],
    #         match_tolerance=0.99,
    #         test_print=True,
    #         test_show=True,
    #     )


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
