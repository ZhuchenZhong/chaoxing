from __future__ import annotations

import asyncio
import random
import time


class AsyncRateLimiter:
    """Async-safe rate limiter matching legacy RateLimiter behavior."""

    def __init__(self, call_interval: float = 0.5) -> None:
        self._last_call = 0.0
        self._lock = asyncio.Lock()
        self.call_interval = call_interval

    async def limit_rate(
        self,
        random_time: bool = False,
        random_min: float = 0.0,
        random_max: float = 1.0,
    ) -> None:
        async with self._lock:
            if random_time:
                await asyncio.sleep(random.uniform(random_min, random_max))

            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.call_interval:
                await asyncio.sleep(self.call_interval - elapsed)

            self._last_call = time.monotonic()
