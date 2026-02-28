"""
Async Discover API
==================
Async version of DiscoverAPI. Full feature parity.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ..async_client import AsyncHttpClient
from ..models.user import UserShort

logger = logging.getLogger("instaapi.discover")

DISCOVER_CHAINING_DOC_ID = "29042405687261020"


class AsyncDiscoverAPI:
    """
    Async Instagram Discover API — similar/suggested users.

    Corresponds to the "Suggested for you" section on profile pages.
    """

    def __init__(self, client: AsyncHttpClient):
        self._client = client

    async def get_suggested_users_raw(
        self,
        user_id: int | str,
        doc_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Similar accounts — raw GraphQL response.

        Args:
            user_id: Target user ID
            doc_id: Custom doc_id

        Returns:
            Full GraphQL response dict
        """
        variables = {"target_id": str(user_id)}
        payload = {
            "variables": json.dumps(variables),
            "doc_id": doc_id or DISCOVER_CHAINING_DOC_ID,
            "fb_api_caller_class": "RelayModern",
            "server_timestamps": "true",
            "fb_api_req_friendly_name": "PolarisProfileSuggestedUsersQuery",
        }
        data = await self._client.post(
            "/graphql/query",
            data=payload,
            rate_category="get_default",
            full_url="https://www.instagram.com/graphql/query",
        )
        return data

    async def get_suggested_users(
        self,
        user_id: int | str,
        doc_id: Optional[str] = None,
    ) -> List[UserShort]:
        """
        Similar accounts — parsed UserShort models.

        Args:
            user_id: Target user ID (pk)
            doc_id: Custom doc_id

        Returns:
            List[UserShort]: List of suggested users
        """
        data = await self.get_suggested_users_raw(user_id=user_id, doc_id=doc_id)
        users_data = (
            data
            .get("data", {})
            .get("xdt_api__v1__discover__chaining", {})
            .get("users", [])
        )

        users: List[UserShort] = []
        for user_dict in users_data:
            if not isinstance(user_dict, dict):
                continue
            try:
                user = UserShort(
                    pk=user_dict.get("pk") or user_dict.get("id", 0),
                    username=user_dict.get("username", ""),
                    full_name=user_dict.get("full_name", ""),
                    is_verified=user_dict.get("is_verified", False),
                    is_private=user_dict.get("is_private", False),
                    profile_pic_url=user_dict.get("profile_pic_url", ""),
                )
                users.append(user)
            except Exception as e:
                logger.warning(f"Suggested user parse error: {e}")
                continue

        logger.info(f"Discover chaining: {len(users)} suggested users for user_id={user_id}")
        return users

    async def get_verified_suggestions(
        self,
        user_id: int | str,
        doc_id: Optional[str] = None,
    ) -> List[UserShort]:
        """
        Returns only verified (blue badge) accounts.

        Args:
            user_id: Target user ID

        Returns:
            List[UserShort]: Only verified users
        """
        all_users = await self.get_suggested_users(user_id=user_id, doc_id=doc_id)
        return [u for u in all_users if u.is_verified]

    async def get_public_suggestions(
        self,
        user_id: int | str,
        doc_id: Optional[str] = None,
    ) -> List[UserShort]:
        """
        Returns only public (open profile) accounts.

        Args:
            user_id: Target user ID

        Returns:
            List[UserShort]: Only public users
        """
        all_users = await self.get_suggested_users(user_id=user_id, doc_id=doc_id)
        return [u for u in all_users if not u.is_private]

    async def get_suggestion_usernames(
        self,
        user_id: int | str,
        doc_id: Optional[str] = None,
    ) -> List[str]:
        """
        Returns only a list of usernames.

        Args:
            user_id: Target user ID

        Returns:
            List[str]: Usernames list
        """
        users = await self.get_suggested_users(user_id=user_id, doc_id=doc_id)
        return [u.username for u in users if u.username]
