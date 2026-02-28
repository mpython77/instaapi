"""
Users API (Async)
=================
User data: profile, search, get by ID.
Full profile scraping (bio mentions, hashtags, entity parsing).
"""

import re
from typing import Any, Dict, List, Optional, Union

from ..async_client import AsyncHttpClient
from ..exceptions import UserNotFound
from ..models.user import User, UserShort, Contact, BioParsed


class AsyncUsersAPI:
    """Instagram Users API (Async)"""

    def __init__(self, client: AsyncHttpClient):
        self._client = client

    async def get_by_username(self, username: str) -> User:
        """
        Get full profile by username.

        Args:
            username: Instagram username (without @)

        Returns:
            User model
        """
        data = await self._client.get(
            "/users/web_profile_info/",
            params={"username": username},
            rate_category="get_profile",
        )
        if "data" in data and "user" in data["data"]:
            return User.from_web_profile(data["data"]["user"])
        return User.from_web_profile(data)

    async def get_by_id(self, user_id: int | str) -> User:
        """
        Get profile by user ID.

        Args:
            user_id: Instagram user ID (numeric)

        Returns:
            User model
        """
        data = await self._client.get(
            f"/users/{user_id}/info/",
            rate_category="get_profile",
        )
        raw = data.get("user", data)
        return User.from_api_info(raw)

    async def search(self, query: str) -> List[UserShort]:
        """
        User search.

        Args:
            query: Search query

        Returns:
            List of UserShort models
        """
        data = await self._client.get(
            "/users/search/",
            params={"query": query},
            rate_category="get_search",
        )
        return [UserShort(**u) for u in data.get("users", [])]

    async def get_user_id(self, username: str) -> int:
        """
        Get user_id by username (shortcut).

        Args:
            username: Instagram username

        Returns:
            User ID (int)
        """
        user = await self.get_by_username(username)
        if user.pk:
            return user.pk
        raise UserNotFound(f"User ID not found: {username}")

    # ─── Bio parsing ────────────────────────────────────────

    @staticmethod
    def parse_bio(user_data: Union[Dict[str, Any], User]) -> BioParsed:
        """
        Parse mentions, hashtags, and entities from bio.

        Args:
            user_data: Result from get_by_username() or raw dict

        Returns:
            BioParsed model
        """
        if isinstance(user_data, User):
            bio = user_data.biography or ""
            raw = user_data.to_dict()
        else:
            bio = user_data.get("biography", "") or ""
            raw = user_data

        mentions = re.findall(r'@([\w.]+)', bio)
        hashtags = re.findall(r'#(\w+)', bio)
        urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', bio)
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', bio)
        emails = [e for e in emails if '.' in e.split('@')[1]]
        phones = re.findall(r'[\+]?[(\d][\d\s\-().]{7,}\d', bio)

        entities = []
        bwe = raw.get("biography_with_entities", {}) if isinstance(raw, dict) else {}
        if isinstance(bwe, dict):
            for entity in bwe.get("entities", []):
                e_user = entity.get("user", {})
                e_hashtag = entity.get("hashtag", {})
                if e_user and isinstance(e_user, dict) and e_user.get("username"):
                    entities.append({"type": "mention", "username": e_user["username"]})
                if e_hashtag and isinstance(e_hashtag, dict) and e_hashtag.get("name"):
                    entities.append({"type": "hashtag", "name": e_hashtag["name"]})

        bio_links = raw.get("bio_links", []) if isinstance(raw, dict) else []

        return BioParsed(
            biography=bio,
            bio_mentions=mentions,
            bio_hashtags=hashtags,
            bio_entities=entities,
            bio_urls=urls,
            bio_links=bio_links,
            bio_emails=emails,
            bio_phones=phones,
        )

    # ─── Full profile scraping ─────────────────────────────

    async def get_full_profile(self, username: str) -> User:
        """
        Gather and return ALL profile data in one call.

        Args:
            username: Instagram username (without @)

        Returns:
            User model with full data
        """
        web_user = await self.get_by_username(username)
        info_user = await self.get_by_id(web_user.pk) if web_user.pk else User()
        bio_data = self.parse_bio(web_user)

        return User(
            pk=web_user.pk or info_user.pk,
            username=web_user.username or info_user.username,
            full_name=web_user.full_name or info_user.full_name,
            is_verified=web_user.is_verified or info_user.is_verified,
            is_private=web_user.is_private or info_user.is_private,
            is_business=web_user.is_business or info_user.is_business,
            is_professional=web_user.is_professional,
            biography=bio_data.biography,
            external_url=web_user.external_url or info_user.external_url,
            category=web_user.category or info_user.category,
            followers=web_user.followers or info_user.followers,
            following=web_user.following or info_user.following,
            posts_count=web_user.posts_count or info_user.posts_count,
            profile_pic_url=web_user.profile_pic_url or info_user.profile_pic_url,
            profile_pic_url_hd=web_user.profile_pic_url_hd or info_user.profile_pic_url_hd,
            contact=info_user.contact,
            bio=bio_data,
            highlight_count=web_user.highlight_count or info_user.highlight_count,
            pronouns=web_user.pronouns,
            fbid=web_user.fbid or info_user.fbid,
            mutual_followers_count=info_user.mutual_followers_count,
            is_threads_user=info_user.is_threads_user,
            total_clips=info_user.total_clips,
        )
