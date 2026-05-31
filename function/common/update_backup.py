import json
import shutil
from pathlib import Path
from typing import Any

from function.common.update_space import format_bytes, path_size


BACKUP_PREFIXES = ("FAA.backup.", "FAA.before-restore.")


def backups_root(root: Path) -> Path:
    return Path(root) / "backups"


def is_backup_dir(path: Path) -> bool:
    return path.is_dir() and any(path.name.startswith(prefix) for prefix in BACKUP_PREFIXES)


def ensure_backup_child(root: Path, backup_dir: Path) -> Path:
    root = backups_root(root).resolve()
    backup_dir = Path(backup_dir).resolve()
    if backup_dir == root or root not in backup_dir.parents:
        raise ValueError(f"Backup path is outside backups directory: {backup_dir}")
    if not is_backup_dir(backup_dir):
        raise ValueError(f"Not a managed FAA backup directory: {backup_dir}")
    return backup_dir


def read_backup_state(backup_dir: Path) -> dict[str, Any]:
    state_path = Path(backup_dir) / ".update_state.json"
    if not state_path.is_file():
        return {}
    return json.loads(state_path.read_text(encoding="utf-8"))


def list_backups(root: Path) -> list[dict[str, Any]]:
    backup_root = backups_root(root)
    if not backup_root.is_dir():
        return []

    backups = []
    for backup_dir in backup_root.iterdir():
        if not is_backup_dir(backup_dir):
            continue
        state = read_backup_state(backup_dir)
        size = path_size(backup_dir)
        stat = backup_dir.stat()
        backups.append(
            {
                "name": backup_dir.name,
                "path": str(backup_dir),
                "version": state.get("version", ""),
                "tag": state.get("tag", ""),
                "commit": state.get("commit", ""),
                "pr": state.get("pr"),
                "created_at": state.get("installed_at") or state.get("packaged_at") or "",
                "modified_at": stat.st_mtime,
                "size": size,
                "size_text": format_bytes(size),
                "state": state,
            }
        )

    return sorted(backups, key=lambda item: item["modified_at"], reverse=True)


def backup_summary(root: Path) -> dict[str, Any]:
    backups = list_backups(root)
    total_size = sum(item["size"] for item in backups)
    return {
        "count": len(backups),
        "total_size": total_size,
        "total_size_text": format_bytes(total_size),
        "backups": backups,
    }


def delete_backup(root: Path, backup_dir: Path) -> Path:
    backup_dir = ensure_backup_child(root, backup_dir)
    shutil.rmtree(backup_dir)
    return backup_dir
