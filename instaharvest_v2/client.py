"""
HTTP Client
===========
Powerful HTTP engine based on curl_cffi.
All requests are sent through this module.
Browser impersonation, proxy rotation, auto-retry, response validation.
"""

import time
import json
import re
import logging
from typing import Any, Dict, Optional

from curl_cffi import requests as curl_requests

from .response_handler import ResponseHandler
from .challenge import ChallengeHandler
from .retry import RetryConfig
from .events import EventType
from .anti_detect import AntiDetect
from .proxy_manager import ProxyManager
from .rate_limiter import RateLimiter
from .session_manager import SessionManager, SessionInfo
from .log_config import get_debug_logger
from .config import (
    API_BASE,
    BASE_URL,
    IG_APP_ID,
    MAX_RETRIES,
    RETRY_BACKOFF_FACTOR,
    RETRY_STATUS_CODES,
    REQUEST_TIMEOUT,
    CONNECT_TIMEOUT,
    SEC_CH_UA_VARIANTS,
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
from .smart_rotation import SmartRotationCoordinator, RotationContext, _mask_proxy

logger = logging.getLogger("instaharvest_v2")


class HttpClient:
    """
    HTTP client for Instagram API.

    All API modules send requests through this client.
    curl_cffi browser impersonation + proxy rotation + retry logic.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        proxy_manager: ProxyManager,
        anti_detect: AntiDetect,
        rate_limiter: RateLimiter,
        challenge_handler: Optional[ChallengeHandler] = None,
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
        self._curl_session: Optional[curl_requests.Session] = None
        self._is_refreshing = False  # Guard against infinite recursion in challenge/refresh

        # Smart rotation coordinator
        self._rotation = SmartRotationCoordinator(anti_detect, proxy_manager)

    def _get_curl_session(self) -> curl_requests.Session:
        """Get or create curl_cffi session with Chrome 142 TLS."""
        if self._curl_session is None:
            # chrome142 — Chrome 145 ga eng yaqin TLS fingerprint
            self._curl_session = curl_requests.Session(
                impersonate="chrome142"
            )
            self._curl_session.max_redirects = 5
        return self._curl_session

    def _rotate_curl_session(self) -> curl_requests.Session:
        """Create a new session with Chrome 142 TLS impersonation."""
        if self._curl_session:
            try:
                self._curl_session.close()
            except Exception:
                pass
        self._curl_session = curl_requests.Session(
            impersonate="chrome142"
        )
        return self._curl_session

    def get(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        rate_category: str = "get_default",
        session: Optional[SessionInfo] = None,
        full_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send GET request.

        Args:
            endpoint: API endpoint (e.g., "/users/web_profile_info/")
            params: Query parameters
            rate_category: Rate limiting category
            session: Specific session to use (otherwise automatic)
            full_url: Full URL (instead of endpoint)

        Returns:
            JSON response (dict)
        """
        url = full_url or f"{API_BASE}{endpoint}"
        return self._request("GET", url, params=params, rate_category=rate_category, session=session)

    def post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        rate_category: str = "post_default",
        session: Optional[SessionInfo] = None,
        full_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send POST request.

        Args:
            endpoint: API endpoint
            data: POST body data
            params: Query parameters
            rate_category: Rate limiting category
            session: Specific session
            full_url: Full URL

        Returns:
            JSON response (dict)
        """
        url = full_url or f"{API_BASE}{endpoint}"
        return self._request("POST", url, data=data, params=params, rate_category=rate_category, session=session)

    def upload_raw(
        self,
        url: str,
        data: bytes,
        headers: Dict[str, str],
        rate_category: str = "post_default",
        session: Optional[SessionInfo] = None,
    ) -> Dict[str, Any]:
        """
        Raw binary upload (for photo/video uploads).

        Args:
            url: Full URL (/rupload_igphoto/ or /rupload_igvideo/)
            data: Raw bytes (image or video)
            headers: Upload-specific headers
            rate_category: Rate limiting category
            session: Session

        Returns:
            JSON response (with upload_id)
        """
        return self._request(
            "POST", url,
            raw_data=data,
            raw_headers=headers,
            rate_category=rate_category,
            session=session,
        )

    def _update_session_cookies(self, response, session: "SessionInfo") -> None:
        """
        Update cookies and headers from response.
        Delegates to SessionManager.update_from_response().

        Reactive approach:
        - csrftoken   → after every POST
        - rur         → on every response
        - sessionid   → rarely rotated
        - x-ig-www-claim → updated when server provides it
        + Auto-save trigger
        """
        self._session_mgr.update_from_response(session, response)


    def _request(
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
        Base request method.
        Retry logic, proxy rotation, error handling.
        """
        # Rate limiting
        self._rate_limiter.check(rate_category)

        # Get session
        sess = session or self._session_mgr.get_session()
        if not sess:
            raise LoginRequired("No active session found. Check your .env file.")

        last_exception = None
        _login_redirect_count = 0  # Per-request counter to prevent infinite 302 loops

        for attempt in range(self._retry.max_retries + 1):
            proxy_url = None
            start_time = time.time()

            try:
                # Human-like delay
                if attempt == 0:
                    self._anti_detect.human_delay("default")
                else:
                    self._anti_detect.human_delay("after_error")

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
                    # Raw upload — minimal headers
                    headers = {
                        "user-agent": sess.user_agent or self._anti_detect.get_identity().user_agent,
                        "cookie": sess.cookie_string,
                        "x-csrftoken": sess.csrf_token,
                        "x-ig-app-id": IG_APP_ID,
                        "referer": "https://www.instagram.com/",
                        "origin": "https://www.instagram.com",
                    }
                    headers.update(raw_headers)
                elif sess.user_agent:
                    # Dynamic Chrome headers from config (auto-rotates)
                    import random as _rnd
                    _sec_ch_ua = _rnd.choice(SEC_CH_UA_VARIANTS)
                    # Extract version for full-version-list
                    import re as _re
                    _ver_match = _re.search(r'Chrome";v="(\d+)', _sec_ch_ua)
                    _chrome_ver = _ver_match.group(1) if _ver_match else "142"
                    headers = {
                        ":authority": "www.instagram.com",
                        ":method": method,
                        ":path": url.replace("https://www.instagram.com", ""),
                        ":scheme": "https",
                        "accept": "*/*",
                        "accept-encoding": "gzip, deflate, br, zstd",
                        "accept-language": "en-US,en;q=0.9",
                        "cache-control": "no-cache",
                        "content-type": "application/x-www-form-urlencoded",
                        "cookie": sess.cookie_string,
                        "origin": "https://www.instagram.com",
                        "pragma": "no-cache",
                        "priority": "u=1, i",
                        "referer": "https://www.instagram.com/",
                        "sec-ch-prefers-color-scheme": "dark",
                        "sec-ch-ua": _sec_ch_ua,
                        "sec-ch-ua-full-version-list": f'"Not A(Brand";v="99.0.0.0", "Google Chrome";v="{_chrome_ver}.0.7632.110", "Chromium";v="{_chrome_ver}.0.7632.110"',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-model": '""',
                        "sec-ch-ua-platform": '"Windows"',
                        "sec-ch-ua-platform-version": '"19.0.0"',
                        "sec-fetch-dest": "empty",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-site": "same-origin",
                        "user-agent": sess.user_agent,
                        "x-asbd-id": "359341",
                        "x-csrftoken": sess.csrf_token,
                        "x-ig-app-id": IG_APP_ID,
                        "x-ig-www-claim": sess.ig_www_claim or "0",
                        "x-instagram-ajax": sess.x_instagram_ajax or "",
                        "x-requested-with": "XMLHttpRequest",
                    }
                else:
                    # Anonymous or no user_agent — use anti_detect
                    if method == "POST":
                        headers = self._anti_detect.get_post_headers(sess.csrf_token)
                    else:
                        headers = self._anti_detect.get_request_headers(sess.csrf_token)

                    identity = self._anti_detect.get_identity()
                    headers["user-agent"] = identity.user_agent
                    headers["sec-ch-ua"] = identity.sec_ch_ua
                    headers["sec-ch-ua-mobile"] = identity.sec_ch_ua_mobile
                    headers["sec-ch-ua-platform"] = identity.sec_ch_ua_platform
                    if sess.ig_www_claim:
                        headers["x-ig-www-claim"] = sess.ig_www_claim
                    if sess.x_instagram_ajax:
                        headers["x-instagram-ajax"] = sess.x_instagram_ajax
                    headers.setdefault("x-asbd-id", "359341")
                    headers.setdefault("sec-fetch-dest", "empty")
                    headers.setdefault("sec-fetch-mode", "cors")
                    headers.setdefault("sec-fetch-site", "same-origin")
                    headers["cookie"] = sess.cookie_string

                # Proxy
                proxy_dict = self._proxy_mgr.get_curl_proxy()
                if proxy_dict:
                    proxy_url = list(proxy_dict.values())[0]

                # curl_cffi session
                curl_sess = self._get_curl_session()

                # Send request
                kwargs = {
                    "url": url,
                    "headers": headers,
                    "timeout": (CONNECT_TIMEOUT, REQUEST_TIMEOUT),
                    "allow_redirects": False,  # We handle redirects ourselves
                    "verify": not bool(proxy_dict),  # Only disable SSL when using proxy
                }

                if proxy_dict:
                    kwargs["proxies"] = proxy_dict
                if params:
                    kwargs["params"] = params
                if raw_data and method == "POST":
                    kwargs["data"] = raw_data  # binary bytes
                elif data and method == "POST":
                    kwargs["data"] = data

                if method == "GET":
                    response = curl_sess.get(**kwargs)
                else:
                    response = curl_sess.post(**kwargs)

                elapsed = time.time() - start_time

                # Record proxy success
                if proxy_url:
                    self._proxy_mgr.report_success(proxy_url, elapsed)

                # Capture response cookies to keep session alive
                self._update_session_cookies(response, sess)

                # Debug: log response
                dbg = get_debug_logger()
                dbg.response(
                    status_code=response.status_code,
                    elapsed_ms=elapsed * 1000,
                    size_bytes=len(response.content) if hasattr(response, 'content') else 0,
                    url=url,
                )

                # ─── Intercept 3xx redirects ───────────────────────
                if 300 <= response.status_code < 400:
                    location = response.headers.get("location", "")
                    is_login_redirect = (
                        "/accounts/login" in location
                        or location.endswith("/#")
                        or location == "https://www.instagram.com/#"
                    )

                    if is_login_redirect:
                        # ── SESSION AUTO-REFRESH ──────────────────────────
                        # Try to refresh session INLINE before failing.
                        # 3-step cascade: one_tap → reload_from_file → callback → fail
                        _login_redirect_count += 1
                        if _login_redirect_count <= 2 and not self._is_refreshing:
                            self._is_refreshing = True
                            refreshed = False
                            try:
                                # Step 1: one_tap_web_login (best — no password needed)
                                logger.info(
                                    f"🔄 [Session Refresh] 302 detected for {url[:50]}. "
                                    f"Trying one_tap_web_login..."
                                )
                                refreshed = self._session_mgr.refresh_via_one_tap(sess)

                                if not refreshed:
                                    # Step 2: reload from file (external update)
                                    logger.info("🔄 [Session Refresh] one_tap failed, trying file reload...")
                                    refreshed = self._session_mgr.reload_from_file(sess)

                                if not refreshed and self._session_refresh_callback:
                                    # Step 3: full re-login (last resort)
                                    logger.info("🔄 [Session Refresh] File reload failed, trying re-login...")
                                    refreshed = self._session_refresh_callback()
                            except Exception as refresh_err:
                                logger.warning(f"🔄 [Session Refresh] Error: {refresh_err}")
                            finally:
                                self._is_refreshing = False

                            if refreshed:
                                logger.info("✅ [Session Refresh] Success! Retrying request...")
                                continue  # Retry the same request with refreshed session

                        # All refresh attempts failed — raise/return error
                        logger.warning(
                            f"[302] {method} → login redirect: {location[:60]}. "
                            f"Session expired — all refresh attempts failed."
                        )
                        dbg = get_debug_logger()
                        dbg.redirect(url, location, is_login_redirect=True)
                        dbg.session_info(
                            ds_user_id=sess.ds_user_id,
                            csrf_token=sess.csrf_token,
                            session_id=sess.session_id,
                        )
                        if method == "POST":
                            return {"status": "fail", "reason": "session_expired"}
                        else:
                            raise LoginRequired(
                                f"Session expired (302 → {location[:60]}). "
                                "All refresh attempts failed. Re-login needed."
                            )

                    elif method == "POST":
                        # Normal POST redirect (like/unlike/comment success)
                        try:
                            return response.json()
                        except Exception:
                            return {"status": "ok", "redirected": True}
                    else:
                        # Normal GET redirect — retry
                        logger.warning(f"GET redirect to {location[:60]} — retrying")
                        continue

                # Handle response
                result = self._response_handler.handle(response, sess)

                # Success — record session and anti-detect
                self._session_mgr.report_success(sess)
                self._rotation.on_request_success(ctx, response.status_code, elapsed * 1000)

                return result

            except ChallengeRequired as e:
                # Rich structured log via coordinator
                action = self._rotation.on_request_error(
                    ctx, e, status_code=getattr(e, 'status_code', 0),
                    rotate_identity=True, rotate_tls=True,
                )
                # Try auto-resolve if handler is configured (with recursion guard)
                if self._challenge_handler and self._challenge_handler.is_enabled and not self._is_refreshing:
                    self._is_refreshing = True
                    try:
                        sess = self._session_mgr.get_session()
                        result = self._challenge_handler.resolve(
                            session=self._get_curl_session(),
                            challenge_url=e.challenge_url or str(e),
                            csrf_token=sess.csrf_token if sess else "",
                            user_agent=sess.user_agent if sess else "",
                        )
                        if result.success:
                            logger.info("✅ Challenge resolved — retrying request")
                            return self._request(
                                method=method, url=url,
                                params=params, data=data,
                                rate_category=rate_category, session=session,
                                raw_data=raw_data, raw_headers=raw_headers,
                            )
                    finally:
                        self._is_refreshing = False

                # Not resolved — rotate TLS and raise
                self._rotate_curl_session()
                raise

            except CheckpointRequired as e:
                self._rotation.on_request_error(
                    ctx, e, status_code=getattr(e, 'status_code', 0),
                    rotate_identity=True, rotate_tls=True,
                )
                self._rotate_curl_session()
                raise

            except LoginRequired as e:
                self._rotation.on_request_error(
                    ctx, e, status_code=getattr(e, 'status_code', 0),
                    rotate_identity=True,
                )
                # ── SESSION AUTO-REFRESH (3-step cascade) ────────
                if not self._is_refreshing:
                    self._is_refreshing = True
                    refreshed = False
                    try:
                        # Step 1: one_tap_web_login
                        if sess and hasattr(self._session_mgr, 'refresh_via_one_tap'):
                            logger.info("🔑 [LoginRequired] Trying one_tap refresh...")
                            refreshed = self._session_mgr.refresh_via_one_tap(sess)

                        # Step 2: reload from file
                        if not refreshed and sess and hasattr(self._session_mgr, 'reload_from_file'):
                            logger.info("🔑 [LoginRequired] Trying file reload...")
                            refreshed = self._session_mgr.reload_from_file(sess)

                        # Step 3: full re-login callback
                        if not refreshed and self._session_refresh_callback:
                            logger.info("🔑 [LoginRequired] Trying re-login callback...")
                            refreshed = self._session_refresh_callback()

                        if refreshed:
                            logger.info("✅ Session refreshed — retrying request")
                            self._is_refreshing = False
                            return self._request(
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
                # Valid response — no rotation
                self._rotation.on_request_error(ctx, e, rotate_proxy=False, rotate_identity=False)
                raise

            except (ConsentRequired, InstagramError) as e:
                self._rotation.on_request_error(
                    ctx, e, status_code=getattr(e, 'status_code', 0),
                    rotate_identity=True, rotate_tls=True,
                )
                self._rotate_curl_session()
                raise

            except RateLimitError as e:
                last_exception = e
                self._rotation.on_request_error(
                    ctx, e, status_code=429,
                    rotate_proxy=True, rotate_identity=True, rotate_tls=True,
                    pause_seconds=30,
                )
                if self._events:
                    self._events.emit(EventType.RATE_LIMIT, endpoint=url, attempt=attempt, error=e)
                self._rate_limiter.pause(30)
                self._anti_detect.human_delay("after_rate_limit")
                self._rotate_curl_session()

            except NetworkError as e:
                last_exception = e
                self._rotation.on_request_error(
                    ctx, e, rotate_proxy=True, rotate_tls=True,
                )
                if self._events:
                    self._events.emit(EventType.NETWORK_ERROR, endpoint=url, attempt=attempt, error=e)
                self._rotate_curl_session()

            except Exception as e:
                err_str = str(e).lower()
                if "redirect" in err_str or "(47)" in err_str:
                    logger.warning(
                        f"🔄 REDIRECT LOOP │ {method} {url[:50]} │ "
                        f"proxy={_mask_proxy(proxy_url)} │ "
                        f"action=ROTATE_TLS │ retrying..."
                    )
                    self._rotate_curl_session()
                    last_exception = LoginRequired("Session redirect loop — new cookie needed", status_code=302)
                    continue
                last_exception = e
                self._rotation.on_request_error(
                    ctx, e, rotate_proxy=True, rotate_identity=True, rotate_tls=True,
                )
                self._rotate_curl_session()

            # Only retry if the exception is retryable
            if last_exception and not self._retry.should_retry(last_exception):
                raise last_exception

            # Exponential backoff with jitter
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
                    self._events.emit(EventType.RETRY, endpoint=url, attempt=attempt + 1, extra={"backoff": backoff})
                time.sleep(backoff)

        # All attempts exhausted
        raise last_exception or NetworkError("All attempts failed")

    # _handle_response delegated to ResponseHandler (response_handler.py)

    def get_session(self) -> Optional[SessionInfo]:
        """Get current active session (public API for submodules)."""
        return self._session_mgr.get_session()

    def get_jazoest(self) -> str:
        """Get jazoest CSRF token from current session."""
        session = self._session_mgr.get_session()
        if session:
            return session.jazoest
        return ""

    def close(self) -> None:
        """Clean up resources."""
        if self._curl_session:
            try:
                self._curl_session.close()
            except Exception:
                pass
            self._curl_session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
