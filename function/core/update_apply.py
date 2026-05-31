import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def updater_source_path(root: Path) -> Path:
    return root / "plugins" / "updater" / "updater.py"


def copy_updater_to_temp(root: Path) -> Path:
    source = updater_source_path(root)
    if not source.is_file():
        raise FileNotFoundError(f"Updater script not found: {source}")

    temp_root = Path(tempfile.gettempdir()) / "FAA-updater"
    temp_root.mkdir(parents=True, exist_ok=True)
    target = temp_root / f"updater.{timestamp()}.py"
    shutil.copy2(source, target)
    return target


def select_python_executable(root: Path) -> Path:
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    if venv_python.is_file():
        return venv_python
    return Path(sys.executable)


def build_update_command(
    root: Path,
    staging: Path,
    updater_script: Path,
    wait_pid: int | None = None,
    launch: str = "AppInstallRun.bat",
) -> list[str]:
    command = [
        str(select_python_executable(root)),
        str(updater_script),
        "update",
        "--root",
        str(root),
        "--staging",
        str(staging),
        "--launch",
        launch,
    ]
    if wait_pid:
        command.extend(["--wait-pid", str(wait_pid)])
    return command


def build_restore_command(
    root: Path,
    backup: Path,
    updater_script: Path,
    wait_pid: int | None = None,
    launch: str = "AppInstallRun.bat",
) -> list[str]:
    command = [
        str(select_python_executable(root)),
        str(updater_script),
        "restore",
        "--root",
        str(root),
        "--backup",
        str(backup),
        "--launch",
        launch,
    ]
    if wait_pid:
        command.extend(["--wait-pid", str(wait_pid)])
    return command


def launch_update_from_staging(
    root: Path,
    staging: Path,
    wait_pid: int | None = None,
    launch: str = "AppInstallRun.bat",
) -> dict[str, Any]:
    root = Path(root).resolve()
    staging = Path(staging).resolve()
    updater_script = copy_updater_to_temp(root)
    command = build_update_command(root, staging, updater_script, wait_pid=wait_pid or os.getpid(), launch=launch)
    process = subprocess.Popen(command, cwd=updater_script.parent)
    return {
        "pid": process.pid,
        "command": command,
        "updater_script": str(updater_script),
    }


def launch_restore_from_backup(
    root: Path,
    backup: Path,
    wait_pid: int | None = None,
    launch: str = "AppInstallRun.bat",
) -> dict[str, Any]:
    root = Path(root).resolve()
    backup = Path(backup).resolve()
    updater_script = copy_updater_to_temp(root)
    command = build_restore_command(root, backup, updater_script, wait_pid=wait_pid or os.getpid(), launch=launch)
    process = subprocess.Popen(command, cwd=updater_script.parent)
    return {
        "pid": process.pid,
        "command": command,
        "updater_script": str(updater_script),
    }
