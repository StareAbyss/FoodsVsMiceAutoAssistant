"""不操作真实游戏，校验 FAA视角坐标、静默生命周期和实际 MP4 输出。"""

import gc
import os
import tempfile
import time
import unittest
import weakref
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QApplication, QWidget

from function.common.bg_img_match import match_all_p_in_w, match_p_in_w, match_ps_in_w
from function.common.faa_view_events import FAA_VIEW_EVENTS, FAAViewEvents
from function.core.qmw_faa_view import FAAViewWorker, QMWFAAView, VIEW_HEIGHT, VIEW_WIDTH, compose_view_frame
from function.globals.thread_action_queue import ThreadActionQueueTimer
from test.output_paths import get_test_output_dir


APP = QApplication.instance() or QApplication([])


def wait_until(predicate, timeout=3):
    """为后台采集留出实际执行时间；超时返回 False 供测试断言。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        APP.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def game_image():
    """创建固定模拟客户区，不读取账号或截取桌面。"""
    image = np.full((600, 950, 4), (62, 48, 32, 255), dtype=np.uint8)
    image[150:210, 300:380, :3] = (100, 180, 220)
    return image


class ViewEventsTest(unittest.TestCase):
    def setUp(self):
        FAA_VIEW_EVENTS.select(0)
        FAA_VIEW_EVENTS.configure(True, True)

    def tearDown(self):
        FAA_VIEW_EVENTS.select(0)

    def test_silent_and_player_isolation(self):
        events = FAAViewEvents()
        image = game_image()
        events.remember_image(image, 11)
        events.click(11, 30, 40)
        self.assertEqual(events.snapshot(), ([], []))
        self.assertEqual(len(events._images), 0)
        events.select(11)
        events.click(22, 1, 2)
        events.click(11, 30, 40)
        self.assertEqual(len(events.snapshot()[0]), 1)
        events.select(22)
        self.assertEqual(events.snapshot(), ([], []))

    def test_slice_provenance_and_weak_reference(self):
        events = FAAViewEvents()
        events.select(11)
        image = game_image().reshape(-1).reshape(600, 950, 4)
        events.remember_image(image, 11)
        cropped = image[100:300, 200:500, :3][10:50, 20:100]
        self.assertEqual(events.image_origin(cropped), (11, 220, 110))
        self.assertIsNone(events.image_origin(cropped.copy()))
        image_ref = weakref.ref(image)
        del image, cropped
        gc.collect()
        self.assertIsNone(image_ref())

    def test_expiry_limits_and_switches(self):
        events = FAAViewEvents()
        events.select(11)
        with patch("function.common.faa_view_events.time.monotonic", return_value=1):
            for x in range(200):
                events.click(11, x, 5)
                events.match((11, 0, 0), None, "目标", (x, 0, x + 1, 1), 0.99, 0.95, True)
        self.assertEqual(len(events._clicks), 160)
        self.assertEqual(len(events._matches), 80)
        with patch("function.common.faa_view_events.time.monotonic", return_value=3):
            self.assertEqual(events.snapshot(), ([], []))
        events.configure(False, False)
        events.click(11, 1, 2)
        events.match((11, 0, 0), None, "目标", (1, 2, 3, 4), 1, 0.95, True)
        self.assertEqual(events.snapshot(), ([], []))

    def test_actual_click_after_dispatch_with_dpi(self):
        FAA_VIEW_EVENTS.select(11)
        actions = ThreadActionQueueTimer()
        actions.zoom_rate = 1.5
        with patch("function.globals.thread_action_queue.windll.user32.PostMessageW", return_value=1) as post:
            actions.do_left_mouse_click(11, 100, 200)
        self.assertEqual(post.call_args.args[-1], (300 << 16) | 150)
        self.assertEqual(FAA_VIEW_EVENTS.snapshot()[0][0][1:], (100, 200))
        FAA_VIEW_EVENTS.select(11)
        with patch("function.globals.thread_action_queue.windll.user32.PostMessageW", return_value=0):
            actions.do_left_mouse_click(11, 100, 200)
        self.assertEqual(FAA_VIEW_EVENTS.snapshot()[0], [])

    def test_match_offsets_and_unchanged_return_values(self):
        rng = np.random.default_rng(42)
        image = rng.integers(20, 240, (150, 200, 3), dtype=np.uint8)
        template = image[65:73, 82:94].copy()
        FAA_VIEW_EVENTS.select(11, {id(template): (weakref.ref(template), "测试目标.png")})
        FAA_VIEW_EVENTS.remember_image(image, 11)
        result = match_p_in_w(template, source_img=image, source_range=[50, 40, 150, 110], return_center=False)
        self.assertEqual(result, (2, [32, 25]))
        event = FAA_VIEW_EVENTS.snapshot()[1][-1]
        self.assertEqual(event[1], "测试目标.png")
        self.assertEqual(event[2], (82, 65, 94, 73))
        self.assertGreater(event[3], 0.999)
        cropped = image[40:110, 50:150]
        self.assertEqual(match_p_in_w(template, source_img=cropped, match_tolerance=1), (1, None))
        self.assertFalse(FAA_VIEW_EVENTS.snapshot()[1][-1][-1])
        # 开关关闭不能改变业务识图结论。
        FAA_VIEW_EVENTS.configure(True, False)
        self.assertEqual(match_p_in_w(template, source_img=cropped, return_center=False), (2, [32, 25]))

    def test_batch_and_multi_target_coordinates(self):
        image = np.random.default_rng(5).integers(20, 230, (180, 200, 3), dtype=np.uint8)
        template = image[65:73, 82:94].copy()
        FAA_VIEW_EVENTS.select(11)
        FAA_VIEW_EVENTS.remember_image(image, 11)
        options = [{"template": template, "source_range": [50, 40, 150, 110], "match_tolerance": 0.95}]
        self.assertEqual(match_ps_in_w(options, "or", source_img=image), [38, 29])
        self.assertEqual(FAA_VIEW_EVENTS.snapshot()[1][-1][2], (82, 65, 94, 73))
        result = match_all_p_in_w(template, source_img=image, source_range=[50, 40, 150, 110], threshold=0.999)
        self.assertEqual(result, (2, [(32, 25)]))
        self.assertEqual(FAA_VIEW_EVENTS.snapshot()[1][-1][2], (82, 65, 94, 73))

    def test_senior_process_message_preserves_strategy(self):
        events = FAAViewEvents()
        events.select(11)
        information = (False, False, [], [], [])
        message = {"information": information, "view_handle": 11, "observed_at": time.monotonic(),
                   "view_matches": [("YOLO flypig", (100, 120, 130, 150), 0.89)]}
        self.assertIs(events.consume_senior_result(message), information)
        self.assertEqual(events.snapshot()[1][-1][3], 0.89)
        events.select(22)
        self.assertIs(events.consume_senior_result(message), information)
        self.assertEqual(events.snapshot()[1], [])
        message["view_handle"] = 22
        message["observed_at"] -= 10
        events.consume_senior_result(message)
        self.assertEqual(events.snapshot()[1], [])
        self.assertIs(events.consume_senior_result(information), information)


class ViewWindowTest(unittest.TestCase):
    def setUp(self):
        FAA_VIEW_EVENTS.select(0)
        FAA_VIEW_EVENTS.configure(True, True)
        self.capture_patch = patch("function.core.qmw_faa_view.capture_image_png", side_effect=lambda *args: game_image())
        self.handle_patch = patch("function.core.qmw_faa_view.faa_get_handle", side_effect=lambda channel, mode: 11 if channel == "游戏" else 22)
        self.valid_patch = patch("function.core.qmw_faa_view.win32gui.IsWindow", return_value=True)
        self.child_patch = patch("function.core.qmw_faa_view.win32gui.IsChild", return_value=True)
        for item in (self.capture_patch, self.handle_patch, self.valid_patch, self.child_patch):
            item.start()
        self.owner = QWidget()
        self.owner.opt = {"base_settings": {"game_name": "游戏", "name_1p": "", "name_2p": "玩家二"}}
        self.window = QMWFAAView(self.owner)

    def tearDown(self):
        self.window.close()
        self.owner.close()
        for item in (self.capture_patch, self.handle_patch, self.valid_patch, self.child_patch):
            item.stop()
        FAA_VIEW_EVENTS.select(0)

    def test_preview_without_recording_switch_hide_and_reopen(self):
        self.assertIsNone(self.window.worker)
        self.window.show()
        self.assertTrue(wait_until(lambda: self.window.start_button.isEnabled()))
        self.assertFalse(self.window.worker._recording)
        self.assertIsNotNone(self.window.preview.pixmap())
        self.assertEqual(FAA_VIEW_EVENTS.handle, 11)
        self.window.click_effect.setChecked(False)
        self.window.recognition_effect.setChecked(False)
        self.assertFalse(FAA_VIEW_EVENTS.show_clicks)
        self.assertFalse(FAA_VIEW_EVENTS.show_recognition)
        self.window.player.setCurrentIndex(1)
        self.assertTrue(wait_until(lambda: FAA_VIEW_EVENTS.handle == 22 and self.window.start_button.isEnabled()))
        previous = self.window.worker
        self.window.hide()
        self.assertFalse(previous.is_alive())
        self.assertEqual(FAA_VIEW_EVENTS.handle, 0)
        self.assertIsNone(self.window.worker)
        self.window.show()
        self.assertTrue(wait_until(lambda: self.window.start_button.isEnabled()))
        self.assertIsNot(self.window.worker, previous)

    def test_real_client_height_596_is_available_without_stretching(self):
        image = game_image()[:596]
        with patch("function.core.qmw_faa_view.capture_image_png", return_value=image):
            self.window.show()
            self.assertTrue(wait_until(lambda: self.window.start_button.isEnabled()))
            frame, ready, recording, notice = self.window.worker.snapshot()
            self.assertTrue(ready)
            self.assertFalse(recording)
            # 图像保持原坐标；底部缺少的 4 行只留底色，不缩放游戏或偏移点击特效。
            self.assertEqual(frame.pixelColor(940, 590).getRgb()[:3], (32, 48, 62))
            self.assertEqual(frame.pixelColor(940, 598).name(), "#111827")

    def test_preview_renders_at_screen_pixel_density(self):
        self.window.show()
        self.assertTrue(wait_until(lambda: self.window.start_button.isEnabled()))
        for ratio in (1.0, 1.25, 1.5, 2.0):
            with self.subTest(ratio=ratio):
                frame = self.window.worker.render_preview(QSize(VIEW_WIDTH, VIEW_HEIGHT), ratio)
                self.assertEqual(frame.size(), QSize(round(VIEW_WIDTH * ratio), round(VIEW_HEIGHT * ratio)))
                self.assertEqual(frame.devicePixelRatioF(), ratio)
                self.assertEqual(frame.deviceIndependentSize().width(), round(950 * ratio) / ratio)
        # 预览的屏幕倍率不会改变录像编码尺寸。
        self.assertEqual(self.window.worker.snapshot()[0].size(), QSize(VIEW_WIDTH, VIEW_HEIGHT))

    def test_black_sample_points_do_not_hide_visible_content(self):
        image = np.zeros((596, 950, 4), dtype=np.uint8)
        image[100:200, 100:200, :3] = (100, 160, 220)
        with patch("function.core.qmw_faa_view.capture_image_png", return_value=image):
            self.window.show()
            self.assertTrue(wait_until(lambda: self.window.start_button.isEnabled()))

    def test_all_black_rgb_is_unavailable_even_with_opaque_alpha(self):
        image = np.zeros((596, 950, 4), dtype=np.uint8)
        image[:, :, 3] = 255
        with patch("function.core.qmw_faa_view.capture_image_png", return_value=image):
            self.window.show()
            self.assertTrue(wait_until(lambda: self.window.worker._frame is not None))
            self.assertFalse(self.window.worker._ready)
            self.assertFalse(self.window.start_button.isEnabled())

    def test_real_mp4_contains_effects_and_stop_keeps_preview(self):
        self.window.show()
        self.assertTrue(wait_until(lambda: self.window.start_button.isEnabled()))
        with tempfile.TemporaryDirectory(dir=str(get_test_output_dir("faa_view"))) as directory:
            path = os.path.join(directory, "带特效录像.mp4")
            with patch("function.core.qmw_faa_view.QFileDialog.getSaveFileName", return_value=(path, "")):
                self.window._start_recording()
            self.assertTrue(wait_until(lambda: self.window.stop_button.isEnabled()))
            self.assertFalse(self.window.player.isEnabled())
            started = time.monotonic()
            while time.monotonic() - started < 0.25:
                FAA_VIEW_EVENTS.click(11, 120, 100)
                APP.processEvents()
                time.sleep(0.03)
            self.window.stop_button.click()
            self.assertTrue(wait_until(lambda: self.window.start_button.isEnabled()))
            self.assertTrue(self.window.worker.is_alive())
            self.assertFalse(self.window.worker._recording)
            capture = cv2.VideoCapture(path)
            try:
                self.assertTrue(capture.isOpened())
                self.assertEqual(int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), 950)
                self.assertEqual(int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)), VIEW_HEIGHT)
                frames = []
                while True:
                    success, image = capture.read()
                    if not success:
                        break
                    frames.append(image)
                self.assertGreaterEqual(len(frames), 4)
                # 黄色动画应存在于编码后的游戏区域，而非仅存在于 QLabel。
                self.assertTrue(any(np.any((frame[65:135, 85:155, 2] > 190) &
                                          (frame[65:135, 85:155, 1] > 130)) for frame in frames))
            finally:
                capture.release()

    def test_close_finalizes_mp4(self):
        self.window.show()
        self.assertTrue(wait_until(lambda: self.window.start_button.isEnabled()))
        with tempfile.TemporaryDirectory(dir=str(get_test_output_dir("faa_view"))) as directory:
            path = os.path.join(directory, "关闭保存.mp4")
            self.window.worker.request_recording(path)
            self.assertTrue(wait_until(lambda: self.window.worker._recording))
            worker = self.window.worker
            self.window.close()
            self.assertFalse(worker.is_alive())
            capture = cv2.VideoCapture(path)
            try:
                self.assertTrue(capture.read()[0])
            finally:
                capture.release()

    def test_encoder_failure_does_not_stop_preview(self):
        self.window.show()
        self.assertTrue(wait_until(lambda: self.window.start_button.isEnabled()))
        with patch("function.core.qmw_faa_view.cv2.VideoWriter", return_value=SimpleNamespace(isOpened=lambda: False, release=lambda: None)):
            self.window.worker.request_recording(os.path.join(str(get_test_output_dir("faa_view")), "失败.mp4"))
            self.assertTrue(wait_until(lambda: "录制失败" in self.window.worker._notice))
        self.assertTrue(self.window.worker.is_alive())
        self.assertFalse(self.window.worker._recording)

    def test_missing_root_never_searches_other_player(self):
        self.handle_patch.stop()
        with patch("function.core.qmw_faa_view.faa_get_handle", return_value=0) as lookup:
            worker = FAAViewWorker("不存在的窗口")
            worker.start()
            try:
                self.assertTrue(wait_until(lambda: worker._frame is not None))
                self.assertFalse(worker._ready)
                self.assertTrue(all(call.args[1:] == () and call.kwargs["mode"] == "360" for call in lookup.call_args_list))
            finally:
                worker.stop()
        self.handle_patch.start()

    def test_composed_frame_visual_artifact(self):
        now = time.monotonic()
        clicks = [(now - 0.2, 140, 180)]
        matches = [(now, "强化按钮.png", (300, 150, 380, 210), 0.996, 0.95, True)]
        matches.extend((now, f"识图目标{index}.png", (300, 150, 380, 210), 0.80 + index * 0.01, 0.95, False)
                       for index in range(2, 7))
        frame = compose_view_frame(game_image(), clicks, matches)
        path = os.path.join(str(get_test_output_dir("faa_view")), "preview.png")
        self.assertTrue(frame.save(path))
        self.assertGreater(frame.pixelColor(300, 170).green(), 150)
        self.window.show()
        self.assertTrue(wait_until(lambda: self.window.start_button.isEnabled()))
        with self.window.worker._lock:
            self.window.worker._frame = frame
            self.window.worker._scene = (game_image(), clicks, matches, "")
        self.window._update_preview()
        APP.processEvents()
        path = os.path.join(str(get_test_output_dir("faa_view")), "window.png")
        self.assertTrue(self.window.grab().save(path))


if __name__ == "__main__":
    unittest.main()
