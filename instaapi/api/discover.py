"""
Discover API
============
Instagram Discover / Suggested Users endpoint.

Endpoint:
    POST /graphql/query  (doc_id based)
    Response key: data.xdt_api__v1__discover__chaining.users[]

Provides:
    - get_suggested_users(user_id) -> List[UserShort]
    - get_suggested_users_raw(user_id) -> raw GraphQL response
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ..client import HttpClient
from ..models.user import UserShort

logger = logging.getLogger("instaapi.discover")

# Known doc_id for discover chaining
# This doc_id is used by the Instagram web client for "Suggested for you" on profile pages
DISCOVER_CHAINING_DOC_ID = "29042405687261020"


class DiscoverAPI:
    """
    Instagram Discover API — similar/suggested users.

    Corresponds to the "Suggested for you" section on profile pages. 
    Returns similar accounts recommended by Instagram for a given user_id.

    Usage:
        ig = Instagram.from_env()
        
        # As UserShort models
        users = ig.discover.get_suggested_users(user_id=12345)
        for user in users:
            print(f"@{user.username} - {user.full_name} {'✓' if user.is_verified else ''}")
        
        # Raw response
        data = ig.discover.get_suggested_users_raw(user_id=12345)
    """

    def __init__(self, client: HttpClient):
        self._client = client

    # ─── Raw API ────────────────────────────────────────────────

    def get_suggested_users_raw(
        self,
        user_id: int | str,
        doc_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Similar accounts — raw GraphQL response.

        Args:
            user_id: Target user ID (profil egasi PK)
            doc_id: Custom doc_id (agar default ishlamasa)

        Returns:
            Full GraphQL response dict
        """
        variables = {
            "target_id": str(user_id),
        }

        payload = {
            "variables": json.dumps(variables),
            "doc_id": doc_id or DISCOVER_CHAINING_DOC_ID,
            "fb_api_caller_class": "RelayModern",
            "server_timestamps": "true",
            "fb_api_req_friendly_name": "PolarisProfileSuggestedUsersQuery",
        }

        data = self._client.post(
            "/graphql/query",
            data=payload,
            rate_category="get_default",
            full_url="https://www.instagram.com/graphql/query",
        )

        return data

    # ─── Parsed API ─────────────────────────────────────────────

    def get_suggested_users(
        self,
        user_id: int | str,
        doc_id: Optional[str] = None,
    ) -> List[UserShort]:
        """
        Similar accounts — parsed UserShort models.

        Corresponds to "Suggested for you" on Instagram profile pages.
        Returns ~30 similar accounts for a given user.

        Args:
            user_id: Target user ID (pk)
            doc_id: Custom doc_id (agar default ishlamasa)

        Returns:
            List[UserShort]: List of suggested users
                Each UserShort: pk, username, full_name, is_verified, is_private, profile_pic_url

        Example:
            users = ig.discover.get_suggested_users(12345)
            verified = [u for u in users if u.is_verified]
            print(f"{len(verified)} verified from {len(users)} suggestions")
        """
        data = self.get_suggested_users_raw(user_id=user_id, doc_id=doc_id)

        # Response structure: data.xdt_api__v1__discover__chaining.users[]
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

        logger.info(
            f"Discover chaining: {len(users)} suggested users for user_id={user_id}"
        )
        return users

    # ─── Utility methods ────────────────────────────────────────

    def get_verified_suggestions(
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
        all_users = self.get_suggested_users(user_id=user_id, doc_id=doc_id)
        return [u for u in all_users if u.is_verified]

    def get_public_suggestions(
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
        all_users = self.get_suggested_users(user_id=user_id, doc_id=doc_id)
        return [u for u in all_users if not u.is_private]

    def get_suggestion_usernames(
        self,
        user_id: int | str,
        doc_id: Optional[str] = None,
    ) -> List[str]:
        """
        Returns only a list of usernames.

        Args:
            user_id: Target user ID

        Returns:
            List[str]: Username'lar listi
        """
        users = self.get_suggested_users(user_id=user_id, doc_id=doc_id)
        return [u.username for u in users if u.username]

    def explore(self) -> Dict[str, Any]:
        """
        Explore page content (proxy to /discover/topical_explore/).

        Returns:
            Explore posts and clusters
        """
        return self._client.get(
            "/discover/topical_explore/",
            rate_category="get_default",
        )
