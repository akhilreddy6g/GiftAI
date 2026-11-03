"""Per-caller request budgets, so one account can't exhaust shared free-tier quotas."""

import math
import time
from collections.abc import Callable
from typing import Protocol


class RateLimiter(Protocol):
    def acquire(self, key: str) -> int | None:
        """Count one request for ``key``.

        Returns None if it is allowed, or the number of seconds to wait if it is not.
        """
        ...


class FixedWindowRateLimiter:
    """Allows ``limit`` requests per key in each ``window_seconds`` window.

    Counts live in process memory, which is exact for the single backend instance the
    free plan runs. With several instances this would move to a shared store behind the
    same ``RateLimiter`` interface.
    """

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._clock = clock
        self._window_index = -1
        self._counts: dict[str, int] = {}

    def acquire(self, key: str) -> int | None:
        now = self._clock()
        window_index = int(now // self._window_seconds)
        if window_index != self._window_index:
            # A new window: forget every old count at once, which also bounds memory.
            self._window_index = window_index
            self._counts.clear()

        count = self._counts.get(key, 0)
        if count >= self._limit:
            window_ends_at = (window_index + 1) * self._window_seconds
            return max(1, math.ceil(window_ends_at - now))
        self._counts[key] = count + 1
        return None
