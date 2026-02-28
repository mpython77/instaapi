"""
Async Public Data API
=====================
Async version of PublicDataAPI for non-blocking operations.

Usage:
    ig = AsyncInstagram.anonymous()

    profile = await ig.public_data.get_profile_info("cristiano")
    posts = await ig.public_data.get_profile_posts("cristiano", max_count=20)
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union

from ..models.public_data import (
    PublicProfile,
    PublicPost,
    HashtagPost,
    ProfileSnapshot,
    PublicDataReport,
)
from .public_data import PublicDataAPI, HashtagQuotaTracker

logger = logging.getLogger("instaharvest_v2.async_public_data")


class AsyncPublicDataAPI:
    """
    Async wrapper for PublicDataAPI.

    All methods are async versions of the sync PublicDataAPI.
    Uses asyncio.to_thread() to run blocking operations.
    """

    MAX_HASHTAG_PER_PROFILE = PublicDataAPI.MAX_HASHTAG_PER_PROFILE
    MAX_HASHTAG_PER_REQUEST = PublicDataAPI.MAX_HASHTAG_PER_REQUEST
    HASHTAG_WINDOW_DAYS = PublicDataAPI.HASHTAG_WINDOW_DAYS

    def __init__(self, public_api):
        self._sync = PublicDataAPI(public_api)

    async def get_profile_info(
        self,
        usernames: Union[str, List[str]],
    ) -> Union[PublicProfile, List[PublicProfile]]:
        """Async version of get_profile_info."""
        return await asyncio.to_thread(self._sync.get_profile_info, usernames)

    async def get_profile_posts(
        self,
        usernames: Union[str, List[str]],
        max_count: int = 12,
        **kwargs,
    ) -> List[PublicPost]:
        """Async version of get_profile_posts."""
        return await asyncio.to_thread(
            self._sync.get_profile_posts, usernames, max_count, **kwargs
        )

    async def search_hashtag_top(
        self,
        hashtags: Union[str, List[str]],
        profile_count: int = 1,
    ) -> List[HashtagPost]:
        """Async version of search_hashtag_top."""
        return await asyncio.to_thread(
            self._sync.search_hashtag_top, hashtags, profile_count
        )

    async def search_hashtag_recent(
        self,
        hashtags: Union[str, List[str]],
        profile_count: int = 1,
    ) -> List[HashtagPost]:
        """Async version of search_hashtag_recent."""
        return await asyncio.to_thread(
            self._sync.search_hashtag_recent, hashtags, profile_count
        )

    async def compare_profiles(
        self,
        usernames: List[str],
        post_count: int = 12,
    ) -> Dict[str, Any]:
        """Async version of compare_profiles."""
        return await asyncio.to_thread(
            self._sync.compare_profiles, usernames, post_count
        )

    async def track_profile(self, username: str) -> Dict[str, Any]:
        """Async version of track_profile."""
        return await asyncio.to_thread(self._sync.track_profile, username)

    async def get_tracking_history(self, username: str) -> List[Dict[str, Any]]:
        """Async version of get_tracking_history."""
        return self._sync.get_tracking_history(username)

    async def engagement_analysis(
        self,
        username: str,
        post_count: int = 12,
    ) -> Dict[str, Any]:
        """Async version of engagement_analysis."""
        return await asyncio.to_thread(
            self._sync.engagement_analysis, username, post_count
        )

    async def build_report(
        self,
        usernames: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
        max_posts: int = 12,
    ) -> PublicDataReport:
        """Async version of build_report."""
        return await asyncio.to_thread(
            self._sync.build_report, usernames, hashtags, max_posts
        )

    async def export_report(
        self,
        report: PublicDataReport,
        format: str = "json",
        filepath: Optional[str] = None,
    ) -> Union[str, Dict[str, Any]]:
        """Async version of export_report."""
        return await asyncio.to_thread(
            self._sync.export_report, report, format, filepath
        )

    def get_hashtag_quota(self, profile_count: int = 1) -> Dict[str, Any]:
        """Get current hashtag search quota status."""
        return self._sync.get_hashtag_quota(profile_count)

    def reset_quota(self) -> None:
        """Reset hashtag quota tracking."""
        self._sync.reset_quota()
