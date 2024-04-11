import cProfile
import time

from cv2 import imwrite, imshow, waitKey

from function.common.bg_p_screenshot import capture_picture_png
from function.scattered.gat_handle import faa_get_handle


def test_screenshot_once():
    def main():
        handle = faa_get_handle(channel="小号4 | 锑食", mode="flash")
        # handle_browser = faa_get_handle(channel="锑食", mode="browser")
        # handle = faa_get_handle(channel="深渊之下 | 锑食", mode="flash")
        # handle = faa_get_handle(channel="深渊之下 | 锑食", mode="360")

        # 调用截图
        image = capture_picture_png(handle=handle, raw_range=[257 - 45, 74 - 64, 257 + 8, 74 + 6])
        # image = capture_picture_png(handle=handle, raw_range=[0, 0, 950, 600])
        # image = capture_picture_png(handle=handle_browser, raw_range=[0, 0, 2000, 2000])
        # image = capture_picture_png(handle=handle, raw_range=[161, 75, 164, 85])

        # 保存图片
        imwrite(time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime()) + ".png", image)

        # 暂时显示
        imshow(winname="Capture Test.png", mat=image)
        waitKey()

    if __name__ == "__main__":
        main()


def test_some_times():
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
