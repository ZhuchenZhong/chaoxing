# -*- coding: utf-8 -*-
import os
from pathlib import Path


def get_app_home() -> Path:
    override = os.environ.get("CHAOXING_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".chaoxing").resolve()


class GlobalConst:
    AESKey = "u2oh6Vu^HWe4_AES"
    APP_HOME = str(get_app_home())
    COOKIES_PATH = str(get_app_home() / "cookies" / "default.txt")
    LOG_PATH = str(get_app_home() / "logs" / "chaoxing.log")

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Chromium";v="118", "Google Chrome";v="118", "Not=A?Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"'
    }
    VIDEO_HEADERS = {
        "Referer": "https://mooc1.chaoxing.com/ananas/modules/video/index.html?v=2025-0725-1842",
    }
    AUDIO_HEADERS = {
        "Referer": "https://mooc1.chaoxing.com/ananas/modules/audio/index_new.html?v=2025-0725-1842",
    }

    THRESHOLD = 1
