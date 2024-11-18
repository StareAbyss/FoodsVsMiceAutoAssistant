import datetime
import hashlib
import json
import os
import time

import cv2
import numpy as np

from function.common.bg_img_screenshot import capture_image_png
from function.common.same_size_match import match_block_equal_in_images
from function.globals import g_resources, EXTRA
from function.globals.get_paths import PATHS
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER


def make_gray(img, mode: str):
    """
    将图片转换为灰度图
    mode->贡献点、成员名称
    """
    # 检查是否有Alpha通道 将RGBA转换为BGR
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    # 默认掩码
    lower_bound = np.array([254, 189, 0])
    upper_bound = np.array([255, 190, 0])
    match mode:
        case "成员名称":
            # 将白色的成员名称(RGB 255 255 255)转化为黑色，其余则为白色
            lower_bound = np.array([254, 254, 254])
            upper_bound = np.array([255, 255, 255])
        case "贡献点":
            # 将所有文本颜色(RGB 255 190 0)转化为黑色，其余则为白色
            lower_bound = np.array([254, 189, 0])
            upper_bound = np.array([255, 190, 0])
        case "周贡献点":
            # 将所有文本颜色(RGB 120 210 0)转化为黑色，其余则为白色
            lower_bound = np.array([119, 209, 0])
            upper_bound = np.array([120, 210, 0])
    mask = cv2.inRange(img, lower_bound, upper_bound)

    # 图片中非字体转化为白色
    img[mask > 0] = [0, 0, 0]

    # 字体转化为黑色
    img[mask == 0] = [255, 255, 255]
    # 转换为灰度图
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    return img_gray


def ocr_contribution(img, mode):
    """
    OCR识别图片中的数字，返回识别结果
    贡献点数字的高度为8，宽度为7；rgb颜色为(255, 190, 0)
    """
    # 获取灰度图
    img_gray = make_gray(img=img, mode=mode)

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


def _hash_image(img):
    # 将公会成员名称图片转换为唯一的哈希值
    return hashlib.sha256(img.tobytes()).hexdigest()


def save_image(image, path):
    if not os.path.exists(path):
        cv2.imencode('.png', image)[1].tofile(path)


class GuildManager:
    """
    公会管理工具，自动扫描并生成带日期的表格
    格式为：
    公会成员名称图片；日期；月贡；周贡；日贡；总贡；备注
    list[
        {
            name_image_hash:int;
            data:{
                date str: value int // 一天 一条数据
                、、、
            }
            data_week:{
                date str: value int // 一天 一条数据
                 、、、
            }
        },
        ... // 更多成员的数据
    ]
    """

    def __init__(self):

        self.members_data = []

        self.data_file = PATHS["logs"] + "\\guild_manager\\guild_manager_data.json"

        self.load_json()

    def load_json(self):
        """加载数据"""
        try:
            with EXTRA.FILE_LOCK:
                with open(file=self.data_file, mode='r', encoding='utf-8') as file:
                    self.members_data = json.load(file)
        except FileNotFoundError:
            # 如果文件不存在，则初始化
            self.members_data = []
        except json.JSONDecodeError:
            # 如果文件存在但不是有效的JSON格式，也初始化
            self.members_data = []

    def save_json(self):
        """保存数据到json文件"""
        with EXTRA.FILE_LOCK:
            with open(file=self.data_file, mode='w', encoding='utf-8') as file:
                json.dump(self.members_data, file, ensure_ascii=False, indent=4)

    def get_guild_member_page(self, handle, handle_360):
        """
        循环获取公会成员页面
        """
        img_old = None
        while True:
            for j in range(5):
                # 尝试五次获取，如果不与之前的图片重复则认为成功翻页，获取一次成员信息
                img = capture_image_png(
                    handle=handle,
                    raw_range=[484, 133, 908, 316],
                    root_handle=handle_360)
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
            T_ACTION_QUEUE_TIMER.add_click_to_queue(
                handle=handle, x=745, y=330)
            time.sleep(0.2)

    def get_guild_member_info(self, img):
        """
        截图，获取成员名称，职位，当前贡献
        """

        # 一页稳定有五个成员，按五行分布
        for i in range(5):
            # 每一行的高度是35，行间距为2。先获取第一行的图片
            img_member = img[37 * i:37 * i + 35, :]

            # 名称图片，用于识别是否是同一个人
            img_name = img_member[:, 0:93]
            img_name_grey = make_gray(img_name, "成员名称")

            # 贡献点图片，用于OCR数字来识别贡献点 高8 宽x
            img_contribution = img_member[5:13, 184:245]
            contribution = ocr_contribution(img=img_contribution, mode="贡献点")

            # 每周贡献点图片 用于OCR数字来识别贡献点 高8 宽x
            img_contribution_week = img_member[19:27, 184:245]
            contribution_week = ocr_contribution(img=img_contribution_week, mode="周贡献点")

            # 保存名称图片
            name_image_hash = _hash_image(img_name_grey)
            save_image(
                image=img_name_grey,
                path=f"{PATHS['logs']}\\guild_manager\\guild_member_images\\{name_image_hash}.png"
            )

            # 调试
            # print(contribution, contribution_week)

            # 如果存在贡献点，更新成员数据
            self.update_member_data(
                name_image_hash=name_image_hash,
                contribution=contribution,
                contribution_week=contribution_week,
                date=datetime.date.today().strftime('%Y-%m-%d')
            )

    def update_member_data(self, name_image_hash, contribution, contribution_week, date):
        """
        :param name_image_hash: 成员名称图片哈希值
        :param contribution: 总贡献点
        :param contribution_week: 周贡献点（游戏内数值）
        :param date: 数据获取日期 请转化为 str yyyy-MM-dd
        :return:
        """

        # 查找成员是否存在
        existing_member = (
            next(
                (member for member in self.members_data if member['name_image_hash'] == name_image_hash),
                None)
        )

        if existing_member is None:
            # 新成员，创建新条目
            new_member = {
                'name_image_hash': name_image_hash,
                'data': {date: contribution},
                'data_week': {date: contribution_week}
            }
            self.members_data.append(new_member)
        else:
            # 成员已存在，更新贡献数据, 先检查结构完整性
            if not existing_member.get('data'):
                existing_member['data'] = {}
            if not existing_member.get('data_week'):
                existing_member['data_week'] = {}
            existing_member['data'][date] = contribution
            existing_member['data_week'][date] = contribution_week

    def scan(self, handle, handle_360):
        """
        主流程函数：扫描公会成员信息，更新数据，并生成表格
        """
        # 加载数据
        self.load_json()

        # 获取公会成员页面，并更新数据
        self.get_guild_member_page(handle, handle_360)

        # 保存数据
        self.save_json()
