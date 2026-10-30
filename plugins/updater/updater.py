import argparse
from contextlib import contextmanager, nullcontext
import os
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from traceback import format_exc
from collections.abc import Callable


ENVIRONMENT_INSTALLER_EXE = "FAA - 环境安装器.exe"
PRESERVED_NAMES = {".venv", "backups", "update_cache"}
# 更新执行期间会移动 FAA 源码，独立脚本不能导入正在替换的模块。
DEFAULT_LAUNCHER_EXE = "FAA - 快速启动.exe"
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
    return log_dir / f"updater.{timestamp()}.{os.getpid()}.log"


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


def version_items(root: Path, preserve_entries: set[str] | None = None) -> list[Path]:
    preserved = {name.casefold() for name in PRESERVED_NAMES | (preserve_entries or set())}
    return [item for item in root.iterdir() if item.name.casefold() not in preserved]


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


def create_backup(root: Path, backups_root: Path, prefix: str, preserve_entries: set[str] | None = None) -> Path:
    backup_dir = backups_root / f"{prefix}.{timestamp()}"
    while backup_dir.exists():
        time.sleep(1)
        backup_dir = backups_root / f"{prefix}.{timestamp()}"

    try:
        move_items(version_items(root, preserve_entries), backup_dir)
        current_state = read_json(state_path(root))
        if current_state:
            write_json(backup_dir / ".update_state.json", current_state)
    except Exception:
        # 备份阶段也可能被占用文件中断；先归还已移动的条目，避免留下半套当前版本。
        if backup_dir.exists():
            move_items([item for item in backup_dir.iterdir() if item.name != ".update_state.json"], root)
        raise

    return backup_dir


def install_packaged_state(root: Path, staging_root: Path) -> None:
    packaged_state = read_json(staging_root / STATE_RELATIVE_PATH)
    if not packaged_state:
        return

    packaged_state.pop("packaged_at", None)
    packaged_state["installed_at"] = datetime.now(timezone.utc).isoformat()
    write_json(state_path(root), packaged_state)


def finalize_preparation(root: Path, staging_root: Path) -> None:
    """FAA 已退出后，按目标源码重新迁移退出时保存的最终配置。

    准备或迁移失败时尚未移动当前版本，保留旧安装和缓存供重试，不能继续备份替换。
    无计划文件的目录仍可供独立文件替换接口使用，但不参与此下载准备协议。
    """
    plan = read_json(staging_root / "update_cache/update_plan.json")
    if not plan:
        return
    if plan.get("schema_version") != 1:
        raise ValueError("无法识别目标版本的更新准备协议，请更新 FAA 更新工具。")
    source = ensure_child(root / "update_cache/staging_work", root / plan["source"], "target source")
    script = source / "plugins/updater/prepare.py"
    if not script.is_file():
        raise FileNotFoundError(f"纯净目标源码已缺失，请重新准备更新：{script}")
    request_path, result_path = source.parent / "final_request.json", source.parent / "final_result.json"
    write_json(request_path, plan["request"])
    result_path.unlink(missing_ok=True)
    console("正在按目标版本规则重新迁移最终用户数据...")
    try:
        process = subprocess.run(
            [sys.executable, "-I", "-X", "utf8", str(script), "--root", str(root),
             "--source", str(source), "--staging", str(staging_root), "--request", str(request_path),
             "--result", str(result_path)],
            cwd=source.parent, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", timeout=600,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if process.returncode:
            raise RuntimeError("最终准备失败，当前版本尚未替换：\n" + process.stdout[-12000:])
        result = read_json(result_path)
        if not result.get("space", {}).get("enough"):
            raise OSError("最终迁移后磁盘空间不足，当前版本尚未替换。")
    except Exception:
        # 重建会先清空预览目录，失败时必须回写计划。重试仍从纯净源码开始，
        # 不能因计划丢失把这份半成品误当成无需准备的完整候选版本。
        write_json(staging_root / "update_cache/update_plan.json", plan)
        raise


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
    """直接启动指定入口。

    Args:
        root: 更新或恢复后的 FAA 根目录。
        entry: 产品入口名称或自定义文件名；为空时不启动。

    Raises:
        FileNotFoundError: 指定入口不存在。
    """
    if not entry:
        return

    entry_path = root / entry
    if not entry_path.is_file():
        raise FileNotFoundError(f"Launch entry not found: {entry_path}")

    subprocess.Popen([str(entry_path)], cwd=root, shell=False, creationflags=subprocess.CREATE_NO_WINDOW)


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


@contextmanager
def update_mutex(root: Path):
    """普通更新 CLI 与原生入口互斥，避免最终迁移期间 FAA 再次启动写配置。

    名称算法与原生 Worker 一致：Windows UTF-16 路径按 C locale 转小写后做 FNV。
    旧版过渡和图形恢复由其原生父进程持锁，直接调用 update/restore 时不再次加锁。
    """
    if sys.platform != "win32":
        yield
        return
    import ctypes
    key = 1469598103934665603
    path = str(root.resolve()).encode("utf-16-le")
    for index in range(0, len(path), 2):
        character = int.from_bytes(path[index:index + 2], "little")
        if 65 <= character <= 90:
            character += 32
        key = ((key ^ character) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.WaitForSingleObject.restype = ctypes.c_uint32
    kernel.ReleaseMutex.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateMutexW(None, False, f"Local\\FAA.NativeLauncher.{key}")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    acquired = kernel.WaitForSingleObject(handle, 0)
    if acquired not in (0, 0x80):
        kernel.CloseHandle(handle)
        raise RuntimeError("另一个 FAA 启动、安装或更新操作正在运行，当前版本未替换。请关闭其他操作后重试。")
    try:
        yield
    finally:
        kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


def update(root: Path, staging_root: Path, launch: str | None, log_path: Path | None = None) -> None:
    root = ensure_directory(root, "root")
    staging_root = ensure_directory(staging_root, "staging")
    ensure_child(root / "update_cache", staging_root, "staging")
    finalize_preparation(root, staging_root)
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
    work_root = root / "update_cache/staging_work"
    if work_root.exists():
        try:
            shutil.rmtree(ensure_child(root / "update_cache", work_root, "update work directory"))
        except OSError as exc:
            console(f"版本替换已完成，更新缓存暂未清理：{exc}")
    if launch:
        console("版本更新完成，正在重新启动 FAA...")
        launch_entry(root, launch)
    else:
        console(f"版本更新完成。请自行运行根目录的 {ENVIRONMENT_INSTALLER_EXE}，准备新版运行环境后启动 FAA。")


def restore(
    root: Path,
    backup_dir: Path,
    launch: str | None,
    log_path: Path | None = None,
    preserve_entries: set[str] | None = None,
    on_phase: Callable[[str], None] | None = None,
) -> None:
    """恢复版本；图形安装器可保留自身和日志，并接收阶段通知。

    保留项只允许根目录内的单个名称。恢复失败时，回滚仍遵守同一保留范围，
    以免移动正在运行的安装器或覆盖当前日志。
    """
    preserve_entries = (preserve_entries or set()) | {ENVIRONMENT_INSTALLER_EXE}
    preserved = {name.casefold() for name in PRESERVED_NAMES | preserve_entries}
    for name in preserve_entries or set():
        if not name or name in {".", ".."} or "/" in name or "\\" in name or ":" in name:
            raise ValueError(f"preserve entry must be a root-level name: {name}")

    def phase(name: str) -> None:
        if on_phase:
            on_phase(name)

    def restorable_items(directory: Path) -> list[Path]:
        return [item for item in directory.iterdir() if item.name.casefold() not in preserved | {".update_state.json"}]

    root = ensure_directory(root, "root")
    backup_dir = ensure_directory(backup_dir, "backup")
    ensure_child(root / "backups", backup_dir, "backup")
    write_updater_state(root, "restore_started", {"backup": str(backup_dir)})
    console("正在执行版本恢复。")
    console(f"备份目录：{backup_dir}")

    if log_path:
        log(log_path, f"restore root={root} backup={backup_dir}")

    console("正在备份当前版本，便于恢复失败时回滚...")
    phase("backup_current_version")
    new_backup = create_backup(root, root / "backups", "FAA.before-restore", preserve_entries)
    write_updater_state(root, "restore_current_backup_created", {"backup": str(new_backup)})
    console(f"当前版本已备份到：{new_backup}")
    if log_path:
        log(log_path, f"current version backed up: {new_backup}")

    try:
        console("正在把选中的备份复制回 FAA 目录...")
        phase("restoring_backup")
        write_updater_state(root, "restoring_backup", {"backup": str(backup_dir)})
        copy_items(restorable_items(backup_dir), root)

        backup_state = read_json(backup_dir / ".update_state.json")
        if backup_state:
            backup_state["restored_at"] = datetime.now(timezone.utc).isoformat()
            write_json(state_path(root), backup_state)
    except Exception:
        console("恢复失败，正在回滚到恢复前版本...")
        phase("restore_rollback_started")
        failed_dir = root / "backups" / f"FAA.failed-restore.{timestamp()}"
        write_updater_state(root, "restore_rollback_started", {"current_backup": str(new_backup)})
        move_items(version_items(root, preserve_entries), failed_dir)
        copy_items(restorable_items(new_backup), root)
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
    phase("restore_completed")
    if launch:
        console("版本恢复完成，正在重新启动 FAA...")
        launch_entry(root, launch)
        console("FAA 已启动。")
    else:
        console("版本文件恢复完成。")


def main() -> None:
    parser = argparse.ArgumentParser(description="FAA updater")
    subparsers = parser.add_subparsers(dest="command", required=True)

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--root", required=True)
    update_parser.add_argument("--staging", required=True)
    update_parser.add_argument("--launch", default="")
    update_parser.add_argument("--wait-pid", type=int)
    update_parser.add_argument("--wait-timeout", type=int, default=120)

    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("--root", required=True)
    restore_parser.add_argument("--backup", required=True)
    restore_parser.add_argument("--launch", default=DEFAULT_LAUNCHER_EXE)
    restore_parser.add_argument("--wait-pid", type=int)
    restore_parser.add_argument("--wait-timeout", type=int, default=120)
    restore_parser.add_argument("--gui", action="store_true")
    restore_parser.add_argument("--preserve-entry", action="append", default=[])

    args = parser.parse_args()
    root = Path(args.root).resolve()
    log_path = create_log_file(root)
    title = "FAA 自动更新工具" if args.command == "update" else "FAA 版本恢复工具"
    print_header(title, root, log_path)
    try:
        # 取得本轮所有权后才写共享状态。锁被其他轮持有时，只记录自己的日志，
        # 不能覆盖对方的等待、备份或旧版过渡交接信息。
        with update_mutex(root) if args.command == "update" else nullcontext():
            try:
                console("正在等待 FAA 主程序退出，避免文件被占用...")
                write_updater_state(root, "waiting_for_process", {"pid": args.wait_pid})
                wait_for_process_exit(args.wait_pid, log_path, args.wait_timeout)
                console("FAA 主程序已退出，可以安全替换文件。")
                if args.command == "update":
                    update(root, Path(args.staging), args.launch, log_path)
                elif args.command == "restore":
                    report_phase = (lambda phase: console(f"FAA_LAUNCHER_PHASE:{phase}")) if args.gui else None
                    restore(root, Path(args.backup), args.launch or None, log_path, set(args.preserve_entry), report_phase)
            except Exception:
                write_updater_state(root, "failed", {"error": format_exc()})
                raise
        console()
        console("操作已完成。")
        if not getattr(args, "gui", False):
            countdown_and_exit(3)
    except Exception:
        error = format_exc()
        log(log_path, "operation failed")
        log(log_path, error)
        console()
        console("[错误] 操作失败。")
        console(f"详细日志已写入：{log_path}")
        console(error)
        if not getattr(args, "gui", False):
            countdown_and_exit(10)
        sys.exit(1)


if __name__ == "__main__":
    main()
