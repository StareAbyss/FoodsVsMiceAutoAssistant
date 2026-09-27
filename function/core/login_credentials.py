import copy
import json
from pathlib import Path

from function.core.my_crypto import decrypt_data, encrypt_data
from function.globals.log import CUS_LOGGER


LOGIN_CREDENTIALS_TEMPLATE = {
    "qq": {
        "1p": {"username": "", "password": ""},
        "2p": {"username": "", "password": ""},
    },
    "4399": {
        "1p": {"username": "", "password": ""},
        "2p": {"username": "", "password": ""},
    },
    "level_2": {
        "1p": {"password": ""},
        "2p": {"password": ""},
    },
}


def _merge_with_template(data: dict) -> dict:
    """补齐凭据文件结构，并丢弃不属于当前协议的字段。"""
    result = copy.deepcopy(LOGIN_CREDENTIALS_TEMPLATE)
    if not isinstance(data, dict):
        return result

    for section, players in result.items():
        source_section = data.get(section)
        if not isinstance(source_section, dict):
            continue
        for player, fields in players.items():
            source_player = source_section.get(player)
            if not isinstance(source_player, dict):
                continue
            for field in fields:
                value = source_player.get(field)
                if isinstance(value, str):
                    result[section][player][field] = value
    return result


def _read_legacy_account(settings: dict, config_key: str, file_name: str) -> dict:
    """读取旧版外置账号文件；没有有效目录时返回空配置。"""
    save_dir = settings.get(config_key, {}).get("path", "")
    if not isinstance(save_dir, str) or not save_dir.strip():
        return {}

    file_path = Path(save_dir) / file_name
    if not file_path.is_file():
        return {}

    try:
        with file_path.open(mode="r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        CUS_LOGGER.warning(f"[登录凭据迁移] 无法读取旧账号文件 '{file_path}': {error}")
        return {}


def _decrypt_password(password: str, source: str) -> str:
    """解密非空密码；旧文件损坏时保留其他可用字段。"""
    if not password:
        return ""
    try:
        return decrypt_data(password)
    except Exception as error:
        CUS_LOGGER.warning(f"[登录凭据读取] 无法解密 {source} 的密码: {error}")
        return ""


def load_login_credentials(file_path: Path, legacy_settings: dict | None = None) -> dict:
    """
    读取并解密登录凭据；首次使用时自动吸收旧版配置。

    Args:
        file_path: ``config/login_credentials.json`` 的路径。
        legacy_settings: 已读取的 ``settings.json``，用于首次迁移旧字段。

    Returns:
        密码已解密、可直接随 ``opt`` 传递的登录凭据。
    """
    file_path = Path(file_path)
    created_from_legacy = not file_path.is_file()

    if created_from_legacy:
        settings = legacy_settings or {}
        credentials = copy.deepcopy(LOGIN_CREDENTIALS_TEMPLATE)

        for player in ("1p", "2p"):
            level_2_password = settings.get("level_2", {}).get(player, {}).get("password", "")
            if isinstance(level_2_password, str):
                credentials["level_2"][player]["password"] = level_2_password

        for section, config_key, file_name in (
                ("qq", "qq_login_info", "QQ_account.json"),
                ("4399", "4399_login_info", "4399_account.json"),
        ):
            legacy_account = _read_legacy_account(settings, config_key, file_name)
            for player in ("1p", "2p"):
                player_data = legacy_account.get(player, {})
                username = player_data.get("username", "")
                password = player_data.get("password", "")
                if isinstance(username, str):
                    credentials[section][player]["username"] = username
                if isinstance(password, str):
                    credentials[section][player]["password"] = _decrypt_password(
                        password,
                        f"旧版 {section} {player}",
                    )

        save_login_credentials(file_path, credentials)
        return credentials

    try:
        with file_path.open(mode="r", encoding="utf-8") as file:
            encrypted_credentials = _merge_with_template(json.load(file))
    except (OSError, json.JSONDecodeError) as error:
        CUS_LOGGER.error(f"[登录凭据读取] 文件不可用，已使用空配置: {error}")
        encrypted_credentials = copy.deepcopy(LOGIN_CREDENTIALS_TEMPLATE)

    credentials = copy.deepcopy(encrypted_credentials)
    for section, players in credentials.items():
        for player, fields in players.items():
            fields["password"] = _decrypt_password(
                fields["password"],
                f"{section} {player}",
            )
    return credentials


def save_login_credentials(file_path: Path, credentials: dict) -> None:
    """把内存中的明文凭据统一加密写入 config 专用文件。"""
    encrypted_credentials = _merge_with_template(credentials)
    for players in encrypted_credentials.values():
        for fields in players.values():
            password = fields["password"]
            fields["password"] = encrypt_data(password) if password else ""

    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open(mode="w", encoding="utf-8") as file:
        json.dump(encrypted_credentials, file, ensure_ascii=False, indent=4)
