# NEW_FILE_CODE
import sys
import ctypes
from ctypes import windll
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt

from function.scattered.gat_handle import faa_get_handle


class POINT(ctypes.Structure):
    """Windows POINT结构体"""
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    """Windows RECT结构体"""
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]



def get_scaling_factor():
    """获取窗口缩放比例（处理高DPI）"""
    hdc = windll.user32.GetDC(0)
    # 获取屏幕的水平DPI
    my_dpi = windll.gdi32.GetDeviceCaps(hdc, 88)  # 88 is the index for LOGPIXELSX
    windll.user32.ReleaseDC(0, hdc)
    return my_dpi / 96.0


class WindowCoordinateViewer(QWidget):
    def __init__(self):
        super().__init__()

        # 初始化设置
        self.init_ui()

        # 获取目标窗口句柄（示例配置）
        self.handle = faa_get_handle(channel="微端", mode="flash")

        # 创建定时器用于更新坐标
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_coordinates)
        self.timer.start(100)  # 每100毫秒更新一次

        # 初始更新
        self.update_coordinates()

    def init_ui(self):
        """初始化界面"""
        # 设置窗口标题和大小
        self.setWindowTitle('窗口坐标查看器')
        self.setGeometry(100, 100, 300, 120)

        # 设置窗口始终置顶
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

        # 创建垂直布局
        layout = QVBoxLayout()

        # 创建标题标签
        title_label = QLabel('当前窗口相对坐标:', self)
        title_label.setStyleSheet("font-size: 16px; font-family: Consolas;")
        layout.addWidget(title_label)

        # 创建全局坐标标签
        self.global_label = QLabel('(0, 0)', self)
        self.global_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #1E90FF;")
        layout.addWidget(self.global_label)

        # 创建窗口相对坐标标签
        self.relative_label = QLabel('[0, 0]', self)
        self.relative_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #32CD32;")
        layout.addWidget(self.relative_label)

        # 设置布局
        self.setLayout(layout)

    def update_coordinates(self):
        """更新坐标信息"""
        if not self.handle:
            self.global_label.setText("未找到窗口")
            self.relative_label.setText("[无效句柄]")
            return

        # 获取鼠标全局坐标
        point = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        x_global, y_global = point.x, point.y

        # 计算缩放因子
        scaling_factor = get_scaling_factor()

        # 转换为窗口相对坐标
        rel_point = POINT(x_global, y_global)
        ctypes.windll.user32.ScreenToClient(self.handle, ctypes.byref(rel_point))

        # 获取窗口客户区尺寸
        rect = RECT()
        ctypes.windll.user32.GetClientRect(self.handle, ctypes.byref(rect))
        client_width = rect.right - rect.left
        client_height = rect.bottom - rect.top

        # 根据缩放调整坐标
        adjusted_x = int(rel_point.x / scaling_factor)
        adjusted_y = int(rel_point.y / scaling_factor)

        # 更新显示
        self.global_label.setText(f"({x_global}, {y_global})")
        self.relative_label.setText(f"[{adjusted_x}, {adjusted_y}]")

        # 根据坐标有效性改变颜色
        if adjusted_x < 0 or adjusted_y < 0 or adjusted_x > client_width or adjusted_y > client_height:
            self.relative_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #FF4500;")
        else:
            self.relative_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #32CD32;")


if __name__ == '__main__':
    # 创建应用程序实例
    app = QApplication(sys.argv)

    # 启用高DPI缩放支持（通过环境变量）
    import os

    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    # 创建并显示主窗口
    viewer = WindowCoordinateViewer()
    viewer.show()

    # 启动应用程序
    sys.exit(app.exec())
