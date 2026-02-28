"""
Direct Messages API
===================
DM inbox, read threads, send messages, mark as seen.
"""

from typing import Any, Dict, List, Optional
import json

from ..async_client import AsyncHttpClient


class AsyncDirectAPI:
    """Instagram Direct Message API"""

    def __init__(self, client: AsyncHttpClient):
        self._client = client

    async def get_inbox(
        self,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        All messages list (inbox).

        Args:
            cursor: Pagination cursor
            limit: How many threads to get

        Returns:
            Inbox data (threads, pending, ...)
        """
        params = {"limit": str(limit)}
        if cursor:
            params["cursor"] = cursor

        return await self._client.get(
            "/direct_v2/inbox/",
            params=params,
            rate_category="get_direct",
        )

    async def get_thread(
        self,
        thread_id: str,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Single conversation history.

        Args:
            thread_id: Thread ID
            cursor: Pagination cursor (for older messages)

        Returns:
            Thread and messages
        """
        params = {}
        if cursor:
            params["cursor"] = cursor

        return await self._client.get(
            f"/direct_v2/threads/{thread_id}/",
            params=params if params else None,
            rate_category="get_direct",
        )

    async def send_text(self, thread_id: str, text: str) -> Dict[str, Any]:
        """
        Send text message.

        Args:
            thread_id: Thread ID
            text: Message text

        Returns:
            Yuborilgan xabar data
        """
        return await self._client.post(
            "/direct_v2/threads/broadcast/text/",
            data={
                "thread_ids": f"[{thread_id}]",
                "text": text,
            },
            rate_category="post_dm",
        )

    async def send_media_share(self, thread_id: str, media_id: int | str) -> Dict[str, Any]:
        """
        Share a post via DM.

        Args:
            thread_id: Thread ID
            media_id: Post PK

        Returns:
            Share result
        """
        return await self._client.post(
            "/direct_v2/threads/broadcast/media_share/",
            data={
                "thread_ids": f"[{thread_id}]",
                "media_id": str(media_id),
            },
            rate_category="post_dm",
        )

    async def mark_seen(self, thread_id: str, item_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Mark a message as seen.

        Args:
            thread_id: Thread ID
            item_id: Message ID (optional)
        """
        data = {}
        if item_id:
            data["item_id"] = item_id

        return await self._client.post(
            f"/direct_v2/threads/{thread_id}/seen/",
            data=data if data else None,
            rate_category="post_default",
        )

    async def get_pending_inbox(self) -> Dict[str, Any]:
        """
        Pending message requests.

        Returns:
            Pending inbox data
        """
        return await self._client.get(
            "/direct_v2/pending_inbox/",
            rate_category="get_direct",
        )

    # ─── ADDITIONAL FEATURES ──────────────────────────────

    async def create_thread(self, user_ids: List[int | str], text: str = "") -> Dict[str, Any]:
        """
        Create a new conversation (thread).

        Args:
            user_ids: Recipient list (user PKs)
            text: Initial message (optional)

        Returns:
            dict: New thread data
        """
        data = {
            "recipient_users": json.dumps([str(uid) for uid in user_ids]),
        }
        if text:
            data["text"] = text
        return await self._client.post(
            "/direct_v2/threads/broadcast/text/",
            data=data,
            rate_category="post_dm",
        )

    async def send_link(self, thread_id: str, url: str, text: str = "") -> Dict[str, Any]:
        """
        Send a link.

        Args:
            thread_id: Thread ID
            url: URL link
            text: Additional text
        """
        return await self._client.post(
            "/direct_v2/threads/broadcast/link/",
            data={
                "thread_ids": f"[{thread_id}]",
                "link_text": url,
                "link_urls": json.dumps([url]),
                "text": text,
            },
            rate_category="post_dm",
        )

    async def send_profile(self, thread_id: str, user_id: int | str) -> Dict[str, Any]:
        """
        Share a profile.

        Args:
            thread_id: Thread ID
            user_id: Profile PK to share
        """
        return await self._client.post(
            "/direct_v2/threads/broadcast/profile/",
            data={
                "thread_ids": f"[{thread_id}]",
                "profile_user_id": str(user_id),
            },
            rate_category="post_dm",
        )

    async def send_reaction(self, thread_id: str, item_id: str, emoji: str = "❤️") -> Dict[str, Any]:
        """
        Send reaction to a message.

        Args:
            thread_id: Thread ID
            item_id: Message ID
            emoji: Emoji (default ❤️)
        """
        return await self._client.post(
            "/direct_v2/threads/broadcast/reaction/",
            data={
                "thread_id": thread_id,
                "item_id": item_id,
                "reaction_type": "like",
                "emoji": emoji,
            },
            rate_category="post_dm",
        )

    async def unsend_message(self, thread_id: str, item_id: str) -> Dict[str, Any]:
        """
        Unsend a message.

        Args:
            thread_id: Thread ID
            item_id: Message ID
        """
        return await self._client.post(
            f"/direct_v2/threads/{thread_id}/items/{item_id}/delete/",
            rate_category="post_dm",
        )

    async def mute_thread(self, thread_id: str) -> Dict[str, Any]:
        """
        Mute conversation.

        Args:
            thread_id: Thread ID
        """
        return await self._client.post(
            f"/direct_v2/threads/{thread_id}/mute/",
            rate_category="post_default",
        )

    async def unmute_thread(self, thread_id: str) -> Dict[str, Any]:
        """
        Unmute conversation.

        Args:
            thread_id: Thread ID
        """
        return await self._client.post(
            f"/direct_v2/threads/{thread_id}/unmute/",
            rate_category="post_default",
        )

    async def leave_thread(self, thread_id: str) -> Dict[str, Any]:
        """
        Leave group conversation.

        Args:
            thread_id: Thread ID
        """
        return await self._client.post(
            f"/direct_v2/threads/{thread_id}/leave/",
            rate_category="post_default",
        )
