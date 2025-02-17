import json

from PyQt6 import uic
from PyQt6.QtWidgets import QWidget

from function.globals import EXTRA
from function.globals.get_paths import PATHS


class AdvancedSettingsWindow(QWidget):

    # 高级设置窗口
    def __init__(self):
        super().__init__()
        # 加载UI文件
        uic.loadUi(PATHS["root"] + '\\resource\\ui\\AdvancedSettings.ui', self)
        # 加载原有设置
        self.advanced_settings_path = PATHS["root"] + "\\config\\advanced_settings.json"
        self.advanced_settings = {}
        self.load_settings()
        # 初始化GUI数据
        self.init_settings()
        # 链接槽函数
        self.save_btn.clicked.connect(self.save_settings)
        # 给窗口设置标题
        self.setWindowTitle('高级设置')
        # 禁止调整窗口大小
        self.setFixedSize(self.size())

    def save_settings(self):
        # 保存设置
        # 将input数据写入字典中
        self.advanced_settings["gift_1p"] = self.gift_1p_input.text()
        self.advanced_settings["gift_2p"] = self.gift_2p_input.text()

        # 保存字典数据 自旋锁读写, 防止多线程读写问题
        with EXTRA.FILE_LOCK:
            with open(file=self.advanced_settings_path, mode='w', encoding='utf-8') as json_file:
                json.dump(self.advanced_settings, json_file, indent=4, ensure_ascii=False)

    def load_settings(self):
        with EXTRA.FILE_LOCK:
            with open(file=self.advanced_settings_path, mode='r', encoding='utf-8') as json_file:
                self.advanced_settings = json.load(json_file)

    def init_settings(self):
        # 根据读取到的数据来初始化GUI
        self.gift_1p_input.setText(str(self.advanced_settings["gift_1p"]))
        self.gift_2p_input.setText(str(self.advanced_settings["gift_2p"]))
