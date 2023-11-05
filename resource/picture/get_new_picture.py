from cv2 import imwrite
from function_common.background_screenshot import capture_picture_png
from script.common import FAA

if __name__ == '__main__':
    def main():
        msdzls = FAA()
        handle = msdzls.handle
        img = capture_picture_png(handle)[468:484, 383:492, :3]  # 裁剪出需要的区域, 并且去掉rgba的alpha
        name = "[1-6][Champagne Island - Water]"
        imwrite("stage_ready_check/" + name + ".png", img)


    main()
