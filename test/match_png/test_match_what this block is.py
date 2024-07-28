import cProfile

import cv2
import numpy as np

from function.core.analyzer_of_loot_logs import match_items_from_image


def f_test():
    # 老方法 0.66s
    img_path = "target_2.png"
    img_array = cv2.imdecode(buf=np.fromfile(file=img_path, dtype=np.uint8), flags=-1)
    drop_dict = match_items_from_image(img_save_path=img_path, image=img_array, mode='loots', test_print=True)

    # CUS_LOGGER.info("[捕获战利品] 处在战利品UI 战利品已 捕获/识别/保存".format(drop_dict))


# f_test()
cProfile.run("f_test()")
