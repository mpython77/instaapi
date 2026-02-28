"""
Insights API
=============
Account and post statistics, business info.
"""

from typing import Any, Dict

from ..async_client import AsyncHttpClient


class AsyncInsightsAPI:
    """Instagram insights/statistika API"""

    def __init__(self, client: AsyncHttpClient):
        self._client = client

    async def get_account_summary(self) -> Dict[str, Any]:
        """
        Account general statistics.

        Returns:
            Statistika (reach, impressions, followers growth, ...)
        """
        return await self._client.get(
            "/insights/account_summary/",
            rate_category="get_default",
        )

    async def get_media_insights(self, media_id: int | str) -> Dict[str, Any]:
        """
        Single post statistics (reach, impressions, saves, ...)

        Args:
            media_id: Media PK

        Returns:
            Post statistikasi
        """
        return await self._client.get(
            f"/insights/media/{media_id}/",
            rate_category="get_default",
        )

    async def get_business_info(self, user_id: int | str) -> Dict[str, Any]:
        """
        Business account info.

        Args:
            user_id: User PK

        Returns:
            Biznes profil data
        """
        return await self._client.get(
            "/business/get_page_info/",
            params={"user_id": str(user_id)},
            rate_category="get_default",
        )

    async def get_ads_accounts(self) -> Dict[str, Any]:
        """
        Ad accounts.

        Returns:
            Ads accounts list
        """
        return await self._client.get(
            "/ads/accounts/",
            rate_category="get_default",
        )
