import copy
import json
import shutil
import time
import uuid
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
        "group": "配置文件",
        "type": "file",
        "locations": [
            Path("config") / "settings.json",
            Path("config") / "opt_main.json",
        ],
    },
    {
        "name": "配置文件 - 关卡全局方案",
        "group": "配置文件",
        "type": "file",
        "locations": [
            Path("config") / "stage_plan.json",
        ],
    },
    {
        "name": "配置文件 - 自定义关卡信息",
        "group": "配置文件",
        "type": "file",
        "locations": [
            Path("config") / "stage_info_extra.json",
        ],
    },
    {
        "name": "用户自截",
        "group": "用户自定义图像",
        "type": "folder_replace",
        "locations": [
            Path("config") / "cus_images" / "用户自截",
            Path("resource") / "image" / "common" / "用户自截",
        ],
        "target_location": Path("config") / "cus_images" / "用户自截",
    },
    {
        "name": "背包道具 - 需删除",
        "group": "用户自定义图像",
        "type": "folder_replace",
        "locations": [
            Path("config") / "cus_images" / "背包_道具_需删除的",
        ],
    },
    {
        "name": "背包装备 - 需使用",
        "group": "用户自定义图像",
        "type": "folder_replace",
        "locations": [
            Path("config") / "cus_images" / "背包_装备_需使用的",
        ],
    },
    {
        "name": "战斗方案",
        "group": "方案与任务",
        "type": "folder_uuid_json",
        "uuid_kind": "dict_meta",
        "locations": [
            Path("battle_plan"),
        ],
    },
    {
        "name": "微调方案",
        "group": "方案与任务",
        "type": "folder_uuid_json",
        "uuid_kind": "dict_meta",
        "locations": [
            Path("tweak_plan"),
        ],
    },
    {
        "name": "自定义任务序列",
        "group": "方案与任务",
        "type": "folder_uuid_json",
        "uuid_kind": "task_sequence",
        "locations": [
            Path("task_sequence"),
        ],
    },
    {
        "name": "公会管理器数据",
        "group": "其他用户数据",
        "type": "folder",
        "locations": [
            Path("logs") / "guild_manager",
        ],
    },
    {
        "name": "战斗方案 - 未激活",
        "group": "其他用户数据",
        "type": "folder_uuid_json",
        "uuid_kind": "dict_meta",
        "locations": [
            Path("battle_plan_not_active"),
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


def resolve_config_locations(config: dict) -> tuple[list[Path], list[Path]]:
    locations = [Path(location) for location in config["locations"]]
    if config.get("target_location"):
        target_locations = [Path(config["target_location"])]
    else:
        target_locations = locations
    return locations, target_locations


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
        locations, target_locations = resolve_config_locations(config)
        path_from = find_source_path(source_root, locations)
        path_to = find_target_path(target_root, target_locations, allow_missing_target)
        config["locations"] = locations
        config["target_locations"] = target_locations
        config["path_from"] = path_from
        config["path_to"] = path_to
        config["available"] = path_from is not None and path_to is not None
        plan.append(config)

    return plan


def generate_uuid() -> str:
    value = str(uuid.uuid1())
    time.sleep(0.001)
    return value


def read_json(path: Path):
    with path.open(mode="r", encoding="utf-8") as file:
        return json.load(file)


def is_legacy_battle_plan(data) -> bool:
    return isinstance(data, dict) and "card" in data and ("player" in data or "uuid" in data)


def ensure_dict_meta_uuid(data) -> tuple[str, bool, str]:
    if not isinstance(data, dict):
        raise ValueError("JSON root is not an object.")

    meta_data = data.get("meta_data")
    if isinstance(meta_data, dict) and meta_data.get("uuid"):
        return meta_data["uuid"], False, "meta_data"

    if data.get("uuid"):
        return data["uuid"], False, "uuid"

    new_uuid = generate_uuid()
    if is_legacy_battle_plan(data):
        data["uuid"] = new_uuid
        return new_uuid, True, "uuid"

    if not isinstance(meta_data, dict):
        meta_data = {}
        data["meta_data"] = meta_data
    meta_data["uuid"] = new_uuid
    return new_uuid, True, "meta_data"


def set_dict_meta_uuid(data, new_uuid: str, uuid_location: str) -> None:
    if uuid_location == "uuid":
        data["uuid"] = new_uuid
        return
    meta_data = data.setdefault("meta_data", {})
    meta_data["uuid"] = new_uuid


def ensure_task_sequence_uuid(data) -> tuple[str, bool, str]:
    if not isinstance(data, list):
        raise ValueError("Task sequence JSON root is not a list.")
    if data and not isinstance(data[0], dict):
        raise ValueError("Task sequence first item is not an object.")

    if data and isinstance(data[0].get("meta_data"), dict) and data[0]["meta_data"].get("uuid"):
        return data[0]["meta_data"]["uuid"], False, "task_sequence"

    new_uuid = generate_uuid()
    meta_item = {
        "meta_data": {
            "uuid": new_uuid,
            "version": "1.0",
        }
    }
    if data and "meta_data" in data[0]:
        data[0]["meta_data"] = meta_item["meta_data"]
    else:
        data.insert(0, meta_item)
    return new_uuid, True, "task_sequence"


def set_task_sequence_uuid(data, new_uuid: str, _uuid_location: str) -> None:
    if not data or not isinstance(data[0], dict):
        data.insert(0, {"meta_data": {"uuid": new_uuid, "version": "1.0"}})
        return
    meta_data = data[0].setdefault("meta_data", {})
    meta_data["uuid"] = new_uuid


UUID_HANDLERS = {
    "dict_meta": (ensure_dict_meta_uuid, set_dict_meta_uuid),
    "task_sequence": (ensure_task_sequence_uuid, set_task_sequence_uuid),
}


def read_uuid_json(path: Path, uuid_kind: str) -> tuple[object, str, bool, str]:
    data = read_json(path)
    ensure_uuid, _set_uuid = UUID_HANDLERS[uuid_kind]
    uuid_value, changed, uuid_location = ensure_uuid(data)
    return data, uuid_value, changed, uuid_location


def collect_target_uuids(folder_to: Path, uuid_kind: str) -> dict[str, Path]:
    target_uuids = {}
    if not folder_to.is_dir():
        return target_uuids

    for file_path in sorted(folder_to.glob("*.json"), key=lambda path: path.name.lower()):
        try:
            _data, uuid_value, _changed, _uuid_location = read_uuid_json(file_path, uuid_kind)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, KeyError, TypeError):
            continue
        if uuid_value and uuid_value not in target_uuids:
            target_uuids[uuid_value] = file_path
    return target_uuids


def unique_destination_path(folder_to: Path, file_name: str) -> Path:
    candidate = folder_to / file_name
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    index = 1
    while True:
        candidate = folder_to / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode="w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
        file.write("\n")


def replace_folder(folder_from: Path, folder_to: Path) -> dict:
    if folder_to.exists():
        if folder_to.is_dir():
            shutil.rmtree(folder_to)
        else:
            folder_to.unlink()
    shutil.copytree(folder_from, folder_to)
    return {"operation": "replace_folder", "from": str(folder_from), "to": str(folder_to)}


def process_uuid_json_folder(folder_from: Path, folder_to: Path, uuid_kind: str) -> dict:
    folder_to.mkdir(parents=True, exist_ok=True)
    _ensure_uuid, set_uuid = UUID_HANDLERS[uuid_kind]
    target_uuids = collect_target_uuids(folder_to, uuid_kind)
    source_seen_uuids = set()
    items = []

    for source_path in sorted(folder_from.glob("*.json"), key=lambda path: path.name.lower()):
        item = {
            "source": str(source_path),
            "target": "",
            "uuid": "",
            "status": "",
            "reason": "",
        }
        try:
            data, uuid_value, generated_missing_uuid, uuid_location = read_uuid_json(source_path, uuid_kind)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
            item["status"] = "invalid_json"
            item["reason"] = str(exc) or exc.__class__.__name__
            items.append(item)
            continue

        item["uuid"] = uuid_value
        if uuid_value in DEFAULT_UUIDS:
            item["status"] = "skipped_default_uuid"
            item["reason"] = "默认 UUID 不迁移，保留目标 FAA 内置方案。"
            items.append(item)
            continue

        if uuid_value in source_seen_uuids:
            old_uuid = uuid_value
            uuid_value = generate_uuid()
            set_uuid(data, uuid_value, uuid_location)
            item["uuid"] = uuid_value
            item["reason"] = f"源目录内 UUID {old_uuid} 撞车，已生成新 UUID。"
        elif uuid_value in target_uuids:
            source_seen_uuids.add(uuid_value)
            item["target"] = str(target_uuids[uuid_value])
            item["status"] = "skipped_same_uuid"
            item["reason"] = "目标 FAA 已存在同 UUID，按规则保留目标文件。"
            items.append(item)
            continue
        elif generated_missing_uuid:
            item["reason"] = "源文件缺少 UUID，已生成新 UUID。"

        source_seen_uuids.add(uuid_value)
        destination = unique_destination_path(folder_to, source_path.name)
        write_json(destination, data)
        target_uuids[uuid_value] = destination
        item["target"] = str(destination)
        item["status"] = "migrated"
        items.append(item)

    summary = {}
    for item in items:
        summary[item["status"]] = summary.get(item["status"], 0) + 1
    return {"operation": "uuid_json_folder", "uuid_kind": uuid_kind, "items": items, "summary": summary}


def migrate_one(config: dict) -> bool:
    migration_type = config["type"]

    path_from = config.get("path_from")
    path_to = config.get("path_to")

    if not path_from or not path_to:
        return False

    path_from = Path(path_from)
    path_to = Path(path_to)

    if migration_type == "file":
        path_to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path_from, path_to)
        config["detail"] = {"operation": "copy_file", "from": str(path_from), "to": str(path_to)}
        return True

    if migration_type == "folder":
        shutil.copytree(path_from, path_to, dirs_exist_ok=True)
        config["detail"] = {"operation": "merge_folder", "from": str(path_from), "to": str(path_to)}
        return True

    if migration_type == "folder_replace":
        config["detail"] = replace_folder(path_from, path_to)
        return True

    if migration_type == "folder_uuid_json":
        config["detail"] = process_uuid_json_folder(path_from, path_to, config.get("uuid_kind", "dict_meta"))
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
