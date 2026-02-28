"""
Async Data Pipeline — SQLite / JSONL Export
============================================
Async version of PipelineAPI. Full feature parity.
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("instaharvest_v2.pipeline")


class AsyncPipelineAPI:
    """
    Async data pipeline — stream Instagram data to databases/files.

    Composes: AsyncUsersAPI, AsyncFriendshipsAPI, AsyncMediaAPI.
    """

    def __init__(self, client, users_api, friendships_api, media_api):
        self._client = client
        self._users = users_api
        self._friendships = friendships_api
        self._media = media_api

    async def to_sqlite(
        self,
        username: str,
        db_path: str,
        include_posts: bool = True,
        include_followers: bool = True,
        include_following: bool = False,
        max_followers: int = 5000,
        max_posts: int = 100,
        incremental: bool = False,
        on_progress: Optional[Callable[[str, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Export account data to SQLite database.

        Creates tables: profile, posts, followers, following.

        Args:
            username: Target username
            db_path: SQLite database path
            include_posts: Include posts table
            include_followers: Include followers table
            include_following: Include following table
            max_followers: Max followers to fetch
            max_posts: Max posts to fetch
            incremental: Append mode (don't drop tables)
            on_progress: Callback(stage, count)

        Returns:
            dict: {file, tables, rows, duration_seconds}
        """
        start = time.time()
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        user = await self._users.get_by_username(username)
        user_id = user.pk if hasattr(user, "pk") else user.get("pk", 0)
        user_dict = self._user_to_dict(user)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        self._create_tables(cursor)

        # Profile
        cursor.execute(
            "INSERT OR REPLACE INTO profile (pk, username, full_name, followers, following, posts_count, biography, is_verified, is_private, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (user_dict.get("pk"), user_dict.get("username"), user_dict.get("full_name"),
             user_dict.get("followers"), user_dict.get("following"), user_dict.get("posts_count"),
             user_dict.get("biography"), user_dict.get("is_verified"), user_dict.get("is_private"),
             datetime.now().isoformat()),
        )
        if on_progress:
            on_progress("profile", 1)

        rows = {"profile": 1, "posts": 0, "followers": 0, "following": 0}

        # Posts
        if include_posts and user_id:
            posts = await self._fetch_posts(user_id, max_posts)
            for p in posts:
                cursor.execute(
                    "INSERT OR REPLACE INTO posts (pk, shortcode, media_type, like_count, comment_count, caption, taken_at) VALUES (?,?,?,?,?,?,?)",
                    (p.get("pk"), p.get("code"), p.get("media_type", 1),
                     p.get("like_count", 0), p.get("comment_count", 0),
                     (p.get("caption", {}) or {}).get("text", ""),
                     p.get("taken_at", 0)),
                )
                rows["posts"] += 1
            if on_progress:
                on_progress("posts", rows["posts"])

        # Followers
        if include_followers and user_id:
            followers = await self._fetch_list(user_id, "followers", max_followers)
            for f in followers:
                fd = self._user_to_dict(f)
                cursor.execute(
                    "INSERT OR REPLACE INTO followers (pk, username, full_name, is_private, is_verified) VALUES (?,?,?,?,?)",
                    (fd.get("pk"), fd.get("username"), fd.get("full_name"),
                     fd.get("is_private"), fd.get("is_verified")),
                )
                rows["followers"] += 1
            if on_progress:
                on_progress("followers", rows["followers"])

        # Following
        if include_following and user_id:
            following = await self._fetch_list(user_id, "following", max_followers)
            for f in following:
                fd = self._user_to_dict(f)
                cursor.execute(
                    "INSERT OR REPLACE INTO following (pk, username, full_name, is_private, is_verified) VALUES (?,?,?,?,?)",
                    (fd.get("pk"), fd.get("username"), fd.get("full_name"),
                     fd.get("is_private"), fd.get("is_verified")),
                )
                rows["following"] += 1
            if on_progress:
                on_progress("following", rows["following"])

        conn.commit()
        conn.close()

        return {
            "file": os.path.abspath(db_path),
            "tables": [k for k, v in rows.items() if v > 0],
            "rows": rows,
            "duration_seconds": round(time.time() - start, 1),
        }

    async def to_jsonl(
        self,
        username: str,
        output_path: str,
        include_posts: bool = True,
        include_followers: bool = True,
        max_followers: int = 5000,
        max_posts: int = 100,
        on_progress: Optional[Callable[[str, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Export to JSONL (one JSON object per line).

        Args:
            username: Target username
            output_path: JSONL file path
            include_posts: Include posts
            include_followers: Include followers
            max_followers: Max followers
            max_posts: Max posts
            on_progress: Callback(stage, count)

        Returns:
            dict: {file, lines, duration_seconds}
        """
        start = time.time()
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        user = await self._users.get_by_username(username)
        user_id = user.pk if hasattr(user, "pk") else user.get("pk", 0)
        user_dict = self._user_to_dict(user)

        lines = 0
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "profile", **user_dict}, default=str) + "\n")
            lines += 1

            if include_posts and user_id:
                posts = await self._fetch_posts(user_id, max_posts)
                for p in posts:
                    f.write(json.dumps({"type": "post", **p}, default=str) + "\n")
                    lines += 1
                if on_progress:
                    on_progress("posts", len(posts))

            if include_followers and user_id:
                followers = await self._fetch_list(user_id, "followers", max_followers)
                for fol in followers:
                    fd = self._user_to_dict(fol)
                    f.write(json.dumps({"type": "follower", **fd}, default=str) + "\n")
                    lines += 1
                if on_progress:
                    on_progress("followers", len(followers))

        return {
            "file": os.path.abspath(output_path),
            "lines": lines,
            "duration_seconds": round(time.time() - start, 1),
        }

    @staticmethod
    def _create_tables(cursor):
        """Create SQLite tables."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profile (
                pk INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
                followers INTEGER, following INTEGER, posts_count INTEGER,
                biography TEXT, is_verified INTEGER, is_private INTEGER, updated_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                pk INTEGER PRIMARY KEY, shortcode TEXT, media_type INTEGER,
                like_count INTEGER, comment_count INTEGER, caption TEXT, taken_at INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS followers (
                pk INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
                is_private INTEGER, is_verified INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS following (
                pk INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
                is_private INTEGER, is_verified INTEGER
            )
        """)

    @staticmethod
    def _user_to_dict(user) -> Dict:
        """Convert user object to dict."""
        if hasattr(user, "pk"):
            return {
                "pk": getattr(user, "pk", 0),
                "username": getattr(user, "username", ""),
                "full_name": getattr(user, "full_name", ""),
                "followers": getattr(user, "followers", 0),
                "following": getattr(user, "following", 0),
                "posts_count": getattr(user, "posts_count", 0),
                "biography": getattr(user, "biography", ""),
                "is_verified": getattr(user, "is_verified", False),
                "is_private": getattr(user, "is_private", False),
            }
        elif isinstance(user, dict):
            return {
                "pk": user.get("pk", 0),
                "username": user.get("username", ""),
                "full_name": user.get("full_name", ""),
                "followers": user.get("follower_count", 0) or user.get("followers", 0),
                "following": user.get("following_count", 0) or user.get("following", 0),
                "posts_count": user.get("media_count", 0),
                "biography": user.get("biography", ""),
                "is_verified": user.get("is_verified", False),
                "is_private": user.get("is_private", False),
            }
        return {"username": str(user)}

    async def _fetch_posts(self, user_id, count: int) -> List[Dict]:
        """Fetch user posts."""
        try:
            data = await self._client.get(
                f"/feed/user/{user_id}/", params={"count": str(count)}, rate_category="get_feed",
            )
            return data.get("items", []) if data else []
        except Exception as e:
            logger.warning(f"Fetch posts error: {e}")
            return []

    async def _fetch_list(self, user_id, list_type: str, max_count: int) -> List:
        """Fetch followers or following list."""
        all_users: list = []
        cursor = None
        while len(all_users) < max_count:
            try:
                fn = self._friendships.get_followers if list_type == "followers" else self._friendships.get_following
                result = await fn(user_id, count=50, after=cursor)
                all_users.extend(result.get("users", []))
                cursor = result.get("next_max_id")
                if not cursor:
                    break
            except Exception:
                break
        return all_users[:max_count]
