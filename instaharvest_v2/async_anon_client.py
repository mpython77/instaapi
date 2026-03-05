"""
Async Anonymous Client
======================
True async HTTP client for public Instagram data without authentication.
Uses curl_cffi.AsyncSession for real non-blocking I/O.
Configurable strategy chain with automatic fallback.

Default strategy chain (profile):
    1. Web API — www.instagram.com/api/v1 (richest data)
    2. GraphQL Public — public query_hash queries
    3. Web HTML Parse — parse profile page for embedded JSON

Other strategies:
    - Embed Endpoint — /p/{shortcode}/embed/captioned/
    - Mobile API — i.instagram.com/api/v1
    - GraphQL doc_id — cookie-free POST queries

Concurrency control:
    - asyncio.Semaphore for global concurrency limit
    - unlimited=True: no limits (1000 concurrent by default)
    - unlimited=False: conservative limits (10 concurrent)
"""

import asyncio
import json
import logging
import random
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from curl_cffi.requests import AsyncSession

from .anti_detect import AntiDetect
from .proxy_manager import ProxyManager
from . import parsers as _parsers
from .strategy import (
    ProfileStrategy,
    PostsStrategy,
    DEFAULT_PROFILE_STRATEGIES,
    DEFAULT_POSTS_STRATEGIES,
    parse_profile_strategies,
    parse_posts_strategies,
)
from .config import (
    ANON_RATE_LIMITS,
    ANON_RATE_LIMITS_UNLIMITED,
    ANON_GRAPHQL_HASHES,
    ANON_REQUEST_DELAYS,
    ANON_REQUEST_DELAYS_UNLIMITED,
    EMBED_URL,
    MOBILE_API_BASE,
    IG_APP_ID,
    GRAPHQL_DOC_IDS,
    GRAPHQL_LSD_TOKEN,
    MAX_RETRIES,
)

logger = logging.getLogger("instaharvest_v2.async_anon")


class AsyncAnonRateLimiter:
    """Async per-strategy rate limiter for anonymous requests."""

    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._windows: Dict[str, List[float]] = {}
        self._limits = ANON_RATE_LIMITS if enabled else ANON_RATE_LIMITS_UNLIMITED
        self._lock = asyncio.Lock()

    async def wait_if_needed(self, strategy: str) -> None:
        """Wait until a request slot is available."""
        if not self._enabled:
            return

        config = self._limits.get(strategy, {"requests": 10, "window": 60})

        while True:
            async with self._lock:
                now = time.time()
                window = config["window"]
                max_requests = config["requests"]

                if strategy not in self._windows:
                    self._windows[strategy] = []

                # Clean old entries
                self._windows[strategy] = [
                    t for t in self._windows[strategy] if now - t < window
                ]

                if len(self._windows[strategy]) < max_requests:
                    self._windows[strategy].append(now)
                    return

            # Limit reached — wait and retry
            await asyncio.sleep(
                config["window"] / config["requests"] + random.uniform(0.1, 0.5)
            )


class AsyncStrategyFailed(Exception):
    """Raised when a single strategy fails (triggers fallback)."""
    pass


class AsyncAnonClient:
    """
    Async anonymous HTTP client — no cookies, no session.

    Features:
        - Configurable scraping strategies with automatic fallback
        - TRUE async I/O via curl_cffi.AsyncSession
        - asyncio.Semaphore concurrency control
        - Shared anti-detect (fingerprint rotation)
        - Shared proxy rotation
        - unlimited=True — raw speed, no throttling

    Architecture:
        ┌──────────────────────────────────────┐
        │     asyncio.Semaphore                │ ← concurrent limit
        │  ┌────────────────────────────────┐  │
        │  │  AsyncAnonRateLimiter          │  │ ← per-strategy
        │  │  ┌──────────────────────────┐  │  │
        │  │  │  curl_cffi.AsyncSession  │  │  │ ← real async I/O
        │  │  └──────────────────────────┘  │  │
        │  └────────────────────────────────┘  │
        └──────────────────────────────────────┘
    """

    def __init__(
        self,
        anti_detect: Optional[AntiDetect] = None,
        proxy_manager: Optional[ProxyManager] = None,
        unlimited: bool = False,
        max_concurrency: int = 0,
        profile_strategies=None,
        posts_strategies=None,
    ):
        """
        Args:
            anti_detect: Shared AntiDetect instance
            proxy_manager: Shared ProxyManager instance
            unlimited: Disable all delays and rate limits
            max_concurrency: Override max concurrent requests
                            (0 = auto: 1000 if unlimited, 10 if normal)
            profile_strategies: Custom profile strategy order
            posts_strategies: Custom posts strategy order
        """
        self._anti_detect = anti_detect or AntiDetect()
        self._proxy_mgr = proxy_manager
        self._unlimited = unlimited
        self._rate_limiter = AsyncAnonRateLimiter(enabled=not unlimited)
        self._delays = ANON_REQUEST_DELAYS_UNLIMITED if unlimited else ANON_REQUEST_DELAYS

        # Concurrency control
        if max_concurrency > 0:
            concurrency = max_concurrency
        else:
            concurrency = 1000 if unlimited else 10
        self._semaphore = asyncio.Semaphore(concurrency)
        self._max_concurrency = concurrency

        # Session pool (one per identity to avoid TLS conflicts)
        self._session: Optional[AsyncSession] = None
        self._session_lock = asyncio.Lock()

        # Stats (protected by _stats_lock)
        self._stats_lock = asyncio.Lock()
        self._request_count = 0
        self._error_count = 0
        self._active_requests = 0

        # Configurable strategy chains
        self._profile_strategies = parse_profile_strategies(profile_strategies)
        self._posts_strategies = parse_posts_strategies(posts_strategies)

    # ═══════════════════════════════════════════════════════════
    # SESSION MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    async def _get_session(self) -> AsyncSession:
        """Get or create async session (thread-safe)."""
        if self._session is None:
            async with self._session_lock:
                if self._session is None:
                    identity = self._anti_detect.get_identity()
                    self._session = AsyncSession(
                        impersonate=identity.impersonation,
                        max_clients=self._max_concurrency,
                        verify=not bool(self._proxy_mgr),
                    )
        return self._session

    async def _rotate_session(self) -> None:
        """Create a new session with fresh TLS fingerprint."""
        async with self._session_lock:
            if self._session:
                try:
                    await self._session.close()
                except Exception:
                    pass
            identity = self._anti_detect.get_identity(force_new=True)
            self._session = AsyncSession(
                impersonate=identity.impersonation,
                max_clients=self._max_concurrency,
                verify=not bool(self._proxy_mgr),
            )

    # ═══════════════════════════════════════════════════════════
    # CORE HTTP — async requests via curl_cffi
    # ═══════════════════════════════════════════════════════════

    async def _request(
        self,
        url: str,
        strategy: str,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        parse_json: bool = True,
        timeout: int = 15,
    ) -> Any:
        """
        Send async anonymous HTTP request with anti-detect and proxy.

        Returns parsed JSON dict or raw response text.
        Raises AsyncStrategyFailed on HTTP errors (429, 401, etc).
        """
        # Concurrency gate
        async with self._semaphore:
            async with self._stats_lock:
                self._active_requests += 1
            try:
                return await self._request_inner(
                    url, strategy, headers, params, parse_json, timeout
                )
            finally:
                async with self._stats_lock:
                    self._active_requests -= 1

    async def _request_inner(
        self,
        url: str,
        strategy: str,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        parse_json: bool = True,
        timeout: int = 15,
    ) -> Any:
        """Inner request logic (already inside semaphore)."""
        identity = self._anti_detect.get_identity()

        # Build headers
        req_headers = {
            "user-agent": identity.user_agent,
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "accept-language": identity.accept_language,
            "accept-encoding": "gzip, deflate, br",
            "cache-control": "no-cache",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
        }
        if identity.sec_ch_ua:
            req_headers["sec-ch-ua"] = identity.sec_ch_ua
            req_headers["sec-ch-ua-mobile"] = identity.sec_ch_ua_mobile
            req_headers["sec-ch-ua-platform"] = identity.sec_ch_ua_platform

        if headers:
            req_headers.update(headers)

        # Proxy
        proxy_dict = None
        proxy_url = None
        if self._proxy_mgr and self._proxy_mgr.active_count > 0:
            proxy_url = self._proxy_mgr.get_proxy()
            if proxy_url:
                proxy_dict = {"https": proxy_url, "http": proxy_url}

        # Human delay (skipped in unlimited mode)
        await self._human_delay()

        # Rate limit check (skipped in unlimited mode)
        await self._rate_limiter.wait_if_needed(strategy)

        # Build kwargs
        kwargs = {
            "url": url,
            "headers": req_headers,
            "timeout": timeout,
            "allow_redirects": True,
            "verify": proxy_dict is None,  # SSL verify off when using proxy (MITM)
        }
        if params:
            kwargs["params"] = params
        if proxy_dict:
            kwargs["proxies"] = proxy_dict

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                session = await self._get_session()
                response = await session.get(**kwargs)
                self._request_count += 1

                # Report proxy success
                if proxy_url:
                    elapsed = getattr(response, 'elapsed', 0.0)
                    if hasattr(elapsed, 'total_seconds'):
                        elapsed = elapsed.total_seconds()
                    self._proxy_mgr.report_success(proxy_url, float(elapsed))

                # Check status
                if response.status_code == 429:
                    logger.warning(f"[AsyncAnon] Rate limited on {strategy}, attempt {attempt + 1}")
                    self._anti_detect.on_error("rate_limit")
                    wait = random.uniform(
                        self._delays["after_rate_limit"]["min"],
                        self._delays["after_rate_limit"]["max"],
                    )
                    if wait > 0:
                        await asyncio.sleep(wait)
                    # Rotate identity for retry
                    identity = self._anti_detect.get_identity(force_new=True)
                    kwargs["headers"]["user-agent"] = identity.user_agent
                    await self._rotate_session()
                    continue

                if response.status_code == 404:
                    return None

                if response.status_code in (401, 403):
                    # Retry with new proxy + identity (proxy may be blocked)
                    if attempt < MAX_RETRIES and self._proxy_mgr and self._proxy_mgr.active_count > 0:
                        logger.debug(f"[AsyncAnon] Auth {response.status_code} on {strategy}, retrying with new proxy...")
                        if proxy_url:
                            self._proxy_mgr.report_failure(proxy_url)
                        proxy_url = self._proxy_mgr.get_proxy()
                        if proxy_url:
                            kwargs["proxies"] = {"https": proxy_url, "http": proxy_url}
                        identity = self._anti_detect.get_identity(force_new=True)
                        kwargs["headers"]["user-agent"] = identity.user_agent
                        await self._rotate_session()
                        err_wait = self._delays.get("after_error", {})
                        if err_wait.get("max", 0) > 0:
                            await asyncio.sleep(random.uniform(err_wait.get("min", 0.5), err_wait["max"]))
                        continue
                    logger.debug(f"[AsyncAnon] Auth required on {strategy}: {response.status_code}")
                    raise AsyncStrategyFailed(f"Auth required: {response.status_code}")

                if response.status_code >= 500:
                    logger.warning(f"[AsyncAnon] Server error {response.status_code} on {strategy}")
                    if not self._unlimited:
                        await asyncio.sleep(random.uniform(1, 3))
                    continue

                response.raise_for_status()

                if parse_json:
                    return response.json()
                return response.text

            except AsyncStrategyFailed:
                raise
            except Exception as e:
                last_error = e
                async with self._stats_lock:
                    self._error_count += 1
                if proxy_url:
                    self._proxy_mgr.report_failure(proxy_url)
                self._anti_detect.on_error("network")

                if attempt < MAX_RETRIES:
                    err_min = self._delays["after_error"]["min"]
                    err_max = self._delays["after_error"]["max"]
                    if err_max > 0:
                        await asyncio.sleep(random.uniform(err_min, err_max))

                    # Get new proxy for retry
                    if self._proxy_mgr and self._proxy_mgr.active_count > 0:
                        proxy_url = self._proxy_mgr.get_proxy()
                        if proxy_url:
                            kwargs["proxies"] = {"https": proxy_url, "http": proxy_url}

        raise AsyncStrategyFailed(f"All attempts failed for {strategy}: {last_error}")

    async def _human_delay(self) -> None:
        """Natural delay between requests. Skipped in unlimited mode."""
        if self._unlimited:
            return

        min_d = self._delays["min"]
        max_d = self._delays["max"]
        if max_d <= 0:
            return

        mean = (min_d + max_d) / 2
        std = (max_d - min_d) / 4
        delay = max(min_d, random.gauss(mean, std))
        delay = min(delay, max_d * 1.5)
        if random.random() < 0.05:
            delay += random.uniform(3.0, 8.0)
        await asyncio.sleep(delay)

    # ═══════════════════════════════════════════════════════════
    # STRATEGY 1: HTML Page Parse
    # ═══════════════════════════════════════════════════════════

    async def get_profile_html(self, username: str) -> Optional[Dict]:
        """Parse Instagram profile page HTML for embedded JSON data."""
        url = f"https://www.instagram.com/{username}/"
        try:
            html = await self._request(url, "html_parse", parse_json=False)
        except AsyncStrategyFailed:
            return None

        if not html:
            return None

        # Check for login redirect
        if '"LoginAndSignupPage"' in html or "login/?next=" in html:
            logger.debug("[AsyncAnon] HTML parse: login redirect detected")
            return None

        result = {}

        # Method 1: window._sharedData
        shared_data_match = re.search(
            r'window\._sharedData\s*=\s*({.+?})\s*;</script>',
            html, re.DOTALL
        )
        if shared_data_match:
            try:
                shared = json.loads(shared_data_match.group(1))
                user_data = (
                    shared.get("entry_data", {})
                    .get("ProfilePage", [{}])[0]
                    .get("graphql", {})
                    .get("user", {})
                )
                if user_data:
                    result = self._parse_graphql_user(user_data)
            except (json.JSONDecodeError, IndexError, KeyError):
                pass

        # Method 2: window.__additionalDataLoaded
        if not result:
            additional_match = re.search(
                r'window\.__additionalDataLoaded\s*\(\s*[\'"].*?[\'"]\s*,\s*({.+?})\s*\)\s*;',
                html, re.DOTALL
            )
            if additional_match:
                try:
                    data = json.loads(additional_match.group(1))
                    user_data = data.get("graphql", {}).get("user", {})
                    if not user_data:
                        user_data = data.get("user", {})
                    if user_data:
                        result = self._parse_graphql_user(user_data)
                except (json.JSONDecodeError, KeyError):
                    pass

        # Method 3: JSON-LD schema
        if not result:
            ld_match = re.search(
                r'<script type="application/ld\+json">\s*({.+?})\s*</script>',
                html, re.DOTALL
            )
            if ld_match:
                try:
                    ld = json.loads(ld_match.group(1))
                    result = {
                        "username": ld.get("alternateName", "").lstrip("@"),
                        "full_name": ld.get("name", ""),
                        "biography": ld.get("description", ""),
                        "profile_pic_url": ld.get("image", ""),
                        "url": ld.get("url", ""),
                    }
                except json.JSONDecodeError:
                    pass

        # Method 4: Meta tags fallback
        if not result:
            result = self._parse_meta_tags(html)

        if result:
            result["_strategy"] = "html_parse"
            result["_username"] = username

        return result if result else None

    def _parse_meta_tags(self, html: str) -> Dict:
        """Delegate to parsers.parse_meta_tags."""
        return _parsers.parse_meta_tags(html)

    def _parse_count(self, text: str) -> int:
        """Delegate to parsers.parse_count."""
        return _parsers.parse_count(text)

    def _parse_graphql_user(self, user: Dict) -> Dict:
        """Delegate to parsers.parse_graphql_user."""
        return _parsers.parse_graphql_user(user)

    def _parse_timeline_edges(self, edges: List[Dict]) -> List[Dict]:
        """Delegate to parsers.parse_timeline_edges."""
        return _parsers.parse_timeline_edges(edges)

    # ═══════════════════════════════════════════════════════════
    # STRATEGY 2: Embed Endpoint
    # ═══════════════════════════════════════════════════════════

    async def get_embed_data(self, shortcode: str) -> Optional[Dict]:
        """Get post data from embed endpoint (async)."""
        url = EMBED_URL.format(shortcode=shortcode)
        try:
            html = await self._request(url, "embed", parse_json=False)
        except AsyncStrategyFailed:
            return None

        if not html:
            return None

        result = {}

        media_match = re.search(
            r'window\.__additionalDataLoaded\s*\(\s*[\'"]extra[\'"]\s*,\s*({.+?})\s*\)',
            html, re.DOTALL
        )
        if media_match:
            try:
                data = json.loads(media_match.group(1))
                shortcode_media = data.get("shortcode_media", {})
                if shortcode_media:
                    result = self._parse_embed_media(shortcode_media)
            except json.JSONDecodeError:
                pass

        if not result:
            result = self._parse_embed_html(html, shortcode)

        if result:
            result["_strategy"] = "embed"
            result["shortcode"] = shortcode

        return result if result else None

    def _parse_embed_media(self, media: Dict) -> Dict:
        """Delegate to parsers.parse_embed_media."""
        return _parsers.parse_embed_media(media)

    def _parse_embed_html(self, html: str, shortcode: str) -> Dict:
        """Delegate to parsers.parse_embed_html."""
        return _parsers.parse_embed_html(html, shortcode)

    # ═══════════════════════════════════════════════════════════
    # STRATEGY 3: GraphQL Public Queries
    # ═══════════════════════════════════════════════════════════

    async def get_graphql_public(
        self,
        query_hash: str,
        variables: Dict,
    ) -> Optional[Dict]:
        """Public GraphQL query (no auth required for some queries)."""
        url = "https://www.instagram.com/graphql/query/"
        params = {
            "query_hash": query_hash,
            "variables": json.dumps(variables, separators=(",", ":")),
        }
        extra_headers = {
            "x-ig-app-id": IG_APP_ID,
            "x-requested-with": "XMLHttpRequest",
            "referer": "https://www.instagram.com/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }

        try:
            data = await self._request(
                url, "graphql",
                headers=extra_headers,
                params=params,
                parse_json=True,
            )
        except AsyncStrategyFailed:
            return None

        if data and isinstance(data, dict):
            return data.get("data", data)

        return None

    async def get_user_posts_graphql(
        self,
        user_id: str,
        first: int = 12,
        after: Optional[str] = None,
    ) -> Optional[Dict]:
        """Fetch user posts via public GraphQL (async)."""
        variables = {"id": str(user_id), "first": first}
        if after:
            variables["after"] = after

        query_hash = ANON_GRAPHQL_HASHES.get("user_posts", "")
        data = await self.get_graphql_public(query_hash, variables)
        if data:
            return data.get("user", {}).get("edge_owner_to_timeline_media", {})
        return None

    async def get_post_comments_graphql(
        self,
        shortcode: str,
        first: int = 24,
        after: Optional[str] = None,
    ) -> Optional[Dict]:
        """Fetch post comments via public GraphQL (async)."""
        variables = {"shortcode": shortcode, "first": first}
        if after:
            variables["after"] = after

        query_hash = ANON_GRAPHQL_HASHES.get("post_comments", "")
        data = await self.get_graphql_public(query_hash, variables)
        if data:
            return data.get("shortcode_media", {}).get("edge_media_to_parent_comment", {})
        return None

    async def get_hashtag_posts_graphql(
        self,
        tag_name: str,
        first: int = 12,
        after: Optional[str] = None,
    ) -> Optional[Dict]:
        """Fetch hashtag posts via public GraphQL (async)."""
        variables = {"tag_name": tag_name, "first": first}
        if after:
            variables["after"] = after

        query_hash = ANON_GRAPHQL_HASHES.get("hashtag_posts", "")
        data = await self.get_graphql_public(query_hash, variables)
        if data:
            return data.get("hashtag", {})
        return None

    # ═══════════════════════════════════════════════════════════
    # STRATEGY 4: Mobile API (i.instagram.com)
    # ═══════════════════════════════════════════════════════════

    async def get_mobile_api(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Fetch data from mobile API (i.instagram.com) — async."""
        url = f"{MOBILE_API_BASE}{endpoint}"
        extra_headers = {
            "accept": "*/*",
            "x-ig-app-id": "936619743392459",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "referer": "https://www.instagram.com/",
        }

        try:
            return await self._request(
                url, "mobile_api",
                headers=extra_headers,
                params=params,
                parse_json=True,
            )
        except AsyncStrategyFailed:
            return None

    async def get_user_info_mobile(self, user_id: Union[int, str]) -> Optional[Dict]:
        """Get user info via mobile API (async)."""
        data = await self.get_mobile_api(f"/users/{user_id}/info/")
        if data and isinstance(data, dict):
            return data.get("user", data)
        return None

    # ═══════════════════════════════════════════════════════════
    # STRATEGY 5: Web API (no cookies)
    # ═══════════════════════════════════════════════════════════

    async def get_web_api(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Web API request without cookies (async)."""
        url = f"https://www.instagram.com/api/v1{endpoint}"
        extra_headers = {
            "accept": "*/*",
            "x-ig-app-id": IG_APP_ID,
            "x-requested-with": "XMLHttpRequest",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "referer": "https://www.instagram.com/",
        }

        try:
            return await self._request(
                url, "web_api",
                headers=extra_headers,
                params=params,
                parse_json=True,
            )
        except AsyncStrategyFailed:
            return None

    async def get_web_profile(self, username: str) -> Optional[Dict]:
        """Get profile via web API without cookies (async)."""
        data = await self.get_web_api(
            "/users/web_profile_info/",
            params={"username": username},
        )
        if data and isinstance(data, dict):
            user = data.get("data", {}).get("user", {})
            if user:
                return user
        return None

    # ═══════════════════════════════════════════════════════════
    # FALLBACK CHAIN — try all strategies (async)
    # ═══════════════════════════════════════════════════════════

    async def _get_web_profile_parsed(self, username: str) -> Optional[Dict]:
        """
        Get profile via web API and parse into standardized format (async).
        Returns the richest data — same format as sync version.
        """
        raw = await self.get_web_profile(username)
        if not raw or not isinstance(raw, dict):
            return None

        edges_media = raw.get("edge_owner_to_timeline_media", {})
        bio_links = raw.get("bio_links", [])

        profile = {
            "user_id": raw.get("id"),
            "username": raw.get("username"),
            "full_name": raw.get("full_name"),
            "biography": raw.get("biography", ""),
            "profile_pic_url": raw.get("profile_pic_url"),
            "profile_pic_url_hd": raw.get("profile_pic_url_hd", raw.get("profile_pic_url")),
            "is_private": raw.get("is_private", False),
            "is_verified": raw.get("is_verified", False),
            "is_business": raw.get("is_business_account", False),
            "category": raw.get("category_name", raw.get("business_category_name", "")),
            "external_url": raw.get("external_url"),
            "followers": raw.get("edge_followed_by", {}).get("count", 0),
            "following": raw.get("edge_follow", {}).get("count", 0),
            "posts_count": edges_media.get("count", 0),
            "bio_links": bio_links if isinstance(bio_links, list) else [],
            "pronouns": raw.get("pronouns", []),
            "highlight_count": raw.get("highlight_reel_count", 0),
            "recent_posts": self._parse_timeline_edges(edges_media.get("edges", [])),
            "has_clips": raw.get("has_clips", False),
            "has_guides": raw.get("has_guides", False),
            "mutual_followers": raw.get("edge_mutual_followed_by", {}).get("count", 0),
            "business_email": raw.get("business_email"),
            "business_phone": raw.get("business_phone_number"),
            "business_address": raw.get("business_address_json"),
        }
        return profile

    async def get_profile_chain(self, username: str) -> Optional[Dict]:
        """
        Get profile using configurable fallback chain (async).
        Strategy order is controlled by self._profile_strategies.
        Default: Web API → GraphQL → HTML parse.
        """
        strategy_map = {
            ProfileStrategy.WEB_API: lambda: self._get_web_profile_parsed(username),
            ProfileStrategy.GRAPHQL: lambda: self._graphql_profile_fallback(username),
            ProfileStrategy.HTML_PARSE: lambda: self.get_profile_html(username),
        }

        for strategy in self._profile_strategies:
            fn = strategy_map.get(strategy)
            if not fn:
                continue
            try:
                result = await fn()
                if result and (result.get("username") or result.get("followers")):
                    logger.info(f"[AsyncAnon] Profile '{username}' fetched via {strategy.value}")
                    result["_strategy"] = strategy.value
                    return result
                logger.debug(f"[AsyncAnon] Strategy {strategy.value} returned empty for '{username}'")
            except Exception as e:
                logger.debug(f"[AsyncAnon] Strategy {strategy.value} failed: {e}")
                continue

        logger.warning(f"[AsyncAnon] All strategies failed for profile '{username}'")
        return None

    async def get_post_chain(self, shortcode: str) -> Optional[Dict]:
        """Get post using fallback chain (async)."""
        strategies = [
            ("embed", lambda: self.get_embed_data(shortcode)),
            ("graphql", lambda: self._graphql_post_fallback(shortcode)),
            ("web_api", lambda: self._web_post_fallback(shortcode)),
        ]

        for name, fn in strategies:
            try:
                result = await fn()
                if result:
                    logger.info(f"[AsyncAnon] Post '{shortcode}' fetched via {name}")
                    return result
                logger.debug(f"[AsyncAnon] Strategy {name} returned empty for '{shortcode}'")
            except Exception as e:
                logger.debug(f"[AsyncAnon] Strategy {name} failed: {e}")
                continue

        logger.warning(f"[AsyncAnon] All strategies failed for post '{shortcode}'")
        return None

    async def _graphql_profile_fallback(self, username: str) -> Optional[Dict]:
        """GraphQL fallback for profile (async)."""
        query_hash = ANON_GRAPHQL_HASHES.get("user_info", "")
        data = await self.get_graphql_public(query_hash, {"username": username})
        if data and data.get("user"):
            return self._parse_graphql_user(data["user"])
        return None

    async def _graphql_post_fallback(self, shortcode: str) -> Optional[Dict]:
        """GraphQL fallback for post (async)."""
        query_hash = ANON_GRAPHQL_HASHES.get("post_info", "")
        data = await self.get_graphql_public(query_hash, {"shortcode": shortcode})
        if data and data.get("shortcode_media"):
            return self._parse_embed_media(data["shortcode_media"])
        return None

    async def _web_post_fallback(self, shortcode: str) -> Optional[Dict]:
        """Web API fallback for post (async)."""
        from . import utils
        try:
            media_pk = utils.shortcode_to_pk(shortcode)
            data = await self.get_web_api(f"/media/{media_pk}/info/")
            if data and data.get("items"):
                return data["items"][0]
        except Exception:
            pass
        return None

    # ═══════════════════════════════════════════════════════════
    # MOBILE FEED — /feed/user/{id}/ (async)
    # ═══════════════════════════════════════════════════════════

    async def get_user_feed_mobile(
        self,
        user_id: Union[int, str],
        count: int = 12,
        max_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Get user feed via mobile API (async).

        Args:
            user_id: User PK
            count: Posts per page (max 33)
            max_id: Pagination cursor

        Returns:
            Dict with: items (parsed posts), more_available, next_max_id
        """
        params = {"count": str(min(count, 33))}
        if max_id:
            params["max_id"] = max_id

        data = await self.get_mobile_api(f"/feed/user/{user_id}/", params=params)
        if data and isinstance(data, dict):
            items = data.get("items", [])
            parsed = [self._parse_mobile_feed_item(item) for item in items]
            return {
                "items": parsed,
                "more_available": data.get("more_available", False),
                "next_max_id": data.get("next_max_id"),
                "num_results": data.get("num_results", len(parsed)),
            }
        return None

    async def get_media_info_mobile(self, media_id: Union[int, str]) -> Optional[Dict]:
        """
        Get single media info via mobile API (async).

        Args:
            media_id: Media PK

        Returns:
            Parsed media dict or None
        """
        data = await self.get_mobile_api(f"/media/{media_id}/info/")
        if data and isinstance(data, dict):
            items = data.get("items", [])
            if items:
                return self._parse_mobile_feed_item(items[0])
        return None

    def _parse_mobile_feed_item(self, item: Dict) -> Dict:
        """Delegate to parsers.parse_mobile_feed_item."""
        return _parsers.parse_mobile_feed_item(item)

    # ═══════════════════════════════════════════════════════════
    # SEARCH — web/search/topsearch (async)
    # ═══════════════════════════════════════════════════════════

    async def search_web(
        self,
        query: str,
        context: str = "blended",
    ) -> Optional[Dict]:
        """
        Search Instagram anonymously (async).

        Args:
            query: Search query
            context: 'blended', 'user', 'hashtag', 'place'

        Returns:
            Dict with: users, hashtags, places
        """
        url = "https://www.instagram.com/web/search/topsearch/"
        headers = {
            "accept": "*/*",
            "x-ig-app-id": IG_APP_ID,
            "x-requested-with": "XMLHttpRequest",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "referer": "https://www.instagram.com/",
        }
        params = {"query": query, "context": context}
        try:
            data = await self._request(url, "web_api", headers=headers, params=params)
            if data and isinstance(data, dict):
                return {
                    "users": [
                        {
                            "username": u.get("user", {}).get("username"),
                            "full_name": u.get("user", {}).get("full_name"),
                            "user_id": u.get("user", {}).get("pk"),
                            "is_private": u.get("user", {}).get("is_private"),
                            "is_verified": u.get("user", {}).get("is_verified"),
                            "profile_pic_url": u.get("user", {}).get("profile_pic_url"),
                            "follower_count": u.get("user", {}).get("follower_count"),
                        }
                        for u in data.get("users", [])
                    ],
                    "hashtags": [
                        {
                            "name": h.get("hashtag", {}).get("name"),
                            "media_count": h.get("hashtag", {}).get("media_count"),
                        }
                        for h in data.get("hashtags", [])
                    ],
                    "places": [
                        {
                            "title": p.get("place", {}).get("title"),
                            "location": p.get("place", {}).get("location", {}),
                        }
                        for p in data.get("places", [])
                    ],
                }
        except AsyncStrategyFailed:
            pass
        return None

    # ═══════════════════════════════════════════════════════════
    # REELS — /clips/user/ (async)
    # ═══════════════════════════════════════════════════════════

    async def get_user_reels(
        self,
        user_id: Union[int, str],
        max_id: Optional[str] = None,
        count: int = 12,
    ) -> Optional[Dict]:
        """
        Get user reels/clips via mobile API (async).

        Args:
            user_id: User PK
            max_id: Pagination cursor
            count: Reels per page

        Returns:
            Dict with: items, more_available, max_id
        """
        params = {
            "target_user_id": str(user_id),
            "page_size": str(count),
        }
        if max_id:
            params["max_id"] = max_id

        data = await self.get_mobile_api("/clips/user/", params=params)
        if data and isinstance(data, dict):
            items = data.get("items", [])
            paging = data.get("paging_info", {})
            reels = []
            for item in items:
                media = item.get("media", item)
                reel = self._parse_mobile_feed_item(media)
                reel["play_count"] = media.get("play_count") or media.get("view_count", 0)
                reel["fb_play_count"] = media.get("fb_play_count", 0)
                reel["is_reel"] = True
                clips_meta = media.get("clips_metadata", {})
                if clips_meta:
                    reel["audio"] = {
                        "title": clips_meta.get("music_info", {}).get("music_asset_info", {}).get("title"),
                        "artist": clips_meta.get("music_info", {}).get("music_asset_info", {}).get("display_artist"),
                    }
                reels.append(reel)

            return {
                "items": reels,
                "more_available": paging.get("more_available", False),
                "max_id": paging.get("max_id"),
                "num_results": len(reels),
            }
        return None

    # ═══════════════════════════════════════════════════════════
    # HASHTAG SECTIONS — /tags/{tag}/sections/ (async)
    # ═══════════════════════════════════════════════════════════

    async def get_hashtag_sections(
        self,
        tag_name: str,
        tab: str = "recent",
        max_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Get hashtag posts via web API sections (async).

        Args:
            tag_name: Hashtag (without #)
            tab: 'recent' or 'top'
            max_id: Pagination cursor

        Returns:
            Dict with: tag_name, posts, more_available, media_count
        """
        tag = tag_name.lstrip("#").strip().lower()
        params = {"tab": tab}
        if max_id:
            params["max_id"] = max_id

        data = await self.get_web_api(f"/tags/{tag}/sections/", params=params)
        if data and isinstance(data, dict):
            posts = []
            for section in data.get("sections", []):
                layout = section.get("layout_content", {})
                for m in layout.get("medias", []):
                    media = m.get("media", {})
                    if media:
                        posts.append(self._parse_mobile_feed_item(media))

            return {
                "tag_name": tag,
                "posts": posts,
                "more_available": data.get("more_available", False),
                "next_max_id": data.get("next_max_id"),
                "next_page": data.get("next_page"),
                "media_count": data.get("media_count"),
            }
        return None

    # ═══════════════════════════════════════════════════════════
    # LOCATION SECTIONS — /locations/{id}/sections/ (async)
    # ═══════════════════════════════════════════════════════════

    async def get_location_sections(
        self,
        location_id: Union[int, str],
        tab: str = "recent",
        max_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Get location posts via web API (async).

        Args:
            location_id: Location PK
            tab: 'recent' or 'ranked'
            max_id: Pagination cursor

        Returns:
            Dict with: location info, posts, more_available
        """
        params = {"tab": tab}
        if max_id:
            params["max_id"] = max_id

        data = await self.get_web_api(f"/locations/{location_id}/sections/", params=params)
        if data and isinstance(data, dict):
            posts = []
            for section in data.get("sections", []):
                layout = section.get("layout_content", {})
                for m in layout.get("medias", []):
                    media = m.get("media", {})
                    if media:
                        posts.append(self._parse_mobile_feed_item(media))

            location_info = data.get("location", {})
            return {
                "location": {
                    "pk": location_info.get("pk"),
                    "name": location_info.get("name"),
                    "address": location_info.get("address"),
                    "city": location_info.get("city"),
                    "lat": location_info.get("lat"),
                    "lng": location_info.get("lng"),
                } if location_info else None,
                "posts": posts,
                "more_available": data.get("more_available", False),
                "next_max_id": data.get("next_max_id"),
                "media_count": data.get("media_count"),
            }
        return None

    # ═══════════════════════════════════════════════════════════
    # SIMILAR ACCOUNTS — /discover/chaining/ (async)
    # ═══════════════════════════════════════════════════════════

    async def get_similar_accounts(self, user_id: Union[int, str]) -> Optional[List[Dict]]:
        """
        Get similar/suggested accounts (async).

        Args:
            user_id: Target user PK

        Returns:
            List of similar user dicts
        """
        data = await self.get_web_api("/discover/chaining/", params={"target_id": str(user_id)})
        if data and isinstance(data, dict):
            return [
                {
                    "username": u.get("username"),
                    "full_name": u.get("full_name"),
                    "user_id": u.get("pk"),
                    "is_private": u.get("is_private"),
                    "is_verified": u.get("is_verified"),
                    "profile_pic_url": u.get("profile_pic_url"),
                    "follower_count": u.get("follower_count"),
                    "is_business": u.get("is_business"),
                    "category": u.get("category"),
                }
                for u in data.get("users", [])
            ]
        return None

    # ═══════════════════════════════════════════════════════════
    # STORY HIGHLIGHTS — /highlights/{id}/highlights_tray/ (async)
    # ═══════════════════════════════════════════════════════════

    async def get_highlights_tray(self, user_id: Union[int, str]) -> Optional[List[Dict]]:
        """
        Get story highlights tray (async).

        Args:
            user_id: User PK

        Returns:
            List of highlight dicts
        """
        data = await self.get_mobile_api(f"/highlights/{user_id}/highlights_tray/")
        if data and isinstance(data, dict):
            tray = data.get("tray", [])
            highlights = []
            for item in tray:
                cover_media = item.get("cover_media", {})
                cropped = cover_media.get("cropped_image_version", {})
                highlights.append({
                    "highlight_id": item.get("id"),
                    "title": item.get("title", ""),
                    "media_count": item.get("media_count", 0),
                    "cover_url": cropped.get("url") or cover_media.get("url", ""),
                    "created_at": item.get("created_at"),
                })
            return highlights
        return None

    # ═══════════════════════════════════════════════════════════
    # GraphQL doc_id (cookie-free, POST /api/graphql) — async
    # ═══════════════════════════════════════════════════════════

    async def _request_post(
        self,
        url: str,
        strategy: str,
        headers: Optional[Dict] = None,
        data: Optional[Dict] = None,
        timeout: int = 15,
    ) -> Any:
        """
        Send async anonymous POST request with anti-detect and proxy.
        Used for GraphQL doc_id endpoint which requires POST.
        """
        identity = self._anti_detect.get_identity()

        req_headers = {
            "user-agent": identity.user_agent,
            "accept": "*/*",
            "accept-language": identity.accept_language,
            "accept-encoding": "gzip, deflate, br",
            "content-type": "application/x-www-form-urlencoded",
            "x-ig-app-id": IG_APP_ID,
            "x-fb-lsd": GRAPHQL_LSD_TOKEN,
            "x-asbd-id": "129477",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "referer": "https://www.instagram.com/",
            "origin": "https://www.instagram.com",
        }
        if identity.sec_ch_ua:
            req_headers["sec-ch-ua"] = identity.sec_ch_ua
            req_headers["sec-ch-ua-mobile"] = identity.sec_ch_ua_mobile
            req_headers["sec-ch-ua-platform"] = identity.sec_ch_ua_platform
        if headers:
            req_headers.update(headers)

        proxy = None
        if self._proxy_mgr and self._proxy_mgr.active_count > 0:
            proxy = self._proxy_mgr.get_proxy()

        await self._human_delay()
        await self._rate_limiter.wait_if_needed(strategy)

        session = await self._get_session()
        kwargs = {
            "url": url,
            "headers": req_headers,
            "data": data or {},
            "timeout": timeout,
            "allow_redirects": True,
            "verify": False,
        }
        if proxy:
            kwargs["proxies"] = {"https": proxy, "http": proxy}

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                session = await self._get_session()
                response = await session.post(**kwargs)
                self._request_count += 1

                # Report proxy success
                if proxy:
                    elapsed = getattr(response, 'elapsed', 0.0)
                    self._proxy_mgr.report_success(proxy, elapsed)

                if response.status_code == 429:
                    logger.warning(f"[AsyncAnon] Rate limited on {strategy} POST, attempt {attempt + 1}")
                    self._anti_detect.on_error("rate_limit")
                    wait = random.uniform(
                        self._delays["after_rate_limit"]["min"],
                        self._delays["after_rate_limit"]["max"],
                    )
                    if wait > 0:
                        await asyncio.sleep(wait)
                    identity = self._anti_detect.get_identity(force_new=True)
                    kwargs["headers"]["user-agent"] = identity.user_agent
                    await self._rotate_session()
                    continue

                if response.status_code == 404:
                    return None

                if response.status_code in (401, 403):
                    # Retry with new proxy + identity
                    if attempt < MAX_RETRIES and self._proxy_mgr and self._proxy_mgr.active_count > 0:
                        logger.debug(f"[AsyncAnon] Auth {response.status_code} on {strategy} POST, retrying...")
                        if proxy:
                            self._proxy_mgr.report_failure(proxy)
                        proxy = self._proxy_mgr.get_proxy()
                        if proxy:
                            kwargs["proxies"] = {"https": proxy, "http": proxy}
                        identity = self._anti_detect.get_identity(force_new=True)
                        kwargs["headers"]["user-agent"] = identity.user_agent
                        await self._rotate_session()
                        err_wait = self._delays.get("after_error", {})
                        if err_wait.get("max", 0) > 0:
                            await asyncio.sleep(random.uniform(err_wait.get("min", 0.5), err_wait["max"]))
                        continue
                    raise AsyncStrategyFailed(f"Auth required: {response.status_code}")

                if response.status_code >= 500:
                    logger.warning(f"[AsyncAnon] Server error {response.status_code} on {strategy} POST")
                    if not self._unlimited:
                        await asyncio.sleep(random.uniform(1, 3))
                    continue

                response.raise_for_status()
                return response.json()

            except AsyncStrategyFailed:
                raise
            except Exception as e:
                last_error = e
                self._error_count += 1
                if proxy:
                    self._proxy_mgr.report_failure(proxy)
                self._anti_detect.on_error("network")

                if attempt < MAX_RETRIES:
                    err_min = self._delays["after_error"]["min"]
                    err_max = self._delays["after_error"]["max"]
                    if err_max > 0:
                        await asyncio.sleep(random.uniform(err_min, err_max))

                    # Get new proxy for retry
                    if self._proxy_mgr and self._proxy_mgr.active_count > 0:
                        proxy = self._proxy_mgr.get_proxy()
                        if proxy:
                            kwargs["proxies"] = {"https": proxy, "http": proxy}

        raise AsyncStrategyFailed(f"All POST attempts failed for {strategy}: {last_error}")

    async def get_graphql_docid(
        self,
        shortcode: str,
    ) -> Optional[Dict]:
        """
        Get post/reel data via GraphQL doc_id API (cookie-free, async).

        Uses Instagram's internal GraphQL POST endpoint with doc_id.
        No cookies or authentication required.

        Args:
            shortcode: Post or reel shortcode

        Returns:
            Parsed media dict or None
        """
        doc_id = GRAPHQL_DOC_IDS.get("media_shortcode")
        if not doc_id:
            return None

        url = "https://www.instagram.com/api/graphql"
        post_data = {
            "variables": json.dumps({"shortcode": shortcode}),
            "doc_id": doc_id,
            "lsd": GRAPHQL_LSD_TOKEN,
        }

        try:
            data = await self._request_post(
                url, "graphql_docid",
                data=post_data,
            )
        except AsyncStrategyFailed:
            return None

        if not data or not isinstance(data, dict):
            return None

        media = (
            data.get("data", {})
            .get("xdt_shortcode_media")
        )
        if not media:
            return None

        return self._parse_graphql_docid_media(media)

    def _parse_graphql_docid_media(self, media: Dict) -> Dict:
        """Delegate to parsers.parse_graphql_docid_media."""
        return _parsers.parse_graphql_docid_media(media)

    # ═══════════════════════════════════════════════════════════
    # CLEANUP & STATS
    # ═══════════════════════════════════════════════════════════

    async def close(self) -> None:
        """Close async session and release resources."""
        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def active_requests(self) -> int:
        return self._active_requests

    @property
    def stats(self) -> Dict:
        return {
            "requests": self._request_count,
            "errors": self._error_count,
            "active": self._active_requests,
            "max_concurrency": self._max_concurrency,
            "unlimited": self._unlimited,
        }

    def __repr__(self) -> str:
        mode = "UNLIMITED" if self._unlimited else "NORMAL"
        return (
            f"<AsyncAnonClient mode={mode} "
            f"requests={self._request_count} "
            f"concurrency={self._max_concurrency}>"
        )
