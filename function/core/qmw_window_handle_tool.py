import numpy as np
import win32con
import win32gui
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QGroupBox, QLabel, QLineEdit, QPushButton, QVBoxLayout,
)

from function.common.bg_img_screenshot import capture_image_png_all
from function.globals.log import CUS_LOGGER
from function.scattered.gat_handle import faa_get_handle


GAME_WINDOW_CLASS = "NativeWindowClass"
GAME_CLIENT_SIZES = {(950, 596), (950, 600)}


class WindowDragTarget(QLabel):
    """将一次拖拽松开的目标窗口交给当前角色的设置面板。"""

    window_picked = pyqtSignal(object)

    def __init__(self, player: int):
        super().__init__(f"按住并拖动到{player}P窗口 获取句柄")
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(32)
        self.setFrameShape(QLabel.Shape.StyledPanel)
        self.dragging = False

    def mousePressEvent(self, event):
        """记录在本拖拽框内按下的左键。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            event.accept()

    def mouseReleaseEvent(self, event):
        """按释放位置获取最上层的窗口，并解析其根窗口。"""
        if self.dragging and event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            try:
                # 使用同一 Win32 坐标系，避免高 DPI 下 Qt 逻辑坐标与屏幕坐标混用。
                target = win32gui.WindowFromPoint(win32gui.GetCursorPos())
                root = win32gui.GetAncestor(target, win32con.GA_ROOT) if target else 0
            except win32gui.error:
                # 窗口可能在松开鼠标时关闭，此时清除本次目标，让用户重新拖取。
                root = 0
            self.window_picked.emit(root)
            event.accept()


class PlayerWindowPanel(QGroupBox):
    """显示一个角色的窗口信息，并用对应客户区测试截图。"""

    window_selected = pyqtSignal(int, str)

    def __init__(self, player: int, channel: str):
        super().__init__(f"{player}P")
        self.player = player
        self.root_handle = faa_get_handle(channel, mode="360") if channel else 0
        self.window_title = QLineEdit(channel)
        self.handle_text = QLineEdit()
        self.class_text = QLineEdit()
        for field in (self.window_title, self.handle_text, self.class_text):
            field.setReadOnly(True)
        self.status = QLabel()
        self.status.setWordWrap(True)

        drag_target = WindowDragTarget(player)
        drag_target.window_picked.connect(self.select_window)
        capture_button = QPushButton("测试获取图像")
        capture_button.clicked.connect(self.test_capture)

        layout = QFormLayout(self)
        layout.addRow("窗口全名", self.window_title)
        layout.addRow("截图句柄", self.handle_text)
        layout.addRow("窗口类名", self.class_text)
        layout.addRow(self.status)
        layout.addRow(drag_target)
        layout.addRow(capture_button)
        self.refresh_target()

    def select_window(self, root: int) -> None:
        """诊断所选窗口，并把有效的游戏大厅窗口名同步到 FAA。"""
        self.root_handle = root
        self.window_title.clear()
        self.refresh_target()
        if self.is_game_root and self.window_title.text():
            self.window_selected.emit(self.player, self.window_title.text())

    def refresh_target(self) -> tuple[int, list[str]]:
        """刷新截图句柄和窗口诊断。Flash 重建后重新查找游戏客户区。"""
        warnings = []
        handle = 0
        class_name = ""
        self.is_game_root = False
        try:
            if self.root_handle and win32gui.IsWindow(self.root_handle):
                title = win32gui.GetWindowText(self.root_handle)
                self.window_title.setText(title)
                root_class = win32gui.GetClassName(self.root_handle)
                self.is_game_root = root_class == "DUIWindow"
                handle = self.root_handle
                if self.is_game_root and title:
                    game = faa_get_handle(title, mode="flash")
                    if game and win32gui.IsChild(self.root_handle, game):
                        handle = game
                class_name = win32gui.GetClassName(handle)
                if class_name != GAME_WINDOW_CLASS:
                    warnings.append(f"窗口类名为 {class_name}，游戏客户区应为 {GAME_WINDOW_CLASS}。"
                                    "请进入游戏后重新拖取。")
                left, top, right, bottom = win32gui.GetClientRect(handle)
                width, height = right - left, bottom - top
                if (width, height) not in GAME_CLIENT_SIZES:
                    warnings.append(f"客户区为 {width}×{height}，标准游戏画面为 950×596 或 950×600。"
                                    "请检查窗口大小。")
            else:
                warnings.append("未找到窗口，请重新拖取。")
        except win32gui.error as error:
            # 刷新或关闭会使句柄失效，本次截图作废并等待用户重新拖取。
            CUS_LOGGER.warning(f"[窗口句柄] [{self.player}P] 无法读取句柄 {handle}：{error}")
            handle = 0
            self.is_game_root = False
            warnings.append("窗口已失效，请重新拖取。")

        self.handle_text.setText(str(handle) if handle else "")
        self.class_text.setText(class_name if handle else "")
        self.status.setText("\n".join(warnings) or "已找到游戏客户区。")
        return handle, warnings

    def test_capture(self) -> None:
        """弹出本次截图，同时说明画面、类名和客户区尺寸的问题。"""
        handle, warnings = self.refresh_target()
        image = None
        if handle:
            try:
                image = capture_image_png_all(handle, self.root_handle)
            except (win32gui.error, OSError, ValueError) as error:
                # 窗口刷新时截图可能失败，保留本次诊断并提示重新截取。
                CUS_LOGGER.warning(f"[窗口句柄] [{self.player}P] 句柄 {handle} 截图失败：{error}")

        preview = QDialog(self)
        preview.setWindowTitle(f"{self.player}P 截图测试")
        layout = QVBoxLayout(preview)
        has_image = image is not None and image.size > 0
        if not has_image or not np.any(image[:, :, :3]):
            warnings.append("未获取到有游戏画面请重新截取")
        status = QLabel("\n".join(warnings) or "已获取到游戏画面。")
        status.setWordWrap(True)
        layout.addWidget(status)
        if has_image:
            pixels = np.ascontiguousarray(image[:, :, :3])
            height, width = pixels.shape[:2]
            frame = QImage(pixels.data, width, height, pixels.strides[0], QImage.Format.Format_BGR888)
            screen_size = preview.screen().availableGeometry().size()
            pixmap = QPixmap.fromImage(frame).scaled(
                min(width, int(screen_size.width() * 0.85)),
                min(height, int(screen_size.height() * 0.75)),
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
            )
            picture = QLabel()
            picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
            picture.setPixmap(pixmap)
            layout.addWidget(picture)
        preview.exec()
        preview.deleteLater()


class QMWWindowHandleTool(QDialog):
    """FAA 内置窗口句柄工具，仅展示当前模式下使用的角色。"""

    window_selected = pyqtSignal(int, str)

    def __init__(self, parent, channels: dict[int, str]):
        super().__init__(parent)
        self.setWindowTitle("获取窗口句柄")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        for player, channel in channels.items():
            panel = PlayerWindowPanel(player, channel)
            panel.window_selected.connect(self.window_selected)
            layout.addWidget(panel)
