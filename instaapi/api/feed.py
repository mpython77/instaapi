"""
Feed API
========
User feeds: posts, liked, saved.
Pagination support.
"""

import json
from typing import Any, Dict, List, Optional

from ..client import HttpClient
from ..models.media import Media as MediaModel


class FeedAPI:
    """Instagram feed API"""

    def __init__(self, client: HttpClient):
        self._client = client

    def get_user_feed(
        self,
        user_id: int | str,
        count: int = 12,
        max_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        User posts.

        Args:
            user_id: User PK
            count: How many posts to get
            max_id: Pagination cursor (next page)

        Returns:
            Posts and pagination data
        """
        params = {"count": str(count)}
        if max_id:
            params["max_id"] = max_id

        data = self._client.get(
            f"/feed/user/{user_id}/",
            params=params,
            rate_category="get_feed",
        )
        return data

    def get_all_posts(
        self,
        user_id: int | str,
        max_posts: int = 100,
        count_per_page: int = 12,
    ) -> List[MediaModel]:
        """
        Get all posts (with pagination).

        Args:
            user_id: User PK
            max_posts: Maximum number of posts
            count_per_page: Posts per page

        Returns:
            List of Media models
        """
        all_posts = []
        max_id = None

        while len(all_posts) < max_posts:
            data = self.get_user_feed(user_id, count=count_per_page, max_id=max_id)

            items = data.get("items", [])
            all_posts.extend([MediaModel.from_api(item) for item in items])

            if not data.get("more_available"):
                break

            max_id = data.get("next_max_id")
            if not max_id:
                break

        return all_posts[:max_posts]

    def get_liked(self, max_id: Optional[str] = None) -> Dict[str, Any]:
        """
        My liked posts (via GraphQL - web compatible).

        Args:
            max_id: Pagination cursor

        Returns:
            Liked posts
        """
        sess = self._client.get_session()
        variables = {"id": str(sess.ds_user_id) if sess else "", "first": 20}
        if max_id:
            variables["after"] = max_id
        data = self._client.get(
            "/graphql/query/",
            params={
                "query_hash": "d5d763b1e2acf209d62d22d184488e57",
                "variables": json.dumps(variables),
            },
            rate_category="get_feed",
            full_url="https://www.instagram.com/graphql/query/",
        )
        return data

    def get_saved(self, max_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Saved (bookmarked) posts (via GraphQL - web compatible).

        Args:
            max_id: Pagination cursor

        Returns:
            Saved posts
        """
        sess = self._client.get_session()
        variables = {"id": str(sess.ds_user_id) if sess else "", "first": 20}
        if max_id:
            variables["after"] = max_id
        data = self._client.get(
            "/graphql/query/",
            params={
                "query_hash": "2ce1d673055b99c84dc0d5b62e3f30d2",
                "variables": json.dumps(variables),
            },
            rate_category="get_feed",
            full_url="https://www.instagram.com/graphql/query/",
        )
        return data

    # ─── TAG / LOCATION FEED ────────────────────────────────

    def get_tag_feed(self, hashtag: str, max_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Posts feed by hashtag.

        Args:
            hashtag: Hashtag name (without #)
            max_id: Pagination cursor

        Returns:
            dict: {items, more_available, next_max_id}
        """
        params = {}
        if max_id:
            params["max_id"] = max_id
        return self._client.get(
            f"/feed/tag/{hashtag}/",
            params=params if params else None,
            rate_category="get_feed",
        )

    def get_location_feed(self, location_id: int | str, max_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Posts feed by location.

        Args:
            location_id: Location PK
            max_id: Pagination cursor

        Returns:
            dict: {items, more_available, next_max_id}
        """
        params = {}
        if max_id:
            params["max_id"] = max_id
        return self._client.get(
            f"/feed/location/{location_id}/",
            params=params if params else None,
            rate_category="get_feed",
        )

    def get_timeline(self, max_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Home timeline feed (GraphQL GET — web compatible).

        Args:
            max_id: Pagination cursor

        Returns:
            dict: Timeline feed data
        """
        # Fallback to REST — some sessions support it
        try:
            params = {}
            if max_id:
                params["max_id"] = max_id
            return self._client.get(
                "/feed/timeline/",
                params=params if params else None,
                rate_category="get_feed",
            )
        except Exception:
            return {"status": "fail", "message": "timeline requires mobile session"}

    def get_reels_feed(self, max_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Reels tab (explore reels).

        Args:
            max_id: Pagination cursor

        Returns:
            dict: Reels posts
        """
        params = {}
        if max_id:
            params["max_id"] = max_id
        return self._client.get(
            "/clips/trending/",
            params=params if params else None,
            rate_category="get_feed",
        )
