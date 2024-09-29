import time

from cv2 import imwrite

from function.common.bg_img_screenshot import capture_image_png
from function.core_battle.get_position_in_battle import get_position_card_deck_in_battle
from function.globals.get_paths import PATHS
from function.scattered.gat_handle import faa_get_handle

handle = faa_get_handle(channel="锑食-微端", mode="flash")
handle_360 = faa_get_handle(channel="锑食-微端", mode="360")
position_dict = get_position_card_deck_in_battle(handle=handle, handle_360=handle_360)
img_path = PATHS["root"] + "\\resource_other\\test_images"

for key, value in position_dict.items():
    # 调用截图
    image = capture_image_png(
        handle=handle,
        raw_range=[value[0], value[1], value[0] + 53, value[1] + 70])

    # 保存图片
    imwrite(
        "{}\\{}_{}X{}.png".format(
            img_path,
            time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime()),
            value[0],
            value[1]),
        image
    )

    # 暂时显示
    # imshow(winname="Capture Test.png", mat=image)
    # waitKey()
