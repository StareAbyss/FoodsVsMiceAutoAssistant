import shutil
from pathlib import Path
from typing import Any


PRESERVED_NAMES = {".venv", "backups", "update_cache", "FAA-恢复到备份.bat"}


def path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size

    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def version_area_size(root: Path) -> int:
    root = Path(root)
    total = 0
    for item in root.iterdir():
        if item.name in PRESERVED_NAMES:
            continue
        total += path_size(item)
    return total


def free_space(path: Path) -> int:
    target = Path(path)
    while not target.exists() and target.parent != target:
        target = target.parent
    return shutil.disk_usage(target).free


def format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def estimate_update_space(
    root: Path,
    staging: Path | None = None,
    safety_margin: int = 512 * 1024 * 1024,
) -> dict[str, Any]:
    root = Path(root).resolve()
    staging = Path(staging).resolve() if staging else None

    backup_size = version_area_size(root)
    staging_size = path_size(staging) if staging else 0
    required = backup_size + staging_size + safety_margin
    available = free_space(root)

    return {
        "backup_size": backup_size,
        "staging_size": staging_size,
        "safety_margin": safety_margin,
        "required": required,
        "available": available,
        "enough": available >= required,
        "backup_size_text": format_bytes(backup_size),
        "staging_size_text": format_bytes(staging_size),
        "safety_margin_text": format_bytes(safety_margin),
        "required_text": format_bytes(required),
        "available_text": format_bytes(available),
    }
