"""FAA 视角的旁路观测；关闭时不保存截图、点击或识图数据。"""

import math
import os
import time
import weakref
from collections import OrderedDict, deque
from threading import Lock


class FAAViewEvents:
    """按所选句柄收集有限数量的事件，不通过 Qt 信号堆积战斗消息。"""

    def __init__(self):
        self.handle = 0
        self.show_clicks = True
        self.show_recognition = True
        self._lock = Lock()
        self._clicks = deque(maxlen=160)
        self._matches = OrderedDict()
        self._images = OrderedDict()
        self._names = {}

    def select(self, handle: int, names: dict | None = None):
        """切换观测句柄并清除旧玩家数据；0 表示停止观测。"""
        with self._lock:
            self.handle = handle
            self._clicks.clear()
            self._matches.clear()
            self._images.clear()
            if names is not None:
                self._names = names
            if not handle and names is None:
                self._names.clear()

    def configure(self, clicks: bool, recognition: bool):
        """关闭某种效果时立即清理对应的短期数据。"""
        with self._lock:
            self.show_clicks = clicks
            self.show_recognition = recognition
            if not clicks:
                self._clicks.clear()
            if not recognition:
                self._matches.clear()
                self._images.clear()

    def remember_image(self, image, handle: int):
        """用弱引用记录截图来源，供数组切片识图还原全窗口坐标。"""
        if not self.handle or handle != self.handle or not self.show_recognition:
            return
        if image is None or not image.size:
            return
        with self._lock:
            if handle != self.handle:
                return
            # NumPy 切片常直接指向一维 base；同时登记 base，不复制游戏截图。
            root = image
            while getattr(root, "base", None) is not None and hasattr(root.base, "__array_interface__"):
                root = root.base
            origin = (image.__array_interface__["data"][0], image.strides[0], image.strides[1])
            for item in (image, root):
                self._images[id(item)] = (weakref.ref(item), handle, origin)
                self._images.move_to_end(id(item))
            while len(self._images) > 256:
                self._images.popitem(last=False)

    def image_origin(self, image):
        """返回数组在窗口中的 (句柄, 左, 上)；独立导入图片不推测玩家。"""
        if not self.handle or not self.show_recognition:
            return None
        with self._lock:
            current = image
            while current is not None:
                record = self._images.get(id(current))
                if record and record[0]() is current and record[1] == self.handle:
                    pointer, row_stride, pixel_stride = record[2]
                    delta = image.__array_interface__["data"][0] - pointer
                    y, remainder = divmod(delta, row_stride)
                    x = remainder // pixel_stride
                    return record[1], x, y
                current = getattr(current, "base", None)
        return None

    def click(self, handle: int, x: float, y: float):
        """仅记录已投递到游戏窗口的实际点击位置。"""
        if not self.handle or handle != self.handle or not self.show_clicks:
            return
        with self._lock:
            if handle == self.handle and self.show_clicks:
                self._clicks.append((time.monotonic(), x, y))

    def match(self, origin, template, name: str, rect, score: float, threshold: float, found: bool):
        """保存匹配框和分数；坐标基于截图原点，保留未达到阈值的结果供排查。"""
        if origin is None or not self.handle or not self.show_recognition or not math.isfinite(score):
            return
        handle, left, top = origin
        with self._lock:
            if handle != self.handle or not self.show_recognition:
                return
            if name == "Unknown":
                resource = self._names.get(id(template))
                name = resource[1] if resource and resource[0]() is template else f"临时模板 {template.shape[1]}×{template.shape[0]}"
            name = os.path.basename(name)
            bounds = (rect[0] + left, rect[1] + top, rect[2] + left, rect[3] + top)
            key = (name, bounds)
            self._matches[key] = (time.monotonic(), name, bounds, score, threshold, found)
            self._matches.move_to_end(key)
            while len(self._matches) > 80:
                self._matches.popitem(last=False)

    def snapshot(self):
        """读取短暂有效的点击及识图事件，限制画面拥挤和长期内存占用。"""
        now = time.monotonic()
        with self._lock:
            clicks = [item for item in self._clicks if now - item[0] < 0.65]
            matches = [item for item in self._matches.values() if now - item[0] < 1.2]
        return clicks, matches

    def consume_senior_result(self, result):
        """读取高级战斗已有队列的诊断数据，并原样返回策略信息。

        Args:
            result: 带窗口句柄与置信度的新版消息，或旧版五项策略元组。

        Returns:
            原有策略元组；关闭工具、玩家不符或消息过期时不保存诊断数据。
        """
        if not isinstance(result, dict):
            return result
        if (self.handle and self.show_recognition and result["view_handle"] == self.handle
                and time.monotonic() - result["observed_at"] < 1.2):
            for name, bounds, score in result["view_matches"]:
                self.match((result["view_handle"], 0, 0), None, name, bounds, score, 0.25, True)
        return result["information"]


FAA_VIEW_EVENTS = FAAViewEvents()
