"""
Hashtags API
============
Hashtag info, posts, follow/unfollow, related.
"""

from typing import Any, Dict, List

from ..async_client import AsyncHttpClient


class AsyncHashtagsAPI:
    """Instagram Hashtags API"""

    def __init__(self, client: AsyncHttpClient):
        self._client = client

    async def get_info(self, hashtag: str) -> Dict[str, Any]:
        """
        Hashtag info: how many posts, how many people follow.

        Args:
            hashtag: Hashtag name (without #)

        Returns:
            Hashtag data
        """
        return await self._client.get(
            f"/tags/{hashtag}/info/",
            rate_category="get_default",
        )

    async def get_posts(self, hashtag: str) -> Dict[str, Any]:
        """
        Hashtag posts (top + recent).

        Args:
            hashtag: Hashtag name

        Returns:
            Posts (in sections format)
        """
        return await self._client.get(
            f"/tags/{hashtag}/sections/",
            rate_category="get_feed",
        )

    async def follow(self, hashtag: str) -> Dict[str, Any]:
        """
        Follow a hashtag.

        Args:
            hashtag: Hashtag name
        """
        return await self._client.post(
            f"/tags/follow/{hashtag}/",
            rate_category="post_follow",
        )

    async def unfollow(self, hashtag: str) -> Dict[str, Any]:
        """
        Unfollow a hashtag.

        Args:
            hashtag: Hashtag name
        """
        return await self._client.post(
            f"/tags/unfollow/{hashtag}/",
            rate_category="post_follow",
        )

    async def get_related(self, hashtag: str) -> List[Dict]:
        """
        Related hashtags.

        Args:
            hashtag: Hashtag name

        Returns:
            List of similar hashtags
        """
        data = await self._client.get(
            f"/tags/{hashtag}/related/",
            rate_category="get_default",
        )
        return data.get("related", [])
