"""
Tests for async anonymous client.
Verifies AsyncAnonClient, AsyncPublicAPI, and AsyncInstagram integration.
"""

import asyncio
import time
import pytest

from instaapi.async_anon_client import AsyncAnonClient, AsyncAnonRateLimiter, AsyncStrategyFailed
from instaapi.speed_modes import get_mode


# ─── AsyncAnonRateLimiter ────────────────────────────────────

class TestAsyncAnonRateLimiter:
    """AsyncAnonRateLimiter tests."""

    @pytest.mark.asyncio
    async def test_disabled_returns_immediately(self):
        limiter = AsyncAnonRateLimiter(enabled=False)
        start = time.time()
        for _ in range(100):
            await limiter.wait_if_needed("html_parse")
        elapsed = time.time() - start
        assert elapsed < 0.1, f"Disabled limiter should be instant, took {elapsed:.3f}s"

    @pytest.mark.asyncio
    async def test_enabled_blocks_after_limit(self):
        limiter = AsyncAnonRateLimiter(enabled=True)
        # Default html_parse: 10 req/60s
        # Fire 12 quick calls — should start blocking
        results = []
        for _ in range(12):
            start = time.time()
            await limiter.wait_if_needed("html_parse")
            results.append(time.time() - start)
        # At least a few should have some delay
        # (first 10 should be fast, 11th+ should have delay)
        assert any(t > 0.05 for t in results[10:]), "Enabled limiter should block after limit"


# ─── AsyncAnonClient ─────────────────────────────────────────

class TestAsyncAnonClient:
    """AsyncAnonClient unit tests."""

    @pytest.mark.asyncio
    async def test_human_delay_skipped_unlimited(self):
        client = AsyncAnonClient(unlimited=True)
        start = time.time()
        for _ in range(50):
            await client._human_delay()
        elapsed = time.time() - start
        assert elapsed < 0.05, f"_human_delay should be skipped in unlimited, took {elapsed:.3f}s"
        await client.close()

    @pytest.mark.asyncio
    async def test_human_delay_normal_has_delay(self):
        client = AsyncAnonClient(unlimited=False)
        start = time.time()
        await client._human_delay()
        elapsed = time.time() - start
        assert elapsed >= 0.5, f"Normal mode should have delay, took {elapsed:.3f}s"
        await client.close()

    def test_unlimited_flag(self):
        client = AsyncAnonClient(unlimited=True)
        assert client._unlimited is True
        assert client._rate_limiter._enabled is False
        assert client._max_concurrency == 1000

    def test_normal_flag(self):
        client = AsyncAnonClient(unlimited=False)
        assert client._unlimited is False
        assert client._rate_limiter._enabled is True
        assert client._max_concurrency == 10

    def test_custom_concurrency(self):
        client = AsyncAnonClient(unlimited=True, max_concurrency=500)
        assert client._max_concurrency == 500

    def test_delays_config_unlimited(self):
        client = AsyncAnonClient(unlimited=True)
        assert client._delays["min"] == 0.0
        assert client._delays["max"] == 0.0

    def test_delays_config_normal(self):
        client = AsyncAnonClient(unlimited=False)
        assert client._delays["min"] > 0
        assert client._delays["max"] > 0

    def test_repr(self):
        client = AsyncAnonClient(unlimited=True)
        assert "UNLIMITED" in repr(client)
        assert "1000" in repr(client)

    def test_stats(self):
        client = AsyncAnonClient(unlimited=True)
        stats = client.stats
        assert stats["unlimited"] is True
        assert stats["max_concurrency"] == 1000
        assert stats["requests"] == 0
        assert stats["active"] == 0


# ─── AsyncInstagram Integration ──────────────────────────────

class TestAsyncInstagramIntegration:
    """AsyncInstagram.anonymous() creates async anonymous client."""

    def test_anonymous_creates_async_client(self):
        from instaapi.async_instagram import AsyncInstagram
        ig = AsyncInstagram.anonymous()
        assert isinstance(ig._anon_client, AsyncAnonClient)
        assert ig._anon_client._unlimited is False

    def test_anonymous_unlimited_creates_async_client(self):
        from instaapi.async_instagram import AsyncInstagram
        ig = AsyncInstagram.anonymous(unlimited=True)
        assert isinstance(ig._anon_client, AsyncAnonClient)
        assert ig._anon_client._unlimited is True
        assert ig._anon_client._max_concurrency == 1000

    def test_anonymous_has_async_public_api(self):
        from instaapi.async_instagram import AsyncInstagram
        from instaapi.api.async_public import AsyncPublicAPI
        ig = AsyncInstagram.anonymous()
        assert isinstance(ig.public, AsyncPublicAPI)

    def test_default_init_uses_async_anon(self):
        """Even default init should have async anon client."""
        from instaapi.async_instagram import AsyncInstagram
        ig = AsyncInstagram()
        assert isinstance(ig._anon_client, AsyncAnonClient)

    @pytest.mark.asyncio
    async def test_close_cleans_async_session(self):
        from instaapi.async_instagram import AsyncInstagram
        ig = AsyncInstagram.anonymous(unlimited=True)
        # Get session (creates it)
        _ = await ig._anon_client._get_session()
        assert ig._anon_client._session is not None
        # Close
        await ig.close()
        assert ig._anon_client._session is None


# ─── Concurrency Tests ───────────────────────────────────────

class TestConcurrency:
    """Verify that asyncio.Semaphore limits concurrent requests."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """Simulate concurrent access to match semaphore limit."""
        client = AsyncAnonClient(unlimited=True, max_concurrency=5)
        active = 0
        max_active = 0

        async def simulated_request():
            nonlocal active, max_active
            async with client._semaphore:
                active += 1
                max_active = max(max_active, active)
                await asyncio.sleep(0.05)
                active -= 1

        tasks = [simulated_request() for _ in range(20)]
        await asyncio.gather(*tasks)

        assert max_active <= 5, f"Max active was {max_active}, expected <=5"
        await client.close()

    @pytest.mark.asyncio
    async def test_unlimited_high_concurrency(self):
        """With unlimited + high concurrency, many tasks can run in parallel."""
        client = AsyncAnonClient(unlimited=True, max_concurrency=100)
        active = 0
        max_active = 0

        async def simulated_request():
            nonlocal active, max_active
            async with client._semaphore:
                active += 1
                max_active = max(max_active, active)
                await asyncio.sleep(0.02)
                active -= 1

        tasks = [simulated_request() for _ in range(200)]
        await asyncio.gather(*tasks)

        assert max_active > 20, f"Expected high parallelism, got max_active={max_active}"
        await client.close()
