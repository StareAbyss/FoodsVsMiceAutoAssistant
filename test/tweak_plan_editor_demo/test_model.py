"""微调方案编辑器 Demo 数据模型测试。"""

import json
import tempfile
import unittest
import uuid
from pathlib import Path

from test.tweak_plan_editor_demo.model import (
    BUILT_IN_TWEAK_PLAN_UUIDS,
    TweakPlanDraft,
    get_export_target_uuid,
)


class TweakPlanDraftTest(unittest.TestCase):
    def test_missing_options_remain_inherited(self):
        draft = TweakPlanDraft.from_mapping(
            {
                "meta_data": {
                    "uuid": "00000000-0000-0000-0000-000000000001",
                    "version": "0.2",
                    "tips": "高级战斗",
                    "senior_setting": True,
                }
            }
        )

        self.assertTrue(draft.senior_setting)
        self.assertIsNone(draft.recording)
        self.assertNotIn("recording", draft.to_mapping()["meta_data"])

    def test_faa_version_metadata_is_preserved(self):
        draft = TweakPlanDraft.from_mapping(
            {
                "meta_data": {
                    "uuid": "00000000-0000-0000-0000-000000000001",
                    "version": "0.3",
                    "faa_version": "v3.1.1",
                }
            }
        )

        self.assertEqual(draft.faa_version, "v3.1.1")
        self.assertEqual(
            draft.to_mapping()["meta_data"]["faa_version"],
            "v3.1.1",
        )

    def test_removed_recording_and_random_fields_are_ignored(self):
        draft = TweakPlanDraft.from_mapping(
            {
                "meta_data": {
                    "uuid": "00000000-0000-0000-0000-000000000000",
                    "version": "0.3",
                    "tips": "默认",
                    "recording": False,
                    "timestamp": True,
                    "recording_player": 0,
                    "cd_after_use_random_range": [0.1, 0.3],
                }
            }
        )

        meta_data = draft.to_mapping()["meta_data"]
        self.assertIsNone(draft.recording)
        self.assertIsNone(draft.timestamp)
        self.assertIsNone(draft.recording_player)
        self.assertEqual(draft.random_interval_mode, "inherit")
        self.assertNotIn("recording", meta_data)
        self.assertNotIn("timestamp", meta_data)
        self.assertNotIn("recording_player", meta_data)
        self.assertNotIn("cd_after_use_random_range", meta_data)

    def test_invalid_recording_player_is_ignored(self):
        draft = TweakPlanDraft.from_mapping(
            {
                "meta_data": {
                    "uuid": "00000000-0000-0000-0000-000000000004",
                    "version": "0.3",
                    "recording": {"player": 0},
                }
            }
        )

        self.assertIsNone(draft.recording_player)
        self.assertNotIn("recording", draft.to_mapping()["meta_data"])

    def test_nested_recording_options_round_trip(self):
        draft = TweakPlanDraft.from_mapping({
            "meta_data": {
                "recording": {
                    "active": True,
                    "timestamp": True,
                    "player": 2,
                }
            }
        })

        self.assertIs(draft.recording, True)
        self.assertIs(draft.timestamp, True)
        self.assertEqual(draft.recording_player, 2)
        self.assertEqual(
            draft.to_mapping()["meta_data"]["recording"],
            {"active": True, "timestamp": True, "player": 2},
        )

    def test_partial_enable_auto_card_stays_sparse(self):
        draft = TweakPlanDraft.from_mapping(
            {
                "meta_data": {
                    "uuid": "00000000-0000-0000-0000-000000000003",
                    "version": "0.3",
                    "enable_auto_card": {"god": True},
                }
            }
        )

        self.assertEqual(
            draft.to_mapping()["meta_data"]["enable_auto_card"],
            {"god": True},
        )

    def test_auto_mat_card_is_independent_and_removed_fields_are_ignored(self):
        inherited = TweakPlanDraft.from_mapping({"meta_data": {}})
        explicit = TweakPlanDraft.from_mapping({
            "meta_data": {
                "auto_mat_card": {
                    "enabled": False,
                    "use_first": False,
                }
            }
        })
        legacy = TweakPlanDraft.from_mapping(
            {"meta_data": {
                "enable_auto_card": {"mat": False},
                "mat_card_first": False,
            }}
        )

        self.assertIsNone(inherited.auto_mat_card_enabled)
        self.assertIsNone(inherited.auto_mat_card_first)
        self.assertNotIn("auto_mat_card", inherited.to_mapping()["meta_data"])
        self.assertEqual(
            explicit.to_mapping()["meta_data"]["auto_mat_card"],
            {"enabled": False, "use_first": False},
        )
        self.assertIsNone(legacy.auto_mat_card_enabled)
        self.assertIsNone(legacy.auto_mat_card_first)
        legacy_meta_data = legacy.to_mapping()["meta_data"]
        self.assertNotIn("enable_auto_card", legacy_meta_data)
        self.assertNotIn("mat_card_first", legacy_meta_data)

    def test_removed_ban_state_is_not_preserved(self):
        draft = TweakPlanDraft.from_mapping(
            {
                "meta_data": {
                    "uuid": "00000000-0000-0000-0000-000000000003",
                    "version": "0.3",
                    "ban_state": {"god": True, "coffee": True},
                }
            }
        )

        meta_data = draft.to_mapping()["meta_data"]
        self.assertNotIn("ban_state", meta_data)
        self.assertNotIn("coffee", draft.enable_auto_card)

    def test_random_range_validation_rejects_reversed_bounds(self):
        draft = TweakPlanDraft(
            random_interval_mode="range",
            random_interval_min=0.5,
            random_interval_max=0.1,
        )

        self.assertIn("放卡间隔下限不能大于上限", draft.validation_messages())

    def test_unknown_metadata_is_preserved(self):
        draft = TweakPlanDraft.from_mapping(
            {
                "meta_data": {
                    "uuid": "00000000-0000-0000-0000-000000000000",
                    "version": "0.3",
                    "future_option": {"enabled": True},
                }
            }
        )

        self.assertEqual(
            draft.to_mapping()["meta_data"]["future_option"],
            {"enabled": True},
        )

    def test_new_drafts_use_uuid1_like_battle_plan_editor(self):
        first_uuid = TweakPlanDraft().plan_uuid
        second_uuid = TweakPlanDraft().plan_uuid

        self.assertEqual(uuid.UUID(first_uuid).version, 1)
        self.assertEqual(uuid.UUID(second_uuid).version, 1)
        self.assertNotEqual(first_uuid, second_uuid)

    def test_built_in_plans_have_fixed_uuid_sequence(self):
        self.assertEqual(
            BUILT_IN_TWEAK_PLAN_UUIDS,
            {
                "!默认": "00000000-0000-0000-0000-000000000000",
                "高级战斗": "00000000-0000-0000-0000-000000000001",
                "慢速放卡": "00000000-0000-0000-0000-000000000002",
                "禁用自动卡片": "00000000-0000-0000-0000-000000000003",
                "开启录制": "00000000-0000-0000-0000-000000000004",
            },
        )

    def test_export_uuid_is_new_for_new_file_and_preserved_for_existing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "方案.json"
            new_uuid = get_export_target_uuid(target)
            self.assertEqual(uuid.UUID(new_uuid).version, 1)

            existing_uuid = "00000000-0000-0000-0000-000000000099"
            target.write_text(
                json.dumps({"meta_data": {"uuid": existing_uuid}}),
                encoding="utf-8",
            )
            self.assertEqual(get_export_target_uuid(target), existing_uuid)

    def test_default_plan_and_template_have_no_tip_helper_fields(self):
        repository_root = Path(__file__).resolve().parents[2]
        live_path = repository_root / "tweak_plan" / "!默认.json"
        template_path = repository_root / "resource" / "template" / "!默认.json"
        live_data = json.loads(live_path.read_text(encoding="utf-8"))
        template_data = json.loads(template_path.read_text(encoding="utf-8"))

        self.assertEqual(live_data, template_data)
        self.assertFalse(
            any(key.endswith("-tip") for key in live_data["meta_data"])
        )


if __name__ == "__main__":
    unittest.main()
