import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


UPDATE_STATE_RELATIVE_PATH = Path("update_cache") / "update_state.json"


def read_extra_version(project_root: Path) -> str:
    extra_path = project_root / "function" / "globals" / "EXTRA.py"
    if not extra_path.is_file():
        return ""

    version_pattern = re.compile(r'^\s*VERSION\s*=\s*["\']([^"\']+)["\']')
    for line in extra_path.read_text(encoding="utf-8").splitlines():
        match = version_pattern.match(line)
        if match:
            return match.group(1)
    return ""


def run_git(project_root: Path, args: list[str]) -> str:
    """
    Run a Git command when a developer Git environment is available.

    普通用户的热更新不依赖本地 Git。这里的 Git 调用只用于开发者工作区状态展示；
    如果用户没有安装 Git、Git 不在 PATH 中，或当前环境无法启动 Git，则返回空字符串，
    让上层自动回退到 update_state.json / EXTRA.VERSION。
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, OSError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def is_git_worktree_root(project_root: Path) -> bool:
    """Return true only when project_root itself is the Git worktree root."""
    project_root = project_root.resolve()
    top_level = run_git(project_root, ["rev-parse", "--show-toplevel"])
    if not top_level:
        return False

    try:
        return Path(top_level).resolve() == project_root
    except OSError:
        return False


def parse_pr_number(commit_message: str) -> int | None:
    match = re.search(r"Merge pull request #(\d+)", commit_message)
    if not match:
        return None
    return int(match.group(1))


def get_git_state(project_root: Path) -> dict[str, Any]:
    if not is_git_worktree_root(project_root):
        return {
            "commit": "",
            "tag": "",
            "pr": None,
            "summary": "",
            "dirty": False,
        }

    commit = run_git(project_root, ["rev-parse", "HEAD"])
    tag = run_git(project_root, ["describe", "--tags", "--exact-match", "HEAD"])
    message = run_git(project_root, ["log", "-1", "--pretty=%B"])
    dirty = bool(run_git(project_root, ["status", "--porcelain"]))

    return {
        "commit": commit,
        "tag": tag,
        "pr": parse_pr_number(message),
        "summary": next((line for line in message.splitlines() if line.strip()), ""),
        "dirty": dirty,
    }


def build_update_state(project_root: Path, timestamp_key: str = "packaged_at") -> dict[str, Any]:
    project_root = project_root.resolve()
    git_state = get_git_state(project_root)
    version = read_extra_version(project_root)

    return {
        "schema_version": 1,
        "version": version,
        "tag": git_state["tag"],
        "commit": git_state["commit"],
        "pr": git_state["pr"],
        "summary": git_state["summary"],
        "merged_at": "",
        "dirty": git_state["dirty"],
        timestamp_key: datetime.now(timezone.utc).isoformat(),
    }


def write_update_state(dest_root: Path, state: dict[str, Any]) -> Path:
    state_path = dest_root / UPDATE_STATE_RELATIVE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )
    return state_path


def write_current_update_state(project_root: Path) -> Path:
    return write_update_state(project_root, build_update_state(project_root, "installed_at"))


def read_update_state(root: Path) -> dict[str, Any]:
    state_path = root / UPDATE_STATE_RELATIVE_PATH
    if not state_path.is_file():
        return {}
    return json.loads(state_path.read_text(encoding="utf-8"))


def find_state_warnings(project_root: Path) -> list[str]:
    saved_state = read_update_state(project_root)
    version = read_extra_version(project_root)
    git_state = get_git_state(project_root)
    warnings = []

    if saved_state and version and saved_state.get("version") and saved_state["version"] != version:
        warnings.append(
            f"update_state version {saved_state['version']} does not match EXTRA.VERSION {version}."
        )

    if saved_state and git_state.get("commit"):
        if saved_state.get("commit") and saved_state["commit"] != git_state["commit"]:
            warnings.append("update_state commit does not match current Git HEAD.")
        if saved_state.get("tag") and git_state.get("tag") and saved_state["tag"] != git_state["tag"]:
            warnings.append("update_state tag does not match current Git tag.")

    return warnings


def detect_local_state(project_root: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    git_state = get_git_state(project_root)
    saved_state = read_update_state(project_root)
    version = read_extra_version(project_root)

    detected = {
        "version": version,
        "saved": saved_state,
        "git": git_state,
        "source": "extra_version",
        "warnings": find_state_warnings(project_root),
    }

    if git_state.get("commit"):
        detected["source"] = "git"
        detected["commit"] = git_state["commit"]
        detected["tag"] = git_state["tag"]
        detected["pr"] = git_state["pr"] or saved_state.get("pr")
        detected["merged_at"] = saved_state.get("merged_at", "")
        detected["dirty"] = git_state["dirty"]
        return detected

    if saved_state:
        detected["source"] = "update_state"
        detected["commit"] = saved_state.get("commit", "")
        detected["tag"] = saved_state.get("tag", version)
        detected["pr"] = saved_state.get("pr")
        detected["merged_at"] = saved_state.get("merged_at", "")
        detected["dirty"] = saved_state.get("dirty", False)
        return detected

    detected["commit"] = ""
    detected["tag"] = ""
    detected["pr"] = None
    detected["merged_at"] = ""
    detected["dirty"] = False
    return detected


def apply_update_entry_metadata(state: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    if not entry:
        return state

    for key in ("pr", "summary", "title", "url", "merged_at"):
        if not state.get(key) and entry.get(key):
            state[key] = entry[key]
    return state


def find_cached_update_entry(project_root: Path, state: dict[str, Any]) -> dict[str, Any]:
    try:
        from function.common.update_manifest import load_manifest_cache
    except ImportError:
        return {}

    try:
        cache = load_manifest_cache(project_root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}

    tag = state.get("tag")
    commit = state.get("commit")
    for bucket in ("versions", "dev_commits"):
        for entry in cache.get(bucket, []):
            if tag and entry.get("tag") == tag:
                return entry
            if commit and entry.get("commit") == commit:
                return entry
    return {}


def fetch_remote_update_entry(state: dict[str, Any]) -> dict[str, Any]:
    commit = state.get("commit")
    if not commit:
        return {}

    try:
        from function.common.update_manifest import GitHubClient, build_dev_entry, build_version_entry

        client = GitHubClient()
        commit_payload = client.get_commit(commit)
        pulls = client.get_pulls_for_commit(commit)
    except Exception:
        return {}

    tag = state.get("tag")
    if tag:
        return build_version_entry(tag, commit_payload, pulls)
    return build_dev_entry(commit_payload, pulls)


def fill_packaged_merge_metadata(project_root: Path, state: dict[str, Any]) -> dict[str, Any]:
    """
    补齐打包产物的 PR 合并时间。

    打包状态最初来自本地 Git，只能得到 commit/tag/PR 号，不能直接得到 GitHub PR
    的 merged_at。这里先用本地 manifest 缓存，再请求 GitHub；如果网络不可用，则回退
    到本地 merge commit 的提交时间，避免正式包的“时间”长期显示为未记录。
    """
    if state.get("merged_at"):
        return state

    state = apply_update_entry_metadata(state, find_cached_update_entry(project_root, state))
    if state.get("merged_at"):
        return state

    state = apply_update_entry_metadata(state, fetch_remote_update_entry(state))
    if state.get("merged_at"):
        return state

    commit_time = run_git(project_root, ["log", "-1", "--format=%cI"])
    if commit_time:
        state["merged_at"] = commit_time
    return state


def write_packaged_update_state(project_root: Path, dest_root: Path) -> Path:
    state = build_update_state(project_root, "packaged_at")
    state = fill_packaged_merge_metadata(project_root, state)
    return write_update_state(dest_root, state)
