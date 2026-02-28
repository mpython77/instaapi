"""
Analytics API — Account Analytics & Engagement
===============================================
Calculate engagement rates, find best posting times,
analyze content performance, generate profile summaries.

Usage:
    ig = Instagram.from_env(".env")

    # Engagement rate
    rate = ig.analytics.engagement_rate("cristiano")
    print(f"Engagement: {rate['engagement_rate']}%")

    # Best posting times
    times = ig.analytics.best_posting_times("cristiano")
    print(f"Best hour: {times['best_hours'][0]}")

    # Full profile summary
    summary = ig.analytics.profile_summary("cristiano")
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("instaapi.analytics")


class AnalyticsAPI:
    """
    Instagram account analytics.

    Composes: UsersAPI, MediaAPI, FeedAPI.
    """

    def __init__(self, client, users_api, media_api, feed_api):
        self._client = client
        self._users = users_api
        self._media = media_api
        self._feed = feed_api

    # ═══════════════════════════════════════════════════════════
    # ENGAGEMENT RATE
    # ═══════════════════════════════════════════════════════════

    def engagement_rate(
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
        user = self._users.get_by_username(username)
        followers = getattr(user, "followers", 0) or getattr(user, "follower_count", 0)
        if not followers:
            followers = (user.get("followers", 0) if isinstance(user, dict) else 0) or 1
        user_id = getattr(user, "pk", None) or (user.get("pk") if isinstance(user, dict) else None)

        posts = self._fetch_posts(user_id, post_count)
        if not posts:
            return {
                "engagement_rate": 0.0,
                "avg_likes": 0,
                "avg_comments": 0,
                "followers": followers,
                "posts_analyzed": 0,
                "rating": "no_data",
            }

        total_likes = sum(self._get_likes(p) for p in posts)
        total_comments = sum(self._get_comments(p) for p in posts)
        n = len(posts)

        avg_likes = total_likes / n
        avg_comments = total_comments / n
        rate = (avg_likes + avg_comments) / max(followers, 1) * 100

        # Rating scale
        if rate >= 6:
            rating = "excellent"
        elif rate >= 3:
            rating = "very_good"
        elif rate >= 1:
            rating = "good"
        elif rate >= 0.5:
            rating = "average"
        else:
            rating = "low"

        result = {
            "engagement_rate": round(rate, 2),
            "avg_likes": round(avg_likes, 1),
            "avg_comments": round(avg_comments, 1),
            "total_likes": total_likes,
            "total_comments": total_comments,
            "followers": followers,
            "posts_analyzed": n,
            "rating": rating,
            "likes_per_post": [self._get_likes(p) for p in posts],
            "comments_per_post": [self._get_comments(p) for p in posts],
        }

        logger.info(
            f"📊 Engagement @{username}: {rate:.2f}% ({rating}) | "
            f"avg_likes={avg_likes:.0f} avg_comments={avg_comments:.0f} | "
            f"followers={followers:,}"
        )
        return result

    # ═══════════════════════════════════════════════════════════
    # BEST POSTING TIMES
    # ═══════════════════════════════════════════════════════════

    def best_posting_times(
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
                - best_hours: list of (hour, avg_engagement) sorted by engagement
                - best_days: list of (day_name, avg_engagement)
                - hourly_breakdown: dict {hour: {posts, avg_likes, avg_comments}}
                - daily_breakdown: dict {day: {posts, avg_likes, avg_comments}}
        """
        user = self._users.get_by_username(username)
        user_id = getattr(user, "pk", None) or (user.get("pk") if isinstance(user, dict) else None)
        followers = getattr(user, "followers", 0) or getattr(user, "follower_count", 0) or 1

        posts = self._fetch_posts(user_id, post_count)
        if not posts:
            return {"best_hours": [], "best_days": [], "hourly_breakdown": {}, "daily_breakdown": {}}

        hourly = defaultdict(lambda: {"posts": 0, "likes": 0, "comments": 0})
        daily = defaultdict(lambda: {"posts": 0, "likes": 0, "comments": 0})
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for post in posts:
            ts = self._get_timestamp(post)
            if not ts:
                continue
            try:
                dt = datetime.fromtimestamp(ts)
            except (ValueError, OSError):
                continue

            hour = dt.hour
            day = day_names[dt.weekday()]
            likes = self._get_likes(post)
            comments = self._get_comments(post)

            hourly[hour]["posts"] += 1
            hourly[hour]["likes"] += likes
            hourly[hour]["comments"] += comments

            daily[day]["posts"] += 1
            daily[day]["likes"] += likes
            daily[day]["comments"] += comments

        # Calculate averages and engagement
        hourly_breakdown = {}
        for h in range(24):
            if h in hourly and hourly[h]["posts"] > 0:
                n = hourly[h]["posts"]
                avg_l = hourly[h]["likes"] / n
                avg_c = hourly[h]["comments"] / n
                eng = (avg_l + avg_c) / max(followers, 1) * 100
                hourly_breakdown[h] = {
                    "posts": n,
                    "avg_likes": round(avg_l, 1),
                    "avg_comments": round(avg_c, 1),
                    "engagement": round(eng, 3),
                }

        daily_breakdown = {}
        for d in day_names:
            if d in daily and daily[d]["posts"] > 0:
                n = daily[d]["posts"]
                avg_l = daily[d]["likes"] / n
                avg_c = daily[d]["comments"] / n
                eng = (avg_l + avg_c) / max(followers, 1) * 100
                daily_breakdown[d] = {
                    "posts": n,
                    "avg_likes": round(avg_l, 1),
                    "avg_comments": round(avg_c, 1),
                    "engagement": round(eng, 3),
                }

        best_hours = sorted(
            hourly_breakdown.items(),
            key=lambda x: x[1]["engagement"],
            reverse=True,
        )
        best_days = sorted(
            daily_breakdown.items(),
            key=lambda x: x[1]["engagement"],
            reverse=True,
        )

        result = {
            "best_hours": [(h, data) for h, data in best_hours[:5]],
            "best_days": [(d, data) for d, data in best_days],
            "hourly_breakdown": hourly_breakdown,
            "daily_breakdown": daily_breakdown,
            "posts_analyzed": len(posts),
        }

        if best_hours:
            logger.info(f"📊 Best time @{username}: {best_hours[0][0]}:00 (eng={best_hours[0][1]['engagement']:.3f}%)")
        return result

    # ═══════════════════════════════════════════════════════════
    # CONTENT ANALYSIS
    # ═══════════════════════════════════════════════════════════

    def content_analysis(
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
                - media_type_breakdown: performance by photo/video/carousel
                - top_posts: top 5 posts by engagement
                - worst_posts: bottom 5 posts
                - avg_caption_length: int
                - top_hashtags: most used hashtags
                - posting_frequency: posts per week
        """
        user = self._users.get_by_username(username)
        user_id = getattr(user, "pk", None) or (user.get("pk") if isinstance(user, dict) else None)
        followers = getattr(user, "followers", 0) or getattr(user, "follower_count", 0) or 1

        posts = self._fetch_posts(user_id, post_count)
        if not posts:
            return {"media_type_breakdown": {}, "top_posts": [], "posting_frequency": 0}

        # Analyze media types
        type_stats = defaultdict(lambda: {"count": 0, "likes": 0, "comments": 0})
        all_hashtags = Counter()
        caption_lengths = []
        timestamps = []
        scored_posts = []

        for post in posts:
            media_type = self._get_media_type(post)
            likes = self._get_likes(post)
            comments = self._get_comments(post)
            caption = self._get_caption(post)
            ts = self._get_timestamp(post)

            type_stats[media_type]["count"] += 1
            type_stats[media_type]["likes"] += likes
            type_stats[media_type]["comments"] += comments

            if caption:
                caption_lengths.append(len(caption))
                # Extract hashtags
                import re
                tags = re.findall(r"#(\w+)", caption)
                all_hashtags.update(tags)

            if ts:
                timestamps.append(ts)

            engagement = (likes + comments) / max(followers, 1) * 100
            scored_posts.append({
                "shortcode": post.get("code") or post.get("shortcode", ""),
                "media_type": media_type,
                "likes": likes,
                "comments": comments,
                "engagement": round(engagement, 3),
                "caption_preview": (caption or "")[:80],
                "posted_at": datetime.fromtimestamp(ts).isoformat() if ts else None,
            })

        # Type breakdown
        media_type_breakdown = {}
        for mtype, stats in type_stats.items():
            n = stats["count"]
            media_type_breakdown[mtype] = {
                "count": n,
                "avg_likes": round(stats["likes"] / n, 1),
                "avg_comments": round(stats["comments"] / n, 1),
                "engagement": round((stats["likes"] / n + stats["comments"] / n) / max(followers, 1) * 100, 3),
            }

        # Top/worst posts
        scored_posts.sort(key=lambda p: p["engagement"], reverse=True)

        # Posting frequency
        posting_frequency = 0.0
        if len(timestamps) >= 2:
            time_span_days = (max(timestamps) - min(timestamps)) / 86400
            if time_span_days > 0:
                posting_frequency = round(len(timestamps) / time_span_days * 7, 1)

        result = {
            "media_type_breakdown": media_type_breakdown,
            "top_posts": scored_posts[:5],
            "worst_posts": scored_posts[-5:] if len(scored_posts) > 5 else [],
            "avg_caption_length": round(sum(caption_lengths) / max(len(caption_lengths), 1)),
            "top_hashtags": all_hashtags.most_common(15),
            "posting_frequency": posting_frequency,
            "posts_analyzed": len(posts),
        }

        logger.info(
            f"📊 Content @{username}: {len(posts)} posts | "
            f"freq={posting_frequency:.1f}/week | "
            f"types={dict(Counter(self._get_media_type(p) for p in posts))}"
        )
        return result

    # ═══════════════════════════════════════════════════════════
    # PROFILE SUMMARY
    # ═══════════════════════════════════════════════════════════

    def profile_summary(
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
        # Gather all analytics
        engagement = self.engagement_rate(username, post_count)
        timing = self.best_posting_times(username, post_count)
        content = self.content_analysis(username, post_count)

        # Profile info
        user = self._users.get_by_username(username)
        profile = {
            "username": getattr(user, "username", username),
            "full_name": getattr(user, "full_name", ""),
            "followers": getattr(user, "followers", 0),
            "following": getattr(user, "following", 0),
            "is_verified": getattr(user, "is_verified", False),
            "is_private": getattr(user, "is_private", False),
            "biography": getattr(user, "biography", ""),
        }

        return {
            "profile": profile,
            "engagement": engagement,
            "best_times": {
                "hours": timing.get("best_hours", [])[:3],
                "days": timing.get("best_days", [])[:3],
            },
            "content": {
                "media_types": content.get("media_type_breakdown", {}),
                "top_posts": content.get("top_posts", [])[:3],
                "posting_frequency": content.get("posting_frequency", 0),
                "top_hashtags": content.get("top_hashtags", [])[:10],
            },
            "analyzed_at": datetime.now().isoformat(),
        }

    # ═══════════════════════════════════════════════════════════
    # COMPETITOR COMPARISON
    # ═══════════════════════════════════════════════════════════

    def compare(
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

        for username in usernames:
            try:
                eng = self.engagement_rate(username, post_count)
                content = self.content_analysis(username, post_count)
                user = self._users.get_by_username(username)

                accounts.append({
                    "username": username,
                    "followers": eng.get("followers", 0),
                    "engagement_rate": eng.get("engagement_rate", 0),
                    "avg_likes": eng.get("avg_likes", 0),
                    "avg_comments": eng.get("avg_comments", 0),
                    "posting_frequency": content.get("posting_frequency", 0),
                    "top_hashtags": content.get("top_hashtags", [])[:5],
                    "rating": eng.get("rating", "no_data"),
                })
            except Exception as e:
                accounts.append({"username": username, "error": str(e)})

        valid = [a for a in accounts if "error" not in a]

        rankings = {}
        if valid:
            rankings["followers"] = sorted(valid, key=lambda a: a.get("followers", 0), reverse=True)[0]["username"]
            rankings["engagement"] = sorted(valid, key=lambda a: a.get("engagement_rate", 0), reverse=True)[0]["username"]
            rankings["avg_likes"] = sorted(valid, key=lambda a: a.get("avg_likes", 0), reverse=True)[0]["username"]
            rankings["posting_frequency"] = sorted(valid, key=lambda a: a.get("posting_frequency", 0), reverse=True)[0]["username"]

        # Overall winner (most #1 rankings)
        from collections import Counter as Cnt
        wins = Cnt(rankings.values())
        winner = wins.most_common(1)[0][0] if wins else None

        result = {
            "accounts": accounts,
            "rankings": rankings,
            "winner": winner,
            "compared_at": datetime.now().isoformat(),
        }
        logger.info(f"📊 Compare {usernames}: winner=@{winner}")
        return result

    # ═══════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════

    def _fetch_posts(self, user_id, count: int = 12) -> List[Dict]:
        """Fetch user posts via feed API."""
        if not user_id:
            return []
        posts = []
        cursor = None
        while len(posts) < count:
            try:
                result = self._client.request(
                    "GET", f"/api/v1/feed/user/{user_id}/",
                    params={"count": str(min(count - len(posts), 33)), **({"max_id": cursor} if cursor else {})},
                )
            except Exception as e:
                logger.debug(f"Fetch posts error: {e}")
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

    @staticmethod
    def _get_likes(post: Dict) -> int:
        return post.get("like_count", 0) or post.get("likes", 0) or 0

    @staticmethod
    def _get_comments(post: Dict) -> int:
        return post.get("comment_count", 0) or post.get("comments", 0) or 0

    @staticmethod
    def _get_timestamp(post: Dict) -> Optional[int]:
        return post.get("taken_at") or post.get("taken_at_timestamp")

    @staticmethod
    def _get_caption(post: Dict) -> str:
        cap = post.get("caption")
        if isinstance(cap, dict):
            return cap.get("text", "")
        return cap or ""

    @staticmethod
    def _get_media_type(post: Dict) -> str:
        mt = post.get("media_type")
        if mt == 1:
            return "photo"
        elif mt == 2:
            return "video"
        elif mt == 8:
            return "carousel"
        typename = post.get("__typename", "")
        if "Video" in typename:
            return "video"
        if "Sidecar" in typename:
            return "carousel"
        return "photo"
