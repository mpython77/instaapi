"""
Location API
=============
Instagram location-based search and feed.
"""

from typing import Any, Dict, List, Optional

from ..async_client import AsyncHttpClient


class AsyncLocationAPI:
    """Instagram Location API"""

    def __init__(self, client: AsyncHttpClient):
        self._client = client

    async def get_info(self, location_id: int | str) -> Dict[str, Any]:
        """
        Get location info.

        Args:
            location_id: Location PK

        Returns:
            dict: Location name, address, coordinates, media count
        """
        return await self._client.get(
            f"/locations/{location_id}/info/",
            rate_category="get_default",
        )

    async def get_feed(
        self,
        location_id: int | str,
        max_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get posts by location (top + recent).

        Args:
            location_id: Location PK
            max_id: Pagination cursor

        Returns:
            dict: {sections, next_max_id, more_available, ...}
        """
        params = {}
        if max_id:
            params["max_id"] = max_id
        return await self._client.get(
            f"/locations/{location_id}/sections/",
            params=params if params else None,
            rate_category="get_feed",
        )

    async def search(self, query: str, lat: float = None, lng: float = None) -> Dict[str, Any]:
        """
        Search for locations.

        Args:
            query: Search query
            lat: Latitude (optional)
            lng: Longitude (optional)

        Returns:
            dict: {venues: [...]} or {items: [...]}
        """
        params = {"query": query}
        if lat is not None:
            params["latitude"] = str(lat)
        if lng is not None:
            params["longitude"] = str(lng)

        return await self._client.get(
            "/fbsearch/places/",
            params=params,
            rate_category="get_search",
        )

    async def get_nearby(self, lat: float, lng: float) -> Dict[str, Any]:
        """
        Get nearby locations.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            dict: List of nearby places
        """
        return await self._client.get(
            "/location_search/",
            params={
                "latitude": str(lat),
                "longitude": str(lng),
                "search_query": "",
            },
            rate_category="get_search",
        )
