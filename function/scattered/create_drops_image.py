import cv2
import numpy as np

from function.common.overlay_images import overlay_images
from function.globals.g_resources import RESOURCE_P

# 图片尺寸
IMAGE_SIZE = (44, 44, 4)
# 默认图片颜色
BG_COLOR = (30, 30, 30, 70)
# 文字参数
FONT = cv2.FONT_HERSHEY_TRIPLEX


def load_image(item_name):
    # 创建默认的纯黑png
    img_black = np.full(IMAGE_SIZE, BG_COLOR, dtype=np.uint8)

    is_band = "-绑定" in item_name
    item_name_png = item_name.split("-绑定")[0] + ".png"

    # 尝试加载特定物品图片
    if item_name_png in RESOURCE_P["item"]["战利品"].keys():
        if not is_band:
            # 叠加黑背景和带透明度的图片
            return_img = overlay_images(
                img_background=img_black,
                img_overlay=RESOURCE_P["item"]["战利品"][item_name_png]
            )
            return return_img
        else:
            # 叠加黑背景和带透明度的图片
            return_img = overlay_images(
                img_background=img_black,
                img_overlay=RESOURCE_P["item"]["战利品"][item_name_png]
            )
            # 叠加绑定角标
            return_img = overlay_images(
                img_background=return_img,
                img_overlay=RESOURCE_P["item"]["物品-绑定角标-背包.png"]  # 特别注意 背包和战利品使用的角标不一样!!!
            )
            return return_img
    else:
        # 找不到 在中间添加问号
        text = "?"
        font_size = 0.8
        font_thickness = 2

        text_size = cv2.getTextSize(text=text, fontFace=FONT, fontScale=font_size, thickness=font_thickness)[0]
        text_x = (IMAGE_SIZE[0] - text_size[0]) // 2
        text_y = (IMAGE_SIZE[1] + text_size[1]) // 2

        # 黑色文本边缘
        cv2.putText(img=img_black, text=text, org=(text_x, text_y), fontFace=FONT, fontScale=font_size,
                    color=(0, 0, 0, 255), thickness=font_thickness + 1, lineType=-1)
        # 文本本体
        cv2.putText(img=img_black, text=text, org=(text_x, text_y), fontFace=FONT, fontScale=font_size,
                    color=(255, 255, 255, 255), thickness=font_thickness, lineType=-1)
        return img_black


def create_drops_image(count_dict):
    images = []

    if not count_dict:
        # 空值 塞个无字样 不然会报错
        image_none = np.full(IMAGE_SIZE, BG_COLOR, dtype=np.uint8)

        text = "None"
        font_size = 0.5
        font_thickness = 1

        text_size = cv2.getTextSize(text=text, fontFace=FONT, fontScale=font_size, thickness=font_thickness)[0]
        text_x = (IMAGE_SIZE[0] - text_size[0]) // 2
        text_y = (IMAGE_SIZE[1] + text_size[1]) // 2

        # 黑色文本边缘
        cv2.putText(img=image_none, text=text, org=(text_x, text_y), fontFace=FONT, fontScale=font_size,
                    color=(0, 0, 0, 255), thickness=font_thickness + 1, lineType=-1)
        # 文本本体
        cv2.putText(img=image_none, text=text, org=(text_x, text_y), fontFace=FONT, fontScale=font_size,
                    color=(255, 255, 255, 255), thickness=font_thickness, lineType=-1)
        images.append(image_none)

    for name, count in count_dict.items():
        font_size = 0.45
        font_thickness = 1

        item_img = load_image(name)

        # 使用cv2.getTextSize来获取文本的宽度和高度
        (text_width, text_height), _ = cv2.getTextSize(
            text=str(count),
            fontFace=FONT,
            fontScale=font_size,
            thickness=font_thickness
        )

        # 计算文本的右下角位置
        right_align_x = IMAGE_SIZE[0] - 3
        bottom_align_y = IMAGE_SIZE[1] - 15

        # 文本的右下角位置应该是文本宽度和高度减去偏移量
        right_align_org = (right_align_x - text_width, bottom_align_y + text_height)

        # 在右下角添加掉落的数量
        # 黑色文本边缘
        cv2.putText(img=item_img, text=str(count), org=right_align_org, fontFace=FONT, fontScale=font_size,
                    color=(0, 0, 0, 255), thickness=font_thickness + 1, lineType=-1)
        # 文本本体
        cv2.putText(img=item_img, text=str(count), org=right_align_org, fontFace=FONT, fontScale=font_size,
                    color=(255, 255, 255, 255), thickness=font_thickness, lineType=-1)

        images.append(item_img)

    # 水平拼接图片 注意 images如果为空会报错 上面做了处理
    rows = []
    row = []
    for i, img in enumerate(images):
        row.append(img)
        if (i + 1) % 14 == 0 or i == len(images) - 1:
            # 如果当前行不足14张图片，添加默认颜色图片补足
            while len(row) < 14:
                blank_img = np.full(IMAGE_SIZE, BG_COLOR, dtype=np.uint8)
                row.append(blank_img)
            rows.append(np.hstack(row))
            row = []
    # 垂直拼接行
    canvas = np.vstack(rows)
    return canvas


if __name__ == '__main__':
    count_loots_dict = {
        '识别失败': 2,
        '幸运金币': 1,
        '2级四叶草': 2,
        '秘制香料': 3,
        '上等香料': 4,
        '天然香料': 5,
        '换气扇配方': 6,
        '三线酒架配方': 7,
        '瓜皮护罩配方': 8,
        '双向水管配方': 9,
        '木塞子配方': 10,
        '香肠配方': 100,
        '煮蛋器投手配方': 1000,
        '火盆配方': 2,
        '扇片': 1,
        '砂纸': 1,
        '啤酒': 1,
        '牛肉': 1,
        '木块': 1,
        '煤油': 3,
        '发动机': 2,
        '灯座': 2,
        '包装袋': 1,
        '火药': 2,
        '异次元空间袋-绑定': 1,
        '异次元空间袋': 1
    }
    # count_loots_dict = {}
    # 使用
    loot_canvas = create_drops_image(count_loots_dict)

    # 显示或保存图片
    cv2.imshow("Loot Canvas", loot_canvas)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    # 或者保存图片
    cv2.imwrite("loot.png", loot_canvas)
