"""
Async Public API
================
True async interface for anonymous Instagram data access.
No login, no cookies — purely public data with real parallelism.

Uses AsyncAnonClient's 5-strategy fallback chain under the hood.
"""

import asyncio
import re
import logging
from typing import Any, Callable, Dict, List, Optional

from ..async_anon_client import AsyncAnonClient
from .. import utils

logger = logging.getLogger("instaapi.async_public")


class AsyncPublicAPI:
    """
    Async anonymous Instagram data access.

    All methods work WITHOUT login — only public data.
    TRUE async I/O — supports parallel operations natively.

    Usage:
        async with AsyncInstagram.anonymous(unlimited=True) as ig:
            # Parallel profiles (real async!)
            tasks = [ig.public.get_profile(u) for u in usernames]
            results = await asyncio.gather(*tasks)

            # Single fetch
            profile = await ig.public.get_profile("cristiano")
            posts = await ig.public.get_posts("cristiano")
    """

    def __init__(self, anon_client: AsyncAnonClient):
        self._client = anon_client

    # ═══════════════════════════════════════════════════════════
    # PROFILE
    # ═══════════════════════════════════════════════════════════

    async def get_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get public profile (anonymous, async).

        Uses fallback chain: HTML parse → Web API → GraphQL.

        Args:
            username: Instagram username (without @)

        Returns:
            Profile data dict or None if not found/private
        """
        username = username.lstrip("@").strip().lower()
        return await self._client.get_profile_chain(username)

    async def get_user_id(self, username: str) -> Optional[int]:
        """
        Get user ID from username (anonymous, async).

        Args:
            username: Instagram username

        Returns:
            User ID (int) or None
        """
        username = username.lstrip("@").strip().lower()

        profile = await self.get_profile(username)
        if profile:
            uid = (
                profile.get("user_id")
                or profile.get("pk")
                or profile.get("id")
                or profile.get("fbid")
            )
            if uid:
                try:
                    return int(uid)
                except (ValueError, TypeError):
                    pass

        try:
            web_profile = await self._client.get_web_profile(username)
            if web_profile:
                uid = web_profile.get("id") or web_profile.get("pk")
                if uid:
                    return int(uid)
        except Exception:
            pass

        return None

    async def get_profile_pic_url(self, username: str) -> Optional[str]:
        """Get profile picture URL (anonymous, async)."""
        profile = await self.get_profile(username)
        if profile:
            return (
                profile.get("profile_pic_url_hd")
                or profile.get("profile_pic_url")
            )
        return None

    # ═══════════════════════════════════════════════════════════
    # POSTS
    # ═══════════════════════════════════════════════════════════

    async def get_post_by_shortcode(self, shortcode: str) -> Optional[Dict[str, Any]]:
        """
        Get post data by shortcode (anonymous, async).

        Uses fallback chain: Embed → GraphQL → Web API.
        """
        return await self._client.get_post_chain(shortcode)

    async def get_post_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get post data by Instagram URL (anonymous, async).
        """
        shortcode = utils.extract_shortcode(url)
        if not shortcode:
            logger.warning(f"[AsyncPublic] Could not extract shortcode from URL: {url}")
            return None
        return await self.get_post_by_shortcode(shortcode)

    async def get_posts(
        self,
        username: str,
        max_count: int = 12,
    ) -> List[Dict[str, Any]]:
        """
        Get user's public posts (anonymous, async).
        """
        username = username.lstrip("@").strip().lower()

        # Strategy 1: Web API
        web_profile = await self._client.get_web_profile(username)
        if web_profile:
            media = web_profile.get("edge_owner_to_timeline_media", {})
            edges = media.get("edges", [])
            if edges:
                posts = self._client._parse_timeline_edges(edges)
                if posts:
                    return posts[:max_count]

        # Strategy 2: HTML parse
        profile = await self._client.get_profile_html(username)
        if profile and profile.get("recent_posts"):
            posts = profile["recent_posts"][:max_count]
            if posts:
                return posts

        # Strategy 3: GraphQL
        user_id = None
        if web_profile:
            user_id = web_profile.get("id")
        if not user_id and profile:
            user_id = profile.get("user_id")

        if user_id:
            gql_data = await self._client.get_user_posts_graphql(
                str(user_id), first=min(max_count, 50)
            )
            if gql_data:
                edges = gql_data.get("edges", [])
                posts = self._client._parse_timeline_edges(edges)
                if posts:
                    return posts[:max_count]

        # Strategy 4: Mobile Feed API
        if user_id:
            feed_data = await self._client.get_user_feed_mobile(user_id, count=max_count)
            if feed_data and feed_data.get("items"):
                return feed_data["items"][:max_count]

        return []

    async def get_media_urls(self, shortcode: str) -> List[Dict[str, str]]:
        """Get all media URLs for a post (async)."""
        post = await self.get_post_by_shortcode(shortcode)
        if not post:
            return []

        urls = []

        carousel = post.get("carousel_media", [])
        if carousel:
            for child in carousel:
                child_url = child.get("display_url")
                if child.get("is_video") and child.get("video_url"):
                    urls.append({"url": child["video_url"], "type": "video"})
                if child_url:
                    resources = child.get("display_resources", [])
                    if resources:
                        best = max(resources, key=lambda r: r.get("width", 0) or 0)
                        urls.append({
                            "url": best.get("url") or child_url,
                            "type": "image",
                            "width": best.get("width"),
                            "height": best.get("height"),
                        })
                    else:
                        urls.append({"url": child_url, "type": "image"})
            return urls

        for img in post.get("images", []):
            if img.get("url"):
                urls.append({
                    "url": img["url"],
                    "type": "image",
                    "width": img.get("width"),
                    "height": img.get("height"),
                })

        if post.get("video_url"):
            urls.append({"url": post["video_url"], "type": "video"})

        if not urls and post.get("display_url"):
            urls.append({"url": post["display_url"], "type": "image"})

        return urls

    # ═══════════════════════════════════════════════════════════
    # COMMENTS
    # ═══════════════════════════════════════════════════════════

    async def get_comments(
        self,
        shortcode: str,
        max_count: int = 24,
    ) -> List[Dict[str, Any]]:
        """Get public post comments (anonymous, async)."""
        data = await self._client.get_post_comments_graphql(
            shortcode, first=min(max_count, 50)
        )
        if not data:
            return []

        comments = []
        for edge in data.get("edges", []):
            node = edge.get("node", {})
            owner = node.get("owner", {})
            comments.append({
                "pk": node.get("id"),
                "text": node.get("text", ""),
                "username": owner.get("username"),
                "user_pk": owner.get("id"),
                "is_verified": owner.get("is_verified", False),
                "profile_pic_url": owner.get("profile_pic_url"),
                "likes": node.get("edge_liked_by", {}).get("count", 0),
                "replies_count": node.get("edge_threaded_comments", {}).get("count", 0),
                "created_at": node.get("created_at"),
            })

        return comments[:max_count]

    # ═══════════════════════════════════════════════════════════
    # HASHTAGS
    # ═══════════════════════════════════════════════════════════

    async def get_hashtag_posts(
        self,
        hashtag: str,
        max_count: int = 12,
    ) -> List[Dict[str, Any]]:
        """Get posts by hashtag (anonymous, async)."""
        tag = hashtag.lstrip("#").strip().lower()
        data = await self._client.get_hashtag_posts_graphql(tag, first=min(max_count, 50))
        if not data:
            return []

        edges = data.get("edge_hashtag_to_media", {}).get("edges", [])
        posts = self._client._parse_timeline_edges(edges)

        return posts[:max_count]

    # ═══════════════════════════════════════════════════════════
    # MOBILE FEED
    # ═══════════════════════════════════════════════════════════

    async def get_feed(
        self,
        user_id: int | str,
        max_count: int = 12,
        max_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get user feed via mobile API (async, with pagination)."""
        result = await self._client.get_user_feed_mobile(user_id, count=max_count, max_id=max_id)
        if result:
            return result
        return {"items": [], "more_available": False, "next_max_id": None}

    async def get_all_posts(
        self,
        username: str,
        max_count: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get all posts combining web profile + mobile feed (async)."""
        username = username.lstrip("@").strip().lower()
        all_posts = []

        web_profile = await self._client.get_web_profile(username)
        user_id = None
        if web_profile:
            user_id = web_profile.get("id") or web_profile.get("pk")
            media = web_profile.get("edge_owner_to_timeline_media", {})
            edges = media.get("edges", [])
            if edges:
                all_posts = self._client._parse_timeline_edges(edges)

        if user_id and len(all_posts) < max_count:
            feed = await self._client.get_user_feed_mobile(user_id, count=33)
            if feed and feed.get("items"):
                seen_codes = {p.get("shortcode") for p in all_posts if p.get("shortcode")}
                for item in feed["items"]:
                    if item.get("shortcode") not in seen_codes:
                        all_posts.append(item)
                        seen_codes.add(item.get("shortcode"))

        return all_posts[:max_count]

    async def get_media(self, media_id: int | str) -> Optional[Dict[str, Any]]:
        """Get single media info via mobile API (async)."""
        return await self._client.get_media_info_mobile(media_id)

    # ═══════════════════════════════════════════════════════════
    # SEARCH
    # ═══════════════════════════════════════════════════════════

    async def search(
        self,
        query: str,
        context: str = "blended",
    ) -> Dict[str, Any]:
        """Search Instagram anonymously (async)."""
        result = await self._client.search_web(query, context=context)
        return result or {"users": [], "hashtags": [], "places": []}

    # ═══════════════════════════════════════════════════════════
    # REELS
    # ═══════════════════════════════════════════════════════════

    async def get_reels(
        self,
        username: str,
        max_count: int = 12,
    ) -> List[Dict[str, Any]]:
        """Get user reels anonymously (async)."""
        username = username.lstrip("@").strip().lower()
        user_id = await self.get_user_id(username)
        if not user_id:
            return []
        result = await self._client.get_user_reels(user_id, count=min(max_count, 33))
        if result and result.get("items"):
            return result["items"][:max_count]
        return []

    # ═══════════════════════════════════════════════════════════
    # HASHTAG v2 (web API sections)
    # ═══════════════════════════════════════════════════════════

    async def get_hashtag_posts_v2(
        self,
        hashtag: str,
        tab: str = "recent",
        max_count: int = 30,
    ) -> Dict[str, Any]:
        """Get hashtag posts via web API (async, v2)."""
        result = await self._client.get_hashtag_sections(hashtag, tab=tab)
        if result:
            result["posts"] = result["posts"][:max_count]
            return result
        return {"tag_name": hashtag, "posts": [], "more_available": False, "media_count": 0}

    # ═══════════════════════════════════════════════════════════
    # LOCATION
    # ═══════════════════════════════════════════════════════════

    async def get_location_posts(
        self,
        location_id: int | str,
        tab: str = "recent",
        max_count: int = 30,
    ) -> Dict[str, Any]:
        """Get posts from a location anonymously (async)."""
        result = await self._client.get_location_sections(location_id, tab=tab)
        if result:
            result["posts"] = result["posts"][:max_count]
            return result
        return {"location": None, "posts": [], "more_available": False, "media_count": 0}

    # ═══════════════════════════════════════════════════════════
    # SIMILAR ACCOUNTS
    # ═══════════════════════════════════════════════════════════

    async def get_similar_accounts(
        self,
        username: str,
    ) -> List[Dict[str, Any]]:
        """Get similar accounts (async)."""
        username = username.lstrip("@").strip().lower()
        user_id = await self.get_user_id(username)
        if not user_id:
            return []
        result = await self._client.get_similar_accounts(user_id)
        return result or []

    # ═══════════════════════════════════════════════════════════
    # HIGHLIGHTS
    # ═══════════════════════════════════════════════════════════

    async def get_highlights(
        self,
        username: str,
    ) -> List[Dict[str, Any]]:
        """Get story highlights anonymously (async)."""
        username = username.lstrip("@").strip().lower()
        user_id = await self.get_user_id(username)
        if not user_id:
            return []
        result = await self._client.get_highlights_tray(user_id)
        return result or []

    # ═══════════════════════════════════════════════════════════
    # BULK OPERATIONS (True Async — asyncio.gather)
    # ═══════════════════════════════════════════════════════════

    async def bulk_profiles(
        self,
        usernames: List[str],
        callback: Optional[Callable] = None,
    ) -> Dict[str, Dict]:
        """
        Fetch multiple profiles in parallel (true async).

        Uses asyncio.gather for maximum concurrency.
        Concurrency is controlled by AsyncAnonClient's Semaphore.

        Usage:
            profiles = await ig.public.bulk_profiles(["nike", "adidas", "puma"])
        """
        async def _fetch(username):
            username = username.lstrip("@").strip().lower()
            try:
                profile = await self.get_profile(username)
                if callback:
                    callback(username, profile)
                return username, profile
            except Exception as e:
                logger.debug(f"bulk_profiles: {username} failed: {e}")
                return username, None

        tasks = [_fetch(u) for u in usernames]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        for i, r in enumerate(results_list):
            if isinstance(r, Exception):
                results[usernames[i].lstrip("@").strip().lower()] = None
            else:
                results[r[0]] = r[1]
        return results

    async def bulk_feeds(
        self,
        user_ids: List[int | str],
        max_count: int = 12,
        callback: Optional[Callable] = None,
    ) -> Dict[str, Dict]:
        """
        Fetch multiple user feeds in parallel (true async).

        Usage:
            feeds = await ig.public.bulk_feeds([13460080, 173560420])
        """
        async def _fetch(user_id):
            uid = str(user_id)
            try:
                feed = await self.get_feed(uid, max_count=max_count)
                if callback:
                    callback(uid, feed)
                return uid, feed
            except Exception as e:
                logger.debug(f"bulk_feeds: {uid} failed: {e}")
                return uid, {"items": [], "error": str(e)}

        tasks = [_fetch(uid) for uid in user_ids]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        for i, r in enumerate(results_list):
            if isinstance(r, Exception):
                results[str(user_ids[i])] = {"items": [], "error": str(r)}
            else:
                results[r[0]] = r[1]
        return results

    # ═══════════════════════════════════════════════════════════
    # UTILITY
    # ═══════════════════════════════════════════════════════════

    async def is_public(self, username: str) -> Optional[bool]:
        """Check if account is public (anonymous, async)."""
        profile = await self.get_profile(username)
        if profile is None:
            return None
        return not profile.get("is_private", True)

    async def exists(self, username: str) -> bool:
        """Check if username exists (anonymous, async)."""
        return await self.get_profile(username) is not None

    @property
    def request_count(self) -> int:
        """Total anonymous requests made."""
        return self._client.request_count

    @property
    def stats(self) -> Dict:
        """Get async client statistics."""
        return self._client.stats
