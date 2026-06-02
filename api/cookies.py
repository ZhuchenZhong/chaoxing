# -*- coding: utf-8 -*-
from pathlib import Path

import requests

from api.config import GlobalConst as gc


def save_cookies(session: requests.Session):
    buffer=""
    cookie_path = Path(gc.COOKIES_PATH)
    cookie_path.parent.mkdir(parents=True, exist_ok=True)
    with cookie_path.open("w", encoding="utf8") as f:
        for k, v in session.cookies.items():
            buffer += f"{k}={v};"
        buffer = buffer.removesuffix(";")
        f.write(buffer)


def use_cookies() -> dict:
    cookie_path = Path(gc.COOKIES_PATH)
    if not cookie_path.exists():
        return {}

    cookies={}
    with cookie_path.open("r", encoding="utf8") as f:
        buffer = f.read().strip()
        for item in buffer.split(";"):
            if "=" not in item:
                continue
            k, v = item.strip().split("=", 1)
            cookies[k] = v

    return cookies
