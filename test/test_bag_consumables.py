"""背包物品配额、数量核对和三次未减少防护；全部使用假窗口。"""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from function.core.faa.faa_core import FAABase
from function.globals import g_resources
from function.scattered.bag_operations import (
    BagItem, _BagPage, _BagPages, _BagRow, _BagTemplates, _BagUseSession, _wait_bag_count, read_bag_item_count,
    _use_selected_bag_consumable, use_bag_consumables, use_targeted_consumables,
)
from contextlib import contextmanager


@contextmanager
def virtual_clock():
    """模拟背包轮询的单线程时钟，不引入强卡器运行时。"""
    clock, delays = [0.0], []

    def sleep(delay):
        delays.append(delay)
        clock[0] += delay

    with patch("function.scattered.bag_operations.time.monotonic", side_effect=lambda: clock[0]), \
            patch("function.scattered.bag_operations.time.sleep", side_effect=sleep):
        yield clock, delays


class BagDictionaryTests(unittest.TestCase):
    def setUp(self):
        self.faa = SimpleNamespace(handle=1, handle_360=2, player=1,
                                   action_bottom_menu=Mock(return_value=True), action_exit=Mock(), print_debug=Mock())
        self.templates = {name: np.zeros((26, 31, 4), np.uint8) for name in ("A.png", "B.png", "C.png")}
        resources = patch.dict(g_resources.RESOURCE_P, {
            "item": dict(self.templates, **{"物品-背包-使用.png": object(), "物品-背包-使用-被选中.png": object()}),
            "common": {"退出.png": object(), "退出_被选中.png": object()},
        })
        resources.start()
        self.addCleanup(resources.stop)
        self.dialog = Mock()

    def execute(self, items, *, stock=None, outcomes=None, scan_only=False, rewards=None):
        """运行真实计量及单次使用，只替换页面识别、数字读取、队列和时钟。"""
        names = tuple(items)
        stock = {name: 20 for name in names} if stock is None else dict(stock)
        events = []

        def row():
            return _BagRow(88, tuple(BagItem(name, stock[name], False) if stock.get(name, 0) > 0
                                    else BagItem(None, 0, None, True) for name in names), b"page")

        def snapshot():
            events.append("scan")
            return (row(),)

        pages = SimpleNamespace(check=Mock(), scan=Mock(side_effect=snapshot),
                                iterate=lambda _scan: iter((_BagPage(88, 108, 413, (row(),)),)),
                                offset=0, first_phase=88, verify=Mock())
        self.scans, self.events = pages.scan, events
        points = {(490 + 49 * i, 112): name for i, name in enumerate(names)}
        outcome = iter(outcomes) if outcomes is not None else None
        submitted, selected = [], [None]

        def click(**kwargs):
            point = (kwargs["x"], kwargs["y"])
            if point in points:
                selected[0] = points[point]
            elif point == (486, 116):
                name = selected[0]
                submitted.append(name)
                events.append(name)
                if outcome is None or next(outcome):
                    stock[name] -= 1
                    for child, amount in (rewards or {}).get(name, {}).items():
                        stock[child] = stock.get(child, 0) + amount

        def count(_faa, point, _control=None, previous=None, **_kwargs):
            return stock[points[tuple(point)]]

        def matcher(**kwargs):
            return (2, (20, 30)) if "source_img" not in kwargs and kwargs["template"] is \
                g_resources.RESOURCE_P["item"]["物品-背包-使用.png"] else (1, None)

        with patch("function.scattered.bag_operations._BagPages", return_value=pages), \
                patch("function.scattered.bag_operations._wait_bag_count", side_effect=count), \
                patch("function.scattered.bag_operations.read_bag_item_count", side_effect=lambda _image, point: stock[points[tuple(point)]]), \
                patch("function.scattered.bag_operations.sort_equipment_inventory", side_effect=lambda *_args: events.append("sort")), \
                patch("function.common.bg_img_match.match_p_in_w", side_effect=matcher), \
                patch("function.common.bg_img_screenshot.capture_image_png", return_value=np.zeros((596, 950, 4), np.uint8)), \
                patch("function.globals.thread_action_queue.T_ACTION_QUEUE_TIMER.add_click_to_queue", side_effect=click), \
                patch("function.globals.SIGNAL.DIALOG", self.dialog), virtual_clock():
            result = FAABase.use_bag_consumables(self.faa, items=items, scan_only=scan_only)
        return result, submitted

    def test_A_three_B_six_in_one_session(self):
        result, submitted = self.execute({"A.png": 3, "B.png": 6})
        self.assertEqual(result, {"A.png": 3, "B.png": 6})
        self.assertEqual(submitted, ["A.png"] * 3 + ["B.png"] * 6)
        self.faa.action_bottom_menu.assert_called_once_with(mode="背包")
        self.faa.action_exit.assert_called_once_with(mode="普通红叉")

    def test_scan_uses_zero_dictionary_and_never_submits(self):
        result, submitted = self.execute({"A.png": 0, "B.png": 0}, stock={"A.png": 3, "B.png": 6}, scan_only=True)
        self.assertEqual((result, submitted), ({"A.png": 3, "B.png": 6}, []))

    def test_999_stops_at_empty_or_requested_limit(self):
        for stock in (2, 1200):
            with self.subTest(stock=stock):
                result, submitted = self.execute({"C.png": 999}, stock={"C.png": stock})
                self.assertEqual(result, {"C.png": min(stock, 999)})
                self.assertEqual(len(submitted), min(stock, 999))

    def test_three_failures_stop_all_items_and_emit_existing_dialog(self):
        result, submitted = self.execute({"A.png": 999, "B.png": 6}, outcomes=[False] * 3)
        self.assertEqual((result, submitted), ({"A.png": 0, "B.png": 0}, ["A.png"] * 3))
        self.dialog.emit.assert_called_once()
        self.assertIn("道具栏可能已满", self.dialog.emit.call_args.kwargs["text"])
        self.faa.action_exit.assert_called_once_with(mode="普通红叉")

    def test_success_resets_failure_streak(self):
        result, submitted = self.execute({"A.png": 2}, outcomes=[False, False, True, False, False, True])
        self.assertEqual((result, len(submitted)), ({"A.png": 2}, 6))
        self.dialog.emit.assert_not_called()

    def test_failure_on_B_preserves_A_confirmed_usage(self):
        result, submitted = self.execute({"A.png": 1, "B.png": 6}, outcomes=[True, False, False, False])
        self.assertEqual(result, {"A.png": 1, "B.png": 0})
        self.assertEqual(submitted, ["A.png"] + ["B.png"] * 3)

    def test_invalid_dictionary_and_scan_quantities_do_not_open_bag(self):
        for items, scan in (({}, False), (["A.png"], False), ({"A.png": -1}, False),
                            ({"A.png": True}, False), ({"A.png": None}, False),
                            ({"A.png": 1}, True), ({"不存在.png": 1}, False)):
            with self.subTest(items=items), self.assertRaises(ValueError):
                use_bag_consumables(self.faa, items=items, scan_only=scan)
        self.faa.action_bottom_menu.assert_not_called()

    def test_zero_without_scan_does_not_open_bag(self):
        self.assertEqual(use_bag_consumables(self.faa, items={"A.png": 0}), {"A.png": 0})
        self.faa.action_bottom_menu.assert_not_called()

    def test_new_item_in_an_earlier_empty_cell_is_used_in_the_next_round(self):
        result, submitted = self.execute({"A.png": 1, "B.png": 1}, stock={"A.png": 0, "B.png": 1},
                                         rewards={"B.png": {"A.png": 1}})
        self.assertEqual(result, {"A.png": 1, "B.png": 1})
        self.assertEqual(submitted, ["B.png", "A.png"])
        self.assertEqual(self.events, ["sort", "scan", "B.png", "sort", "scan", "A.png"])

    def test_generated_item_cycles_stop_after_three_rounds(self):
        result, submitted = self.execute(
            {"C.png": 999, "B.png": 999, "A.png": 999}, stock={"A.png": 1, "B.png": 0, "C.png": 0},
            rewards={"A.png": {"B.png": 1}, "B.png": {"C.png": 1}, "C.png": {"A.png": 1}})
        self.assertEqual(submitted, ["A.png", "B.png", "C.png"])
        self.assertEqual(result, {"A.png": 1, "B.png": 1, "C.png": 1})
        self.assertEqual(self.scans.call_count, 3)

    def test_rounds_do_not_reset_item_allowances(self):
        result, submitted = self.execute({"A.png": 1, "B.png": 2}, stock={"A.png": 1, "B.png": 1},
                                         rewards={"B.png": {"A.png": 2}})
        self.assertEqual((result, submitted), ({"A.png": 1, "B.png": 1}, ["A.png", "B.png"]))
        self.assertEqual(self.scans.call_count, 2)

    def test_scan_only_is_one_round(self):
        self.execute({"A.png": 0}, stock={"A.png": 2}, scan_only=True)
        self.assertEqual(self.events, ["sort", "scan"])

    def test_later_stacks_of_the_same_item_remain_in_the_plan(self):
        first = BagItem("A.png", 1, False)
        second = BagItem("A.png", 4, False)
        rows = (_BagRow(88, (first,), b"first"), _BagRow(137, (second,), b"second"))
        pages = SimpleNamespace(check=Mock(), scan=Mock(return_value=rows), offset=0, first_phase=88,
                                verify=Mock(), iterate=lambda _scan: iter((_BagPage(88, 108, 413, rows),)))
        amounts = {(490, 112): 1, (490, 161): 4}
        consumed = []

        def use(session, name, point):
            amounts[point] -= 1
            session.used[name] += 1
            consumed.append(point)
            return amounts[point]

        with patch("function.scattered.bag_operations._BagPages", return_value=pages), \
                patch("function.scattered.bag_operations._BagUseSession.use", use), \
                patch("function.scattered.bag_operations.sort_equipment_inventory"), virtual_clock():
            result = use_bag_consumables(self.faa, {"A.png": 3})
        self.assertEqual(result, {"A.png": 3})
        self.assertEqual(consumed, [(490, 112), (490, 161), (490, 161)])


class BagRewardCloseTests(unittest.TestCase):
    def exercise(self, frames, window="gift"):
        """模拟使用菜单延迟退出及奖励关闭动画，执行真实单件处理。"""
        sequence = iter(frames)
        self.clicks = []
        self.capture = Mock(side_effect=lambda **_kwargs: next(sequence, frames[-1]))

        def match(**kwargs):
            if "source_img" not in kwargs:
                return 2, (20, 30)
            frame, template = kwargs["source_img"], kwargs["template"]
            rect = [680, 188, 714, 218] if window == "gift" else [432, 178, 466, 208]
            if kwargs["source_range"] == rect:
                name = "退出_被选中.png" if frame == "hover" else "退出.png"
                if frame in ("reward", "hover", "error") and template is g_resources.RESOURCE_P["common"][name]:
                    return (0, None) if frame == "error" else (2, (16, 14))
            if frame == "menu" and template is g_resources.RESOURCE_P["item"]["物品-背包-使用.png"]:
                return 2, (20, 30)
            return 1, None

        with patch("function.common.bg_img_match.match_p_in_w", side_effect=match), \
                patch("function.common.bg_img_screenshot.capture_image_png", self.capture), \
                patch("function.scattered.bag_operations.read_bag_item_count", side_effect=lambda image, _point: 1 if image == "closed" else 2), \
                patch("function.globals.thread_action_queue.T_ACTION_QUEUE_TIMER.add_click_to_queue",
                      side_effect=lambda **kwargs: self.clicks.append((kwargs["x"], kwargs["y"]))), virtual_clock():
            return _use_selected_bag_consumable(SimpleNamespace(handle=1, handle_360=2), ("A",), (490, 112), previous_count=2)

    def test_delayed_reward_and_hover_close_wait_for_real_disappearance(self):
        for window, point in (("single", (448, 192)), ("gift", (696, 202))):
            for reward in ("reward", "hover"):
                with self.subTest(window=window, reward=reward):
                    self.assertEqual(self.exercise(["menu", "pending", "pending", reward, reward, reward, "closed"], window), 1)
                    self.assertEqual(self.clicks, [(490, 112), (486, 116), point])
                    self.assertEqual(self.capture.call_count, 7)

    def test_stuck_reward_stops_without_repeated_close_or_consumption(self):
        with self.assertRaisesRegex(RuntimeError, "3秒内未关闭"):
            self.exercise(["reward"])
        self.assertEqual(self.clicks, [(490, 112), (486, 116), (696, 202)])

    def test_no_reward_window_never_clicks_a_fixed_close_point(self):
        self.assertEqual(self.exercise(["pending", "closed", "closed"]), 1)
        self.assertEqual(self.clicks, [(490, 112), (486, 116)])

    def test_recognition_error_does_not_count_as_closed(self):
        with self.assertRaisesRegex(RuntimeError, "奖励窗识别失败"):
            self.exercise(["error"])
        self.assertEqual(self.clicks, [(490, 112), (486, 116)])


class CountedBagRoundsTests(unittest.TestCase):
    def test_callback_reader_finds_new_earlier_item_after_resorting(self):
        faa = SimpleNamespace(action_bottom_menu=Mock(return_value=True), action_exit=Mock())
        stock = {"A": 0, "B": 1}
        reader = Mock(side_effect=lambda _faa: tuple(BagItem(name, count, True) for name, count in stock.items()))
        sorter = Mock()
        consumed = []

        def locate(_faa, names):
            return (490 if names[0] == "A" else 539, 112) if stock[names[0]] else None

        def use(session, name, _point):
            consumed.append(name)
            stock[name] -= 1
            if name == "B":
                stock["A"] += 1
            session.used[name] += 1
            session.submitted += 1
            return stock[name]

        with patch("function.scattered.bag_operations._BagUseSession.use", use):
            result = use_targeted_consumables(faa, {"A": 1, "B": 1}, inventory_reader=reader,
                                              inventory_sorter=sorter, item_locator=locate, use_checker=Mock())
        self.assertEqual(consumed, ["B", "A"])
        self.assertEqual(result.completed, 2)
        self.assertEqual(sorter.call_count, 2)
        self.assertEqual(reader.call_count, 3)

    def test_callback_unknown_quantity_is_not_treated_as_absent(self):
        faa = SimpleNamespace(action_bottom_menu=Mock(return_value=True))
        locate = Mock()
        with self.assertRaisesRegex(RuntimeError, "数量未知"):
            use_targeted_consumables(faa, {"A": 1}, inventory_reader=Mock(return_value=(BagItem("A", None, True),)),
                                     inventory_sorter=Mock(), item_locator=locate, use_checker=Mock())
        locate.assert_not_called()


class BagQuantityTests(unittest.TestCase):
    def test_drop_rate_originals_match_with_or_without_backpack_binding_and_quantity(self):
        from function.common.image_processing.overlay_images import overlay_images

        resources = g_resources.RESOURCE_P["item"]
        names = ("物品-双暴卡.png", "物品-三暴卡.png")
        matcher = _BagTemplates({name: resources[name] for name in names})
        background = np.full((44, 44, 4), [61, 38, 20, 255], dtype=np.uint8)
        for name in names:
            for bound in (False, True):
                with self.subTest(name=name, bound=bound):
                    icon = overlay_images(background, resources[name])
                    if bound:
                        icon = overlay_images(icon, resources["物品-绑定角标-背包.png"])
                    icon[36:42, 36:43, :3] = 255
                    cell = np.zeros((49, 49, 4), dtype=np.uint8)
                    cell[1:45, 1:45] = icon
                    self.assertEqual([target for target in names if matcher.matches(cell, target)], [name])

    def test_last_item_replaced_by_another_one_is_not_retried_or_used(self):
        original = np.ones((596, 950, 3), np.uint8)
        replacement = np.full_like(original, 2)
        current = [original]
        templates = SimpleNamespace(matches=lambda block, _name: np.all(block == 1))
        session = _BagUseSession(SimpleNamespace(handle=1, handle_360=2), {"A": 2}, templates=templates)

        with patch("function.common.bg_img_screenshot.capture_image_png", side_effect=lambda **_kwargs: current[0]), \
                patch("function.scattered.bag_operations._use_selected_bag_consumable",
                      side_effect=lambda *_args, **_kwargs: current.__setitem__(0, replacement)) as consume, virtual_clock():
            self.assertEqual(session.use("A", (490, 112)), 0)
            self.assertEqual(session.used, {"A": 1})
            self.assertEqual(session.failures, {"A": 0})
            with self.assertRaisesRegex(RuntimeError, "无法识别"):
                session.use("A", (490, 112))
        consume.assert_called_once()

    def test_full_memory_scan_stops_at_real_empty_tail_but_keeps_unknown_cells(self):
        unknown = BagItem(None, None, None)
        empty = BagItem(None, 0, None, True)
        rows = (_BagRow(88, (unknown,) * 9, b"unknown"),
                _BagRow(137, (BagItem("A", 4, True),) + (empty,) * 8, b"tail"))
        scanner = _BagPages(SimpleNamespace(handle=1), {})
        scanner.wait = Mock(return_value=_BagPage(88, 108, 200, rows))
        with patch("function.globals.thread_action_queue.T_ACTION_QUEUE_TIMER.add_click_to_queue") as click:
            memory = scanner.scan()
        self.assertEqual(len(memory), 2)
        self.assertFalse(memory[0].cells[0].empty)
        self.assertEqual(memory[1].cells[0].count, 4)
        click.assert_not_called()

    def test_scan_refuses_occupied_cells_after_a_sorted_empty_cell(self):
        empty, occupied = BagItem(None, 0, None, True), BagItem(None, None, None)
        scanner = _BagPages(SimpleNamespace(handle=1), {})
        scanner.wait = Mock(return_value=_BagPage(88, 108, 413, (
            _BagRow(88, (empty, occupied) + (empty,) * 7, b"invalid"),)))
        with self.assertRaisesRegex(RuntimeError, "空格后仍有物品"):
            scanner.scan()

    def test_template_matching_checks_every_cell_using_template_sized_crops(self):
        images = {"A": np.zeros((44, 44, 4), np.uint8)}
        matcher = _BagTemplates(images)
        block = np.zeros((49, 49, 3), np.uint8)
        with patch("function.common.bg_img_match.match_p_in_w", return_value=(2, (0, 0))) as match:
            self.assertTrue(matcher.matches(block, "A"))
            self.assertTrue(matcher.matches(block, "A"))
        self.assertEqual(match.call_count, 2)
        for call in match.call_args_list:
            self.assertEqual(call.kwargs["source_img"].shape[:2], call.kwargs["template"].shape[:2])

    def test_small_template_calibrates_within_one_cell_then_uses_the_same_crop(self):
        image = np.zeros((26, 31, 4), np.uint8)
        matcher = _BagTemplates({"A": image})
        block = np.zeros((49, 49, 3), np.uint8)
        with patch("function.common.bg_img_match.match_p_in_w", side_effect=[(1, None), (2, (7, 5)), (2, (0, 0))]) as match:
            self.assertTrue(matcher.matches(block, "A"))
            self.assertTrue(matcher.matches(block, "A"))
        self.assertEqual(matcher.origins["A"], (7, 5))
        self.assertEqual([call.kwargs["source_img"].shape[:2] for call in match.call_args_list],
                         [(26, 31), (49, 49), (26, 31)])

    def test_numbers_include_red_outline_and_32767(self):
        for number in (1, 2, 14, 110, 1274, 32767, 99999):
            for color in ([72, 35, 13], [0, 0, 255]):
                image = np.zeros((596, 950, 3), np.uint8)
                left = 40 - (len(str(number)) - 1) * 7
                image[122:132, 466 + left - 1:513] = color
                for place, digit in enumerate(reversed(str(number))):
                    x = 466 + 40 - place * 7
                    mask = np.all(g_resources.RESOURCE_P["number"][f"{digit}.png"][:, :, :3] >= 250, axis=2)
                    image[123:131, x:x + 6][mask] = 255
                with self.subTest(number=number, color=color):
                    self.assertEqual(read_bag_item_count(image, (490, 112)), number)

    def test_empty_is_zero_corruption_is_unknown(self):
        image = np.zeros((596, 950, 3), np.uint8)
        image[98:121, 476:499] = [99, 66, 26]
        self.assertEqual(read_bag_item_count(image, (490, 112)), 0)
        image[110, 480] = [1, 2, 3]
        image[122:132, 505:513] = [72, 35, 13]
        self.assertIsNone(read_bag_item_count(image, (490, 112)))

    def test_unreadable_count_never_becomes_full_bag_failure(self):
        with patch("function.common.bg_img_screenshot.capture_image_png"), \
                patch("function.scattered.bag_operations.read_bag_item_count", return_value=None), \
                patch("function.globals.SIGNAL.DIALOG", Mock()) as dialog, virtual_clock():
            with self.assertRaisesRegex(RuntimeError, "无法识别"):
                _wait_bag_count(SimpleNamespace(handle=1, handle_360=2), (490, 112), previous=20)
        dialog.emit.assert_not_called()

    def test_overlapping_pages_count_absolute_rows_once(self):
        def page(first, top):
            rows = tuple(_BagRow(88 + i * 49, (BagItem("A", first + i + 1, True),), bytes([first + i])) for i in range(7))
            return _BagPage(88, top, top + 92, rows)

        scanner = _BagPages(SimpleNamespace(), {})
        scanner.first_phase = 88
        first, second = page(0, 108), page(3, 147)
        scanner.merge(first)
        delta = scanner.advance(first, second)
        self.assertEqual(delta, 147)
        scanner.offset += delta
        scanner.merge(second)
        self.assertEqual(sum(row.cells[0].count for row in scanner.rows.values()), 55)


class DoubleCardScheduleTests(unittest.TestCase):
    def test_workdays_delegate_with_dictionary(self):
        for weekday in range(5):
            faa = SimpleNamespace(use_bag_consumables=Mock())
            with self.subTest(weekday=weekday), patch("function.core.faa.faa_core.datetime") as clock:
                clock.now.return_value.weekday.return_value = weekday
                FAABase.use_items_double_card(faa, 3)
            self.assertEqual(str(clock.now.call_args.args[0]), "Asia/Shanghai")
            faa.use_bag_consumables.assert_called_once_with(items={"物品-双暴卡.png": 3})

    def test_three_times_uses_only_the_three_times_drop_rate_card(self):
        faa = SimpleNamespace(use_bag_consumables=Mock())
        with patch("function.core.faa.faa_core.datetime") as clock:
            clock.now.return_value.weekday.return_value = 0
            FAABase.use_items_double_card(faa, max_times=2, multiplier=3)
        faa.use_bag_consumables.assert_called_once_with(items={"物品-三暴卡.png": 2})

    def test_weekends_skip(self):
        for weekday in (5, 6):
            for multiplier in (2, 3):
                faa = SimpleNamespace(use_bag_consumables=Mock())
                with self.subTest(weekday=weekday, multiplier=multiplier), \
                        patch("function.core.faa.faa_core.datetime") as clock, \
                        patch("function.globals.SIGNAL.PRINT_TO_UI", SimpleNamespace(emit=Mock())):
                    clock.now.return_value.weekday.return_value = weekday
                    FAABase.use_items_double_card(faa, 3, multiplier=multiplier)
                faa.use_bag_consumables.assert_not_called()


class BagTaskEntryTests(unittest.TestCase):
    def test_selected_players_use_the_new_entry(self):
        from function.core import todo

        for players in ([1], [2], [1, 2]):
            with self.subTest(players=players):
                task = SimpleNamespace(
                    check_player=Mock(return_value=players), model_start_print=Mock(), model_end_print=Mock(),
                    faa_dict={pid: SimpleNamespace(use_bag_consumables=Mock()) for pid in (1, 2)},
                )
                with patch.object(todo, "sleep"):
                    todo.ThreadTodo.batch_use_bag_consumables(task, player=players)
                for pid in (1, 2):
                    self.assertEqual(task.faa_dict[pid].use_bag_consumables.call_count, int(pid in players))
                task.model_end_print.assert_called_once_with(text="使用绑定消耗品")


if __name__ == "__main__":
    unittest.main()
