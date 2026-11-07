"""战利品候选、正式模板、人工名单和辅助报告的路径。"""

from pathlib import Path
from function.common.loot_policy import BLACKLIST_FILENAME, WHITELIST_FILENAME, UNKNOWN_FILENAME

DEFAULT_OUTPUT_ROOT = Path("resource_other") / "图像资源_战利品_最新资源"
DEFAULT_LOOT_ROOT = Path("resource") / "image" / "item" / "战利品"
DEFAULT_LOOT_BLACKLIST_CSV = Path("resource") / "image" / "item" / BLACKLIST_FILENAME
DEFAULT_LOOT_WHITELIST_CSV = Path("resource") / "image" / "item" / WHITELIST_FILENAME
DEFAULT_LOOT_UNKNOWN_CSV = Path("resource") / "image" / "item" / UNKNOWN_FILENAME
DEFAULT_COMPARE_SAME_CSV = DEFAULT_OUTPUT_ROOT / "现有与最新图像资源相同部分一览.csv"
DEFAULT_COMPARE_MISSING_CSV = DEFAULT_OUTPUT_ROOT / "现有与最新图像资源缺失图片一览.csv"
DEFAULT_COMPARE_EXTRA_CSV = DEFAULT_OUTPUT_ROOT / "现有与最新图像资源多出图片一览.csv"
DEFAULT_CLASSIFY_CSV = DEFAULT_OUTPUT_ROOT / "战利品分类迁移计划.csv"
DEFAULT_FAILED_ROOT = Path("logs") / "match_failed" / "loots"
DEFAULT_REPORT_ROOT = Path("resource_other") / "战利品识别失败分析"
DEFAULT_LOOT_MASK = Path("resource") / "image" / "item" / "物品-掩模-不绑定.png"
