import os
import sys

from PyQt6 import uic, QtGui, QtCore, QtWidgets

from function.common.get_system_dpi import get_system_dpi
from function.globals import EXTRA
from function.globals.get_paths import PATHS
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
# noinspection PyUnresolvedReferences
from function.qrc import test_rc, theme_rc, GTRONICK_rc

# 虽然ide显示上面这行没用，但实际是用来加载相关资源的，不可删除,我用奇妙的方式强制加载了

ZOOM_RATE = None


def create_icon(color, mode):
    """
    绘制图表
    :param color: Q color
    :param mode: "-" "x" "<-" "->"
    :return:
    """
    pixmap = QtGui.QPixmap(16, 16)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)

    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

    # 绘制图标
    painter.setPen(QtGui.QPen(color, 2))
    match mode:
        case "x":
            painter.drawLine(3, 3, 13, 13)
            painter.drawLine(3, 13, 13, 3)
        case "-":
            painter.drawLine(3, 8, 13, 8)
        case "<-":
            painter.drawLine(2, 8, 14, 8)  # 主线
            painter.drawLine(2, 8, 6, 4)  # 左上角
            painter.drawLine(2, 8, 6, 12)  # 左下角
        case "->":
            painter.drawLine(2, 8, 14, 8)  # 主线
            painter.drawLine(14, 8, 10, 4)  # 右上角
            painter.drawLine(14, 8, 10, 12)  # 右下角
        case _:
            pass

    painter.end()

    return QtGui.QIcon(pixmap)


class QMainWindowLoadUI(QtWidgets.QMainWindow):
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

        # 设置显示版本号
        self.Title_Version.setText(EXTRA.VERSION)

        # 获取 dpi & zoom 仅能在类中调用
        self.zoom_rate = get_system_dpi() / 96
        T_ACTION_QUEUE_TIMER.set_zoom_rate(self.zoom_rate)

        # 获取系统样式(日夜)
        self.theme = self.get_theme()

        # 获取系统样式(高亮颜色)
        self.theme_highlight_color = QtWidgets.QApplication.palette().color(QtGui.QPalette.ColorRole.Highlight).name()

    def get_theme(self):
        if self.palette().color(QtGui.QPalette.ColorRole.Window).lightness() < 128:
            theme = "dark"
        else:
            theme = "light"
        return theme

    """任何ui都要设置的样式表"""

    def set_theme_common(self):
        # 进行特殊的无边框和阴影处理
        self.set_no_border()

        # 设置logo阴影
        self.set_logo_shadow()

        # 根据系统样式,设定开关图标
        self.set_exit_and_minimized_btn_icon()

        # 部分图片元素的加载
        self.set_image_resource()

    def set_logo_shadow(self):
        effect_shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        effect_shadow.setOffset(0, 0)  # 偏移
        effect_shadow.setBlurRadius(10)  # 阴影半径
        effect_shadow.setColor(QtCore.Qt.GlobalColor.gray)  # 阴影颜色
        self.Title_Logo.setGraphicsEffect(effect_shadow)  # 将设置套用到widget窗口中

    def set_no_border(self):
        # 设置无边框窗口
        self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint)

        # 设背景为透明
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_common_theme(self):

        style_sheet = self.styleSheet()

        # 增加边框
        style_sheet += "#MainFrame{border-radius: 8px; border: 1px solid #3c3d3e;} "

        style_sheet = self.styleSheet()

        # 获取当前样式表 然后在此基础上增加背景色, 根据白天黑夜主题为不同颜色
        match self.theme:
            case "dark":
                style_sheet += "#MainFrame{background-color: #1e1e1e;}"
            case "light":
                style_sheet += "#MainFrame{background-color: #FFFFFF;}"

        self.setStyleSheet(style_sheet)

    def set_exit_and_minimized_btn_icon(self):
        """
        设置退出按钮和最小化按钮样式，需已获取主题
        :return:
        """
        # 根据系统样式,设定开关图标
        color = QtGui.QColor(240, 240, 240) if self.theme == "dark" else QtGui.QColor(15, 15, 15)
        self.Button_Exit.setIcon(create_icon(color=color, mode="x"))
        self.Button_Minimized.setIcon(create_icon(color=color, mode="-"))

    def set_image_resource(self):

        # title - logo
        cus_path = PATHS["root"] + "\\resource\\logo\\圆角-FetTuo-48x.ico"
        cus_path = cus_path.replace("\\", "/")  # pyqt 使用正斜杠
        radius = 20
        style_sheet = f"""
            #Title_Logo{{
                min-width: {radius * 2}px;
                min-height: {radius * 2}px;
                max-width: {radius * 2}px;
                max-height: {radius * 2}px;
                border-radius: {radius}px;
                background-image: url({cus_path});
                background-repeat: no-repeat;
                background-position: center;
                background-size: {radius * 2}px {radius * 2}px;
            }}
        """
        self.Title_Logo.setStyleSheet(style_sheet)

        # 背景图
        cus_path = PATHS["root"] + "\\resource\\ui\\firefly.png"
        cus_path = cus_path.replace("\\", "/")  # pyqt 使用正斜杠
        style_sheet = f"""
            #SkinWidget{{
            border-radius: 8px;
            border-image: url({cus_path});
            background-repeat: no-repeat;
            background-position: center;
            background-size: cover;
            }}
        """

        self.SkinWidget.setStyleSheet(style_sheet)

    """仅默认ui需要设置的样式表"""

    def set_theme_default(self):

        # 初始化样式表
        self.MainFrame.setStyleSheet("")

        # 设置箭头特殊样式
        self.set_arrow_btn_icon()

        # 设置tab栏特殊样式
        self.set_tab_bar_style()

    def set_main_window_shadow(self):
        # 添加阴影
        effect_shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        effect_shadow.setOffset(0, 0)  # 偏移
        effect_shadow.setBlurRadius(8)  # 阴影半径
        effect_shadow.setColor(QtCore.Qt.GlobalColor.black)  # 阴影颜色
        self.MainFrame.setGraphicsEffect(effect_shadow)  # 将设置套用到widget窗口中

    def set_tab_bar_style(self):

        style_sheet = self.MainFrame.styleSheet()
        selected_text_color = "#FFFFFF" if self.theme == "dark" else "#000000"

        style_sheet += f"""
            QTabBar::tab {{
                min-width: 136px;  /* 最小宽度 */
                height: 20px;
                border-style: solid;
                border-top-color: transparent;
                border-right-color: transparent;
                border-left-color: transparent;
                border-bottom-color: transparent;
                border-bottom-width: 1px;
                border-style: solid;
                color: #808086;
                padding: 3px;
                margin-left:3px;
            }}
            QTabBar::tab:selected, QTabBar::tab:last:selected, QTabBar::tab:hover {{
                border-style: solid;
                border-top-color: transparent;
                border-right-color: transparent;
                border-left-color: transparent;
                border-bottom-color: {self.theme_highlight_color};
                border-bottom-width: 2px;
                border-style: solid;
                color: {selected_text_color};
                padding-left: 3px;
                padding-bottom: 2px;
                margin-left:3px;
            }}
            QTabWidget::tab-bar {{
                alignment: center;
            }}
            QTabWidget::pane{{
                border:none;
            }}
            """

        self.MainFrame.setStyleSheet(style_sheet)

    def set_arrow_btn_icon(self):

        # 设置图标
        color = QtGui.QColor(240, 240, 240) if self.theme == "dark" else QtGui.QColor(15, 15, 15)
        prev_icon = create_icon(color=color, mode="<-")
        next_icon = create_icon(color=color, mode="->")

        # 找到前后月份按钮
        prev_month_button = self.DateSelector.findChild(QtWidgets.QToolButton, "qt_calendar_prevmonth")
        next_month_button = self.DateSelector.findChild(QtWidgets.QToolButton, "qt_calendar_nextmonth")

        prev_month_button.setIcon(prev_icon)
        next_month_button.setIcon(next_icon)

    """重写拖动窗口"""

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
        if self.childAt(a0.pos().x(), a0.pos().y()).objectName() == "FrameTitle":
            # 判断鼠标按下的是左键
            if a0.button() == QtCore.Qt.MouseButton.LeftButton:
                self._isTracking = True
                # 记录初始位置
                self._startPos = QtCore.QPoint(a0.pos().x(), a0.pos().y())

    # 鼠标松开事件
    def mouseReleaseEvent(self, a0: QtGui.QMouseEvent):
        if a0.button() == QtCore.Qt.MouseButton.LeftButton:
            self._isTracking = False
            self._startPos = None
            self._endPos = None


if __name__ == "__main__":
    def main():
        # 实例化 PyQt后台管理
        app = QtWidgets.QApplication(sys.argv)

        # 实例化 主窗口
        my_main_window = QMainWindowLoadUI()

        my_main_window.show()

        # 运行主循环，必须调用此函数才可以开始事件处理
        app.exec()

        sys.exit()


    main()
