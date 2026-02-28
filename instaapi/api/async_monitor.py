"""
Async Account Monitor — Real-time Monitoring
==============================================
Async version of MonitorAPI. Full feature parity.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .monitor import AccountWatcher

logger = logging.getLogger("instaapi.monitor")


class AsyncMonitorAPI:
    """
    Async Instagram Account Monitor.

    Poll-based monitoring with configurable intervals.
    Supports multiple accounts simultaneously.
    """

    def __init__(self, client, users_api, feed_api=None, stories_api=None):
        self._client = client
        self._users = users_api
        self._feed = feed_api
        self._stories = stories_api
        self._watchers: Dict[str, AccountWatcher] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._interval = 300
        self._event_log: List[Dict] = []

    def watch(self, username: str) -> AccountWatcher:
        """
        Start watching an account. Returns watcher for callback registration.

        Args:
            username: Instagram username

        Returns:
            AccountWatcher instance for registering callbacks
        """
        if username not in self._watchers:
            self._watchers[username] = AccountWatcher(username)
        return self._watchers[username]

    def unwatch(self, username: str) -> None:
        """Stop watching an account."""
        self._watchers.pop(username, None)

    @property
    def watched_accounts(self) -> List[str]:
        """List of watched usernames."""
        return list(self._watchers.keys())

    @property
    def watcher_count(self) -> int:
        return len(self._watchers)

    async def start(self, interval: int = 300) -> None:
        """
        Start background monitoring.

        Args:
            interval: Check interval in seconds (default 300 = 5 min)
        """
        if self._running:
            return
        self._interval = interval
        self._running = True
        await self._check_all(initial=True)
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop background monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    @property
    def is_running(self) -> bool:
        return self._running

    async def check_now(self) -> Dict[str, Any]:
        """
        Manual check — poll all watched accounts now.

        Returns:
            dict: {checked, events_fired, errors}
        """
        return await self._check_all()

    async def _poll_loop(self) -> None:
        """Background polling loop."""
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                if self._running:
                    await self._check_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor poll error: {e}")

    async def _check_all(self, initial: bool = False) -> Dict[str, Any]:
        """Check all watched accounts."""
        checked = 0
        events = 0
        errors = 0
        for username, watcher in list(self._watchers.items()):
            try:
                ev = await self._check_account(watcher, initial=initial)
                events += ev
                checked += 1
            except Exception as e:
                errors += 1
                logger.warning(f"Monitor check error for @{username}: {e}")
        return {"checked": checked, "events_fired": events, "errors": errors}

    async def _check_account(self, watcher: AccountWatcher, initial: bool = False) -> int:
        """Check a single account for changes. Returns number of events fired."""
        events = 0
        try:
            user = await self._users.get_by_username(watcher.username)
            state = self._extract_state(user)
        except Exception as e:
            logger.debug(f"Check @{watcher.username} error: {e}")
            return 0

        if not watcher.user_id:
            watcher.user_id = state.get("pk")

        if initial or watcher.state is None:
            watcher.state = state
            watcher._last_check = time.time()
            return 0

        prev = watcher.state

        # Check follower change
        old_f = prev.get("followers", 0)
        new_f = state.get("followers", 0)
        if old_f != new_f and old_f > 0:
            watcher._fire(watcher._on_follower_change, old_f, new_f)
            self._log_event(watcher.username, "follower_change", {"old": old_f, "new": new_f})
            events += 1

        # Check bio change
        old_bio = prev.get("biography", "")
        new_bio = state.get("biography", "")
        if old_bio != new_bio:
            watcher._fire(watcher._on_bio_change, old_bio, new_bio)
            self._log_event(watcher.username, "bio_change", {"old": old_bio, "new": new_bio})
            events += 1

        # Check post count
        old_posts = prev.get("posts_count", 0)
        new_posts = state.get("posts_count", 0)
        if new_posts > old_posts:
            watcher._fire(watcher._on_new_post, {"new_count": new_posts, "old_count": old_posts})
            self._log_event(watcher.username, "new_post", {"old": old_posts, "new": new_posts})
            events += 1

        watcher.state = state
        watcher._last_check = time.time()
        return events

    @staticmethod
    def _extract_state(user) -> Dict:
        """Extract monitorable state from user object."""
        if hasattr(user, "pk"):
            return {
                "pk": getattr(user, "pk", 0),
                "username": getattr(user, "username", ""),
                "followers": getattr(user, "followers", 0),
                "following": getattr(user, "following", 0),
                "posts_count": getattr(user, "posts_count", 0),
                "biography": getattr(user, "biography", ""),
                "profile_pic_url": getattr(user, "profile_pic_url", ""),
                "is_private": getattr(user, "is_private", False),
            }
        elif isinstance(user, dict):
            return {
                "pk": user.get("pk", 0),
                "username": user.get("username", ""),
                "followers": user.get("follower_count", 0) or user.get("followers", 0),
                "following": user.get("following_count", 0) or user.get("following", 0),
                "posts_count": user.get("media_count", 0) or user.get("posts_count", 0),
                "biography": user.get("biography", ""),
                "profile_pic_url": user.get("profile_pic_url", ""),
                "is_private": user.get("is_private", False),
            }
        return {}

    def _log_event(self, username: str, event_type: str, data: Dict) -> None:
        """Log a monitoring event."""
        self._event_log.append({
            "username": username, "event": event_type,
            "data": data, "timestamp": datetime.now().isoformat(),
        })
        if len(self._event_log) > 1000:
            self._event_log = self._event_log[-500:]

    @property
    def event_log(self) -> List[Dict]:
        """Recent events."""
        return self._event_log[-100:]

    def get_stats(self) -> Dict[str, Any]:
        """Monitor statistics."""
        return {
            "watched_accounts": len(self._watchers),
            "total_events": len(self._event_log),
            "is_running": self._running,
            "interval": self._interval,
        }
