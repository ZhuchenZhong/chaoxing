from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class EndpointRateLimiter:
    """Simple in-memory sliding-window rate limiter for FastAPI endpoints."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_key(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def __call__(self, request: Request) -> None:
        key = self._get_client_key(request)
        now = time.monotonic()
        window_start = now - self.window_seconds

        # Clean old entries
        self._requests[key] = [t for t in self._requests[key] if t > window_start]

        if len(self._requests[key]) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {self.window_seconds} seconds.",
            )

        self._requests[key].append(now)


# Pre-configured limiters
login_limiter = EndpointRateLimiter(max_requests=5, window_seconds=60)
register_limiter = EndpointRateLimiter(max_requests=3, window_seconds=60)
