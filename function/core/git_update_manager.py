"""
GitHub-based update workers.

The old in-place git updater has been removed. This module only exposes
threaded workers for the new tag/PR-merge-commit update flow.
"""

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from function.common.update_manifest import (
    GitHubRateLimitError,
    get_cached_dev_commits,
    get_cached_versions,
    refresh_dev_commits,
    refresh_update_manifest,
)
from function.common.update_state import detect_local_state
from function.core.update_prepare import prepare_update_from_github
from function.globals.get_paths import PATHS
from function.globals.log import CUS_LOGGER


def explain_update_error(action: str, exc: Exception) -> str:
    """
    把底层网络/系统异常翻译成用户能理解的更新失败说明。

    Args:
        action: 当前正在执行的更新阶段，例如刷新正式版本列表。
        exc: worker 捕获到的原始异常。

    Returns:
        面向 UI 展示的中文失败说明，末尾保留原始错误便于排查。
    """
    raw_error = str(exc).strip() or exc.__class__.__name__
    lower_error = raw_error.lower()

    if "remote end closed connection without response" in lower_error:
        reason = (
            "连接 GitHub 时，对方或中间网络在返回数据前断开了连接。\n"
            "这通常是临时网络波动、代理/VPN 不稳定、GitHub 访问质量差导致的，不代表版本数据损坏。"
        )
        suggestion = "请稍后重试；如果多次出现，请检查代理/VPN、DNS 或网络防火墙。"
    elif "incompleteread" in lower_error or "more expected" in lower_error:
        reason = (
            "从 GitHub 读取数据时连接中断，只收到了一部分响应内容。\n"
            "这通常是网络传输不稳定、代理/VPN 中途断流，或 GitHub 访问链路质量较差导致的。"
        )
        suggestion = "请直接重试；如果连续出现，请切换网络/代理，或稍后再加载更新列表。"
    elif "timed out" in lower_error or "timeout" in lower_error:
        reason = "连接 GitHub 超时，当前网络没有在限定时间内拿到响应。"
        suggestion = "请稍后重试，或切换网络/代理后再加载更新列表。"
    elif "name resolution" in lower_error or "getaddrinfo" in lower_error:
        reason = "无法解析 GitHub 域名，通常是 DNS 或网络连接异常。"
        suggestion = "请检查网络是否可访问 github.com，或尝试更换 DNS/代理。"
    elif "ssl" in lower_error or "certificate" in lower_error:
        reason = "HTTPS 证书校验失败，可能与系统证书、代理抓包或安全软件有关。"
        suggestion = "请检查系统时间、代理证书和安全软件设置。"
    elif "403" in lower_error or "rate limit" in lower_error:
        reason = "GitHub API 暂时限制了访问频率。"
        suggestion = "请稍后再试；如果频繁检查更新，可以减少刷新次数。"
    else:
        reason = "更新请求失败，可能是网络、GitHub 服务或本地环境临时异常。"
        suggestion = "请稍后重试；如果持续失败，请把原始错误发给开发者排查。"

    return f"{action}失败：\n{reason}\n建议：{suggestion}\n原始错误：{raw_error}"


class ReleaseManifestWorker(QThread):
    """Fetch release tag update candidates without blocking the UI thread."""

    result = pyqtSignal(bool, str, dict)

    def run(self):
        try:
            root = Path(PATHS["root"])
            local_state = detect_local_state(root)
            current_version = local_state.get("version") or None
            current_commit = local_state.get("commit") or None

            cache = refresh_update_manifest(
                root,
                current_version=current_version,
                current_commit=current_commit,
                include_dev=False,
            )
            versions = get_cached_versions(root, current_version)
            current_release = self._find_current_release(cache, current_version, current_commit)

            payload = {
                "local_state": local_state,
                "cache": cache,
                "versions": versions,
                "current_release": current_release,
            }
            known_tags = set(cache.get("known_tags", []))
            if current_version and known_tags and current_version not in known_tags:
                payload["state_warning"] = f"当前版本 {current_version} 未在远端正式版本 tag 列表中找到。"

            if versions:
                self.result.emit(True, f"发现 {len(versions)} 个正式版本更新", payload)
            else:
                self.result.emit(True, "当前没有高于本地版本的正式版更新", payload)
        except GitHubRateLimitError as exc:
            root = Path(PATHS["root"])
            local_state = detect_local_state(root)
            versions = get_cached_versions(root, local_state.get("version") or None)
            self.result.emit(
                bool(versions),
                "GitHub API 触发访问限制，已保留并显示本地缓存结果",
                {"local_state": local_state, "versions": versions, "error": str(exc)},
            )
        except Exception as exc:
            CUS_LOGGER.error(f"刷新正式版本列表失败：{exc}")
            self.result.emit(False, explain_update_error("刷新正式版本列表", exc), {"error": str(exc)})

    @staticmethod
    def _find_current_release(cache: dict, current_version: str | None, current_commit: str | None) -> dict:
        """
        从正式版缓存中找到当前本地版本对应的发布条目。

        Args:
            cache: refresh_update_manifest 返回的 manifest 缓存。
            current_version: 本地 EXTRA.VERSION 或 update_state 版本。
            current_commit: 本地记录的 commit。

        Returns:
            当前正式版条目；无法确认时返回空 dict。
        """
        for entry in cache.get("versions", []):
            if current_version and entry.get("tag") == current_version:
                return entry
            if current_commit and entry.get("commit") == current_commit:
                return entry
        return {}


class ReleasePrepareWorker(QThread):
    """Prepare staging for a selected release target."""

    result = pyqtSignal(bool, str, dict)

    def __init__(self, target: dict, parent=None):
        super().__init__(parent)
        self.target = target

    def run(self):
        try:
            root = Path(PATHS["root"])
            payload = prepare_update_from_github(root, self.target)
            self.result.emit(True, "更新准备完成", payload)
        except Exception as exc:
            CUS_LOGGER.error(f"准备更新失败：{exc}")
            self.result.emit(False, explain_update_error("准备更新", exc), {"error": str(exc)})


class DevManifestWorker(QThread):
    """Fetch recent PR merge commits for developer update mode."""

    result = pyqtSignal(bool, str, dict)

    def __init__(self, max_pages: int = 1, stop_at_cached: bool = True, parent=None):
        super().__init__(parent)
        self.max_pages = max_pages
        self.stop_at_cached = stop_at_cached

    def run(self):
        try:
            root = Path(PATHS["root"])
            local_state = detect_local_state(root)
            current_commit = local_state.get("commit") or None
            stop_at_commits = {current_commit} if current_commit else None

            cache = refresh_dev_commits(
                root,
                per_page=20,
                max_pages=self.max_pages,
                stop_at_commits=stop_at_commits,
                stop_at_cached=self.stop_at_cached,
            )
            dev_commits = get_cached_dev_commits(root)
            payload = {
                "local_state": local_state,
                "cache": cache,
                "dev_commits": dev_commits,
            }
            if dev_commits:
                self.result.emit(True, f"已加载 {len(dev_commits)} 个开发者 PR 合并提交", payload)
            else:
                self.result.emit(True, "没有发现高于当前位置的开发者 PR 合并提交", payload)
        except GitHubRateLimitError as exc:
            root = Path(PATHS["root"])
            local_state = detect_local_state(root)
            dev_commits = get_cached_dev_commits(root)
            self.result.emit(
                bool(dev_commits),
                "GitHub API 触发访问限制，已保留并显示本地缓存结果",
                {"local_state": local_state, "dev_commits": dev_commits, "error": str(exc)},
            )
        except Exception as exc:
            CUS_LOGGER.error(f"刷新开发者提交列表失败：{exc}")
            self.result.emit(False, explain_update_error("刷新开发者提交列表", exc), {"error": str(exc)})


def refresh_release_manifest():
    worker = ReleaseManifestWorker()
    worker.start()
    return worker


def prepare_release_update(target: dict):
    worker = ReleasePrepareWorker(target=target)
    worker.start()
    return worker


def refresh_dev_manifest(max_pages: int = 1, stop_at_cached: bool = True):
    worker = DevManifestWorker(max_pages=max_pages, stop_at_cached=stop_at_cached)
    worker.start()
    return worker
