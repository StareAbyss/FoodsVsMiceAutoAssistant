import http.client
import json
import re
import shutil
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from function.common.update_manifest import DEFAULT_OWNER, DEFAULT_REPO
from function.common.update_state import write_update_state
from function.common.distribution_layout import (
    PACKAGE_FOLDERS, PACKAGE_FILES, ROOT_ENTRY_DIRECTORY, ROOT_ENTRY_FILES,
    UV_ARCHIVE, ENVIRONMENT_INSTALLER_EXE, LAUNCHER_EXE,
    validate_source_entries, validate_distribution,
)


STAGING_RELATIVE_PATH = Path("update_cache") / "staging" / "FAA.update.new"
FAILED_STAGING_RELATIVE_PATH = Path("update_cache") / "failed_staging"
STAGING_WORK_RELATIVE_PATH = Path("update_cache") / "staging_work"
ARCHIVE_WORK_RELATIVE_PATH = Path("update_cache") / "staging_archives"

PRESERVE_FAILED_STAGING_COUNT = 2

IMAGE_RESOURCE_EXCEL_PATTERN = "点我获取更多图像资源 *.xlsx"
IMAGE_RESOURCE_EXCEL_DATE_RE = re.compile(r"点我获取更多图像资源 (?P<date>\d{4}-\d{2}-\d{2})\.xlsx$")



class StagingError(RuntimeError):
    pass


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def staging_path(root: Path) -> Path:
    return root / STAGING_RELATIVE_PATH


def failed_staging_path(root: Path) -> Path:
    return root / FAILED_STAGING_RELATIVE_PATH


def staging_work_path(root: Path) -> Path:
    return root / STAGING_WORK_RELATIVE_PATH


def archive_work_path(root: Path) -> Path:
    return root / ARCHIVE_WORK_RELATIVE_PATH


def ensure_child(parent: Path, child: Path) -> Path:
    parent = parent.resolve()
    child = child.resolve()
    if child == parent or parent not in child.parents:
        raise StagingError(f"Path is outside allowed directory: {child}")
    return child


def isolate_existing_staging(root: Path) -> Path | None:
    staging = staging_path(root)
    if not staging.exists():
        return None

    failed_root = failed_staging_path(root)
    failed_root.mkdir(parents=True, exist_ok=True)
    target = failed_root / f"FAA.failed-staging.{utc_stamp()}"
    counter = 1
    while target.exists():
        counter += 1
        target = failed_root / f"FAA.failed-staging.{utc_stamp()}.{counter}"

    shutil.move(str(ensure_child(root, staging)), str(ensure_child(root, target)))
    prune_failed_staging(root)
    return target


def prune_failed_staging(root: Path, keep: int = PRESERVE_FAILED_STAGING_COUNT) -> None:
    failed_root = failed_staging_path(root)
    if not failed_root.is_dir():
        return

    entries = sorted(
        [entry for entry in failed_root.iterdir() if entry.is_dir()],
        key=lambda entry: entry.stat().st_mtime,
        reverse=True,
    )
    for entry in entries[keep:]:
        shutil.rmtree(ensure_child(failed_root, entry))


def download_github_archive(
    ref: str,
    dest_zip: Path,
    owner: str = DEFAULT_OWNER,
    repo: str = DEFAULT_REPO,
    retries: int = 2,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> Path:
    url = f"https://github.com/{owner}/{repo}/archive/{ref}.zip"
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "FAA-Updater"}

    def emit_progress(downloaded_bytes: int, total_bytes: int | None, started_at: float) -> None:
        if progress_callback is None:
            return

        elapsed_seconds = max(time.monotonic() - started_at, 0.001)
        speed_bytes_per_second = downloaded_bytes / elapsed_seconds
        remaining_seconds = None
        percent = None
        if total_bytes and total_bytes > 0:
            percent = min(downloaded_bytes / total_bytes * 100, 100.0)
            if speed_bytes_per_second > 0:
                remaining_seconds = max((total_bytes - downloaded_bytes) / speed_bytes_per_second, 0.0)

        progress_callback({
            "phase": "download",
            "downloaded_bytes": downloaded_bytes,
            "total_bytes": total_bytes,
            "percent": percent,
            "speed_bytes_per_second": speed_bytes_per_second,
            "remaining_seconds": remaining_seconds,
        })

    for attempt in range(retries + 1):
        request = urllib.request.Request(url, headers=headers)
        started_at = time.monotonic()
        if progress_callback is not None:
            progress_callback({
                "phase": "download_connecting",
                "message": "正在连接 GitHub 源码包下载地址，尚未收到文件大小",
            })
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                total_header = response.headers.get("Content-Length")
                total_bytes = int(total_header) if total_header and total_header.isdigit() else None
                downloaded_bytes = 0
                last_emit_at = 0.0
                emit_progress(downloaded_bytes, total_bytes, started_at)
                with dest_zip.open("wb") as file:
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        file.write(chunk)
                        downloaded_bytes += len(chunk)
                        now = time.monotonic()
                        if now - last_emit_at >= 0.5:
                            emit_progress(downloaded_bytes, total_bytes, started_at)
                            last_emit_at = now
                emit_progress(downloaded_bytes, total_bytes, started_at)
            return dest_zip
        except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError):
            if dest_zip.exists():
                dest_zip.unlink()
            if attempt >= retries:
                raise
            if progress_callback is not None:
                progress_callback({
                    "phase": "download_connecting",
                    "message": f"GitHub 源码包下载连接失败，正在第 {attempt + 1} 次重试",
                })
            time.sleep(1.0 * (attempt + 1))

    raise StagingError(f"Failed to download GitHub archive: {url}")


def validate_zip_members(zip_file: zipfile.ZipFile) -> None:
    for member in zip_file.infolist():
        member_path = Path(member.filename)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise StagingError(f"Unsafe path in archive: {member.filename}")


def extract_single_root(zip_path: Path, extract_parent: Path) -> Path:
    """
    解压 GitHub 源码包，同时剥离仓库名和 commit 组成的公共顶层目录。

    GitHub archive 的顶层目录通常包含 40 位 commit。若直接交给 extractall，深层安装目录会叠加这段无业务价值的路径，容易触发 Windows MAX_PATH。

    Args:
        zip_path: 已下载的源码 ZIP 路径。
        extract_parent: 去除公共顶层目录后的源码输出目录。

    Returns:
        可直接用于构建 staging 的源码根目录。

    Raises:
        StagingError: ZIP 不安全或没有且仅有一个公共顶层目录。
    """
    extract_parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zip_file:
        validate_zip_members(zip_file)
        members = [member for member in zip_file.infolist() if Path(member.filename).parts]
        root_names = {Path(member.filename).parts[0] for member in members}
        if len(root_names) != 1:
            raise StagingError(f"Expected one archive root directory, got {len(root_names)}")

        for member in members:
            relative_parts = Path(member.filename).parts[1:]
            if not relative_parts:
                continue

            destination = ensure_child(extract_parent, extract_parent.joinpath(*relative_parts))
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            with zip_file.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)

    return extract_parent


def copy_file(source_root: Path, dest_root: Path, relative_path: str | Path, required: bool = True, destination: str | Path | None = None) -> None:
    relative_path = Path(relative_path)
    source = source_root / relative_path
    dest = dest_root / (Path(destination) if destination is not None else relative_path)
    if not source.is_file():
        if required:
            raise StagingError(f"Missing required file: {relative_path}")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)


def image_resource_excel_sort_key(path: Path) -> tuple[int, float, str]:
    """
    生成图像资源 Excel 的新旧排序键，无合法日期时回退到修改时间。

    Args:
        path: 待排序的 Excel 文件路径。

    Returns:
        由资源日期序号、修改时间和文件名组成的排序键。
    """
    match = IMAGE_RESOURCE_EXCEL_DATE_RE.fullmatch(path.name)
    if match:
        try:
            file_date = datetime.strptime(match.group("date"), "%Y-%m-%d").date()
            return file_date.toordinal(), path.stat().st_mtime, path.name
        except ValueError:
            pass
    return -1, path.stat().st_mtime, path.name


def copy_latest_image_resource_excel(source_root: Path, dest_root: Path) -> Path | None:
    excel_files = [path for path in source_root.glob(IMAGE_RESOURCE_EXCEL_PATTERN) if path.is_file()]
    if not excel_files:
        return None

    latest_file = max(excel_files, key=image_resource_excel_sort_key)
    destination = dest_root / latest_file.name
    shutil.copy2(latest_file, destination)
    return destination


def copy_folder(
    source_root: Path,
    dest_root: Path,
    folder: str | Path,
    dest_subdir: Path,
    exclude_files: set[str],
    exclude_paths: set[Path],
    exclude_suffixes: set[str],
    required: bool = True,
) -> None:
    folder = Path(folder)
    source_folder = source_root / folder
    if not source_folder.is_dir():
        if required:
            raise StagingError(f"Missing required folder: {folder}")
        return

    for source in source_folder.rglob("*"):
        if not source.is_file():
            continue

        relative_to_source = source.relative_to(source_root)
        relative_inside_folder = source.relative_to(source_folder)
        if source.name in exclude_files:
            continue
        if relative_to_source in exclude_paths:
            continue
        if source.suffix in exclude_suffixes:
            continue

        dest = dest_root / dest_subdir / relative_inside_folder
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)


def build_distribution_from_source(source_root: Path, dest_root: Path) -> Path:
    if dest_root.exists():
        raise StagingError(f"Staging destination already exists: {dest_root}")

    try:
        validate_source_entries(source_root)
    except FileNotFoundError as exc:
        raise StagingError("所选版本的发行文件不完整，已停止准备更新；请改选完整版本或联系维护者。" + str(exc)) from exc
    dest_root.mkdir(parents=True, exist_ok=False)

    for name in ROOT_ENTRY_FILES:
        copy_file(source_root, dest_root, ROOT_ENTRY_DIRECTORY / name, destination=name)

    for folder, dest_subdir, exclude_files, exclude_paths, exclude_suffixes in PACKAGE_FOLDERS:
        copy_folder(
            source_root=source_root,
            dest_root=dest_root,
            folder=folder,
            dest_subdir=dest_subdir,
            exclude_files=set(exclude_files),
            exclude_paths=set(exclude_paths),
            exclude_suffixes=set(exclude_suffixes),
            required=True,
        )

    for file_path in PACKAGE_FILES:
        copy_file(source_root, dest_root, file_path)
    copy_latest_image_resource_excel(source_root, dest_root)

    return dest_root


def build_staging_state(target: dict[str, Any]) -> dict[str, Any]:
    commit = target.get("commit", "")
    tag = target.get("tag", "")
    version = tag or target.get("version") or (f"dev-{commit[:12]}" if commit else "")
    return {
        "schema_version": 1,
        "channel": "release" if tag else "developer",
        "version": version,
        "tag": tag,
        "commit": commit,
        "pr": target.get("pr"),
        "summary": target.get("summary") or target.get("title", ""),
        "title": target.get("title", ""),
        "url": target.get("url", ""),
        "merged_at": target.get("merged_at", ""),
        "dirty": False,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }


def validate_staging(staging_root: Path) -> None:
    try:
        validate_distribution(staging_root)
    except ValueError as exc:
        raise StagingError(str(exc)) from exc
    if (staging_root / ".git").exists():
        raise StagingError("Prepared staging must not contain .git")


def prepare_staging_from_archive(root: Path, archive_path: Path, target: dict[str, Any]) -> Path:
    root = root.resolve()
    staging = staging_path(root)
    work_root = staging_work_path(root)
    extract_parent = work_root / "source"

    ensure_child(root, staging)
    ensure_child(root, work_root)
    isolate_existing_staging(root)

    if work_root.exists():
        shutil.rmtree(ensure_child(root, work_root))
    work_root.mkdir(parents=True, exist_ok=True)

    try:
        source_root = extract_single_root(archive_path, extract_parent)
        build_distribution_from_source(source_root, staging)
        write_update_state(staging, build_staging_state(target))
        validate_staging(staging)
    except Exception:
        if staging.exists():
            failed = failed_staging_path(root) / f"FAA.failed-staging.{utc_stamp()}"
            failed.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(ensure_child(root, staging)), str(ensure_child(root, failed)))
            prune_failed_staging(root)
        raise
    finally:
        if work_root.exists():
            shutil.rmtree(ensure_child(root, work_root))

    return staging


def prepare_staging_from_github(
    root: Path,
    target: dict[str, Any],
    owner: str = DEFAULT_OWNER,
    repo: str = DEFAULT_REPO,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> Path:
    ref = target.get("tag") or target.get("commit")
    if not ref:
        raise StagingError("Target must contain tag or commit.")

    root = root.resolve()
    archive_root = archive_work_path(root)
    archive_path = archive_root / f"archive.{ref[:32]}.{utc_stamp()}.zip"

    if archive_root.exists():
        shutil.rmtree(ensure_child(root, archive_root))
    archive_root.mkdir(parents=True, exist_ok=True)

    try:
        download_github_archive(ref, archive_path, owner=owner, repo=repo, progress_callback=progress_callback)
        return prepare_staging_from_archive(root, archive_path, target)
    finally:
        if archive_root.exists():
            shutil.rmtree(ensure_child(root, archive_root))


def describe_staging(staging_root: Path) -> dict[str, Any]:
    state_path = staging_root / "update_cache" / "update_state.json"
    state = {}
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    return {
        "path": str(staging_root),
        "state": state,
        "has_git": (staging_root / ".git").exists(),
        "has_exe_launcher": (staging_root / LAUNCHER_EXE).is_file(),
        "has_environment_installer": (staging_root / ENVIRONMENT_INSTALLER_EXE).is_file(),
        "has_uv_archive": (staging_root / UV_ARCHIVE).is_file(),
        "has_updater": (staging_root / "plugins/updater/updater.py").is_file(),
    }
