from cv2 import imwrite, imread, IMREAD_UNCHANGED, matchTemplate, TM_SQDIFF_NORMED, minMaxLoc
from function.global_paths import PATHS

from function.common.bg_p_screenshot import capture_picture_png
from function.scattered.gat_handle import faa_get_handle


def get_house_id(handle):
    image_0 = capture_picture_png(handle=handle, raw_range=[0, 0, 950, 600])
    image_0[image_0 != 255] = 0
    my_number = ""

    images = [image_0[28:36, 152:152 + 6],
              image_0[28:36, 159:159 + 6],
              image_0[28:36, 166:166 + 6],
              image_0[28:36, 173:173 + 6]]
    for image in images:
        for i in range(10):
            target_img = imread(filename=PATHS["picture"]["number"] + "\\" + str(i) + ".png",
                                flags=IMREAD_UNCHANGED)

            # 执行模板匹配，采用的匹配方式cv2.TM_SQDIFF_NORMED
            result = matchTemplate(target_img, image, TM_SQDIFF_NORMED)
            (minVal, maxVal, minLoc, maxLoc) = minMaxLoc(result)

            # 如果匹配度100%，认为找到
            if minVal == 0:
                my_number = my_number + str(i)
                break

    if my_number == "":
        images = [image_0[28:36, 152 + 3:152 + 3 + 6],
                  image_0[28:36, 159 + 3:159 + 3 + 6],
                  image_0[28:36, 166 + 3:166 + 3 + 6],
                  image_0[28:36, 173 + 3:173 + 3 + 6]]
        for image in images:
            for i in range(10):
                target_img = imread(filename=PATHS["picture"]["number"] + "\\" + str(i) + ".png",
                                    flags=IMREAD_UNCHANGED)

                # 执行模板匹配，采用的匹配方式cv2.TM_SQDIFF_NORMED
                result = matchTemplate(target_img, image, TM_SQDIFF_NORMED)
                (minVal, maxVal, minLoc, maxLoc) = minMaxLoc(result)

                # 如果匹配度100%，认为找到
                if minVal == 0:
                    my_number = my_number + str(i)
                    break

    return my_number


if __name__ == "__main__":
    def main():

        handle = faa_get_handle(channel="深渊之下 | 锑食", mode="flash")

        image_0 = capture_picture_png(handle=handle, raw_range=[0, 0, 950, 600])
        images = [image_0[28:36, 152 + 3:152 + 3 + 6],
                  image_0[28:36, 159 + 3:159 + 3 + 6],
                  image_0[28:36, 166 + 3:166 + 3 + 6],
                  image_0[28:36, 173 + 3:173 + 3 + 6]]

        for i in range(4):
            image = images[i]
            image[image != 255] = 0
            imwrite("t{}.png".format(i), image)

        print(get_house_id(handle=handle))


    main()
