"""
Async Instagram — Main Class
=============================
Async version of Instagram class. Full feature parity.
Uses curl_cffi.AsyncSession for non-blocking I/O.

Usage:
    async with AsyncInstagram.from_env(".env") as ig:
        user = await ig.users.get_by_username("cristiano")

    # Parallel — 50x faster!
    async with AsyncInstagram.from_env() as ig:
        tasks = [ig.users.get_by_username(u) for u in usernames]
        results = await asyncio.gather(*tasks)
"""

import logging
from typing import List, Optional

from .async_client import AsyncHttpClient
from .session_manager import SessionManager
from .proxy_manager import ProxyManager, RotationStrategy
from .anti_detect import AntiDetect
from .async_rate_limiter import AsyncRateLimiter
from .speed_modes import get_mode
from .async_challenge import AsyncChallengeHandler
from .retry import RetryConfig
from .log_config import LogConfig, DebugLogger, set_debug_logger
from .events import EventEmitter, EventType, EventData
from .async_anon_client import AsyncAnonClient
from .api.async_users import AsyncUsersAPI
from .api.async_media import AsyncMediaAPI
from .api.async_friendships import AsyncFriendshipsAPI
from .api.async_feed import AsyncFeedAPI
from .api.async_stories import AsyncStoriesAPI
from .api.async_direct import AsyncDirectAPI
from .api.async_search import AsyncSearchAPI
from .api.async_upload import AsyncUploadAPI
from .api.async_hashtags import AsyncHashtagsAPI
from .api.async_insights import AsyncInsightsAPI
from .api.async_account import AsyncAccountAPI
from .api.async_notifications import AsyncNotificationsAPI
from .api.async_graphql import AsyncGraphQLAPI
from .api.async_location import AsyncLocationAPI
from .api.async_collections import AsyncCollectionsAPI
from .api.async_download import AsyncDownloadAPI
from .api.async_auth import AsyncAuthAPI
from .api.async_public import AsyncPublicAPI
from .batch import BatchAPI

logger = logging.getLogger("instaapi.async")


class AsyncInstagram:
    """
    Async Instagram Private API.

    Speed modes:
        🐢 SAFE  — 5 concurrent, human delays, ban-proof
        ⚡ FAST  — 15 concurrent, moderate delays, balanced
        🚀 TURBO — 50 concurrent, minimal delays, proxy required

    Usage:
        async with AsyncInstagram.from_env(mode='fast') as ig:
            results = await ig.batch.check_profiles(usernames)

    Parallel operations:
        async with AsyncInstagram.from_env(mode='turbo') as ig:
            tasks = [ig.users.get_by_username(u) for u in usernames]
            profiles = await asyncio.gather(*tasks)
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        csrf_token: Optional[str] = None,
        ds_user_id: Optional[str] = None,
        mid: str = "",
        ig_did: str = "",
        datr: str = "",
        user_agent: str = "",
        mode: str = "safe",
        rate_limiting: bool = True,
        challenge_callback=None,
        session_file: Optional[str] = None,
        retry: Optional[RetryConfig] = None,
        log_level: str = "WARNING",
        log_file: Optional[str] = None,
        log_format: Optional[str] = None,
        debug: bool = False,
        debug_log_file: Optional[str] = None,
    ):
        # ─── DEBUG MODE ──────────────────────────────────────
        if debug:
            self._debug = DebugLogger(enabled=True, log_file=debug_log_file)
            set_debug_logger(self._debug)
            log_level = "DEBUG"
        else:
            self._debug = DebugLogger(enabled=False)

        # Logging
        LogConfig.configure(
            level=log_level,
            filename=log_file,
            format=log_format,
        )

        self._mode = get_mode(mode)
        self._session_file = session_file
        self._retry = retry or RetryConfig()
        self._events = EventEmitter()

        # Shared infrastructure
        self._session_mgr = SessionManager()
        self._proxy_mgr = ProxyManager()
        self._anti_detect = AntiDetect()
        self._rate_limiter = AsyncRateLimiter(
            mode=mode,
            proxy_count=0,
            enabled=rate_limiting,
        )
        self._challenge_handler = AsyncChallengeHandler(
            code_callback=challenge_callback,
        )

        # Add initial session if provided
        if session_id:
            self._session_mgr.add_session(
                session_id=session_id,
                csrf_token=csrf_token or "",
                ds_user_id=ds_user_id or "",
                mid=mid,
                ig_did=ig_did,
                datr=datr,
                user_agent=user_agent,
            )

        # Async HTTP client
        self._client = AsyncHttpClient(
            session_manager=self._session_mgr,
            proxy_manager=self._proxy_mgr,
            anti_detect=self._anti_detect,
            rate_limiter=self._rate_limiter,
            challenge_handler=self._challenge_handler,
            session_refresh_callback=self._build_refresh_callback(),
            retry_config=self._retry,
            event_emitter=self._events,
        )

        # Async API modules
        self.users = AsyncUsersAPI(self._client)
        self.media = AsyncMediaAPI(self._client)
        self.friendships = AsyncFriendshipsAPI(self._client)
        self.feed = AsyncFeedAPI(self._client)
        self.stories = AsyncStoriesAPI(self._client)
        self.direct = AsyncDirectAPI(self._client)
        self.search = AsyncSearchAPI(self._client)
        self.upload = AsyncUploadAPI(self._client)
        self.hashtags = AsyncHashtagsAPI(self._client)
        self.insights = AsyncInsightsAPI(self._client)
        self.account = AsyncAccountAPI(self._client)
        self.notifications = AsyncNotificationsAPI(self._client)
        self.graphql = AsyncGraphQLAPI(self._client)
        self.location = AsyncLocationAPI(self._client)
        self.collections = AsyncCollectionsAPI(self._client)
        self.download = AsyncDownloadAPI(self._client)
        self.auth = AsyncAuthAPI(self._client)

        # Batch operations (async power)
        self.batch = BatchAPI(self)

        # Anonymous public API (TRUE async with AsyncAnonClient)
        self._anon_client = AsyncAnonClient(
            anti_detect=self._anti_detect,
            proxy_manager=self._proxy_mgr,
        )
        self.public = AsyncPublicAPI(self._anon_client)

    # ─── EVENT SYSTEM ────────────────────────────────────────

    def on(self, event_type, callback):
        """Register event listener."""
        self._events.on(event_type, callback)
        return self

    def off(self, event_type, callback):
        """Remove event listener."""
        self._events.off(event_type, callback)
        return self

    # ─── SESSION AUTO-REFRESH ────────────────────────────────

    def _build_refresh_callback(self):
        """Build session refresh callback for auto-retry on LoginRequired."""
        if not self._session_file:
            return None

        async def _refresh():
            import os
            if os.path.exists(self._session_file):
                try:
                    await self.auth.load_session(self._session_file)
                    return True
                except Exception:
                    pass
            return False

        return _refresh

    # ─── SESSION CONVENIENCE ─────────────────────────────────

    async def save_session(self, filepath: str = "session.json") -> None:
        """Save current session to file."""
        await self.auth.save_session(filepath)

    async def load_session(self, filepath: str = "session.json") -> bool:
        """Load session from file."""
        return await self.auth.load_session(filepath)

    # ─── FACTORY METHODS ─────────────────────────────────────

    @classmethod
    def from_session_file(
        cls,
        filepath: str = "session.json",
        debug: bool = False,
        debug_log_file: Optional[str] = None,
        **kwargs,
    ) -> "AsyncInstagram":
        """Create async client from saved session file."""
        ig = cls(
            session_file=filepath,
            debug=debug,
            debug_log_file=debug_log_file,
            **kwargs,
        )
        ig.load_session(filepath)
        return ig

    @classmethod
    def anonymous(cls, mode: str = "safe", unlimited: bool = False) -> "AsyncInstagram":
        """
        Create anonymous-only async client (no login).

        Args:
            mode: Speed mode — 'safe', 'fast', 'turbo', or 'unlimited'
            unlimited: If True, force unlimited mode (no delays, no rate limits)

        Usage:
            async with AsyncInstagram.anonymous() as ig:
                profile = await ig.public.get_profile("cristiano")

            # Maximum speed — 1000 concurrent, no delays:
            async with AsyncInstagram.anonymous(unlimited=True) as ig:
                tasks = [ig.public.get_profile(u) for u in usernames]
                results = await asyncio.gather(*tasks)
        """
        if unlimited:
            mode = "unlimited"
        instance = cls(mode=mode, rate_limiting=not unlimited)
        # Override with unlimited AsyncAnonClient
        instance._anon_client = AsyncAnonClient(
            anti_detect=instance._anti_detect,
            proxy_manager=instance._proxy_mgr,
            unlimited=unlimited,
        )
        instance.public = AsyncPublicAPI(instance._anon_client)
        return instance

    @classmethod
    def from_env(
        cls,
        env_path: str = ".env",
        mode: str = "safe",
        rate_limiting: bool = True,
        debug: bool = False,
        debug_log_file: Optional[str] = None,
    ) -> "AsyncInstagram":
        """
        Create async client from .env file.

        Args:
            env_path: Path to .env file
            mode: Speed mode — 'safe', 'fast', or 'turbo'
            rate_limiting: Enable/disable rate limiting
            debug: Enable structured debug logging
            debug_log_file: Debug log file path
        """
        instance = cls(
            mode=mode,
            rate_limiting=rate_limiting,
            debug=debug,
            debug_log_file=debug_log_file,
        )
        instance._session_mgr.load_from_env(env_path)

        if instance._session_mgr.session_count == 0:
            logger.warning(
                f"No sessions found! Check {env_path}. "
                "SESSION_ID, CSRF_TOKEN, DS_USER_ID are required."
            )

        # Debug: log session info
        if debug and instance._session_mgr.session_count > 0:
            sess = instance._session_mgr.get_session()
            if sess:
                instance._debug.session_info(
                    ds_user_id=sess.ds_user_id,
                    csrf_token=sess.csrf_token,
                    ig_www_claim=sess.ig_www_claim,
                    session_id=sess.session_id,
                    user_agent=sess.user_agent,
                )

        return instance

    # ─── PROXY MANAGEMENT ─────────────────────────────────────

    def add_proxies(self, proxy_urls: List[str]) -> "AsyncInstagram":
        """Add proxies and auto-update rate limiter concurrency."""
        self._proxy_mgr.add_proxies(proxy_urls)
        self._rate_limiter.update_proxy_count(self._proxy_mgr.active_count)
        return self

    def add_proxy(self, proxy_url: str) -> "AsyncInstagram":
        """Add a single proxy."""
        return self.add_proxies([proxy_url])

    # ─── CONTEXT MANAGER ─────────────────────────────────────

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def close(self) -> None:
        """Clean up async resources."""
        await self._client.close()
        # Close async anon client session
        if hasattr(self._anon_client, 'close'):
            await self._anon_client.close()

    def __repr__(self) -> str:
        sessions = self._session_mgr.session_count
        proxies = self._proxy_mgr.active_count
        mode = self._mode.name.upper()
        return f"<AsyncInstagram mode={mode} sessions={sessions} proxies={proxies}>"
