from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from function.core.faa.faa_action_interface_jump import FAAActionInterfaceJump


def _owner():
    return SimpleNamespace(handle=11, handle_360=22, print_warning=Mock())


class TestTopMenuPages(unittest.TestCase):
    def test_change_activity_list_reaches_first_page_through_blank_page(self):
        owner = _owner()
        match_results = [
            (1, None),    # second page
            (1, None),    # blank page
            (2, [1, 1]),  # first page
        ]

        with (
            patch(
                "function.core.faa.faa_action_interface_jump.match_p_in_w",
                side_effect=match_results,
            ),
            patch(
                "function.core.faa.faa_action_interface_jump."
                "T_ACTION_QUEUE_TIMER.add_click_to_queue"
            ) as click,
            patch("function.core.faa.faa_action_interface_jump.time.sleep"),
        ):
            result = FAAActionInterfaceJump.action_change_activity_list(owner, 1)

        self.assertTrue(result)
        self.assertEqual(click.call_count, 2)
        owner.print_warning.assert_not_called()

    def test_change_activity_list_reaches_second_page_through_blank_and_first_page(self):
        owner = _owner()

        with (
            patch(
                "function.core.faa.faa_action_interface_jump.match_p_in_w",
                side_effect=[(1, None), (1, None), (2, [1, 1])],
            ),
            patch(
                "function.core.faa.faa_action_interface_jump."
                "T_ACTION_QUEUE_TIMER.add_click_to_queue"
            ) as click,
            patch("function.core.faa.faa_action_interface_jump.time.sleep"),
        ):
            result = FAAActionInterfaceJump.action_change_activity_list(owner, 2)

        self.assertTrue(result)
        self.assertEqual(click.call_count, 2)
        owner.print_warning.assert_not_called()

    def test_change_activity_list_stops_after_one_complete_three_state_scan(self):
        owner = _owner()

        with (
            patch(
                "function.core.faa.faa_action_interface_jump.match_p_in_w",
                side_effect=[(1, None), (1, None), (1, None)],
            ),
            patch(
                "function.core.faa.faa_action_interface_jump."
                "T_ACTION_QUEUE_TIMER.add_click_to_queue"
            ) as click,
            patch("function.core.faa.faa_action_interface_jump.time.sleep"),
        ):
            result = FAAActionInterfaceJump.action_change_activity_list(owner, 2)

        self.assertFalse(result)
        self.assertEqual(click.call_count, 2)
        owner.print_warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
