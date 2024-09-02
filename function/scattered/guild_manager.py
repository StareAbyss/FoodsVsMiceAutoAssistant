import hashlib
import os
import time
import datetime
from collections import defaultdict

import pandas as pd

import cv2
import numpy as np

from function.common.bg_img_screenshot import capture_image_png
from function.common.same_size_match import match_block_equal_in_images
from function.globals import g_resources
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.globals.get_paths import PATHS


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
            # 将白色的成员名称转化为黑色，其余则为白色
            lower_bound = np.array([254, 254, 254])
            upper_bound = np.array([255, 255, 255])
        case "贡献点":
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


def ocr_contribution(img):
    """
    OCR识别图片中的数字，返回识别结果
    贡献点数字的高度为8，宽度为7；rgb颜色为(255, 190, 0)
    """
    # 获取灰度图
    img_gray = make_gray(img, "贡献点")

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


class GuildManager:
    """
    公会管理工具，自动扫描并生成带日期的表格
    格式为：
    公会成员名称图片；日期；月贡；周贡；日贡；总贡；备注
    """

    def __init__(self):
        # 初始化成员数据存储结构，使用字典嵌套字典的形式
        self.member_data = defaultdict(lambda: {
            "name_image": None,
            "name_image_hash": "",
            "dates": {},
            "status": "active"
        })
        self.data_file = PATHS["logs"] + "\\guild_manager\\guild_manager_data.csv"
        self.load_data()

    def _hash_image(self, img):
        # 将公会成员名称图片转换为唯一的哈希值
        return hashlib.sha256(img.tobytes()).hexdigest()

    def load_data(self):
        """从CSV文件加载数据，恢复成员信息"""
        if os.path.exists(self.data_file):
            df = pd.read_csv(self.data_file)
            for _, row in df.iterrows():
                member_hash = row["Member Hash"]
                self.member_data[member_hash]["name_image"] = cv2.imread(row["Name Image Path"])
                self.member_data[member_hash]["name_image_hash"] = member_hash
                self.member_data[member_hash]["status"] = row["Status"]
                self.member_data[member_hash]["dates"][row["Date"]] = {
                    "contribution": row["Total Contribution"]
                }
                if "Join Date" in row and not pd.isna(row["Join Date"]):
                    self.member_data[member_hash]["join_date"] = row["Join Date"]
                if "Exit Date" in row and not pd.isna(row["Exit Date"]):
                    self.member_data[member_hash]["exit_date"] = row["Exit Date"]

    def get_guild_member_page(self, handle, handle_360):
        """
        循环获取公会成员页面
        """
        img_old = None
        for i in range(20):
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

        current_members = set()
        # 一页稳定有五个成员，按五行分布
        for i in range(5):
            # 每一行的宽度是35，行间距为2。先获取第一行的图片
            img_member = img[37 * i:37 * i + 35, :]
            # 名称图片，用于识别是否是同一个人
            img_name = img_member[:, 0:93]
            img_name_grey = make_gray(img_name, "成员名称")
            # 贡献点图片，用于OCR数字来识别贡献点
            img_contribution = img_member[5:13, 184:245]
            contribution = ocr_contribution(img_contribution)

            # 如果存在贡献点，更新成员数据
            if contribution:
                member_hash = self._hash_image(img_name)
                current_members.add(member_hash)
                self.update_member_data(img_name_grey, contribution, datetime.date.today())
                if member_hash not in self.member_data:
                    self.add_new_member(img_name)

        self.mark_inactive_members(current_members)

    def update_member_data(self, img_name, contribution, date):
        """
        更新成员数据，img_name是成员名称图片，contribution是总贡献点，date是数据获取日期
        """
        member_hash = self._hash_image(img_name)

        # 检查成员是否存在，不存在则初始化
        if self.member_data[member_hash]["name_image_hash"] == "":
            self.member_data[member_hash]["name_image"] = img_name
            self.member_data[member_hash]["name_image_hash"] = member_hash

        # 更新贡献数据，按日期存储
        if date in self.member_data[member_hash]["dates"]:
            # 如果同一天已有数据且新数据更晚，更新
            if contribution > self.member_data[member_hash]["dates"][date]["contribution"]:
                self.member_data[member_hash]["dates"][date]["contribution"] = contribution
        else:
            # 存储新日期的数据
            self.member_data[member_hash]["dates"][date] = {
                "contribution": contribution
            }

    def mark_inactive_members(self, current_members):
        today = datetime.date.today()
        for member_hash, info in self.member_data.items():
            if info["status"] == "active" and member_hash not in current_members:
                self.member_data[member_hash]["status"] = "inactive"
                self.member_data[member_hash]["exit_date"] = today

    def add_new_member(self, img_name):
        """添加新成员"""
        member_hash = self._hash_image(img_name)
        if member_hash not in self.member_data:
            self.member_data[member_hash] = {
                "name_image": img_name,
                "name_image_hash": member_hash,
                "dates": {},
                "status": "active",
                "join_date": datetime.date.today()
            }

    def save_image(self, image, name_image_path):
        if not os.path.exists(name_image_path):
            cv2.imwrite(name_image_path, image)

    def make_table(self):
        """
        生成表格，输出为DataFrame，并按日期进行数据处理和排序
        """
        # 初始化表格结构
        columns = ["Name Image Path", "Member Hash", "Date", "Total Contribution", "Status", "Join Date", "Exit Date"]
        data = []

        for member_hash, info in self.member_data.items():
            for date, details in info["dates"].items():
                # 保存名称图片到文件（如果未保存过）
                name_image_path = f"{PATHS['logs']}\\guild_manager\\guild_member_images\\{member_hash}.png"
                self.save_image(info["name_image"], name_image_path)

                data.append([
                    name_image_path,
                    member_hash,
                    date,
                    details["contribution"],
                    info["status"],
                    info.get("join_date", ""),
                    info.get("exit_date", "")
                ])

        # 创建DataFrame
        df = pd.DataFrame(data, columns=columns)

        # 按成员哈希和日期排序
        df = df.sort_values(by=["Member Hash", "Date"])

        # 保存到CSV文件
        df.to_csv(f"{PATHS["logs"]}\\guild_manager\\guild_members_contributions.csv", index=False)

    def main(self, handle, handle_360):
        """
        主流程函数：扫描公会成员信息，更新数据，并生成表格
        """
        # 获取公会成员页面，并更新数据
        self.get_guild_member_page(handle, handle_360)

        # 用数据生成表格
        self.make_table()
