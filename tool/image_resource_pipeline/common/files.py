"""共用文件命名、CSV 输出与完整图片替换。"""

import csv
import os
import re
import shutil
import tempfile
from pathlib import Path

def safe_filename(name: str) -> str:
    """Keep the Excel display name, only replacing characters illegal on Windows."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().rstrip(".")


def collect_pngs(root: Path) -> dict[str, Path]:
    """Collect png files recursively, keyed by filename stem."""
    files: dict[str, Path] = {}
    if not root.exists():
        return files
    for path in sorted(root.rglob("*.png")):
        files[path.stem] = path
    return files


def category_for_path(root: Path, path: Path) -> str:
    parent = path.parent
    if parent == root:
        return ""
    return str(parent.relative_to(root))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sort_rows_by_type_name(rows: list[dict[str, object]], type_key: str = "类型", name_key: str = "名称"):
    """Sort CSV rows by type first, then name."""
    return sorted(rows, key=lambda row: (str(row.get(type_key, "")), str(row.get(name_key, ""))))


def copy_local_source(source: str, target: Path) -> None:
    src = Path(source)
    if not src.exists():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)

def atomic_copy(source: Path, target: Path) -> bool:
    """完整写入后替换图片；内容相同时不触碰现有文件，返回是否发生变化。"""
    if target.is_file() and source.read_bytes() == target.read_bytes():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".tmp", delete=False) as file:
        temporary = Path(file.name)
    try:
        shutil.copyfile(str(source), str(temporary))
        os.replace(str(temporary), str(target))
    finally:
        temporary.unlink(missing_ok=True)
    return True
