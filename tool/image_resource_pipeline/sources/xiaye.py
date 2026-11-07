"""只负责从根目录私有凭据导出数据库，不调用快照编排。"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import mysql.connector
import pandas as pd

from ..common.paths import DB_DIR, PROJECT_ROOT

DEFAULT_TABLE_NAME = "card_image_url"
DEFAULT_OUTPUT_PATTERN = "点我获取更多图像资源 {date}.xlsx"
ENV_PREFIX = "FAA_IMAGE_RESOURCE_DB_"
LOCAL_CONFIG_FILE = "image_resource_db.local.json"
LOCAL_CONFIG_PATH = PROJECT_ROOT / LOCAL_CONFIG_FILE

def load_local_db_config(config_path: Path) -> dict[str, object]:
    if not config_path.is_file():
        return {}

    with open(config_path, encoding="utf-8") as file:
        raw_config = json.load(file)

    return {
        "host": raw_config.get("host") or raw_config.get(f"{ENV_PREFIX}HOST"),
        "port": raw_config.get("port") or raw_config.get(f"{ENV_PREFIX}PORT"),
        "user": raw_config.get("user") or raw_config.get(f"{ENV_PREFIX}USER"),
        "password": raw_config.get("password") or raw_config.get(f"{ENV_PREFIX}PASSWORD"),
        "database": raw_config.get("database") or raw_config.get(f"{ENV_PREFIX}DATABASE"),
    }


def require_db_config() -> dict[str, object]:
    """只从项目根目录的本地 JSON 获取连接信息，不回显配置值。"""
    local_config = load_local_db_config(LOCAL_CONFIG_PATH)
    config = {
        "host": local_config.get("host"),
        "port": local_config.get("port") or 3306,
        "user": local_config.get("user"),
        "password": local_config.get("password"),
        "database": local_config.get("database"),
    }
    missing = [key for key, value in config.items() if value in (None, "")]
    if missing:
        raise ValueError(f"请在项目根目录 {LOCAL_CONFIG_FILE} 中补齐字段：{', '.join(missing)}")
    config["port"] = int(config["port"])
    return config


def export_image_resource_excel(db_config: dict[str, object], table_name: str, output_dir: Path) -> Path:
    if not output_dir.resolve().is_relative_to(DB_DIR.resolve()):
        raise ValueError("Excel 只能输出到 resource/db 或其暂存子目录")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / DEFAULT_OUTPUT_PATTERN.format(date=datetime.now().strftime("%Y-%m-%d"))

    print("正在连接图像资源数据库...")
    connection = mysql.connector.connect(**db_config)
    try:
        query = f"SELECT * FROM `{table_name}`"
        df = pd.read_sql(query, connection)
        df.to_excel(output_file, index=False)
    finally:
        connection.close()
        print("数据库连接已关闭")

    print(f"图像资源 Excel 已导出到 {output_file}")
    return output_file


def main() -> int:
    """内部导出子进程入口，只允许写入 db 内的暂存目录。"""
    parser = argparse.ArgumentParser(description="资源数据库导出工作进程")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        export_image_resource_excel(require_db_config(), DEFAULT_TABLE_NAME, args.output_dir)
    except Exception as exc:
        print(f"导出图像资源 Excel 失败（{type(exc).__name__}），请检查根目录本地配置和数据库连接。")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
