"""完成已发布旧更新器的首次过渡，最终文件仍按目标版本自己的规则生成。"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import time


STATE_RELATIVE_PATH = Path("update_cache/legacy_bridge/state.json")
COMPATIBILITY_FILES = (
    "FAA-支持性检测, 仅限Win10+.bat", "FAA-恢复到备份.bat",
    "FAA-卸除运行环境.bat", "FAA-调试模式启动.bat",
    "plugins/launcher_scripts/AppInstallRun.bat", "plugins/launcher_scripts/AppInstallRun.ps1",
    "plugins/launcher_scripts/UVFAAUninstaller.ps1",
)


def read_json(path: Path) -> dict:
    """读取桥接状态，缺失时返回空字典以启动首次交接。"""
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def write_json(path: Path, value: dict) -> None:
    """原子写入本轮原始备份和目标提交，重试不能被后续中间备份覆盖。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    pending.replace(path)


def original_update(root: Path) -> dict:
    """固定首次旧更新器留下的完整原始备份和精确目标提交。"""
    pending = read_json(root / STATE_RELATIVE_PATH)
    if pending:
        if pending.get("schema_version") != 1:
            raise ValueError("无法识别旧版过渡记录，请保留更新日志并联系维护者。")
    else:
        target = read_json(root / "update_cache/update_state.json")
        operation = read_json(root / "update_cache/updater_state.json")
        if operation.get("phase") != "update_completed":
            raise ValueError("没有找到已完成的旧版更新交接，当前文件未修改。")
        pending = {
            "schema_version": 1, "target": target,
            "backup": operation.get("details", {}).get("backup", ""),
        }
    commit = pending.get("target", {}).get("commit", "")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise ValueError("旧版交接缺少精确目标提交，不能改用可变分支下载。")
    backup = Path(pending.get("backup") or "").resolve()
    backups = (root / "backups").resolve()
    if backups not in backup.parents or not backup.is_dir() or not backup.name.startswith("FAA.backup."):
        raise ValueError("旧版原始备份不存在或不在当前 backups 内，已停止过渡。")
    pending["backup"] = str(backup)
    write_json(root / STATE_RELATIVE_PATH, pending)
    return pending


def clean_compatibility_files(root: Path) -> None:
    """只删除带专用标记的过渡脚本和与正式快速入口一致的旧名别名。"""
    for relative in COMPATIBILITY_FILES:
        path = root / relative
        if path.is_file() and b"FAA_LEGACY_UPDATE_BRIDGE" in path.read_bytes():
            path.unlink()
    alias, launcher = root / "FAA.exe", root / "FAA - 快速启动.exe"
    if alias.is_file() and launcher.is_file():
        if hashlib.sha256(alias.read_bytes()).digest() != hashlib.sha256(launcher.read_bytes()).digest():
            raise ValueError("旧名启动入口与正式入口不同，未自动移除，请联系维护者。")
        # 旧名入口先派生缓存内的同一原生程序再退出；Windows 可能短暂保留映像占用。
        for attempt in range(50):
            try:
                alias.unlink(missing_ok=True)
                break
            except PermissionError:
                if attempt == 49:
                    raise
                time.sleep(0.1)


def complete_legacy_update(root: Path, archive_path: Path | None = None, on_progress=None) -> None:
    """从原始旧版本备份完成目标规则迁移，支持失败后通过快速入口重试。

    旧更新器只认识旧清单，首次会先完成一次旧流程。本函数随后获取同一精确提交的
    纯净源码，以首次备份为迁移来源，纠正旧规则可能漏掉或合并不当的内容。
    第二次准备失败时不替换当前目录，原始备份和固定交接记录均保留。

    Args:
        root: 已由旧更新器替换过一轮的 FAA 根目录。
        archive_path: 可选的离线目标源码包；普通自动过渡按精确提交重新下载。
        on_progress: 可选的阶段回调，参数为 0～5 的阶段编号和说明。

    Raises:
        ValueError: 运行位置、精确提交或原始备份不符合旧版交接条件。
        OSError: 空间不足，或准备、清理及替换所需的文件操作失败。
    """
    root = root.resolve()
    if (root / ".git").exists() or not (root / "LICENSE").is_file():
        raise ValueError("旧版过渡只能在 FAA 用户安装目录中运行。")

    def phase(index: int, message: str) -> None:
        """把实际进度传给原生界面，不在下载或替换期间留下无响应的窗口。"""
        print(f"FAA_LEGACY_PHASE:{index}:{message}", flush=True)
        if on_progress:
            on_progress(index, message)

    if read_json(root / "update_cache/update_state.json").get("update_protocol") == 1:
        # 文件替换已成功时，缓存清理失败不能触发再次迁移，覆盖用户之后保存的新配置。
        try:
            (root / STATE_RELATIVE_PATH).unlink(missing_ok=True)
        except OSError as exc:
            print(f"更新已经完成，过渡缓存暂未清理：{exc}", flush=True)
        phase(5, "更新已完成，请自行运行 FAA - 环境安装器.exe")
        return

    phase(0, "正在核对旧版更新记录和原始备份")
    pending = original_update(root)
    clean_compatibility_files(root)
    sys.path.insert(0, str(root))
    from function.common.update_staging import (
        download_github_archive, extract_single_root, isolate_existing_staging,
        run_target_preparation, staging_path, staging_work_path, ensure_child,
    )
    from function.core.update_prepare import check_initial_space
    check_initial_space(root)
    work = staging_work_path(root)
    source, staging = work / "source", staging_path(root)
    isolate_existing_staging(root)
    if work.exists():
        shutil.rmtree(ensure_child(root, work))
    work.mkdir(parents=True)
    downloaded = archive_path is None
    archive = archive_path.resolve() if archive_path is not None else root / "update_cache/legacy_bridge/source.zip"
    phase(1, "兼容旧版：正在重新获取精确目标版本的纯净源码")
    if downloaded:
        download_github_archive(
            pending["target"]["commit"], archive,
            progress_callback=lambda progress: print(json.dumps(progress, ensure_ascii=False), flush=True),
        )
    phase(2, "正在解压纯净源码并读取目标发行规则")
    extract_single_root(archive, source)
    phase(3, "正在使用目标规则从原始备份迁移用户数据")
    result = run_target_preparation(
        root, source, staging, pending["target"], migration_source=Path(pending["backup"]),
    )
    if not result.get("space", {}).get("enough"):
        raise OSError("按目标规则准备后空间不足，当前文件和原始备份保留，可释放空间后重试。")
    script = staging / "plugins/updater/updater.py"
    spec = importlib.util.spec_from_file_location("faa_legacy_target_updater", script)
    updater = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(updater)
    phase(4, "正在备份中间版本并替换为按目标规则生成的完整版本，请勿关闭")
    updater.update(root, staging, None)
    try:
        (root / STATE_RELATIVE_PATH).unlink(missing_ok=True)
        if downloaded:
            archive.unlink(missing_ok=True)
    except OSError as exc:
        print(f"版本替换已完成，过渡缓存暂未清理：{exc}", flush=True)
    phase(5, "更新完成，请自行运行 FAA - 环境安装器.exe，准备新版环境后启动 FAA")


def main() -> None:
    """由原生快速入口隐藏执行；失败原因持续保留在界面和桥接日志中。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--archive", type=Path)
    arguments = parser.parse_args()
    complete_legacy_update(arguments.root, arguments.archive)


if __name__ == "__main__":
    main()
