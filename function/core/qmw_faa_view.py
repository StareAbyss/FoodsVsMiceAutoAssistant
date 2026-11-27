"""实时查看 FAA 所选玩家的游戏画面或 360 大厅画面，并可独立录制带诊断特效的视频。"""

import ctypes
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

from function.common.bg_img_screenshot import capture_image_png, capture_image_png_all
from function.common.faa_view_events import FAA_VIEW_EVENTS
from function.globals import EXTRA, g_resources
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER
from function.scattered.gat_handle import faa_get_handle
from function.scattered.get_channel_name import get_channel_name


VIEW_FPS = 20
VIEW_WIDTH = 950
VIEW_DEBUG_ROWS = 6
# 底部信息条：一行字幕 + 若干行识图调试文本，所有画面来源共用。
BOTTOM_BAR_HEIGHT = 28 + VIEW_DEBUG_ROWS * 22
VIEW_HEIGHT = 600 + BOTTOM_BAR_HEIGHT

GAME_RANGE = [0, 0, 950, 600]

# 画面来源：游戏客户区是 Flash 层；大厅内容层与大厅外框用于登录、选服等未进入游戏的阶段。
SOURCE_GAME = "游戏客户区"
SOURCE_HALL_CONTENT = "大厅内容层"
SOURCE_HALL_FRAME = "大厅外框"
SOURCES = (SOURCE_GAME, SOURCE_HALL_CONTENT, SOURCE_HALL_FRAME)


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


def hall_crop_scale(handle: int) -> float:
    """返回 DWM 放大大厅窗口的倍数，用于裁掉窗口 DC 里未绘制的黑边。

    360 大厅是 DPI 不感知程序：它在 96 DPI 坐标系里按约 950×668 逻辑像素绘制，
    由 Windows 按系统缩放拉伸显示。窗口 DC 的 BitBlt 只返回拉伸前的绘制结果，
    所以内容固定在左上角，右侧和下方是黑边。只有“窗口按 96 DPI 绘制、系统实际
    缩放更高”时才需要裁剪；DPI 感知窗口直接返回 1.0，避免裁掉真实内容。

    Args:
        handle: 大厅目标窗口句柄。

    Returns:
        系统缩放比，例如 150% 缩放返回 1.5；无法判断时返回 1.0。
    """
    user32 = ctypes.windll.user32
    try:
        window_dpi = user32.GetDpiForWindow(handle)
        system_dpi = user32.GetDpiForSystem()
    except AttributeError:
        return 1.0
    if window_dpi == 96 and system_dpi > 96:
        return system_dpi / 96
    return 1.0


def capture_hall_image(handle: int, root: int) -> np.ndarray:
    """抓取大厅客户区，并按 DPI 缩放裁掉未绘制的黑边。

    Args:
        handle: 大厅目标窗口句柄（内容层或外框层）。
        root: 360 外壳句柄，用于窗口最小化时尝试恢复。

    Returns:
        BGRA 截图；内容只保留实际绘制区域，坐标原点仍在左上角。
    """
    image = capture_image_png_all(handle, root)
    scale = hall_crop_scale(handle)
    if scale > 1.0 and image.size:
        height, width = image.shape[:2]
        image = image[:max(1, round(height / scale)), :max(1, round(width / scale))]
    return image


def resolve_window(channel: str, source: str) -> tuple[int, int]:
    """按画面来源解析外层窗口与目标层句柄。

    Args:
        channel: FAA 保存的玩家窗口频道名。
        source: 画面来源，取值见 SOURCES。

    Returns:
        (root, handle)；root 为 360 外壳句柄，handle 为要截图的层。
        找不到窗口时对应值为 0，且不再继续往下层查找，避免误取另一个玩家的窗口。
    """
    root = faa_get_handle(channel, mode="360") if channel else 0
    if not root:
        return 0, 0
    if source == SOURCE_HALL_FRAME:
        # 外框层就是 360 外壳本身，不需要再往下找子窗口。
        return root, root
    handle = faa_get_handle(channel, mode="browser" if source == SOURCE_HALL_CONTENT else "flash")
    if handle and not win32gui.IsChild(root, handle):
        handle = 0
    return root, handle


def compose_view_frame(image, clicks, matches, message: str = "", font: QFont | None = None,
                       output_size: QSize | None = None, canvas_size: QSize | None = None,
                       caption: str | None = None) -> QImage:
    """合成预览和录像共同使用的画面，避免只录到没有特效的原始截图。

    Args:
        image: 截图，最大 950×600 的游戏客户区或大厅实际绘制区域；None 表示窗口尚不可用。
        clicks: 近期实际点击事件 (时间, x, y)。
        matches: 近期识图事件 (时间, 名称, 全窗口框, 分数, 阈值, 是否命中)。
        message: 无可用截图时显示的原因。
        font: 主线程加载的 FAA 字体，保证录制中文标签不依赖系统字体。
        output_size: 可选输出物理像素尺寸；预览直接在最终分辨率绘制文字，录像保持固定尺寸。
        canvas_size: 画布逻辑尺寸（画面 + 底部信息条）；None 时按 950×760 的游戏默认尺寸。
        caption: 底部字幕；None 时使用通用说明。

    Returns:
        包含画面、点击动画、目标框及匹配度说明的 RGB 图像。
    """
    base = canvas_size or QSize(VIEW_WIDTH, VIEW_HEIGHT)
    frame = QImage(output_size or base, QImage.Format.Format_RGB888)
    frame.fill(QColor("#111827"))
    painter = QPainter(frame)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.scale(frame.width() / base.width(), frame.height() / base.height())
    overlay_font = QFont(font if font is not None else get_view_font())
    painter.setFont(overlay_font)
    picture_width = base.width()
    picture_height = base.height() - BOTTOM_BAR_HEIGHT
    if image is not None:
        rgb = np.ascontiguousarray(image[:, :, :3][:, :, ::-1])
        game = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format.Format_RGB888)
        # 客户区实测可能比画布小；按原坐标绘制，缺少的边缘留底色，不拉伸目标框。
        painter.drawImage(0, 0, game)
    else:
        painter.setPen(QColor("#cbd5e1"))
        painter.drawText(QRectF(0, 0, picture_width, picture_height), Qt.AlignmentFlag.AlignCenter, message)

    # 特效绘制与画面来源无关：大厅层和游戏客户区共用同一套坐标，不按来源换算法。
    for _, name, bounds, score, threshold, found in matches[-18:]:
        if not found:
            continue
        x1, y1, x2, y2 = bounds
        painter.setPen(QPen(QColor("#4ade80"), 2))
        painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))
        label = f"{name}  {score:.1%}"
        width = min(picture_width, painter.fontMetrics().horizontalAdvance(label) + 12)
        label_rect = QRectF(max(0, min(x1, picture_width - width)), max(0, y1 - 24), width, 24)
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

    painter.fillRect(0, picture_height, picture_width, BOTTOM_BAR_HEIGHT, QColor("#1e293b"))
    painter.setPen(QColor("#e2e8f0"))
    text = caption or "FAA视角 · 黄色：点击 · 绿色：识图命中 · 百分比：匹配度 / YOLO置信度"
    text = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, picture_width - 24)
    painter.drawText(12, picture_height + 22, text)
    for row, (_, name, bounds, score, threshold, found) in enumerate(matches[-VIEW_DEBUG_ROWS:]):
        painter.setPen(QColor("#4ade80" if found else "#fbbf24"))
        line = f"{'找到' if found else '未达到阈值'}  {name}  {score:.2%} / 阈值 {threshold:.2%}"
        line = painter.fontMetrics().elidedText(line, Qt.TextElideMode.ElideRight, picture_width - 24)
        painter.drawText(12, picture_height + 44 + row * 22, line)
    if not matches:
        painter.setPen(QColor("#f1f5f9"))
        painter.drawText(12, picture_height + 50, "等待 FAA 识图事件；查看识图效果不会额外执行识别或操作游戏。")
    painter.end()
    return frame


def frame_to_bgr(frame: QImage) -> np.ndarray:
    """把合成后的 RGB QImage 转成 BGR 数组，按实际宽度处理行对齐填充。

    Args:
        frame: compose_view_frame() 的输出。

    Returns:
        高度和宽度与 frame 一致的 BGR 数组。
    """
    width, height = frame.width(), frame.height()
    pixels = frame.constBits()
    pixels.setsize(frame.sizeInBytes())
    rgb = np.frombuffer(pixels, np.uint8).reshape(height, frame.bytesPerLine())
    rgb = rgb[:, :width * 3].reshape(height, width, 3)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def fit_frame(image: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """把当前画布缩放到录像锁定尺寸，比例不一致时补黑边。

    录像开始后玩家、画面来源和尺寸都不再允许变化；窗口被缩放或大厅重新布局时，
    用黑边补齐可以保证同一个 MP4 的分辨率恒定，避免编码器写入失败。

    Args:
        image: 当前画布图像（BGR 或 BGRA）。
        size: 录像锁定的 (宽, 高)。

    Returns:
        与 size 完全一致的 BGR 图像。
    """
    width, height = size
    if image.shape[1] == width and image.shape[0] == height:
        return image
    scale = min(width / image.shape[1], height / image.shape[0])
    target_w = max(1, int(image.shape[1] * scale))
    target_h = max(1, int(image.shape[0] * scale))
    resized = cv2.resize(image, (target_w, target_h), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    left = (width - target_w) // 2
    top = (height - target_h) // 2
    canvas[top:top + target_h, left:left + target_w] = resized
    return canvas


def unavailable_message(source: str) -> str:
    """返回所选来源找不到窗口时的等待提示。"""
    if source == SOURCE_GAME:
        return "未找到所选玩家的游戏窗口，请检查 FAA 玩家窗口设置并进入游戏。"
    if source == SOURCE_HALL_CONTENT:
        return "未找到所选玩家的大厅内容层，请确认 360 大厅已打开并完成页面加载。"
    return "未找到所选玩家的 360 大厅窗口，请确认 360 大厅已打开。"


def refresh_message(source: str) -> str:
    """返回截图异常时的提示；大厅刷新同样会让句柄短暂失效。"""
    return "游戏窗口正在刷新，等待恢复…" if source == SOURCE_GAME else "大厅窗口正在刷新，等待恢复…"


class FAAViewWorker(Thread):
    """在后台采集和编码，主线程只取最新帧，避免录像拖慢主窗口。"""

    def __init__(self, channel: str, names: dict | None = None, source: str = SOURCE_GAME):
        super().__init__(name="FAA视角", daemon=True)
        self._channel = channel
        self._source = source
        self._names = names or {}
        # 字体数据库只能在主线程初始化，采集线程只使用已加载的字体副本。
        self._font = get_view_font()
        self._lock = Lock()
        self._stop_event = Event()
        self._commands = queue.SimpleQueue()
        self._frame = None
        self._scene = None
        self._canvas = QSize(VIEW_WIDTH, VIEW_HEIGHT)
        self._ready = False
        self._recording = False
        self._notice = ""
        self._writer = None
        self._path = ""
        self._written = 0
        self._record_started = 0.0
        self._record_size = (VIEW_WIDTH, VIEW_HEIGHT)

    def set_channel(self, channel: str):
        """切换预览玩家，下一帧重新获取窗口，旧帧不用于开始录像。"""
        with self._lock:
            self._channel = channel
            self._ready = False
            self._frame = None
            self._scene = None

    def set_source(self, source: str):
        """切换画面来源，下一帧重新解析窗口层级并清除旧场景。"""
        with self._lock:
            self._source = source
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
            canvas = QSize(self._canvas)
        if scene is None or available_size.isEmpty():
            return None
        size = canvas.scaled(available_size, Qt.AspectRatioMode.KeepAspectRatio)
        physical_size = QSize(max(1, round(size.width() * device_pixel_ratio)),
                              max(1, round(size.height() * device_pixel_ratio)))
        frame = compose_view_frame(*scene, font=self._font, output_size=physical_size, canvas_size=canvas)
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

    def _capture_scene(self, handle: int, root: int, source: str):
        """按画面来源截图并给出等待提示。

        Returns:
            (image, message)；image 为 None 时 message 说明原因。
        """
        if source == SOURCE_GAME:
            captured = capture_image_png(handle, GAME_RANGE, root)
        else:
            captured = capture_hall_image(handle, root)
        if captured is not None and captured.size and np.any(captured[:, :, :3]):
            return captured, ""
        if captured is None or not captured.size:
            return None, unavailable_message(source)
        height, width = captured.shape[:2]
        return None, f"截图为空或 RGB 全黑（{width}×{height}），等待画面恢复…"

    def _canvas_size_for(self, source: str, image) -> QSize:
        """按来源与实际截图尺寸计算画布大小。

        游戏客户区沿用 950×760 的固定画布，保持既有录像规格；大厅按实际绘制区域
        计算，宽度不小于 950，保证点击与识图坐标仍在同一左上原点上。
        """
        if image is None or source == SOURCE_GAME:
            return QSize(VIEW_WIDTH, VIEW_HEIGHT)
        height, width = image.shape[:2]
        return QSize(max(VIEW_WIDTH, width), height + BOTTOM_BAR_HEIGHT)

    def run(self):
        """以固定目标帧率采集，窗口刷新时重取句柄，异常不影响 FAA 执行线程。"""
        root = handle = 0
        channel = None
        source = None
        next_lookup = 0.0
        failure = ""
        canvas = QSize(VIEW_WIDTH, VIEW_HEIGHT)
        try:
            while not self._stop_event.is_set():
                started = time.monotonic()
                with self._lock:
                    requested_channel = self._channel
                    requested_source = self._source
                if (requested_channel != channel or requested_source != source
                        or started >= next_lookup or (handle and not win32gui.IsWindow(handle))):
                    channel = requested_channel
                    source = requested_source
                    # 外层窗口不存在时禁止沿句柄 0 查找，防止串到另一个玩家。
                    root, handle = resolve_window(channel, source)
                    next_lookup = started + 1
                    if FAA_VIEW_EVENTS.handle != handle:
                        FAA_VIEW_EVENTS.select(handle, self._names)

                image = None
                message = unavailable_message(source)
                if handle:
                    try:
                        image, message = self._capture_scene(handle, root, source)
                        if image is not None:
                            failure = ""
                    except Exception as exc:
                        # Flash 刷新或大厅页面重建都会让句柄失效；本次只丢弃预览帧，下一轮重新查找。
                        message = refresh_message(source)
                        handle = 0
                        next_lookup = 0
                        if failure != str(exc):
                            CUS_LOGGER.warning(f"[FAA视角] [截图] 玩家窗口 {channel} 采集失败：{exc}")
                            failure = str(exc)
                canvas = self._canvas_size_for(source, image)
                # 没有可用截图时不再读取事件，避免把上一帧的点击和识图画到新画布上。
                if image is not None:
                    clicks, matches = FAA_VIEW_EVENTS.snapshot()
                else:
                    clicks, matches = [], []
                caption = f"FAA视角 · {source} · 黄色：点击 · 绿色：识图命中 · 百分比：匹配度 / YOLO置信度"
                frame = compose_view_frame(image, clicks, matches, message, self._font,
                                           canvas_size=canvas, caption=caption)

                while not self._commands.empty():
                    path = self._commands.get()
                    if path is None:
                        self._finish_recording()
                    elif self._writer is None:
                        try:
                            if image is None:
                                raise ValueError("所选画面尚不可用，请在画面恢复后开始录制。")
                            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                            # 录像分辨率取偶数，避免部分编码器对奇数宽高写出失败。
                            record_w = canvas.width() - canvas.width() % 2
                            record_h = canvas.height() - canvas.height() % 2
                            writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), VIEW_FPS,
                                                     (record_w, record_h))
                            if not writer.isOpened():
                                writer.release()
                                raise OSError("无法打开 MP4 编码器，请检查保存路径和文件权限。")
                            self._writer = writer
                            self._path = path
                            self._written = 0
                            self._record_size = (record_w, record_h)
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
                        bgr = fit_frame(frame_to_bgr(frame), self._record_size)
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
                    if channel == self._channel and source == self._source:
                        self._frame = frame
                        self._canvas = QSize(canvas)
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
        controls.addWidget(QLabel("画面来源"))
        self.source = QComboBox()
        self.source.addItems(list(SOURCES))
        self.source.setToolTip("游戏客户区＝进游戏后的 Flash 画面；大厅内容层与外框用于登录、选服阶段。")
        self.source.wheelEvent = lambda event: event.ignore()
        controls.addWidget(self.source)
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
        hint = QLabel("实时预览始终开启 · 可切换 1P/2P 与画面来源 · 点击效果来自 FAA 实际执行的点击 · "
                      "录制包含画面及当前特效，无声音")
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
        self.source.currentIndexChanged.connect(self._change_source)
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

    def _source(self):
        """读取当前画面来源。"""
        return SOURCES[self.source.currentIndex()]

    def _change_player(self):
        """切换预览玩家时立即清理旧玩家帧和特效。"""
        if self.worker:
            self.worker.set_channel(self._channel())
            self.preview.clear()
            self.preview.setText("正在切换玩家…")
            self.start_button.setEnabled(False)

    def _change_source(self):
        """切换画面来源时重新解析窗口并清理旧画面。"""
        if self.worker:
            self.worker.set_source(self._source())
            self.preview.clear()
            self.preview.setText("正在切换画面来源…")
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
        self.source.setEnabled(False)
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
            self.status.setText("实时预览中（未录制）" if ready else "等待所选画面的窗口…")
        self.player.setEnabled(not recording and not self._recording_pending)
        self.source.setEnabled(not recording and not self._recording_pending)
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
            self.worker = FAAViewWorker(self._channel(), names, self._source())
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
        self.source.setEnabled(True)
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
