# coding:utf-8

import sys
from pathlib import Path

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QMainWindow, QApplication, QCheckBox, QLineEdit, QComboBox, QPushButton, QLabel, QWidget


def initialize_dic_p(num_process):
    dic_p = {
        "flag_activation": {},  # 记录进程当前状态
        "dic_process_opt": {},  # 进程内函数的参数字典
        "process": {},  # 保存进程对象地址
        "weiget_id": {},  # 保存控件主id
    }
    for p_id in range(num_process):
        dic_p["flag_activation"][p_id] = False
        dic_p["dic_process_opt"][p_id] = {}
        dic_p["process"][p_id] = None
        dic_p["weiget_id"][p_id] = int(p_id * 2 + 1)
    return dic_p


class MyMainWindow(QMainWindow):
    # 注意：
    # 若ui界面文件是个对话框，那么MyApp就必须继承 QDialog
    # 若ui界面文件是个MainWindow，那么MyApp就必须继承 QMainWindow
    def __init__(self, num_p):
        """
        Args:
            num_p: number of process
        """
        # 继承父方法
        super().__init__()

        # 加载 ui文件
        # self.path_root = str(Path(__file__).resolve().parent.parent)  # 资源文件路径
        # uic.loadUi(self.path_root + '\\resource\\fvm\\ui\\fvm.ui', self)

        # 最大线程数
        self.num_process = num_p

        # 初始化进程状态和参数表
        # self.dic_p = initialize_dic_p(self.num_process)

        # 初始化 进程内函数的参数字典
        # for p_id in range(self.num_process):
        #     self.refresh_process_parameter(p_id)

        # 初始化 dpi参数
        # self.dpi = 1
        # self.refresh_dpi()

    def refresh_process_parameter(self, p_id):
        """
        用于获取进程参数表的最新数据
        Args:
            p_id: 进程编号
        """
        # boolean 是否激活
        self.dic_p["dic_process_opt"][p_id]["activation"] = (
            self.findChild(QCheckBox, "E_{}_1_1".format(p_id * 2 + 1)).isChecked()
        )

        # boolean 是否使用钥匙
        self.dic_p["dic_process_opt"][p_id]["use_key"] = (
            self.findChild(QCheckBox, "E_{}_1_2".format(p_id * 2 + 1)).isChecked()
        )

        # boolean 是否使用自动战斗
        self.dic_p["dic_process_opt"][p_id]["use_card"] = (
            self.findChild(QCheckBox, "E_{}_1_3".format(p_id * 2 + 1)).isChecked()
        )

        # int 战斗次数
        self.dic_p["dic_process_opt"][p_id]["battle_time_max"] = int(
            self.findChild(QLineEdit, "E_{}_3_2_2".format(p_id * 2 + 1)).text()
        )

        # str 频道文本
        self.dic_p["dic_process_opt"][p_id]["channel"] = (
            self.findChild(QComboBox, "E_{}_5_1_2".format(p_id * 2 + 1)).currentText()
        )

    def refresh_dpi(self):
        """
        刷新dpi
        """
        self.dpi = float(self.findChild(QLineEdit, "E_9_2").text())

    def refresh_data(self, cmd_dic):
        """接受信号函数"""
        # dic = {"process_id": ,"key":, "value":}
        if cmd_dic["key"] == "completed_count":
            (self.findChild(QLabel, "E_{}_3_3_2".format(cmd_dic["process_id"] * 2 + 1))
             .setText(str(cmd_dic["value"])))
        if cmd_dic["key"] == "auto_handle":
            (self.findChild(QLabel, "E_{}_5_2_2".format(cmd_dic["process_id"] * 2 + 1))
             .setText(str(cmd_dic["value"])))
        if cmd_dic["key"] == "completed_used_time":
            (self.findChild(QLabel, "E_{}_5_3_2".format(cmd_dic["process_id"] * 2 + 1))
             .setText(str(cmd_dic["value"])))
        if cmd_dic["key"] == "process_status":
            (self.findChild(QLabel, "E_{}_7_2".format(cmd_dic["process_id"] * 2 + 1))
             .setText(str(cmd_dic["value"])))


if __name__ == "__main__":
    def main():
        # 进程总数
        num_process = 4

        # 实例化 PyQt后台管理
        app = QApplication(sys.argv)

        # 实例化 主窗口
        my_main_window = MyMainWindow(num_process)

        my_main_window.show()

        # 运行主循环，必须调用此函数才可以开始事件处理
        sys.exit(app.exec_())


    main()
