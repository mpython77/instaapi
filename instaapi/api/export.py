"""
Export API — Lead Generation & Data Export
==========================================
Export followers, following, hashtag users, post likers/commenters
to CSV/JSON with powerful filtering and streaming.

Usage:
    ig = Instagram.from_env(".env")

    # Export followers to CSV
    ig.export.followers_to_csv("cristiano", "followers.csv", max_count=1000)

    # Export hashtag users
    ig.export.hashtag_users("python", "python_users.csv", count=500)

    # Export post likers
    ig.export.post_likers(media_id, "likers.csv")

    # Full profile + posts to JSON
    ig.export.to_json("cristiano", "cristiano_full.json")
"""

import csv
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger("instaapi.export")


class ExportFilter:
    """
    Filter users during export.

    Usage:
        f = ExportFilter(min_followers=100, max_followers=50000, is_business=True)
        ig.export.followers_to_csv("user", "out.csv", filters=f)
    """

    def __init__(
        self,
        min_followers: int = 0,
        max_followers: int = 0,
        min_following: int = 0,
        max_following: int = 0,
        min_posts: int = 0,
        is_private: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        is_business: Optional[bool] = None,
        has_bio: Optional[bool] = None,
        has_profile_pic: Optional[bool] = None,
        bio_keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None,
        custom_filter: Optional[Callable[[Dict], bool]] = None,
    ):
        self.min_followers = min_followers
        self.max_followers = max_followers
        self.min_following = min_following
        self.max_following = max_following
        self.min_posts = min_posts
        self.is_private = is_private
        self.is_verified = is_verified
        self.is_business = is_business
        self.has_bio = has_bio
        self.has_profile_pic = has_profile_pic
        self.bio_keywords = [k.lower() for k in (bio_keywords or [])]
        self.exclude_keywords = [k.lower() for k in (exclude_keywords or [])]
        self.custom_filter = custom_filter

    def matches(self, user_data: Dict) -> bool:
        """Check if user passes all filters."""
        followers = user_data.get("follower_count", 0) or user_data.get("followers", 0) or 0
        following = user_data.get("following_count", 0) or user_data.get("following", 0) or 0
        posts = user_data.get("media_count", 0) or user_data.get("posts_count", 0) or 0
        bio = (user_data.get("biography", "") or "").lower()

        if self.min_followers and followers < self.min_followers:
            return False
        if self.max_followers and followers > self.max_followers:
            return False
        if self.min_following and following < self.min_following:
            return False
        if self.max_following and following > self.max_following:
            return False
        if self.min_posts and posts < self.min_posts:
            return False
        if self.is_private is not None and user_data.get("is_private") != self.is_private:
            return False
        if self.is_verified is not None and user_data.get("is_verified") != self.is_verified:
            return False
        if self.is_business is not None and user_data.get("is_business_account") != self.is_business:
            return False
        if self.has_bio is True and not bio.strip():
            return False
        if self.has_bio is False and bio.strip():
            return False
        if self.has_profile_pic is True:
            pic = user_data.get("profile_pic_url", "")
            if not pic or "default" in pic.lower():
                return False
        if self.bio_keywords and not any(kw in bio for kw in self.bio_keywords):
            return False
        if self.exclude_keywords and any(kw in bio for kw in self.exclude_keywords):
            return False
        if self.custom_filter and not self.custom_filter(user_data):
            return False
        return True


class ExportAPI:
    """
    Instagram data export — CSV, JSON, streaming.

    Composes: UsersAPI, FriendshipsAPI, MediaAPI, HashtagsAPI.
    """

    # Default CSV columns for user exports
    USER_COLUMNS = [
        "username", "full_name", "user_id", "followers", "following",
        "posts_count", "is_private", "is_verified", "is_business",
        "biography", "external_url", "profile_pic_url", "category",
    ]

    COMMENT_COLUMNS = [
        "username", "user_id", "text", "likes", "created_at", "is_reply",
    ]

    def __init__(self, client, users_api, friendships_api, media_api, hashtags_api):
        self._client = client
        self._users = users_api
        self._friendships = friendships_api
        self._media = media_api
        self._hashtags = hashtags_api

    # ═══════════════════════════════════════════════════════════
    # FOLLOWERS / FOLLOWING EXPORT
    # ═══════════════════════════════════════════════════════════

    def followers_to_csv(
        self,
        username: str,
        output_path: str,
        max_count: int = 0,
        filters: Optional[ExportFilter] = None,
        enrich: bool = False,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Export followers to CSV.

        Args:
            username: Target username
            output_path: CSV file path
            max_count: Max followers (0 = all)
            filters: ExportFilter for filtering
            enrich: If True, fetch full profile for each user (slower but more data)
            on_progress: Callback(exported_count, total_count)

        Returns:
            dict: {exported: int, filtered: int, total: int, file: str, duration: float}
        """
        return self._export_user_list(
            username=username,
            list_type="followers",
            output_path=output_path,
            max_count=max_count,
            filters=filters,
            enrich=enrich,
            on_progress=on_progress,
        )

    def following_to_csv(
        self,
        username: str,
        output_path: str,
        max_count: int = 0,
        filters: Optional[ExportFilter] = None,
        enrich: bool = False,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Export following to CSV.

        Args:
            username: Target username
            output_path: CSV file path
            max_count: Max following to export (0 = all)
            filters: ExportFilter for filtering
            enrich: If True, fetch full profile for each user
            on_progress: Callback(exported_count, total_count)

        Returns:
            dict: {exported: int, filtered: int, total: int, file: str}
        """
        return self._export_user_list(
            username=username,
            list_type="following",
            output_path=output_path,
            max_count=max_count,
            filters=filters,
            enrich=enrich,
            on_progress=on_progress,
        )

    def _export_user_list(
        self,
        username: str,
        list_type: str,
        output_path: str,
        max_count: int = 0,
        filters: Optional[ExportFilter] = None,
        enrich: bool = False,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """Internal: export followers or following list."""
        start = time.time()

        # Resolve user ID
        user = self._users.get_by_username(username)
        user_id = user.pk if hasattr(user, "pk") else user.get("pk") or user.get("user_id")
        if not user_id:
            raise ValueError(f"Could not resolve user ID for '{username}'")

        # Determine API method
        if list_type == "followers":
            get_fn = self._friendships.get_followers
        else:
            get_fn = self._friendships.get_following

        # Collect users with pagination
        exported = 0
        filtered_out = 0
        total_fetched = 0
        cursor = None

        effective_max = max_count if max_count > 0 else 100_000

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.USER_COLUMNS, extrasaction="ignore")
            writer.writeheader()

            while exported < effective_max:
                try:
                    result = get_fn(user_id, count=50, after=cursor)
                except Exception as e:
                    logger.warning(f"Export {list_type} page error: {e}")
                    break

                users = result.get("users", [])
                if not users:
                    break

                for u in users:
                    total_fetched += 1
                    row = self._user_to_row(u)

                    # Enrich with full profile
                    if enrich and row.get("username"):
                        try:
                            full = self._users.get_by_username(row["username"])
                            row = self._user_to_row(full)
                        except Exception:
                            pass

                    if filters and not filters.matches(row):
                        filtered_out += 1
                        continue

                    writer.writerow(row)
                    exported += 1

                    if on_progress:
                        on_progress(exported, total_fetched)

                    if exported >= effective_max:
                        break

                cursor = result.get("next_max_id") or result.get("next_cursor")
                if not cursor:
                    break

        duration = time.time() - start
        summary = {
            "exported": exported,
            "filtered_out": filtered_out,
            "total_fetched": total_fetched,
            "file": os.path.abspath(output_path),
            "duration_seconds": round(duration, 1),
        }
        logger.info(f"📥 Export {list_type}: {exported} users → {output_path} ({duration:.1f}s)")
        return summary

    # ═══════════════════════════════════════════════════════════
    # HASHTAG USERS
    # ═══════════════════════════════════════════════════════════

    def hashtag_users(
        self,
        tag: str,
        output_path: str,
        count: int = 100,
        section: str = "recent",
        filters: Optional[ExportFilter] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Export users who posted with a hashtag.

        Args:
            tag: Hashtag (without #)
            output_path: CSV output path
            count: Max users to collect
            section: 'recent' or 'top'
            filters: ExportFilter
            on_progress: Callback(exported, total)

        Returns:
            dict: {exported, filtered_out, total_fetched, file, duration_seconds}
        """
        start = time.time()
        tag = tag.lstrip("#").strip().lower()

        seen_users = set()
        exported = 0
        filtered_out = 0
        cursor = None

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.USER_COLUMNS, extrasaction="ignore")
            writer.writeheader()

            pages = 0
            max_pages = max(count // 10, 5)

            while exported < count and pages < max_pages:
                try:
                    result = self._hashtags.get_recent_media(tag, max_id=cursor)
                except Exception as e:
                    logger.warning(f"Hashtag page error: {e}")
                    break

                items = result.get("items", []) if isinstance(result, dict) else []
                if not items:
                    # Try sections endpoint
                    try:
                        result = self._hashtags.get_sections(tag, tab=section, max_id=cursor)
                        sections = result.get("sections", []) if isinstance(result, dict) else []
                        items = []
                        for sec in sections:
                            layout = sec.get("layout_content", {})
                            for m in layout.get("medias", []):
                                media = m.get("media", {})
                                if media:
                                    items.append(media)
                    except Exception:
                        break

                if not items:
                    break

                for item in items:
                    user_data = item.get("user", {})
                    if not user_data:
                        continue
                    uname = user_data.get("username", "")
                    if uname in seen_users:
                        continue
                    seen_users.add(uname)

                    row = self._user_to_row(user_data)

                    if filters and not filters.matches(row):
                        filtered_out += 1
                        continue

                    writer.writerow(row)
                    exported += 1
                    if on_progress:
                        on_progress(exported, len(seen_users))
                    if exported >= count:
                        break

                cursor = (
                    result.get("next_max_id")
                    or result.get("next_cursor")
                    or result.get("next_page")
                )
                if not cursor:
                    break
                pages += 1

        duration = time.time() - start
        summary = {
            "exported": exported,
            "filtered_out": filtered_out,
            "total_fetched": len(seen_users) + filtered_out,
            "file": os.path.abspath(output_path),
            "duration_seconds": round(duration, 1),
        }
        logger.info(f"📥 Export #{tag}: {exported} users → {output_path} ({duration:.1f}s)")
        return summary

    # ═══════════════════════════════════════════════════════════
    # POST LIKERS / COMMENTERS
    # ═══════════════════════════════════════════════════════════

    def post_likers(
        self,
        media_id: Union[int, str],
        output_path: str,
        filters: Optional[ExportFilter] = None,
    ) -> Dict[str, Any]:
        """
        Export post likers to CSV.

        Args:
            media_id: Media PK
            output_path: CSV output path
            filters: ExportFilter

        Returns:
            dict: {exported, filtered_out, total_fetched, file}
        """
        start = time.time()
        try:
            result = self._media.get_likers(media_id)
        except Exception as e:
            logger.error(f"Get likers error: {e}")
            return {"exported": 0, "error": str(e)}

        users = result.get("users", []) if isinstance(result, dict) else []
        return self._write_user_list(users, output_path, filters, "likers", start)

    def post_commenters(
        self,
        media_id: Union[int, str],
        output_path: str,
        max_pages: int = 10,
        filters: Optional[ExportFilter] = None,
    ) -> Dict[str, Any]:
        """
        Export post commenters to CSV.

        Args:
            media_id: Media PK
            output_path: CSV output path
            max_pages: Max comment pages
            filters: ExportFilter

        Returns:
            dict: {exported, filtered_out, total_fetched, file}
        """
        start = time.time()
        try:
            comments = self._media.get_all_comments(media_id, max_pages=max_pages)
        except Exception as e:
            logger.error(f"Get comments error: {e}")
            return {"exported": 0, "error": str(e)}

        seen = set()
        users = []
        comment_list = comments if isinstance(comments, list) else []
        for c in comment_list:
            user = c.get("user", {}) if isinstance(c, dict) else {}
            uname = user.get("username")
            if uname and uname not in seen:
                seen.add(uname)
                users.append(user)

        return self._write_user_list(users, output_path, filters, "commenters", start)

    # ═══════════════════════════════════════════════════════════
    # FULL PROFILE TO JSON
    # ═══════════════════════════════════════════════════════════

    def to_json(
        self,
        username: str,
        output_path: str,
        include_posts: bool = True,
        include_followers_sample: int = 0,
    ) -> Dict[str, Any]:
        """
        Export full profile data to JSON.

        Args:
            username: Instagram username
            output_path: JSON output path
            include_posts: Include recent posts
            include_followers_sample: Number of followers to include (0 = none)

        Returns:
            dict: {file, sections}
        """
        start = time.time()
        data: Dict[str, Any] = {"exported_at": datetime.now().isoformat(), "username": username}

        # Profile
        try:
            profile = self._users.get_full_profile(username)
            data["profile"] = profile if isinstance(profile, dict) else self._user_to_row(profile)
        except Exception as e:
            data["profile"] = {"error": str(e)}

        # Recent posts
        if include_posts:
            try:
                user_id = data["profile"].get("user_id") or data["profile"].get("pk")
                if user_id:
                    feed = self._client.request("GET", f"/api/v1/feed/user/{user_id}/", params={"count": "12"})
                    data["recent_posts"] = feed.get("items", []) if feed else []
            except Exception as e:
                data["recent_posts"] = {"error": str(e)}

        # Followers sample
        if include_followers_sample > 0:
            try:
                user_id = data["profile"].get("user_id") or data["profile"].get("pk")
                if user_id:
                    result = self._friendships.get_followers(user_id, count=include_followers_sample)
                    data["followers_sample"] = [
                        self._user_to_row(u) for u in result.get("users", [])
                    ]
            except Exception as e:
                data["followers_sample"] = {"error": str(e)}

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        duration = time.time() - start
        logger.info(f"📥 Export JSON: {username} → {output_path} ({duration:.1f}s)")
        return {"file": os.path.abspath(output_path), "duration_seconds": round(duration, 1)}

    # ═══════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════

    def _user_to_row(self, user) -> Dict:
        """Normalize user object/dict to export row."""
        if hasattr(user, "__dict__"):
            d = {}
            d["username"] = getattr(user, "username", "")
            d["full_name"] = getattr(user, "full_name", "")
            d["user_id"] = getattr(user, "pk", "") or getattr(user, "user_id", "")
            d["followers"] = getattr(user, "followers", 0) or getattr(user, "follower_count", 0)
            d["following"] = getattr(user, "following", 0) or getattr(user, "following_count", 0)
            d["posts_count"] = getattr(user, "media_count", 0) or getattr(user, "posts_count", 0)
            d["is_private"] = getattr(user, "is_private", False)
            d["is_verified"] = getattr(user, "is_verified", False)
            d["is_business"] = getattr(user, "is_business_account", False) or getattr(user, "is_business", False)
            d["biography"] = getattr(user, "biography", "")
            d["external_url"] = getattr(user, "external_url", "")
            d["profile_pic_url"] = getattr(user, "profile_pic_url", "")
            d["category"] = getattr(user, "category", "") or getattr(user, "category_name", "")
            return d
        elif isinstance(user, dict):
            return {
                "username": user.get("username", ""),
                "full_name": user.get("full_name", ""),
                "user_id": user.get("pk") or user.get("user_id", ""),
                "followers": user.get("follower_count", 0) or user.get("followers", 0),
                "following": user.get("following_count", 0) or user.get("following", 0),
                "posts_count": user.get("media_count", 0) or user.get("posts_count", 0),
                "is_private": user.get("is_private", False),
                "is_verified": user.get("is_verified", False),
                "is_business": user.get("is_business_account", False),
                "biography": user.get("biography", ""),
                "external_url": user.get("external_url", ""),
                "profile_pic_url": user.get("profile_pic_url", ""),
                "category": user.get("category_name", "") or user.get("category", ""),
            }
        return {"username": str(user)}

    def _write_user_list(
        self,
        users: List,
        output_path: str,
        filters: Optional[ExportFilter],
        label: str,
        start_time: float,
    ) -> Dict[str, Any]:
        """Write a list of users to CSV."""
        exported = 0
        filtered_out = 0

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.USER_COLUMNS, extrasaction="ignore")
            writer.writeheader()

            for u in users:
                row = self._user_to_row(u)
                if filters and not filters.matches(row):
                    filtered_out += 1
                    continue
                writer.writerow(row)
                exported += 1

        duration = time.time() - start_time
        summary = {
            "exported": exported,
            "filtered_out": filtered_out,
            "total_fetched": len(users),
            "file": os.path.abspath(output_path),
            "duration_seconds": round(duration, 1),
        }
        logger.info(f"📥 Export {label}: {exported} users → {output_path} ({duration:.1f}s)")
        return summary
