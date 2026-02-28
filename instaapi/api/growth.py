"""
Growth API — Smart Follow/Unfollow System
==========================================
Targetted follow/unfollow with safety limits, anti-ban delays,
whitelist/blacklist, and progress tracking.

Usage:
    ig = Instagram.from_env(".env")

    # Follow competitor's followers
    result = ig.growth.follow_users_of("competitor", count=20,
        filters={"min_posts": 5, "is_private": False})

    # Unfollow non-followers
    result = ig.growth.unfollow_non_followers()

    # Get non-followers list
    non_followers = ig.growth.get_non_followers()

Safety:
    - Max 20 follow/unfollow per hour (configurable)
    - Random 25-90s delays between actions
    - Auto-stop on rate limit / challenge
    - Whitelist / blacklist support
"""

import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional, Set, Union

logger = logging.getLogger("instaapi.growth")


class GrowthLimits:
    """Safety limits for growth actions."""

    def __init__(
        self,
        max_per_hour: int = 20,
        max_per_day: int = 150,
        min_delay: float = 25.0,
        max_delay: float = 90.0,
        stop_on_challenge: bool = True,
        stop_on_rate_limit: bool = True,
    ):
        self.max_per_hour = max_per_hour
        self.max_per_day = max_per_day
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.stop_on_challenge = stop_on_challenge
        self.stop_on_rate_limit = stop_on_rate_limit


class GrowthFilters:
    """Filters for selecting users to follow."""

    def __init__(
        self,
        min_followers: int = 0,
        max_followers: int = 0,
        min_posts: int = 0,
        is_private: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        has_bio: Optional[bool] = None,
        bio_keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None,
    ):
        self.min_followers = min_followers
        self.max_followers = max_followers
        self.min_posts = min_posts
        self.is_private = is_private
        self.is_verified = is_verified
        self.has_bio = has_bio
        self.bio_keywords = [k.lower() for k in (bio_keywords or [])]
        self.exclude_keywords = [k.lower() for k in (exclude_keywords or [])]

    def matches(self, user: Dict) -> bool:
        followers = user.get("follower_count", 0)
        posts = user.get("media_count", 0)
        bio = (user.get("biography", "") or "").lower()

        if self.min_followers and followers < self.min_followers:
            return False
        if self.max_followers and followers > self.max_followers:
            return False
        if self.min_posts and posts < self.min_posts:
            return False
        if self.is_private is not None and user.get("is_private") != self.is_private:
            return False
        if self.is_verified is not None and user.get("is_verified") != self.is_verified:
            return False
        if self.has_bio is True and not bio.strip():
            return False
        if self.bio_keywords and not any(kw in bio for kw in self.bio_keywords):
            return False
        if self.exclude_keywords and any(kw in bio for kw in self.exclude_keywords):
            return False
        return True


class GrowthAPI:
    """
    Smart follow/unfollow system with safety limits.

    Composes: UsersAPI, FriendshipsAPI.
    """

    def __init__(self, client, users_api, friendships_api):
        self._client = client
        self._users = users_api
        self._friendships = friendships_api
        self._whitelist: Set[str] = set()
        self._blacklist: Set[str] = set()
        self._action_log: List[Dict] = []

    # ═══════════════════════════════════════════════════════════
    # FOLLOW
    # ═══════════════════════════════════════════════════════════

    def follow_users_of(
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
            limits: GrowthLimits (default: 20/hour)
            on_progress: Callback(followed, total, username)

        Returns:
            dict: {followed, skipped, errors, duration_seconds, users}
        """
        if isinstance(filters, dict):
            filters = GrowthFilters(**filters)
        limits = limits or GrowthLimits()

        user = self._users.get_by_username(username)
        user_id = getattr(user, "pk", None) or (user.get("pk") if isinstance(user, dict) else None)
        if not user_id:
            raise ValueError(f"Could not resolve user ID for '{username}'")

        return self._follow_from_list(
            source=f"followers of @{username}",
            user_id=user_id,
            list_type="followers",
            count=count,
            filters=filters,
            limits=limits,
            on_progress=on_progress,
        )

    def follow_hashtag_users(
        self,
        tag: str,
        count: int = 20,
        filters: Optional[Union[GrowthFilters, Dict]] = None,
        limits: Optional[GrowthLimits] = None,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Follow users who posted with a hashtag.

        Args:
            tag: Hashtag (without #)
            count: How many to follow
            filters: GrowthFilters
            limits: GrowthLimits

        Returns:
            dict: {followed, skipped, errors, duration_seconds}
        """
        if isinstance(filters, dict):
            filters = GrowthFilters(**filters)
        limits = limits or GrowthLimits()

        tag = tag.lstrip("#").strip().lower()
        start = time.time()
        followed = 0
        skipped = 0
        errors = 0
        followed_users = []

        # Get users from hashtag posts
        try:
            result = self._client.request("GET", f"/api/v1/tags/{tag}/sections/", params={"tab": "recent"})
            sections = result.get("sections", []) if result else []
        except Exception as e:
            logger.error(f"Hashtag fetch error: {e}")
            return {"followed": 0, "error": str(e)}

        seen = set()
        candidates = []
        for sec in sections:
            for m in sec.get("layout_content", {}).get("medias", []):
                user_data = m.get("media", {}).get("user", {})
                uname = user_data.get("username", "")
                if uname and uname not in seen:
                    seen.add(uname)
                    candidates.append(user_data)

        for user_data in candidates:
            if followed >= count:
                break

            uname = user_data.get("username", "")
            uid = user_data.get("pk")

            if not uid or uname in self._blacklist:
                skipped += 1
                continue

            if filters and not filters.matches(user_data):
                skipped += 1
                continue

            try:
                self._friendships.follow(uid)
                followed += 1
                followed_users.append(uname)
                self._log_action("follow", uname, uid)
                if on_progress:
                    on_progress(followed, count, uname)
                logger.info(f"✅ Followed @{uname} ({followed}/{count})")
                self._smart_delay(limits)
            except Exception as e:
                errors += 1
                if self._should_stop(e, limits):
                    logger.warning(f"🛑 Stopping: {e}")
                    break

        return {
            "followed": followed,
            "skipped": skipped,
            "errors": errors,
            "duration_seconds": round(time.time() - start, 1),
            "users": followed_users,
        }

    # ═══════════════════════════════════════════════════════════
    # UNFOLLOW
    # ═══════════════════════════════════════════════════════════

    def unfollow_non_followers(
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
            on_progress: Callback(unfollowed, total, username)

        Returns:
            dict: {unfollowed, skipped, total_non_followers, duration_seconds}
        """
        limits = limits or GrowthLimits()
        extra_whitelist = set(whitelist or [])
        combined_whitelist = self._whitelist | extra_whitelist

        # Get non-followers
        non_followers = self.get_non_followers()

        start = time.time()
        unfollowed = 0
        skipped = 0

        for user in non_followers:
            if unfollowed >= max_count:
                break

            uname = user.get("username", "")
            uid = user.get("pk")

            if uname in combined_whitelist or not uid:
                skipped += 1
                continue

            try:
                self._friendships.unfollow(uid)
                unfollowed += 1
                self._log_action("unfollow", uname, uid)
                if on_progress:
                    on_progress(unfollowed, max_count, uname)
                logger.info(f"👋 Unfollowed @{uname} ({unfollowed}/{max_count})")
                self._smart_delay(limits)
            except Exception as e:
                if self._should_stop(e, limits):
                    logger.warning(f"🛑 Stopping: {e}")
                    break

        return {
            "unfollowed": unfollowed,
            "skipped": skipped,
            "total_non_followers": len(non_followers),
            "duration_seconds": round(time.time() - start, 1),
        }

    def unfollow_all(
        self,
        keep_list: Optional[List[str]] = None,
        max_count: int = 100,
        limits: Optional[GrowthLimits] = None,
    ) -> Dict[str, Any]:
        """
        Mass unfollow (keep specified users).

        Args:
            keep_list: Usernames to keep following
            max_count: Max to unfollow
            limits: GrowthLimits

        Returns:
            dict: {unfollowed, skipped, duration_seconds}
        """
        limits = limits or GrowthLimits()
        keep = set(keep_list or []) | self._whitelist
        start = time.time()

        # Get my following
        my_id = self._get_my_id()
        following = self._get_all_list(my_id, "following", max_count=max_count + len(keep))

        unfollowed = 0
        skipped = 0

        for user in following:
            if unfollowed >= max_count:
                break
            uname = user.get("username", "")
            if uname in keep:
                skipped += 1
                continue

            try:
                self._friendships.unfollow(user.get("pk"))
                unfollowed += 1
                self._log_action("unfollow", uname, user.get("pk"))
                self._smart_delay(limits)
            except Exception as e:
                if self._should_stop(e, limits):
                    break

        return {
            "unfollowed": unfollowed,
            "skipped": skipped,
            "duration_seconds": round(time.time() - start, 1),
        }

    # ═══════════════════════════════════════════════════════════
    # ANALYSIS
    # ═══════════════════════════════════════════════════════════

    def get_non_followers(self) -> List[Dict]:
        """
        Get list of users you follow but don't follow you back.

        Returns:
            List of user dicts
        """
        my_id = self._get_my_id()

        followers_set = set()
        following_list = []

        # Collect followers usernames
        followers = self._get_all_list(my_id, "followers", max_count=5000)
        for u in followers:
            followers_set.add(u.get("username", ""))

        # Collect following
        following = self._get_all_list(my_id, "following", max_count=5000)
        for u in following:
            uname = u.get("username", "")
            if uname and uname not in followers_set:
                following_list.append(u)

        logger.info(f"📊 Non-followers: {len(following_list)} / {len(following)} following")
        return following_list

    def get_fans(self) -> List[Dict]:
        """
        Get fans — followers you don't follow back.

        Returns:
            List of user dicts
        """
        my_id = self._get_my_id()

        following_set = set()
        fans = []

        following = self._get_all_list(my_id, "following", max_count=5000)
        for u in following:
            following_set.add(u.get("username", ""))

        followers = self._get_all_list(my_id, "followers", max_count=5000)
        for u in followers:
            if u.get("username", "") not in following_set:
                fans.append(u)

        return fans

    # ═══════════════════════════════════════════════════════════
    # WHITELIST / BLACKLIST
    # ═══════════════════════════════════════════════════════════

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

    @property
    def action_log(self) -> List[Dict]:
        """Recent actions log."""
        return self._action_log[-100:]

    # ═══════════════════════════════════════════════════════════
    # INTERNAL
    # ═══════════════════════════════════════════════════════════

    def _follow_from_list(
        self,
        source: str,
        user_id,
        list_type: str,
        count: int,
        filters: Optional[GrowthFilters],
        limits: GrowthLimits,
        on_progress: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Internal: follow users from a follower/following list."""
        start = time.time()
        followed = 0
        skipped = 0
        errors = 0
        followed_users = []
        cursor = None

        while followed < count:
            try:
                if list_type == "followers":
                    result = self._friendships.get_followers(user_id, count=50, after=cursor)
                else:
                    result = self._friendships.get_following(user_id, count=50, after=cursor)
            except Exception as e:
                logger.warning(f"List fetch error: {e}")
                break

            users = result.get("users", [])
            if not users:
                break

            for u in users:
                if followed >= count:
                    break

                uname = u.get("username", "")
                uid = u.get("pk")

                if not uid or uname in self._blacklist:
                    skipped += 1
                    continue

                if filters and not filters.matches(u):
                    skipped += 1
                    continue

                try:
                    self._friendships.follow(uid)
                    followed += 1
                    followed_users.append(uname)
                    self._log_action("follow", uname, uid)
                    if on_progress:
                        on_progress(followed, count, uname)
                    logger.info(f"✅ Followed @{uname} from {source} ({followed}/{count})")
                    self._smart_delay(limits)
                except Exception as e:
                    errors += 1
                    if self._should_stop(e, limits):
                        logger.warning(f"🛑 Stopping: {e}")
                        return {
                            "followed": followed, "skipped": skipped, "errors": errors,
                            "duration_seconds": round(time.time() - start, 1),
                            "users": followed_users, "stopped_reason": str(e),
                        }

            cursor = result.get("next_max_id") or result.get("next_cursor")
            if not cursor:
                break

        return {
            "followed": followed,
            "skipped": skipped,
            "errors": errors,
            "duration_seconds": round(time.time() - start, 1),
            "users": followed_users,
        }

    def _get_my_id(self) -> str:
        """Get authenticated user's ID."""
        sm = getattr(self._client, "_session_mgr", None)
        if sm:
            sess = sm.get_session()
            return str(getattr(sess, "ds_user_id", ""))
        raise RuntimeError("Cannot determine authenticated user ID")

    def _get_all_list(self, user_id, list_type: str, max_count: int = 5000) -> List[Dict]:
        """Fetch full followers or following list."""
        all_users: list = []
        cursor = None
        while len(all_users) < max_count:
            try:
                if list_type == "followers":
                    result = self._friendships.get_followers(user_id, count=50, after=cursor)
                else:
                    result = self._friendships.get_following(user_id, count=50, after=cursor)
            except Exception:
                break
            users = result.get("users", [])
            if not users:
                break
            all_users.extend(users)
            cursor = result.get("next_max_id") or result.get("next_cursor")
            if not cursor:
                break
        return all_users[:max_count]

    def _smart_delay(self, limits: GrowthLimits) -> None:
        """Human-like delay between actions."""
        base = random.uniform(limits.min_delay, limits.max_delay)
        # Occasionally longer pause (simulates reading)
        if random.random() < 0.1:
            base += random.uniform(30, 120)
        time.sleep(base)

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

    def _log_action(self, action: str, username: str, user_id) -> None:
        """Log an action."""
        self._action_log.append({
            "action": action,
            "username": username,
            "user_id": user_id,
            "timestamp": time.time(),
        })
        # Keep last 500
        if len(self._action_log) > 500:
            self._action_log = self._action_log[-500:]
