from time import sleep, strftime, localtime

from cv2 import vconcat, imwrite

from function.common.bg_mouse import mouse_left_click
from function.common.bg_screenshot import capture_picture_png


def screen_loot_logs(handle, zoom, save_log, stage_id, player):
    # 记录战利品
    img = []
    mouse_left_click(handle, int(708 * zoom), int(484 * zoom), 0.05, 0.05)
    mouse_left_click(handle, int(708 * zoom), int(484 * zoom), 0.05, 0.3)
    img.append(capture_picture_png(handle)[453:551, 209:698])  # Y_min:Y_max,X_min:X_max
    sleep(0.5)
    mouse_left_click(handle, int(708 * zoom), int(510 * zoom), 0.05, 0.05)
    mouse_left_click(handle, int(708 * zoom), int(510 * zoom), 0.05, 0.3)
    img.append(capture_picture_png(handle)[453:552, 209:698])  # Y_min:Y_max,X_min:X_max
    sleep(0.5)
    mouse_left_click(handle, int(708 * zoom), int(527 * zoom), 0.05, 0.05)
    mouse_left_click(handle, int(708 * zoom), int(527 * zoom), 0.05, 0.3)
    img.append(capture_picture_png(handle)[503:552, 209:698])  # Y_min:Y_max,X_min:X_max
    # 垂直拼接
    img = vconcat(img)
    # 保存图片
    title = "{}\\{}_{}_{}.png".format(save_log,
                                      stage_id,
                                      strftime('%Y-%m-%d_%Hh%Mm%Ss', localtime()),
                                      player)
    imwrite(title, img)
