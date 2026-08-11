import json
import unittest
from pathlib import Path

from function.core.faa.tweak_plan import (
    get_auto_card_target_names,
    get_tweak_plan_auto_card_enabled,
    get_tweak_plan_auto_mat_card,
    get_tweak_plan_random_interval,
    get_tweak_plan_recording,
)


class TweakPlanSchemaTest(unittest.TestCase):
    def test_schema_version_is_0_3(self):
        root = Path(__file__).resolve().parents[1]
        live = json.loads(
            (root / "tweak_plan" / "!默认.json").read_text(encoding="utf-8")
        )
        template = json.loads(
            (root / "resource" / "template" / "!默认.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(live, template)
        self.assertEqual(live["meta_data"]["version"], "0.3")

    def test_recording_reads_only_aggregated_structure(self):
        current = {
            "meta_data": {
                "recording": {"active": True, "timestamp": True, "player": 2}
            }
        }
        removed = {
            "meta_data": {
                "recording": True,
                "timestamp": True,
                "recording_player": 0,
            }
        }
        self.assertEqual(get_tweak_plan_recording(current), (True, True, 2))
        self.assertEqual(get_tweak_plan_recording(removed), (False, False, 1))

    def test_random_interval_reads_only_aggregated_structure(self):
        current = {
            "meta_data": {
                "cd_after_use_random": {
                    "active": True,
                    "range": [0.05, 0.25],
                }
            }
        }
        removed = {"meta_data": {"cd_after_use_random_range": [0.1, 0.3]}}
        self.assertEqual(
            get_tweak_plan_random_interval(current),
            (True, [0.05, 0.25]),
        )
        self.assertEqual(get_tweak_plan_random_interval(removed), (False, None))

    def test_auto_mat_reads_only_auto_mat_card(self):
        current = {
            "meta_data": {
                "auto_mat_card": {"enabled": False, "use_first": False}
            }
        }
        removed = {
            "meta_data": {
                "enable_auto_card": {"mat": False},
                "mat_card_first": False,
            }
        }
        self.assertEqual(
            get_tweak_plan_auto_mat_card(current),
            {"enabled": False, "use_first": False},
        )
        self.assertEqual(
            get_tweak_plan_auto_mat_card(removed),
            {"enabled": True, "use_first": True},
        )

    def test_auto_cards_use_positive_enable_flags(self):
        enabled = get_tweak_plan_auto_card_enabled(
            {
                "meta_data": {
                    "enable_auto_card": {
                        "icecream": False,
                        "god": False,
                        "ikun": False,
                        "timer": True,
                    }
                }
            }
        )
        self.assertEqual(
            enabled,
            {"icecream": False, "god": False, "ikun": False, "timer": True},
        )
        self.assertEqual(
            get_tweak_plan_auto_card_enabled(
                {"meta_data": {"ban_state": {"god": True}}}
            ),
            {"icecream": True, "god": True, "ikun": True, "timer": False},
        )

    def test_disabled_auto_cards_produce_no_recognition_targets(self):
        tweak = {
            "meta_data": {
                "auto_mat_card": {"enabled": False},
                "enable_auto_card": {
                    "icecream": False,
                    "god": False,
                    "ikun": False,
                },
            }
        }
        self.assertEqual(
            get_auto_card_target_names(["木盘子"], tweak),
            ([], [], []),
        )


if __name__ == "__main__":
    unittest.main()
