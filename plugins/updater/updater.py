import argparse
import os
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from traceback import format_exc


PRESERVED_NAMES = {".venv", "backups", "update_cache", "FAA-恢复到备份.bat"}
STATE_RELATIVE_PATH = Path("update_cache") / "update_state.json"
UPDATER_STATE_RELATIVE_PATH = Path("update_cache") / "updater_state.json"


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def console(message: str = "") -> None:
    print(message, flush=True)


def print_header(title: str, root: Path, log_path: Path) -> None:
    console("=" * 60)
    console(title)
    console("=" * 60)
    console(f"FAA 目录：{root}")
    console(f"日志文件：{log_path}")
    console()


def countdown_and_exit(seconds: int = 3) -> None:
    for remaining in range(seconds, 0, -1):
        console(f"窗口将在 {remaining} 秒后自动关闭...")
        time.sleep(1)


def create_log_file(root: Path) -> Path:
    log_dir = root / "update_cache" / "updater_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"updater.{timestamp()}.log"


def log(log_path: Path, message: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(line)


def ensure_directory(path: Path, name: str) -> Path:
    path = path.resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"{name} is not a directory: {path}")
    return path


def ensure_child(parent: Path, child: Path, name: str) -> Path:
    parent = parent.resolve()
    child = child.resolve()
    if child == parent or parent not in child.parents:
        raise ValueError(f"{name} must be inside {parent}: {child}")
    return child


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def state_path(root: Path) -> Path:
    return root / STATE_RELATIVE_PATH


def updater_state_path(root: Path) -> Path:
    return root / UPDATER_STATE_RELATIVE_PATH


def write_updater_state(root: Path, phase: str, details: dict | None = None) -> None:
    write_json(
        updater_state_path(root),
        {
            "phase": phase,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        },
    )


def version_items(root: Path) -> list[Path]:
    return [item for item in root.iterdir() if item.name not in PRESERVED_NAMES]


def move_items(items: list[Path], dest_root: Path) -> None:
    dest_root.mkdir(parents=True, exist_ok=True)
    for item in items:
        shutil.move(str(item), str(dest_root / item.name))


def copy_items(items: list[Path], dest_root: Path) -> None:
    dest_root.mkdir(parents=True, exist_ok=True)
    for item in items:
        dest = dest_root / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)


def create_backup(root: Path, backups_root: Path, prefix: str) -> Path:
    backup_dir = backups_root / f"{prefix}.{timestamp()}"
    while backup_dir.exists():
        time.sleep(1)
        backup_dir = backups_root / f"{prefix}.{timestamp()}"

    move_items(version_items(root), backup_dir)

    current_state = read_json(state_path(root))
    if current_state:
        write_json(backup_dir / ".update_state.json", current_state)

    return backup_dir


def install_packaged_state(root: Path, staging_root: Path) -> None:
    packaged_state = read_json(staging_root / STATE_RELATIVE_PATH)
    if not packaged_state:
        return

    packaged_state.pop("packaged_at", None)
    packaged_state["installed_at"] = datetime.now(timezone.utc).isoformat()
    write_json(state_path(root), packaged_state)


def prune_failed_staging(root: Path, keep: int = 2) -> None:
    failed_root = root / "update_cache" / "failed_staging"
    if not failed_root.is_dir():
        return

    entries = sorted(
        [entry for entry in failed_root.iterdir() if entry.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for entry in entries[keep:]:
        shutil.rmtree(entry)


def launch_entry(root: Path, entry: str | None) -> None:
    if not entry:
        return

    entry_path = root / entry
    if not entry_path.exists():
        raise FileNotFoundError(f"Launch entry not found: {entry_path}")

    subprocess.Popen([str(entry_path)], cwd=root, shell=True)


def wait_for_process_exit(pid: int | None, log_path: Path | None = None, timeout_seconds: int = 120) -> None:
    if not pid:
        return

    deadline = time.monotonic() + timeout_seconds
    if log_path:
        log(log_path, f"waiting for process to exit: pid={pid}")

    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            if log_path:
                log(log_path, f"process exited: pid={pid}")
            return
        time.sleep(0.5)

    raise TimeoutError(f"Process did not exit within {timeout_seconds} seconds: pid={pid}")


def update(root: Path, staging_root: Path, launch: str | None, log_path: Path | None = None) -> None:
    root = ensure_directory(root, "root")
    staging_root = ensure_directory(staging_root, "staging")
    ensure_child(root / "update_cache", staging_root, "staging")
    write_updater_state(root, "update_started", {"staging": str(staging_root)})
    console("正在执行版本更新。")
    console(f"新版本临时目录：{staging_root}")

    if log_path:
        log(log_path, f"update root={root} staging={staging_root}")

    backups_root = root / "backups"
    console("正在备份当前版本...")
    write_updater_state(root, "backup_current_version")
    backup_dir = create_backup(root, backups_root, "FAA.backup")
    write_updater_state(root, "backup_created", {"backup": str(backup_dir)})
    console(f"当前版本已备份到：{backup_dir}")
    if log_path:
        log(log_path, f"backup created: {backup_dir}")

    try:
        console("正在替换为新版本文件...")
        write_updater_state(root, "installing_staging", {"backup": str(backup_dir)})
        move_items([item for item in staging_root.iterdir() if item.name not in PRESERVED_NAMES], root)
        console("正在写入版本记录并清理更新临时文件...")
        install_packaged_state(root, staging_root)
        prune_failed_staging(root)
    except Exception:
        console("更新失败，正在回滚到更新前版本...")
        write_updater_state(root, "rollback_started", {"backup": str(backup_dir)})
        failed_dir = backups_root / f"FAA.failed-update.{timestamp()}"
        move_items(version_items(root), failed_dir)
        move_items([item for item in backup_dir.iterdir() if item.name != ".update_state.json"], root)
        backup_state = read_json(backup_dir / ".update_state.json")
        if backup_state:
            write_json(state_path(root), backup_state)
        write_updater_state(root, "rollback_completed", {"backup": str(backup_dir), "failed": str(failed_dir)})
        raise

    if log_path:
        log(log_path, "update completed")
    write_updater_state(root, "update_completed", {"backup": str(backup_dir)})
    console("版本更新完成，正在重新启动 FAA...")
    launch_entry(root, launch)
    console("FAA 已启动。")


def restore(root: Path, backup_dir: Path, launch: str | None, log_path: Path | None = None) -> None:
    root = ensure_directory(root, "root")
    backup_dir = ensure_directory(backup_dir, "backup")
    ensure_child(root / "backups", backup_dir, "backup")
    write_updater_state(root, "restore_started", {"backup": str(backup_dir)})
    console("正在执行版本恢复。")
    console(f"备份目录：{backup_dir}")

    if log_path:
        log(log_path, f"restore root={root} backup={backup_dir}")

    console("正在备份当前版本，便于恢复失败时回滚...")
    new_backup = create_backup(root, root / "backups", "FAA.before-restore")
    write_updater_state(root, "restore_current_backup_created", {"backup": str(new_backup)})
    console(f"当前版本已备份到：{new_backup}")
    if log_path:
        log(log_path, f"current version backed up: {new_backup}")

    try:
        console("正在把选中的备份复制回 FAA 目录...")
        write_updater_state(root, "restoring_backup", {"backup": str(backup_dir)})
        copy_items([item for item in backup_dir.iterdir() if item.name != ".update_state.json"], root)

        backup_state = read_json(backup_dir / ".update_state.json")
        if backup_state:
            backup_state["restored_at"] = datetime.now(timezone.utc).isoformat()
            write_json(state_path(root), backup_state)
    except Exception:
        console("恢复失败，正在回滚到恢复前版本...")
        failed_dir = root / "backups" / f"FAA.failed-restore.{timestamp()}"
        write_updater_state(root, "restore_rollback_started", {"current_backup": str(new_backup)})
        move_items(version_items(root), failed_dir)
        copy_items([item for item in new_backup.iterdir() if item.name != ".update_state.json"], root)
        previous_state = read_json(new_backup / ".update_state.json")
        if previous_state:
            write_json(state_path(root), previous_state)
        write_updater_state(
            root,
            "restore_rollback_completed",
            {"current_backup": str(new_backup), "failed": str(failed_dir)},
        )
        raise

    if log_path:
        log(log_path, "restore completed")
    write_updater_state(root, "restore_completed", {"backup": str(backup_dir), "previous_current": str(new_backup)})
    console("版本恢复完成，正在重新启动 FAA...")
    launch_entry(root, launch)
    console("FAA 已启动。")


def main() -> None:
    parser = argparse.ArgumentParser(description="FAA updater")
    subparsers = parser.add_subparsers(dest="command", required=True)

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--root", required=True)
    update_parser.add_argument("--staging", required=True)
    update_parser.add_argument("--launch", default="FAA.exe")
    update_parser.add_argument("--wait-pid", type=int)
    update_parser.add_argument("--wait-timeout", type=int, default=120)

    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("--root", required=True)
    restore_parser.add_argument("--backup", required=True)
    restore_parser.add_argument("--launch", default="FAA.exe")
    restore_parser.add_argument("--wait-pid", type=int)
    restore_parser.add_argument("--wait-timeout", type=int, default=120)

    args = parser.parse_args()
    root = Path(args.root).resolve()
    log_path = create_log_file(root)
    title = "FAA 自动更新工具" if args.command == "update" else "FAA 版本恢复工具"
    print_header(title, root, log_path)
    try:
        console("正在等待 FAA 主程序退出，避免文件被占用...")
        write_updater_state(root, "waiting_for_process", {"pid": args.wait_pid})
        wait_for_process_exit(args.wait_pid, log_path, args.wait_timeout)
        console("FAA 主程序已退出，可以安全替换文件。")
        if args.command == "update":
            update(root, Path(args.staging), args.launch, log_path)
        elif args.command == "restore":
            restore(root, Path(args.backup), args.launch, log_path)
        console()
        console("操作已完成。")
        countdown_and_exit(3)
    except Exception:
        error = format_exc()
        log(log_path, "operation failed")
        log(log_path, error)
        write_updater_state(root, "failed", {"error": error})
        console()
        console("[错误] 操作失败。")
        console(f"详细日志已写入：{log_path}")
        console(error)
        countdown_and_exit(10)
        sys.exit(1)


if __name__ == "__main__":
    main()
