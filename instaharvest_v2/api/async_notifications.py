"""
Notifications API
=================
Instagram notifications and activity feed.
/news/inbox/ endpoint - works via POST method.

Response structure:
    - counts: 17 category counters (likes, comments, relationships, ...)
    - new_stories: Unread notifications
    - old_stories: Old notifications
    - continuation_token: Token for pagination
    - is_last_page: Whether this is the last page
    - partition: "Today", "This week", "This month", "Earlier" categories

Each story/notification structure:
    - story_type: 13 (comment_like), 101 (user_followed), 1686 (threads), ...
    - notif_name: "comment_like", "user_followed", "ig_text_*", ...
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

from typing import Any, Dict, Optional

from ..async_client import AsyncHttpClient


class AsyncNotificationsAPI:
    """Instagram notifications and activity API"""

    def __init__(self, client: AsyncHttpClient):
        self._client = client

    async def get_activity(self) -> Dict[str, Any]:
        """
        Notifications (activity/news inbox).
        
        Fetched via POST /api/v1/news/inbox/.

        Returns:
            dict:
                - counts: Counters by type
                    - likes, comments, comment_likes, relationships
                    - usertags, photos_of_you, requests, new_posts
                    - media_to_approve, promotional, fundraiser, shopping_notification
                - new_stories: New (unread) notifications list
                - old_stories: Old notifications
                - continuation_token: Token for next page
                - is_last_page: bool
                - partition: Time categories
                - status: "ok"
        """
        return await self._client.post(
            "/news/inbox/",
            rate_category="get_default",
        )

    async def get_activity_counts(self) -> Dict[str, int]:
        """
        Get only notification counters.

        Returns:
            dict: Unread notification count by type.
                Keys: likes, comments, comment_likes, relationships,
                usertags, photos_of_you, requests, new_posts, etc.
        """
        data = await self.get_activity()
        return data.get("counts", {})

    async def get_new_notifications(self) -> list:
        """
        Only new (unread) notifications.

        Returns:
            list: New notifications list.
                Each element: {story_type, notif_name, type, args, pk, ...}
        """
        data = await self.get_activity()
        return data.get("new_stories", [])

    async def get_all_notifications(self) -> list:
        """
        All notifications (new + old).

        Returns:
            list: All notifications, new ones first.
        """
        data = await self.get_activity()
        new = data.get("new_stories", [])
        old = data.get("old_stories", [])
        return new + old

    async def get_follow_notifications(self) -> list:
        """
        Get only follow notifications.

        Returns:
            list: Follow notifications (story_type=101, notif_name='user_followed')
                Each element contains inline_follow with user_info and friendship_status
        """
        all_notifs = await self.get_all_notifications()
        return [n for n in all_notifs if n.get("notif_name") == "user_followed"]

    async def get_like_notifications(self) -> list:
        """
        Get only like notifications.

        Returns:
            list: Like notifications (notif_name='comment_like', 'like', ...)
        """
        all_notifs = await self.get_all_notifications()
        return [
            n for n in all_notifs
            if n.get("notif_name") in ("like", "comment_like", "comment_mention")
        ]

    async def get_timeline(self) -> Dict[str, Any]:
        """
        Feed timeline (main feed).

        Returns:
            dict: Timeline feed data
                - feed_items: Posts list
                - num_results: Number of results
                - more_available: Whether more are available
        """
        return await self._client.get(
            "/feed/timeline/",
            rate_category="get_default",
        )
