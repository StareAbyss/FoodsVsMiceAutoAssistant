import http.client
import json
import shutil
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from function.common.update_manifest import DEFAULT_OWNER, DEFAULT_REPO
from function.common.update_state import write_update_state


STAGING_RELATIVE_PATH = Path("update_cache") / "staging" / "FAA.update.new"
FAILED_STAGING_RELATIVE_PATH = Path("update_cache") / "failed_staging"
STAGING_WORK_RELATIVE_PATH = Path("update_cache") / "staging_work"
ARCHIVE_WORK_RELATIVE_PATH = Path("update_cache") / "staging_archives"

PRESERVE_FAILED_STAGING_COUNT = 2

CONFIG_EXCLUDE_FILES = {
    "settings.json",
    "空间服登录界面_1P.png",
    "空间服登录界面_2P.png",
    "跨服远征_1p.png",
}
CONFIG_EXCLUDE_PATHS = {
    Path("config/cus_images/背包_装备_需使用的/任意通用包裹.png"),
    Path("config/cus_images/背包_装备_需使用的/星际酬劳.png"),
    Path("config/cus_images/背包_装备_需使用的/浮空酬劳.png"),
    Path("config/cus_images/背包_装备_需使用的/火山酬劳.png"),
    Path("config/cus_images/背包_装备_需使用的/美味酬劳.png"),
}

PACKAGE_FOLDERS = (
    ("config", Path("config"), CONFIG_EXCLUDE_FILES, CONFIG_EXCLUDE_PATHS, set()),
    ("plugins/uv", Path("."), set(), set(), set()),
    ("function", Path("function"), set(), set(), {".pyc"}),
    ("plugins/pak", Path("plugins/pak"), set(), set(), set()),
    ("plugins/updater", Path("plugins/updater"), set(), set(), set()),
    ("battle_plan", Path("battle_plan"), set(), set(), set()),
    ("battle_plan_not_active", Path("battle_plan_not_active"), set(), set(), set()),
    ("md_img", Path("md_img"), set(), set(), set()),
    ("task_sequence", Path("task_sequence"), set(), set(), set()),
    ("tweak_plan", Path("tweak_plan"), set(), set(), set()),
    ("resource", Path("resource"), set(), set(), {".pyc"}),
)

PACKAGE_FILES = (
    "新手入门 看我!!! 看我!!! 看我!!!.txt",
    "FAA支持性检测, 仅限Win10+.bat",
    "LICENSE",
    "README.md",
    "README - 高级放卡.md",
    "致谢名单.md",
    "致谢名单.png",
    "恢复到备份.bat",
    "config/item_ranking_dag_graph.json",
    ".python-version",
    "pyproject.toml",
    "uv.lock",
)

IMAGE_RESOURCE_EXCEL_PATTERN = "点我获取更多图像资源 *.xlsx"

REQUIRED_STAGING_PATHS = (
    "LICENSE",
    "pyproject.toml",
    "uv.lock",
    "AppInstallRun.bat",
    "function",
    "resource",
)


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
) -> Path:
    url = f"https://github.com/{owner}/{repo}/archive/{ref}.zip"
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "FAA-Updater"}

    for attempt in range(retries + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                with dest_zip.open("wb") as file:
                    shutil.copyfileobj(response, file)
            return dest_zip
        except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError):
            if attempt >= retries:
                raise
            time.sleep(1.0 * (attempt + 1))

    raise StagingError(f"Failed to download GitHub archive: {url}")


def validate_zip_members(zip_file: zipfile.ZipFile) -> None:
    for member in zip_file.infolist():
        member_path = Path(member.filename)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise StagingError(f"Unsafe path in archive: {member.filename}")


def extract_single_root(zip_path: Path, extract_parent: Path) -> Path:
    extract_parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zip_file:
        validate_zip_members(zip_file)
        zip_file.extractall(extract_parent)

    roots = [entry for entry in extract_parent.iterdir() if entry.is_dir()]
    if len(roots) != 1:
        raise StagingError(f"Expected one archive root directory, got {len(roots)}")
    return roots[0]


def copy_file(source_root: Path, dest_root: Path, relative_path: str | Path, required: bool = True) -> None:
    relative_path = Path(relative_path)
    source = source_root / relative_path
    dest = dest_root / relative_path
    if not source.is_file():
        if required:
            raise StagingError(f"Missing required file: {relative_path}")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)


def copy_latest_image_resource_excel(source_root: Path, dest_root: Path) -> Path | None:
    excel_files = [path for path in source_root.glob(IMAGE_RESOURCE_EXCEL_PATTERN) if path.is_file()]
    if not excel_files:
        return None

    latest_file = max(excel_files, key=lambda path: path.stat().st_mtime)
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

    dest_root.mkdir(parents=True, exist_ok=False)

    for folder, dest_subdir, exclude_files, exclude_paths, exclude_suffixes in PACKAGE_FOLDERS:
        copy_folder(
            source_root=source_root,
            dest_root=dest_root,
            folder=folder,
            dest_subdir=dest_subdir,
            exclude_files=set(exclude_files),
            exclude_paths=set(exclude_paths),
            exclude_suffixes=set(exclude_suffixes),
            required=folder not in {"plugins/updater"},
        )

    for file_path in PACKAGE_FILES:
        copy_file(source_root, dest_root, file_path, required=file_path not in {"恢复到备份.bat"})
    copy_latest_image_resource_excel(source_root, dest_root)

    return dest_root


def copy_update_tools_from_current_root(current_root: Path, staging_root: Path) -> None:
    current_updater = current_root / "plugins" / "updater"
    staging_updater = staging_root / "plugins" / "updater"
    if current_updater.is_dir() and not (staging_updater / "updater.py").is_file():
        shutil.copytree(current_updater, staging_updater, dirs_exist_ok=True)

    restore_script = Path("恢复到备份.bat")
    current_restore_script = current_root / restore_script
    staging_restore_script = staging_root / restore_script
    if current_restore_script.is_file() and not staging_restore_script.is_file():
        shutil.copy2(current_restore_script, staging_restore_script)


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
        "branch": target.get("branch", "main"),
        "pr": target.get("pr"),
        "summary": target.get("summary") or target.get("title", ""),
        "title": target.get("title", ""),
        "url": target.get("url", ""),
        "merged_at": target.get("merged_at", ""),
        "dirty": False,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }


def validate_staging(staging_root: Path) -> None:
    missing = [relative for relative in REQUIRED_STAGING_PATHS if not (staging_root / relative).exists()]
    if missing:
        raise StagingError(f"Prepared staging is incomplete; missing: {', '.join(missing)}")
    if (staging_root / ".git").exists():
        raise StagingError("Prepared staging must not contain .git")


def prepare_staging_from_archive(root: Path, archive_path: Path, target: dict[str, Any]) -> Path:
    root = root.resolve()
    staging = staging_path(root)
    work_root = staging_work_path(root)
    extract_parent = work_root / f"extract.{utc_stamp()}"

    ensure_child(root, staging)
    ensure_child(root, work_root)
    isolate_existing_staging(root)

    if work_root.exists():
        shutil.rmtree(ensure_child(root, work_root))
    work_root.mkdir(parents=True, exist_ok=True)

    try:
        source_root = extract_single_root(archive_path, extract_parent)
        build_distribution_from_source(source_root, staging)
        copy_update_tools_from_current_root(root, staging)
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
        download_github_archive(ref, archive_path, owner=owner, repo=repo)
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
        "has_launcher": (staging_root / "AppInstallRun.bat").is_file(),
    }
