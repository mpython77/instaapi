"""
Bulk Media Downloader
=====================
Download all media from a user: posts, stories, highlights, reels.
Organized folder structure with resume support.

Usage:
    ig = Instagram.from_env(".env")

    # Download all posts
    ig.bulk_download.all_posts("cristiano", "downloads/cristiano/posts/")

    # Download stories
    ig.bulk_download.all_stories("cristiano", "downloads/cristiano/stories/")

    # Download highlights
    ig.bulk_download.all_highlights("cristiano", "downloads/cristiano/highlights/")

    # Download everything
    ig.bulk_download.everything("cristiano", "downloads/cristiano/")
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger("instaapi.bulk_download")


class BulkDownloadAPI:
    """
    Bulk media downloader with organized folders and resume.

    Composes: DownloadAPI, UsersAPI, FeedAPI, StoriesAPI.
    """

    def __init__(self, client, download_api, users_api, stories_api=None):
        self._client = client
        self._download = download_api
        self._users = users_api
        self._stories = stories_api

    # ═══════════════════════════════════════════════════════════
    # ALL POSTS
    # ═══════════════════════════════════════════════════════════

    def all_posts(
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
        user = self._users.get_by_username(username)
        user_id = getattr(user, "pk", None) or (user.get("pk") if isinstance(user, dict) else None)
        if not user_id:
            raise ValueError(f"Could not resolve user for '{username}'")

        os.makedirs(output_dir, exist_ok=True)

        # Fetch all post items
        posts = self._fetch_all_posts(user_id, max_count)
        total = len(posts)
        downloaded = 0
        skipped = 0
        errors = 0

        # Save metadata
        meta_path = os.path.join(output_dir, "_metadata.json")
        metadata = []

        for i, post in enumerate(posts):
            shortcode = post.get("code", "") or post.get("shortcode", "")
            media_type = post.get("media_type", 1)
            taken_at = post.get("taken_at", 0)

            try:
                date_str = datetime.fromtimestamp(taken_at).strftime("%Y%m%d") if taken_at else "unknown"
            except (ValueError, OSError):
                date_str = "unknown"

            # Determine files to download
            files_to_dl = self._extract_media_urls(post)

            for j, (url, ext) in enumerate(files_to_dl):
                suffix = f"_{j+1}" if len(files_to_dl) > 1 else ""
                filename = f"{date_str}_{shortcode}{suffix}{ext}"
                filepath = os.path.join(output_dir, filename)

                if skip_existing and os.path.exists(filepath):
                    skipped += 1
                    continue

                try:
                    self._download_file(url, filepath)
                    downloaded += 1
                    if on_progress:
                        on_progress(downloaded, total, filename)
                except Exception as e:
                    errors += 1
                    logger.debug(f"Download error {shortcode}: {e}")

            # Metadata
            caption = post.get("caption", {})
            if isinstance(caption, dict):
                caption_text = caption.get("text", "")
            else:
                caption_text = str(caption or "")

            metadata.append({
                "shortcode": shortcode,
                "media_type": {1: "photo", 2: "video", 8: "carousel"}.get(media_type, str(media_type)),
                "likes": post.get("like_count", 0),
                "comments": post.get("comment_count", 0),
                "caption": caption_text[:200],
                "posted_at": date_str,
            })

        # Save metadata
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)

        duration = time.time() - start
        summary = {
            "downloaded": downloaded,
            "skipped": skipped,
            "errors": errors,
            "total": total,
            "output_dir": os.path.abspath(output_dir),
            "duration_seconds": round(duration, 1),
        }
        logger.info(f"📦 Posts @{username}: {downloaded} files → {output_dir} ({duration:.1f}s)")
        return summary

    # ═══════════════════════════════════════════════════════════
    # ALL STORIES
    # ═══════════════════════════════════════════════════════════

    def all_stories(
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

        user = self._users.get_by_username(username)
        user_id = getattr(user, "pk", None) or (user.get("pk") if isinstance(user, dict) else None)

        os.makedirs(output_dir, exist_ok=True)

        try:
            stories = self._stories.get_user_stories(user_id)
            items = stories.get("items", []) if isinstance(stories, dict) else []
        except Exception as e:
            return {"downloaded": 0, "error": str(e)}

        downloaded = 0
        for item in items:
            taken_at = item.get("taken_at", 0)
            try:
                date_str = datetime.fromtimestamp(taken_at).strftime("%Y%m%d_%H%M%S") if taken_at else "story"
            except (ValueError, OSError):
                date_str = "story"

            urls = self._extract_media_urls(item)
            for url, ext in urls:
                filename = f"story_{date_str}{ext}"
                filepath = os.path.join(output_dir, filename)

                if skip_existing and os.path.exists(filepath):
                    continue

                try:
                    self._download_file(url, filepath)
                    downloaded += 1
                    if on_progress:
                        on_progress(downloaded, len(items), filename)
                except Exception:
                    pass

        duration = time.time() - start
        logger.info(f"📦 Stories @{username}: {downloaded} files ({duration:.1f}s)")
        return {"downloaded": downloaded, "total": len(items), "duration_seconds": round(duration, 1)}

    # ═══════════════════════════════════════════════════════════
    # ALL HIGHLIGHTS
    # ═══════════════════════════════════════════════════════════

    def all_highlights(
        self,
        username: str,
        output_dir: str,
        skip_existing: bool = True,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Download all highlight reels.

        Each highlight gets its own subfolder.
        """
        start = time.time()
        if not self._stories:
            return {"downloaded": 0, "error": "StoriesAPI not available"}

        user = self._users.get_by_username(username)
        user_id = getattr(user, "pk", None) or (user.get("pk") if isinstance(user, dict) else None)

        os.makedirs(output_dir, exist_ok=True)
        total_downloaded = 0

        try:
            highlights = self._stories.get_highlights(user_id)
            trays = highlights.get("tray", []) if isinstance(highlights, dict) else []
        except Exception as e:
            return {"downloaded": 0, "error": str(e)}

        for tray in trays:
            title = tray.get("title", "highlight")
            highlight_id = tray.get("id", "")
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]
            hl_dir = os.path.join(output_dir, safe_title)
            os.makedirs(hl_dir, exist_ok=True)

            # Fetch highlight items
            try:
                hl_data = self._stories.get_highlight_items(highlight_id)
                items = hl_data.get("items", []) if isinstance(hl_data, dict) else []
            except Exception:
                items = tray.get("items", [])

            for idx, item in enumerate(items):
                urls = self._extract_media_urls(item)
                for url, ext in urls:
                    filename = f"{safe_title}_{idx+1:03d}{ext}"
                    filepath = os.path.join(hl_dir, filename)

                    if skip_existing and os.path.exists(filepath):
                        continue

                    try:
                        self._download_file(url, filepath)
                        total_downloaded += 1
                        if on_progress:
                            on_progress(total_downloaded, 0, filename)
                    except Exception:
                        pass

        duration = time.time() - start
        logger.info(f"📦 Highlights @{username}: {total_downloaded} files ({duration:.1f}s)")
        return {
            "downloaded": total_downloaded,
            "highlights": len(trays),
            "duration_seconds": round(duration, 1),
        }

    # ═══════════════════════════════════════════════════════════
    # EVERYTHING
    # ═══════════════════════════════════════════════════════════

    def everything(
        self,
        username: str,
        output_dir: str,
        max_posts: int = 0,
        on_progress: Optional[Callable[[str, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Download everything: posts, stories, highlights.

        Args:
            username: Target username
            output_dir: Root output directory
            max_posts: Max posts (0 = all)

        Returns:
            dict: Combined results
        """
        start = time.time()
        results = {}

        # Posts
        posts_dir = os.path.join(output_dir, "posts")
        results["posts"] = self.all_posts(
            username, posts_dir, max_count=max_posts,
            on_progress=lambda d, t, f: on_progress("posts", d, f) if on_progress else None,
        )

        # Stories
        stories_dir = os.path.join(output_dir, "stories")
        results["stories"] = self.all_stories(
            username, stories_dir,
            on_progress=lambda d, t, f: on_progress("stories", d, f) if on_progress else None,
        )

        # Highlights
        hl_dir = os.path.join(output_dir, "highlights")
        results["highlights"] = self.all_highlights(
            username, hl_dir,
            on_progress=lambda d, t, f: on_progress("highlights", d, f) if on_progress else None,
        )

        total_files = sum(r.get("downloaded", 0) for r in results.values())
        duration = time.time() - start

        logger.info(f"📦 Everything @{username}: {total_files} total files ({duration:.1f}s)")
        return {
            "username": username,
            "total_files": total_files,
            "duration_seconds": round(duration, 1),
            "details": results,
        }

    # ═══════════════════════════════════════════════════════════
    # INTERNAL
    # ═══════════════════════════════════════════════════════════

    def _fetch_all_posts(self, user_id, max_count: int = 0) -> List[Dict]:
        """Fetch all user posts with pagination."""
        all_posts: list = []
        cursor = None
        limit = max_count if max_count > 0 else 10000

        while len(all_posts) < limit:
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
            all_posts.extend(items)

            if not result.get("more_available", False):
                break
            cursor = result.get("next_max_id")
            if not cursor:
                break

        return all_posts[:limit] if max_count > 0 else all_posts

    @staticmethod
    def _extract_media_urls(item: Dict) -> List[tuple]:
        """Extract downloadable media URLs from a post/story item. Returns [(url, ext)]."""
        urls = []
        media_type = item.get("media_type", 1)

        # Video
        if media_type == 2:
            video_versions = item.get("video_versions", [])
            if video_versions:
                best = max(video_versions, key=lambda v: v.get("width", 0) * v.get("height", 0))
                urls.append((best.get("url", ""), ".mp4"))
                return urls

        # Carousel
        if media_type == 8:
            carousel = item.get("carousel_media", [])
            for child in carousel:
                child_type = child.get("media_type", 1)
                if child_type == 2:
                    vv = child.get("video_versions", [])
                    if vv:
                        urls.append((vv[0].get("url", ""), ".mp4"))
                else:
                    candidates = child.get("image_versions2", {}).get("candidates", [])
                    if candidates:
                        best = max(candidates, key=lambda c: c.get("width", 0) * c.get("height", 0))
                        urls.append((best.get("url", ""), ".jpg"))
            return urls

        # Photo (default)
        candidates = item.get("image_versions2", {}).get("candidates", [])
        if candidates:
            best = max(candidates, key=lambda c: c.get("width", 0) * c.get("height", 0))
            urls.append((best.get("url", ""), ".jpg"))

        return urls

    def _download_file(self, url: str, filepath: str) -> None:
        """Download a single file."""
        if not url:
            return
        try:
            self._download.url_to_file(url, filepath)
        except AttributeError:
            # Fallback: direct HTTP download
            import urllib.request
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            urllib.request.urlretrieve(url, filepath)
