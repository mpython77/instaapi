"""
Notifications API
=================
Instagram notifications and activity feed.
/news/inbox/ endpoint — works via POST method.

Response structure:
    - counts: 15 category counters (likes, comments, relationships, ...)
    - new_stories: Unread notifications
    - old_stories: Old notifications
    - continuation_token: Token for pagination
    - is_last_page: Whether this is the last page
    - partition: "Today", "This week", "This month", "Earlier" categories

Each story/notification structure:
    - story_type: 101 (user_followed), 13 (comment_like), 1487 (threads), 95008 (system)
    - notif_name: "user_followed", "comment_like", "like", "qp_ig_nf_generic", ...
    - type: numeric type (1, 3, 4, 13, 20)
    - args:
        - text: Plain text version
        - rich_text: Formatted text
        - profile_id, profile_name, profile_image: From whom
        - media[]: Media image (if available)
        - inline_follow: Full user info + friendship in follow notifications
        - destination: Link target
        - timestamp: Unix time
        - extra_actions: ["hide", "block", "remove_follower"] (for follow)
"""

from typing import Any, Dict, List, Optional

from ..client import HttpClient
from ..models.notification import (
    Notification, NotifCounts, NotifInbox,
)


class NotificationsAPI:
    """Instagram notifications and activity API"""

    def __init__(self, client: HttpClient):
        self._client = client

    # ─── RAW METHODS (returns dict) ────────────────

    def get_activity(self) -> Dict[str, Any]:
        """
        Notifications (activity/news inbox) — RAW dict.

        Retrieved via POST /api/v1/news/inbox/.

        Returns:
            dict: counts, new_stories, old_stories, ...
        """
        return self._client.post(
            "/news/inbox/",
            rate_category="get_default",
        )

    def mark_inbox_seen(self) -> Dict[str, Any]:
        """
        Mark all notifications as read.
        POST /api/v1/news/inbox_seen/

        Returns:
            dict: {status: "ok"}
        """
        return self._client.post(
            "/news/inbox_seen/",
            rate_category="post_default",
        )

    def get_activity_counts(self) -> Dict[str, int]:
        """
        Get only notification counters (raw dict).

        Returns:
            dict: likes, comments, relationships, ...
        """
        data = self.get_activity()
        return data.get("counts", {})

    # ─── PARSED METHODS (returns Model) ────────────

    def get_inbox_parsed(self) -> NotifInbox:
        """
        Full inbox — all notifications parsed.

        Returns:
            NotifInbox: counts, new_notifications, old_notifications

        Usage:
            inbox = ig.notifications.get_inbox_parsed()
            print(f"Unread: {inbox.counts.total}")
            for n in inbox.follows:
                print(f"  {n.follower_username} followed you ({n.time_ago})")
            for n in inbox.likes:
                print(f"  {n.profile_name} liked — {n.media_shortcode}")
        """
        data = self.get_activity()
        return NotifInbox.from_response(data)

    def get_counts_parsed(self) -> NotifCounts:
        """
        Notification counters — Pydantic model.

        Returns:
            NotifCounts: likes, comments, relationships, ...

        Usage:
            counts = ig.notifications.get_counts_parsed()
            print(f"Likes: {counts.likes}")
            print(f"Followers: {counts.relationships}")
            print(f"Total: {counts.total}")
        """
        data = self.get_activity()
        return NotifCounts(**data.get("counts", {}))

    def get_all_parsed(self) -> List[Notification]:
        """
        All notifications — parsed list.

        Returns:
            List[Notification]: New ones first, then old.

        Usage:
            for n in ig.notifications.get_all_parsed():
                print(f"[{n.notif_name}] {n.text} ({n.time_ago})")
        """
        inbox = self.get_inbox_parsed()
        return inbox.all_notifications

    def get_new_parsed(self) -> List[Notification]:
        """
        Only new (unread) notifications — parsed.

        Returns:
            List[Notification]: Unread notifications.
        """
        inbox = self.get_inbox_parsed()
        return inbox.new_notifications

    def get_follow_notifications(self) -> List[Notification]:
        """
        Only follow notifications — parsed.

        Each Notification contains:
            - n.follower_username: Who followed
            - n.follower_info: Full user info (NotifUserInfo)
            - n.is_following_back: Am I following back
            - n.time_ago: When

        Returns:
            List[Notification]: Follow notifications.

        Usage:
            for n in ig.notifications.get_follow_notifications():
                user = n.follower_info
                print(f"  {user.username} ({user.full_name})")
                print(f"  Verified: {user.is_verified} | Private: {user.is_private}")
                print(f"  Following back: {n.is_following_back}")
                print(f"  Avatar: {user.hd_profile_pic}")
        """
        inbox = self.get_inbox_parsed()
        return inbox.follows

    def get_like_notifications(self) -> List[Notification]:
        """
        Only like notifications — parsed.

        Each Notification contains:
            - n.profile_name: Who liked
            - n.media_shortcode: Which post
            - n.media_image: Post image
            - n.text: Text ("user liked your comment: ...")

        Returns:
            List[Notification]: Like notifications.
        """
        inbox = self.get_inbox_parsed()
        return inbox.likes

    # ─── LEGACY COMPAT ───────────────────────────────

    def get_new_notifications(self) -> list:
        """Unread notifications (raw dict)."""
        data = self.get_activity()
        return data.get("new_stories", [])

    def get_all_notifications(self) -> list:
        """All notifications (raw dict)."""
        data = self.get_activity()
        new = data.get("new_stories", [])
        old = data.get("old_stories", [])
        return new + old

    def get_timeline(self) -> Dict[str, Any]:
        """
        Feed timeline (main feed).

        Returns:
            dict: Timeline feed data
        """
        try:
            return self._client.get(
                "/feed/timeline/",
                rate_category="get_default",
            )
        except Exception:
            return {"status": "fail", "message": "timeline requires active session"}
