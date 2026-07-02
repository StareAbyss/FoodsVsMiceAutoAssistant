from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import mysql.connector
import pandas as pd


DEFAULT_TABLE_NAME = "card_image_url"
DEFAULT_OUTPUT_PATTERN = "点我获取更多图像资源 {date}.xlsx"
ENV_PREFIX = "FAA_IMAGE_RESOURCE_DB_"
LOCAL_CONFIG_FILE = "image_resource_db.local.json"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从图像资源数据库导出最新 Excel。")
    parser.add_argument("--host", default=os.getenv(f"{ENV_PREFIX}HOST"), help="数据库主机，默认读取 FAA_IMAGE_RESOURCE_DB_HOST")
    parser.add_argument("--port", default=os.getenv(f"{ENV_PREFIX}PORT"), help="数据库端口，默认读取 FAA_IMAGE_RESOURCE_DB_PORT")
    parser.add_argument("--user", default=os.getenv(f"{ENV_PREFIX}USER"), help="数据库用户，默认读取 FAA_IMAGE_RESOURCE_DB_USER")
    parser.add_argument("--password", default=os.getenv(f"{ENV_PREFIX}PASSWORD"), help="数据库密码，默认读取 FAA_IMAGE_RESOURCE_DB_PASSWORD")
    parser.add_argument("--database", default=os.getenv(f"{ENV_PREFIX}DATABASE"), help="数据库名，默认读取 FAA_IMAGE_RESOURCE_DB_DATABASE")
    parser.add_argument("--table", default=DEFAULT_TABLE_NAME, help="导出的表名")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd(), help="Excel 输出目录")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.cwd() / LOCAL_CONFIG_FILE,
        help=f"本地数据库配置文件，默认读取项目根目录 {LOCAL_CONFIG_FILE}",
    )
    return parser


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


def require_db_config(args: argparse.Namespace) -> dict[str, object]:
    local_config = load_local_db_config(args.config)
    config = {
        "host": args.host or local_config.get("host"),
        "port": args.port or local_config.get("port") or 3306,
        "user": args.user or local_config.get("user"),
        "password": args.password or local_config.get("password"),
        "database": args.database or local_config.get("database"),
    }
    missing = [key for key, value in config.items() if value in (None, "")]
    if missing:
        env_names = ", ".join(f"{ENV_PREFIX}{key.upper()}" for key in missing)
        raise ValueError(f"缺少数据库连接配置，请设置环境变量或本地配置文件 {args.config}: {env_names}")
    config["port"] = int(config["port"])
    return config


def export_image_resource_excel(db_config: dict[str, object], table_name: str, output_dir: Path) -> Path:
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
    args = build_arg_parser().parse_args()
    try:
        db_config = require_db_config(args)
        export_image_resource_excel(db_config, args.table, args.output_dir)
    except Exception as exc:
        print(f"导出图像资源 Excel 失败: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
