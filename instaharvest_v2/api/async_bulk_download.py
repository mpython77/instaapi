"""
Async Bulk Media Downloader
============================
Async version of BulkDownloadAPI. Full feature parity.
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger("instaharvest_v2.bulk_download")


class AsyncBulkDownloadAPI:
    """
    Async bulk media downloader with organized folders and resume.

    Composes: AsyncDownloadAPI, AsyncUsersAPI, AsyncFeedAPI, AsyncStoriesAPI.
    """

    def __init__(self, client, download_api, users_api, stories_api=None):
        self._client = client
        self._download = download_api
        self._users = users_api
        self._stories = stories_api

    async def all_posts(
        self,
        username: str,
        output_dir: str,
        max_count: int = 0,
        skip_existing: bool = True,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Download all posts (photos, videos, carousels).

        Args:
            username: Target username
            output_dir: Output directory
            max_count: Max posts (0 = all)
            skip_existing: Skip already downloaded files
            on_progress: Callback(downloaded, total, filename)

        Returns:
            dict: {downloaded, skipped, errors, total, duration_seconds}
        """
        start = time.time()
        user = await self._users.get_by_username(username)
        user_id = user.pk if hasattr(user, "pk") else user.get("pk", 0)
        if not user_id:
            return {"downloaded": 0, "error": f"User '{username}' not found"}

        posts = await self._fetch_all_posts(user_id, max_count)
        post_dir = os.path.join(output_dir, username, "posts")
        os.makedirs(post_dir, exist_ok=True)

        downloaded = 0
        skipped = 0
        errors = 0

        for i, post in enumerate(posts):
            urls = self._extract_media_urls(post)
            for url, ext in urls:
                ts = post.get("taken_at", int(time.time()))
                filename = f"post_{ts}_{i}.{ext}"
                filepath = os.path.join(post_dir, filename)

                if skip_existing and os.path.exists(filepath):
                    skipped += 1
                    continue

                try:
                    await self._download_file(url, filepath)
                    downloaded += 1
                    if on_progress:
                        on_progress(downloaded, len(posts), filename)
                except Exception as e:
                    errors += 1
                    logger.debug(f"Download error: {e}")

        duration = time.time() - start
        return {
            "downloaded": downloaded, "skipped": skipped, "errors": errors,
            "total": len(posts), "directory": post_dir,
            "duration_seconds": round(duration, 1),
        }

    async def all_stories(
        self,
        username: str,
        output_dir: str,
        skip_existing: bool = True,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Download current stories.

        Args:
            username: Target username
            output_dir: Output directory
            skip_existing: Skip existing files
            on_progress: Callback

        Returns:
            dict: {downloaded, total, duration_seconds}
        """
        start = time.time()
        if not self._stories:
            return {"downloaded": 0, "error": "StoriesAPI not available"}

        user = await self._users.get_by_username(username)
        user_id = user.pk if hasattr(user, "pk") else user.get("pk", 0)
        if not user_id:
            return {"downloaded": 0, "error": f"User '{username}' not found"}

        try:
            data = await self._stories.get_user_stories(user_id)
            items = data.get("items", []) if isinstance(data, dict) else []
        except Exception as e:
            return {"downloaded": 0, "error": str(e)}

        story_dir = os.path.join(output_dir, username, "stories")
        os.makedirs(story_dir, exist_ok=True)
        downloaded = 0

        for item in items:
            urls = self._extract_media_urls(item)
            for url, ext in urls:
                ts = item.get("taken_at", int(time.time()))
                filename = f"story_{ts}.{ext}"
                filepath = os.path.join(story_dir, filename)
                if skip_existing and os.path.exists(filepath):
                    continue
                try:
                    await self._download_file(url, filepath)
                    downloaded += 1
                    if on_progress:
                        on_progress(downloaded, len(items), filename)
                except Exception:
                    pass

        return {"downloaded": downloaded, "total": len(items), "duration_seconds": round(time.time() - start, 1)}

    async def everything(
        self,
        username: str,
        output_dir: str,
        max_posts: int = 0,
        on_progress: Optional[Callable[[str, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Download everything: posts, stories.

        Args:
            username: Target username
            output_dir: Root output directory
            max_posts: Max posts (0 = all)

        Returns:
            dict: Combined results
        """
        start = time.time()
        posts_result = await self.all_posts(username, output_dir, max_posts)
        stories_result = await self.all_stories(username, output_dir)
        return {
            "posts": posts_result,
            "stories": stories_result,
            "duration_seconds": round(time.time() - start, 1),
        }

    async def _fetch_all_posts(self, user_id, max_count: int = 0) -> List[Dict]:
        """Fetch all user posts with pagination."""
        all_posts = []
        max_id = None
        effective_max = max_count if max_count > 0 else 500

        while len(all_posts) < effective_max:
            try:
                params = {"count": "33"}
                if max_id:
                    params["max_id"] = max_id
                data = await self._client.get(
                    f"/feed/user/{user_id}/", params=params, rate_category="get_feed",
                )
                items = data.get("items", []) if data else []
                all_posts.extend(items)
                if not data.get("more_available"):
                    break
                max_id = data.get("next_max_id")
                if not max_id:
                    break
            except Exception as e:
                logger.warning(f"Fetch posts error: {e}")
                break

        return all_posts[:effective_max]

    @staticmethod
    def _extract_media_urls(item: Dict) -> List[tuple]:
        """Extract downloadable media URLs from a post/story item. Returns [(url, ext)]."""
        urls = []
        # Video
        video_versions = item.get("video_versions", [])
        if video_versions:
            urls.append((video_versions[0].get("url", ""), "mp4"))
            return urls
        # Carousel
        carousel = item.get("carousel_media", [])
        if carousel:
            for cm in carousel:
                vv = cm.get("video_versions", [])
                if vv:
                    urls.append((vv[0].get("url", ""), "mp4"))
                else:
                    candidates = cm.get("image_versions2", {}).get("candidates", [])
                    if candidates:
                        urls.append((candidates[0].get("url", ""), "jpg"))
            return urls
        # Photo
        candidates = item.get("image_versions2", {}).get("candidates", [])
        if candidates:
            urls.append((candidates[0].get("url", ""), "jpg"))
        return urls

    async def _download_file(self, url: str, filepath: str) -> None:
        """Download a single file."""
        import aiohttp
        try:
            # Use client session if available
            data = await self._client.get_raw(url)
            with open(filepath, "wb") as f:
                f.write(data)
        except Exception:
            # Fallback: direct download
            try:
                from curl_cffi.requests import AsyncSession
                async with AsyncSession() as s:
                    resp = await s.get(url)
                    with open(filepath, "wb") as f:
                        f.write(resp.content)
            except Exception as e:
                raise RuntimeError(f"Download failed: {e}")
