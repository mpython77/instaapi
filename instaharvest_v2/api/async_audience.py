"""
Async Lookalike Audience Finder
================================
Async version of AudienceAPI. Full feature parity.
"""

import logging
import random
import re
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("instaharvest_v2.audience")


class AsyncAudienceAPI:
    """
    Async Lookalike Audience Finder & Analyzer.

    Composes: AsyncUsersAPI, AsyncFriendshipsAPI.
    """

    def __init__(self, client, users_api, friendships_api):
        self._client = client
        self._users = users_api
        self._friendships = friendships_api

    async def find_lookalike(
        self,
        source_username: str,
        count: int = 50,
        min_followers: int = 100,
        max_followers: int = 50000,
        filter_private: bool = True,
        method: str = "mixed",
    ) -> Dict[str, Any]:
        """
        Find users similar to a source account's audience.

        Args:
            source_username: Source account
            count: Number of results
            min_followers: Min follower count
            max_followers: Max follower count
            filter_private: Skip private accounts
            method: 'followers', 'hashtag', 'mixed'

        Returns:
            dict: {users, method, source, duration_seconds}
        """
        start = time.time()
        user = await self._users.get_by_username(source_username)
        user_id = user.pk if hasattr(user, "pk") else user.get("pk", 0)
        if not user_id:
            return {"users": [], "error": f"User '{source_username}' not found"}

        candidates: Dict[str, Dict] = {}

        if method in ("followers", "mixed"):
            await self._discover_via_followers(user_id, candidates, count, min_followers, max_followers, filter_private)

        # Score and sort
        scored = self._score_candidates(candidates, source_username)
        return {
            "users": scored[:count],
            "method": method,
            "source": source_username,
            "total_found": len(scored),
            "duration_seconds": round(time.time() - start, 1),
        }

    async def overlap(
        self,
        username_a: str,
        username_b: str,
        max_followers: int = 2000,
    ) -> Dict[str, Any]:
        """
        Find follower overlap between two accounts.

        Args:
            username_a: First account
            username_b: Second account
            max_followers: Max followers to compare

        Returns:
            dict: {common_followers, overlap_rate, unique_to_a, unique_to_b}
        """
        user_a = await self._users.get_by_username(username_a)
        user_b = await self._users.get_by_username(username_b)
        id_a = user_a.pk if hasattr(user_a, "pk") else user_a.get("pk", 0)
        id_b = user_b.pk if hasattr(user_b, "pk") else user_b.get("pk", 0)

        set_a = await self._get_follower_set(id_a, max_followers)
        set_b = await self._get_follower_set(id_b, max_followers)

        common = set_a & set_b
        total = len(set_a | set_b)
        overlap_rate = len(common) / total * 100 if total > 0 else 0

        return {
            "common_followers": len(common),
            "overlap_rate": round(overlap_rate, 1),
            "unique_to_a": len(set_a - set_b),
            "unique_to_b": len(set_b - set_a),
            "total_a": len(set_a),
            "total_b": len(set_b),
        }

    async def insights(
        self,
        username: str,
        sample_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Audience insights — profile analysis of followers.

        Args:
            username: Target username
            sample_size: Number of followers to sample

        Returns:
            dict: {verified_rate, private_rate, avg_followers, avg_posts, quality}
        """
        user = await self._users.get_by_username(username)
        user_id = user.pk if hasattr(user, "pk") else user.get("pk", 0)

        followers = await self._get_followers_list(user_id, sample_size)
        if not followers:
            return {"error": "No followers data"}

        verified = sum(1 for f in followers if f.get("is_verified"))
        private = sum(1 for f in followers if f.get("is_private"))
        total_followers = sum(f.get("follower_count", 0) for f in followers)
        total_posts = sum(f.get("media_count", 0) for f in followers)
        count = len(followers)

        verified_rate = round(verified / count * 100, 1)
        private_rate = round(private / count * 100, 1)
        avg_followers = round(total_followers / count)
        avg_posts = round(total_posts / count)

        quality = self._audience_quality_score(verified_rate, private_rate, avg_followers, avg_posts)

        return {
            "sample_size": count,
            "verified_rate": verified_rate,
            "private_rate": private_rate,
            "avg_followers": avg_followers,
            "avg_posts": avg_posts,
            "quality": quality,
        }

    # ─── Internal ─────────────────────────────────────────────

    async def _discover_via_followers(self, user_id, candidates, target, min_f, max_f, skip_private):
        """Discover users by analyzing followers' other followings."""
        followers = await self._get_followers_list(user_id, min(target * 3, 200))
        sample = random.sample(followers, min(20, len(followers)))

        for follower in sample:
            fid = follower.get("pk") or follower.get("id")
            if not fid:
                continue
            try:
                result = await self._friendships.get_following(fid, count=30)
                for u in result.get("users", []):
                    uname = u.get("username", "")
                    if uname and uname not in candidates:
                        fc = u.get("follower_count", 0)
                        if min_f <= fc <= max_f:
                            if skip_private and u.get("is_private"):
                                continue
                            candidates[uname] = u
            except Exception:
                continue

    async def _get_followers_list(self, user_id, count: int) -> List[Dict]:
        """Fetch followers list."""
        try:
            result = await self._friendships.get_followers(user_id, count=count)
            return result.get("users", [])
        except Exception:
            return []

    async def _get_follower_set(self, user_id, count: int) -> Set[str]:
        """Get set of follower usernames."""
        followers = await self._get_followers_list(user_id, count)
        return {u.get("username", "") for u in followers if u.get("username")}

    @staticmethod
    def _score_candidates(candidates: Dict, source: str) -> List[Dict]:
        """Score candidates by relevance."""
        scored = []
        for uname, data in candidates.items():
            if uname == source:
                continue
            score = 0
            fc = data.get("follower_count", 0)
            if 1000 <= fc <= 100000:
                score += 50
            elif 100 <= fc <= 1000:
                score += 30
            if not data.get("is_private"):
                score += 20
            if data.get("is_verified"):
                score += 10
            scored.append({**data, "relevance_score": score})
        scored.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return scored

    @staticmethod
    def _audience_quality_score(verified_rate, private_rate, avg_followers, avg_posts) -> str:
        """Calculate audience quality."""
        score = 0
        if verified_rate > 2:
            score += 25
        if private_rate < 50:
            score += 25
        if avg_followers > 500:
            score += 25
        if avg_posts > 20:
            score += 25
        if score >= 75:
            return "excellent"
        elif score >= 50:
            return "good"
        elif score >= 25:
            return "average"
        return "low"
