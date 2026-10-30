import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from function.common.update_manifest import GitHubClient, compare_update_target
from function.common.update_state import detect_local_state
from function.common.update_staging import (
    prepare_staging_from_archive,
    prepare_staging_from_github,
    staging_work_path,
)
from function.common.update_space import estimate_update_space, format_bytes


MIGRATION_REPORT_RELATIVE_PATH = Path("update_cache") / "migration_report.json"


def to_json_serializable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: to_json_serializable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_json_serializable(item) for item in value]
    if isinstance(value, tuple):
        return [to_json_serializable(item) for item in value]
    return value


def write_migration_report(staging_root: Path, results: list[dict[str, Any]]) -> Path:
    report_path = staging_root / MIGRATION_REPORT_RELATIVE_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "results": to_json_serializable(results),
        "summary": summarize_migration_results(results),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    return report_path


def summarize_migration_results(results: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"migrated": 0, "skipped": 0, "unavailable": 0}
    for item in results:
        status = item.get("status", "unavailable")
        summary[status] = summary.get(status, 0) + 1
    return summary


def validate_update_target(root: Path, target: dict[str, Any], client: GitHubClient | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    current_commit = detect_local_state(root).get("commit", "")
    target_commit = target.get("commit", "")
    client = client or GitHubClient()

    try:
        return compare_update_target(client, current_commit, target_commit)
    except Exception as exc:
        return {
            "allowed": True,
            "status": "compare_failed",
            "message": f"Could not compare current and target commits: {exc}",
        }


def prepare_update_from_archive(
    root: Path,
    archive_path: Path,
    target: dict[str, Any],
    selected_migration_names: set[str] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    validation = validate_update_target(root, target)
    if not validation["allowed"] and validation["status"] != "compare_failed":
        raise ValueError(validation["message"])

    precheck = check_initial_space(root)
    prepare_staging_from_archive(root, archive_path, target, selected_migration_names)
    result = json.loads((staging_work_path(root) / "prepare_result.json").read_text(encoding="utf-8"))
    return {**result, "target_validation": validation, "initial_space": precheck}


def prepare_update_from_github(
    root: Path,
    target: dict[str, Any],
    selected_migration_names: set[str] | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    if progress_callback is not None:
        progress_callback({
            "phase": "prepare",
            "message": "正在校验目标版本，尚未开始下载",
        })
    precheck = check_initial_space(root)
    validation = validate_update_target(root, target)
    if not validation["allowed"] and validation["status"] != "compare_failed":
        raise ValueError(validation["message"])

    if progress_callback is not None:
        progress_callback({
            "phase": "prepare",
            "message": "目标版本校验完成，正在请求源码包",
        })
    prepare_staging_from_github(
        root, target, progress_callback=progress_callback, selected_migration_names=selected_migration_names,
    )
    result = json.loads((staging_work_path(root) / "prepare_result.json").read_text(encoding="utf-8"))
    return {**result, "target_validation": validation, "initial_space": precheck}


def check_initial_space(root: Path) -> dict[str, Any]:
    """下载前按当前版本体积粗估两份临时内容，精确结果仍以目标版本准备后为准。"""
    result = estimate_update_space(root)
    result["required"] = result["backup_size"] * 2 + result["safety_margin"]
    result["required_text"] = format_bytes(result["required"])
    result["enough"] = result["available"] >= result["required"]
    if not result["enough"]:
        raise OSError("下载前空间预估不足，已停止更新；请先释放磁盘空间。")
    return result
