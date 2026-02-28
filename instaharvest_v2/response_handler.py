"""
Response Handler
================
Centralized HTTP response parsing and error detection.
Used by both sync HttpClient and async AsyncHttpClient.
DRY principle — all response handling logic in one place.
"""

import logging
from typing import Any, Dict, Optional

from .session_manager import SessionManager, SessionInfo
from .exceptions import (
    InstagramError,
    LoginRequired,
    RateLimitError,
    NotFoundError,
    ChallengeRequired,
    CheckpointRequired,
    ConsentRequired,
    NetworkError,
    PrivateAccountError,
)

logger = logging.getLogger("instaharvest_v2.response")

# Import at function-call time to avoid circular import
def _dbg():
    from .log_config import get_debug_logger
    return get_debug_logger()


class ResponseHandler:
    """
    Centralized response handler for Instagram API responses.

    Handles:
        - HTTP status code mapping to exceptions
        - Instagram internal error detection (status=fail, require_login, etc.)
        - Session header updates (x-ig-set-www-claim)
        - JSON parsing with fallback detection
    """

    def __init__(self, session_manager: SessionManager):
        self._session_mgr = session_manager

    def _classify_error(
        self,
        msg: str,
        status_code: int,
        body: dict,
        session: SessionInfo,
    ) -> None:
        """
        Classify and raise appropriate exception based on error message.
        Shared logic for HTTP 400/403 and JSON status=fail.

        Raises:
            LoginRequired, ChallengeRequired, CheckpointRequired,
            ConsentRequired, NotFoundError, PrivateAccountError,
            InstagramError
        """
        if not msg:
            return

        msg_lower = msg.lower()

        if "login_required" in msg_lower or "login" in msg_lower:
            self._session_mgr.report_error(session, is_login_error=True)
            raise LoginRequired(msg, status_code=status_code, response=body)

        if "useragent mismatch" in msg_lower:
            raise InstagramError(
                "User-Agent mismatch. USER_AGENT in .env must match "
                "the UA from the browser where the session was created.",
                status_code=status_code,
                response=body,
            )

        if "challenge" in msg_lower:
            raise ChallengeRequired(msg, status_code=status_code, response=body)

        if "checkpoint" in msg_lower:
            raise CheckpointRequired(msg, status_code=status_code, response=body)

        if "consent" in msg_lower:
            raise ConsentRequired(msg, status_code=status_code, response=body)

        if "not_found" in msg_lower or "user_not_found" in msg_lower:
            raise NotFoundError(msg, status_code=status_code, response=body)

        if "private" in msg_lower:
            raise PrivateAccountError(msg, status_code=status_code, response=body)

    def handle(self, response, session: SessionInfo) -> Dict[str, Any]:
        """
        Parse HTTP response, detect errors, update session headers.

        Args:
            response: curl_cffi Response object
            session: Current session info

        Returns:
            Parsed JSON dict

        Raises:
            LoginRequired, RateLimitError, NotFoundError,
            ChallengeRequired, CheckpointRequired, ConsentRequired,
            PrivateAccountError, NetworkError, InstagramError
        """
        status = response.status_code

        # ─── Update session from response headers ──────────────
        ig_set_www_claim = response.headers.get("x-ig-set-www-claim")
        if ig_set_www_claim:
            session.ig_www_claim = ig_set_www_claim

        # ─── 429 Rate Limit ───────────────────────────────────
        if status == 429:
            _dbg().error(
                error_type="RateLimitError",
                status_code=429,
                message="Too many requests",
            )
            raise RateLimitError(
                "Rate limit - too many requests",
                status_code=429,
            )

        # ─── 401 Unauthorized ─────────────────────────────────
        if status == 401:
            _dbg().error(
                error_type="LoginRequired",
                status_code=401,
                message="Session expired (401 Unauthorized)",
            )
            self._session_mgr.report_error(session, is_login_error=True)
            raise LoginRequired(
                "Session expired. New session_id needed.",
                status_code=401,
            )

        # ─── 404 Not Found ────────────────────────────────────
        if status == 404:
            raise NotFoundError("Resource not found", status_code=404)

        # ─── 3xx Redirect (POST with allow_redirects=False) ───
        if 300 <= status < 400:
            try:
                return response.json()
            except Exception:
                return {"status": "ok", "redirected": True}

        # ─── 400/403 Client Errors ────────────────────────────
        if status in (400, 403):
            try:
                body = response.json()
            except Exception:
                body = {}

            # Login required
            if body.get("require_login") or body.get("message") == "login_required":
                self._session_mgr.report_error(session, is_login_error=True)
                raise LoginRequired("Login required", status_code=status, response=body)

            # 403 + login_required in text (HTML response)
            if status == 403 and not body:
                text = response.text[:200]
                if "login_required" in text:
                    self._session_mgr.report_error(session, is_login_error=True)
                    raise LoginRequired(
                        "Session login_required — new cookie needed",
                        status_code=403,
                    )

            # Challenge
            if body.get("challenge"):
                challenge_url = body.get('challenge', {}).get('url', '')
                _dbg().block_detected(
                    block_type="CHALLENGE REQUIRED",
                    url=challenge_url,
                    status_code=status,
                    message=f"Challenge in {status} response",
                )
                raise ChallengeRequired(
                    f"Challenge required: {challenge_url}",
                    status_code=status,
                    response=body,
                )

            # Checkpoint
            if body.get("checkpoint_url"):
                cp_url = body.get('checkpoint_url', '')
                _dbg().block_detected(
                    block_type="CHECKPOINT REQUIRED",
                    url=cp_url,
                    status_code=status,
                )
                raise CheckpointRequired(
                    f"Checkpoint: {cp_url}",
                    status_code=status,
                    response=body,
                )

            # Consent
            if body.get("consent_required"):
                raise ConsentRequired("Consent required", status_code=status, response=body)

            # Spam detection
            if body.get("spam"):
                _dbg().error(
                    error_type="SpamDetected",
                    status_code=status,
                    message="Instagram detected spam behavior",
                )
                raise RateLimitError("Spam detected", status_code=status, response=body)

            # Message-based errors — single classify method
            msg = body.get("message", "")
            self._classify_error(msg, status_code=status, body=body, session=session)

            raise InstagramError(
                f"Instagram error: {msg or body or response.text[:200]}",
                status_code=status,
                response=body,
            )

        # ─── 5xx Server Errors ────────────────────────────────
        if status >= 500:
            raise NetworkError(f"Server error ({status})", status_code=status)

        # ─── Parse JSON ───────────────────────────────────────
        try:
            data = response.json()
        except Exception:
            text = response.text[:200]
            if "login" in text.lower() or "LoginAndSignupPage" in text:
                _dbg().error(
                    error_type="LoginRequired",
                    status_code=status,
                    message="Redirected to login page (HTML response)",
                    response_preview=text[:100],
                )
                self._session_mgr.report_error(session, is_login_error=True)
                raise LoginRequired("Instagram redirected to login page")
            _dbg().error(
                error_type="JSONParseError",
                status_code=status,
                message="Failed to parse JSON response",
                response_preview=text[:100],
            )
            raise InstagramError(
                f"JSON parse error. Status: {status}",
                status_code=status,
            )

        # ─── Instagram internal errors (status=fail) ──────────
        if isinstance(data, dict):
            ig_status = data.get("status", "")
            message = data.get("message", "")

            if ig_status == "fail":
                # Use shared classify method
                self._classify_error(
                    msg=message, status_code=status, body=data, session=session,
                )
                raise InstagramError(message, status_code=status, response=data)

            # require_login flag
            if data.get("require_login"):
                self._session_mgr.report_error(session, is_login_error=True)
                raise LoginRequired(
                    "require_login flag detected",
                    status_code=status,
                    response=data,
                )

        return data
