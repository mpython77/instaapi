"""
Download API
=============
Download media content — photos, videos, stories, highlights, profile pictures.
Full download support similar to instaloader and instagrapi.
"""

import os
import time
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from ..client import HttpClient

logger = logging.getLogger("instaapi")


class DownloadAPI:
    """Instagram media download API"""

    def __init__(self, client: HttpClient):
        self._client = client

    def _ensure_dir(self, path: str) -> str:
        """Ensure directory exists, create if not."""
        dir_path = os.path.dirname(path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        return path

    def _download_url(self, url: str, save_path: str) -> str:
        """
        Download a file from URL.

        Args:
            url: Media URL
            save_path: Local file path to save to

        Returns:
            str: Saved file path
        """
        self._ensure_dir(save_path)
        session = self._client._get_curl_session()
        sess_info = self._client._session_mgr.get_session()

        headers = {
            "user-agent": sess_info.user_agent if sess_info else "Mozilla/5.0",
            "referer": "https://www.instagram.com/",
        }

        response = session.get(url, headers=headers, timeout=60)
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(response.content)
            return save_path
        else:
            raise Exception(f"Download failed: HTTP {response.status_code}")

    def _get_extension(self, url: str, default: str = ".jpg") -> str:
        """Determine file extension from URL."""
        path = url.split("?")[0]
        if path.endswith(".mp4"):
            return ".mp4"
        elif path.endswith(".jpg") or path.endswith(".jpeg"):
            return ".jpg"
        elif path.endswith(".png"):
            return ".png"
        elif path.endswith(".webp"):
            return ".webp"
        return default

    # ─── PHOTO / VIDEO DOWNLOAD ─────────────────────────────

    def download_media(
        self,
        media_pk: int | str,
        folder: str = "downloads",
        filename: str = None,
    ) -> List[str]:
        """
        Download all media (photos/videos) from a post.
        For carousel posts, downloads all items.

        Args:
            media_pk: Media PK
            folder: Destination folder
            filename: Custom filename (optional, default: {shortcode}_{index})

        Returns:
            list: Saved file paths
        """
        from .media import MediaAPI
        media_api = MediaAPI(self._client)
        info = media_api.get_info(media_pk)

        saved_files = []
        items = info.get("items", [info])
        if isinstance(items, list) and len(items) > 0:
            media = items[0] if isinstance(items[0], dict) else info
        else:
            media = info

        shortcode = media.get("code", str(media_pk))

        # Carousel (album)
        carousel = media.get("carousel_media", [])
        if carousel:
            for i, item in enumerate(carousel):
                url = self._get_best_url(item)
                if url:
                    ext = self._get_extension(url)
                    fname = filename or shortcode
                    path = os.path.join(folder, f"{fname}_{i+1}{ext}")
                    self._download_url(url, path)
                    saved_files.append(path)
        else:
            # Single post (one photo/video)
            url = self._get_best_url(media)
            if url:
                ext = self._get_extension(url)
                fname = filename or shortcode
                path = os.path.join(folder, f"{fname}{ext}")
                self._download_url(url, path)
                saved_files.append(path)

        return saved_files

    def _get_best_url(self, media: dict) -> Optional[str]:
        """Get the highest quality URL from media item."""
        # Video
        video_versions = media.get("video_versions", [])
        if video_versions:
            return video_versions[0].get("url")

        # Photo
        img_versions = media.get("image_versions2", {})
        candidates = img_versions.get("candidates", [])
        if candidates:
            best = max(candidates, key=lambda c: c.get("width", 0) * c.get("height", 0))
            return best.get("url")

        return None

    def download_photo(
        self,
        media_pk: int | str,
        folder: str = "downloads",
        filename: str = None,
    ) -> str:
        """
        Download a single photo.

        Args:
            media_pk: Media PK
            folder: Destination folder
            filename: Custom filename

        Returns:
            str: Saved file path
        """
        files = self.download_media(media_pk, folder, filename)
        return files[0] if files else ""

    def download_video(
        self,
        media_pk: int | str,
        folder: str = "downloads",
        filename: str = None,
    ) -> str:
        """
        Download a video.

        Args:
            media_pk: Media PK
            folder: Destination folder
            filename: Custom filename

        Returns:
            str: Saved file path
        """
        files = self.download_media(media_pk, folder, filename)
        return files[0] if files else ""

    # ─── STORY / HIGHLIGHT DOWNLOAD ──────────────────────────

    def download_stories(
        self,
        user_pk: int | str,
        folder: str = "downloads/stories",
    ) -> List[str]:
        """
        Download all stories of a user.

        Args:
            user_pk: User PK
            folder: Destination folder

        Returns:
            list: Saved file paths
        """
        from .stories import StoriesAPI
        stories_api = StoriesAPI(self._client)
        data = stories_api.get_user_stories(user_pk)

        reel = data.get("reel") or data.get("reels", {}).get(str(user_pk), {})
        items = reel.get("items", [])
        user = reel.get("user", {})
        username = user.get("username", str(user_pk))

        saved = []
        for item in items:
            url = self._get_best_url(item)
            if url:
                ts = item.get("taken_at", int(time.time()))
                ext = self._get_extension(url, ".mp4" if item.get("video_versions") else ".jpg")
                path = os.path.join(folder, username, f"story_{ts}{ext}")
                self._download_url(url, path)
                saved.append(path)

        return saved

    def download_highlights(
        self,
        user_pk: int | str,
        folder: str = "downloads/highlights",
    ) -> Dict[str, List[str]]:
        """
        Download all highlights of a user.

        Args:
            user_pk: User PK
            folder: Destination folder

        Returns:
            dict: {highlight_title: [file_paths]}
        """
        from .stories import StoriesAPI
        stories_api = StoriesAPI(self._client)

        highlights = stories_api.get_highlights_tray(user_pk)
        tray = highlights.get("tray", [])

        result = {}
        for hl in tray:
            hl_id = hl.get("id", "")
            title = hl.get("title", hl_id)
            safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)

            items_data = stories_api.get_highlight_items(hl_id)
            reel = items_data.get("reels", {}).get(hl_id, {})
            items = reel.get("items", [])

            saved = []
            for i, item in enumerate(items):
                url = self._get_best_url(item)
                if url:
                    ext = self._get_extension(url, ".mp4" if item.get("video_versions") else ".jpg")
                    path = os.path.join(folder, safe_title, f"{i+1:03d}{ext}")
                    self._download_url(url, path)
                    saved.append(path)

            result[title] = saved
            time.sleep(1)  # Rate limiting

        return result

    # ─── PROFILE PICTURE ─────────────────────────────────────

    def download_profile_pic(
        self,
        username: str = None,
        user_pk: int | str = None,
        folder: str = "downloads",
        hd: bool = True,
    ) -> str:
        """
        Download profile picture (HD).

        Args:
            username: Instagram username
            user_pk: User PK (alternative to username)
            folder: Destination folder
            hd: Download HD version

        Returns:
            str: Saved file path
        """
        from .users import UsersAPI
        users_api = UsersAPI(self._client)

        if username:
            user_data = users_api.get_by_username(username)
        elif user_pk:
            user_data = users_api.get_by_id(user_pk)
        else:
            raise ValueError("Either username or user_pk is required!")

        user = user_data.get("user", user_data)
        uname = user.get("username", str(user_pk or username))

        pic_url = None
        if hd:
            pic_url = user.get("hd_profile_pic_url_info", {}).get("url")
            if not pic_url:
                pic_url = user.get("hd_profile_pic_versions", [{}])[0].get("url") if user.get("hd_profile_pic_versions") else None

        if not pic_url or not hd:
            pic_url = user.get("profile_pic_url_hd", user.get("profile_pic_url", ""))

        if not pic_url:
            raise Exception(f"Profile picture not found: {uname}")

        ext = self._get_extension(pic_url)
        path = os.path.join(folder, f"{uname}_profile{ext}")
        return self._download_url(pic_url, path)

    # ─── BATCH DOWNLOAD ──────────────────────────────────────

    def download_user_posts(
        self,
        user_pk: int | str,
        folder: str = "downloads/posts",
        max_posts: int = 50,
        only_photos: bool = False,
        only_videos: bool = False,
    ) -> List[str]:
        """
        Download all posts of a user.

        Args:
            user_pk: User PK
            folder: Destination folder
            max_posts: Maximum number of posts
            only_photos: Download photos only
            only_videos: Download videos only

        Returns:
            list: Saved file paths
        """
        from .feed import FeedAPI
        feed_api = FeedAPI(self._client)

        all_posts = feed_api.get_all_posts(user_pk, max_posts=max_posts)
        saved = []

        for post in all_posts:
            media_type = post.get("media_type", 1)
            if only_photos and media_type != 1:
                continue
            if only_videos and media_type != 2:
                continue

            pk = post.get("pk")
            code = post.get("code", str(pk))

            carousel = post.get("carousel_media", [])
            if carousel:
                for i, item in enumerate(carousel):
                    url = self._get_best_url(item)
                    if url:
                        ext = self._get_extension(url)
                        path = os.path.join(folder, f"{code}_{i+1}{ext}")
                        try:
                            self._download_url(url, path)
                            saved.append(path)
                        except Exception as e:
                            logger.warning(f"Download error {code}_{i+1}: {e}")
            else:
                url = self._get_best_url(post)
                if url:
                    ext = self._get_extension(url)
                    path = os.path.join(folder, f"{code}{ext}")
                    try:
                        self._download_url(url, path)
                        saved.append(path)
                    except Exception as e:
                        logger.warning(f"Download error {code}: {e}")

            time.sleep(0.5)  # Rate limiting

        return saved

    def download_by_url(
        self,
        url: str,
        folder: str = "downloads",
    ) -> List[str]:
        """
        Download media from an Instagram URL.
        Supports: instagram.com/p/ABC123/ or instagram.com/reel/ABC123/

        Args:
            url: Instagram post URL
            folder: Destination folder

        Returns:
            list: Saved file paths
        """
        shortcode = self._extract_shortcode(url)
        if not shortcode:
            raise ValueError(f"Could not extract shortcode from URL: {url}")

        pk = self._shortcode_to_pk(shortcode)
        return self.download_media(pk, folder, shortcode)

    # ─── URL/SHORTCODE UTILITIES ─────────────────────────────

    @staticmethod
    def _shortcode_to_pk(shortcode: str) -> int:
        """Convert shortcode to media PK."""
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        pk = 0
        for char in shortcode:
            pk = pk * 64 + alphabet.index(char)
        return pk

    @staticmethod
    def _pk_to_shortcode(pk: int) -> str:
        """Convert media PK to shortcode."""
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        shortcode = ""
        while pk > 0:
            shortcode = alphabet[pk % 64] + shortcode
            pk //= 64
        return shortcode

    @staticmethod
    def _extract_shortcode(url: str) -> Optional[str]:
        """
        Extract shortcode from Instagram URL.
        Supports:
            instagram.com/p/ABC123/
            instagram.com/reel/ABC123/
            instagram.com/tv/ABC123/
        """
        import re
        patterns = [
            r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)",
            r"instagr\.am/p/([A-Za-z0-9_-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
