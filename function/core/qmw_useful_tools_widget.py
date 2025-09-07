import sys
from function.globals.loadings import loading
loading.update_progress(75,"正在加载妙妙小工具...")
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QIcon
from PyQt6.QtWidgets import (
    QWidget, QApplication, QVBoxLayout, QPushButton, QLabel, QComboBox, QHBoxLayout, QSpacerItem, QSizePolicy, QFrame
)

from function.globals import SIGNAL
from function.globals.get_paths import PATHS
from function.globals.thread_action_queue import T_ACTION_QUEUE_TIMER
from function.scattered.gat_handle import faa_get_handle
from function.scattered.get_channel_name import get_channel_name
from function.tools.useful_tools import *


class Magnifier(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(200, 200)
        self.setStyleSheet("background-color: rgba(255, 255, 255, 150); border: 1px solid black;")

    def update_view(self, x, y):
        screen = QApplication.primaryScreen()
        region_size = 10
        half = region_size // 2

        # 获取屏幕设备像素比（解决高DPI屏幕问题）
        ratio = screen.devicePixelRatio()

        # 精确捕获物理像素（需要转换为QImage操作）
        pixmap = screen.grabWindow(
            0,
            int((x - half) * ratio),  # 物理像素坐标
            int((y - half) * ratio),
            int(region_size * ratio),  # 物理像素尺寸
            int(region_size * ratio))
        img = pixmap.toImage()  # 转换为QImage进行像素级操作

        # 创建放大画布
        pixel_size = 20  # 每个物理像素放大20倍
        scaled = QPixmap(region_size * pixel_size, region_size * pixel_size)
        scaled.fill(Qt.GlobalColor.transparent)

        painter = QPainter(scaled)

        # 直接使用原始像素颜色填充放大块
        for i in range(region_size):
            for j in range(region_size):
                # 读取原始物理像素颜色（考虑缩放比例）
                color = img.pixelColor(int(i * ratio), int(j * ratio))

                # 绘制纯色方块（避免任何图像处理）
                painter.fillRect(
                    i * pixel_size,
                    j * pixel_size,
                    pixel_size,
                    pixel_size,
                    color
                )

        # 绘制黑色网格（加强像素边界）
        painter.setPen(QPen(QColor(0, 0, 0, 100), 1))  # 半透明黑色细线
        for pos in range(0, scaled.width() + 1, pixel_size):
            painter.drawLine(pos, 0, pos, scaled.height())
            painter.drawLine(0, pos, scaled.width(), pos)

        # 红色中心十字（保持原有样式）
        painter.setPen(QPen(QColor(255, 0, 0), 2))
        center = scaled.rect().center()
        painter.drawLine(center.x(), 0, center.x(), scaled.height())
        painter.drawLine(0, center.y(), scaled.width(), center.y())

        painter.end()

        self.setPixmap(scaled)
        self.move(x + 20, y + 20)


class DraggablePointer(QLabel):
    position_changed = pyqtSignal(int, int)
    drag_started = pyqtSignal()
    drag_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setPixmap(QPixmap(f"{PATHS['logo']}\\圆角-FetDeathWing-450x.png").scaled(32, 32))
        self.setFixedSize(32, 32)
        self.drag_offset = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_started.emit()
            self.drag_offset = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            global_pos = event.globalPosition().toPoint()
            self.position_changed.emit(global_pos.x(), global_pos.y())

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.drag_finished.emit()


class UsefulToolsWidget(QWidget):
    def __init__(self, faa=None):
        super().__init__()
        self.target_handle = None
        self.channel_2p = None
        self.channel_1p = None
        self.faa = faa

        self.setWindowTitle("实用小工具")
        self.setWindowIcon(QIcon(PATHS["logo"] + "\\圆角-FetDeathWing-450x.png"))
        self.setFixedSize(300, 250)

        self.gacha_thread: GachaGoldThread | None = None

        """init ui控件"""

        layout = QVBoxLayout()
        self.setLayout(layout)

        layout_wish_pool = QVBoxLayout()
        layout.addLayout(layout_wish_pool)

        label_title = QLabel("许愿池抽取")
        label_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_wish_pool.addWidget(label_title)

        handel_layout = QHBoxLayout()
        layout_wish_pool.addLayout(handel_layout)

        self.current_window = QLabel("目标窗口选择")
        handel_layout.addWidget(self.current_window)

        self.target_window = QComboBox()
        self.target_window.addItem("P1")
        self.target_window.addItem("P2")
        self.target_window.currentIndexChanged.connect(self.select_target_window)
        handel_layout.addWidget(self.target_window)

        gold_layout = QHBoxLayout()
        layout_wish_pool.addLayout(gold_layout)

        self.btn_gold_start = QPushButton("开始抽金币许愿池")
        self.btn_gold_start.clicked.connect(self.on_gold_clicked)
        gold_layout.addWidget(self.btn_gold_start)

        self.btn_gold_stop = QPushButton("停止抽金币许愿池")
        self.btn_gold_stop.clicked.connect(self.on_gold_stop_clicked)
        gold_layout.addWidget(self.btn_gold_stop)

        # 停止按钮初始状态设为禁用
        self.btn_gold_stop.setEnabled(False)

        # 插入竖向弹簧
        vertical_spacer1 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        layout.addItem(vertical_spacer1)

        # 插入横向分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # 插入另一个竖向弹簧
        vertical_spacer2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        layout.addItem(vertical_spacer2)

        layout_magnifier = QVBoxLayout()
        layout.addLayout(layout_magnifier)

        label_title = QLabel("开发用 - 放大镜")
        label_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_magnifier.addWidget(label_title)

        note_label = QLabel("拖动图标,获取鼠标在目标窗口的坐标")
        layout_magnifier.addWidget(note_label)

        self.label_position = QLabel("当前位置：未获取")
        self.label_position.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_magnifier.addWidget(self.label_position)

        # 创建一个新的横向布局，用于包含 self.pointer 和横向弹簧
        pointer_layout = QHBoxLayout()
        layout_magnifier.addLayout(pointer_layout)

        # 添加左侧横向弹簧
        horizontal_spacer_left = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        pointer_layout.addItem(horizontal_spacer_left)

        # 拖动开启放大镜的图标
        self.pointer = DraggablePointer()
        pointer_layout.addWidget(self.pointer)

        # 添加右侧横向弹簧
        horizontal_spacer_right = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        pointer_layout.addItem(horizontal_spacer_right)

        # 放大镜本体
        self.magnifier = Magnifier()

        # 交互
        self.pointer.drag_started.connect(self.magnifier.show)
        self.pointer.drag_finished.connect(self.magnifier.hide)
        self.pointer.position_changed.connect(self.update_ui)

    def try_get_handle(self):
        self.channel_1p, self.channel_2p = get_channel_name(
            game_name=self.faa.opt["base_settings"]["game_name"],
            name_1p=self.faa.opt["base_settings"]["name_1p"],
            name_2p=self.faa.opt["base_settings"]["name_2p"])
        self.target_handle = faa_get_handle(channel=self.channel_1p, mode="flash")

        return self.target_handle

    def update_ui(self, x, y):
        self.magnifier.update_view(x, y)
        relative_x, relative_y = get_pixel_position(self.target_handle, x, y)
        self.label_position.setText(f"捕获位置：({relative_x}, {relative_y})")

    def select_target_window(self, index):
        self.target_handle = faa_get_handle(
            channel=self.channel_1p if index == 0 else self.channel_2p,
            mode="flash"
        )

    def on_gold_clicked(self):
        #print("执行金币许愿池操作...")
        self.gacha_thread = GachaGoldThread(self.target_handle)
        self.btn_gold_start.setEnabled(False)
        self.btn_gold_stop.setEnabled(True)
        self.gacha_thread.start()

    def on_gold_stop_clicked(self):
        #print("停止执行金币许愿池操作...")
        if self.gacha_thread:
            self.gacha_thread.stop()
            self.gacha_thread.wait()
            self.gacha_thread = None
        self.btn_gold_start.setEnabled(True)
        self.btn_gold_stop.setEnabled(False)

    def closeEvent(self, event):
        self.pointer.close()
        self.magnifier.close()
        super().closeEvent(event)


class GachaGoldThread(QThread):
    def __init__(self, handle):
        super().__init__()
        self.handle = handle
        self._is_running = False  # 线程运行状态标识

    def run(self):
        """线程主循环"""
        self._is_running = True
        T_ACTION_QUEUE_TIMER.start()
        while self._is_running:
            # 执行单次许愿池操作
            result, message = once_gacha_gold_trevi_fountain(self.handle)
            if not result:
                # 出现错误，停止线程并弹窗
                SIGNAL.DIALOG.emit(
                    "出错！(╬◣д◢)",
                    message)
                self.stop()
                break

    def stop(self):
        """安全停止线程"""
        T_ACTION_QUEUE_TIMER.stop()
        self._is_running = False
        self.wait()  # 等待线程完全退出


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UsefulToolsWidget()
    window.resize(300, 200)
    window.show()
    sys.exit(app.exec())
