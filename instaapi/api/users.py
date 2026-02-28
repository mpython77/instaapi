"""
Users API
=========
User data: profile, search, get by ID.
Full profile scraping (bio mentions, hashtags, entity parsing).
"""

import re
from typing import Any, Dict, List, Optional, Union

from ..client import HttpClient
from ..exceptions import UserNotFound
from ..models.user import User, UserShort, Contact, BioParsed


class UsersAPI:
    """Instagram Users API"""

    def __init__(self, client: HttpClient):
        self._client = client

    def get_by_username(self, username: str) -> User:
        """
        Get full profile by username.

        Args:
            username: Instagram username (without @)

        Returns:
            User model (followers, bio, post count, etc.)
        """
        data = self._client.get(
            "/users/web_profile_info/",
            params={"username": username},
            rate_category="get_profile",
        )
        if "data" in data and "user" in data["data"]:
            return User.from_web_profile(data["data"]["user"])
        return User.from_web_profile(data)

    def get_by_id(self, user_id: int | str) -> User:
        """
        Get profile by user ID via GraphQL (web-compatible).

        Args:
            user_id: Instagram user ID (numeric)

        Returns:
            User model
        """
        import json as _json
        # GraphQL GET — web compatible, same as followers/following queries
        variables = {"id": str(user_id), "render_surface": "PROFILE"}
        data = self._client.get(
            "/graphql/query/",
            params={
                "query_hash": "c9100bf9110dd6361671f113dd02e7d6",
                "variables": _json.dumps(variables),
            },
            rate_category="get_profile",
            full_url="https://www.instagram.com/graphql/query/",
        )
        user_data = data.get("data", {}).get("user", {})
        if isinstance(user_data, dict) and user_data.get("username"):
            return User.from_web_profile(user_data)
        # Fallback: try direct REST
        try:
            data2 = self._client.get(
                f"/users/{user_id}/info/",
                rate_category="get_profile",
            )
            raw = data2.get("user", data2)
            return User.from_api_info(raw)
        except Exception:
            return User(pk=int(user_id) if str(user_id).isdigit() else 0)

    def search(self, query: str) -> List[UserShort]:
        """
        User search via web-compatible endpoints.
        1) If query looks like a username — directly search via web_profile_info
        2) Fallback: /web/search/topsearch/ (session-dependent)

        Args:
            query: Search query (username or name)

        Returns:
            List of UserShort models
        """
        users = []

        # Method 1: If query looks like a username (no spaces) — direct get
        if " " not in query.strip():
            try:
                data = self._client.get(
                    "/users/web_profile_info/",
                    params={"username": query.strip().lstrip("@")},
                    rate_category="get_search",
                )
                user_data = data.get("data", {}).get("user", {})
                if user_data and user_data.get("username"):
                    users.append(UserShort(**user_data))
                    return users
            except Exception:
                pass

        # Method 2: Blended search (works with session)
        try:
            data = self._client.get(
                "/web/search/topsearch/",
                params={"query": query, "context": "blended"},
                rate_category="get_search",
            )
            for u in data.get("users", []):
                user_data = u.get("user", u) if isinstance(u, dict) else u
                if isinstance(user_data, dict):
                    users.append(UserShort(**user_data))
        except Exception:
            pass

        return users

    def get_user_id(self, username: str) -> int:
        """
        Get user_id by username (shortcut).

        Args:
            username: Instagram username

        Returns:
            User ID (int)
        """
        user = self.get_by_username(username)
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
        # Support both dict and User model
        if isinstance(user_data, User):
            bio = user_data.biography or ""
            raw = user_data.to_dict()
        else:
            bio = user_data.get("biography", "") or ""
            raw = user_data

        # Mentions (@username)
        mentions = re.findall(r'@([\w.]+)', bio)

        # Hashtags (#tag)
        hashtags = re.findall(r'#(\w+)', bio)

        # URLs
        urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', bio)

        # Email addresses
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', bio)
        emails = [e for e in emails if '.' in e.split('@')[1]]

        # Phone numbers
        phones = re.findall(r'[\+]?[(\d][\d\s\-().]{7,}\d', bio)

        # Instagram entities (if available)
        entities = []
        bwe = raw.get("biography_with_entities", {}) if isinstance(raw, dict) else {}
        if isinstance(bwe, dict):
            for entity in bwe.get("entities", []):
                e_user = entity.get("user", {})
                e_hashtag = entity.get("hashtag", {})
                if e_user and isinstance(e_user, dict) and e_user.get("username"):
                    entities.append({
                        "type": "mention",
                        "username": e_user["username"],
                    })
                if e_hashtag and isinstance(e_hashtag, dict) and e_hashtag.get("name"):
                    entities.append({
                        "type": "hashtag",
                        "name": e_hashtag["name"],
                    })

        # Bio links (official Instagram)
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

    def get_full_profile(self, username: str) -> User:
        """
        Gather and return ALL profile data in one call.
        Combined web_profile_info + user_info + bio parsing.

        Args:
            username: Instagram username (without @)

        Returns:
            User model with full data: contact, bio, counters, etc.
        """
        # 1. web_profile_info
        web_user = self.get_by_username(username)

        # 2. user_info (qo'shimcha infolar)
        info_user = self.get_by_id(web_user.pk) if web_user.pk else User()

        # 3. Bio parse
        bio_data = self.parse_bio(web_user)

        # Merge: prefer web data, supplement with info data
        return User(
            # Identity
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

            # Counters
            followers=web_user.followers or info_user.followers,
            following=web_user.following or info_user.following,
            posts_count=web_user.posts_count or info_user.posts_count,

            # Images
            profile_pic_url=web_user.profile_pic_url or info_user.profile_pic_url,
            profile_pic_url_hd=web_user.profile_pic_url_hd or info_user.profile_pic_url_hd,

            # Contact (from info API)
            contact=info_user.contact,

            # Bio parsed
            bio=bio_data,

            # Additional
            highlight_count=web_user.highlight_count or info_user.highlight_count,
            pronouns=web_user.pronouns,
            fbid=web_user.fbid or info_user.fbid,
            mutual_followers_count=info_user.mutual_followers_count,
            is_threads_user=info_user.is_threads_user,
            total_clips=info_user.total_clips,
        )

    # Alias for convenience
    get_profile = get_full_profile
