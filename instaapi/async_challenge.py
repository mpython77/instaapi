"""
Async Challenge Handler
========================
Async version of challenge.py for AsyncHttpClient.
Same logic as sync version but with async/await.
"""

import re
import logging
from typing import Any, Awaitable, Callable, Dict, Optional, Union

from .challenge import (
    ChallengeType,
    ChallengeContext,
    ChallengeResult,
)

logger = logging.getLogger("instaapi.challenge")


class AsyncChallengeHandler:
    """
    Async version of ChallengeHandler.
    
    Supports both sync and async callbacks:
        - sync:  lambda ctx: input(f"Code: ")
        - async: async def get_code(ctx): return await ...
    """

    def __init__(
        self,
        code_callback: Optional[
            Union[
                Callable[[ChallengeContext], str],
                Callable[[ChallengeContext], Awaitable[str]],
            ]
        ] = None,
        preferred_method: ChallengeType = ChallengeType.EMAIL,
    ):
        self._code_callback = code_callback
        self._preferred_method = preferred_method

    @property
    def is_enabled(self) -> bool:
        return self._code_callback is not None

    async def _get_code(self, ctx: ChallengeContext) -> str:
        """Call callback, handling both sync and async."""
        import asyncio
        import inspect

        if inspect.iscoroutinefunction(self._code_callback):
            return await self._code_callback(ctx)
        else:
            # Run sync callback in executor to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._code_callback, ctx)

    async def resolve(
        self,
        session,
        challenge_url: str,
        csrf_token: str,
        user_agent: str = "",
    ) -> ChallengeResult:
        """
        Resolve an Instagram challenge (async).

        Args:
            session: aiohttp/curl_cffi async session
            challenge_url: Challenge URL
            csrf_token: CSRF token
            user_agent: User-Agent

        Returns:
            ChallengeResult
        """
        if not self._code_callback:
            return ChallengeResult(
                success=False,
                message="No challenge callback provided.",
            )

        headers = self._build_headers(csrf_token, user_agent)
        full_url = self._normalize_url(challenge_url)

        try:
            # Step 1: GET challenge info
            info = await self._get_challenge_info(session, full_url, headers)
            challenge_type = self._detect_type(info)

            logger.info(f"Challenge detected: type={challenge_type.value}")

            # Step 2: Handle by type
            if challenge_type == ChallengeType.CONSENT:
                return await self._handle_consent(session, full_url, headers, info)

            if challenge_type in (ChallengeType.EMAIL, ChallengeType.SMS, ChallengeType.PHONE):
                return await self._handle_verification(
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

    async def _get_challenge_info(self, session, url, headers) -> Dict[str, Any]:
        resp = await session.get(url, headers=headers, timeout=15)
        try:
            return resp.json()
        except Exception:
            return self._parse_challenge_html(resp.text)

    async def _select_method(self, session, url, headers, method) -> Dict[str, Any]:
        choice = 1 if method == ChallengeType.EMAIL else 0
        resp = await session.post(
            url, headers=headers,
            data={"choice": str(choice)},
            timeout=15,
        )
        try:
            return resp.json()
        except Exception:
            return {"status": "fail", "raw": resp.text[:500]}

    async def _submit_code(self, session, url, headers, code) -> Dict[str, Any]:
        resp = await session.post(
            url, headers=headers,
            data={"security_code": code},
            timeout=15,
        )
        try:
            return resp.json()
        except Exception:
            return {"status": "fail", "raw": resp.text[:500]}

    async def _handle_verification(
        self, session, url, headers, info, challenge_type,
    ) -> ChallengeResult:
        step_name = info.get("step_name", "")
        step_data = info.get("step_data", {})

        contact_point = (
            step_data.get("contact_point", "")
            or step_data.get("email", "")
            or step_data.get("phone_number", "")
        )

        # Select method if needed
        if "select" in step_name.lower() or step_name == "select_verify_method":
            select_result = await self._select_method(session, url, headers, challenge_type)
            if select_result.get("status") == "fail":
                return ChallengeResult(
                    success=False,
                    challenge_type=challenge_type,
                    message=f"Method selection failed: {select_result}",
                    raw_response=select_result,
                )
            step_data = select_result.get("step_data", step_data)
            contact_point = (
                step_data.get("contact_point", contact_point)
                or step_data.get("email", "")
                or step_data.get("phone_number", "")
            )

        # Get code from user
        ctx = ChallengeContext(
            challenge_type=challenge_type,
            contact_point=contact_point,
            step_name=step_name,
            message=f"Instagram sent verification code to {contact_point}",
        )
        code = await self._get_code(ctx)

        if not code or not code.strip():
            return ChallengeResult(
                success=False,
                challenge_type=challenge_type,
                message="No code provided by user",
            )

        # Submit
        result = await self._submit_code(session, url, headers, code.strip())

        if result.get("status") == "ok" or result.get("logged_in_user"):
            logger.info("Challenge resolved successfully! ✅")
            return ChallengeResult(
                success=True,
                challenge_type=challenge_type,
                message="Challenge resolved",
                raw_response=result,
            )

        return ChallengeResult(
            success=False,
            challenge_type=challenge_type,
            message=f"Code verification failed: {result.get('message', 'Invalid code')}",
            raw_response=result,
        )

    async def _handle_consent(self, session, url, headers, info) -> ChallengeResult:
        logger.info("Handling consent challenge — auto-accepting")
        resp = await session.post(
            url, headers=headers, data={"choice": "0"}, timeout=15,
        )
        try:
            result = resp.json()
        except Exception:
            result = {"status": "fail"}

        success = result.get("status") == "ok"
        return ChallengeResult(
            success=success,
            challenge_type=ChallengeType.CONSENT,
            message="Consent accepted" if success else f"Consent failed: {result}",
            raw_response=result,
        )

    # ─── Helpers (reused from sync) ──────────────────────────

    def _build_headers(self, csrf_token: str, user_agent: str = "") -> dict:
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
        if challenge_url.startswith("http"):
            return challenge_url
        if challenge_url.startswith("/"):
            return f"https://i.instagram.com/api/v1{challenge_url}"
        return f"https://i.instagram.com/api/v1/{challenge_url}"

    @staticmethod
    def _detect_type(info: Dict[str, Any]) -> ChallengeType:
        """Same detection logic as sync handler."""
        step_name = info.get("step_name", "").lower()
        type_map = {
            "verify_email": ChallengeType.EMAIL,
            "email": ChallengeType.EMAIL,
            "verify_code": ChallengeType.EMAIL,
            "phone_number": ChallengeType.SMS,
            "verify_phone": ChallengeType.SMS,
            "sms": ChallengeType.SMS,
            "consent": ChallengeType.CONSENT,
            "accept": ChallengeType.CONSENT,
            "delta_login_review": ChallengeType.EMAIL,
            "captcha": ChallengeType.CAPTCHA,
        }
        for key, ctype in type_map.items():
            if key in step_name:
                return ctype

        step_data = info.get("step_data", {})
        if step_data.get("email"):
            return ChallengeType.EMAIL
        if step_data.get("phone_number"):
            return ChallengeType.SMS
        if step_data.get("contact_point"):
            return ChallengeType.EMAIL if "@" in step_data["contact_point"] else ChallengeType.SMS

        return ChallengeType.UNKNOWN

    @staticmethod
    def _parse_challenge_html(html: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        step_match = re.search(r'"step_name"\s*:\s*"([^"]+)"', html)
        if step_match:
            data["step_name"] = step_match.group(1)
        contact_match = re.search(r'"contact_point"\s*:\s*"([^"]+)"', html)
        if contact_match:
            data.setdefault("step_data", {})["contact_point"] = contact_match.group(1)
        return data
