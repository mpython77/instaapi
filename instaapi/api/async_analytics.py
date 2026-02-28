"""
Async Analytics API — Account Analytics & Engagement
=====================================================
Async version of AnalyticsAPI. Full feature parity.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("instaapi.analytics")


class AsyncAnalyticsAPI:
    """
    Async Instagram account analytics.

    Composes: AsyncUsersAPI, AsyncMediaAPI, AsyncFeedAPI.
    """

    def __init__(self, client, users_api, media_api, feed_api):
        self._client = client
        self._users = users_api
        self._media = media_api
        self._feed = feed_api

    async def engagement_rate(
        self,
        username: str,
        post_count: int = 12,
    ) -> Dict[str, Any]:
        """
        Calculate engagement rate from recent posts.

        Formula: (avg_likes + avg_comments) / followers * 100

        Args:
            username: Target username
            post_count: Number of recent posts to analyze (default 12)

        Returns:
            dict:
                - engagement_rate: float (percentage)
                - avg_likes: float
                - avg_comments: float
                - followers: int
                - posts_analyzed: int
                - rating: str (excellent/good/average/low)
        """
        user = await self._users.get_by_username(username)
        user_id = user.pk if hasattr(user, "pk") else user.get("pk", 0)
        followers = user.followers if hasattr(user, "followers") else user.get("follower_count", 0)

        if not followers:
            return {"engagement_rate": 0, "error": "No followers data"}

        posts = await self._fetch_posts(user_id, count=post_count)
        if not posts:
            return {"engagement_rate": 0, "error": "No posts found"}

        total_likes = sum(self._get_likes(p) for p in posts)
        total_comments = sum(self._get_comments(p) for p in posts)
        count = len(posts)

        avg_likes = total_likes / count
        avg_comments = total_comments / count
        rate = (avg_likes + avg_comments) / followers * 100

        if rate > 6:
            rating = "excellent"
        elif rate > 3:
            rating = "good"
        elif rate > 1:
            rating = "average"
        else:
            rating = "low"

        return {
            "engagement_rate": round(rate, 2),
            "avg_likes": round(avg_likes, 1),
            "avg_comments": round(avg_comments, 1),
            "followers": followers,
            "posts_analyzed": count,
            "rating": rating,
        }

    async def best_posting_times(
        self,
        username: str,
        post_count: int = 30,
    ) -> Dict[str, Any]:
        """
        Analyze post timestamps to find best posting times.

        Args:
            username: Target username
            post_count: Posts to analyze (more = better accuracy)

        Returns:
            dict:
                - best_hours: list of best hours (0-23)
                - best_days: list of best days
                - daily_breakdown: dict {day: {posts, avg_likes, avg_comments}}
        """
        user = await self._users.get_by_username(username)
        user_id = user.pk if hasattr(user, "pk") else user.get("pk", 0)
        posts = await self._fetch_posts(user_id, count=post_count)

        hour_stats: Dict[int, Dict] = defaultdict(lambda: {"likes": 0, "comments": 0, "count": 0})
        day_stats: Dict[str, Dict] = defaultdict(lambda: {"likes": 0, "comments": 0, "count": 0})

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for post in posts:
            ts = self._get_timestamp(post)
            if not ts:
                continue
            try:
                dt = datetime.fromtimestamp(ts)
                hour = dt.hour
                day = days[dt.weekday()]
                likes = self._get_likes(post)
                comments = self._get_comments(post)

                hour_stats[hour]["likes"] += likes
                hour_stats[hour]["comments"] += comments
                hour_stats[hour]["count"] += 1

                day_stats[day]["likes"] += likes
                day_stats[day]["comments"] += comments
                day_stats[day]["count"] += 1
            except (ValueError, OSError):
                continue

        # Find best hours by average engagement
        hour_engagement = {}
        for h, s in hour_stats.items():
            if s["count"]:
                hour_engagement[h] = (s["likes"] + s["comments"]) / s["count"]
        best_hours = sorted(hour_engagement, key=hour_engagement.get, reverse=True)[:5]

        # Find best days
        day_engagement = {}
        for d, s in day_stats.items():
            if s["count"]:
                day_engagement[d] = (s["likes"] + s["comments"]) / s["count"]
        best_days = sorted(day_engagement, key=day_engagement.get, reverse=True)[:3]

        daily_breakdown = {}
        for d, s in day_stats.items():
            c = max(s["count"], 1)
            daily_breakdown[d] = {
                "posts": s["count"],
                "avg_likes": round(s["likes"] / c, 1),
                "avg_comments": round(s["comments"] / c, 1),
            }

        return {
            "best_hours": best_hours,
            "best_days": best_days,
            "daily_breakdown": daily_breakdown,
            "posts_analyzed": len(posts),
        }

    async def content_analysis(
        self,
        username: str,
        post_count: int = 20,
    ) -> Dict[str, Any]:
        """
        Analyze content performance by type, hashtags, caption length.

        Args:
            username: Target username
            post_count: Posts to analyze

        Returns:
            dict:
                - by_type: {photo, video, carousel} engagement
                - caption_length_impact: correlation
                - top_hashtags: most used hashtags
                - posting_frequency: posts per week
        """
        user = await self._users.get_by_username(username)
        user_id = user.pk if hasattr(user, "pk") else user.get("pk", 0)
        posts = await self._fetch_posts(user_id, count=post_count)

        type_stats: Dict[str, Dict] = defaultdict(lambda: {"likes": 0, "comments": 0, "count": 0})
        all_hashtags: List[str] = []
        timestamps: List[float] = []

        for post in posts:
            media_type = self._get_media_type(post)
            likes = self._get_likes(post)
            comments = self._get_comments(post)

            type_stats[media_type]["likes"] += likes
            type_stats[media_type]["comments"] += comments
            type_stats[media_type]["count"] += 1

            caption = self._get_caption(post)
            import re
            tags = re.findall(r"#(\w+)", caption)
            all_hashtags.extend(tags)

            ts = self._get_timestamp(post)
            if ts:
                timestamps.append(ts)

        by_type = {}
        for t, s in type_stats.items():
            c = max(s["count"], 1)
            by_type[t] = {
                "count": s["count"],
                "avg_likes": round(s["likes"] / c, 1),
                "avg_comments": round(s["comments"] / c, 1),
            }

        top_hashtags = [{"tag": tag, "count": cnt} for tag, cnt in Counter(all_hashtags).most_common(20)]

        freq = 0.0
        if len(timestamps) >= 2:
            span_days = (max(timestamps) - min(timestamps)) / 86400
            if span_days > 0:
                freq = round(len(timestamps) / span_days * 7, 1)

        return {
            "by_type": by_type,
            "top_hashtags": top_hashtags,
            "posting_frequency_per_week": freq,
            "posts_analyzed": len(posts),
        }

    async def profile_summary(
        self,
        username: str,
        post_count: int = 12,
    ) -> Dict[str, Any]:
        """
        Complete profile analytics summary.

        Args:
            username: Target username
            post_count: Posts to analyze

        Returns:
            dict: Combined engagement, timing, content, and profile data
        """
        engagement = await self.engagement_rate(username, post_count)
        timing = await self.best_posting_times(username, post_count)
        content = await self.content_analysis(username, post_count)

        user = await self._users.get_by_username(username)

        return {
            "username": username,
            "profile": {
                "followers": getattr(user, "followers", 0),
                "following": getattr(user, "following", 0),
                "posts_count": getattr(user, "posts_count", 0),
                "is_verified": getattr(user, "is_verified", False),
                "is_business": getattr(user, "is_business", False),
            },
            "engagement": engagement,
            "best_times": timing,
            "content": content,
        }

    async def compare(
        self,
        usernames: List[str],
        post_count: int = 12,
    ) -> Dict[str, Any]:
        """
        Compare multiple accounts side by side.

        Args:
            usernames: List of usernames to compare
            post_count: Posts to analyze per account

        Returns:
            dict:
                - accounts: list of per-account analytics
                - rankings: who leads in each metric
                - winner: best overall account
        """
        accounts = []
        for u in usernames:
            try:
                summary = await self.profile_summary(u, post_count)
                accounts.append(summary)
            except Exception as e:
                accounts.append({"username": u, "error": str(e)})

        valid = [a for a in accounts if "error" not in a]
        rankings = {}
        if valid:
            rankings["engagement"] = max(valid, key=lambda a: a.get("engagement", {}).get("engagement_rate", 0)).get("username")
            rankings["followers"] = max(valid, key=lambda a: a.get("profile", {}).get("followers", 0)).get("username")

        return {
            "accounts": accounts,
            "rankings": rankings,
            "compared": len(accounts),
        }

    # ─── Helpers ─────────────────────────────────────────────────

    async def _fetch_posts(self, user_id, count: int = 12) -> List[Dict]:
        """Fetch user posts via feed API."""
        try:
            data = await self._client.get(
                f"/feed/user/{user_id}/",
                params={"count": str(count)},
                rate_category="get_feed",
            )
            return data.get("items", []) if data else []
        except Exception as e:
            logger.warning(f"Fetch posts error: {e}")
            return []

    @staticmethod
    def _get_likes(post: Dict) -> int:
        return post.get("like_count", 0) or post.get("likes", {}).get("count", 0) or 0

    @staticmethod
    def _get_comments(post: Dict) -> int:
        return post.get("comment_count", 0) or post.get("comments", {}).get("count", 0) or 0

    @staticmethod
    def _get_timestamp(post: Dict) -> int:
        return post.get("taken_at", 0) or post.get("taken_at_timestamp", 0) or 0

    @staticmethod
    def _get_caption(post: Dict) -> str:
        cap = post.get("caption")
        if isinstance(cap, dict):
            return cap.get("text", "")
        return cap or ""

    @staticmethod
    def _get_media_type(post: Dict) -> str:
        mt = post.get("media_type", 1)
        if mt == 8 or post.get("carousel_media"):
            return "carousel"
        elif mt == 2:
            return "video"
        return "photo"
