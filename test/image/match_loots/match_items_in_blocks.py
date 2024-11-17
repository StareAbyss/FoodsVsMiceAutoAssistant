import cv2
import numpy as np

from function.common.same_size_match import one_item_match
from function.core.analyzer_of_loot_logs import match_items_from_image_and_save


def f_test_match_items_from_image_and_save():
    # 老方法 0.66s
    img_path = "NO-4-5_2P_2024-07-29_11-45-23.png"
    img_array = cv2.imdecode(buf=np.fromfile(file=img_path, dtype=np.uint8), flags=-1)

    drop_dict = match_items_from_image_and_save(img_save_path=img_path, image=img_array, mode='loots', test_print=True)

    print("[Test] [捕获战利品] 处在战利品UI 战利品已 捕获/识别/保存".format(drop_dict))


def f_test_match_block_is_item():
    img_block_path = "花园钥匙.png"
    img_block = cv2.imdecode(buf=np.fromfile(file=img_block_path, dtype=np.uint8), flags=-1)

    img_tar_path = "F://My Project//Python//FoodsVsMousesAutoAssistant//resource//image//item//战利品//花园钥匙.png"
    img_tar = cv2.imdecode(buf=np.fromfile(file=img_tar_path, dtype=np.uint8), flags=-1)

    print(one_item_match(
        img_block=img_block,
        img_tar=img_tar,
        mode="match_template_with_mask_tradable"))


f_test_match_items_from_image_and_save()
