import unittest
from unittest.mock import Mock, call, patch

from function.core.faa import faa_action_interface_jump as jump


class TestTopMenuPages(unittest.TestCase):
    def setUp(self):
        self.owner = jump.FAAActionInterfaceJump()
        self.owner.handle = 11
        self.owner.handle_360 = 22
        self.owner.print_warning = Mock()
        self.click = self.enterContext(patch.object(jump.T_ACTION_QUEUE_TIMER, "add_click_to_queue"))
        self.enterContext(patch.object(jump.time, "sleep"))

    def test_change_activity_list_handles_all_start_and_target_pages(self):
        for start in (1, 2, 3):
            for target in (1, 2, 3):
                with self.subTest(start=start, target=target):
                    clicks_needed = (target - start) % 3
                    self.click.reset_mock()
                    pages = [start]
                    for index in range(clicks_needed):
                        # 翻页动作进入队列后，第一帧仍可能是旧页面。
                        pages.extend(((start + index - 1) % 3 + 1, (start + index) % 3 + 1))
                    with patch.object(self.owner, "_get_activity_list_page", side_effect=pages):
                        self.assertTrue(self.owner.action_change_activity_list(target))
                    self.assertEqual(self.click.call_args_list, [call(handle=11, x=785, y=30)] * clicks_needed)

    def test_unknown_frame_and_stuck_arrow_do_not_cause_blind_clicks(self):
        for page, clicks in ((None, 0), (2, 1)):
            with self.subTest(page=page):
                self.click.reset_mock()
                with patch.object(self.owner, "_get_activity_list_page", return_value=page):
                    self.assertFalse(self.owner.action_change_activity_list(3))
                self.assertEqual(self.click.call_count, clicks)

    def test_transient_blank_during_first_flip_is_not_the_third_page(self):
        with patch.object(self.owner, "_get_activity_list_page", side_effect=[1, 3, 2, 3]):
            self.assertTrue(self.owner.action_change_activity_list(3))
        self.assertEqual(self.click.call_count, 2)

    def test_blank_page_requires_visible_world_map(self):
        for map_status, expected in ((1, None), (2, 3)):
            with (
                self.subTest(map_status=map_status),
                patch.object(jump, "capture_image_png") as capture,
                patch.object(jump, "match_p_in_w", side_effect=[(1, None)] * 4 + [(map_status, None)]) as match,
            ):
                self.assertEqual(self.owner._get_activity_list_page(), expected)
                capture.assert_called_once()
                self.assertTrue(all(item.kwargs["source_img"] is capture.return_value for item in match.call_args_list))

    def test_snow_top_gate_is_selected_only_after_blank_page(self):
        self.owner.stage_info = {"id": "NO-2-15"}
        self.owner.is_main = True
        self.owner.random_seed = 0
        templates = {"stage": {"NO-2-15.png": "snow"}, "common": {"战斗": {"战斗前_创建房间.png": "create"}}}
        steps = Mock()
        with (
            patch.object(jump, "RESOURCE_P", templates),
            patch.object(self.owner, "action_goto_map", steps.map),
            patch.object(self.owner, "action_change_activity_list", steps.page),
            patch.object(jump, "loop_match_p_in_w", steps.match),
        ):
            steps.page.return_value = True
            steps.match.return_value = True
            self.owner.action_goto_stage()
            self.assertEqual([step[0] for step in steps.mock_calls], ["map", "page", "match", "match"])
            steps.page.assert_called_once_with(serial_num=3)
            self.assertEqual(steps.match.call_args_list[0].kwargs["template"], "snow")


if __name__ == "__main__":
    unittest.main()
