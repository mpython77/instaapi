"""
Async Rate Limiter v2
=====================
Production-grade async rate control with:
- Global semaphore (concurrency limit)
- Mode-based adaptive delays (SAFE/FAST/TURBO)
- Proxy-aware throughput scaling
- Burst detection and throttling
- Token bucket algorithm for smooth rate limiting

Usage:
    limiter = AsyncRateLimiter(mode="fast", proxy_count=5)
    async with limiter.acquire("get_profile"):
        response = await session.get(...)
"""

import asyncio
import time
import random
import logging
from typing import Dict, Optional

from .speed_modes import SpeedMode, get_mode

logger = logging.getLogger("instaapi.rate_limiter")


class AsyncRateLimiter:
    """
    Async rate limiter with global concurrency control.

    Architecture:
        ┌─────────────────────────────┐
        │     Global Semaphore        │  ← max N concurrent requests
        │  ┌───────────────────────┐  │
        │  │   Token Bucket        │  │  ← smooth rate limiting
        │  │  ┌─────────────────┐  │  │
        │  │  │  Adaptive Delay │  │  │  ← human-like timing
        │  │  └─────────────────┘  │  │
        │  └───────────────────────┘  │
        └─────────────────────────────┘
    """

    def __init__(
        self,
        mode: str = "safe",
        proxy_count: int = 0,
        enabled: bool = True,
    ):
        self._mode: SpeedMode = get_mode(mode)
        self._enabled = enabled
        self._proxy_count = proxy_count

        # Calculate effective concurrency
        effective = self._calculate_concurrency(proxy_count)
        self._semaphore = asyncio.Semaphore(effective)
        self._effective_concurrency = effective

        # Token bucket for rate limiting
        self._tokens: float = float(self._mode.burst_size)
        self._max_tokens: float = float(self._mode.burst_size)
        self._refill_rate: float = self._mode.rate_per_minute / 60.0  # tokens/sec
        self._last_refill: float = time.time()
        self._token_lock = asyncio.Lock()

        # Statistics
        self._request_count: int = 0
        self._wait_time_total: float = 0
        self._errors: int = 0
        self._start_time: float = time.time()

        # Escalation (increases delay on repeated errors)
        self._escalation_level: int = 0
        self._last_error_time: float = 0

        # Per-category tracking
        self._category_windows: Dict[str, list] = {}

        logger.info(
            f"[RateLimiter] Mode={self._mode.name} "
            f"Concurrency={effective} "
            f"Rate={self._mode.rate_per_minute}/min "
            f"Proxies={proxy_count}"
        )

    def _calculate_concurrency(self, proxy_count: int) -> int:
        """Calculate effective concurrency based on mode + proxy count."""
        base = self._mode.max_concurrency
        if proxy_count > 0:
            extra = int(proxy_count * self._mode.proxy_multiplier)
            return min(base + extra, 200)  # Hard cap at 200
        return base

    def update_proxy_count(self, count: int) -> None:
        """Dynamically update proxy count and adjust concurrency."""
        self._proxy_count = count
        new_concurrency = self._calculate_concurrency(count)
        if new_concurrency != self._effective_concurrency:
            self._semaphore = asyncio.Semaphore(new_concurrency)
            self._effective_concurrency = new_concurrency
            # Scale rate by proxy count
            self._refill_rate = (
                self._mode.rate_per_minute * max(1, count)
            ) / 60.0
            logger.info(
                f"[RateLimiter] Updated: concurrency={new_concurrency} "
                f"rate={self._refill_rate * 60:.0f}/min"
            )

    # ─── CORE: ACQUIRE ──────────────────────────────────────

    async def acquire(self, category: str = "default") -> None:
        """
        Acquire permission to make a request.

        1. Wait for semaphore (concurrency limit)
        2. Wait for token (rate limit)
        3. Apply adaptive delay (human-like)
        """
        if not self._enabled:
            return

        # Step 1: Global concurrency gate
        await self._semaphore.acquire()

        try:
            # Step 2: Token bucket — smooth rate limiting
            await self._wait_for_token()

            # Step 3: Adaptive delay — human-like timing
            delay = self._calculate_delay()
            if delay > 0:
                await asyncio.sleep(delay)
                self._wait_time_total += delay

        except Exception:
            self._semaphore.release()
            raise

        self._request_count += 1

    def release(self) -> None:
        """Release semaphore after request completes."""
        if self._enabled:
            self._semaphore.release()

    async def _wait_for_token(self) -> None:
        """Token bucket algorithm — wait until a token is available."""
        while True:
            async with self._token_lock:
                now = time.time()
                # Refill tokens
                elapsed = now - self._last_refill
                self._tokens = min(
                    self._max_tokens,
                    self._tokens + elapsed * self._refill_rate,
                )
                self._last_refill = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

                # Calculate wait time while still under lock
                wait_time = (1.0 - self._tokens) / max(self._refill_rate, 0.001)
                wait_time = min(wait_time, 10.0)  # Max 10s wait

            # Sleep outside lock — other coroutines can proceed
            await asyncio.sleep(wait_time)

    def _calculate_delay(self) -> float:
        """Calculate adaptive delay based on mode and escalation."""
        min_d, max_d = self._mode.delay_range

        # Escalation multiplier (increases on errors)
        escalation = 1.0 + (self._escalation_level * 0.3)
        min_d *= escalation
        max_d *= escalation

        # Gaussian distribution for natural timing
        mean = (min_d + max_d) / 2
        std = (max_d - min_d) / 4
        delay = max(min_d, random.gauss(mean, std))
        delay = min(delay, max_d * 1.5)

        # Random long pause (1% chance) — mimics human breaks
        if random.random() < 0.01:
            delay += random.uniform(1.0, 3.0)

        return delay

    # ─── ERROR HANDLING ──────────────────────────────────────

    def on_error(self, error_type: str = "unknown") -> None:
        """Escalate on errors — increase delays."""
        self._errors += 1
        now = time.time()

        if error_type == "rate_limit":
            self._escalation_level = min(5, self._escalation_level + 2)
        elif error_type in ("challenge", "checkpoint"):
            self._escalation_level = min(5, self._escalation_level + 3)
        else:
            self._escalation_level = min(5, self._escalation_level + 1)

        self._last_error_time = now

    def on_success(self) -> None:
        """De-escalate on success — decrease delays."""
        now = time.time()
        # Gradually reduce escalation (every 30 successful seconds)
        if (now - self._last_error_time) > 30:
            self._escalation_level = max(0, self._escalation_level - 1)

    def pause(self, seconds: float) -> None:
        """Temporarily reduce token bucket."""
        self._tokens = 0
        self._last_refill = time.time() + seconds

    # ─── CONTEXT MANAGER ─────────────────────────────────────

    class _RateContext:
        """Async context manager for rate limiting."""
        def __init__(self, limiter: "AsyncRateLimiter", category: str):
            self._limiter = limiter
            self._category = category

        async def __aenter__(self):
            await self._limiter.acquire(self._category)
            return self

        async def __aexit__(self, *args):
            self._limiter.release()

    def gate(self, category: str = "default") -> "_RateContext":
        """
        Context manager for rate-limited requests.

        Usage:
            async with limiter.gate("get_profile"):
                response = await session.get(...)
        """
        return self._RateContext(self, category)

    # ─── BACKWARDS COMPAT ────────────────────────────────────

    async def check(self, category: str = "default") -> None:
        """Legacy method — same as acquire()."""
        await self.acquire(category)

    # ─── STATS ──────────────────────────────────────────────

    @property
    def mode(self) -> SpeedMode:
        return self._mode

    @property
    def stats(self) -> dict:
        elapsed = max(1, time.time() - self._start_time)
        return {
            "mode": self._mode.name,
            "requests": self._request_count,
            "errors": self._errors,
            "req_per_sec": round(self._request_count / elapsed, 2),
            "avg_wait": round(self._wait_time_total / max(1, self._request_count), 3),
            "concurrency": self._effective_concurrency,
            "escalation": self._escalation_level,
            "proxies": self._proxy_count,
        }

    def __repr__(self) -> str:
        s = self.stats
        return (
            f"<RateLimiter mode={s['mode']} "
            f"{s['req_per_sec']} req/s "
            f"concurrent={s['concurrency']} "
            f"escalation={s['escalation']}>"
        )
