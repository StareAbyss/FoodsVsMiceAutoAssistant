"""FAA 微调方案编辑器使用的纯数据模型。"""

from __future__ import annotations

import copy
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


OPTION_KEYS = {
    "recording",
    "cd_after_use_random",
    "senior_setting",
    "auto_mat_card",
    "enable_auto_card",
}
REMOVED_OPTION_KEYS = {
    "timestamp",
    "recording_player",
    "cd_after_use_random_range",
    "mat_card_first",
    "ban_state",
}
AUTO_CARD_KEYS = ("icecream", "god", "ikun", "timer")
BUILT_IN_TWEAK_PLAN_UUIDS = {
    "!默认": "00000000-0000-0000-0000-000000000000",
    "高级战斗": "00000000-0000-0000-0000-000000000001",
    "慢速放卡": "00000000-0000-0000-0000-000000000002",
    "禁用自动卡片": "00000000-0000-0000-0000-000000000003",
    "开启录制": "00000000-0000-0000-0000-000000000004",
}


def generate_plan_uuid() -> str:
    """按战斗方案编辑器现行规则生成时间型 UUID。"""
    return str(uuid.uuid1())


def get_export_target_uuid(path: Path) -> str:
    """
    根据战斗方案“另存为”规则确定导出 UUID。

    新文件生成 UUID1；覆盖已有方案时沿用目标文件的有效 UUID。目标文件无法
    解析或缺少有效 UUID 时生成新的 UUID1。

    Args:
        path: 用户选择的 JSON 导出目标。

    Returns:
        应写入导出方案的 UUID 字符串。
    """
    if path.is_file():
        try:
            with path.open("r", encoding="utf-8") as file:
                target_uuid = json.load(file).get("meta_data", {}).get("uuid")
            uuid.UUID(str(target_uuid))
            return str(target_uuid)
        except (OSError, json.JSONDecodeError, AttributeError, TypeError, ValueError):
            pass
    return generate_plan_uuid()


def _optional_bool(meta_data: dict[str, Any], key: str) -> bool | None:
    """读取可缺省布尔值，格式异常时按缺省处理。"""
    value = meta_data.get(key)
    return value if isinstance(value, bool) else None


@dataclass
class TweakPlanDraft:
    """表示一份可保留“继承默认值”语义的微调方案草稿。"""

    plan_uuid: str = field(default_factory=generate_plan_uuid)
    version: str = "0.3"
    faa_version: str | None = None
    tips: str = ""
    recording: bool | None = None
    timestamp: bool | None = None
    recording_player: int | None = None
    random_interval_mode: str = "inherit"
    random_interval_min: float = 0.05
    random_interval_max: float = 0.25
    senior_setting: bool | None = None
    auto_mat_card_enabled: bool | None = None
    auto_mat_card_first: bool | None = None
    enable_auto_card: dict[str, bool | None] = field(
        default_factory=lambda: {key: None for key in AUTO_CARD_KEYS}
    )
    unknown_meta_data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "TweakPlanDraft":
        """
        从微调方案 JSON 对象创建草稿。

        缺失选项保留为 ``None``，用于在界面中表示“继承默认值”。未知元数据
        会原样保留，避免 Demo 导出时意外丢失将来新增的字段。

        Args:
            data: 顶层包含 ``meta_data`` 的微调方案对象。

        Returns:
            可供界面编辑和再次序列化的草稿。

        Raises:
            ValueError: 顶层或 ``meta_data`` 不是 JSON 对象。
        """
        if not isinstance(data, dict):
            raise ValueError("微调方案顶层必须是 JSON 对象")
        meta_data = data.get("meta_data")
        if not isinstance(meta_data, dict):
            raise ValueError("微调方案缺少 meta_data 对象")

        random_mode = "inherit"
        random_min = 0.05
        random_max = 0.25
        random_settings = meta_data.get("cd_after_use_random")
        if isinstance(random_settings, dict):
            interval = random_settings.get("range")
            if (
                    isinstance(interval, list)
                    and len(interval) == 2
                    and all(isinstance(value, (int, float)) for value in interval)
            ):
                random_min, random_max = float(interval[0]), float(interval[1])
            if isinstance(random_settings.get("active"), bool):
                random_mode = "range" if random_settings["active"] else "off"
        raw_recording = meta_data.get("recording")
        if isinstance(raw_recording, dict):
            recording = _optional_bool(raw_recording, "active")
            timestamp = _optional_bool(raw_recording, "timestamp")
            recording_player = raw_recording.get("player")
        else:
            recording = None
            timestamp = None
            recording_player = None
        if recording_player not in (1, 2):
            recording_player = None

        raw_auto_card = meta_data.get("enable_auto_card")
        enable_auto_card = {key: None for key in AUTO_CARD_KEYS}
        if isinstance(raw_auto_card, dict):
            for key in AUTO_CARD_KEYS:
                if isinstance(raw_auto_card.get(key), bool):
                    enable_auto_card[key] = raw_auto_card[key]

        raw_auto_mat_card = meta_data.get("auto_mat_card")
        auto_mat_card_enabled = None
        auto_mat_card_first = None
        if isinstance(raw_auto_mat_card, dict):
            if isinstance(raw_auto_mat_card.get("enabled"), bool):
                auto_mat_card_enabled = raw_auto_mat_card["enabled"]
            if isinstance(raw_auto_mat_card.get("use_first"), bool):
                auto_mat_card_first = raw_auto_mat_card["use_first"]

        # 已废弃字段不参与读取，也不在编辑器再次保存时写回。
        known_keys = {
            "uuid",
            "version",
            "faa_version",
            "tips",
            *OPTION_KEYS,
            *REMOVED_OPTION_KEYS,
        }
        unknown_meta_data = {
            key: copy.deepcopy(value)
            for key, value in meta_data.items()
            if key not in known_keys
        }

        return cls(
            plan_uuid=str(meta_data.get("uuid") or generate_plan_uuid()),
            version=str(meta_data.get("version", "0.3")),
            faa_version=(
                str(meta_data["faa_version"])
                if meta_data.get("faa_version") is not None
                else None
            ),
            tips=str(meta_data.get("tips", "")),
            recording=recording,
            timestamp=timestamp,
            recording_player=recording_player,
            random_interval_mode=random_mode,
            random_interval_min=random_min,
            random_interval_max=random_max,
            senior_setting=_optional_bool(meta_data, "senior_setting"),
            auto_mat_card_enabled=auto_mat_card_enabled,
            auto_mat_card_first=auto_mat_card_first,
            enable_auto_card=enable_auto_card,
            unknown_meta_data=unknown_meta_data,
        )

    @classmethod
    def load(cls, path: Path) -> "TweakPlanDraft":
        """从 UTF-8 JSON 文件读取微调方案草稿。"""
        with path.open("r", encoding="utf-8") as file:
            return cls.from_mapping(json.load(file))

    def to_mapping(self) -> dict[str, Any]:
        """
        生成可写入磁盘的稀疏微调方案对象。

        Returns:
            顶层包含 ``meta_data`` 的字典；选择“继承”的选项不会被写入。
        """
        meta_data = copy.deepcopy(self.unknown_meta_data)
        meta_data.update(
            {
                "uuid": self.plan_uuid,
                "version": self.version,
            }
        )
        if self.faa_version is not None:
            meta_data["faa_version"] = self.faa_version
        meta_data["tips"] = self.tips

        recording_options = {}
        if self.recording is not None:
            recording_options["active"] = self.recording
        if self.timestamp is not None:
            recording_options["timestamp"] = self.timestamp
        if self.recording_player is not None:
            recording_options["player"] = self.recording_player
        if recording_options:
            meta_data["recording"] = recording_options

        if self.senior_setting is not None:
            meta_data["senior_setting"] = self.senior_setting

        if self.random_interval_mode == "off":
            meta_data["cd_after_use_random"] = {
                "active": False,
                "range": [
                    self.random_interval_min,
                    self.random_interval_max,
                ],
            }
        elif self.random_interval_mode == "range":
            meta_data["cd_after_use_random"] = {
                "active": True,
                "range": [
                    self.random_interval_min,
                    self.random_interval_max,
                ],
            }

        explicit_auto_mat_card = {}
        if self.auto_mat_card_enabled is not None:
            explicit_auto_mat_card["enabled"] = self.auto_mat_card_enabled
        if self.auto_mat_card_first is not None:
            explicit_auto_mat_card["use_first"] = self.auto_mat_card_first
        if explicit_auto_mat_card:
            meta_data["auto_mat_card"] = explicit_auto_mat_card

        explicit_auto_card = {
            key: value
            for key, value in self.enable_auto_card.items()
            if value is not None
        }
        if explicit_auto_card:
            meta_data["enable_auto_card"] = explicit_auto_card

        return {"meta_data": meta_data}

    def validation_messages(self) -> list[str]:
        """返回阻止导出的数据校验错误。"""
        messages = []
        try:
            uuid.UUID(self.plan_uuid)
        except (ValueError, AttributeError):
            messages.append("UUID 格式无效")

        if not self.version.strip():
            messages.append("版本号不能为空")
        if self.random_interval_mode == "range":
            if self.random_interval_min < 0 or self.random_interval_max < 0:
                messages.append("放卡间隔不能为负数")
            if self.random_interval_min > self.random_interval_max:
                messages.append("放卡间隔下限不能大于上限")
        return messages

    def to_json(self) -> str:
        """生成带中文字符和四空格缩进的 JSON 预览文本。"""
        return json.dumps(self.to_mapping(), ensure_ascii=False, indent=4)
