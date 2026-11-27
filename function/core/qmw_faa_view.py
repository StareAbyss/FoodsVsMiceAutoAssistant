"""实时查看 FAA 所选玩家的游戏画面，并可独立录制带诊断特效的视频。"""

import datetime
import os
import queue
import time
import weakref
from threading import Event, Lock, Thread

import cv2
import numpy as np
import win32gui
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from function.common.bg_img_screenshot import capture_image_png
from function.common.faa_view_events import FAA_VIEW_EVENTS
from function.globals import EXTRA, g_resources
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from function.scattered.gat_handle import faa_get_handle
from function.scattered.get_channel_name import get_channel_name


VIEW_FPS = 20
VIEW_WIDTH = 950
VIEW_DEBUG_ROWS = 6
VIEW_HEIGHT = 600 + 28 + VIEW_DEBUG_ROWS * 22


def get_view_font() -> QFont:
    """在主线程选择清晰的中文正文字体；系统字体缺失时沿用 FAA 随附字体。"""
    fallback = EXTRA.Q_FONT
    families = QFontDatabase.families()
    family = next((name for name in ("Microsoft YaHei UI", "Microsoft YaHei") if name in families), fallback.family())
    font = QFont(family)
    font.setStyle(QFont.Style.StyleNormal)
    font.setWeight(QFont.Weight.Medium)
    font.setPixelSize(18)
    return font


def compose_view_frame(image, clicks, matches, message: str = "", font: QFont | None = None,
                       output_size: QSize | None = None) -> QImage:
    """合成预览和录像共同使用的画面，避免只录到没有特效的原始截图。

    Args:
        image: 最大 950×600 的 BGR/BGRA 游戏截图，客户区可能略小；None 表示窗口尚不可用。
        clicks: 近期实际点击事件 (时间, x, y)。
        matches: 近期识图事件 (时间, 名称, 全窗口框, 分数, 阈值, 是否命中)。
        message: 无可用游戏截图时显示的原因。
        font: 主线程加载的 FAA 字体，保证录制中文标签不依赖系统字体。
        output_size: 可选输出物理像素尺寸；预览直接在最终分辨率绘制文字，录像保持固定尺寸。

    Returns:
        包含游戏、点击动画、目标框及匹配度说明的 RGB 图像。
    """
    frame = QImage(output_size or QSize(VIEW_WIDTH, VIEW_HEIGHT), QImage.Format.Format_RGB888)
    frame.fill(QColor("#111827"))
    painter = QPainter(frame)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.scale(frame.width() / VIEW_WIDTH, frame.height() / VIEW_HEIGHT)
    overlay_font = QFont(font if font is not None else get_view_font())
    painter.setFont(overlay_font)
    if image is not None:
        rgb = np.ascontiguousarray(image[:, :, :3][:, :, ::-1])
        game = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format.Format_RGB888)
        # 客户区实测可能为 950×596；按原坐标绘制，缺少的边缘留底色，不拉伸目标框。
        painter.drawImage(0, 0, game)
        for _, name, bounds, score, threshold, found in matches[-18:]:
            if not found:
                continue
            x1, y1, x2, y2 = bounds
            painter.setPen(QPen(QColor("#4ade80"), 2))
            painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))
            label = f"{name}  {score:.1%}"
            width = min(VIEW_WIDTH, painter.fontMetrics().horizontalAdvance(label) + 12)
            label_rect = QRectF(max(0, min(x1, VIEW_WIDTH - width)), max(0, y1 - 24), width, 24)
            painter.fillRect(label_rect, QColor(15, 23, 42, 225))
            painter.drawText(label_rect.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter, label)
        now = time.monotonic()
        for timestamp, x, y in clicks:
            progress = min(1.0, max(0.0, (now - timestamp) / 0.65))
            alpha = int(255 * (1 - progress))
            painter.setPen(QPen(QColor(255, 193, 7, alpha), 3))
            painter.setBrush(QColor(255, 193, 7, alpha // 5))
            radius = 7 + progress * 24
            painter.drawEllipse(QPointF(x, y), radius, radius)
            painter.drawLine(QPointF(x - 6, y), QPointF(x + 6, y))
            painter.drawLine(QPointF(x, y - 6), QPointF(x, y + 6))
            painter.setBrush(Qt.BrushStyle.NoBrush)
    else:
        painter.setPen(QColor("#cbd5e1"))
        painter.drawText(QRectF(0, 0, VIEW_WIDTH, 600), Qt.AlignmentFlag.AlignCenter, message)

    painter.fillRect(0, 600, VIEW_WIDTH, VIEW_HEIGHT - 600, QColor("#1e293b"))
    painter.setPen(QColor("#e2e8f0"))
    caption = "FAA视角 · 黄色：点击 · 绿色：识图命中 · 百分比：匹配度 / YOLO置信度"
    caption = painter.fontMetrics().elidedText(caption, Qt.TextElideMode.ElideRight, VIEW_WIDTH - 24)
    painter.drawText(12, 622, caption)
    for row, (_, name, bounds, score, threshold, found) in enumerate(matches[-VIEW_DEBUG_ROWS:]):
        painter.setPen(QColor("#4ade80" if found else "#fbbf24"))
        text = f"{'找到' if found else '未达到阈值'}  {name}  {score:.2%} / 阈值 {threshold:.2%}"
        text = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, VIEW_WIDTH - 24)
        painter.drawText(12, 644 + row * 22, text)
    if not matches:
        painter.setPen(QColor("#f1f5f9"))
        painter.drawText(12, 650, "等待 FAA 识图事件；查看识图效果不会额外执行识别或操作游戏。")
    painter.end()
    return frame


class FAAViewWorker(Thread):
    """在后台采集和编码，主线程只取最新帧，避免录像拖慢主窗口。"""

    def __init__(self, channel: str, names: dict | None = None):
        super().__init__(name="FAA视角", daemon=True)
        self._channel = channel
        self._names = names or {}
        # 字体数据库只能在主线程初始化，采集线程只使用已加载的字体副本。
        self._font = get_view_font()
        self._lock = Lock()
        self._stop_event = Event()
        self._commands = queue.SimpleQueue()
        self._frame = None
        self._scene = None
        self._ready = False
        self._recording = False
        self._notice = ""
        self._writer = None
        self._path = ""
        self._written = 0
        self._record_started = 0.0

    def set_channel(self, channel: str):
        """切换预览玩家，下一帧重新获取窗口，旧帧不用于开始录像。"""
        with self._lock:
            self._channel = channel
            self._ready = False
            self._frame = None
            self._scene = None

    def request_recording(self, path: str | None):
        """传入保存路径开始录像，None 表示仅停止录像并继续预览。"""
        self._commands.put(path)

    def snapshot(self):
        """供 UI 读取最新帧、窗口可用性、录像状态和一次性通知。"""
        with self._lock:
            result = self._frame, self._ready, self._recording, self._notice
            self._notice = ""
        return result

    def render_preview(self, available_size: QSize, device_pixel_ratio: float) -> QImage | None:
        """按预览控件的物理像素合成文字，避免固定录像帧缩放后发糊。

        Args:
            available_size: 控件可用的逻辑像素尺寸。
            device_pixel_ratio: 当前屏幕的物理像素与逻辑像素之比。

        Returns:
            按比例适配且带正确 DPI 标记的图像；未采集到场景时返回 None。
        """
        with self._lock:
            scene = self._scene
        if scene is None or available_size.isEmpty():
            return None
        size = QSize(VIEW_WIDTH, VIEW_HEIGHT).scaled(available_size, Qt.AspectRatioMode.KeepAspectRatio)
        physical_size = QSize(max(1, round(size.width() * device_pixel_ratio)),
                              max(1, round(size.height() * device_pixel_ratio)))
        frame = compose_view_frame(*scene, font=self._font, output_size=physical_size)
        frame.setDevicePixelRatio(device_pixel_ratio)
        return frame

    def stop(self):
        """停止后台采集；等待编码器释放，确保 MP4 尾部索引写入。"""
        self._stop_event.set()
        self.join()

    def _finish_recording(self):
        """关闭编码器并保留已录内容，窗口丢失或工具关闭也可完成文件。"""
        if self._writer is None:
            return
        self._writer.release()
        self._writer = None
        with self._lock:
            self._recording = False
            self._notice = f"录制已保存：{self._path}"
        CUS_LOGGER.info(f"[FAA视角] [录制] 保存完成：{self._path}，帧数：{self._written}")

    def run(self):
        """以固定目标帧率采集，窗口刷新时重取句柄，异常不影响 FAA 执行线程。"""
        handle = root = 0
        channel = None
        next_lookup = 0.0
        failure = ""
        try:
            while not self._stop_event.is_set():
                started = time.monotonic()
                with self._lock:
                    requested_channel = self._channel
                if requested_channel != channel or started >= next_lookup or (handle and not win32gui.IsWindow(handle)):
                    channel = requested_channel
                    # 外层窗口不存在时禁止沿句柄 0 查找，防止串到另一个玩家。
                    root = faa_get_handle(channel, mode="360") if channel else 0
                    handle = faa_get_handle(channel, mode="flash") if root else 0
                    if handle and not win32gui.IsChild(root, handle):
                        handle = 0
                    next_lookup = started + 1
                    if FAA_VIEW_EVENTS.handle != handle:
                        FAA_VIEW_EVENTS.select(handle, self._names)

                image = None
                message = "未找到所选玩家的游戏窗口，请检查 FAA 玩家窗口设置并进入游戏。"
                if handle:
                    try:
                        captured = capture_image_png(handle, [0, 0, 950, 600], root)
                        # 950×600 是 FAA 的坐标范围，不是客户区必须满足的精确尺寸。
                        # 检查真实 RGB 内容，避免少数黑色采样点或 BGRA 的 Alpha 导致误判。
                        if captured.size and np.any(captured[:, :, :3]):
                            image = captured
                            failure = ""
                        else:
                            height, width = captured.shape[:2]
                            message = f"截图为空或 RGB 全黑（{width}×{height}），等待游戏画面恢复…"
                    except Exception as exc:
                        # Flash 刷新会让句柄失效；本次只丢弃预览帧，下一轮重新查找。
                        message = "游戏窗口正在刷新，等待恢复…"
                        handle = 0
                        next_lookup = 0
                        if failure != str(exc):
                            CUS_LOGGER.warning(f"[FAA视角] [截图] 玩家窗口 {channel} 采集失败：{exc}")
                            failure = str(exc)
                clicks, matches = FAA_VIEW_EVENTS.snapshot() if image is not None else ([], [])
                frame = compose_view_frame(image, clicks, matches, message, self._font)

                while not self._commands.empty():
                    path = self._commands.get()
                    if path is None:
                        self._finish_recording()
                    elif self._writer is None:
                        try:
                            if image is None:
                                raise ValueError("所选玩家画面尚不可用，请在画面恢复后开始录制。")
                            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                            writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), VIEW_FPS,
                                                     (VIEW_WIDTH, VIEW_HEIGHT))
                            if not writer.isOpened():
                                writer.release()
                                raise OSError("无法打开 MP4 编码器，请检查保存路径和文件权限。")
                            self._writer = writer
                            self._path = path
                            self._written = 0
                            self._record_started = time.monotonic()
                            with self._lock:
                                self._recording = True
                                self._notice = f"正在录制：{path}"
                        except Exception as exc:
                            # 文件或编码器不可用只取消这次录像，继续实时预览。
                            CUS_LOGGER.error(f"[FAA视角] [录制] 无法开始 {path}：{exc}")
                            with self._lock:
                                self._notice = f"录制失败：{exc}"

                if self._writer is not None:
                    try:
                        pixels = frame.constBits()
                        pixels.setsize(frame.sizeInBytes())
                        rgb = np.frombuffer(pixels, np.uint8).reshape(VIEW_HEIGHT, frame.bytesPerLine())
                        rgb = rgb[:, :VIEW_WIDTH * 3].reshape(VIEW_HEIGHT, VIEW_WIDTH, 3)
                        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                        # 偶发截图延迟时补帧，保持视频时长与实际录制时间一致。
                        expected = int((time.monotonic() - self._record_started) * VIEW_FPS) + 1
                        for _ in range(max(1, expected - self._written)):
                            self._writer.write(bgr)
                            self._written += 1
                    except Exception as exc:
                        self._finish_recording()
                        CUS_LOGGER.error(f"[FAA视角] [录制] 写入失败 {self._path}：{exc}")
                        with self._lock:
                            self._notice = f"录制中断，已尝试保存此前内容：{exc}"
                with self._lock:
                    if channel == self._channel:
                        self._frame = frame
                        # 保留一份最新场景，主线程可按实际屏幕 DPI 重绘文字；不积压历史截图。
                        self._scene = (image, clicks, matches, message)
                        self._ready = image is not None
                self._stop_event.wait(max(0, 1 / VIEW_FPS - (time.monotonic() - started)))
        except Exception as exc:
            # 旁路工具异常不能中止战斗，保留错误供 UI 显示，并在 finally 完成录像。
            CUS_LOGGER.exception(f"[FAA视角] [预览] 后台采集退出：{exc}")
            with self._lock:
                self._notice = f"预览已停止：{exc}；关闭工具后可重新打开。"
        finally:
            self._finish_recording()
            FAA_VIEW_EVENTS.select(0)
            with self._lock:
                self._ready = False


class QMWFAAView(QWidget):
    """打开即预览，录制为独立开关；隐藏或关闭后释放观测和视频资源。"""

    def __init__(self, owner):
        super().__init__(owner, Qt.WindowType.Window)
        self.owner = owner
        self.worker = None
        self.last_recording_path = ""
        self._recording_pending = False
        self.setWindowTitle("FAA视角")
        self.setFont(EXTRA.Q_FONT)
        self.setWindowIcon(owner.windowIcon())
        self.resize(1000, 888)
        self.setMinimumSize(640, 510)

        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("玩家"))
        self.player = QComboBox()
        self.player.addItems(["1P", "2P"])
        self.player.wheelEvent = lambda event: event.ignore()
        controls.addWidget(self.player)
        self.click_effect = QCheckBox("显示点击特效")
        self.click_effect.setChecked(True)
        self.recognition_effect = QCheckBox("查看识图效果")
        self.recognition_effect.setChecked(True)
        controls.addWidget(self.click_effect)
        controls.addWidget(self.recognition_effect)
        controls.addStretch()
        self.start_button = QPushButton("开始录制")
        self.stop_button = QPushButton("停止录制")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        layout.addLayout(controls)
        self.preview = QLabel("打开后实时预览")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.preview.setStyleSheet("background: #111827; color: #cbd5e1; border-radius: 6px;")
        layout.addWidget(self.preview, 1)
        hint = QLabel("实时预览始终开启 · 点击效果来自 FAA 实际执行的点击 · 录制包含画面及当前特效，无声音")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.status = QLabel("等待游戏画面")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status)

        def update_effects():
            """勾选开关同时控制预览和录像合成，不额外执行识图。"""
            FAA_VIEW_EVENTS.configure(self.click_effect.isChecked(), self.recognition_effect.isChecked())

        def stop_recording():
            """仅停止编码，玩家画面继续实时显示。"""
            if self.worker:
                self.worker.request_recording(None)
                self._recording_pending = True
                self.stop_button.setEnabled(False)

        self.player.currentIndexChanged.connect(self._change_player)
        self.click_effect.toggled.connect(update_effects)
        self.recognition_effect.toggled.connect(update_effects)
        self.start_button.clicked.connect(self._start_recording)
        self.stop_button.clicked.connect(stop_recording)
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._update_preview)

    def _channel(self):
        """读取 FAA 当前保存的玩家窗口设置。"""
        settings = self.owner.opt["base_settings"]
        channels = get_channel_name(settings["game_name"], settings["name_1p"], settings["name_2p"])
        return channels[self.player.currentIndex()]

    def _change_player(self):
        """切换预览玩家时立即清理旧玩家帧和特效。"""
        if self.worker:
            self.worker.set_channel(self._channel())
            self.preview.clear()
            self.preview.setText("正在切换玩家…")
            self.start_button.setEnabled(False)

    def _start_recording(self):
        """选择 MP4 保存位置后交给后台编码；取消选择不改变预览。"""
        directory = os.path.join(PATHS["logs"], "recording")
        filename = f"FAA视角_{self.player.currentText()}_{datetime.datetime.now():%Y%m%d_%H%M%S_%f}.mp4"
        path, _ = QFileDialog.getSaveFileName(self, "保存 FAA视角录像", os.path.join(directory, filename), "MP4 视频 (*.mp4)")
        if not path or not self.worker:
            return
        if not path.lower().endswith(".mp4"):
            path += ".mp4"
        self.last_recording_path = path
        self._recording_pending = True
        self.start_button.setEnabled(False)
        self.player.setEnabled(False)
        self.worker.request_recording(path)

    def _update_preview(self):
        """主线程只展示后台最新一帧，大小变化按比例缩放，不积压信号。"""
        if not self.worker:
            return
        _, ready, recording, notice = self.worker.snapshot()
        preview_frame = self.worker.render_preview(self.preview.size(), self.preview.devicePixelRatioF())
        if preview_frame is not None:
            self.preview.setPixmap(QPixmap.fromImage(preview_frame))
        if notice:
            self._recording_pending = False
            self.status.setText(notice)
            if notice.startswith("录制失败"):
                QMessageBox.warning(self, "FAA视角", notice)
        elif not recording and not self.last_recording_path:
            self.status.setText("实时预览中（未录制）" if ready else "等待所选玩家的游戏画面…")
        self.player.setEnabled(not recording and not self._recording_pending)
        self.start_button.setEnabled(ready and not recording and not self._recording_pending)
        self.stop_button.setEnabled(recording and not self._recording_pending)

    def showEvent(self, event):
        """真正打开工具时才启动采集及观测，不在 FAA 启动时创建工作线程。"""
        super().showEvent(event)
        if self.worker is None:
            names = {}

            def collect_names(resources):
                """建立资源数组名称索引，不复制模板像素。"""
                for name, value in resources.items():
                    if isinstance(value, dict):
                        collect_names(value)
                    elif isinstance(value, np.ndarray):
                        names[id(value)] = (weakref.ref(value), name)

            collect_names(g_resources.RESOURCE_P)
            FAA_VIEW_EVENTS.configure(self.click_effect.isChecked(), self.recognition_effect.isChecked())
            self.worker = FAAViewWorker(self._channel(), names)
            self.worker.start()
            self.timer.start()

    def shutdown(self):
        """关闭采集和录像；FAA 主窗口强制退出前也必须调用此方法。"""
        self.timer.stop()
        if self.worker is not None:
            self.worker.stop()
            _, _, _, notice = self.worker.snapshot()
            if notice:
                self.status.setText(notice)
            self.worker = None
        FAA_VIEW_EVENTS.select(0)
        self._recording_pending = False
        self.player.setEnabled(True)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.preview.clear()

    def hideEvent(self, event):
        """关闭或隐藏工具都恢复静默；最小化仍可持续录制。"""
        if not self.isMinimized():
            self.shutdown()
        super().hideEvent(event)

    def closeEvent(self, event):
        """允许关闭窗口，同时完成正在录制的 MP4。"""
        self.shutdown()
        super().closeEvent(event)
