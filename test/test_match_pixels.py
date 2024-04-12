import numpy as np


def compare_pixels(img, tar_img):
    """为抵消游戏蒙版色，导致的差距，用于对比识别目标像素和标准像素的函数, 只要有一个像素颜色正确就视为True """
    for y in range(len(img)):
        for x in range(len(img[y])):
            result = abs(np.sum(img[y][x] - tar_img[y][x]))
            print(result)
            if result < 25:
                return True
    return False


class TestComparePixels:

    def __init__(self):
        self.test_pixel_match()
        self.test_pixel_no_match()
        self.test_pixel_close_match()

    def test_pixel_match(self):
        """测试当像素匹配时函数返回True"""
        # 4x4白色像素
        img = np.array([
            [[255, 255, 255], [255, 255, 255]],
            [[255, 255, 255], [255, 255, 255]]
        ])
        # 4x4白色像素
        tar_img = np.array([
            [[255, 255, 255], [255, 255, 255]],
            [[255, 255, 255], [255, 255, 255]]
        ])
        print(compare_pixels(img, tar_img))

    def test_pixel_no_match(self):
        """测试当像素不匹配时函数返回False"""
        # 4x4 白 和 4x4黑
        img = np.array([
            [[255, 255, 255], [255, 255, 255]],
            [[255, 255, 255], [255, 255, 255]]
        ])
        tar_img = np.array([
            [[0, 0, 0], [0, 0, 0]],
            [[0, 0, 0], [0, 0, 0]]
        ])
        print(compare_pixels(img, tar_img))

    def test_pixel_close_match(self):
        """测试当像素接近但在容忍范围内时函数返回True"""
        # 接近白色的像素 + 3 黑像素
        img = np.array([
            [[0, 0, 0], [0, 0, 0]],
            [[250, 250, 250], [0, 0, 0]]
        ])
        # 白色像素x4
        tar_img = np.array([
            [[255, 255, 255], [255, 255, 255]],
            [[255, 255, 255], [255, 255, 255]]
        ])
        print(compare_pixels(img, tar_img))


if __name__ == '__main__':
    t = TestComparePixels()
