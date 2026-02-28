"""
Data Pipeline — SQLite / JSONL Export
======================================
Stream Instagram data to SQLite database or JSONL files.
Incremental updates with deduplication.

Usage:
    ig = Instagram.from_env(".env")

    # Export to SQLite
    ig.pipeline.to_sqlite("cristiano", "data.db")

    # Export to JSONL (one JSON per line)
    ig.pipeline.to_jsonl("cristiano", "data.jsonl")

    # Incremental update
    ig.pipeline.to_sqlite("cristiano", "data.db", incremental=True)
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("instaapi.pipeline")


class PipelineAPI:
    """
    Data pipeline — stream Instagram data to databases/files.

    Composes: UsersAPI, FriendshipsAPI, MediaAPI.
    """

    def __init__(self, client, users_api, friendships_api, media_api):
        self._client = client
        self._users = users_api
        self._friendships = friendships_api
        self._media = media_api

    # ═══════════════════════════════════════════════════════════
    # SQLITE
    # ═══════════════════════════════════════════════════════════

    def to_sqlite(
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
            db_path: SQLite db file path
            include_posts: Include posts table
            include_followers: Include followers table
            include_following: Include following table
            max_followers: Max followers to store
            max_posts: Max posts to store
            incremental: If True, only add new data
            on_progress: Callback(section_name, count)

        Returns:
            dict: {tables_created, rows_inserted, file, duration_seconds}
        """
        start = time.time()
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        rows_inserted = 0

        try:
            # Create tables
            self._create_tables(cursor)
            conn.commit()

            # Profile
            user = self._users.get_by_username(username)
            user_id = getattr(user, "pk", None) or (user.get("pk") if isinstance(user, dict) else None)
            profile_data = self._user_to_dict(user)
            profile_data["scraped_at"] = datetime.now().isoformat()

            cursor.execute(
                """INSERT OR REPLACE INTO profiles
                (user_id, username, full_name, followers, following, posts_count,
                 is_private, is_verified, biography, external_url, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    profile_data.get("user_id"), profile_data.get("username"),
                    profile_data.get("full_name"), profile_data.get("followers"),
                    profile_data.get("following"), profile_data.get("posts_count"),
                    profile_data.get("is_private"), profile_data.get("is_verified"),
                    profile_data.get("biography"), profile_data.get("external_url"),
                    profile_data.get("scraped_at"),
                )
            )
            rows_inserted += 1
            if on_progress:
                on_progress("profile", 1)

            # Posts
            if include_posts and user_id:
                posts = self._fetch_posts(user_id, max_posts)
                for post in posts:
                    media_id = post.get("pk") or post.get("id")
                    if incremental:
                        cursor.execute("SELECT 1 FROM posts WHERE media_id=?", (str(media_id),))
                        if cursor.fetchone():
                            continue

                    caption = post.get("caption", {})
                    caption_text = caption.get("text", "") if isinstance(caption, dict) else str(caption or "")
                    taken_at = post.get("taken_at", 0)

                    cursor.execute(
                        """INSERT OR REPLACE INTO posts
                        (media_id, shortcode, user_id, media_type, likes, comments,
                         caption, taken_at, scraped_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            str(media_id), post.get("code", ""), str(user_id),
                            post.get("media_type", 1),
                            post.get("like_count", 0), post.get("comment_count", 0),
                            caption_text, taken_at, datetime.now().isoformat(),
                        )
                    )
                    rows_inserted += 1

                if on_progress:
                    on_progress("posts", len(posts))

            # Followers
            if include_followers and user_id:
                followers = self._fetch_list(user_id, "followers", max_followers)
                for f in followers:
                    fid = f.get("pk")
                    if incremental:
                        cursor.execute("SELECT 1 FROM followers WHERE user_id=? AND follower_id=?",
                                       (str(user_id), str(fid)))
                        if cursor.fetchone():
                            continue
                    cursor.execute(
                        """INSERT OR REPLACE INTO followers
                        (user_id, follower_id, follower_username, follower_fullname,
                         is_private, is_verified, scraped_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            str(user_id), str(fid), f.get("username", ""),
                            f.get("full_name", ""), f.get("is_private", False),
                            f.get("is_verified", False), datetime.now().isoformat(),
                        )
                    )
                    rows_inserted += 1

                if on_progress:
                    on_progress("followers", len(followers))

            # Following
            if include_following and user_id:
                following = self._fetch_list(user_id, "following", max_followers)
                for f in following:
                    fid = f.get("pk")
                    cursor.execute(
                        """INSERT OR REPLACE INTO following
                        (user_id, following_id, following_username, following_fullname,
                         is_private, is_verified, scraped_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            str(user_id), str(fid), f.get("username", ""),
                            f.get("full_name", ""), f.get("is_private", False),
                            f.get("is_verified", False), datetime.now().isoformat(),
                        )
                    )
                    rows_inserted += 1

                if on_progress:
                    on_progress("following", len(following))

            conn.commit()

        finally:
            conn.close()

        duration = time.time() - start
        logger.info(f"🗄️ SQLite @{username}: {rows_inserted} rows → {db_path} ({duration:.1f}s)")
        return {
            "rows_inserted": rows_inserted,
            "file": os.path.abspath(db_path),
            "duration_seconds": round(duration, 1),
        }

    # ═══════════════════════════════════════════════════════════
    # JSONL
    # ═══════════════════════════════════════════════════════════

    def to_jsonl(
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

        Each line has {"type": "profile"|"post"|"follower", ...data}.

        Args:
            username: Target username
            output_path: JSONL file path
            include_posts: Include posts
            include_followers: Include followers
            max_followers: Max followers
            max_posts: Max posts

        Returns:
            dict: {lines_written, file, duration_seconds}
        """
        start = time.time()
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        lines_written = 0

        user = self._users.get_by_username(username)
        user_id = getattr(user, "pk", None) or (user.get("pk") if isinstance(user, dict) else None)

        with open(output_path, "w", encoding="utf-8") as f:
            # Profile
            profile = self._user_to_dict(user)
            profile["_type"] = "profile"
            profile["_scraped_at"] = datetime.now().isoformat()
            f.write(json.dumps(profile, ensure_ascii=False, default=str) + "\n")
            lines_written += 1
            if on_progress:
                on_progress("profile", 1)

            # Posts
            if include_posts and user_id:
                posts = self._fetch_posts(user_id, max_posts)
                for post in posts:
                    caption = post.get("caption", {})
                    caption_text = caption.get("text", "") if isinstance(caption, dict) else str(caption or "")
                    record = {
                        "_type": "post",
                        "media_id": post.get("pk"),
                        "shortcode": post.get("code", ""),
                        "media_type": post.get("media_type", 1),
                        "likes": post.get("like_count", 0),
                        "comments": post.get("comment_count", 0),
                        "caption": caption_text,
                        "taken_at": post.get("taken_at"),
                        "_scraped_at": datetime.now().isoformat(),
                    }
                    f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                    lines_written += 1

                if on_progress:
                    on_progress("posts", len(posts))

            # Followers
            if include_followers and user_id:
                followers = self._fetch_list(user_id, "followers", max_followers)
                for fol in followers:
                    record = {
                        "_type": "follower",
                        "user_id": fol.get("pk"),
                        "username": fol.get("username", ""),
                        "full_name": fol.get("full_name", ""),
                        "is_private": fol.get("is_private", False),
                        "is_verified": fol.get("is_verified", False),
                        "_scraped_at": datetime.now().isoformat(),
                    }
                    f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                    lines_written += 1

                if on_progress:
                    on_progress("followers", len(followers))

        duration = time.time() - start
        logger.info(f"📄 JSONL @{username}: {lines_written} lines → {output_path} ({duration:.1f}s)")
        return {
            "lines_written": lines_written,
            "file": os.path.abspath(output_path),
            "duration_seconds": round(duration, 1),
        }

    # ═══════════════════════════════════════════════════════════
    # INTERNAL
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _create_tables(cursor):
        """Create SQLite tables."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                followers INTEGER,
                following INTEGER,
                posts_count INTEGER,
                is_private BOOLEAN,
                is_verified BOOLEAN,
                biography TEXT,
                external_url TEXT,
                scraped_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                media_id TEXT PRIMARY KEY,
                shortcode TEXT,
                user_id TEXT,
                media_type INTEGER,
                likes INTEGER,
                comments INTEGER,
                caption TEXT,
                taken_at INTEGER,
                scraped_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS followers (
                user_id TEXT,
                follower_id TEXT,
                follower_username TEXT,
                follower_fullname TEXT,
                is_private BOOLEAN,
                is_verified BOOLEAN,
                scraped_at TEXT,
                PRIMARY KEY (user_id, follower_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS following (
                user_id TEXT,
                following_id TEXT,
                following_username TEXT,
                following_fullname TEXT,
                is_private BOOLEAN,
                is_verified BOOLEAN,
                scraped_at TEXT,
                PRIMARY KEY (user_id, following_id)
            )
        """)

    @staticmethod
    def _user_to_dict(user) -> Dict:
        """Convert user object to dict."""
        if hasattr(user, "__dict__"):
            return {
                "user_id": getattr(user, "pk", ""),
                "username": getattr(user, "username", ""),
                "full_name": getattr(user, "full_name", ""),
                "followers": getattr(user, "followers", 0) or getattr(user, "follower_count", 0),
                "following": getattr(user, "following", 0) or getattr(user, "following_count", 0),
                "posts_count": getattr(user, "media_count", 0),
                "is_private": getattr(user, "is_private", False),
                "is_verified": getattr(user, "is_verified", False),
                "biography": getattr(user, "biography", ""),
                "external_url": getattr(user, "external_url", ""),
            }
        elif isinstance(user, dict):
            return {
                "user_id": user.get("pk", ""),
                "username": user.get("username", ""),
                "full_name": user.get("full_name", ""),
                "followers": user.get("follower_count", 0) or user.get("followers", 0),
                "following": user.get("following_count", 0) or user.get("following", 0),
                "posts_count": user.get("media_count", 0),
                "is_private": user.get("is_private", False),
                "is_verified": user.get("is_verified", False),
                "biography": user.get("biography", ""),
                "external_url": user.get("external_url", ""),
            }
        return {}

    def _fetch_posts(self, user_id, count: int) -> List[Dict]:
        """Fetch user posts."""
        posts: list = []
        cursor = None
        while len(posts) < count:
            try:
                params = {"count": "33"}
                if cursor:
                    params["max_id"] = cursor
                result = self._client.request("GET", f"/api/v1/feed/user/{user_id}/", params=params)
            except Exception:
                break
            if not result or not isinstance(result, dict):
                break
            items = result.get("items", [])
            if not items:
                break
            posts.extend(items)
            if not result.get("more_available", False):
                break
            cursor = result.get("next_max_id")
            if not cursor:
                break
        return posts[:count]

    def _fetch_list(self, user_id, list_type: str, max_count: int) -> List[Dict]:
        """Fetch followers or following list."""
        all_users: list = []
        cursor = None
        while len(all_users) < max_count:
            try:
                if list_type == "followers":
                    result = self._friendships.get_followers(user_id, count=50, after=cursor)
                else:
                    result = self._friendships.get_following(user_id, count=50, after=cursor)
            except Exception:
                break
            users = result.get("users", [])
            if not users:
                break
            all_users.extend(users)
            cursor = result.get("next_max_id") or result.get("next_cursor")
            if not cursor:
                break
        return all_users[:max_count]
