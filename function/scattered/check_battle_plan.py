import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from function.globals import EXTRA
from function.globals.get_paths import PATHS
from function.scattered.class_battle_plan_v3d0 import convert_v2_to_v3, json_to_obj
from function.scattered.check_tweak_plan import compare_versions, format_protocol_version
from function.scattered.get_list_battle_plan import get_list_battle_plan


LOGGER = logging.getLogger(__name__)


@dataclass
class BattlePlanCheckResult:
    """汇总一次战斗方案协议检查和自动修复。"""

    current_version: str
    checked_count: int = 0
    migrated_count: int = 0
    repaired_count: int = 0
    high_version_count: int = 0
    messages: list[str] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        """返回是否需要向用户展示检查汇总。"""
        return bool(self.messages)

    def startup_text(self) -> str:
        """生成加载窗口中的战斗方案检查结果。"""
        if self.high_version_count:
            return "存在高版本战斗方案，请先升级 FAA。"
        changed_count = self.migrated_count + self.repaired_count
        if changed_count:
            return f"部分战斗方案已迁移或修复（{changed_count}条）"
        if self.messages:
            return f"部分战斗方案检查失败（{len(self.messages)}条）"
        version = format_protocol_version(self.current_version)
        return f"已检查 [战斗方案] 版本，均为最新版本({version} 协议)"

    def dialog_text(self) -> str:
        """生成战斗方案检查汇总正文。"""
        header = (
            f"当前战斗方案协议：{format_protocol_version(self.current_version)}\n"
            f"本次共检查 {self.checked_count} 个方案。"
        )
        return header + "\n" + "\n".join(self.messages)


def _read_json(path: Path):
    """在全局文件锁保护下读取方案 JSON。"""
    with EXTRA.FILE_LOCK:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)


def _write_json(path: Path, data: dict) -> None:
    """在全局文件锁保护下写回检查后的方案。"""
    with EXTRA.FILE_LOCK:
        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)


def _refresh_uuid_mapping(plan_names: list[str], folder: Path, target_name: str) -> None:
    """
    只读刷新方案 UUID 到路径的映射，不转换格式、不修复文件也不弹窗。

    无法读取、缺少 UUID 或 UUID 重复的文件会记录日志并跳过，等待用户在
    FAA 启动或手动打开相应编辑器时运行完整检查。
    """
    uuid_to_path = {}
    for plan_name in plan_names:
        path = folder / f"{plan_name}.json"
        try:
            data = _read_json(path)
            meta_data = data.get("meta_data") if isinstance(data, dict) else None
            plan_uuid = meta_data.get("uuid") if isinstance(meta_data, dict) else None
            uuid.UUID(str(plan_uuid))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, AttributeError) as error:
            LOGGER.warning(f"[方案刷新] 跳过无法建立 UUID 索引的方案: {path}; 错误: {error}")
            continue
        if plan_uuid in uuid_to_path:
            LOGGER.warning(
                f"[方案刷新] 跳过 UUID 重复的方案: {path}; UUID: {plan_uuid}; "
                f"已索引方案: {uuid_to_path[plan_uuid]}"
            )
            continue
        uuid_to_path[plan_uuid] = str(path)
    setattr(EXTRA, target_name, uuid_to_path)


def refresh_all_battle_plan() -> None:
    """只读刷新全部战斗方案的 UUID 路径索引。"""
    _refresh_uuid_mapping(
        get_list_battle_plan(with_extension=False),
        Path(PATHS["battle_plan"]),
        "BATTLE_PLAN_UUID_TO_PATH",
    )


def check_all_battle_plan(
        current_version: str | None = None,
) -> BattlePlanCheckResult:
    """
    检查全部战斗方案，仅在明确的检查入口转换旧协议并修复 UUID。

    当前协议方案还会通过严格数据类反序列化执行基础结构检查；高版本方案
    只提示升级，不由旧 FAA 写回。UUID 路径索引由调用方另行刷新。
    """
    current_version = current_version or EXTRA.BATTLE_PLAN_VERSION
    result = BattlePlanCheckResult(current_version=current_version)
    seen_uuids = {}

    for plan_name in get_list_battle_plan(with_extension=False):
        path = Path(PATHS["battle_plan"]) / f"{plan_name}.json"
        result.checked_count += 1
        try:
            data = _read_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            result.messages.append(
                f"【{path.name}】方案无法读取或解析，未进行修改（原因：{error}）。"
            )
            continue

        meta_data = data.get("meta_data") if isinstance(data, dict) else None
        source_version = meta_data.get("version") if isinstance(meta_data, dict) else None
        comparison = compare_versions(source_version, current_version)
        need_save = False
        migrated = False
        repair_messages = []

        if comparison == 1:
            result.high_version_count += 1
            result.messages.append(
                f"【{path.name}】您使用了来自高版本 FAA 的方案，请更新软件！"
                f"（您的版本：{format_protocol_version(current_version)}；"
                f"方案版本：{format_protocol_version(source_version)}）。"
            )
            continue

        if comparison == -1 or source_version is None:
            try:
                data = convert_v2_to_v3(v2_data=data)
                data["meta_data"]["version"] = current_version
                meta_data = data["meta_data"]
                need_save = True
                migrated = True
            except (KeyError, TypeError, ValueError) as error:
                result.messages.append(
                    f"【{path.name}】该方案版本过低，仅能转换部分字段，请检查方案"
                    f"（v2.0 → {format_protocol_version(current_version)}，"
                    f"转换失败；原因：{error}）。"
                )
                continue
        elif comparison is None:
            result.messages.append(
                f"【{path.name}】方案版本无法识别，未进行修改"
                f"（方案版本：{format_protocol_version(source_version)}）。"
            )
            continue

        try:
            json_to_obj(data)
        except Exception as error:
            result.messages.append(
                f"【{path.name}】该方案检查到手动篡改，无法安全转换，请检查方案"
                f"（未修改；原因：{error}）。"
            )
            continue

        plan_uuid = meta_data.get("uuid")
        try:
            uuid.UUID(str(plan_uuid))
        except (ValueError, AttributeError):
            plan_uuid = str(uuid.uuid1())
            meta_data["uuid"] = plan_uuid
            need_save = True
            repair_messages.append(
                f"【{path.name}】方案 UUID 无效，已自动修改"
                f"（旧 UUID：无效或缺失；新 UUID：{plan_uuid}）。"
            )
            time.sleep(0.001)

        owner = seen_uuids.get(plan_uuid)
        if owner is not None:
            old_uuid = plan_uuid
            plan_uuid = str(uuid.uuid1())
            meta_data["uuid"] = plan_uuid
            need_save = True
            repair_messages.append(
                f"【{path.name}】方案 UUID 与【{owner.name}】冲突，已自动修改"
                f"（旧 UUID：{old_uuid}；新 UUID：{plan_uuid}）。"
            )
            time.sleep(0.001)
        seen_uuids[plan_uuid] = path

        if need_save:
            try:
                _write_json(path, data)
            except OSError as error:
                result.messages.append(
                    f"【{path.name}】方案检查完成但写回失败，未进行修改（原因：{error}）。"
                )
                continue
            if migrated:
                result.migrated_count += 1
                result.messages.append(
                    f"【{path.name}】该方案版本过低，仅能转换部分字段，请检查方案"
                    f"（v2.0 → {format_protocol_version(current_version)}，已迁移）。"
                )
            if repair_messages:
                result.repaired_count += 1
                result.messages.extend(repair_messages)

    return result


if __name__ == '__main__':
    check_all_battle_plan()
    refresh_all_battle_plan()
    print(EXTRA.BATTLE_PLAN_UUID_TO_PATH)
