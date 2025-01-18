import os

import cv2

from function.common.bg_img_screenshot import capture_image_png
from function.scattered.gat_handle import faa_get_handle

channel = "锑食-微端"
handle = faa_get_handle(channel=channel, mode="flash")
handle_browser = faa_get_handle(channel=channel, mode="browser")
handle_360 = faa_get_handle(channel=channel, mode="360")

img = capture_image_png(
    handle=handle,
    raw_range=[484,133,908,316],
    root_handle=handle_360
)
if not os.path.exists("img"):
    os.makedirs("img")
cv2.imencode(ext=".png", img=img)[1].tofile("img\\test.png")

