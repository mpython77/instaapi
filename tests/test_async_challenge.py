"""
Tests for AsyncChallengeHandler — async challenge resolution.
"""

import asyncio
import pytest
from instaharvest_v2.async_challenge import AsyncChallengeHandler
from instaharvest_v2.challenge import ChallengeType, ChallengeContext, ChallengeResult


class TestAsyncChallengeHandlerInit:
    """Test initialization."""

    def test_default_init(self):
        handler = AsyncChallengeHandler()
        assert handler.is_enabled is False
        assert handler._preferred_method == ChallengeType.EMAIL

    def test_with_sync_callback(self):
        handler = AsyncChallengeHandler(code_callback=lambda ctx: "123456")
        assert handler.is_enabled is True

    def test_with_async_callback(self):
        async def async_cb(ctx):
            return "123456"
        handler = AsyncChallengeHandler(code_callback=async_cb)
        assert handler.is_enabled is True

    def test_preferred_method(self):
        handler = AsyncChallengeHandler(preferred_method=ChallengeType.SMS)
        assert handler._preferred_method == ChallengeType.SMS


class TestAsyncChallengeTypeDetection:
    """Test challenge type detection."""

    def test_email_type(self):
        handler = AsyncChallengeHandler()
        assert handler._detect_type({"step_name": "verify_email"}) == ChallengeType.EMAIL

    def test_sms_type(self):
        handler = AsyncChallengeHandler()
        assert handler._detect_type({"step_name": "verify_phone"}) == ChallengeType.SMS

    def test_consent_type(self):
        handler = AsyncChallengeHandler()
        assert handler._detect_type({"step_name": "consent"}) == ChallengeType.CONSENT

    def test_unknown_type(self):
        handler = AsyncChallengeHandler()
        assert handler._detect_type({"step_name": "something_else"}) == ChallengeType.UNKNOWN


class TestChallengeContext:
    """Test ChallengeContext dataclass."""

    def test_creation(self):
        ctx = ChallengeContext(
            challenge_type=ChallengeType.EMAIL,
            contact_point="t***@gmail.com",
        )
        assert ctx.challenge_type == ChallengeType.EMAIL
        assert ctx.contact_point == "t***@gmail.com"

    def test_defaults(self):
        ctx = ChallengeContext(challenge_type=ChallengeType.SMS)
        assert ctx.contact_point == ""
        assert ctx.step_name == ""


class TestChallengeResult:
    """Test ChallengeResult dataclass."""

    def test_success(self):
        result = ChallengeResult(success=True, message="OK")
        assert result.success is True
        assert result.message == "OK"

    def test_failure(self):
        result = ChallengeResult(success=False, message="Invalid code")
        assert result.success is False
        assert result.message == "Invalid code"


class TestAsyncCallbackHandling:
    """Test async callback invocation."""

    @pytest.mark.asyncio
    async def test_sync_callback_via_async(self):
        received = []

        def sync_cb(ctx: ChallengeContext) -> str:
            received.append(ctx.challenge_type)
            return "123456"

        handler = AsyncChallengeHandler(code_callback=sync_cb)
        ctx = ChallengeContext(challenge_type=ChallengeType.EMAIL)
        code = await handler._get_code(ctx)
        assert code == "123456"
        assert received == [ChallengeType.EMAIL]

    @pytest.mark.asyncio
    async def test_async_callback(self):
        received = []

        async def async_cb(ctx: ChallengeContext) -> str:
            received.append(ctx.challenge_type)
            return "654321"

        handler = AsyncChallengeHandler(code_callback=async_cb)
        ctx = ChallengeContext(challenge_type=ChallengeType.SMS)
        code = await handler._get_code(ctx)
        assert code == "654321"
        assert received == [ChallengeType.SMS]


class TestURLNormalization:
    """Test challenge URL normalization."""

    def test_full_url(self):
        handler = AsyncChallengeHandler()
        url = handler._normalize_url("https://www.instagram.com/challenge/12345/")
        assert url == "https://www.instagram.com/challenge/12345/"

    def test_path_only(self):
        handler = AsyncChallengeHandler()
        url = handler._normalize_url("/challenge/12345/")
        assert url.startswith("https://")
        assert "/challenge/12345/" in url
