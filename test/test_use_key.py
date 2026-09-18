import queue
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from function.core.faa.faa_battle import FAABattle


class UseKeyTest(unittest.TestCase):
    def test_missing_continue_button_keeps_pending_actions(self):
        action_queue = queue.Queue()
        pending_action = ("click", 1, [100, 200])
        action_queue.put(pending_action)
        action_queue_timer = SimpleNamespace(action_queue=action_queue)
        faa = SimpleNamespace(is_used_key=False, handle=1)

        with (
            patch(
                "function.core.faa.faa_battle.match_p_in_w",
                return_value=(None, False),
            ),
            patch(
                "function.core.faa.faa_battle.T_ACTION_QUEUE_TIMER",
                action_queue_timer,
            ),
        ):
            self.assertFalse(FAABattle.use_key(faa))

        self.assertEqual(action_queue.get_nowait(), pending_action)

    def test_continue_button_discards_stale_battle_actions(self):
        action_queue = queue.Queue()
        action_queue.put(("click", 1, [100, 200]))
        action_queue_timer = SimpleNamespace(action_queue=action_queue)
        faa = SimpleNamespace(
            is_used_key=False,
            need_key=False,
            handle=1,
            handle_360=2,
            print_info=lambda **_kwargs: None,
        )

        with (
            patch(
                "function.core.faa.faa_battle.match_p_in_w",
                side_effect=[(None, True), (None, False)],
            ),
            patch("function.core.faa.faa_battle.loop_match_p_in_w"),
            patch(
                "function.core.faa.faa_battle.T_ACTION_QUEUE_TIMER",
                action_queue_timer,
            ),
        ):
            self.assertFalse(FAABattle.use_key(faa))

        self.assertTrue(action_queue.empty())


if __name__ == "__main__":
    unittest.main()
