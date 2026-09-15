"""微调方案协议版本检查、兼容迁移与扫描结果描述。"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from itertools import zip_longest
from pathlib import Path
from typing import Any

from function.core.tweak_plan_editor_model import (
    AUTO_CARD_KEYS,
    BUILT_IN_TWEAK_PLAN_UUIDS,
    REMOVED_OPTION_KEYS,
    TweakPlanDraft,
    generate_plan_uuid,
)
from function.globals.get_paths import PATHS
from function.scattered.get_list_battle_plan import get_list_tweak_plan


ISSUE_LOW_VERSION = "low_version"
ISSUE_CURRENT_INVALID = "current_invalid"
ISSUE_HIGH_VERSION = "high_version"
ISSUE_UNREADABLE = "unreadable"
ISSUE_WRITE_FAILED = "write_failed"
LOGGER = logging.getLogger(__name__)


def format_protocol_version(version: Any) -> str:
    """统一把协议版本展示为 ``v0.3`` 形式。"""
    if version is None:
        return "未记录"
    text = str(version).strip()
    if not text or text == "未记录":
        return "未记录"
    return text if text.lower().startswith("v") else f"v{text}"


@dataclass
class TweakPlanScanIssue:
    """记录一份微调方案在版本扫描中的处理结果。"""

    path: Path
    category: str
    source_version: str
    message: str


@dataclass
class TweakPlanScanResult:
    """汇总一次微调方案目录扫描，供启动页和编辑器共同展示。"""

    current_version: str
    checked_at: datetime = field(default_factory=datetime.now)
    checked_count: int = 0
    migrated_count: int = 0
    repaired_count: int = 0
    high_version_count: int = 0
    issues: list[TweakPlanScanIssue] = field(default_factory=list)

    @property
    def changed_count(self) -> int:
        """返回本次成功写回当前协议的方案数量。"""
        return self.migrated_count + self.repaired_count

    @property
    def has_issues(self) -> bool:
        """返回是否需要向用户展示汇总弹窗。"""
        return bool(self.issues)

    def startup_text(self) -> str:
        """生成加载窗口中的版本检查结果。"""
        if self.high_version_count:
            return "您的FAA版本过低，请先升级FAA再使用，否则会产生微调方案报错。"
        if self.migrated_count and not self.repaired_count:
            return f"部分方案老旧已迁移（迁移{self.migrated_count}条）"
        if self.changed_count:
            return f"部分方案老旧或异常，已迁移（迁移{self.changed_count}条）"
        if self.issues:
            return f"部分微调方案检查失败（{len(self.issues)}条），请查看提示。"
        version = format_protocol_version(self.current_version)
        return f"已检查 [微调方案] 版本，均为最新版本({version} 协议)"

    def editor_status_text(self) -> str:
        """生成微调方案编辑器右上角的最近检查状态。"""
        checked_time = self.checked_at.strftime("%Y-%m-%d %H:%M:%S")
        if not self.issues:
            return f"目前方案均为最新版本，上次检查：{checked_time}"
        if self.high_version_count:
            return f"发现高版本方案，请升级 FAA。上次检查：{checked_time}"
        if self.changed_count:
            return f"已迁移 {self.changed_count} 个方案，请核实。上次检查：{checked_time}"
        return f"发现 {len(self.issues)} 个异常方案。上次检查：{checked_time}"

    def dialog_text(self) -> str:
        """生成包含全部异常方案的单个汇总弹窗正文。"""
        lines = [
            f"当前微调方案协议：{format_protocol_version(self.current_version)}",
            f"本次共检查 {self.checked_count} 个方案。",
        ]
        lines.extend(issue.message for issue in self.issues)
        return "\n".join(lines)


@dataclass
class TweakPlanUuidCheckResult:
    """汇总一次微调方案 UUID 检查和自动修复。"""

    checked_count: int = 0
    repaired_count: int = 0
    messages: list[str] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        """返回是否需要向用户展示 UUID 检查汇总。"""
        return bool(self.messages)


def _parse_version(version: Any) -> tuple[int, ...] | None:
    """把 ``0.3`` 或 ``v0.3`` 转为可比较的整数元组。"""
    if not isinstance(version, str):
        return None
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", version.strip(), re.IGNORECASE)
    if match is None:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def compare_versions(source_version: Any, current_version: str) -> int | None:
    """比较方案和当前协议版本，无法解析时返回 ``None``。"""
    source = _parse_version(source_version)
    current = _parse_version(current_version)
    if source is None or current is None:
        return None
    for source_part, current_part in zip_longest(source, current, fillvalue=0):
        if source_part < current_part:
            return -1
        if source_part > current_part:
            return 1
    return 0


def _is_number(value: Any) -> bool:
    """判断值是否为 JSON 数字，并排除 Python 中属于整数子类的布尔值。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_current_tweak_plan(data: Any, current_version: str) -> list[str]:
    """
    对声明为当前协议的微调方案执行基础结构与类型检查。

    微调方案允许省略普通选项以继承默认方案，因此这里只检查已经写入的字段；
    一旦字段存在，就必须符合当前协议的结构和类型。
    """
    if not isinstance(data, dict):
        return ["JSON 顶层不是对象"]
    meta_data = data.get("meta_data")
    if not isinstance(meta_data, dict):
        return ["缺少 meta_data 对象"]

    messages = []
    try:
        uuid.UUID(str(meta_data.get("uuid", "")))
    except (ValueError, AttributeError):
        messages.append("UUID 无效或缺失")

    if compare_versions(meta_data.get("version"), current_version) != 0:
        messages.append("格式版本与当前协议不一致")
    if not isinstance(meta_data.get("faa_version"), str) or not meta_data["faa_version"].strip():
        messages.append("缺少有效的 FAA 版本记录")
    if not isinstance(meta_data.get("tips"), str):
        messages.append("方案说明不是文本")

    removed = [key for key in REMOVED_OPTION_KEYS if key in meta_data]
    removed.extend(key for key in meta_data if key.endswith("-tip"))
    if removed:
        messages.append(f"包含已废弃字段：{', '.join(sorted(removed))}")

    recording = meta_data.get("recording")
    if recording is not None:
        if not isinstance(recording, dict):
            messages.append("recording 不是对象")
        else:
            unexpected = set(recording) - {"active", "timestamp", "player"}
            if unexpected:
                messages.append("recording 包含未知字段")
            if "active" in recording and not isinstance(recording["active"], bool):
                messages.append("recording.active 不是布尔值")
            if "timestamp" in recording and not isinstance(recording["timestamp"], bool):
                messages.append("recording.timestamp 不是布尔值")
            if "player" in recording and recording["player"] not in (1, 2):
                messages.append("recording.player 不是 1 或 2")

    random_settings = meta_data.get("cd_after_use_random")
    if random_settings is not None:
        if not isinstance(random_settings, dict):
            messages.append("cd_after_use_random 不是对象")
        else:
            interval = random_settings.get("range")
            if not isinstance(random_settings.get("active"), bool):
                messages.append("cd_after_use_random.active 不是布尔值")
            if (
                    not isinstance(interval, list)
                    or len(interval) != 2
                    or not all(_is_number(value) for value in interval)
                    or interval[0] < 0
                    or interval[1] < interval[0]
            ):
                messages.append("cd_after_use_random.range 无效")
            if set(random_settings) - {"active", "range"}:
                messages.append("cd_after_use_random 包含未知字段")

    if "senior_setting" in meta_data and not isinstance(meta_data["senior_setting"], bool):
        messages.append("senior_setting 不是布尔值")

    auto_mat_card = meta_data.get("auto_mat_card")
    if auto_mat_card is not None:
        if not isinstance(auto_mat_card, dict):
            messages.append("auto_mat_card 不是对象")
        else:
            if set(auto_mat_card) - {"enabled", "use_first"}:
                messages.append("auto_mat_card 包含未知字段")
            if any(not isinstance(value, bool) for value in auto_mat_card.values()):
                messages.append("auto_mat_card 包含非布尔值")

    auto_card = meta_data.get("enable_auto_card")
    if auto_card is not None:
        if not isinstance(auto_card, dict):
            messages.append("enable_auto_card 不是对象")
        else:
            if set(auto_card) - set(AUTO_CARD_KEYS):
                messages.append("enable_auto_card 包含未知字段")
            if any(not isinstance(value, bool) for value in auto_card.values()):
                messages.append("enable_auto_card 包含非布尔值")
    return messages


def _prepare_legacy_meta_data(meta_data: dict[str, Any]) -> dict[str, Any]:
    """把可确定语义的 0.1/0.2 字段整理为当前模型能够读取的结构。"""
    converted = copy.deepcopy(meta_data)

    recording = converted.get("recording")
    if isinstance(recording, bool):
        recording_settings = {"active": recording}
    elif isinstance(recording, dict):
        recording_settings = copy.deepcopy(recording)
    else:
        recording_settings = {}
    if isinstance(converted.get("timestamp"), bool):
        recording_settings.setdefault("timestamp", converted["timestamp"])
    if converted.get("recording_player") in (1, 2):
        recording_settings.setdefault("player", converted["recording_player"])
    if recording_settings:
        converted["recording"] = recording_settings

    legacy_interval = converted.get("cd_after_use_random_range", ...)
    if legacy_interval is None:
        converted["cd_after_use_random"] = {
            "active": False,
            "range": [0.05, 0.25],
        }
    elif (
            isinstance(legacy_interval, list)
            and len(legacy_interval) == 2
            and all(_is_number(value) for value in legacy_interval)
    ):
        converted["cd_after_use_random"] = {
            "active": True,
            "range": legacy_interval,
        }

    raw_auto_card = converted.get("enable_auto_card")
    auto_card = copy.deepcopy(raw_auto_card) if isinstance(raw_auto_card, dict) else {}
    raw_auto_mat = converted.get("auto_mat_card")
    auto_mat = copy.deepcopy(raw_auto_mat) if isinstance(raw_auto_mat, dict) else {}
    ban_state = converted.get("ban_state")
    if isinstance(ban_state, dict):
        if isinstance(ban_state.get("mat"), bool):
            auto_mat.setdefault("enabled", not ban_state["mat"])
        for key in ("icecream", "god", "ikun"):
            if isinstance(ban_state.get(key), bool):
                auto_card.setdefault(key, not ban_state[key])
    if isinstance(auto_card.get("mat"), bool):
        auto_mat.setdefault("enabled", auto_card["mat"])
    if isinstance(converted.get("mat_card_first"), bool):
        auto_mat.setdefault("use_first", converted["mat_card_first"])
    if auto_mat:
        converted["auto_mat_card"] = auto_mat
    if auto_card:
        converted["enable_auto_card"] = auto_card

    for key in list(converted):
        if key.endswith("-tip"):
            converted.pop(key)
    return converted


def convert_tweak_plan_to_current(
        data: dict[str, Any],
        current_version: str,
        current_faa_version: str,
) -> dict[str, Any]:
    """
    尽可能保留有效字段并生成当前协议，无法确认的字段回退为缺省语义。

    有效 UUID 保持不变；只有 UUID 本身缺失或无效时才生成新值。未知元数据
    原样保留，旧版提示字段和已废弃字段不会再次写回。
    """
    meta_data = data.get("meta_data")
    if not isinstance(meta_data, dict):
        raise ValueError("缺少 meta_data 对象，无法自动转换")

    prepared = _prepare_legacy_meta_data(meta_data)
    if not isinstance(prepared.get("tips"), str):
        prepared["tips"] = ""
    draft = TweakPlanDraft.from_mapping({"meta_data": prepared})
    try:
        uuid.UUID(draft.plan_uuid)
    except (ValueError, AttributeError):
        draft.plan_uuid = generate_plan_uuid()
    draft.version = current_version
    draft.faa_version = current_faa_version
    return draft.to_mapping()


def _write_plan(path: Path, data: dict[str, Any]) -> None:
    """使用同目录临时文件原子写回方案，避免中断时留下半截 JSON。"""
    temp_path = path.with_name(
        f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    try:
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _read_plan_with_lock(path: Path) -> dict[str, Any]:
    """在 FAA 全局文件锁保护下读取微调方案。"""
    from function.globals import EXTRA

    with EXTRA.FILE_LOCK:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)


def _write_plan_with_lock(path: Path, data: dict[str, Any]) -> None:
    """在 FAA 全局文件锁保护下原子写回微调方案。"""
    from function.globals import EXTRA

    with EXTRA.FILE_LOCK:
        _write_plan(path, data)


def refresh_all_tweak_plan() -> None:
    """只读刷新全部微调方案的 UUID 路径索引。"""
    from function.globals import EXTRA

    uuid_to_path = {}
    folder = Path(PATHS["tweak_battle_plan"])
    for plan_name in get_list_tweak_plan(with_extension=False):
        path = folder / f"{plan_name}.json"
        try:
            data = _read_plan_with_lock(path)
            meta_data = data.get("meta_data") if isinstance(data, dict) else None
            plan_uuid = str(meta_data.get("uuid")) if isinstance(meta_data, dict) else ""
            uuid.UUID(plan_uuid)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, AttributeError) as error:
            LOGGER.warning(f"[微调方案刷新] 跳过无法建立 UUID 索引的方案: {path}; 错误: {error}")
            continue
        if plan_uuid in uuid_to_path:
            LOGGER.warning(
                f"[微调方案刷新] 跳过 UUID 重复的方案: {path}; UUID: {plan_uuid}; "
                f"已索引方案: {uuid_to_path[plan_uuid]}"
            )
            continue
        uuid_to_path[plan_uuid] = str(path)
    EXTRA.TWEAK_BATTLE_PLAN_UUID_TO_PATH = uuid_to_path


def check_all_tweak_plan_uuids() -> TweakPlanUuidCheckResult:
    """
    在明确的检查入口修复微调方案 UUID。

    协议版本迁移由 ``scan_and_migrate_tweak_plans`` 完成；这里检查固定内置
    UUID、无效 UUID 和重复 UUID。UUID 路径索引由调用方另行刷新。
    """
    seen_uuids = {}
    result = TweakPlanUuidCheckResult()
    folder = Path(PATHS["tweak_battle_plan"])
    for plan_name in get_list_tweak_plan(with_extension=False):
        path = folder / f"{plan_name}.json"
        result.checked_count += 1
        try:
            data = _read_plan_with_lock(path)
            meta_data = data.get("meta_data") if isinstance(data, dict) else None
            if not isinstance(meta_data, dict):
                continue
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue

        plan_uuid = str(meta_data.get("uuid", ""))
        expected_uuid = BUILT_IN_TWEAK_PLAN_UUIDS.get(plan_name)
        changed = False
        repair_messages = []
        if expected_uuid is not None and plan_uuid != expected_uuid:
            old_uuid = plan_uuid
            plan_uuid = expected_uuid
            meta_data["uuid"] = plan_uuid
            changed = True
            repair_messages.append(
                f"【{path.name}】内置方案 UUID {old_uuid} 已恢复为固定值：{plan_uuid}"
            )

        try:
            uuid.UUID(plan_uuid)
        except (ValueError, AttributeError):
            plan_uuid = str(uuid.uuid1())
            meta_data["uuid"] = plan_uuid
            changed = True
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
            changed = True
            repair_messages.append(
                f"【{path.name}】方案 UUID 与【{owner.name}】冲突，已自动修改"
                f"（旧 UUID：{old_uuid}；新 UUID：{plan_uuid}）。"
            )
            time.sleep(0.001)
        seen_uuids[plan_uuid] = path

        if changed:
            try:
                _write_plan_with_lock(path, data)
            except OSError as error:
                result.messages.append(
                    f"【{path.name}】方案 UUID 已生成但写回失败，未进行修改（原因：{error}）。"
                )
                continue
            result.repaired_count += 1
            result.messages.extend(repair_messages)
    return result


def scan_and_migrate_tweak_plans(
        tweak_plan_dir: Path,
        current_version: str,
        current_faa_version: str,
) -> TweakPlanScanResult:
    """
    扫描全部微调方案，并迁移低版本或当前版本中结构异常的方案。

    高版本方案只提示，不写回，避免旧 FAA 删除自己无法理解的新字段。严重
    损坏且无法取得 ``meta_data`` 的文件同样只报告，交由用户手动处理。
    """
    result = TweakPlanScanResult(current_version=current_version)
    if not tweak_plan_dir.is_dir():
        return result

    for path in sorted(tweak_plan_dir.glob("*.json"), key=lambda item: item.name.lower()):
        result.checked_count += 1
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            result.issues.append(TweakPlanScanIssue(
                path=path,
                category=ISSUE_UNREADABLE,
                source_version="无法读取",
                message=f"【{path.name}】方案无法读取或解析，未进行修改（原因：{error}）。",
            ))
            continue

        meta_data = data.get("meta_data") if isinstance(data, dict) else None
        source_version = (
            str(meta_data.get("version", "未记录"))
            if isinstance(meta_data, dict)
            else "未记录"
        )
        version_comparison = compare_versions(source_version, current_version)
        if version_comparison == 1:
            result.high_version_count += 1
            result.issues.append(TweakPlanScanIssue(
                path=path,
                category=ISSUE_HIGH_VERSION,
                source_version=source_version,
                message=(
                    f"【{path.name}】您使用了来自高版本 FAA 的方案，请更新软件！"
                    f"（您的版本：{format_protocol_version(current_version)}；"
                    f"方案版本：{format_protocol_version(source_version)}）。"
                ),
            ))
            continue

        validation_messages = validate_current_tweak_plan(data, current_version)
        is_low_version = version_comparison == -1
        if not is_low_version and version_comparison == 0 and not validation_messages:
            continue

        try:
            converted = convert_tweak_plan_to_current(
                data=data,
                current_version=current_version,
                current_faa_version=current_faa_version,
            )
            _write_plan(path, converted)
        except (OSError, ValueError, TypeError) as error:
            if is_low_version:
                failure_message = (
                    f"【{path.name}】该方案版本过低，仅能转换部分字段，请检查方案"
                    f"（{format_protocol_version(source_version)} → "
                    f"{format_protocol_version(current_version)}，转换失败；原因：{error}）。"
                )
            else:
                failure_message = (
                    f"【{path.name}】该方案检查到手动篡改，无法安全转换，请检查方案"
                    f"（未修改；原因：{error}）。"
                )
            result.issues.append(TweakPlanScanIssue(
                path=path,
                category=ISSUE_WRITE_FAILED,
                source_version=source_version,
                message=failure_message,
            ))
            continue

        if is_low_version:
            result.migrated_count += 1
            message = (
                f"【{path.name}】该方案版本过低，仅能转换部分字段，请检查方案"
                f"（{format_protocol_version(source_version)} → "
                f"{format_protocol_version(current_version)}，已迁移）。"
            )
            category = ISSUE_LOW_VERSION
        else:
            result.repaired_count += 1
            reason = "；".join(validation_messages) or "格式版本无法识别"
            message = (
                f"【{path.name}】该方案检查到手动篡改，仅能转换部分字段，请检查方案"
                f"（已转换；原因：{reason}）。"
            )
            category = ISSUE_CURRENT_INVALID
        result.issues.append(TweakPlanScanIssue(
            path=path,
            category=category,
            source_version=source_version,
            message=message,
        ))
    return result
