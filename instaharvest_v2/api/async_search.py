"""
Search API
==========
Search endpoints:
    /web/search/topsearch/          -> Users + hashtags + places
    /tags/search/                   -> Hashtag search
    /fbsearch/places/               -> Place search
    /fbsearch/web/top_serp/         -> Hashtag top posts (media_grid)
    /discover/topical_explore/      -> Explore page
"""

import uuid
from typing import Any, Dict, List, Optional

from ..async_client import AsyncHttpClient
from ..models.user import UserShort


class AsyncSearchAPI:
    """Instagram qidiruv API"""

    def __init__(self, client: AsyncHttpClient):
        self._client = client

    # ─── UMUMIY QIDIRUV ─────────────────────────────────────

    async def top_search(self, query: str, context: str = "blended") -> Dict[str, Any]:
        """
        Top search (users + hashtags + places).

        Args:
            query: Search query
            context: "blended" (all), "user", "hashtag", "place"

        Returns:
            {users: [...], hashtags: [...], places: [...]}
        """
        return await self._client.get(
            "/web/search/topsearch/",
            params={"context": context, "query": query},
            rate_category="get_search",
        )

    async def search_users(self, query: str) -> List[UserShort]:
        """
        User search (parsed).

        Args:
            query: Username or ism

        Returns:
            List of UserShort models
        """
        data = await self.top_search(query, context="user")
        users = []
        for item in data.get("users", []):
            u = item.get("user", {})
            if isinstance(u, dict):
                users.append(UserShort(**u))
        return users

    async def search_hashtags(self, query: str) -> List[Dict]:
        """
        Search hashtags.

        Args:
            query: Hashtag name (without #)

        Returns:
            Topilgan hashtaglar list
        """
        data = await self._client.get(
            "/tags/search/",
            params={"q": query},
            rate_category="get_search",
        )
        return data.get("results", [])

    async def search_places(self, query: str) -> List[Dict]:
        """
        Location search.

        Args:
            query: Place name

        Returns:
            Topilgan joylar list
        """
        data = await self._client.get(
            "/fbsearch/places/",
            params={"query": query},
            rate_category="get_search",
        )
        return data.get("items", [])

    # ─── WEB SERP (hashtag posts) ────────────────────────

    async def web_search(
        self,
        query: str,
        enable_metadata: bool = True,
    ) -> Dict[str, Any]:
        """
        Web SERP — get top posts by hashtag.
        /fbsearch/web/top_serp/ endpoint.

        Start hashtag with "#": "#fashion"

        Args:
            query: Search query (e.g. "#fashion")

        Returns:
            dict:
                - media_grid: {sections: [{medias: [{media: ...}]}]}
                - rank_token
                - status
        """
        params = {
            "enable_metadata": "true" if enable_metadata else "false",
            "query": query,
            "search_session_id": str(uuid.uuid4()),
        }
        return await self._client.get(
            "/fbsearch/web/top_serp/",
            params=params,
            rate_category="get_search",
        )

    async def web_search_posts(self, hashtag: str) -> List[Dict]:
        """
        Get top posts by hashtag (parsed).

        Args:
            hashtag: Hashtag name (with or without #) — "fashion" or "#fashion"

        Returns:
            [{
                pk, code, media_type, like_count, comment_count,
                caption_text, image_url, video_url, username, taken_at
            }]
        """
        if not hashtag.startswith("#"):
            hashtag = f"#{hashtag}"

        raw = await self.web_search(hashtag)
        media_grid = raw.get("media_grid", {})
        sections = media_grid.get("sections", [])

        posts = []
        for section in sections:
            # Medias layout_content ichida
            layout_content = section.get("layout_content", {})
            medias = layout_content.get("medias", section.get("medias", []))
            for m_item in medias:
                media = m_item.get("media", {})
                if not media:
                    continue

                # Caption
                caption = media.get("caption") or {}
                caption_text = caption.get("text", "")

                # Image URL
                image_url = ""
                img_versions = media.get("image_versions2", {})
                candidates = img_versions.get("candidates", [])
                if candidates:
                    image_url = candidates[0].get("url", "")

                # Video URL
                video_url = ""
                video_versions = media.get("video_versions", [])
                if video_versions:
                    video_url = video_versions[0].get("url", "")

                # User
                user = media.get("user", {})

                posts.append({
                    "pk": media.get("pk"),
                    "code": media.get("code"),
                    "media_type": media.get("media_type"),
                    "like_count": media.get("like_count", 0),
                    "comment_count": media.get("comment_count", 0),
                    "play_count": media.get("play_count"),
                    "caption_text": caption_text,
                    "image_url": image_url,
                    "video_url": video_url,
                    "username": user.get("username"),
                    "user_pk": user.get("pk"),
                    "is_verified": user.get("is_verified", False),
                    "taken_at": media.get("taken_at"),
                    "has_audio": media.get("has_audio"),
                })

        return posts

    # ─── EXPLORE ────────────────────────────────────────────

    async def explore(self) -> Dict[str, Any]:
        """
        Explore page content.

        Returns:
            Explore posts and clusters
        """
        return await self._client.get(
            "/discover/topical_explore/",
            rate_category="get_default",
        )
