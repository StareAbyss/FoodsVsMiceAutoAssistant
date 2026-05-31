import http.client
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OWNER = "StareAbyss"
DEFAULT_REPO = "FoodsVsMiceAutoAssistant"
DEFAULT_BRANCH = "main"
MANIFEST_CACHE_RELATIVE_PATH = Path("update_cache") / "update_manifest_cache.json"


class GitHubRateLimitError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, owner: str = DEFAULT_OWNER, repo: str = DEFAULT_REPO, token: str | None = None):
        self.owner = owner
        self.repo = repo
        self.token = token or os.environ.get("GITHUB_TOKEN")

    def request_json(self, path: str, params: dict[str, Any] | None = None, retries: int = 2) -> Any:
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}{path}{query}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "FAA-Updater",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        for attempt in range(retries + 1):
            request = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 403:
                    body = exc.read().decode("utf-8", errors="replace")
                    if "rate limit" in body.lower():
                        raise GitHubRateLimitError(body) from exc
                raise
            except (http.client.IncompleteRead, http.client.RemoteDisconnected, urllib.error.URLError, TimeoutError):
                if attempt >= retries:
                    raise
                time.sleep(0.8 * (attempt + 1))

        raise RuntimeError(f"Failed to request GitHub API: {url}")

    def list_tag_refs(self, per_page: int = 30, max_pages: int = 10) -> list[dict[str, Any]]:
        refs = []
        for page in range(1, max_pages + 1):
            tags = self.request_json("/tags", {"per_page": per_page, "page": page})
            if not tags:
                break
            for tag in tags:
                refs.append(
                    {
                        "ref": f"refs/tags/{tag.get('name', '')}",
                        "object": {
                            "type": "commit",
                            "sha": tag.get("commit", {}).get("sha", ""),
                        },
                    }
                )
            if len(tags) < per_page:
                break
        return refs

    def get_commit(self, sha: str) -> dict[str, Any]:
        return self.request_json(f"/commits/{sha}")

    def get_tag_object(self, sha: str) -> dict[str, Any]:
        return self.request_json(f"/git/tags/{sha}")

    def get_pulls_for_commit(self, sha: str) -> list[dict[str, Any]]:
        return self.request_json(f"/commits/{sha}/pulls")

    def list_commits(self, branch: str = DEFAULT_BRANCH, per_page: int = 50, page: int = 1) -> list[dict[str, Any]]:
        return self.request_json(
            "/commits",
            {"sha": branch, "per_page": per_page, "page": page},
        )

    def compare_commits(self, base: str, head: str) -> dict[str, Any]:
        return self.request_json(f"/compare/{base}...{head}")


def manifest_cache_path(root: Path) -> Path:
    return root / MANIFEST_CACHE_RELATIVE_PATH


def load_manifest_cache(root: Path) -> dict[str, Any]:
    path = manifest_cache_path(root)
    if not path.is_file():
        return empty_manifest_cache()
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest_cache(root: Path, cache: dict[str, Any]) -> Path:
    path = manifest_cache_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    cache["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    return path


def empty_manifest_cache() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "repo": f"{DEFAULT_OWNER}/{DEFAULT_REPO}",
        "updated_at": "",
        "known_tags": [],
        "versions": [],
        "dev_commits": [],
        "pulls_by_commit": {},
    }


def semver_key(version: str) -> tuple[int, int, int, str]:
    match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)(.*)$", version)
    if not match:
        return (-1, -1, -1, version)
    major, minor, patch, suffix = match.groups()
    return (int(major), int(minor), int(patch), suffix)


def is_version_tag(tag: str) -> bool:
    return bool(re.match(r"^v\d+\.\d+\.\d+$", tag))


def is_pr_merge_commit(commit_payload: dict[str, Any]) -> bool:
    message = commit_payload.get("commit", {}).get("message", "")
    return len(commit_payload.get("parents", [])) >= 2 and message.startswith("Merge pull request #")


def merge_commit_summary(commit_payload: dict[str, Any]) -> str:
    message = commit_payload.get("commit", {}).get("message", "")
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    if len(lines) >= 2:
        return lines[1]
    return lines[0] if lines else ""


def merge_commit_pr_number(commit_payload: dict[str, Any]) -> int | None:
    message = commit_payload.get("commit", {}).get("message", "")
    match = re.search(r"Merge pull request #(\d+)", message)
    return int(match.group(1)) if match else None


def first_pull(pulls: list[dict[str, Any]]) -> dict[str, Any]:
    return pulls[0] if pulls else {}


def get_pulls_cached(cache: dict[str, Any], client: GitHubClient, commit_sha: str) -> list[dict[str, Any]]:
    pulls_by_commit = cache.setdefault("pulls_by_commit", {})
    if commit_sha not in pulls_by_commit:
        try:
            pulls_by_commit[commit_sha] = client.get_pulls_for_commit(commit_sha)
        except GitHubRateLimitError:
            raise
        except Exception:
            pulls_by_commit[commit_sha] = []
    return pulls_by_commit[commit_sha]


def build_version_entry(tag: str, commit_payload: dict[str, Any], pulls: list[dict[str, Any]]) -> dict[str, Any]:
    pr = first_pull(pulls)
    return {
        "tag": tag,
        "commit": commit_payload.get("sha", ""),
        "pr": pr.get("number") or merge_commit_pr_number(commit_payload),
        "title": pr.get("title") or merge_commit_summary(commit_payload),
        "summary": merge_commit_summary(commit_payload),
        "author": commit_payload.get("commit", {}).get("author", {}).get("name", ""),
        "merged_at": pr.get("merged_at") or commit_payload.get("commit", {}).get("author", {}).get("date", ""),
        "url": pr.get("html_url") or commit_payload.get("html_url", ""),
    }


def build_dev_entry(commit_payload: dict[str, Any], pulls: list[dict[str, Any]]) -> dict[str, Any]:
    pr = first_pull(pulls)
    return {
        "commit": commit_payload.get("sha", ""),
        "pr": pr.get("number") or merge_commit_pr_number(commit_payload),
        "title": pr.get("title") or merge_commit_summary(commit_payload),
        "summary": merge_commit_summary(commit_payload),
        "author": commit_payload.get("commit", {}).get("author", {}).get("name", ""),
        "merged_at": pr.get("merged_at") or commit_payload.get("commit", {}).get("author", {}).get("date", ""),
        "url": pr.get("html_url") or commit_payload.get("html_url", ""),
    }


def resolve_ref_commit_sha(client: GitHubClient, ref: dict[str, Any]) -> str:
    obj = ref.get("object", {})
    if obj.get("type") == "commit":
        return obj.get("sha", "")
    if obj.get("type") == "tag":
        tag_obj = client.get_tag_object(obj.get("sha", ""))
        return tag_obj.get("object", {}).get("sha", "")
    return ""


def merge_entries_by_key(existing: list[dict[str, Any]], incoming: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    merged = {entry.get(key): entry for entry in existing if entry.get(key)}
    for entry in incoming:
        if entry.get(key):
            merged[entry[key]] = entry
    return list(merged.values())


def merge_manifest_cache(
    cache: dict[str, Any],
    versions: list[dict[str, Any]] | None = None,
    dev_commits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cache = cache or empty_manifest_cache()
    if versions:
        cache["versions"] = sorted(
            merge_entries_by_key(cache.get("versions", []), versions, "tag"),
            key=lambda entry: semver_key(entry.get("tag", "")),
            reverse=True,
        )
    if dev_commits:
        cache["dev_commits"] = sorted(
            merge_entries_by_key(cache.get("dev_commits", []), dev_commits, "commit"),
            key=lambda entry: entry.get("merged_at", ""),
            reverse=True,
        )
    return cache


def get_cached_versions(root: Path, current_version: str | None = None) -> list[dict[str, Any]]:
    versions = load_manifest_cache(root).get("versions", [])
    if not current_version:
        return versions
    return [
        entry
        for entry in versions
        if entry.get("tag") and semver_key(entry["tag"]) > semver_key(current_version)
    ]


def get_cached_dev_commits(root: Path) -> list[dict[str, Any]]:
    return load_manifest_cache(root).get("dev_commits", [])


def refresh_tag_versions(
    root: Path,
    client: GitHubClient | None = None,
    current_version: str | None = None,
) -> dict[str, Any]:
    client = client or GitHubClient()
    cache = load_manifest_cache(root)
    cached_tags = {entry.get("tag") for entry in cache.get("versions", [])}
    known_tags = set(cache.get("known_tags", []))
    versions = []

    for ref in client.list_tag_refs():
        tag = ref.get("ref", "").removeprefix("refs/tags/")
        if not is_version_tag(tag):
            continue
        known_tags.add(tag)
        if tag in cached_tags:
            continue
        if current_version and semver_key(tag) <= semver_key(current_version):
            continue

        commit_sha = resolve_ref_commit_sha(client, ref)
        if not commit_sha:
            continue

        commit_payload = client.get_commit(commit_sha)
        if not is_pr_merge_commit(commit_payload):
            continue

        pulls = get_pulls_cached(cache, client, commit_sha)
        versions.append(build_version_entry(tag, commit_payload, pulls))

    cache = merge_manifest_cache(cache, versions=versions)
    cache["known_tags"] = sorted(known_tags, key=semver_key, reverse=True)
    save_manifest_cache(root, cache)
    return cache


def refresh_dev_commits(
    root: Path,
    client: GitHubClient | None = None,
    branch: str = DEFAULT_BRANCH,
    per_page: int = 20,
    max_pages: int = 1,
    stop_at_commits: set[str] | None = None,
    stop_at_cached: bool = True,
) -> dict[str, Any]:
    client = client or GitHubClient()
    cache = load_manifest_cache(root)
    cached_commits = {entry.get("commit") for entry in cache.get("dev_commits", [])}
    stop_at_commits = set(stop_at_commits or set())
    dev_entries = []

    for page in range(1, max_pages + 1):
        commits = client.list_commits(branch=branch, per_page=per_page, page=page)
        if not commits:
            break

        should_stop = False
        for commit_payload in commits:
            sha = commit_payload.get("sha", "")
            if sha in stop_at_commits or (stop_at_cached and sha in cached_commits):
                should_stop = True
                break
            if not is_pr_merge_commit(commit_payload):
                continue
            pulls = get_pulls_cached(cache, client, sha)
            dev_entries.append(build_dev_entry(commit_payload, pulls))

        if should_stop:
            break

    cache = merge_manifest_cache(cache, dev_commits=dev_entries)
    save_manifest_cache(root, cache)
    return cache


def refresh_update_manifest(
    root: Path,
    client: GitHubClient | None = None,
    current_version: str | None = None,
    current_commit: str | None = None,
    include_dev: bool = False,
    dev_pages: int = 1,
) -> dict[str, Any]:
    client = client or GitHubClient()
    cache = refresh_tag_versions(root, client=client, current_version=current_version)
    if include_dev:
        stop_at_commits = {current_commit} if current_commit else None
        cache = refresh_dev_commits(
            root,
            client=client,
            max_pages=dev_pages,
            stop_at_commits=stop_at_commits,
        )
    return cache


def compare_update_target(client: GitHubClient, current_commit: str, target_commit: str) -> dict[str, Any]:
    if not current_commit:
        return {"allowed": True, "status": "unknown", "message": "Current commit is unknown."}
    if not target_commit:
        return {"allowed": False, "status": "missing_target", "message": "Target commit is missing."}
    if current_commit == target_commit:
        return {"allowed": False, "status": "identical", "message": "Target commit is the current commit."}

    comparison = client.compare_commits(current_commit, target_commit)
    status = comparison.get("status", "")
    allowed = status == "ahead"
    message = {
        "ahead": "Target commit is ahead of current commit.",
        "identical": "Target commit is the current commit.",
        "behind": "Target commit is behind current commit.",
        "diverged": "Target commit has diverged from current commit.",
    }.get(status, f"Unexpected compare status: {status}")

    return {
        "allowed": allowed,
        "status": status,
        "ahead_by": comparison.get("ahead_by"),
        "behind_by": comparison.get("behind_by"),
        "message": message,
    }
