import os
import sys

from PyQt6 import uic, QtGui, QtCore
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QPen, QIcon, QColor
from PyQt6.QtWidgets import QMainWindow, QApplication

from function.common.get_system_dpi import get_system_dpi
from function.globals.get_paths import PATHS
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER

# 虽然ide显示下面这行没用，但实际是用来加载相关资源的，不可删除

ZOOM_RATE = None


def create_icon(color,mode):
    """
    绘制图表
    :param color: Q color
    :param mode: "-"和"x"
    :return:
    """
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # 绘制图标
    painter.setPen(QPen(color, 2))
    match mode:
        case "x":
            painter.drawLine(3, 3, 13, 13)
            painter.drawLine(3, 13, 13, 3)
        case "-":
            painter.drawLine(3, 8, 13, 8)
    painter.end()

    return QIcon(pixmap)


class QMainWindowLoadUI(QMainWindow):
    """读取.ui文件创建类 并加上一些常用方法"""

    # 注意：
    # 若ui界面文件是个对话框，那么MyApp就必须继承 QDialog
    # 若ui界面文件是个MainWindow，那么MyApp就必须继承 QMainWindow
    def __init__(self):
        # 继承父方法
        super().__init__()

        # 加载 ui文件
        uic.loadUi(PATHS["root"] + '\\resource\\ui\\FAA_3.0.ui', self)

        # 设置窗口名称
        self.setWindowTitle("FAA - 本软件免费且开源")

        # 设置版本号
        self.version = "v1.5.0-beta.3"
        self.Label_Version.setText(self.version)

        # 获取 dpi & zoom 仅能在类中调用
        self.zoom_rate = get_system_dpi() / 96
        T_ACTION_QUEUE_TIMER.set_zoom_rate(self.zoom_rate)

        # 获取系统样式(日夜)
        if self.palette().color(QtGui.QPalette.ColorRole.Window).lightness() < 128:
            self.theme = "dark"
        else:
            self.theme = "light"

        # 根据系统样式,设定开关图标
        color = QColor(240, 240, 240) if self.theme == "dark" else QColor(15, 15, 15)
        self.Button_Exit.setIcon(create_icon(color=color,mode="x"))
        self.Button_Minimized.setIcon(create_icon(color=color,mode="-"))

    def closeEvent(self, event):
        """
        对MainWindow的函数closeEvent进行重构, 退出软件时弹窗提醒 并且结束所有进程(和内部的线程)
        """

        event.accept()
        # 用过sys.exit(0)和sys.exit(app.exec())，但没起效果
        os._exit(0)

    # 切换最大化与正常大小
    def maxOrNormal(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # 弹出警告提示窗口确认是否要关闭
    def queryExit(self):
        QtCore.QCoreApplication.instance().exit()

    _startPos = None
    _endPos = None
    _isTracking = None

    # 鼠标移动事件
    def mouseMoveEvent(self, a0: QtGui.QMouseEvent):
        if self._startPos:
            self._endPos = a0.pos() - self._startPos
            # 移动窗口
            self.move(self.pos() + self._endPos)

    # 鼠标按下事件
    def mousePressEvent(self, a0: QtGui.QMouseEvent):
        # 根据鼠标按下时的位置判断是否在QFrame范围内
        if self.childAt(a0.pos().x(), a0.pos().y()).objectName() == "title_tag":
            # 判断鼠标按下的是左键
            if a0.button() == Qt.MouseButton.LeftButton:
                self._isTracking = True
                # 记录初始位置
                self._startPos = QtCore.QPoint(a0.pos().x(), a0.pos().y())

    # 鼠标松开事件
    def mouseReleaseEvent(self, a0: QtGui.QMouseEvent):
        if a0.button() == Qt.MouseButton.LeftButton:
            self._isTracking = False
            self._startPos = None
            self._endPos = None


if __name__ == "__main__":
    def main():
        # 实例化 PyQt后台管理
        app = QApplication(sys.argv)

        # 实例化 主窗口
        my_main_window = QMainWindowLoadUI()

        my_main_window.show()

        # 运行主循环，必须调用此函数才可以开始事件处理
        sys.exit(app.exec())


    main()
