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
    # 同一秒内重复准备更新也不能覆盖另一轮正在运行的脚本。
    target = temp_root / f"updater.{timestamp()}.{os.urandom(6).hex()}.py"
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
    launch: str = "",
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


def launch_update_from_staging(
    root: Path,
    staging: Path,
    wait_pid: int | None = None,
    launch: str = "",
) -> dict[str, Any]:
    root = Path(root).resolve()
    staging = Path(staging).resolve()
    # 替换规则属于目标版本；临时副本在移动 FAA 源码后仍能独立运行。
    updater_script = copy_updater_to_temp(staging)
    command = build_update_command(root, staging, updater_script, wait_pid=wait_pid or os.getpid(), launch=launch)
    process = subprocess.Popen(command, cwd=updater_script.parent)
    return {
        "pid": process.pid,
        "command": command,
        "updater_script": str(updater_script),
    }
