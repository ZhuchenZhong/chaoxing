"""Async captcha handler for Chaoxing platform.

Ported from legacy ``bak/legacy-cli/api/captcha.py`` (sync/requests)
to async httpx.  OCR is optional — if ``ddddocr`` is not installed the
module still imports cleanly; callers can check ``OCR_AVAILABLE``.
"""

from __future__ import annotations

from random import randint
from typing import Any

import httpx

try:
    from ddddocr import DdddOcr

    OCR_AVAILABLE = True
except ImportError:  # pragma: no cover
    DdddOcr = None  # type: ignore[assignment,misc]
    OCR_AVAILABLE = False

CAPTCHA_HOST = "https://mooc1.chaoxing.com"
CAPTCHA_GET_PATH = "/processVerifyPng.ac"
CAPTCHA_SUBMIT_PATH = "/html/processVerify.ac"


def ocr_init() -> Any:
    """Initialise a DdddOcr instance (requires ``ddddocr`` package)."""
    if not OCR_AVAILABLE:
        raise RuntimeError("ddddocr is not installed; captcha OCR is unavailable")
    return DdddOcr(show_ad=False)


class CxCaptcha:
    """Async captcha solver for Chaoxing verification challenges."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        ocr: Any | None = None,
    ) -> None:
        self.client = client
        self.ocr = ocr if ocr is not None else (ocr_init() if OCR_AVAILABLE else None)

    async def get_captcha(self) -> bytes | None:
        """Download captcha image from the platform."""
        url = CAPTCHA_HOST + CAPTCHA_GET_PATH
        random_t = randint(0, 2147483647)
        response = await self.client.get(
            url,
            params={"t": random_t},
            headers={"Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"},
        )
        if response.status_code == 200 and "image/png" in response.headers.get("content-type", ""):
            return response.content
        return None

    async def submit_captcha(self, cap_token: str) -> bool:
        """Submit the recognised captcha token for verification."""
        url = CAPTCHA_HOST + CAPTCHA_SUBMIT_PATH
        response = await self.client.get(
            url,
            params={"ucode": cap_token, "app": 0},
            follow_redirects=False,
        )
        return response.status_code in (301, 302)

    def recognise(self, img: bytes) -> str:
        """Run OCR on the captcha image bytes."""
        if self.ocr is None:
            raise RuntimeError("OCR engine not available; install ddddocr")
        return self.ocr.classification(img)

    async def try_pass(self) -> bool:
        """Full captcha flow: download → recognise → submit."""
        cap_img = await self.get_captcha()
        if not cap_img:
            return False
        cap_token = self.recognise(cap_img)
        return await self.submit_captcha(cap_token)
