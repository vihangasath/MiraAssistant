"""Per-model requests-per-minute limiter.

The Gemini free tier allows ~15 RPM for flash-lite and 5 RPM for 2.5-flash. Without
this, concurrent eval cases (or a busy demo) get 429s and fail for reasons that have
nothing to do with Mira. Limits are configurable: MIRA_RPM="model=limit,model=limit".
"""
from __future__ import annotations

import asyncio
import os
import threading
import time
from collections import deque

_DEFAULTS = {"gemini-3.1-flash-lite": 14, "gemini-3.5-flash": 9, "gemini-2.5-flash": 4, "gemini-3-flash-preview": 9}
_WINDOW = 60.0


def _limits() -> dict[str, int]:
    limits = dict(_DEFAULTS)
    for part in filter(None, os.getenv("MIRA_RPM", "").split(",")):
        name, _, value = part.partition("=")
        if value.strip().isdigit():
            limits[name.strip()] = int(value)
    return limits


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: dict[str, deque[float]] = {}
        self._limits = _limits()

    def _reserve(self, model: str) -> float:
        """Reserve a slot; return how long the caller must wait before using it."""
        limit = self._limits.get(model, 8)
        with self._lock:
            q = self._calls.setdefault(model, deque())
            now = time.monotonic()
            while q and now - q[0] > _WINDOW:
                q.popleft()
            if len(q) < limit:
                q.append(now)
                return 0.0
            start = q[-limit] + _WINDOW + 0.25   # when the oldest call in the window expires
            q.append(max(start, now))
            return max(0.0, start - now)

    async def acquire(self, model: str) -> None:
        wait = self._reserve(model)
        if wait:
            await asyncio.sleep(wait)

    def acquire_sync(self, model: str) -> None:
        wait = self._reserve(model)
        if wait:
            time.sleep(wait)


limiter = RateLimiter()


def retry_delay_seconds(error: Exception, default: float = 10.0) -> float:
    """Read Gemini's suggested retryDelay ('4s') from a 429 error, if present."""
    import re
    m = re.search(r"retryDelay'?:\s*'(\d+(?:\.\d+)?)s'", str(error))
    return float(m.group(1)) + 0.5 if m else default


# Models whose *daily* free-tier quota is used up. Waiting is pointless (Google suggests ~24 h),
# so callers skip straight to the fallback model until the process restarts.
exhausted_today: set[str] = set()


def is_daily_quota(error: Exception) -> bool:
    return "PerDay" in str(error)


def capped_delay(error: Exception, cap: float = 20.0) -> float:
    return min(retry_delay_seconds(error), cap)
