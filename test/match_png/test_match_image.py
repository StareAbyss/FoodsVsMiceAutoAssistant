import cProfile

from function.common.bg_img_match import loop_match_p_in_w
from function.globals.get_paths import PATHS
from function.globals.init_resources import RESOURCE_P
from function.scattered.gat_handle import faa_get_handle


def f_test():
    handle = faa_get_handle(channel="锑食-微端", mode="flash")
    template = PATHS["root"] + "\\resource_other\\原始资源\\2\\炭烧海星-初级技能书.png"  # 44x44

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

    source_range_2 = [275, 210, 395, 265]  # 游币兑换按钮位置
    result = loop_match_p_in_w(
        source_handle=faa_get_handle(channel="小号2 | 锑食-微端", mode="flash"),
        source_range=source_range_2,
        template=RESOURCE_P["top_up_money"]["充值界面_游币兑换.png"],
        match_tolerance=0.99,
        match_interval=0.2,
        match_failed_check=5,
        after_sleep=2,
        click=True,
        click_handle=faa_get_handle(channel="小号2 | 锑食-微端", mode="browser")
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
