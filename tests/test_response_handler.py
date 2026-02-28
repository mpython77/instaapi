"""
Tests for ResponseHandler: exception mapping and error detection.
"""

import pytest
from unittest.mock import MagicMock
from instaharvest_v2.response_handler import ResponseHandler
from instaharvest_v2.session_manager import SessionManager, SessionInfo
from instaharvest_v2.exceptions import (
    LoginRequired,
    RateLimitError,
    NotFoundError,
    ChallengeRequired,
    CheckpointRequired,
    ConsentRequired,
    PrivateAccountError,
    NetworkError,
    InstagramError,
)


@pytest.fixture
def handler():
    sm = SessionManager()
    sm.add_session("sid", "csrf", "uid")
    return ResponseHandler(sm)


@pytest.fixture
def session():
    return SessionInfo(
        session_id="sid", csrf_token="csrf", ds_user_id="uid",
    )


def make_response(status_code=200, json_data=None, text="", headers=None):
    """Create mock response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.headers = headers or {}
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("No JSON")
    return resp


class TestStatusCodes:
    """Test HTTP status code → exception mapping."""

    def test_429_rate_limit(self, handler, session):
        resp = make_response(429)
        with pytest.raises(RateLimitError):
            handler.handle(resp, session)

    def test_401_login_required(self, handler, session):
        resp = make_response(401)
        with pytest.raises(LoginRequired):
            handler.handle(resp, session)

    def test_404_not_found(self, handler, session):
        resp = make_response(404)
        with pytest.raises(NotFoundError):
            handler.handle(resp, session)

    def test_500_network_error(self, handler, session):
        resp = make_response(500)
        with pytest.raises(NetworkError):
            handler.handle(resp, session)

    def test_3xx_redirect(self, handler, session):
        resp = make_response(302, json_data={"status": "ok"})
        result = handler.handle(resp, session)
        assert result["status"] == "ok"


class TestBodyErrors:
    """Test Instagram body-level error detection."""

    def test_challenge_required(self, handler, session):
        resp = make_response(400, json_data={
            "challenge": {"url": "/challenge/123/"},
        })
        with pytest.raises(ChallengeRequired) as exc_info:
            handler.handle(resp, session)
        assert "123" in str(exc_info.value)

    def test_checkpoint_required(self, handler, session):
        resp = make_response(400, json_data={
            "checkpoint_url": "/checkpoint/123/",
        })
        with pytest.raises(CheckpointRequired):
            handler.handle(resp, session)

    def test_consent_required(self, handler, session):
        resp = make_response(400, json_data={
            "consent_required": True,
        })
        with pytest.raises(ConsentRequired):
            handler.handle(resp, session)

    def test_login_required_flag(self, handler, session):
        resp = make_response(400, json_data={
            "require_login": True,
        })
        with pytest.raises(LoginRequired):
            handler.handle(resp, session)

    def test_spam_detected(self, handler, session):
        resp = make_response(400, json_data={
            "spam": True,
        })
        with pytest.raises(RateLimitError):
            handler.handle(resp, session)

    def test_challenge_in_message(self, handler, session):
        resp = make_response(400, json_data={
            "message": "challenge_required",
        })
        with pytest.raises(ChallengeRequired):
            handler.handle(resp, session)

    def test_private_account(self, handler, session):
        resp = make_response(400, json_data={
            "message": "private user",
        })
        with pytest.raises(PrivateAccountError):
            handler.handle(resp, session)


class TestSuccessResponse:
    """Test successful response parsing."""

    def test_200_ok(self, handler, session):
        resp = make_response(200, json_data={
            "status": "ok",
            "user": {"pk": 123},
        })
        result = handler.handle(resp, session)
        assert result["status"] == "ok"

    def test_status_fail(self, handler, session):
        resp = make_response(200, json_data={
            "status": "fail",
            "message": "something went wrong",
        })
        with pytest.raises(InstagramError):
            handler.handle(resp, session)

    def test_header_update(self, handler, session):
        resp = make_response(200, json_data={"status": "ok"}, headers={
            "x-ig-set-www-claim": "new_claim_value",
        })
        handler.handle(resp, session)
        assert session.ig_www_claim == "new_claim_value"
