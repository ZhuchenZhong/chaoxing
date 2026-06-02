# -*- coding: utf-8 -*-
from __future__ import annotations

import configparser
import os
import shutil
from pathlib import Path
from typing import Any

APP_HOME_ENV = "CHAOXING_HOME"
APP_DIR_NAME = ".chaoxing"
DEFAULT_PROFILE = "default"


def app_home() -> Path:
    override = os.environ.get(APP_HOME_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / APP_DIR_NAME).resolve()


def ensure_app_home() -> Path:
    home = app_home()
    for child in (home, home / "cookies", home / "logs"):
        child.mkdir(parents=True, exist_ok=True)
    return home


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def config_template_path() -> Path:
    return project_root() / "config_template.ini"


def default_config_path() -> Path:
    return ensure_app_home() / "config.ini"


def default_cookie_path(profile: str = DEFAULT_PROFILE) -> Path:
    safe_profile = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in profile) or DEFAULT_PROFILE
    return ensure_app_home() / "cookies" / f"{safe_profile}.txt"


def default_log_path() -> Path:
    return ensure_app_home() / "logs" / "chaoxing.log"


def ensure_config_file(config_path: str | os.PathLike[str] | None = None) -> Path:
    path = Path(config_path).expanduser().resolve() if config_path else default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path

    template = config_template_path()
    if template.exists():
        shutil.copyfile(template, path)
    else:
        parser = configparser.ConfigParser()
        for section in ("common", "tiku", "notification"):
            parser.add_section(section)
        with path.open("w", encoding="utf8") as handle:
            parser.write(handle)
    return path


def str_to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _split_csv(value: Any) -> list[str] | None:
    if value is None:
        return None
    items = [item.strip() for item in str(value).split(",") if item.strip()]
    return items or None


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(item).strip() for item in value if str(item).strip())
    return str(value)


def read_config(config_path: str | os.PathLike[str] | None = None) -> configparser.ConfigParser:
    path = ensure_config_file(config_path)
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf8")
    for section in ("common", "tiku", "notification"):
        if not parser.has_section(section):
            parser.add_section(section)
    return parser


def normalize_common_config(common_config: dict[str, Any]) -> dict[str, Any]:
    common = dict(common_config)
    common["use_cookies"] = str_to_bool(common.get("use_cookies", False))
    common["remember_password"] = str_to_bool(common.get("remember_password", False))
    common["course_list"] = _split_csv(common.get("course_list"))
    try:
        common["speed"] = float(common.get("speed", 1.0))
    except (TypeError, ValueError):
        common["speed"] = 1.0
    common["speed"] = min(2.0, max(1.0, common["speed"]))
    try:
        common["jobs"] = int(common.get("jobs", 4))
    except (TypeError, ValueError):
        common["jobs"] = 4
    if common.get("notopen_action") not in {"retry", "ask", "continue"}:
        common["notopen_action"] = "retry"
    for key in ("username", "password"):
        if key in common and common[key] is not None:
            common[key] = str(common[key]).strip()
    return common


def normalize_tiku_config(tiku_config: dict[str, Any]) -> dict[str, Any]:
    tiku = dict(tiku_config)
    for key in ("delay", "cover_rate"):
        if key in tiku and tiku[key] not in (None, ""):
            try:
                tiku[key] = float(tiku[key])
            except (TypeError, ValueError):
                pass
    return tiku


def load_config_from_file(
    config_path: str | os.PathLike[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    parser = read_config(config_path)
    common_config = dict(parser.items("common")) if parser.has_section("common") else {}
    tiku_config = dict(parser.items("tiku")) if parser.has_section("tiku") else {}
    notification_config = dict(parser.items("notification")) if parser.has_section("notification") else {}
    return (
        normalize_common_config(common_config),
        normalize_tiku_config(tiku_config),
        notification_config,
    )


def save_config_to_file(
    config_path: str | os.PathLike[str] | None,
    common_config: dict[str, Any],
    tiku_config: dict[str, Any],
    notification_config: dict[str, Any],
) -> Path:
    path = ensure_config_file(config_path)
    parser = read_config(path)

    common = dict(common_config)
    remember_password = str_to_bool(common.get("remember_password", False))
    common["remember_password"] = remember_password
    if not remember_password:
        common["password"] = ""

    for section, values in (
        ("common", common),
        ("tiku", tiku_config),
        ("notification", notification_config),
    ):
        if not parser.has_section(section):
            parser.add_section(section)
        for key, value in values.items():
            parser.set(section, key, _stringify(value))

    with path.open("w", encoding="utf8") as handle:
        parser.write(handle)
    return path
