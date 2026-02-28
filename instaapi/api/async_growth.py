"""
Async Growth API — Smart Follow/Unfollow System
=================================================
Async version of GrowthAPI. Full feature parity.
"""

import asyncio
import logging
import random
from typing import Any, Callable, Dict, List, Optional, Set, Union

from .growth import GrowthFilters, GrowthLimits

logger = logging.getLogger("instaapi.growth")


class AsyncGrowthAPI:
    """
    Async smart follow/unfollow system with safety limits.

    Composes: AsyncUsersAPI, AsyncFriendshipsAPI.
    """

    def __init__(self, client, users_api, friendships_api):
        self._client = client
        self._users = users_api
        self._friendships = friendships_api
        self._whitelist: Set[str] = set()
        self._blacklist: Set[str] = set()

    async def follow_users_of(
        self,
        username: str,
        count: int = 20,
        filters: Optional[Union[GrowthFilters, Dict]] = None,
        limits: Optional[GrowthLimits] = None,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Follow followers of a target user (competitor).

        Args:
            username: Target user whose followers to follow
            count: How many to follow
            filters: GrowthFilters or dict with filter params
            limits: GrowthLimits
            on_progress: Callback(followed, total, username)

        Returns:
            dict: {followed, skipped, errors, duration_seconds}
        """
        limits = limits or GrowthLimits()
        if isinstance(filters, dict):
            filters = GrowthFilters(**filters)

        user = await self._users.get_by_username(username)
        user_id = user.pk if hasattr(user, "pk") else user.get("pk", 0)
        if not user_id:
            return {"followed": 0, "error": f"User '{username}' not found"}

        result = await self._friendships.get_followers(user_id, count=count * 3)
        candidates = result.get("users", [])

        followed = 0
        skipped = 0
        errors = 0
        import time
        start = time.time()

        for candidate in candidates:
            if followed >= count:
                break
            uname = candidate.get("username", "")
            if uname in self._blacklist or uname in self._whitelist:
                skipped += 1
                continue
            if filters and not filters.matches(candidate):
                skipped += 1
                continue
            cid = candidate.get("pk") or candidate.get("id")
            if not cid:
                continue
            try:
                await self._friendships.follow(cid)
                followed += 1
                if on_progress:
                    on_progress(followed, count, uname)
                await self._smart_delay(limits)
            except Exception as e:
                errors += 1
                if self._should_stop(e, limits):
                    break

        return {
            "followed": followed, "skipped": skipped, "errors": errors,
            "source": username, "duration_seconds": round(time.time() - start, 1),
        }

    async def unfollow_non_followers(
        self,
        max_count: int = 50,
        whitelist: Optional[List[str]] = None,
        limits: Optional[GrowthLimits] = None,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Unfollow users who don't follow you back.

        Args:
            max_count: Max users to unfollow
            whitelist: Usernames to never unfollow
            limits: GrowthLimits

        Returns:
            dict: {unfollowed, skipped, duration_seconds}
        """
        limits = limits or GrowthLimits()
        keep = set(whitelist or []) | self._whitelist
        non_followers = await self.get_non_followers()

        unfollowed = 0
        skipped = 0
        import time
        start = time.time()

        for user in non_followers:
            if unfollowed >= max_count:
                break
            uname = user.get("username", "")
            if uname in keep:
                skipped += 1
                continue
            uid = user.get("pk") or user.get("id")
            if not uid:
                continue
            try:
                await self._friendships.unfollow(uid)
                unfollowed += 1
                if on_progress:
                    on_progress(unfollowed, max_count, uname)
                await self._smart_delay(limits)
            except Exception as e:
                if self._should_stop(e, limits):
                    break

        return {
            "unfollowed": unfollowed, "skipped": skipped,
            "duration_seconds": round(time.time() - start, 1),
        }

    async def get_non_followers(self) -> List[Dict]:
        """
        Get list of users you follow but don't follow you back.

        Returns:
            List of user dicts
        """
        sm = getattr(self._client, "_session_mgr", None)
        my_id = str(getattr(sm.get_session(), "ds_user_id", "")) if sm else ""
        if not my_id:
            return []

        following_result = await self._friendships.get_following(my_id, count=200)
        followers_result = await self._friendships.get_followers(my_id, count=200)

        follower_set = {u.get("username") for u in followers_result.get("users", [])}
        non = [u for u in following_result.get("users", []) if u.get("username") not in follower_set]
        return non

    async def get_fans(self) -> List[Dict]:
        """
        Get fans — followers you don't follow back.

        Returns:
            List of user dicts
        """
        sm = getattr(self._client, "_session_mgr", None)
        my_id = str(getattr(sm.get_session(), "ds_user_id", "")) if sm else ""
        if not my_id:
            return []

        following_result = await self._friendships.get_following(my_id, count=200)
        followers_result = await self._friendships.get_followers(my_id, count=200)

        following_set = {u.get("username") for u in following_result.get("users", [])}
        fans = [u for u in followers_result.get("users", []) if u.get("username") not in following_set]
        return fans

    def add_whitelist(self, usernames: List[str]) -> None:
        """Add usernames to whitelist (never unfollow)."""
        self._whitelist.update(usernames)

    def add_blacklist(self, usernames: List[str]) -> None:
        """Add usernames to blacklist (never follow)."""
        self._blacklist.update(usernames)

    def clear_whitelist(self) -> None:
        self._whitelist.clear()

    def clear_blacklist(self) -> None:
        self._blacklist.clear()

    async def _smart_delay(self, limits: GrowthLimits) -> None:
        """Human-like async delay."""
        delay = random.uniform(limits.min_delay, limits.max_delay)
        if random.random() < 0.1:
            delay += random.uniform(10, 40)
        await asyncio.sleep(delay)

    @staticmethod
    def _should_stop(error: Exception, limits: GrowthLimits) -> bool:
        """Check if we should stop based on error type."""
        name = type(error).__name__
        if limits.stop_on_rate_limit and name == "RateLimitError":
            return True
        if limits.stop_on_challenge and name in ("ChallengeRequired", "CheckpointRequired"):
            return True
        if name == "LoginRequired":
            return True
        return False
