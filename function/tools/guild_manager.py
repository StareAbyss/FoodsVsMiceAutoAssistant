import time
from datetime import datetime
from function.common.bg_img_screenshot import capture_image_png
from function.common.same_size_match import match_block_equal_in_images
from function.globals import g_resources
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.gat_handle import faa_get_handle
import cv2
import numpy as np


class GuildManager:
    """
    公会管理工具，自动扫描并生成带日期的表格
    格式为：
    公会成员名称图片；日期；月贡；周贡；日贡；总贡；备注
    """

    def get_time(self):
        """
        获取当前时间，年月日
        """
        return datetime.now().strftime("%Y-%m-%d")

    def get_guild_member_page(self, handle, handle_360):
        """
        循环获取公会成员页面
        """
        img_old = None
        for i in range(20):
            for j in range(5):
                # 尝试五次获取，如果不与之前的图片重复则认为成功翻页，获取一次成员信息
                img = capture_image_png(handle=handle, raw_range=[484, 133, 908, 316], root_handle=handle_360)
                if img_old is None or not np.array_equal(img, img_old):
                    # 如果是第一次截图或不与之前截图重复，则认为成功翻页
                    img_old = img
                    break
                else:
                    # 翻页后图片未刷新，等待0.2s继续识别
                    time.sleep(0.2)
            else:
                # 五次等待截图均重复，认为翻页已经到头了
                return
            # 获取一次成员信息
            self.get_guild_member_info(img)
            # 获取后点击下一页
            T_ACTION_QUEUE_TIMER.add_click_to_queue(handle=handle, x=745, y=330)
            time.sleep(0.2)

    def get_guild_member_info(self, img):
        """
        截图，获取成员名称，职位，当前贡献
        """

        # 一页稳定有五个成员，按五行分布
        for i in range(5):
            # 每一行的宽度是35，行间距为2。先获取第一行的图片
            img_member = img[37 * i:37 * i + 35, :]
            # 名称图片，用于识别是否是同一个人
            img_name = img_member[:, 0:93]
            # 贡献点图片，用于OCR数字来识别贡献点
            img_contribution = img_member[5:13, 184:245]
            contribution = self.ocr_contribution(img_contribution)
            print(contribution)

    def ocr_contribution(self, img):
        """
        OCR识别图片中的数字，返回识别结果
        贡献点数字的高度为8，宽度为7；rgb颜色为(255, 190, 0)
        """
        # 获取灰度图
        img_gray = self.make_gray(img)

        # 开始分割数字
        start_pos = 0
        numbers = ""

        # 第一步，获取图片数字开始列，即第一个含有黑色像素的列(1不够宽，所以第一列得尝试两次
        for i in range(img_gray.shape[1]):
            if np.any(img_gray[:, i] == 0):
                start_pos = i
                break

        while start_pos < img_gray.shape[1]:
            number_block = img_gray[:, start_pos:start_pos + 7]

            number_block_1 = img_gray[:, start_pos - 1:start_pos + 6]

            number = match_block_equal_in_images(
                block_array=number_block,
                images=g_resources.RESOURCE_P["ocr"]["贡献点数字"])

            number_1 = match_block_equal_in_images(
                block_array=number_block_1,
                images=g_resources.RESOURCE_P["ocr"]["贡献点数字"])

            if number:
                numbers += number
                start_pos += 7
            # 如果数字图片全白，则说明识别完毕
            elif np.all(number_block == 255):
                break
            # 特殊情况，第一个数字是1，改变start_pos后照常识别
            elif number_1:
                numbers += number_1
                start_pos += 6
            # 识别失败，则保存这张图片
            else:
                cv2.imwrite(f"number{start_pos}.png", number_block)
                start_pos += 7

        if not numbers:
            return 0

        return int(numbers)

    def make_gray(self, img):
        """
        将图片转换为灰度图
        """
        # 检查是否有Alpha通道 将RGBA转换为BGR
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        # 将所有文本颜色转化为黑色，其余则为白色
        lower_bound = np.array([254, 189, 0])
        upper_bound = np.array([255, 190, 0])
        mask = cv2.inRange(img, lower_bound, upper_bound)

        # 图片中非字体转化为白色
        img[mask > 0] = [0, 0, 0]

        # 字体转化为黑色
        img[mask == 0] = [255, 255, 255]
        # 转换为灰度图
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        return img_gray

    def make_table(self):
        """
        生成表格
        """
        pass


if __name__ == '__main__':
    gm = GuildManager()
    print(gm.get_time())
    handle = faa_get_handle(channel="美食大战老鼠微端", mode="flash")
    handle_360 = faa_get_handle(channel="美食大战老鼠微端", mode="360")
    gm.get_guild_member_page(handle, handle_360)
