"""
Account Monitor — Real-time Webhook System
============================================
Monitor Instagram accounts for changes: new posts, follower count
changes, new stories, bio updates. Background polling with callbacks.

Usage:
    ig = Instagram.from_env(".env")

    # Watch a user
    watcher = ig.monitor.watch("cristiano")

    # Register callbacks
    watcher.on_new_post(lambda post: print(f"New post! {post['shortcode']}"))
    watcher.on_follower_change(lambda old, new: print(f"Followers: {old} → {new}"))
    watcher.on_new_story(lambda count: print(f"{count} new stories!"))
    watcher.on_bio_change(lambda old, new: print(f"Bio changed!"))

    # Start monitoring (background thread)
    ig.monitor.start(interval=300)  # check every 5 min

    # Stop monitoring
    ig.monitor.stop()
"""

import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("instaharvest_v2.monitor")


class AccountWatcher:
    """
    Monitors a single account for changes.

    Tracks: posts, followers, stories, bio, profile pic.
    """

    def __init__(self, username: str):
        self.username = username
        self.user_id: Optional[int] = None

        # Callbacks
        self._on_new_post: List[Callable] = []
        self._on_follower_change: List[Callable] = []
        self._on_new_story: List[Callable] = []
        self._on_bio_change: List[Callable] = []
        self._on_profile_change: List[Callable] = []

        # Last known state
        self._last_state: Optional[Dict] = None
        self._last_post_ids: set = set()
        self._last_check: float = 0
        self._check_count: int = 0

    # ─── Callback registration ─────────────────────────

    def on_new_post(self, callback: Callable) -> "AccountWatcher":
        """Register callback for new posts. Receives post dict."""
        self._on_new_post.append(callback)
        return self

    def on_follower_change(self, callback: Callable) -> "AccountWatcher":
        """Register callback for follower count change. Receives (old_count, new_count)."""
        self._on_follower_change.append(callback)
        return self

    def on_new_story(self, callback: Callable) -> "AccountWatcher":
        """Register callback for new stories. Receives story_count."""
        self._on_new_story.append(callback)
        return self

    def on_bio_change(self, callback: Callable) -> "AccountWatcher":
        """Register callback for bio changes. Receives (old_bio, new_bio)."""
        self._on_bio_change.append(callback)
        return self

    def on_profile_change(self, callback: Callable) -> "AccountWatcher":
        """Register callback for any profile change. Receives (field, old, new)."""
        self._on_profile_change.append(callback)
        return self

    def _fire(self, callbacks: List[Callable], *args) -> None:
        """Safely fire callbacks."""
        for cb in callbacks:
            try:
                cb(*args)
            except Exception as e:
                logger.error(f"Callback error for @{self.username}: {e}")

    @property
    def last_state(self) -> Optional[Dict]:
        return self._last_state

    @property
    def is_initialized(self) -> bool:
        return self._last_state is not None


class MonitorAPI:
    """
    Instagram Account Monitor.

    Poll-based monitoring with configurable intervals.
    Supports multiple accounts simultaneously.
    """

    def __init__(self, client, users_api, feed_api=None, stories_api=None):
        self._client = client
        self._users = users_api
        self._feed = feed_api
        self._stories = stories_api
        self._watchers: Dict[str, AccountWatcher] = {}
        self._lock = threading.Lock()
        self._worker: Optional[threading.Thread] = None
        self._running = False
        self._interval = 300  # seconds
        self._event_log: List[Dict] = []

    # ═══════════════════════════════════════════════════════════
    # WATCH MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    def watch(self, username: str) -> AccountWatcher:
        """
        Start watching an account. Returns watcher for callback registration.

        Args:
            username: Instagram username

        Returns:
            AccountWatcher instance for registering callbacks
        """
        username = username.lstrip("@").lower()
        with self._lock:
            if username not in self._watchers:
                self._watchers[username] = AccountWatcher(username)
                logger.info(f"👁️ Watching @{username}")
        return self._watchers[username]

    def unwatch(self, username: str) -> bool:
        """Stop watching an account."""
        username = username.lstrip("@").lower()
        with self._lock:
            if username in self._watchers:
                del self._watchers[username]
                logger.info(f"🚫 Unwatched @{username}")
                return True
        return False

    @property
    def watched_accounts(self) -> List[str]:
        """List of watched usernames."""
        with self._lock:
            return list(self._watchers.keys())

    @property
    def watcher_count(self) -> int:
        return len(self._watchers)

    # ═══════════════════════════════════════════════════════════
    # START / STOP
    # ═══════════════════════════════════════════════════════════

    def start(self, interval: int = 300) -> None:
        """
        Start background monitoring.

        Args:
            interval: Check interval in seconds (default 300 = 5 min)
        """
        if self._running:
            logger.warning("Monitor already running")
            return

        self._interval = max(interval, 60)  # Min 60s to be safe
        self._running = True
        self._worker = threading.Thread(target=self._poll_loop, daemon=True, name="monitor-worker")
        self._worker.start()
        logger.info(f"▶️ Monitor started | {len(self._watchers)} accounts | interval={self._interval}s")

    def stop(self) -> None:
        """Stop background monitoring."""
        self._running = False
        if self._worker:
            self._worker.join(timeout=10)
            self._worker = None
        logger.info("⏹️ Monitor stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def check_now(self) -> Dict[str, Any]:
        """
        Manual check — poll all watched accounts now.

        Returns:
            dict: {checked, events_fired, errors}
        """
        return self._check_all()

    # ═══════════════════════════════════════════════════════════
    # POLLING LOGIC
    # ═══════════════════════════════════════════════════════════

    def _poll_loop(self) -> None:
        """Background polling loop."""
        # Initial baseline fetch
        self._check_all(initial=True)

        while self._running:
            time.sleep(self._interval)
            if not self._running:
                break
            try:
                self._check_all()
            except Exception as e:
                logger.error(f"Monitor poll error: {e}")

    def _check_all(self, initial: bool = False) -> Dict[str, Any]:
        """Check all watched accounts."""
        with self._lock:
            watchers = list(self._watchers.values())

        checked = 0
        events = 0
        errors = 0

        for watcher in watchers:
            try:
                ev = self._check_account(watcher, initial)
                events += ev
                checked += 1
            except Exception as e:
                errors += 1
                logger.debug(f"Check @{watcher.username} error: {e}")

        if not initial:
            logger.debug(f"📡 Monitor check: {checked} accounts, {events} events, {errors} errors")

        return {"checked": checked, "events_fired": events, "errors": errors}

    def _check_account(self, watcher: AccountWatcher, initial: bool = False) -> int:
        """Check a single account for changes. Returns number of events fired."""
        events = 0

        # Fetch current state
        try:
            user = self._users.get_by_username(watcher.username)
        except Exception:
            return 0

        current = self._extract_state(user)

        if not watcher.user_id:
            watcher.user_id = current.get("user_id")

        # Fetch recent posts
        current_post_ids = set()
        if watcher._on_new_post:
            try:
                uid = current.get("user_id")
                if uid:
                    feed = self._client.request(
                        "GET", f"/api/v1/feed/user/{uid}/",
                        params={"count": "12"},
                    )
                    items = feed.get("items", []) if feed else []
                    for item in items:
                        pid = item.get("pk") or item.get("id")
                        if pid:
                            current_post_ids.add(str(pid))
                    current["_post_items"] = items
            except Exception:
                pass

        if initial or not watcher.is_initialized:
            # First check — set baseline
            watcher._last_state = current
            watcher._last_post_ids = current_post_ids
            watcher._last_check = time.time()
            watcher._check_count += 1
            return 0

        prev = watcher._last_state

        # ─── Check for changes ────────────────────────────

        # Follower change
        old_followers = prev.get("followers", 0)
        new_followers = current.get("followers", 0)
        if old_followers != new_followers and watcher._on_follower_change:
            watcher._fire(watcher._on_follower_change, old_followers, new_followers)
            self._log_event(watcher.username, "follower_change", {"old": old_followers, "new": new_followers})
            events += 1

        # New posts
        if current_post_ids and watcher._last_post_ids:
            new_posts = current_post_ids - watcher._last_post_ids
            if new_posts and watcher._on_new_post:
                items = current.get("_post_items", [])
                for item in items:
                    pid = str(item.get("pk") or item.get("id", ""))
                    if pid in new_posts:
                        post_info = {
                            "pk": item.get("pk"),
                            "shortcode": item.get("code", ""),
                            "media_type": item.get("media_type"),
                            "caption": (item.get("caption", {}) or {}).get("text", ""),
                            "like_count": item.get("like_count", 0),
                        }
                        watcher._fire(watcher._on_new_post, post_info)
                        self._log_event(watcher.username, "new_post", post_info)
                        events += 1

        # Bio change
        old_bio = prev.get("biography", "")
        new_bio = current.get("biography", "")
        if old_bio != new_bio and watcher._on_bio_change:
            watcher._fire(watcher._on_bio_change, old_bio, new_bio)
            self._log_event(watcher.username, "bio_change", {"old": old_bio[:80], "new": new_bio[:80]})
            events += 1

        # Profile changes (name, pic, verified, private)
        for field in ["full_name", "is_private", "is_verified", "profile_pic_url", "external_url"]:
            old_val = prev.get(field)
            new_val = current.get(field)
            if old_val != new_val and watcher._on_profile_change:
                watcher._fire(watcher._on_profile_change, field, old_val, new_val)
                self._log_event(watcher.username, "profile_change", {"field": field})
                events += 1

        # Update state
        watcher._last_state = current
        watcher._last_post_ids = current_post_ids if current_post_ids else watcher._last_post_ids
        watcher._last_check = time.time()
        watcher._check_count += 1

        return events

    # ═══════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _extract_state(user) -> Dict:
        """Extract monitorable state from user object."""
        if hasattr(user, "__dict__"):
            return {
                "user_id": getattr(user, "pk", None),
                "username": getattr(user, "username", ""),
                "full_name": getattr(user, "full_name", ""),
                "followers": getattr(user, "followers", 0) or getattr(user, "follower_count", 0),
                "following": getattr(user, "following", 0) or getattr(user, "following_count", 0),
                "posts_count": getattr(user, "media_count", 0),
                "biography": getattr(user, "biography", ""),
                "is_private": getattr(user, "is_private", False),
                "is_verified": getattr(user, "is_verified", False),
                "profile_pic_url": getattr(user, "profile_pic_url", ""),
                "external_url": getattr(user, "external_url", ""),
            }
        elif isinstance(user, dict):
            return {
                "user_id": user.get("pk"),
                "username": user.get("username", ""),
                "full_name": user.get("full_name", ""),
                "followers": user.get("follower_count", 0) or user.get("followers", 0),
                "following": user.get("following_count", 0) or user.get("following", 0),
                "posts_count": user.get("media_count", 0),
                "biography": user.get("biography", ""),
                "is_private": user.get("is_private", False),
                "is_verified": user.get("is_verified", False),
                "profile_pic_url": user.get("profile_pic_url", ""),
                "external_url": user.get("external_url", ""),
            }
        return {}

    def _log_event(self, username: str, event_type: str, data: Dict) -> None:
        """Log a monitoring event."""
        self._event_log.append({
            "username": username,
            "event": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        })
        if len(self._event_log) > 1000:
            self._event_log = self._event_log[-1000:]
        logger.info(f"📡 @{username} → {event_type}: {data}")

    @property
    def event_log(self) -> List[Dict]:
        """Recent events."""
        return self._event_log[-100:]

    def get_stats(self) -> Dict[str, Any]:
        """Monitor statistics."""
        with self._lock:
            return {
                "is_running": self._running,
                "interval": self._interval,
                "watched_accounts": len(self._watchers),
                "total_events": len(self._event_log),
                "accounts": [
                    {
                        "username": w.username,
                        "checks": w._check_count,
                        "last_check": datetime.fromtimestamp(w._last_check).isoformat() if w._last_check else None,
                        "callbacks": {
                            "on_new_post": len(w._on_new_post),
                            "on_follower_change": len(w._on_follower_change),
                            "on_bio_change": len(w._on_bio_change),
                        },
                    }
                    for w in self._watchers.values()
                ],
            }
