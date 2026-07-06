import json
import tempfile
import unittest
from pathlib import Path

from function.core.settings_migration import DEFAULT_UUIDS, get_migration_configs, migrate_one
from function.core.update_prepare import write_migration_report


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class SettingsMigrationTest(unittest.TestCase):
    def test_default_migration_config_order(self):
        names = [config["name"] for config in get_migration_configs()]

        self.assertEqual(
            names,
            [
                "配置文件 - 核心",
                "配置文件 - 关卡全局方案",
                "配置文件 - 自定义关卡信息",
                "用户自截",
                "背包道具 - 需删除",
                "背包装备 - 需使用",
                "战斗方案",
                "微调方案",
                "自定义任务序列",
                "公会管理器数据",
                "战斗方案 - 未激活",
            ],
        )

        self.assertEqual(
            [config["group"] for config in get_migration_configs()],
            [
                "配置文件",
                "配置文件",
                "配置文件",
                "用户自定义图像",
                "用户自定义图像",
                "用户自定义图像",
                "方案与任务",
                "方案与任务",
                "方案与任务",
                "其他用户数据",
                "其他用户数据",
            ],
        )

    def test_uuid_json_folder_keeps_target_same_uuid_and_renames_same_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source" / "battle_plan"
            target = root / "target" / "battle_plan"

            keep_uuid = "11111111-1111-1111-1111-111111111111"
            target_name_uuid = "22222222-2222-2222-2222-222222222222"
            source_name_uuid = "33333333-3333-3333-3333-333333333333"
            duplicated_uuid = "44444444-4444-4444-4444-444444444444"

            write_json(target / "Keep.json", {"meta_data": {"uuid": keep_uuid}, "value": "target"})
            write_json(target / "SameName.json", {"meta_data": {"uuid": target_name_uuid}, "value": "target"})

            write_json(source / "KeepSource.json", {"meta_data": {"uuid": keep_uuid}, "value": "source"})
            write_json(source / "KeepSourceCopy.json", {"meta_data": {"uuid": keep_uuid}, "value": "source_copy"})
            write_json(source / "SameName.json", {"meta_data": {"uuid": source_name_uuid}, "value": "source"})
            write_json(source / "MissingUuid.json", {"meta_data": {"version": "3.0"}, "value": "missing_uuid"})
            write_json(source / "DupA.json", {"meta_data": {"uuid": duplicated_uuid}, "value": "dup_a"})
            write_json(source / "DupB.json", {"meta_data": {"uuid": duplicated_uuid}, "value": "dup_b"})
            write_json(source / "DefaultUuid.json", {"meta_data": {"uuid": next(iter(DEFAULT_UUIDS))}})
            (source / "Broken.json").write_text("{broken", encoding="utf-8")

            config = {
                "name": "战斗方案",
                "type": "folder_uuid_json",
                "uuid_kind": "dict_meta",
                "path_from": source,
                "path_to": target,
            }

            self.assertTrue(migrate_one(config))

            self.assertEqual(read_json(target / "Keep.json")["value"], "target")
            self.assertNotEqual(read_json(target / "KeepSourceCopy.json")["meta_data"]["uuid"], keep_uuid)
            self.assertEqual(read_json(target / "KeepSourceCopy.json")["value"], "source_copy")
            self.assertEqual(read_json(target / "SameName.json")["meta_data"]["uuid"], target_name_uuid)
            self.assertEqual(read_json(target / "SameName (1).json")["meta_data"]["uuid"], source_name_uuid)
            self.assertTrue((target / "MissingUuid.json").is_file())
            self.assertTrue(read_json(target / "MissingUuid.json")["meta_data"]["uuid"])
            self.assertEqual(read_json(target / "DupA.json")["meta_data"]["uuid"], duplicated_uuid)
            self.assertNotEqual(read_json(target / "DupB.json")["meta_data"]["uuid"], duplicated_uuid)
            self.assertFalse((target / "Broken.json").exists())
            self.assertFalse((target / "DefaultUuid.json").exists())

            summary = config["detail"]["summary"]
            self.assertEqual(summary["migrated"], 5)
            self.assertEqual(summary["skipped_same_uuid"], 1)
            self.assertEqual(summary["skipped_default_uuid"], 1)
            self.assertEqual(summary["invalid_json"], 1)

    def test_task_sequence_uuid_folder_inserts_missing_meta_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source" / "task_sequence"
            target = root / "target" / "task_sequence"

            keep_uuid = "55555555-5555-5555-5555-555555555555"
            write_json(target / "Keep.json", [{"meta_data": {"uuid": keep_uuid}}, {"task": "target"}])
            write_json(source / "KeepSource.json", [{"meta_data": {"uuid": keep_uuid}}, {"task": "source"}])
            write_json(source / "NoMeta.json", [{"task": "source"}])

            config = {
                "name": "自定义任务序列",
                "type": "folder_uuid_json",
                "uuid_kind": "task_sequence",
                "path_from": source,
                "path_to": target,
            }

            self.assertTrue(migrate_one(config))

            self.assertEqual(read_json(target / "Keep.json")[1]["task"], "target")
            migrated = read_json(target / "NoMeta.json")
            self.assertIn("meta_data", migrated[0])
            self.assertTrue(migrated[0]["meta_data"]["uuid"])
            self.assertEqual(migrated[1]["task"], "source")

    def test_folder_replace_removes_existing_target_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source" / "config" / "cus_images" / "用户自截"
            target = root / "target" / "config" / "cus_images" / "用户自截"
            source.mkdir(parents=True)
            target.mkdir(parents=True)
            (source / "new.png").write_text("new", encoding="utf-8")
            (target / "old.png").write_text("old", encoding="utf-8")

            config = {
                "name": "用户自截",
                "type": "folder_replace",
                "path_from": source,
                "path_to": target,
            }

            self.assertTrue(migrate_one(config))
            self.assertTrue((target / "new.png").is_file())
            self.assertFalse((target / "old.png").exists())

    def test_write_migration_report_serializes_paths_recursively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            staging_root = Path(temp_dir)
            report_path = write_migration_report(
                staging_root,
                [
                    {
                        "name": "用户自截",
                        "status": "migrated",
                        "locations": [Path("config") / "cus_images" / "用户自截"],
                        "target_locations": [Path("config") / "cus_images" / "用户自截"],
                        "path_from": staging_root / "source",
                        "path_to": staging_root / "target",
                        "detail": {
                            "operation": "replace_folder",
                            "paths": [staging_root / "target" / "new.png"],
                        },
                    }
                ],
            )

            report = read_json(report_path)
            result = report["results"][0]
            self.assertEqual(result["locations"], [str(Path("config") / "cus_images" / "用户自截")])
            self.assertEqual(result["target_locations"], [str(Path("config") / "cus_images" / "用户自截")])
            self.assertEqual(result["detail"]["paths"], [str(staging_root / "target" / "new.png")])


if __name__ == "__main__":
    unittest.main()
