"""
Public API
==========
High-level interface for anonymous Instagram data access.
No login, no cookies — purely public data.

Uses AnonClient's 5-strategy fallback chain under the hood.
"""

import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Callable

from ..anon_client import AnonClient
from .. import utils

logger = logging.getLogger("instaharvest_v2.public")


class PublicAPI:
    """
    Anonymous Instagram data access.

    All methods work WITHOUT login — only public data.

    Usage:
        ig = Instagram.anonymous()
        profile = ig.public.get_profile("cristiano")
        posts = ig.public.get_posts("cristiano")
        post = ig.public.get_post_by_url("https://instagram.com/p/ABC123/")
    """

    def __init__(self, anon_client: AnonClient):
        self._client = anon_client

    # ═══════════════════════════════════════════════════════════
    # PROFILE
    # ═══════════════════════════════════════════════════════════

    def get_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get public profile (anonymous — no login needed).

        Uses fallback chain: HTML parse → Web API → GraphQL.

        Args:
            username: Instagram username (without @)

        Returns:
            Profile data dict or None if not found/private
        """
        username = username.lstrip("@").strip().lower()
        return self._client.get_profile_chain(username)

    def get_user_id(self, username: str) -> Optional[int]:
        """
        Get user ID from username (anonymous).

        Args:
            username: Instagram username

        Returns:
            User ID (int) or None
        """
        username = username.lstrip("@").strip().lower()

        # Strategy 1: Get profile (may be HTML-only — no user_id)
        profile = self.get_profile(username)
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

        # Strategy 2: Try web API directly — often returns user IDs
        try:
            web_profile = self._client.get_web_profile(username)
            if web_profile:
                uid = web_profile.get("id") or web_profile.get("pk")
                if uid:
                    return int(uid)
        except Exception:
            pass

        return None

    def get_profile_pic_url(self, username: str) -> Optional[str]:
        """
        Get profile picture URL (anonymous).

        Args:
            username: Instagram username

        Returns:
            HD profile picture URL or None
        """
        profile = self.get_profile(username)
        if profile:
            return (
                profile.get("profile_pic_url_hd")
                or profile.get("profile_pic_url")
            )
        return None

    # ═══════════════════════════════════════════════════════════
    # POSTS
    # ═══════════════════════════════════════════════════════════

    def get_post_by_shortcode(self, shortcode: str) -> Optional[Dict[str, Any]]:
        """
        Get post data by shortcode (anonymous).

        Uses fallback chain: Embed → GraphQL → Web API.

        Args:
            shortcode: Post shortcode (e.g. "ABC123" from instagram.com/p/ABC123/)

        Returns:
            Post data dict or None
        """
        return self._client.get_post_chain(shortcode)

    def get_post_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get post data by Instagram URL (anonymous).

        Args:
            url: Full Instagram post URL
                 e.g. https://instagram.com/p/ABC123/
                 e.g. https://instagram.com/reel/ABC123/

        Returns:
            Post data dict or None
        """
        shortcode = utils.extract_shortcode(url)
        if not shortcode:
            logger.warning(f"[Public] Could not extract shortcode from URL: {url}")
            return None
        return self.get_post_by_shortcode(shortcode)

    def get_posts(
        self,
        username: str,
        max_count: int = 12,
    ) -> List[Dict[str, Any]]:
        """
        Get user's public posts (anonymous).

        Strategy:
        1. Web API (web_profile_info) — returns 12 posts with full data
        2. HTML parse — embedded posts (fallback)
        3. GraphQL with user_id (fallback)

        Args:
            username: Instagram username
            max_count: Maximum number of posts (default 12)

        Returns:
            List of post dicts
        """
        username = username.lstrip("@").strip().lower()

        # Strategy 1: Web API — best source, returns 12 posts
        web_profile = self._client.get_web_profile(username)
        if web_profile:
            media = web_profile.get("edge_owner_to_timeline_media", {})
            edges = media.get("edges", [])
            if edges:
                posts = self._client._parse_timeline_edges(edges)
                if posts:
                    return posts[:max_count]

        # Strategy 2: HTML parse gives us embedded posts
        profile = self._client.get_profile_html(username)
        if profile and profile.get("recent_posts"):
            posts = profile["recent_posts"][:max_count]
            if posts:
                return posts

        # Strategy 3: GraphQL with user_id
        user_id = None
        if web_profile:
            user_id = web_profile.get("id")
        if not user_id and profile:
            user_id = profile.get("user_id")

        if user_id:
            gql_data = self._client.get_user_posts_graphql(
                str(user_id), first=min(max_count, 50)
            )
            if gql_data:
                edges = gql_data.get("edges", [])
                posts = self._client._parse_timeline_edges(edges)
                if posts:
                    return posts[:max_count]

        # Strategy 4: Mobile feed API (with user_id)
        if user_id:
            feed = self._client.get_user_feed_mobile(str(user_id), count=min(max_count, 33))
            if feed and feed.get("items"):
                return feed["items"][:max_count]

        return []

    def get_feed(
        self,
        user_id: int | str,
        max_count: int = 12,
        max_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get user feed via mobile API (anonymous).

        Returns richer data than get_posts():
        - like_count, comment_count per post
        - carousel_media with all images/videos
        - video_url, video_duration
        - location info
        - user tags
        - caption with hashtags

        Supports pagination via max_id.

        Args:
            user_id: User PK (numeric ID, get from get_user_id())
            max_count: Max posts per page (max 33)
            max_id: Pagination cursor (from previous response)

        Returns:
            Dict with: items, next_max_id, more_available, num_results

        Usage:
            user_id = ig.public.get_user_id("nike")
            feed = ig.public.get_feed(user_id, max_count=12)
            for post in feed["items"]:
                print(post["likes"], post["caption"][:50])

            # Pagination:
            page2 = ig.public.get_feed(user_id, max_id=feed["next_max_id"])
        """
        result = self._client.get_user_feed_mobile(
            str(user_id),
            max_id=max_id,
            count=min(max_count, 33),
        )
        if result:
            return result
        return {"items": [], "next_max_id": None, "more_available": False, "num_results": 0}

    def get_all_posts(
        self,
        username: str,
        max_count: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get maximum posts for a user (anonymous).

        Combines multiple strategies:
        1. Web API (12 posts) — fast, first batch
        2. Mobile feed API (paginated) — extends beyond 12

        Args:
            username: Instagram username
            max_count: Maximum total posts (default 50, max ~150)

        Returns:
            List of post dicts (combined from all sources)

        Usage:
            posts = ig.public.get_all_posts("nike", max_count=50)
            print(f"Got {len(posts)} posts")
        """
        username = username.lstrip("@").strip().lower()
        all_posts = []
        seen_pks = set()

        # Stage 1: web_profile_info (first 12 posts + user_id)
        user_id = None
        web_profile = self._client.get_web_profile(username)
        if web_profile:
            user_id = web_profile.get("id") or web_profile.get("pk")
            media = web_profile.get("edge_owner_to_timeline_media", {})
            edges = media.get("edges", [])
            if edges:
                posts = self._client._parse_timeline_edges(edges)
                for p in posts:
                    pk = p.get("pk") or p.get("shortcode")
                    if pk and pk not in seen_pks:
                        seen_pks.add(pk)
                        all_posts.append(p)

        if len(all_posts) >= max_count:
            return all_posts[:max_count]

        # Stage 2: Mobile feed API (paginated, extends beyond 12)
        if not user_id:
            user_id = self.get_user_id(username)

        if user_id:
            max_id = None
            remaining = max_count - len(all_posts)
            max_pages = 5  # Safety limit

            for page in range(max_pages):
                if remaining <= 0:
                    break

                feed = self._client.get_user_feed_mobile(
                    str(user_id),
                    max_id=max_id,
                    count=min(remaining, 33),
                )
                if not feed or not feed.get("items"):
                    break

                for item in feed["items"]:
                    pk = item.get("pk") or item.get("shortcode")
                    if pk and pk not in seen_pks:
                        seen_pks.add(pk)
                        all_posts.append(item)
                        remaining -= 1

                max_id = feed.get("next_max_id")
                if not max_id or not feed.get("more_available"):
                    break

        return all_posts[:max_count]

    def get_media(self, media_id: int | str) -> Optional[Dict[str, Any]]:
        """
        Get single media details via mobile API (anonymous).

        Args:
            media_id: Media PK (numeric ID)

        Returns:
            Post data dict with likes, comments, carousel, video, location, etc.

        Usage:
            media = ig.public.get_media(3823732431648645952)
            print(media["likes"], media["caption"][:50])
        """
        return self._client.get_media_info_mobile(media_id)

    def get_media_urls(self, shortcode: str) -> List[Dict[str, str]]:
        """
        Get all media URLs for a post (images + videos).
        Supports carousel posts — returns ALL images/videos.

        Args:
            shortcode: Post shortcode

        Returns:
            List of dicts with {url, type, width, height}
        """
        post = self.get_post_by_shortcode(shortcode)
        if not post:
            return []

        urls = []

        # Carousel children (GraphSidecar) — ALL images/videos
        carousel = post.get("carousel_media", [])
        if carousel:
            for child in carousel:
                child_url = child.get("display_url")
                if child.get("is_video") and child.get("video_url"):
                    urls.append({
                        "url": child["video_url"],
                        "type": "video",
                    })
                if child_url:
                    # Get highest resolution from display_resources
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

        # Single image post
        for img in post.get("images", []):
            if img.get("url"):
                urls.append({
                    "url": img["url"],
                    "type": "image",
                    "width": img.get("width"),
                    "height": img.get("height"),
                })

        # Video
        if post.get("video_url"):
            urls.append({
                "url": post["video_url"],
                "type": "video",
            })

        # Display URL fallback
        if not urls and post.get("display_url"):
            urls.append({"url": post["display_url"], "type": "image"})

        return urls

    # ═══════════════════════════════════════════════════════════
    # COMMENTS
    # ═══════════════════════════════════════════════════════════

    def get_comments(
        self,
        shortcode: str,
        max_count: int = 24,
    ) -> List[Dict[str, Any]]:
        """
        Get public post comments (anonymous).

        Args:
            shortcode: Post shortcode
            max_count: Maximum comments to fetch

        Returns:
            List of comment dicts
        """
        data = self._client.get_post_comments_graphql(
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

    def get_hashtag_posts(
        self,
        hashtag: str,
        max_count: int = 12,
    ) -> List[Dict[str, Any]]:
        """
        Get posts by hashtag (anonymous).

        Args:
            hashtag: Hashtag name (with or without #)
            max_count: Maximum posts

        Returns:
            List of post dicts
        """
        tag = hashtag.lstrip("#").strip().lower()
        data = self._client.get_hashtag_posts_graphql(tag, first=min(max_count, 50))
        if not data:
            return []

        posts = []
        edges = data.get("edge_hashtag_to_media", {}).get("edges", [])
        posts = self._client._parse_timeline_edges(edges)

        return posts[:max_count]

    # ═══════════════════════════════════════════════════════════
    # SEARCH
    # ═══════════════════════════════════════════════════════════

    def search(
        self,
        query: str,
        context: str = "blended",
    ) -> Dict[str, Any]:
        """
        Search Instagram anonymously.

        Args:
            query: Search query (username, hashtag, keyword)
            context: 'blended' (all), 'user', 'hashtag', or 'place'

        Returns:
            Dict with: users, hashtags, places lists

        Usage:
            results = ig.public.search("cristiano")
            for user in results["users"]:
                print(user["username"], user["follower_count"])
        """
        result = self._client.search_web(query, context=context)
        if result:
            return result
        return {"users": [], "hashtags": [], "places": []}

    # ═══════════════════════════════════════════════════════════
    # REELS
    # ═══════════════════════════════════════════════════════════

    def get_reels(
        self,
        username: str,
        max_count: int = 12,
    ) -> List[Dict[str, Any]]:
        """
        Get user reels anonymously.

        Args:
            username: Instagram username
            max_count: Maximum reels to return

        Returns:
            List of reel dicts with play_count, likes, caption, audio

        Usage:
            reels = ig.public.get_reels("cristiano", max_count=10)
            for reel in reels:
                print(reel["play_count"], reel["likes"])
        """
        username = username.lstrip("@").strip().lower()
        user_id = self.get_user_id(username)
        if not user_id:
            return []

        result = self._client.get_user_reels(user_id, count=min(max_count, 33))
        if result and result.get("items"):
            return result["items"][:max_count]
        return []

    # ═══════════════════════════════════════════════════════════
    # HASHTAG (v2 — web API sections)
    # ═══════════════════════════════════════════════════════════

    def get_hashtag_posts_v2(
        self,
        hashtag: str,
        tab: str = "recent",
        max_count: int = 30,
    ) -> Dict[str, Any]:
        """
        Get hashtag posts via web API (v2, more reliable than GraphQL).

        Args:
            hashtag: Tag name (with or without #)
            tab: 'recent' or 'top'
            max_count: Max posts

        Returns:
            Dict with: tag_name, posts, more_available, media_count

        Usage:
            data = ig.public.get_hashtag_posts_v2("football", tab="top")
            for post in data["posts"]:
                print(post["likes"], post["caption"][:50])
        """
        result = self._client.get_hashtag_sections(
            hashtag, tab=tab
        )
        if result:
            result["posts"] = result["posts"][:max_count]
            return result
        return {"tag_name": hashtag, "posts": [], "more_available": False, "media_count": 0}

    # ═══════════════════════════════════════════════════════════
    # LOCATION
    # ═══════════════════════════════════════════════════════════

    def get_location_posts(
        self,
        location_id: int | str,
        tab: str = "recent",
        max_count: int = 30,
    ) -> Dict[str, Any]:
        """
        Get posts from a location anonymously.

        Args:
            location_id: Location PK (from post data or search)
            tab: 'recent' or 'ranked'
            max_count: Max posts

        Returns:
            Dict with: location info, posts, more_available

        Usage:
            data = ig.public.get_location_posts(213385402)
            print(data["location"]["name"])
            for post in data["posts"]:
                print(post["likes"])
        """
        result = self._client.get_location_sections(
            location_id, tab=tab
        )
        if result:
            result["posts"] = result["posts"][:max_count]
            return result
        return {"location": None, "posts": [], "more_available": False, "media_count": 0}

    # ═══════════════════════════════════════════════════════════
    # SIMILAR ACCOUNTS
    # ═══════════════════════════════════════════════════════════

    def get_similar_accounts(
        self,
        username: str,
    ) -> List[Dict[str, Any]]:
        """
        Get similar/suggested accounts for a user.

        Args:
            username: Instagram username

        Returns:
            List of similar user dicts with username, followers, etc.

        Usage:
            similar = ig.public.get_similar_accounts("nike")
            for acc in similar:
                print(acc["username"], acc["follower_count"])
        """
        username = username.lstrip("@").strip().lower()
        user_id = self.get_user_id(username)
        if not user_id:
            return []

        result = self._client.get_similar_accounts(user_id)
        return result or []

    # ═══════════════════════════════════════════════════════════
    # HIGHLIGHTS
    # ═══════════════════════════════════════════════════════════

    def get_highlights(
        self,
        username: str,
    ) -> List[Dict[str, Any]]:
        """
        Get story highlights for a user anonymously.

        Args:
            username: Instagram username

        Returns:
            List of highlights with title, cover_url, media_count

        Usage:
            highlights = ig.public.get_highlights("nike")
            for h in highlights:
                print(h["title"], h["media_count"])
        """
        username = username.lstrip("@").strip().lower()
        user_id = self.get_user_id(username)
        if not user_id:
            return []

        result = self._client.get_highlights_tray(user_id)
        return result or []

    # ═══════════════════════════════════════════════════════════
    # BULK OPERATIONS
    # ═══════════════════════════════════════════════════════════

    def bulk_profiles(
        self,
        usernames: List[str],
        workers: int = 10,
        callback: Optional[Callable] = None,
    ) -> Dict[str, Dict]:
        """
        Fetch multiple profiles in parallel (anonymous).

        Args:
            usernames: List of usernames
            workers: Parallel workers (default 10)
            callback: Optional callback(username, profile) for progress

        Returns:
            Dict mapping username -> profile dict (or None if failed)

        Usage:
            profiles = ig.public.bulk_profiles(["nike", "adidas", "puma"])
            for username, profile in profiles.items():
                if profile:
                    print(username, profile["followers"])
        """
        results = {}

        def _fetch(username):
            username = username.lstrip("@").strip().lower()
            try:
                profile = self.get_profile(username)
                if callback:
                    callback(username, profile)
                return username, profile
            except Exception as e:
                logger.debug(f"bulk_profiles: {username} failed: {e}")
                return username, None

        with ThreadPoolExecutor(max_workers=min(workers, len(usernames))) as executor:
            futures = {executor.submit(_fetch, u): u for u in usernames}
            for future in as_completed(futures):
                try:
                    username, profile = future.result()
                    results[username] = profile
                except Exception:
                    results[futures[future]] = None

        return results

    def bulk_feeds(
        self,
        user_ids: List[int | str],
        max_count: int = 12,
        workers: int = 10,
        callback: Optional[Callable] = None,
    ) -> Dict[str, Dict]:
        """
        Fetch multiple user feeds in parallel (anonymous).

        Args:
            user_ids: List of user PKs
            max_count: Posts per user
            workers: Parallel workers
            callback: Optional callback(user_id, feed) for progress

        Returns:
            Dict mapping user_id -> feed dict

        Usage:
            feeds = ig.public.bulk_feeds([13460080, 173560420])
            for uid, feed in feeds.items():
                print(uid, len(feed.get("items", [])))
        """
        results = {}

        def _fetch(user_id):
            uid = str(user_id)
            try:
                feed = self.get_feed(uid, max_count=max_count)
                if callback:
                    callback(uid, feed)
                return uid, feed
            except Exception as e:
                logger.debug(f"bulk_feeds: {uid} failed: {e}")
                return uid, {"items": [], "error": str(e)}

        with ThreadPoolExecutor(max_workers=min(workers, len(user_ids))) as executor:
            futures = {executor.submit(_fetch, uid): uid for uid in user_ids}
            for future in as_completed(futures):
                try:
                    uid, feed = future.result()
                    results[uid] = feed
                except Exception:
                    results[str(futures[future])] = {"items": [], "error": "unknown"}

        return results

    # ═══════════════════════════════════════════════════════════
    # UTILITY
    # ═══════════════════════════════════════════════════════════

    def is_public(self, username: str) -> Optional[bool]:
        """
        Check if account is public (anonymous).

        Returns:
            True = public, False = private, None = not found
        """
        profile = self.get_profile(username)
        if profile is None:
            return None
        return not profile.get("is_private", True)

    def exists(self, username: str) -> bool:
        """Check if username exists (anonymous)."""
        return self.get_profile(username) is not None

    @property
    def request_count(self) -> int:
        """Total anonymous requests made."""
        return self._client.request_count
