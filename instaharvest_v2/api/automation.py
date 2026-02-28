"""
Automation API — Bot Framework
===============================
Auto DM, auto-comment, auto-like with templates,
safety limits, and human-like behavior.

Usage:
    ig = Instagram.from_env(".env")

    # Welcome DM to new followers
    ig.automation.dm_new_followers("Welcome! Thanks for following 👋")

    # Auto-comment on hashtag posts
    ig.automation.comment_on_hashtag("python", [
        "Great post! 🔥",
        "Love this! 💯",
        "Amazing content! 🚀",
    ], count=10)

    # Auto-like feed
    ig.automation.auto_like_feed(count=20)

    # Watch stories
    ig.automation.watch_stories("cristiano")
"""

import logging
import random
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Union

logger = logging.getLogger("instaharvest_v2.automation")


class AutomationLimits:
    """Safety limits for automation actions."""

    def __init__(
        self,
        max_per_hour: int = 30,
        min_delay: float = 15.0,
        max_delay: float = 60.0,
        stop_on_challenge: bool = True,
        stop_on_rate_limit: bool = True,
    ):
        self.max_per_hour = max_per_hour
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.stop_on_challenge = stop_on_challenge
        self.stop_on_rate_limit = stop_on_rate_limit


class TemplateEngine:
    """
    Simple template engine with variables and randomization.

    Supports:
        - {username} — target username
        - {name} — target full name or username
        - {random} — random emoji from predefined set
        - Multiple templates (random selection)
    """

    EMOJIS = ["🔥", "💯", "👏", "✨", "🚀", "💪", "❤️", "👍", "⭐", "🎯"]

    @classmethod
    def render(cls, template: str, context: Optional[Dict[str, str]] = None) -> str:
        """Render a template with variables."""
        ctx = context or {}
        text = template
        text = text.replace("{username}", ctx.get("username", ""))
        text = text.replace("{name}", ctx.get("name", ctx.get("username", "")))
        text = text.replace("{random}", random.choice(cls.EMOJIS))
        if "{date}" in text:
            text = text.replace("{date}", datetime.now().strftime("%Y-%m-%d"))
        return text

    @classmethod
    def pick_and_render(cls, templates: List[str], context: Optional[Dict[str, str]] = None) -> str:
        """Pick a random template and render it."""
        template = random.choice(templates)
        return cls.render(template, context)


class AutomationAPI:
    """
    Instagram automation bot framework.

    Composes: DirectAPI, MediaAPI, FriendshipsAPI, HashtagsAPI, StoriesAPI.
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

    # ═══════════════════════════════════════════════════════════
    # AUTO DM
    # ═══════════════════════════════════════════════════════════

    def dm_new_followers(
        self,
        templates: Union[str, List[str]],
        max_count: int = 10,
        limits: Optional[AutomationLimits] = None,
        on_progress: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Send welcome DM to new followers.

        Args:
            templates: Message template(s). Supports {username}, {name}, {random}
            max_count: Max DMs to send
            limits: AutomationLimits
            on_progress: Callback(sent_count, username)

        Returns:
            dict: {sent, errors, new_followers_found, duration_seconds}
        """
        if isinstance(templates, str):
            templates = [templates]
        limits = limits or AutomationLimits()

        start = time.time()
        sent = 0
        errors = 0

        # Get current followers
        my_id = self._get_my_id()
        current_followers = self._get_followers_set(my_id)

        # Find new followers
        new_followers = current_followers - self._known_followers if self._known_followers else set()
        if not self._known_followers:
            # First run — save current followers, don't DM
            self._known_followers = current_followers
            logger.info(f"📋 Saved {len(current_followers)} current followers. Will DM new ones next time.")
            return {"sent": 0, "new_followers_found": 0, "note": "First run — saved baseline", "duration_seconds": 0}

        logger.info(f"🆕 {len(new_followers)} new followers detected")

        # Get user details and send DMs
        for username in list(new_followers)[:max_count]:
            if username in self._seen_users:
                continue

            try:
                user = self._users_get_safe(username)
                context = {
                    "username": username,
                    "name": user.get("full_name", username) if isinstance(user, dict) else username,
                }
                message = TemplateEngine.pick_and_render(templates, context)

                # Send DM
                user_id = user.get("pk") if isinstance(user, dict) else None
                if user_id:
                    self._direct.send_text(user_id, message)
                    sent += 1
                    self._seen_users.add(username)
                    self._log_action("dm", username, message[:50])
                    if on_progress:
                        on_progress(sent, username)
                    logger.info(f"💬 DM sent to @{username} ({sent}/{max_count})")
                    self._smart_delay(limits)

            except Exception as e:
                errors += 1
                if self._should_stop(e, limits):
                    logger.warning(f"🛑 Stopping DMs: {e}")
                    break
                logger.debug(f"DM to @{username} failed: {e}")

        # Update known followers
        self._known_followers = current_followers

        return {
            "sent": sent,
            "errors": errors,
            "new_followers_found": len(new_followers),
            "duration_seconds": round(time.time() - start, 1),
        }

    # ═══════════════════════════════════════════════════════════
    # AUTO COMMENT
    # ═══════════════════════════════════════════════════════════

    def comment_on_hashtag(
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
            templates: Comment templates (random pick). Supports {username}, {random}
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

        # Fetch hashtag posts
        posts = self._get_hashtag_posts(tag, count * 2)

        for post in posts:
            if commented >= count:
                break

            media_id = post.get("pk") or post.get("id")
            shortcode = post.get("code", "")
            owner = post.get("user", {})
            if not media_id:
                continue

            context = {
                "username": owner.get("username", ""),
                "name": owner.get("full_name", owner.get("username", "")),
            }
            comment_text = TemplateEngine.pick_and_render(templates, context)

            try:
                self._media.comment(media_id, comment_text)
                commented += 1
                self._log_action("comment", shortcode, comment_text[:50])
                if on_progress:
                    on_progress(commented, shortcode)
                logger.info(f"💬 Commented on {shortcode} ({commented}/{count})")
                self._smart_delay(limits)
            except Exception as e:
                errors += 1
                if self._should_stop(e, limits):
                    logger.warning(f"🛑 Stopping comments: {e}")
                    break
                logger.debug(f"Comment on {shortcode} failed: {e}")

        return {
            "commented": commented,
            "errors": errors,
            "hashtag": tag,
            "duration_seconds": round(time.time() - start, 1),
        }

    # ═══════════════════════════════════════════════════════════
    # AUTO LIKE
    # ═══════════════════════════════════════════════════════════

    def auto_like_feed(
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
            result = self._client.request("GET", "/api/v1/feed/timeline/", params={"count": str(count * 2)})
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
                self._media.like(media_id)
                liked += 1
                self._log_action("like", shortcode, "")
                if on_progress:
                    on_progress(liked, shortcode)
                logger.info(f"❤️ Liked {shortcode} ({liked}/{count})")
                self._smart_delay(limits)
            except Exception as e:
                errors += 1
                if self._should_stop(e, limits):
                    break

        return {
            "liked": liked,
            "errors": errors,
            "duration_seconds": round(time.time() - start, 1),
        }

    def auto_like_hashtag(
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

        posts = self._get_hashtag_posts(tag, count * 2)

        for post in posts:
            if liked >= count:
                break

            media_id = post.get("pk") or post.get("id")
            shortcode = post.get("code", "")

            if not media_id or post.get("has_liked"):
                continue

            try:
                self._media.like(media_id)
                liked += 1
                self._log_action("like", shortcode, f"#{tag}")
                if on_progress:
                    on_progress(liked, shortcode)
                logger.info(f"❤️ Liked #{tag} — {shortcode} ({liked}/{count})")
                self._smart_delay(limits)
            except Exception as e:
                errors += 1
                if self._should_stop(e, limits):
                    break

        return {
            "liked": liked,
            "errors": errors,
            "hashtag": tag,
            "duration_seconds": round(time.time() - start, 1),
        }

    # ═══════════════════════════════════════════════════════════
    # WATCH STORIES
    # ═══════════════════════════════════════════════════════════

    def watch_stories(
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
            user = self._users_get_safe(username)
            user_id = user.get("pk") if isinstance(user, dict) else None
            if not user_id:
                return {"watched": 0, "error": f"User '{username}' not found"}

            stories = self._stories.get_user_stories(user_id)
            items = stories.get("items", []) if isinstance(stories, dict) else []

            # Mark as seen
            seen_count = 0
            for item in items:
                story_id = item.get("pk") or item.get("id")
                if story_id:
                    try:
                        self._stories.mark_seen(story_id, user_id)
                        seen_count += 1
                        self._smart_delay(limits, factor=0.3)
                    except Exception:
                        pass

            self._log_action("watch_stories", username, f"{seen_count} stories")
            logger.info(f"👁️ Watched {seen_count} stories of @{username}")
            return {"watched": seen_count, "username": username}

        except Exception as e:
            return {"watched": 0, "error": str(e)}

    # ═══════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════

    def _get_my_id(self) -> str:
        sm = getattr(self._client, "_session_mgr", None)
        if sm:
            sess = sm.get_session()
            return str(getattr(sess, "ds_user_id", ""))
        raise RuntimeError("Cannot determine authenticated user ID")

    def _get_followers_set(self, user_id) -> Set[str]:
        """Get followers as a set of usernames."""
        followers = set()
        cursor = None
        while True:
            try:
                result = self._friendships.get_followers(user_id, count=50, after=cursor)
                for u in result.get("users", []):
                    followers.add(u.get("username", ""))
                cursor = result.get("next_max_id")
                if not cursor:
                    break
            except Exception:
                break
        return followers

    def _users_get_safe(self, username: str) -> Dict:
        """Get user info safely, returning dict."""
        try:
            user = self._client.request("GET", "/api/v1/users/web_profile_info/", params={"username": username})
            if isinstance(user, dict):
                return user.get("data", {}).get("user", user)
            return {"username": username}
        except Exception:
            return {"username": username}

    def _get_hashtag_posts(self, tag: str, count: int) -> List[Dict]:
        """Get posts from hashtag."""
        posts = []
        try:
            result = self._client.request("GET", f"/api/v1/tags/{tag}/sections/", params={"tab": "recent"})
            if result and isinstance(result, dict):
                for sec in result.get("sections", []):
                    for m in sec.get("layout_content", {}).get("medias", []):
                        media = m.get("media", {})
                        if media:
                            posts.append(media)
        except Exception as e:
            logger.debug(f"Hashtag posts fetch error: {e}")
        return posts[:count]

    def _smart_delay(self, limits: AutomationLimits, factor: float = 1.0) -> None:
        """Human-like delay between actions."""
        base = random.uniform(limits.min_delay, limits.max_delay) * factor
        # 10% chance of a micro-break
        if random.random() < 0.1:
            base += random.uniform(20, 60)
        time.sleep(base)

    @staticmethod
    def _should_stop(error: Exception, limits: AutomationLimits) -> bool:
        name = type(error).__name__
        if limits.stop_on_rate_limit and name == "RateLimitError":
            return True
        if limits.stop_on_challenge and name in ("ChallengeRequired", "CheckpointRequired"):
            return True
        if name == "LoginRequired":
            return True
        return False

    def _log_action(self, action: str, target: str, detail: str) -> None:
        self._action_log.append({
            "action": action,
            "target": target,
            "detail": detail,
            "timestamp": time.time(),
        })
        if len(self._action_log) > 500:
            self._action_log = self._action_log[-500:]

    @property
    def action_log(self) -> List[Dict]:
        return self._action_log[-100:]
