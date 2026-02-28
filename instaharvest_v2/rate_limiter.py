"""
Rate Limiter
=============
Thread-safe sliding window rate limiting system.
Separate limits for each endpoint type.
Uses threading.Condition for atomic wait-and-record.
"""

import time
import threading
from collections import defaultdict, deque
from typing import Optional

from .config import RATE_LIMITS


class RateLimiter:
    """
    Thread-safe sliding window rate limiting.
    Separate limits for each endpoint category.

    Uses threading.Condition to atomically wait and record requests,
    preventing race conditions between threads.
    """

    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._windows: dict[str, deque] = defaultdict(deque)
        self._condition = threading.Condition()
        self._paused_until: float = 0

    def check(self, category: str = "get_default") -> None:
        """
        Check rate limit and wait if needed (thread-safe).

        Uses Condition.wait() which atomically releases and reacquires
        the lock, so no other thread can slip in during the wait.

        Args:
            category: RATE_LIMITS key (e.g., 'get_profile', 'post_like')
        """
        if not self._enabled:
            return

        # Global pause (after receiving 429 response)
        now = time.time()
        if now < self._paused_until:
            wait = self._paused_until - now
            time.sleep(wait)

        limits = RATE_LIMITS.get(category, RATE_LIMITS.get("get_default"))
        if not limits:
            return

        max_calls = limits["calls"]
        period = limits["period"]

        with self._condition:
            # Loop until we have capacity — re-check after every wait
            while True:
                now = time.time()
                window = self._windows[category]

                # Clean expired entries
                while window and window[0] < now - period:
                    window.popleft()

                # Capacity available — record and proceed
                if len(window) < max_calls:
                    window.append(time.time())
                    self._condition.notify_all()
                    return

                # Limit reached — wait until the oldest entry expires
                oldest = window[0]
                wait_time = oldest + period - now + 0.1

                if wait_time > 0:
                    # Atomically releases lock, sleeps, re-acquires lock
                    self._condition.wait(timeout=wait_time)
                # Loop back to re-check (another thread may have consumed capacity)

    def pause(self, seconds: float) -> None:
        """Temporarily pause all requests (for 429 responses)."""
        self._paused_until = time.time() + seconds

    def reset(self, category: Optional[str] = None) -> None:
        """Reset rate limit counters."""
        with self._condition:
            if category:
                self._windows.pop(category, None)
            else:
                self._windows.clear()
            self._condition.notify_all()

    def get_remaining(self, category: str = "get_default") -> int:
        """Get remaining requests count."""
        limits = RATE_LIMITS.get(category, RATE_LIMITS.get("get_default"))
        if not limits:
            return 999

        with self._condition:
            window = self._windows[category]
            now = time.time()
            period = limits["period"]

            # Clean expired
            while window and window[0] < now - period:
                window.popleft()

            return max(0, limits["calls"] - len(window))

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
