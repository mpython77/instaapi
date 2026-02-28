"""
Async Export API — Lead Generation & Data Export
=================================================
Async version of ExportAPI. Full feature parity.
"""

import csv
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

from .export import ExportFilter

logger = logging.getLogger("instaapi.export")


class AsyncExportAPI:
    """
    Async Instagram data export — CSV, JSON, streaming.

    Composes: AsyncUsersAPI, AsyncFriendshipsAPI, AsyncMediaAPI, AsyncHashtagsAPI.
    """

    USER_COLUMNS = [
        "username", "full_name", "user_id", "followers", "following",
        "posts_count", "is_private", "is_verified", "is_business",
        "biography", "external_url", "profile_pic_url", "category",
    ]

    def __init__(self, client, users_api, friendships_api, media_api, hashtags_api):
        self._client = client
        self._users = users_api
        self._friendships = friendships_api
        self._media = media_api
        self._hashtags = hashtags_api

    async def followers_to_csv(
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
            enrich: If True, fetch full profile for each user
            on_progress: Callback(exported_count, total_count)

        Returns:
            dict: {exported, filtered_out, total_fetched, file, duration_seconds}
        """
        return await self._export_user_list(
            username=username, list_type="followers",
            output_path=output_path, max_count=max_count,
            filters=filters, enrich=enrich, on_progress=on_progress,
        )

    async def following_to_csv(
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
            dict: {exported, filtered_out, total_fetched, file, duration_seconds}
        """
        return await self._export_user_list(
            username=username, list_type="following",
            output_path=output_path, max_count=max_count,
            filters=filters, enrich=enrich, on_progress=on_progress,
        )

    async def _export_user_list(
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
        user = await self._users.get_by_username(username)
        user_id = user.pk if hasattr(user, "pk") else user.get("pk") or user.get("user_id")
        if not user_id:
            raise ValueError(f"Could not resolve user ID for '{username}'")

        if list_type == "followers":
            get_fn = self._friendships.get_followers
        else:
            get_fn = self._friendships.get_following

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
                    result = await get_fn(user_id, count=50, after=cursor)
                except Exception as e:
                    logger.warning(f"Export {list_type} page error: {e}")
                    break

                users = result.get("users", [])
                if not users:
                    break

                for u in users:
                    total_fetched += 1
                    row = self._user_to_row(u)
                    if enrich and row.get("username"):
                        try:
                            full = await self._users.get_by_username(row["username"])
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
        return {
            "exported": exported, "filtered_out": filtered_out,
            "total_fetched": total_fetched,
            "file": os.path.abspath(output_path),
            "duration_seconds": round(duration, 1),
        }

    async def post_likers(
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
            result = await self._media.get_likers(media_id)
        except Exception as e:
            return {"exported": 0, "error": str(e)}
        users = result.get("users", []) if isinstance(result, dict) else []
        return self._write_user_list(users, output_path, filters, "likers", start)

    async def to_json(
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
            dict: {file, duration_seconds}
        """
        start = time.time()
        data: Dict[str, Any] = {"exported_at": datetime.now().isoformat(), "username": username}
        try:
            profile = await self._users.get_full_profile(username)
            data["profile"] = profile if isinstance(profile, dict) else self._user_to_row(profile)
        except Exception as e:
            data["profile"] = {"error": str(e)}

        if include_posts:
            try:
                user_id = data["profile"].get("user_id") or data["profile"].get("pk")
                if user_id:
                    feed = await self._client.get(f"/feed/user/{user_id}/", params={"count": "12"}, rate_category="get_feed")
                    data["recent_posts"] = feed.get("items", []) if feed else []
            except Exception as e:
                data["recent_posts"] = {"error": str(e)}

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        duration = time.time() - start
        return {"file": os.path.abspath(output_path), "duration_seconds": round(duration, 1)}

    def _user_to_row(self, user) -> Dict:
        """Normalize user object/dict to export row."""
        if hasattr(user, "__dict__"):
            return {
                "username": getattr(user, "username", ""),
                "full_name": getattr(user, "full_name", ""),
                "user_id": getattr(user, "pk", "") or getattr(user, "user_id", ""),
                "followers": getattr(user, "followers", 0) or getattr(user, "follower_count", 0),
                "following": getattr(user, "following", 0) or getattr(user, "following_count", 0),
                "posts_count": getattr(user, "media_count", 0) or getattr(user, "posts_count", 0),
                "is_private": getattr(user, "is_private", False),
                "is_verified": getattr(user, "is_verified", False),
                "is_business": getattr(user, "is_business_account", False) or getattr(user, "is_business", False),
                "biography": getattr(user, "biography", ""),
                "external_url": getattr(user, "external_url", ""),
                "profile_pic_url": getattr(user, "profile_pic_url", ""),
                "category": getattr(user, "category", "") or getattr(user, "category_name", ""),
            }
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

    def _write_user_list(self, users, output_path, filters, label, start_time) -> Dict[str, Any]:
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
        return {
            "exported": exported, "filtered_out": filtered_out,
            "total_fetched": len(users),
            "file": os.path.abspath(output_path),
            "duration_seconds": round(duration, 1),
        }
