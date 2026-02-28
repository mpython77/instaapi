"""
Public Data API — Instagram Public Data Analytics
===================================================
Supermetrics-style public data analytics for Instagram.

Provides 3 query types (matching Supermetrics connector):
  1. Profile Info  — followers, following, posts, bio, website
  2. Profile Posts  — all public posts with metrics
  3. Post Search   — hashtag-based search (Top & Recent)

Plus advanced features:
  - Multi-profile comparison with rankings
  - Profile growth tracking with snapshots
  - Engagement analysis
  - CSV/JSON/JSONL export

Usage:
    ig = Instagram.anonymous()

    # Profile Info
    profile = ig.public_data.get_profile_info("cristiano")
    print(f"@{profile.username} — {profile.followers:,} followers")

    # Multi-profile
    profiles = ig.public_data.get_profile_info(["cristiano", "messi"])

    # Profile Posts
    posts = ig.public_data.get_profile_posts("cristiano", max_count=20)

    # Hashtag Search
    top = ig.public_data.search_hashtag_top("fitness")
    recent = ig.public_data.search_hashtag_recent("fitness")

    # Compare
    comparison = ig.public_data.compare_profiles(["nike", "adidas"])

    # Export
    ig.public_data.export_report(report, "json", "output.json")
"""

import csv
import json
import logging
import re
import time
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from ..models.public_data import (
    PublicProfile,
    PublicPost,
    HashtagPost,
    ProfileSnapshot,
    PublicDataReport,
)

logger = logging.getLogger("instaharvest_v2.public_data")


# ═══════════════════════════════════════════════════════════════════
# Rate limit tracker for hashtag searches
# ═══════════════════════════════════════════════════════════════════

class HashtagQuotaTracker:
    """
    Track hashtag search quota per Instagram profile.

    Instagram limits: 30 unique hashtag IDs per profile per 7 days.
    Re-searching the same hashtag does NOT count as additional usage.
    """

    def __init__(self, max_per_profile: int = 30, window_days: int = 7):
        self.max_per_profile = max_per_profile
        self.window_days = window_days
        self._searches: Dict[str, List[Dict[str, Any]]] = {}  # profile -> [{hashtag, timestamp}]

    def can_search(self, hashtag: str, profile_count: int = 1) -> bool:
        """Check if a hashtag search is allowed within quota."""
        total_quota = self.max_per_profile * profile_count
        unique_searched = self._get_unique_searched()
        if hashtag in unique_searched:
            return True  # Re-search doesn't count
        return len(unique_searched) < total_quota

    def record_search(self, hashtag: str) -> None:
        """Record a hashtag search."""
        key = "_default"
        if key not in self._searches:
            self._searches[key] = []
        self._searches[key].append({
            "hashtag": hashtag.lower().strip("#"),
            "timestamp": datetime.utcnow(),
        })

    def get_remaining_quota(self, profile_count: int = 1) -> int:
        """Get remaining hashtag search quota."""
        total_quota = self.max_per_profile * profile_count
        unique_count = len(self._get_unique_searched())
        return max(0, total_quota - unique_count)

    def _get_unique_searched(self) -> set:
        """Get unique hashtags searched within the rolling window."""
        cutoff = datetime.utcnow() - timedelta(days=self.window_days)
        unique = set()
        for entries in self._searches.values():
            for entry in entries:
                if entry["timestamp"] >= cutoff:
                    unique.add(entry["hashtag"])
        return unique

    def reset(self) -> None:
        """Reset all tracked searches."""
        self._searches.clear()


# ═══════════════════════════════════════════════════════════════════
# Main Public Data API
# ═══════════════════════════════════════════════════════════════════

class PublicDataAPI:
    """
    Instagram Public Data API — Supermetrics-style analytics.

    Composes: PublicAPI (AnonClient-based public data access).
    Works WITHOUT login — purely public data.

    Query Types (matching Supermetrics):
        1. Profile Info:    get_profile_info()
        2. Profile Posts:   get_profile_posts()
        3. Post Search:     search_hashtag_top(), search_hashtag_recent()

    Extended Features:
        - compare_profiles(): Multi-profile comparison
        - track_profile(): Growth tracking with snapshots
        - engagement_analysis(): Detailed engagement metrics
        - export_report(): CSV/JSON/JSONL export

    Rate Limits (Instagram API):
        - Hashtag search: 30 unique / profile / 7 days
        - Max 100 unique hashtag IDs per request
    """

    # Constants matching Supermetrics documentation
    MAX_HASHTAG_PER_PROFILE = 30
    MAX_HASHTAG_PER_REQUEST = 100
    HASHTAG_WINDOW_DAYS = 7
    HISTORY_RANGE_YEARS = 2
    RECENT_SEARCH_HOURS = 24
    RECENT_SEARCH_MAX = 250
    TOP_SEARCH_MAX = 100

    def __init__(self, public_api):
        """
        Initialize Public Data API.

        Args:
            public_api: PublicAPI instance (anonymous, no login needed)
        """
        self._public = public_api
        self._quota = HashtagQuotaTracker(
            max_per_profile=self.MAX_HASHTAG_PER_PROFILE,
            window_days=self.HASHTAG_WINDOW_DAYS,
        )
        self._snapshots: Dict[str, List[ProfileSnapshot]] = {}
        logger.debug("PublicDataAPI initialized")

    # ─── Query Type 1: Profile Info ───────────────────────────

    def get_profile_info(
        self,
        usernames: Union[str, List[str]],
    ) -> Union[PublicProfile, List[PublicProfile]]:
        """
        Get public profile information (Supermetrics: Profile Info query type).

        Returns current follower count, following count, posts count,
        bio, website, profile pic, and other basic info.

        Note: Historical data is NOT available — only current values.
        Use track_profile() to build historical data over time.

        Args:
            usernames: Single username or list of usernames (case-sensitive)

        Returns:
            PublicProfile or list of PublicProfile

        Raises:
            ValueError: If username is empty or invalid
        """
        single = isinstance(usernames, str)
        if single:
            usernames = [usernames]

        usernames = [u.strip().strip("@") for u in usernames if u.strip()]
        if not usernames:
            raise ValueError("At least one username is required")

        profiles = []
        for username in usernames:
            try:
                raw = self._public.get_profile(username)
                if raw:
                    profile = PublicProfile.from_api(
                        raw if isinstance(raw, dict) else {"user": raw}
                    )
                    if not profile.username:
                        profile.username = username
                    profiles.append(profile)
                    logger.info(f"Profile fetched: @{username} ({profile.followers:,} followers)")
                else:
                    logger.warning(
                        f"Profile not found or restricted: @{username}. "
                        "Account may be private, restricted, or age-limited."
                    )
            except Exception as e:
                logger.error(f"Error fetching profile @{username}: {e}")

        if single:
            return profiles[0] if profiles else PublicProfile(username=usernames[0])
        return profiles

    # ─── Query Type 2: Profile Posts ──────────────────────────

    def get_profile_posts(
        self,
        usernames: Union[str, List[str]],
        max_count: int = 12,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[PublicPost]:
        """
        Get public posts from profiles (Supermetrics: Profile Posts query type).

        Returns post metrics: likes, comments, post URL, image URL,
        media type (image/video/carousel), caption, hashtags, etc.

        Historical data available for the last 2 years.

        Args:
            usernames: Single username or list (case-sensitive)
            max_count: Maximum posts per profile (default 12)
            date_from: Filter posts from this date (optional)
            date_to: Filter posts until this date (optional)

        Returns:
            List of PublicPost objects

        Note:
            Stories, Reels, and IGTV content are NOT available.
            Private/restricted/age-limited accounts return empty results.
        """
        if isinstance(usernames, str):
            usernames = [usernames]

        usernames = [u.strip().strip("@") for u in usernames if u.strip()]
        all_posts = []

        for username in usernames:
            try:
                raw_posts = self._fetch_user_posts(username, max_count)
                for raw in raw_posts:
                    post = PublicPost.from_api(raw, username=username)

                    # Date filtering
                    if date_from and post.created_at and post.created_at < date_from:
                        continue
                    if date_to and post.created_at and post.created_at > date_to:
                        continue

                    all_posts.append(post)

                logger.info(f"Posts fetched: @{username} — {len(raw_posts)} posts")

            except Exception as e:
                logger.error(f"Error fetching posts for @{username}: {e}")

        return all_posts

    # ─── Query Type 3: Post Search ────────────────────────────

    def search_hashtag_top(
        self,
        hashtags: Union[str, List[str]],
        profile_count: int = 1,
    ) -> List[HashtagPost]:
        """
        Search for top posts by hashtag (Supermetrics: Post Search — Top).

        Returns up to 100 top posts based on Instagram's algorithm
        (not purely by likes or comments).

        Args:
            hashtags: Single hashtag or list (with or without #)
            profile_count: Number of IG profiles available (affects quota)

        Returns:
            List of HashtagPost objects

        Raises:
            ValueError: If hashtag quota exceeded

        Note:
            - Max 30 unique hashtags per profile per 7 days
            - Emoji hashtags are NOT supported
            - Stories, Reels, IGTV, promoted media are NOT returned
        """
        return self._search_hashtags(hashtags, "top", profile_count)

    def search_hashtag_recent(
        self,
        hashtags: Union[str, List[str]],
        profile_count: int = 1,
    ) -> List[HashtagPost]:
        """
        Search for recent posts by hashtag (Supermetrics: Post Search — Recent).

        Returns posts from the last 24 hours (max 250 posts).

        Args:
            hashtags: Single hashtag or list (with or without #)
            profile_count: Number of IG profiles available (affects quota)

        Returns:
            List of HashtagPost objects

        Note:
            - Only returns posts from last 24 hours
            - Maximum 250 most recent posts
            - Same quota limits as Top search
        """
        return self._search_hashtags(hashtags, "recent", profile_count)

    # ─── Extended: Compare Profiles ───────────────────────────

    def compare_profiles(
        self,
        usernames: List[str],
        post_count: int = 12,
    ) -> Dict[str, Any]:
        """
        Compare multiple profiles side by side.

        Provides rankings by followers, engagement rate, posting frequency,
        and determines an overall winner.

        Args:
            usernames: List of usernames to compare
            post_count: Posts to analyze per profile

        Returns:
            dict with:
                - accounts: per-account data
                - rankings: category rankings
                - winner: best overall account
        """
        if len(usernames) < 2:
            raise ValueError("Need at least 2 usernames to compare")

        accounts = []
        for username in usernames:
            username = username.strip().strip("@")
            try:
                profile = self.get_profile_info(username)
                posts = self.get_profile_posts(username, max_count=post_count)

                # Calculate engagement
                total_likes = sum(p.likes for p in posts)
                total_comments = sum(p.comments for p in posts)
                avg_likes = total_likes / len(posts) if posts else 0
                avg_comments = total_comments / len(posts) if posts else 0
                engagement_rate = (
                    (avg_likes + avg_comments) / profile.followers * 100
                    if profile.followers > 0 and posts else 0
                )

                accounts.append({
                    "username": username,
                    "followers": profile.followers,
                    "following": profile.following,
                    "posts_count": profile.posts_count,
                    "avg_likes": round(avg_likes, 1),
                    "avg_comments": round(avg_comments, 1),
                    "engagement_rate": round(engagement_rate, 4),
                    "posts_analyzed": len(posts),
                    "top_post": max(posts, key=lambda p: p.engagement).to_dict() if posts else None,
                    "profile": profile.to_dict(),
                })

            except Exception as e:
                logger.error(f"Error comparing @{username}: {e}")
                accounts.append({
                    "username": username,
                    "error": str(e),
                })

        # Rankings
        valid = [a for a in accounts if "error" not in a]
        rankings = {}
        if valid:
            rankings["followers"] = sorted(
                valid, key=lambda a: a["followers"], reverse=True
            )
            rankings["engagement_rate"] = sorted(
                valid, key=lambda a: a["engagement_rate"], reverse=True
            )
            rankings["avg_likes"] = sorted(
                valid, key=lambda a: a["avg_likes"], reverse=True
            )

        # Winner (most #1 positions)
        winner = None
        if valid:
            scores = Counter()
            for ranking_list in rankings.values():
                if ranking_list:
                    scores[ranking_list[0]["username"]] += 1
            winner = scores.most_common(1)[0][0] if scores else None

        return {
            "accounts": accounts,
            "rankings": {k: [a["username"] for a in v] for k, v in rankings.items()},
            "winner": winner,
            "compared_at": datetime.utcnow().isoformat(),
        }

    # ─── Extended: Track Profile ──────────────────────────────

    def track_profile(
        self,
        username: str,
    ) -> Dict[str, Any]:
        """
        Take a snapshot of a profile for growth tracking.

        Call periodically to build historical data over time.
        Since Instagram API only returns current values, snapshots
        let you track changes.

        Args:
            username: Target username

        Returns:
            dict with current snapshot and growth data since last snapshot
        """
        username = username.strip().strip("@")
        profile = self.get_profile_info(username)
        snapshot = ProfileSnapshot.from_profile(profile)

        if username not in self._snapshots:
            self._snapshots[username] = []

        self._snapshots[username].append(snapshot)

        result = {
            "profile": profile.to_dict(),
            "snapshot": snapshot.to_dict(),
            "total_snapshots": len(self._snapshots[username]),
        }

        # Growth comparison with previous snapshot
        if len(self._snapshots[username]) >= 2:
            prev = self._snapshots[username][-2]
            growth = snapshot.growth_since(prev)
            result["growth"] = growth
            logger.info(
                f"Track @{username}: followers {growth['follower_change']:+d} "
                f"({growth['follower_growth_rate']:+.1f}/hr)"
            )

        return result

    def get_tracking_history(self, username: str) -> List[Dict[str, Any]]:
        """Get all snapshots for a username."""
        return [s.to_dict() for s in self._snapshots.get(username, [])]

    # ─── Extended: Engagement Analysis ────────────────────────

    def engagement_analysis(
        self,
        username: str,
        post_count: int = 12,
    ) -> Dict[str, Any]:
        """
        Detailed engagement analysis for a profile.

        Calculates average likes, comments, engagement rate,
        best performing posts, content type breakdown, and more.

        Args:
            username: Target username
            post_count: Number of posts to analyze

        Returns:
            dict with comprehensive engagement metrics
        """
        username = username.strip().strip("@")
        profile = self.get_profile_info(username)
        posts = self.get_profile_posts(username, max_count=post_count)

        if not posts:
            return {
                "username": username,
                "followers": profile.followers,
                "error": "No posts found or account is restricted",
            }

        # Basic metrics
        total_likes = sum(p.likes for p in posts)
        total_comments = sum(p.comments for p in posts)
        avg_likes = total_likes / len(posts)
        avg_comments = total_comments / len(posts)
        engagement_rate = (
            (avg_likes + avg_comments) / profile.followers * 100
            if profile.followers > 0 else 0
        )

        # Rating
        if engagement_rate >= 6:
            rating = "excellent"
        elif engagement_rate >= 3:
            rating = "good"
        elif engagement_rate >= 1:
            rating = "average"
        else:
            rating = "low"

        # Content type breakdown
        type_stats = {}
        for p in posts:
            mt = p.media_type
            if mt not in type_stats:
                type_stats[mt] = {"count": 0, "total_likes": 0, "total_comments": 0}
            type_stats[mt]["count"] += 1
            type_stats[mt]["total_likes"] += p.likes
            type_stats[mt]["total_comments"] += p.comments

        for mt_data in type_stats.values():
            if mt_data["count"] > 0:
                mt_data["avg_likes"] = round(mt_data["total_likes"] / mt_data["count"], 1)
                mt_data["avg_comments"] = round(mt_data["total_comments"] / mt_data["count"], 1)

        # Top hashtags
        all_hashtags = []
        for p in posts:
            all_hashtags.extend(p.hashtags)
        top_hashtags = Counter(all_hashtags).most_common(20)

        # Top posts
        sorted_posts = sorted(posts, key=lambda p: p.engagement, reverse=True)
        top_3 = [
            {
                "url": p.post_url,
                "likes": p.likes,
                "comments": p.comments,
                "type": p.media_type,
                "caption": p.caption[:100] if p.caption else "",
            }
            for p in sorted_posts[:3]
        ]

        # Posting frequency
        if len(posts) >= 2:
            dates = [p.created_at for p in posts if p.created_at]
            if len(dates) >= 2:
                span = (max(dates) - min(dates)).days or 1
                posts_per_week = round(len(dates) / span * 7, 1)
            else:
                posts_per_week = 0
        else:
            posts_per_week = 0

        return {
            "username": username,
            "followers": profile.followers,
            "posts_analyzed": len(posts),
            "avg_likes": round(avg_likes, 1),
            "avg_comments": round(avg_comments, 1),
            "engagement_rate": round(engagement_rate, 4),
            "rating": rating,
            "content_type_breakdown": type_stats,
            "top_hashtags": [{"tag": t, "count": c} for t, c in top_hashtags],
            "top_posts": top_3,
            "posts_per_week": posts_per_week,
            "total_likes": total_likes,
            "total_comments": total_comments,
        }

    # ─── Extended: Build Full Report ──────────────────────────

    def build_report(
        self,
        usernames: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
        max_posts: int = 12,
    ) -> PublicDataReport:
        """
        Build a comprehensive Public Data report.

        Combines profile info, posts, and hashtag search results
        into a single PublicDataReport object.

        Args:
            usernames: Profiles to include
            hashtags: Hashtags to search (Top search)
            max_posts: Max posts per profile

        Returns:
            PublicDataReport with all data
        """
        start_time = time.time()
        report = PublicDataReport(
            query_start=datetime.utcnow(),
            usernames_queried=usernames or [],
            hashtags_queried=hashtags or [],
        )

        # Fetch profiles
        if usernames:
            report.profiles = self.get_profile_info(usernames)
            if isinstance(report.profiles, PublicProfile):
                report.profiles = [report.profiles]

            # Fetch posts for each profile
            for username in usernames:
                posts = self.get_profile_posts(username, max_count=max_posts)
                report.posts.extend(posts)

            report.query_type = "profile_posts" if max_posts > 0 else "profile_info"

        # Fetch hashtag search
        if hashtags:
            hashtag_posts = self.search_hashtag_top(hashtags)
            report.hashtag_posts = hashtag_posts
            if not report.query_type:
                report.query_type = "post_search"

        report.query_end = datetime.utcnow()
        report.query_duration_seconds = round(time.time() - start_time, 2)

        logger.info(
            f"Report built: {report.total_profiles} profiles, "
            f"{report.total_posts} posts, "
            f"{report.total_hashtag_posts} hashtag posts "
            f"in {report.query_duration_seconds}s"
        )

        return report

    # ─── Extended: Export ──────────────────────────────────────

    def export_report(
        self,
        report: PublicDataReport,
        format: str = "json",
        filepath: Optional[str] = None,
    ) -> Union[str, Dict[str, Any]]:
        """
        Export a Public Data report to file or string.

        Supports Supermetrics-compatible table formats.

        Args:
            report: PublicDataReport to export
            format: "json", "csv", or "jsonl"
            filepath: Output file path (None = return as string/dict)

        Returns:
            Exported data (string or dict)
        """
        format = format.lower().strip()

        if format == "json":
            data = {
                "profiles": report.to_profiles_table(),
                "posts": report.to_posts_table(),
                "hashtags": report.to_hashtags_table(),
                "metadata": {
                    "query_type": report.query_type,
                    "query_start": report.query_start.isoformat() if report.query_start else None,
                    "query_end": report.query_end.isoformat() if report.query_end else None,
                    "duration_seconds": report.query_duration_seconds,
                    "usernames": report.usernames_queried,
                    "hashtags": report.hashtags_queried,
                    "total_profiles": report.total_profiles,
                    "total_posts": report.total_posts,
                    "total_hashtag_posts": report.total_hashtag_posts,
                    "avg_likes": report.avg_likes,
                    "avg_comments": report.avg_comments,
                },
            }
            if filepath:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                logger.info(f"Report exported to {filepath}")
            return data

        elif format == "csv":
            rows = report.to_posts_table() or report.to_profiles_table()
            if not rows:
                return ""

            if filepath:
                with open(filepath, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
                logger.info(f"CSV exported to {filepath}")
                return filepath
            else:
                import io
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
                return output.getvalue()

        elif format == "jsonl":
            rows = report.to_posts_table() or report.to_profiles_table()
            lines = [json.dumps(row, ensure_ascii=False, default=str) for row in rows]
            content = "\n".join(lines)
            if filepath:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info(f"JSONL exported to {filepath}")
            return content

        else:
            raise ValueError(f"Unsupported format: {format}. Use 'json', 'csv', or 'jsonl'.")

    # ─── Quota Management ─────────────────────────────────────

    def get_hashtag_quota(self, profile_count: int = 1) -> Dict[str, Any]:
        """Get current hashtag search quota status."""
        remaining = self._quota.get_remaining_quota(profile_count)
        total = self.MAX_HASHTAG_PER_PROFILE * profile_count
        return {
            "remaining": remaining,
            "total": total,
            "used": total - remaining,
            "window_days": self.HASHTAG_WINDOW_DAYS,
            "profiles": profile_count,
        }

    def reset_quota(self) -> None:
        """Reset hashtag quota tracking (for testing)."""
        self._quota.reset()

    # ─── Internal Methods ─────────────────────────────────────

    def _fetch_user_posts(self, username: str, max_count: int) -> List[Dict]:
        """Fetch posts for a user via PublicAPI."""
        try:
            if max_count <= 12:
                posts = self._public.get_posts(username, max_count=max_count)
            else:
                posts = self._public.get_all_posts(username, max_count=max_count)
            return posts if isinstance(posts, list) else []
        except Exception as e:
            logger.error(f"Error fetching posts for @{username}: {e}")
            return []

    def _search_hashtags(
        self,
        hashtags: Union[str, List[str]],
        search_type: str,
        profile_count: int,
    ) -> List[HashtagPost]:
        """Internal hashtag search implementation."""
        if isinstance(hashtags, str):
            hashtags = [hashtags]

        # Clean hashtags
        hashtags = [h.strip().strip("#").lower() for h in hashtags if h.strip()]
        if not hashtags:
            raise ValueError("At least one hashtag is required")

        # Validate quota
        if len(hashtags) > self.MAX_HASHTAG_PER_REQUEST:
            raise ValueError(
                f"Too many hashtags: {len(hashtags)} "
                f"(max {self.MAX_HASHTAG_PER_REQUEST} per request)"
            )

        results = []
        for tag in hashtags:
            # Check quota
            if not self._quota.can_search(tag, profile_count):
                logger.warning(
                    f"Hashtag quota exceeded for #{tag}. "
                    f"Limit: {self.MAX_HASHTAG_PER_PROFILE} per profile / {self.HASHTAG_WINDOW_DAYS} days."
                )
                continue

            try:
                raw_posts = self._public.get_hashtag_posts(tag, max_count=12)
                if not isinstance(raw_posts, list):
                    raw_posts = []

                self._quota.record_search(tag)

                for raw in raw_posts:
                    post = PublicPost.from_api(raw)

                    # Find matching hashtags
                    matching = [
                        h for h in post.hashtags
                        if h.lower() in [t.lower() for t in hashtags]
                    ]

                    hp = HashtagPost(
                        post=post,
                        search_hashtag=tag,
                        matching_hashtags=matching,
                        search_type=search_type,
                    )
                    results.append(hp)

                logger.info(f"Hashtag #{tag} ({search_type}): {len(raw_posts)} posts found")

            except Exception as e:
                logger.error(f"Error searching hashtag #{tag}: {e}")

        return results

    def __repr__(self) -> str:
        quota = self._quota.get_remaining_quota()
        return (
            f"<PublicDataAPI "
            f"hashtag_quota={quota}/{self.MAX_HASHTAG_PER_PROFILE}>"
        )
