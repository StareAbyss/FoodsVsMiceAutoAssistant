import time

from cv2 import imwrite, imshow, waitKey

from function.battle.get_position_in_battle import get_position_card_deck_in_battle
from function.common.bg_p_screenshot import capture_picture_png
from function.globals.get_paths import PATHS
from function.scattered.gat_handle import faa_get_handle

handle = faa_get_handle(channel="锑食", mode="flash")
position_dict = get_position_card_deck_in_battle(handle=handle)
img_path = PATHS["root"] + "\\resource_other\\test_images"
for key, value in position_dict.items():

    # 调用截图
    image = capture_picture_png(handle=handle, raw_range=[value[0] - 45, value[1] - 64, value[0] + 8, value[1] + 6])

    # 保存图片
    imwrite(
        "{}\\{}.png".format(img_path,time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())),
        image
    )

    # 暂时显示
    imshow(winname="Capture Test.png", mat=image)
    waitKey()
