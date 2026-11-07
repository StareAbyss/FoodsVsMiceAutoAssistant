"""只读快照索引与路径校验，不触发网络获取。"""

import re
from datetime import datetime
from pathlib import Path
from .paths import DB_DIR

SNAPSHOT_PATTERNS = {
    "excel": re.compile(r"点我获取更多图像资源 (\d{4}-\d{2}-\d{2})(?:_(\d{2}-\d{2}-\d{2}))?\.xlsx$"),
    "compose": re.compile(r"compose (\d{4}-\d{2}-\d{2})(?:_(\d{2}-\d{2}-\d{2}))?\.xml$"),
    "CardFusion": re.compile(r"CardFusion (\d{4}-\d{2}-\d{2})(?:_(\d{2}-\d{2}-\d{2}))?\.xml$"),
}
SNAPSHOT_FILENAMES = {
    "excel": "点我获取更多图像资源 {stamp}.xlsx",
    "compose": "compose {stamp}.xml",
    "CardFusion": "CardFusion {stamp}.xml",
}

def _sort_key(path: Path, kind: str) -> tuple[datetime, str]:
    match = SNAPSHOT_PATTERNS[kind].fullmatch(path.name)
    if match is None:
        return datetime.min, path.name
    stamp = match.group(1) + ("_" + match.group(2) if match.group(2) else "")
    try:
        return datetime.strptime(stamp, "%Y-%m-%d_%H-%M-%S" if match.group(2) else "%Y-%m-%d"), path.name
    except ValueError:
        return datetime.min, path.name


def latest_snapshot(kind: str, db_dir: Path = DB_DIR) -> Path | None:
    """只查找给定目录中的合法快照名；不从网络读取。"""
    pattern = SNAPSHOT_PATTERNS[kind]
    candidates = [
        path for path in db_dir.iterdir()
        if path.is_file() and pattern.fullmatch(path.name) and _sort_key(path, kind)[0] != datetime.min
    ] if db_dir.is_dir() else []
    return max(candidates, key=lambda path: _sort_key(path, kind)) if candidates else None


def resolve_excel_path(path: Path, db_dir: Path = DB_DIR) -> Path:
    """核对显式输入位于 db 目录，防止旧根目录表重新进入资源流程。"""
    if path.resolve().parent != db_dir.resolve():
        raise ValueError("图像资源 Excel 必须位于 resource/db/，不再读取根目录表格")
    if path.suffix.lower() != ".xlsx" or not path.is_file():
        raise FileNotFoundError(f"图像资源 Excel 不存在：{path}")
    return path
