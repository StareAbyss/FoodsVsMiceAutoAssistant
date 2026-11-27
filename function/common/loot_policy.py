"""战利品工具与运行时共用的人工黑白名单协议。"""

import csv
from pathlib import Path


BLACKLIST_FILENAME = "道具可掉落-黑名单.csv"
WHITELIST_FILENAME = "道具可掉落-白名单.csv"
UNKNOWN_FILENAME = "道具可掉落-未分类.csv"


def read_drop_list(path: str | Path) -> set[tuple[str, str]]:
    """读取人工名单；缺失、表头错误或非法路径字段均报错，避免误清理资源。"""
    entries = set()
    with open(path, encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or not {"类型", "名称"}.issubset(reader.fieldnames):
            raise ValueError(f"名单必须包含类型、名称两列：{path}")
        for row in reader:
            category, name = (row.get("类型") or "").strip(), (row.get("名称") or "").strip()
            if not category and not name:
                continue
            if not category or not name or any(
                value in {".", ".."} or any(char in value for char in '<>:"/\\|?*')
                or any(ord(char) < 32 for char in value)
                for value in (category, name)
            ):
                raise ValueError(f"名单含不完整或非法的类型、名称：{path} 第 {reader.line_num} 行")
            entries.add((category, name))
    return entries
