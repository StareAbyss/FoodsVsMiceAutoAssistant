"""准备房间卡片正式图片、配置及报告的路径。"""

from pathlib import Path

DEFAULT_OUTPUT_DIR = Path("resource") / "image" / "card" / "准备房间"
DEFAULT_REPORT_DIR = Path("resource_other") / "图像资源_卡片准备房间_最新资源"
DEFAULT_CATEGORY_OUTPUT = Path("config") / "card_stage_categories.json"
DEFAULT_BLACKLIST_PATH = Path(__file__).with_name("card_prepare_room_card_blacklist.csv")
