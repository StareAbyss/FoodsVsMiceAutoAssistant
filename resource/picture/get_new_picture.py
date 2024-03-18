from cv2 import imwrite

from function.common.bg_p_screenshot import capture_picture_png
from function.script.FAA import FAA

if __name__ == '__main__':
    def main():
        msdzls = FAA()
        handle = msdzls.handle

        # 裁剪出需要的区域, 并且去掉rgba的alpha
        img = capture_picture_png(handle=handle,raw_range=[383,468,492,484])
        name = "[1-6][Champagne Island - Water]"
        name = "test"
        imwrite("stage_ready_check/" + name + ".png", img)

    main()
