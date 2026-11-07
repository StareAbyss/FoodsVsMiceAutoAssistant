"""名单排序、正式模板校验和精确文件清理的底层操作。"""

import csv
import os
import tempfile
from pathlib import Path
from PIL import Image
from function.common.loot_policy import read_drop_list
from ..common.files import atomic_copy
from .paths import DEFAULT_LOOT_BLACKLIST_CSV

def scan_images(root: Path) -> dict[tuple[str, str], Path]:
    """按类型和名称收集图片，拒绝越界链接和非一级分类，约束后续删除范围。"""
    files = {}
    for path in root.rglob("*.png"):
        relative = path.relative_to(root)
        if len(relative.parts) != 2 or path.resolve().parent.parent != root.resolve():
            raise ValueError(f"战利品目录必须是类型/名称.png，且不能指向外部：{path}")
        files[(relative.parts[0], path.stem)] = path
    return files


def valid_loot_image(path: Path) -> bool:
    """允许 44×44 四通道 PNG，包括可无损解码为 RGBA 的透明索引图。"""
    try:
        with Image.open(str(path)) as image:
            image.load()
            has_alpha = image.mode == "RGBA" or (image.mode == "P" and "transparency" in image.info)
            return image.size == (44, 44) and has_alpha and image.convert("RGBA").getchannel("A").getextrema()[1] == 255
    except (OSError, ValueError):
        return False

def sort_loot_list(path: Path) -> bool:
    """按类型、名称稳定排序人工名单，保留重复行与附加列；有变动时原子替换并返回 True。"""
    read_drop_list(path)
    with path.open(newline="", encoding="utf-8-sig") as file:
        header, *rows = csv.reader(file)
    category_index, name_index = header.index("类型"), header.index("名称")
    ordered = sorted(rows, key=lambda row: tuple(
        row[index].strip() if index < len(row) else "" for index in (category_index, name_index)))
    if ordered == rows:
        return False
    with tempfile.NamedTemporaryFile(mode="w", newline="", encoding="utf-8-sig",
                                     dir=path.parent, suffix=".tmp", delete=False) as file:
        temporary = Path(file.name)
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(ordered)
    try:
        os.replace(str(temporary), str(path))
    finally:
        temporary.unlink(missing_ok=True)
    return True


def read_loot_blacklist(path: Path = DEFAULT_LOOT_BLACKLIST_CSV) -> set[tuple[str, str]]:
    """
    读取不会在战利品中掉落的物品名单。

    Args:
        path: 包含“类型,名称”两列的战利品黑名单 CSV。

    Returns:
        由 `(类型, 名称)` 组成的集合。文件不存在或字段缺失时返回空集合。
    """
    if not path.is_file():
        return set()

    blacklist = set()
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        for row in reader:
            item_type = (row.get("类型") or "").strip()
            name = (row.get("名称") or "").strip()
            if item_type and name:
                blacklist.add((item_type, name))
    return blacklist


def sync_whitelist_images(fresh, white, conflicts, formal_root: Path) -> tuple[tuple[int, int, int], list[str]]:
    """
    将完整白名单候选同步到正式库；无效图片保留旧模板，冲突项目不写入。

    Args:
        fresh: 已成功获取的 `(类型, 名称)` 到候选文件的映射。
        white: 人工白名单集合。
        conflicts: 黑白名单交集，本轮暂停处理。
        formal_root: 经过主流程校验的正式战利品目录。

    Returns:
        新增、更新、未变化三个数量，以及格式错误说明列表。
    """
    added = updated = unchanged = 0
    errors = []
    for key, source in sorted(fresh.items()):
        if key not in white or key in conflicts:
            continue
        if not valid_loot_image(source):
            errors.append(f"{key[0]}/{key[1]}：图片不能解码为有效 44×44 RGBA，保留旧正式模板")
            continue
        target = formal_root / key[0] / (key[1] + ".png")
        exists = target.exists()
        changed = atomic_copy(source, target)
        added += int(changed and not exists)
        updated += int(changed and exists)
        unchanged += int(not changed)
    return (added, updated, unchanged), errors


def cleanup_images(formal, cached, white, unknown, conflicts) -> tuple[int, int]:
    """
    对已验证的图片映射逐文件清理，只保留正式白名单图与未分类候选。

    Args:
        formal: 经 scan_images 验证的正式图片映射。
        cached: 经 scan_images 验证的候选图片映射；退回未分类的正式图已在清理前保全。
        white: 人工白名单集合。
        unknown: 本轮未分类集合。
        conflicts: 本轮暂停处理的名单交集。

    Returns:
        清理的正式图片与候选图片数量；不递归删除目录或操作失败日志。
    """
    removed_formal = removed_candidates = 0
    for key, path in formal.items():
        if key not in white and key not in conflicts:
            path.unlink()
            removed_formal += 1
    for key, path in cached.items():
        if key not in unknown and key not in conflicts:
            path.unlink()
            removed_candidates += 1
    return removed_formal, removed_candidates
