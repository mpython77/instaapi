"""
Batch Operations
================
High-level utilities for parallel Instagram operations.
Uses asyncio.Semaphore for concurrency control.

Usage:
    async with AsyncInstagram.from_env() as ig:
        profiles = await ig.batch.check_profiles(
            ["user1", "user2", "user3"],
            concurrency=20,
        )
"""

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .async_instagram import AsyncInstagram

logger = logging.getLogger("instaharvest_v2.batch")


class BatchAPI:
    """
    Batch operations for parallel processing.

    All methods use asyncio.Semaphore for concurrency control
    and respect Instagram's rate limits.
    """

    def __init__(self, ig: "AsyncInstagram"):
        """
        Args:
            ig: AsyncInstagram instance
        """
        self._ig = ig

    async def _run_batch(
        self,
        items: List[Any],
        fn: Callable,
        concurrency: int = 10,
        fail_silently: bool = True,
        on_progress: Optional[Callable[[int, int, Any, Any], None]] = None,
    ) -> List[Tuple[Any, Any]]:
        """
        Run a batch of async tasks with concurrency control.

        Args:
            items: List of items to process
            fn: Async function taking one item, returns result
            concurrency: Max parallel tasks
            fail_silently: Skip errors instead of raising
            on_progress: Optional callback(completed, total, item, result)
                         Called after each item completes.

        Returns:
            List of (item, result) tuples. Result is None on error.
        """
        sem = asyncio.Semaphore(concurrency)
        completed = 0
        total = len(items)
        results: List[Tuple[Any, Any]] = []

        async def task(item):
            nonlocal completed
            async with sem:
                try:
                    result = await fn(item)
                    completed += 1
                    if on_progress:
                        try:
                            on_progress(completed, total, item, result)
                        except Exception:
                            pass
                    return (item, result)
                except Exception as e:
                    completed += 1
                    if on_progress:
                        try:
                            on_progress(completed, total, item, None)
                        except Exception:
                            pass
                    if fail_silently:
                        logger.warning(f"[Batch] Error for {item}: {e}")
                        return (item, None)
                    raise

        tasks = [task(item) for item in items]
        results = await asyncio.gather(*tasks)
        return list(results)

    # ─── PROFILES ────────────────────────────────────────────

    async def check_profiles(
        self,
        usernames: List[str],
        concurrency: int = 10,
    ) -> Dict[str, Optional[Dict]]:
        """
        Fetch multiple profiles in parallel.

        Args:
            usernames: List of usernames
            concurrency: Max parallel requests (default 10)

        Returns:
            Dict of {username: profile_data or None}
        """
        results = await self._run_batch(
            usernames,
            self._ig.users.get_by_username,
            concurrency=concurrency,
        )
        return {username: data for username, data in results}

    # ─── FOLLOW-BACK CHECK ───────────────────────────────────

    async def check_follow_backs(
        self,
        user_ids: List[int | str],
        concurrency: int = 10,
    ) -> Dict[str, Dict]:
        """
        Check follow-back status for multiple users in parallel.

        Args:
            user_ids: List of user IDs
            concurrency: Max parallel requests

        Returns:
            Dict of {user_id: {following, followed_by, is_bestie, ...}}
        """
        results = await self._run_batch(
            user_ids,
            self._ig.friendships.show,
            concurrency=concurrency,
        )
        return {str(uid): data for uid, data in results}

    # ─── MEDIA INFO ──────────────────────────────────────────

    async def get_media_infos(
        self,
        media_ids: List[str],
        concurrency: int = 10,
    ) -> Dict[str, Optional[Dict]]:
        """
        Fetch multiple media items in parallel.

        Args:
            media_ids: List of media IDs or shortcodes
            concurrency: Max parallel requests

        Returns:
            Dict of {media_id: media_data or None}
        """
        results = await self._run_batch(
            media_ids,
            self._ig.media.get_info,
            concurrency=concurrency,
        )
        return {mid: data for mid, data in results}

    # ─── BULK OPERATIONS ──────────────────────────────────────

    async def bulk_follow(
        self,
        user_ids: List[int | str],
        concurrency: int = 3,
        delay: float = 2.0,
    ) -> Dict[str, bool]:
        """
        Follow multiple users with safe delays.

        Args:
            user_ids: User IDs to follow
            concurrency: Max parallel follows (keep low!)
            delay: Delay between follows in seconds

        Returns:
            Dict of {user_id: success}
        """
        async def follow_with_delay(uid):
            result = await self._ig.friendships.follow(uid)
            await asyncio.sleep(delay)
            return result

        results = await self._run_batch(
            user_ids,
            follow_with_delay,
            concurrency=concurrency,
        )
        return {str(uid): data is not None for uid, data in results}

    async def bulk_like(
        self,
        media_ids: List[str],
        concurrency: int = 3,
        delay: float = 1.5,
    ) -> Dict[str, bool]:
        """
        Like multiple posts with safe delays.

        Args:
            media_ids: Media IDs to like
            concurrency: Max parallel likes
            delay: Delay between likes

        Returns:
            Dict of {media_id: success}
        """
        async def like_with_delay(mid):
            result = await self._ig.media.like(mid)
            await asyncio.sleep(delay)
            return result

        results = await self._run_batch(
            media_ids,
            like_with_delay,
            concurrency=concurrency,
        )
        return {mid: data is not None for mid, data in results}

    # ─── CUSTOM BATCH ────────────────────────────────────────

    async def run(
        self,
        items: List[Any],
        fn: Callable,
        concurrency: int = 10,
        fail_silently: bool = True,
    ) -> List[Tuple[Any, Any]]:
        """
        Run any async function in batch mode.

        Args:
            items: Items to process
            fn: Async function(item) -> result
            concurrency: Max parallel tasks
            fail_silently: True to skip errors

        Returns:
            List of (item, result) tuples

        Example:
            results = await ig.batch.run(
                usernames,
                ig.users.get_by_username,
                concurrency=20,
            )
        """
        return await self._run_batch(items, fn, concurrency, fail_silently)
