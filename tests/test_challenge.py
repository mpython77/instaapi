"""
Tests for Challenge Handler: type detection, context building, result handling.
"""

import pytest
from instaharvest_v2.challenge import ChallengeHandler, ChallengeType, ChallengeContext, ChallengeResult
from instaharvest_v2.exceptions import ChallengeRequired


class TestChallengeType:
    """Test ChallengeType enum."""

    def test_values(self):
        assert ChallengeType.EMAIL == "email"
        assert ChallengeType.SMS == "sms"
        assert ChallengeType.CONSENT == "consent"
        assert ChallengeType.CAPTCHA == "captcha"
        assert ChallengeType.UNKNOWN == "unknown"


class TestChallengeHandler:
    """Test ChallengeHandler methods."""

    def test_is_enabled_without_callback(self):
        handler = ChallengeHandler()
        assert handler.is_enabled is False

    def test_is_enabled_with_callback(self):
        handler = ChallengeHandler(code_callback=lambda ctx: "123456")
        assert handler.is_enabled is True

    def test_detect_type_email(self, challenge_response_email):
        handler = ChallengeHandler()
        ctype = handler._detect_type(challenge_response_email)
        assert ctype in (ChallengeType.EMAIL, ChallengeType.UNKNOWN)

    def test_detect_type_sms(self, challenge_response_sms):
        handler = ChallengeHandler()
        ctype = handler._detect_type(challenge_response_sms)
        assert ctype == ChallengeType.SMS

    def test_detect_type_consent(self):
        handler = ChallengeHandler()
        info = {"step_name": "consent_required"}
        ctype = handler._detect_type(info)
        assert ctype == ChallengeType.CONSENT

    def test_detect_type_verify_email(self):
        handler = ChallengeHandler()
        info = {"step_name": "verify_email"}
        ctype = handler._detect_type(info)
        assert ctype == ChallengeType.EMAIL

    def test_detect_type_delta_login(self):
        handler = ChallengeHandler()
        info = {"step_name": "delta_login_review"}
        ctype = handler._detect_type(info)
        assert ctype == ChallengeType.EMAIL

    def test_detect_type_unknown(self):
        handler = ChallengeHandler()
        info = {"step_name": "something_new"}
        ctype = handler._detect_type(info)
        assert ctype == ChallengeType.UNKNOWN

    def test_detect_type_from_step_data_email(self):
        handler = ChallengeHandler()
        info = {"step_name": "", "step_data": {"email": "t@g.com"}}
        ctype = handler._detect_type(info)
        assert ctype == ChallengeType.EMAIL

    def test_detect_type_from_step_data_phone(self):
        handler = ChallengeHandler()
        info = {"step_name": "", "step_data": {"phone_number": "+1234"}}
        ctype = handler._detect_type(info)
        assert ctype == ChallengeType.SMS

    def test_normalize_url_absolute(self):
        url = ChallengeHandler._normalize_url("https://i.instagram.com/api/v1/challenge/123/")
        assert url == "https://i.instagram.com/api/v1/challenge/123/"

    def test_normalize_url_relative(self):
        url = ChallengeHandler._normalize_url("/challenge/123/")
        assert url == "https://i.instagram.com/api/v1/challenge/123/"

    def test_resolve_without_callback(self):
        handler = ChallengeHandler()
        result = handler.resolve(None, "/challenge/123/", "token")
        assert result.success is False
        assert "No challenge callback" in result.message

    def test_parse_challenge_html(self):
        html = '{"step_name": "verify_email", "contact_point": "t***@g.com"}'
        data = ChallengeHandler._parse_challenge_html(html)
        assert data.get("step_name") == "verify_email"


class TestChallengeContext:
    """Test ChallengeContext dataclass."""

    def test_creation(self):
        ctx = ChallengeContext(
            challenge_type=ChallengeType.EMAIL,
            contact_point="t***@gmail.com",
            message="Code sent",
        )
        assert ctx.challenge_type == ChallengeType.EMAIL
        assert ctx.contact_point == "t***@gmail.com"


class TestChallengeResult:
    """Test ChallengeResult dataclass."""

    def test_success(self):
        result = ChallengeResult(success=True, message="OK")
        assert result.success is True

    def test_failure(self):
        result = ChallengeResult(success=False, message="Bad code")
        assert result.success is False
        assert result.challenge_type == ChallengeType.UNKNOWN


class TestChallengeRequiredException:
    """Test ChallengeRequired exception properties."""

    def test_challenge_url_from_response(self):
        exc = ChallengeRequired(
            "test",
            response={"challenge": {"url": "/challenge/123/", "challenge_type": "email"}},
        )
        assert exc.challenge_url == "/challenge/123/"
        assert exc.challenge_type == "email"

    def test_challenge_url_empty(self):
        exc = ChallengeRequired("test", response={})
        assert exc.challenge_url == ""
        assert exc.challenge_type == "unknown"
