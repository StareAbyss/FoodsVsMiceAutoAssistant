import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from function.common.update_manifest import GitHubClient, compare_update_target
from function.common.update_state import detect_local_state
from function.common.update_staging import (
    describe_staging,
    prepare_staging_from_archive,
    prepare_staging_from_github,
)
from function.common.update_space import estimate_update_space
from function.core.settings_migration import migrate_user_data


MIGRATION_REPORT_RELATIVE_PATH = Path("update_cache") / "migration_report.json"


def write_migration_report(staging_root: Path, results: list[dict[str, Any]]) -> Path:
    report_path = staging_root / MIGRATION_REPORT_RELATIVE_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)

    serializable_results = []
    for item in results:
        copied = dict(item)
        for key in ("path_from", "path_to"):
            if copied.get(key) is not None:
                copied[key] = str(copied[key])
        copied["locations"] = [str(location) for location in copied.get("locations", [])]
        serializable_results.append(copied)

    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "results": serializable_results,
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

    staging = prepare_staging_from_archive(root, archive_path, target)
    migration_results = migrate_user_data(
        source_root=root,
        target_root=staging,
        selected_names=selected_migration_names,
        allow_missing_target=True,
    )
    report_path = write_migration_report(staging, migration_results)

    return {
        "staging": describe_staging(staging),
        "migration_summary": summarize_migration_results(migration_results),
        "migration_report": str(report_path),
        "space": estimate_update_space(root, staging),
        "target_validation": validation,
    }


def prepare_update_from_github(
    root: Path,
    target: dict[str, Any],
    selected_migration_names: set[str] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    validation = validate_update_target(root, target)
    if not validation["allowed"] and validation["status"] != "compare_failed":
        raise ValueError(validation["message"])

    staging = prepare_staging_from_github(root, target)
    migration_results = migrate_user_data(
        source_root=root,
        target_root=staging,
        selected_names=selected_migration_names,
        allow_missing_target=True,
    )
    report_path = write_migration_report(staging, migration_results)

    return {
        "staging": describe_staging(staging),
        "migration_summary": summarize_migration_results(migration_results),
        "migration_report": str(report_path),
        "space": estimate_update_space(root, staging),
        "target_validation": validation,
    }
