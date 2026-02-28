"""
Tests for unlimited anonymous scraping mode.
Verifies that all throttling is bypassed when unlimited=True.
"""

import time
import pytest

from instaapi.config import (
    ANON_RATE_LIMITS_UNLIMITED,
    ANON_REQUEST_DELAYS_UNLIMITED,
)
from instaapi.anon_client import AnonRateLimiter, AnonClient
from instaapi.speed_modes import get_mode, UNLIMITED


# ─── AnonRateLimiter ─────────────────────────────────────────

class TestAnonRateLimiterDisabled:
    """AnonRateLimiter with enabled=False should never block."""

    def test_check_always_true(self):
        limiter = AnonRateLimiter(enabled=False)
        # Even 1000 consecutive checks should pass instantly
        for _ in range(1000):
            assert limiter.check("html_parse") is True

    def test_wait_if_needed_returns_immediately(self):
        limiter = AnonRateLimiter(enabled=False)
        start = time.time()
        for _ in range(100):
            limiter.wait_if_needed("graphql")
        elapsed = time.time() - start
        # 100 calls should take <0.1s (no waiting)
        assert elapsed < 0.1, f"wait_if_needed should be instant, took {elapsed:.3f}s"

    def test_enabled_limiter_blocks(self):
        """Sanity check: enabled limiter should eventually block."""
        limiter = AnonRateLimiter(enabled=True)
        results = [limiter.check("html_parse") for _ in range(20)]
        # Default limit is 10/60s — after 10, should get False
        assert False in results, "Enabled limiter should block after limit"


# ─── AnonClient unlimited ────────────────────────────────────

class TestAnonClientUnlimited:
    """AnonClient(unlimited=True) should have no internal delays."""

    def test_human_delay_skipped(self):
        client = AnonClient(unlimited=True)
        start = time.time()
        for _ in range(50):
            client._human_delay()
        elapsed = time.time() - start
        # 50 calls with delay=0 should be nearly instant
        assert elapsed < 0.05, f"_human_delay should be skipped, took {elapsed:.3f}s"

    def test_human_delay_normal_mode_has_delay(self):
        """Normal mode should have measurable delay."""
        client = AnonClient(unlimited=False)
        start = time.time()
        client._human_delay()
        elapsed = time.time() - start
        # Normal min delay is 1.5s
        assert elapsed >= 0.5, f"Normal mode should have delay, took {elapsed:.3f}s"

    def test_unlimited_flag_stored(self):
        client = AnonClient(unlimited=True)
        assert client._unlimited is True

    def test_rate_limiter_disabled(self):
        client = AnonClient(unlimited=True)
        assert client._rate_limiter._enabled is False

    def test_delays_config_is_zero(self):
        client = AnonClient(unlimited=True)
        assert client._delays["min"] == 0.0
        assert client._delays["max"] == 0.0
        assert client._delays["after_error"]["min"] == 0.0
        assert client._delays["after_rate_limit"]["max"] == 0.0


# ─── UNLIMITED Speed Mode ────────────────────────────────────

class TestUnlimitedSpeedMode:
    """UNLIMITED speed mode should have max throughput settings."""

    def test_mode_exists(self):
        mode = get_mode("unlimited")
        assert mode.name == "unlimited"

    def test_concurrency(self):
        assert UNLIMITED.max_concurrency == 1000

    def test_zero_delay(self):
        assert UNLIMITED.delay_range == (0.0, 0.0)

    def test_high_rate(self):
        assert UNLIMITED.rate_per_minute == 999999

    def test_burst_size(self):
        assert UNLIMITED.burst_size == 1000

    def test_no_backoff(self):
        assert UNLIMITED.error_backoff == 1.0


# ─── Config Presets ───────────────────────────────────────────

class TestUnlimitedConfig:
    """Config presets for unlimited mode."""

    def test_rate_limits_unlimited(self):
        for strategy, config in ANON_RATE_LIMITS_UNLIMITED.items():
            assert config["requests"] == 999999
            assert config["window"] == 1

    def test_delays_unlimited(self):
        assert ANON_REQUEST_DELAYS_UNLIMITED["min"] == 0.0
        assert ANON_REQUEST_DELAYS_UNLIMITED["max"] == 0.0
        assert ANON_REQUEST_DELAYS_UNLIMITED["after_error"]["min"] == 0.0
        assert ANON_REQUEST_DELAYS_UNLIMITED["after_rate_limit"]["max"] == 0.0


# ─── Factory Methods ─────────────────────────────────────────

class TestFactoryMethods:
    """Instagram.anonymous(unlimited=True) creates unlimited client."""

    def test_sync_anonymous_unlimited(self):
        from instaapi.instagram import Instagram
        ig = Instagram.anonymous(unlimited=True)
        assert ig._anon_client._unlimited is True
        assert ig._anon_client._rate_limiter._enabled is False
        ig.close()

    def test_sync_anonymous_normal(self):
        from instaapi.instagram import Instagram
        ig = Instagram.anonymous()
        assert ig._anon_client._unlimited is False
        assert ig._anon_client._rate_limiter._enabled is True
        ig.close()

    def test_async_anonymous_unlimited(self):
        from instaapi.async_instagram import AsyncInstagram
        ig = AsyncInstagram.anonymous(unlimited=True)
        assert ig._anon_client._unlimited is True
        assert ig._anon_client._rate_limiter._enabled is False

    def test_async_anonymous_normal(self):
        from instaapi.async_instagram import AsyncInstagram
        ig = AsyncInstagram.anonymous()
        assert ig._anon_client._unlimited is False
        assert ig._anon_client._rate_limiter._enabled is True
