"""由目标版本执行源码转发行和用户数据迁移，只依赖 Python 标准库。"""

import argparse
import json
from pathlib import Path
import shutil
import sys


PLAN_RELATIVE_PATH = Path("update_cache/update_plan.json")


def prepare(root: Path, source: Path, staging: Path, request: dict) -> dict:
    """使用本源码内的规则构建候选版本，旧安装只作为迁移来源。

    同一接口同时用于下载后的预览和 FAA 退出后的最终准备。最终准备必须重新
    生成干净的候选目录，否则 UUID 合并可能把预览中已复制的数据误当成新版内置数据。

    Args:
        root: 当前 FAA 安装根目录。
        source: 保留在 update_cache 内的纯净目标源码目录。
        staging: 候选发行目录，只允许位于 root/update_cache/staging 内。
        request: 目标版本信息和可选迁移项名单。

    Returns:
        候选版本、迁移报告与空间评估，供调用方确认是否继续替换。

    Raises:
        ValueError: 源码、候选目录或迁移来源超出当前安装的允许范围。
        FileNotFoundError: 目标源码目录或独立准备入口缺失。
    """
    root, source, staging = root.resolve(), source.resolve(), staging.resolve()
    allowed = (root / "update_cache/staging").resolve()
    if staging == allowed or allowed not in staging.parents:
        raise ValueError(f"候选版本不在更新暂存目录中：{staging}")
    source_allowed = (root / "update_cache/staging_work").resolve()
    if source_allowed not in source.parents or source == staging:
        raise ValueError(f"目标源码不在更新工作目录中：{source}")
    if not source.is_dir() or not (source / "plugins/updater/prepare.py").is_file():
        raise FileNotFoundError(f"所选版本缺少独立更新准备入口：{source}")

    # -I 子进程中显式加入目标根目录；不能继承正在运行的旧 FAA 已导入的同名模块。
    sys.path.insert(0, str(source))
    from function.common.update_staging import build_distribution_from_source, build_staging_state, describe_staging, validate_staging
    from function.common.update_state import write_update_state
    from function.common.update_space import estimate_update_space
    from function.core.settings_migration import migrate_user_data
    from function.core.update_prepare import summarize_migration_results, write_migration_report

    migration_source = Path(request.get("migration_source") or root).resolve()
    if migration_source != root and (root / "backups").resolve() not in migration_source.parents:
        raise ValueError("用户数据来源只能是当前 FAA 或其备份目录")
    if staging.exists():
        shutil.rmtree(staging)
    build_distribution_from_source(source, staging)
    selected = request.get("selected_migration_names")
    results = migrate_user_data(
        source_root=migration_source, target_root=staging,
        selected_names=set(selected) if selected is not None else None, allow_missing_target=True,
    )
    report_path = write_migration_report(staging, results)
    write_update_state(staging, build_staging_state(request["target"]))
    validate_staging(staging)
    plan = {
        "schema_version": 1,
        "source": str(source.relative_to(root)),
        "request": request,
    }
    plan_path = staging / PLAN_RELATIVE_PATH
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    return {
        "staging": describe_staging(staging),
        "migration_summary": summarize_migration_results(results),
        "migration_report": str(report_path),
        "space": estimate_update_space(root, staging),
    }


def main() -> None:
    """接收显式目录和 JSON 请求，将结果写入 JSON，不导入 FAA 图形界面。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.root, args.source, args.staging, json.loads(args.request.read_text(encoding="utf-8")))
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
