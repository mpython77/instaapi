"""
Async Automation API — Bot Framework
======================================
Async version of AutomationAPI. Full feature parity.
"""

import asyncio
import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional, Set, Union

from .automation import AutomationLimits, TemplateEngine

logger = logging.getLogger("instaharvest_v2.automation")


class AsyncAutomationAPI:
    """
    Async Instagram automation bot framework.

    Composes: AsyncDirectAPI, AsyncMediaAPI, AsyncFriendshipsAPI, AsyncStoriesAPI.
    """

    def __init__(self, client, direct_api, media_api, friendships_api, stories_api=None):
        self._client = client
        self._direct = direct_api
        self._media = media_api
        self._friendships = friendships_api
        self._stories = stories_api
        self._seen_users: Set[str] = set()
        self._known_followers: Set[str] = set()
        self._action_log: List[Dict] = []

    async def comment_on_hashtag(
        self,
        tag: str,
        templates: List[str],
        count: int = 10,
        limits: Optional[AutomationLimits] = None,
        on_progress: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Auto-comment on hashtag posts.

        Args:
            tag: Hashtag (without #)
            templates: Comment templates (random pick)
            count: Posts to comment on
            limits: AutomationLimits
            on_progress: Callback(count, shortcode)

        Returns:
            dict: {commented, errors, duration_seconds}
        """
        limits = limits or AutomationLimits()
        tag = tag.lstrip("#").strip().lower()
        start = time.time()
        commented = 0
        errors = 0

        posts = await self._get_hashtag_posts(tag, count * 2)
        for post in posts:
            if commented >= count:
                break
            media_id = post.get("pk") or post.get("id")
            shortcode = post.get("code", "")
            owner = post.get("user", {})
            if not media_id:
                continue

            context = {"username": owner.get("username", ""), "name": owner.get("full_name", owner.get("username", ""))}
            comment_text = TemplateEngine.pick_and_render(templates, context)

            try:
                await self._media.comment(media_id, comment_text)
                commented += 1
                self._log_action("comment", shortcode, comment_text[:50])
                if on_progress:
                    on_progress(commented, shortcode)
                await self._smart_delay(limits)
            except Exception as e:
                errors += 1
                if self._should_stop(e, limits):
                    break

        return {"commented": commented, "errors": errors, "hashtag": tag, "duration_seconds": round(time.time() - start, 1)}

    async def auto_like_feed(
        self,
        count: int = 20,
        limits: Optional[AutomationLimits] = None,
        on_progress: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Auto-like posts from your timeline feed.

        Args:
            count: Posts to like
            limits: AutomationLimits
            on_progress: Callback(liked_count, shortcode)

        Returns:
            dict: {liked, errors, duration_seconds}
        """
        limits = limits or AutomationLimits()
        start = time.time()
        liked = 0
        errors = 0

        try:
            result = await self._client.get("/feed/timeline/", params={"count": str(count * 2)}, rate_category="get_feed")
            items = result.get("feed_items", []) if result else []
        except Exception as e:
            return {"liked": 0, "error": str(e)}

        for item in items:
            if liked >= count:
                break
            media = item.get("media_or_ad") or item
            media_id = media.get("pk") or media.get("id")
            shortcode = media.get("code", "")
            if not media_id or media.get("has_liked"):
                continue
            try:
                await self._media.like(media_id)
                liked += 1
                self._log_action("like", shortcode, "")
                if on_progress:
                    on_progress(liked, shortcode)
                await self._smart_delay(limits)
            except Exception as e:
                errors += 1
                if self._should_stop(e, limits):
                    break

        return {"liked": liked, "errors": errors, "duration_seconds": round(time.time() - start, 1)}

    async def auto_like_hashtag(
        self,
        tag: str,
        count: int = 20,
        limits: Optional[AutomationLimits] = None,
        on_progress: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Auto-like posts from a hashtag.

        Args:
            tag: Hashtag (without #)
            count: Posts to like
            limits: AutomationLimits

        Returns:
            dict: {liked, errors, hashtag, duration_seconds}
        """
        limits = limits or AutomationLimits()
        tag = tag.lstrip("#").strip().lower()
        start = time.time()
        liked = 0
        errors = 0

        posts = await self._get_hashtag_posts(tag, count * 2)
        for post in posts:
            if liked >= count:
                break
            media_id = post.get("pk") or post.get("id")
            shortcode = post.get("code", "")
            if not media_id or post.get("has_liked"):
                continue
            try:
                await self._media.like(media_id)
                liked += 1
                self._log_action("like", shortcode, f"#{tag}")
                if on_progress:
                    on_progress(liked, shortcode)
                await self._smart_delay(limits)
            except Exception as e:
                errors += 1
                if self._should_stop(e, limits):
                    break

        return {"liked": liked, "errors": errors, "hashtag": tag, "duration_seconds": round(time.time() - start, 1)}

    async def watch_stories(
        self,
        username: str,
        limits: Optional[AutomationLimits] = None,
    ) -> Dict[str, Any]:
        """
        Watch all stories of a user.

        Args:
            username: Target username
            limits: AutomationLimits

        Returns:
            dict: {watched, username}
        """
        limits = limits or AutomationLimits()
        if not self._stories:
            return {"watched": 0, "error": "StoriesAPI not available"}
        try:
            user = await self._users_get_safe(username)
            user_id = user.get("pk") if isinstance(user, dict) else None
            if not user_id:
                return {"watched": 0, "error": f"User '{username}' not found"}
            stories = await self._stories.get_user_stories(user_id)
            items = stories.get("items", []) if isinstance(stories, dict) else []
            seen_count = 0
            for item in items:
                story_id = item.get("pk") or item.get("id")
                if story_id:
                    try:
                        await self._stories.mark_seen(story_id, user_id)
                        seen_count += 1
                        await self._smart_delay(limits, factor=0.3)
                    except Exception:
                        pass
            self._log_action("watch_stories", username, f"{seen_count} stories")
            return {"watched": seen_count, "username": username}
        except Exception as e:
            return {"watched": 0, "error": str(e)}

    # ─── Helpers ─────────────────────────────────────────────────

    async def _get_hashtag_posts(self, tag: str, count: int) -> List[Dict]:
        """Get posts from hashtag."""
        posts = []
        try:
            result = await self._client.get(f"/tags/{tag}/sections/", params={"tab": "recent"}, rate_category="get_default")
            if result and isinstance(result, dict):
                for sec in result.get("sections", []):
                    for m in sec.get("layout_content", {}).get("medias", []):
                        media = m.get("media", {})
                        if media:
                            posts.append(media)
        except Exception as e:
            logger.debug(f"Hashtag posts fetch error: {e}")
        return posts[:count]

    async def _users_get_safe(self, username: str) -> Dict:
        """Get user info safely, returning dict."""
        try:
            user = await self._client.get("/users/web_profile_info/", params={"username": username}, rate_category="get_profile")
            if isinstance(user, dict):
                return user.get("data", {}).get("user", user)
            return {"username": username}
        except Exception:
            return {"username": username}

    async def _smart_delay(self, limits: AutomationLimits, factor: float = 1.0) -> None:
        """Human-like async delay between actions."""
        base = random.uniform(limits.min_delay, limits.max_delay) * factor
        if random.random() < 0.1:
            base += random.uniform(20, 60)
        await asyncio.sleep(base)

    @staticmethod
    def _should_stop(error: Exception, limits: AutomationLimits) -> bool:
        """Check if we should stop based on error type."""
        name = type(error).__name__
        if limits.stop_on_rate_limit and name == "RateLimitError":
            return True
        if limits.stop_on_challenge and name in ("ChallengeRequired", "CheckpointRequired"):
            return True
        if name == "LoginRequired":
            return True
        return False

    def _log_action(self, action: str, target: str, detail: str) -> None:
        """Log an action."""
        self._action_log.append({"action": action, "target": target, "detail": detail, "timestamp": time.time()})
        if len(self._action_log) > 500:
            self._action_log = self._action_log[-500:]

    @property
    def action_log(self) -> List[Dict]:
        """Recent action log."""
        return self._action_log[-100:]
