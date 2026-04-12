from __future__ import annotations

from typing import Any


class ChaoxingError(Exception):
    def __init__(
        self,
        message: str,
        *,
        detail: dict[str, Any] | None = None,
        status_code: int = 502,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}
        self.status_code = status_code


class ChaoxingLoginError(ChaoxingError):
    pass


class ChaoxingAuthError(ChaoxingError):
    pass


class ChaoxingCookieExpiredError(ChaoxingAuthError):
    pass


class ChaoxingRequestError(ChaoxingError):
    pass


class ChaoxingParseError(ChaoxingError):
    pass
