"""
Collections API
================
Instagram saved collections management.
Create, edit, delete collections and manage saved posts.
"""

from typing import Any, Dict, List, Optional

from ..client import HttpClient


class CollectionsAPI:
    """Instagram collections (saved posts) API"""

    def __init__(self, client: HttpClient):
        self._client = client

    def get_list(self) -> Dict[str, Any]:
        """
        Get all collections.

        Returns:
            dict: {items: [{collection_id, collection_name, collection_media_count, cover_media, ...}]}
        """
        return self._client.get(
            "/collections/list/",
            rate_category="get_default",
        )

    def get_items(self, collection_id: str, max_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get posts in a collection.

        Args:
            collection_id: Collection ID
            max_id: Pagination cursor

        Returns:
            dict: {items: [...], more_available, next_max_id}
        """
        params = {}
        if max_id:
            params["max_id"] = max_id
        return self._client.get(
            f"/feed/collection/{collection_id}/",
            params=params if params else None,
            rate_category="get_feed",
        )

    def create(self, name: str, media_ids: List[str] = None) -> Dict[str, Any]:
        """
        Create a new collection.

        Args:
            name: Collection name
            media_ids: Initial media PKs (optional)

        Returns:
            dict: Created collection data
        """
        data = {"name": name}
        if media_ids:
            data["added_media_ids"] = str(media_ids)
        return self._client.post(
            "/collections/create/",
            data=data,
            rate_category="post_default",
        )

    def delete(self, collection_id: str) -> Dict[str, Any]:
        """
        Delete a collection.

        Args:
            collection_id: Collection ID
        """
        return self._client.post(
            f"/collections/{collection_id}/delete/",
            rate_category="post_default",
        )

    def edit(self, collection_id: str, name: str) -> Dict[str, Any]:
        """
        Rename a collection.

        Args:
            collection_id: Collection ID
            name: New name
        """
        return self._client.post(
            f"/collections/{collection_id}/edit/",
            data={"name": name},
            rate_category="post_default",
        )

    def add_media(self, collection_id: str, media_ids: List[str]) -> Dict[str, Any]:
        """
        Add posts to a collection.

        Args:
            collection_id: Collection ID
            media_ids: Media PKs to add
        """
        return self._client.post(
            f"/collections/{collection_id}/edit/",
            data={"added_media_ids": str(media_ids)},
            rate_category="post_default",
        )

    def remove_media(self, collection_id: str, media_ids: List[str]) -> Dict[str, Any]:
        """
        Remove posts from a collection.

        Args:
            collection_id: Collection ID
            media_ids: Media PKs to remove
        """
        return self._client.post(
            f"/collections/{collection_id}/edit/",
            data={"removed_media_ids": str(media_ids)},
            rate_category="post_default",
        )

    # Alias for convenience
    get_all = get_list
