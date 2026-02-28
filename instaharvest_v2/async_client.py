"""
Async HTTP Client v2
====================
Async HTTP client with speed mode integration.
Uses global semaphore + token bucket for optimal throughput.
"""

import asyncio
import time
import json
import logging
from typing import Any, Dict, Optional

from curl_cffi.requests import AsyncSession

from .response_handler import ResponseHandler
from .async_challenge import AsyncChallengeHandler
from .retry import RetryConfig

from .session_manager import SessionManager, SessionInfo
from .log_config import get_debug_logger
from .proxy_manager import ProxyManager
from .anti_detect import AntiDetect
from .async_rate_limiter import AsyncRateLimiter
from .config import (
    API_BASE,
    IG_APP_ID,
    MAX_RETRIES,
    RETRY_BACKOFF_FACTOR,
    CONNECT_TIMEOUT,
    REQUEST_TIMEOUT,
)
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
# (AsyncChallengeHandler already imported above)
from .smart_rotation import SmartRotationCoordinator, RotationContext, _mask_proxy

logger = logging.getLogger("instaharvest_v2.async")


class AsyncHttpClient:
    """
    Async HTTP client for Instagram API.

    Features:
    - Speed mode integration (SAFE/FAST/TURBO)
    - Global semaphore concurrency control
    - Token bucket rate limiting
    - Adaptive delays with escalation
    - Browser impersonation via curl_cffi
    - Proxy rotation with health tracking
    """

    def __init__(
        self,
        session_manager: SessionManager,
        proxy_manager: ProxyManager,
        anti_detect: AntiDetect,
        rate_limiter: AsyncRateLimiter,
        challenge_handler: Optional[AsyncChallengeHandler] = None,
        session_refresh_callback=None,
        retry_config: Optional[RetryConfig] = None,
        event_emitter=None,
    ):
        self._session_mgr = session_manager
        self._proxy_mgr = proxy_manager
        self._anti_detect = anti_detect
        self._rate_limiter = rate_limiter
        self._response_handler = ResponseHandler(session_manager)
        self._challenge_handler = challenge_handler
        self._session_refresh_callback = session_refresh_callback
        self._retry = retry_config or RetryConfig()
        self._events = event_emitter
        self._async_session: Optional[AsyncSession] = None
        self._is_refreshing = False  # Guard against infinite recursion in challenge/refresh

        # Smart rotation coordinator
        self._rotation = SmartRotationCoordinator(anti_detect, proxy_manager)

    def _get_async_session(self) -> AsyncSession:
        """Get or create curl_cffi AsyncSession."""
        if self._async_session is None:
            identity = self._anti_detect.get_identity()
            self._async_session = AsyncSession(impersonate=identity.impersonation)
        return self._async_session

    async def _rotate_async_session(self) -> None:
        """Create a new async session (new TLS fingerprint)."""
        if self._async_session:
            try:
                await self._async_session.close()
            except Exception:
                pass
        identity = self._anti_detect.get_identity()
        self._async_session = AsyncSession(impersonate=identity.impersonation)

    # ─── PUBLIC API ──────────────────────────────────────────

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        rate_category: str = "get_default",
        session: Optional[SessionInfo] = None,
        full_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send async GET request."""
        url = full_url or f"{API_BASE}{endpoint}"
        return await self._request(
            "GET", url,
            params=params,
            rate_category=rate_category,
            session=session,
        )

    async def post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        rate_category: str = "post_default",
        session: Optional[SessionInfo] = None,
        full_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send async POST request."""
        url = full_url or f"{API_BASE}{endpoint}"
        return await self._request(
            "POST", url,
            params=params,
            data=data,
            rate_category=rate_category,
            session=session,
        )

    async def upload_raw(
        self,
        url: str,
        data: bytes,
        headers: Dict[str, str],
        rate_category: str = "post_default",
        session: Optional[SessionInfo] = None,
    ) -> Dict[str, Any]:
        """Async raw binary upload (for photo/video uploads)."""
        return await self._request(
            "POST", url,
            rate_category=rate_category,
            session=session,
            raw_data=data,
            raw_headers=headers,
        )

    # ─── CORE REQUEST ENGINE ─────────────────────────────────

    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        rate_category: str = "get_default",
        session: Optional[SessionInfo] = None,
        raw_data: Optional[bytes] = None,
        raw_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Base async request method.
        Uses acquire/release pattern for rate limiting.
        """
        # Step 1: Rate limiter — semaphore + token + delay
        await self._rate_limiter.acquire(rate_category)

        # Get session
        sess = session or self._session_mgr.get_session()
        if not sess:
            self._rate_limiter.release()
            raise LoginRequired("No active session found. Check your .env file.")

        last_exception = None

        try:
            for attempt in range(self._retry.max_retries + 1):
                proxy_url = None
                start_time = time.time()

                try:
                    # Anti-detect delay only on retries (first request uses rate limiter delay)
                    if attempt > 0:
                        backoff_delay = self._anti_detect.get_delay("after_error")
                        if backoff_delay > 0:
                            await asyncio.sleep(backoff_delay)

                    # Debug: log outgoing request
                    dbg = get_debug_logger()
                    dbg.request(
                        method=method,
                        url=url,
                        params=params,
                        session_id=sess.session_id,
                        proxy=proxy_url or "direct",
                        attempt=attempt + 1,
                        max_attempts=self._retry.max_retries + 1,
                        has_data=bool(data or raw_data),
                    )

                    # Rotation context for this attempt
                    ctx = self._rotation.on_request_start(
                        method=method, endpoint=url,
                        attempt=attempt + 1,
                        max_attempts=self._retry.max_retries + 1,
                        proxy_url=proxy_url,
                    )

                    # Headers
                    if raw_data and raw_headers:
                        headers = {
                            "user-agent": sess.user_agent or self._anti_detect.get_identity().user_agent,
                            "cookie": sess.cookie_string,
                            "x-csrftoken": sess.csrf_token,
                            "x-ig-app-id": IG_APP_ID,
                            "referer": "https://www.instagram.com/",
                            "origin": "https://www.instagram.com",
                        }
                        headers.update(raw_headers)
                    elif method == "POST":
                        headers = self._anti_detect.get_post_headers(sess.csrf_token)
                    else:
                        headers = self._anti_detect.get_request_headers(sess.csrf_token)

                    # Session headers for non-raw requests
                    if not (raw_data and raw_headers):
                        if sess.user_agent:
                            headers["user-agent"] = sess.user_agent
                            for key in list(headers.keys()):
                                if key.startswith("sec-ch-"):
                                    del headers[key]
                        if sess.ig_www_claim:
                            headers["x-ig-www-claim"] = sess.ig_www_claim
                        headers.setdefault("x-asbd-id", "359341")
                        headers["cookie"] = sess.cookie_string

                    # Proxy
                    proxy_dict = self._proxy_mgr.get_curl_proxy()
                    if proxy_dict:
                        proxy_url = list(proxy_dict.values())[0]

                    # curl_cffi async session
                    curl_sess = self._get_async_session()

                    # Build request kwargs
                    kwargs = {
                        "url": url,
                        "headers": headers,
                        "timeout": (CONNECT_TIMEOUT, REQUEST_TIMEOUT),
                        "allow_redirects": method == "GET",
                        "verify": not bool(proxy_dict),  # Only disable SSL when using proxy
                    }

                    if proxy_dict:
                        kwargs["proxies"] = proxy_dict
                    if params:
                        kwargs["params"] = params
                    if raw_data and method == "POST":
                        kwargs["data"] = raw_data
                    elif data and method == "POST":
                        kwargs["data"] = data

                    # async request
                    if method == "GET":
                        response = await curl_sess.get(**kwargs)
                    else:
                        response = await curl_sess.post(**kwargs)

                    elapsed = time.time() - start_time

                    # Record proxy success
                    if proxy_url:
                        self._proxy_mgr.report_success(proxy_url, elapsed)

                    # Update session cookies from response
                    self._session_mgr.update_from_response(sess, response)

                    # Handle response (sync — pure parsing, no I/O)
                    result = self._response_handler.handle(response, sess)

                    # Debug: log response
                    dbg = get_debug_logger()
                    dbg.response(
                        status_code=response.status_code,
                        elapsed_ms=elapsed * 1000,
                        size_bytes=len(response.content) if hasattr(response, 'content') else 0,
                        url=url,
                    )

                    # Success
                    self._session_mgr.report_success(sess)
                    self._rotation.on_request_success(ctx, response.status_code, elapsed * 1000)
                    self._rate_limiter.on_success()

                    return result

                except ChallengeRequired as e:
                    # Rich structured log via coordinator
                    self._rotation.on_request_error(
                        ctx, e, status_code=getattr(e, 'status_code', 0),
                        rotate_identity=True, rotate_tls=True,
                    )
                    # Try auto-resolve if handler configured (with recursion guard)
                    if self._challenge_handler and self._challenge_handler.is_enabled and not self._is_refreshing:
                        self._is_refreshing = True
                        try:
                            sess = self._session_mgr.get_session()
                            result = await self._challenge_handler.resolve(
                                session=self._get_async_session(),
                                challenge_url=e.challenge_url or str(e),
                                csrf_token=sess.csrf_token if sess else "",
                                user_agent=sess.user_agent if sess else "",
                            )
                            if result.success:
                                logger.info("✅ Challenge resolved — retrying request")
                                return await self._request(
                                    method=method, url=url,
                                    params=params, data=data,
                                    rate_category=rate_category, session=session,
                                    raw_data=raw_data, raw_headers=raw_headers,
                                )
                        finally:
                            self._is_refreshing = False

                    # Not resolved
                    self._rate_limiter.on_error("challenge")
                    await self._rotate_async_session()
                    raise

                except CheckpointRequired as e:
                    self._rotation.on_request_error(
                        ctx, e, status_code=getattr(e, 'status_code', 0),
                        rotate_identity=True, rotate_tls=True,
                    )
                    self._rate_limiter.on_error("checkpoint")
                    await self._rotate_async_session()
                    raise

                except LoginRequired as e:
                    self._rotation.on_request_error(
                        ctx, e, status_code=getattr(e, 'status_code', 0),
                        rotate_identity=True,
                    )
                    # Try auto-refresh if callback available (with recursion guard)
                    if self._session_refresh_callback and not self._is_refreshing:
                        self._is_refreshing = True
                        try:
                            import inspect
                            if inspect.iscoroutinefunction(self._session_refresh_callback):
                                refreshed = await self._session_refresh_callback()
                            else:
                                refreshed = self._session_refresh_callback()
                            if refreshed:
                                logger.info("🔑 Session refreshed — retrying request")
                                return await self._request(
                                    method=method, url=url,
                                    params=params, data=data,
                                    rate_category=rate_category, session=session,
                                    raw_data=raw_data, raw_headers=raw_headers,
                                )
                        except Exception as refresh_err:
                            logger.warning(f"🔑 Session refresh failed: {refresh_err}")
                        finally:
                            self._is_refreshing = False
                    raise

                except (NotFoundError, PrivateAccountError) as e:
                    self._rotation.on_request_error(ctx, e, rotate_proxy=False, rotate_identity=False)
                    raise

                except (ConsentRequired, InstagramError) as e:
                    self._rotation.on_request_error(
                        ctx, e, status_code=getattr(e, 'status_code', 0),
                        rotate_identity=True, rotate_tls=True,
                    )
                    self._rate_limiter.on_error("instagram")
                    await self._rotate_async_session()
                    raise

                except RateLimitError as e:
                    last_exception = e
                    self._rotation.on_request_error(
                        ctx, e, status_code=429,
                        rotate_proxy=True, rotate_identity=True, rotate_tls=True,
                        pause_seconds=30,
                    )
                    self._rate_limiter.on_error("rate_limit")
                    self._rate_limiter.pause(30)
                    await asyncio.sleep(self._anti_detect.get_delay("after_rate_limit"))
                    await self._rotate_async_session()

                except NetworkError as e:
                    last_exception = e
                    self._rotation.on_request_error(
                        ctx, e, rotate_proxy=True, rotate_tls=True,
                    )
                    self._rate_limiter.on_error("network")
                    await self._rotate_async_session()

                except Exception as e:
                    err_str = str(e).lower()
                    if "redirect" in err_str or "(47)" in err_str:
                        logger.warning(
                            f"🔄 REDIRECT LOOP │ {method} {url[:50]} │ "
                            f"proxy={_mask_proxy(proxy_url)} │ "
                            f"action=ROTATE_TLS"
                        )
                        self._session_mgr.report_error(sess, is_login_error=True)
                        raise LoginRequired("Session redirect loop — new cookie needed", status_code=302)
                    last_exception = e
                    self._rotation.on_request_error(
                        ctx, e, rotate_proxy=True, rotate_identity=True, rotate_tls=True,
                    )
                    self._rate_limiter.on_error("unknown")
                    await self._rotate_async_session()

                # Only retry if the exception is retryable
                if last_exception and not self._retry.should_retry(last_exception):
                    raise last_exception

                # Exponential backoff (async) — using RetryConfig
                if attempt < self._retry.max_retries:
                    backoff = self._retry.calculate_delay(attempt)
                    logger.debug(f"Backoff: {backoff:.1f}s (attempt {attempt + 1})")
                    # Debug: log retry
                    dbg = get_debug_logger()
                    dbg.retry(
                        attempt=attempt + 1,
                        max_attempts=self._retry.max_retries + 1,
                        backoff_seconds=backoff,
                        reason=type(last_exception).__name__ if last_exception else "unknown",
                        endpoint=url,
                    )
                    if self._events:
                        from .events import EventType
                        self._events.emit(EventType.RETRY, endpoint=url, attempt=attempt + 1, extra={"backoff": backoff})
                    await asyncio.sleep(backoff)

            raise last_exception or NetworkError("All attempts failed")

        finally:
            # Always release semaphore
            self._rate_limiter.release()

    # _handle_response delegated to ResponseHandler (response_handler.py)

    # ─── PUBLIC ACCESSORS ────────────────────────────────────

    def get_session(self) -> Optional[SessionInfo]:
        """Get current active session."""
        return self._session_mgr.get_session()

    def get_jazoest(self) -> str:
        """Get jazoest CSRF token from current session."""
        session = self._session_mgr.get_session()
        if session:
            return session.jazoest
        return ""

    @property
    def rate_limiter(self) -> AsyncRateLimiter:
        """Access rate limiter for stats and configuration."""
        return self._rate_limiter

    async def close(self) -> None:
        """Clean up async resources."""
        if self._async_session:
            try:
                await self._async_session.close()
            except Exception:
                pass
            self._async_session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False
