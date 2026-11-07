"""开发工具的项目根目录和数据快照目录。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_DIR = PROJECT_ROOT / "resource" / "db"
