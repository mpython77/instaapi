"""
Challenge Handler
=================
Automatic Instagram challenge/verification resolver.

Challenge flow:
    1. API request → ChallengeRequired exception (with challenge URL)
    2. GET challenge URL → form data (step_name, methods)
    3. Select verification method (email/SMS)
    4. POST → Instagram sends code to user
    5. Get code from user via callback
    6. POST code → challenge resolved
    7. Retry original request

Usage:
    ig = Instagram(challenge_callback=lambda: input("Enter code: "))
    # Challenges will be resolved automatically

    # Or disable auto-resolve:
    ig = Instagram()  # raises ChallengeRequired
"""

import json
import re
import time
import logging
from enum import Enum
from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass, field

from curl_cffi import requests as curl_requests

logger = logging.getLogger("instaapi.challenge")


# ─── Types ──────────────────────────────────────────────────

class ChallengeType(str, Enum):
    """Instagram challenge types."""
    EMAIL = "email"
    SMS = "sms"
    PHONE = "phone"
    CONSENT = "consent"
    CAPTCHA = "captcha"
    UNKNOWN = "unknown"


@dataclass
class ChallengeContext:
    """
    Context passed to the challenge callback.
    
    The callback receives this so the user knows
    what type of challenge and where the code was sent.
    """
    challenge_type: ChallengeType
    contact_point: str = ""       # e.g. "a****@gmail.com" or "+1 *** ***42"
    step_name: str = ""           # e.g. "verify_email", "verify_code"
    message: str = ""             # Human-readable message


@dataclass
class ChallengeResult:
    """Result of challenge resolution attempt."""
    success: bool
    challenge_type: ChallengeType = ChallengeType.UNKNOWN
    message: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)


# ─── Challenge Handler ──────────────────────────────────────

class ChallengeHandler:
    """
    Resolves Instagram challenges (email/SMS verification, consent).

    Architecture:
        1. Intercepts ChallengeRequired from ResponseHandler
        2. GETs challenge page to detect type
        3. Selects verification method (email preferred)
        4. Sends code request to Instagram
        5. Gets code from user via callback
        6. Submits code and verifies
        7. Returns ChallengeResult

    Supports:
        - Email verification
        - SMS/Phone verification
        - Consent acceptance
        - Custom callback for code input
        - Auto-method selection (email > SMS)
    """

    # Instagram challenge endpoints
    CHALLENGE_BASE = "https://i.instagram.com/api/v1"

    def __init__(
        self,
        code_callback: Optional[Callable[[ChallengeContext], str]] = None,
        preferred_method: ChallengeType = ChallengeType.EMAIL,
    ):
        """
        Args:
            code_callback: Function that receives ChallengeContext and returns
                          the verification code as string.
                          Example: lambda ctx: input(f"Enter code sent to {ctx.contact_point}: ")
            preferred_method: Preferred verification method (EMAIL or SMS)
        """
        self._code_callback = code_callback
        self._preferred_method = preferred_method

    @property
    def is_enabled(self) -> bool:
        """Whether auto-resolve is enabled (callback provided)."""
        return self._code_callback is not None

    def resolve(
        self,
        session: curl_requests.Session,
        challenge_url: str,
        csrf_token: str,
        user_agent: str = "",
    ) -> ChallengeResult:
        """
        Resolve an Instagram challenge.

        Args:
            session: curl_cffi Session with cookies
            challenge_url: Challenge URL from ChallengeRequired exception
            csrf_token: Current CSRF token
            user_agent: User-Agent string

        Returns:
            ChallengeResult with success/failure
        """
        if not self._code_callback:
            return ChallengeResult(
                success=False,
                message="No challenge callback provided. Set challenge_callback on Instagram().",
            )

        headers = self._build_headers(csrf_token, user_agent)
        full_url = self._normalize_url(challenge_url)

        try:
            # Step 1: GET challenge info
            info = self._get_challenge_info(session, full_url, headers)
            challenge_type = self._detect_type(info)

            logger.info(f"Challenge detected: type={challenge_type.value}, step={info.get('step_name', '?')}")

            # Step 2: Handle by type
            if challenge_type == ChallengeType.CONSENT:
                return self._handle_consent(session, full_url, headers, info)

            if challenge_type in (ChallengeType.EMAIL, ChallengeType.SMS, ChallengeType.PHONE):
                return self._handle_verification(
                    session, full_url, headers, info, challenge_type,
                )

            return ChallengeResult(
                success=False,
                challenge_type=challenge_type,
                message=f"Unsupported challenge type: {challenge_type.value}",
                raw_response=info,
            )

        except Exception as e:
            logger.error(f"Challenge resolution failed: {e}")
            return ChallengeResult(
                success=False,
                message=f"Challenge resolution error: {e}",
            )

    # ─── Internal Methods ────────────────────────────────────

    def _get_challenge_info(
        self,
        session: curl_requests.Session,
        url: str,
        headers: dict,
    ) -> Dict[str, Any]:
        """GET challenge URL to fetch form data and available methods."""
        # Only disable SSL verify when proxy is configured (to avoid MITM)
        uses_proxy = bool(getattr(session, '_proxy', None) or getattr(session, 'proxies', None))
        resp = session.get(
            url,
            headers=headers,
            timeout=15,
            verify=not uses_proxy,
        )
        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError):
            # Try to parse HTML response for challenge form
            data = self._parse_challenge_html(resp.text)

        logger.debug(f"Challenge info: {data}")
        return data

    def _detect_type(self, info: Dict[str, Any]) -> ChallengeType:
        """Detect challenge type from response data."""
        step_name = info.get("step_name", "").lower()

        # Direct step_name mapping
        type_map = {
            "verify_email": ChallengeType.EMAIL,
            "email": ChallengeType.EMAIL,
            "verify_code": ChallengeType.EMAIL,  # generic code → try email
            "phone_number": ChallengeType.SMS,
            "verify_phone": ChallengeType.SMS,
            "sms": ChallengeType.SMS,
            "consent": ChallengeType.CONSENT,
            "accept": ChallengeType.CONSENT,
            "delta_login_review": ChallengeType.EMAIL,  # "Was this you?" → email
            "captcha": ChallengeType.CAPTCHA,
        }

        for key, ctype in type_map.items():
            if key in step_name:
                return ctype

        # Check step_data for clues
        step_data = info.get("step_data", {})

        if step_data.get("email"):
            return ChallengeType.EMAIL
        if step_data.get("phone_number"):
            return ChallengeType.SMS
        if step_data.get("contact_point"):
            contact = step_data["contact_point"]
            if "@" in contact:
                return ChallengeType.EMAIL
            return ChallengeType.SMS

        # Check challenge_context
        challenge_context = info.get("challenge_context", "")
        if isinstance(challenge_context, str):
            if "email" in challenge_context.lower():
                return ChallengeType.EMAIL
            if "sms" in challenge_context.lower() or "phone" in challenge_context.lower():
                return ChallengeType.SMS

        return ChallengeType.UNKNOWN

    def _select_method(
        self,
        session: curl_requests.Session,
        url: str,
        headers: dict,
        method: ChallengeType,
    ) -> Dict[str, Any]:
        """
        Select verification method (email or SMS).
        Instagram uses choice=0 for SMS, choice=1 for email.
        """
        choice = 1 if method == ChallengeType.EMAIL else 0

        uses_proxy = bool(getattr(session, '_proxy', None) or getattr(session, 'proxies', None))
        resp = session.post(
            url,
            headers=headers,
            data={"choice": str(choice)},
            timeout=15,
            verify=not uses_proxy,
        )
        try:
            return resp.json()
        except (ValueError, json.JSONDecodeError):
            return {"status": "fail", "raw": resp.text[:500]}

    def _submit_code(
        self,
        session: curl_requests.Session,
        url: str,
        headers: dict,
        code: str,
    ) -> Dict[str, Any]:
        """Submit verification code."""
        uses_proxy = bool(getattr(session, '_proxy', None) or getattr(session, 'proxies', None))
        resp = session.post(
            url,
            headers=headers,
            data={"security_code": code},
            timeout=15,
            verify=not uses_proxy,
        )
        try:
            return resp.json()
        except (ValueError, json.JSONDecodeError):
            return {"status": "fail", "raw": resp.text[:500]}

    def _handle_verification(
        self,
        session: curl_requests.Session,
        url: str,
        headers: dict,
        info: Dict[str, Any],
        challenge_type: ChallengeType,
    ) -> ChallengeResult:
        """Handle email/SMS verification challenge."""
        step_name = info.get("step_name", "")
        step_data = info.get("step_data", {})

        # Extract contact point
        contact_point = (
            step_data.get("contact_point", "")
            or step_data.get("email", "")
            or step_data.get("phone_number", "")
        )

        # If step is "select_verify_method" → need to choose method first
        if "select" in step_name.lower() or info.get("step_name") == "select_verify_method":
            logger.info(f"Selecting verification method: {challenge_type.value}")
            select_result = self._select_method(session, url, headers, challenge_type)

            if select_result.get("status") == "fail":
                return ChallengeResult(
                    success=False,
                    challenge_type=challenge_type,
                    message=f"Method selection failed: {select_result}",
                    raw_response=select_result,
                )

            # Update step data from selection result
            step_data = select_result.get("step_data", step_data)
            contact_point = (
                step_data.get("contact_point", contact_point)
                or step_data.get("email", "")
                or step_data.get("phone_number", "")
            )

        # Build context for callback
        ctx = ChallengeContext(
            challenge_type=challenge_type,
            contact_point=contact_point,
            step_name=step_name,
            message=f"Instagram sent verification code to {contact_point}",
        )

        # Get code from user
        logger.info(f"Requesting code from user (sent to {contact_point})")
        code = self._code_callback(ctx)

        if not code or not code.strip():
            return ChallengeResult(
                success=False,
                challenge_type=challenge_type,
                message="No code provided by user",
            )

        code = code.strip()

        # Submit code
        logger.info(f"Submitting verification code: {code[:2]}***")
        result = self._submit_code(session, url, headers, code)

        # Check result
        if result.get("status") == "ok" or result.get("logged_in_user"):
            logger.info("Challenge resolved successfully! ✅")
            return ChallengeResult(
                success=True,
                challenge_type=challenge_type,
                message="Challenge resolved",
                raw_response=result,
            )

        # Retry with fresh code?
        error_msg = result.get("message", "Invalid code")
        logger.warning(f"Code verification failed: {error_msg}")

        return ChallengeResult(
            success=False,
            challenge_type=challenge_type,
            message=f"Code verification failed: {error_msg}",
            raw_response=result,
        )

    def _handle_consent(
        self,
        session: curl_requests.Session,
        url: str,
        headers: dict,
        info: Dict[str, Any],
    ) -> ChallengeResult:
        """Handle consent/ToS acceptance challenge."""
        logger.info("Handling consent challenge — auto-accepting")

        uses_proxy = bool(getattr(session, '_proxy', None) or getattr(session, 'proxies', None))
        resp = session.post(
            url,
            headers=headers,
            data={"choice": "0"},  # Accept
            timeout=15,
            verify=not uses_proxy,
        )

        try:
            result = resp.json()
        except (ValueError, json.JSONDecodeError):
            result = {"status": "fail", "raw": resp.text[:300]}

        success = result.get("status") == "ok"
        if success:
            logger.info("Consent accepted ✅")
        else:
            logger.warning(f"Consent acceptance failed: {result}")

        return ChallengeResult(
            success=success,
            challenge_type=ChallengeType.CONSENT,
            message="Consent accepted" if success else f"Consent failed: {result}",
            raw_response=result,
        )

    # ─── Helpers ─────────────────────────────────────────────

    def _build_headers(self, csrf_token: str, user_agent: str = "") -> dict:
        """Build request headers for challenge endpoints."""
        ua = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/142.0.0.0 Safari/537.36"
        )
        return {
            "user-agent": ua,
            "x-csrftoken": csrf_token,
            "x-requested-with": "XMLHttpRequest",
            "x-ig-app-id": "936619743392459",
            "referer": "https://www.instagram.com/",
            "origin": "https://www.instagram.com",
            "content-type": "application/x-www-form-urlencoded",
            "accept": "*/*",
        }

    @staticmethod
    def _normalize_url(challenge_url: str) -> str:
        """Ensure challenge URL is absolute."""
        if challenge_url.startswith("http"):
            return challenge_url
        if challenge_url.startswith("/"):
            return f"https://i.instagram.com/api/v1{challenge_url}"
        return f"https://i.instagram.com/api/v1/{challenge_url}"

    @staticmethod
    def _parse_challenge_html(html: str) -> Dict[str, Any]:
        """Extract challenge data from HTML response (fallback)."""
        data: Dict[str, Any] = {}

        # Try to find step_name
        step_match = re.search(r'"step_name"\s*:\s*"([^"]+)"', html)
        if step_match:
            data["step_name"] = step_match.group(1)

        # Try to find contact_point
        contact_match = re.search(r'"contact_point"\s*:\s*"([^"]+)"', html)
        if contact_match:
            data.setdefault("step_data", {})["contact_point"] = contact_match.group(1)

        # Try to find challenge_context
        ctx_match = re.search(r'"challenge_context"\s*:\s*"([^"]+)"', html)
        if ctx_match:
            data["challenge_context"] = ctx_match.group(1)

        return data
