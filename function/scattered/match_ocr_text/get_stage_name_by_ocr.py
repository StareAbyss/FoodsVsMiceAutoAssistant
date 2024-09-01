from function.common.bg_img_screenshot import capture_image_png
from function.scattered.gat_handle import faa_get_handle
from function.scattered.match_ocr_text.match_text import match


def screen_get_stage_name(handle, handle_360) -> str:
    """
    在关卡备战界面 获得关卡名字 该函数未完工
    """

    img = capture_image_png(
        handle=handle,
        raw_range=[388, 470, 492, 482],
        root_handle=handle_360
    )

    # cv2.imshow("img", img)
    # cv2.waitKey(0)

    stage_id = match(source=img, mode="关卡名称")

    return stage_id


if __name__ == '__main__':
    handle = faa_get_handle(channel="美食大战老鼠微端", mode="flash")
    handle_360 = faa_get_handle(channel="美食大战老鼠微端", mode="360")


    def main():
        print(screen_get_stage_name(handle=handle, handle_360=handle_360))


    main()
