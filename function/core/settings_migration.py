import copy
import json
import shutil
from pathlib import Path
from typing import Iterable


DEFAULT_UUIDS = {
    "00000000-0000-0000-0000-000000000000",
    "00000000-0000-0000-0000-000000000001",
    "00000000-0000-0000-0000-000000000002",
}


MIGRATION_CONFIGS = [
    {
        "name": "配置文件 - 核心",
        "type": "file",
        "locations": [
            Path("config") / "settings.json",
            Path("config") / "opt_main.json",
        ],
    },
    {
        "name": "配置文件 - 关卡全局方案",
        "type": "file",
        "locations": [
            Path("config") / "stage_plan.json",
        ],
    },
    {
        "name": "用户自截 - 空间服登录界面_1P",
        "type": "file",
        "locations": [
            Path("config") / "cus_images" / "用户自截" / "空间服登录界面_1P.png",
            Path("resource") / "image" / "common" / "用户自截" / "空间服登录界面_1P.png",
        ],
    },
    {
        "name": "用户自截 - 空间服登录界面_2P",
        "type": "file",
        "locations": [
            Path("config") / "cus_images" / "用户自截" / "空间服登录界面_2P.png",
            Path("resource") / "image" / "common" / "用户自截" / "空间服登录界面_2P.png",
        ],
    },
    {
        "name": "用户自截 - 跨服远征_1P",
        "type": "file",
        "locations": [
            Path("config") / "cus_images" / "用户自截" / "跨服远征_1p.png",
            Path("config") / "cus_images" / "用户自截" / "跨服远征_1P.png",
            Path("resource") / "image" / "common" / "用户自截" / "跨服远征_1p.png",
            Path("resource") / "image" / "common" / "用户自截" / "跨服远征_1P.png",
        ],
    },
    {
        "name": "战斗方案",
        "type": "folder_battle_plan",
        "locations": [
            Path("battle_plan"),
        ],
    },
    {
        "name": "战斗方案 - 未激活",
        "type": "folder_battle_plan",
        "locations": [
            Path("battle_plan_not_active"),
        ],
    },
    {
        "name": "公会管理器数据",
        "type": "folder",
        "locations": [
            Path("logs") / "guild_manager",
        ],
    },
    {
        "name": "自定义任务序列",
        "type": "folder_json_only",
        "locations": [
            Path("task_sequence"),
        ],
    },
]


def get_migration_configs() -> list[dict]:
    return copy.deepcopy(MIGRATION_CONFIGS)


def find_source_path(root: Path, locations: Iterable[Path]) -> Path | None:
    for location in locations:
        path = root / location
        if path.exists():
            return path
    return None


def find_target_path(root: Path, locations: list[Path], allow_missing_target: bool) -> Path | None:
    for location in locations:
        path = root / location
        if path.exists():
            return path
    if allow_missing_target and locations:
        return root / locations[0]
    return None


def build_migration_plan(
    source_root: Path,
    target_root: Path,
    configs: list[dict] | None = None,
    allow_missing_target: bool = True,
) -> list[dict]:
    source_root = Path(source_root)
    target_root = Path(target_root)
    plan = []

    for config in get_migration_configs() if configs is None else copy.deepcopy(configs):
        locations = [Path(location) for location in config["locations"]]
        path_from = find_source_path(source_root, locations)
        path_to = find_target_path(target_root, locations, allow_missing_target)
        config["locations"] = locations
        config["path_from"] = path_from
        config["path_to"] = path_to
        config["available"] = path_from is not None and path_to is not None
        plan.append(config)

    return plan


def read_uuid(path: Path) -> str | None:
    with path.open(mode="r", encoding="utf-8") as file:
        data = json.load(file)

    uuid = data.get("uuid")
    if not uuid:
        uuid = data.get("meta_data", {}).get("uuid")
    if uuid in DEFAULT_UUIDS:
        return None
    return uuid


def process_json_files_by_uuid(folder_from: Path, folder_to: Path) -> None:
    folder_to.mkdir(parents=True, exist_ok=True)

    source_uuids = {}
    for file_path in folder_from.glob("*.json"):
        uuid = read_uuid(file_path)
        if uuid:
            source_uuids[uuid] = file_path

    target_uuids = {}
    for file_path in folder_to.glob("*.json"):
        uuid = read_uuid(file_path)
        if uuid:
            target_uuids[uuid] = file_path

    common_uuids = set(source_uuids) & set(target_uuids)
    source_only_uuids = set(source_uuids) - set(target_uuids)

    for uuid in common_uuids:
        with source_uuids[uuid].open(mode="r", encoding="utf-8") as file:
            data = json.load(file)
        with target_uuids[uuid].open(mode="w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

    for uuid in source_only_uuids:
        shutil.copy2(source_uuids[uuid], folder_to / source_uuids[uuid].name)


def migrate_one(config: dict) -> bool:
    path_from = config.get("path_from")
    path_to = config.get("path_to")

    if not path_from or not path_to:
        return False

    path_from = Path(path_from)
    path_to = Path(path_to)
    migration_type = config["type"]

    if migration_type == "file":
        path_to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path_from, path_to)
        return True

    if migration_type == "folder":
        shutil.copytree(path_from, path_to, dirs_exist_ok=True)
        return True

    if migration_type == "folder_json_only":
        def ignore_non_json_files(_dir, files):
            return [file for file in files if not file.endswith(".json")]

        shutil.copytree(path_from, path_to, dirs_exist_ok=True, ignore=ignore_non_json_files)
        return True

    if migration_type == "folder_battle_plan":
        process_json_files_by_uuid(path_from, path_to)
        return True

    raise ValueError(f"Unsupported migration type: {migration_type}")


def migrate_user_data(
    source_root: Path,
    target_root: Path,
    selected_names: set[str] | None = None,
    allow_missing_target: bool = True,
) -> list[dict]:
    plan = build_migration_plan(source_root, target_root, allow_missing_target=allow_missing_target)

    results = []
    for config in plan:
        if selected_names is not None and config["name"] not in selected_names:
            config["status"] = "skipped"
            results.append(config)
            continue

        if not config["available"]:
            config["status"] = "unavailable"
            results.append(config)
            continue

        migrate_one(config)
        config["status"] = "migrated"
        results.append(config)

    return results
