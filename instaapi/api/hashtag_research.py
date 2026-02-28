"""
Hashtag Research Tool
=====================
Analyze hashtags: difficulty, competition, related hashtags,
average engagement, and smart suggestions.

Usage:
    ig = Instagram.from_env(".env")

    # Full hashtag analysis
    result = ig.hashtag_research.analyze("python")
    print(result["difficulty"])  # "medium"
    print(result["related"])    # [...related hashtags...]

    # Find related hashtags
    related = ig.hashtag_research.related("python")

    # Smart suggestions
    suggestions = ig.hashtag_research.suggest("programming", count=20)
"""

import logging
import math
from collections import Counter
from typing import Any, Dict, List, Optional

logger = logging.getLogger("instaapi.hashtag_research")


class HashtagResearchAPI:
    """
    Hashtag research and analysis.

    Composes: HashtagsAPI, client direct requests.
    """

    # Difficulty thresholds (posts count)
    DIFFICULTY_THRESHOLDS = [
        (5_000_000, "very_hard"),
        (1_000_000, "hard"),
        (200_000, "medium"),
        (50_000, "easy"),
        (0, "very_easy"),
    ]

    def __init__(self, client, hashtags_api):
        self._client = client
        self._hashtags = hashtags_api

    # ═══════════════════════════════════════════════════════════
    # FULL ANALYSIS
    # ═══════════════════════════════════════════════════════════

    def analyze(
        self,
        tag: str,
        sample_posts: int = 30,
    ) -> Dict[str, Any]:
        """
        Full hashtag analysis.

        Args:
            tag: Hashtag (with or without #)
            sample_posts: Posts to sample for engagement stats

        Returns:
            dict:
                - name: hashtag name
                - media_count: total posts
                - difficulty: very_easy/easy/medium/hard/very_hard
                - competition_score: 0-1 float
                - avg_likes: average likes per post
                - avg_comments: average comments per post
                - engagement_score: combined engagement metric
                - top_posts_sample: top posts with engagement
                - related: related hashtags found in posts
                - suggested_size: ideal follower range for this hashtag
        """
        tag = tag.lstrip("#").strip().lower()

        # Fetch hashtag info
        info = self._get_hashtag_info(tag)
        media_count = info.get("media_count", 0)

        # Difficulty
        difficulty = self._calculate_difficulty(media_count)
        competition = self._competition_score(media_count)

        # Sample posts for engagement analysis
        posts = self._sample_posts(tag, sample_posts)
        engagement = self._analyze_engagement(posts)

        # Find related hashtags
        related = self._extract_related(posts, tag)

        result = {
            "name": tag,
            "media_count": media_count,
            "difficulty": difficulty,
            "competition_score": round(competition, 2),
            "avg_likes": engagement["avg_likes"],
            "avg_comments": engagement["avg_comments"],
            "engagement_score": engagement["score"],
            "top_posts_sample": engagement["top_posts"][:5],
            "related": related[:20],
            "suggested_size": self._suggest_audience_size(media_count),
            "posts_analyzed": len(posts),
        }

        logger.info(
            f"🔍 #{tag}: {media_count:,} posts | difficulty={difficulty} | "
            f"avg_likes={engagement['avg_likes']:.0f} | "
            f"related={len(related)} tags"
        )
        return result

    # ═══════════════════════════════════════════════════════════
    # RELATED HASHTAGS
    # ═══════════════════════════════════════════════════════════

    def related(self, tag: str, count: int = 30) -> List[Dict[str, Any]]:
        """
        Find related hashtags that appear together.

        Args:
            tag: Source hashtag
            count: Max related tags to return

        Returns:
            List of {name, co_occurrence, media_count} dicts
        """
        tag = tag.lstrip("#").strip().lower()
        posts = self._sample_posts(tag, 50)
        related = self._extract_related(posts, tag)
        return related[:count]

    # ═══════════════════════════════════════════════════════════
    # SUGGESTIONS
    # ═══════════════════════════════════════════════════════════

    def suggest(
        self,
        seed_tag: str,
        count: int = 20,
        mix: str = "balanced",
    ) -> List[Dict[str, Any]]:
        """
        Smart hashtag suggestions based on a seed tag.

        Creates a balanced mix of difficulty levels.

        Args:
            seed_tag: Starting hashtag
            count: Total suggestions needed
            mix: 'easy', 'balanced', 'competitive'

        Returns:
            List of {name, media_count, difficulty, reason} dicts
        """
        seed_tag = seed_tag.lstrip("#").strip().lower()

        # Get related
        posts = self._sample_posts(seed_tag, 50)
        raw_related = self._extract_related(posts, seed_tag)

        # Enrich with media counts
        enriched = []
        for r in raw_related[:40]:  # Limit API calls
            tag_name = r.get("name", "")
            info = self._get_hashtag_info(tag_name)
            mc = info.get("media_count", 0)
            diff = self._calculate_difficulty(mc)
            enriched.append({
                "name": tag_name,
                "media_count": mc,
                "difficulty": diff,
                "co_occurrence": r.get("co_occurrence", 0),
                "reason": f"Related to #{seed_tag}",
            })

        # Mix strategy
        if mix == "easy":
            enriched.sort(key=lambda x: x.get("media_count", 0))
        elif mix == "competitive":
            enriched.sort(key=lambda x: x.get("media_count", 0), reverse=True)
        else:
            # Balanced — mix easy + medium + hard
            easy = [t for t in enriched if t["difficulty"] in ("very_easy", "easy")]
            medium = [t for t in enriched if t["difficulty"] == "medium"]
            hard = [t for t in enriched if t["difficulty"] in ("hard", "very_hard")]

            balanced: list = []
            while len(balanced) < count and (easy or medium or hard):
                if easy:
                    balanced.append(easy.pop(0))
                if medium and len(balanced) < count:
                    balanced.append(medium.pop(0))
                if hard and len(balanced) < count:
                    balanced.append(hard.pop(0))
            enriched = balanced

        return enriched[:count]

    # ═══════════════════════════════════════════════════════════
    # COMPARE HASHTAGS
    # ═══════════════════════════════════════════════════════════

    def compare(self, tags: List[str]) -> List[Dict[str, Any]]:
        """
        Compare multiple hashtags side by side.

        Args:
            tags: List of hashtags to compare

        Returns:
            List of analysis results, one per tag
        """
        results = []
        for tag in tags:
            result = self.analyze(tag, sample_posts=15)
            results.append(result)
        return results

    # ═══════════════════════════════════════════════════════════
    # INTERNAL
    # ═══════════════════════════════════════════════════════════

    def _get_hashtag_info(self, tag: str) -> Dict:
        """Get basic hashtag info."""
        try:
            result = self._client.request(
                "GET", f"/api/v1/tags/{tag}/info/",
            )
            return result if isinstance(result, dict) else {}
        except Exception:
            return {"name": tag, "media_count": 0}

    def _sample_posts(self, tag: str, count: int) -> List[Dict]:
        """Sample recent posts from a hashtag."""
        posts = []
        try:
            result = self._client.request(
                "GET", f"/api/v1/tags/{tag}/sections/",
                params={"tab": "recent", "count": str(min(count, 50))},
            )
            if result and isinstance(result, dict):
                for sec in result.get("sections", []):
                    for m in sec.get("layout_content", {}).get("medias", []):
                        media = m.get("media", {})
                        if media:
                            posts.append(media)
        except Exception as e:
            logger.debug(f"Sample posts error for #{tag}: {e}")

        # Also try top posts
        if len(posts) < count:
            try:
                result = self._client.request(
                    "GET", f"/api/v1/tags/{tag}/sections/",
                    params={"tab": "top"},
                )
                if result and isinstance(result, dict):
                    for sec in result.get("sections", []):
                        for m in sec.get("layout_content", {}).get("medias", []):
                            media = m.get("media", {})
                            if media:
                                posts.append(media)
            except Exception:
                pass

        return posts[:count]

    @staticmethod
    def _analyze_engagement(posts: List[Dict]) -> Dict[str, Any]:
        """Analyze engagement from post samples."""
        if not posts:
            return {"avg_likes": 0, "avg_comments": 0, "score": 0, "top_posts": []}

        scored = []
        total_likes = 0
        total_comments = 0

        for post in posts:
            likes = post.get("like_count", 0) or 0
            comments = post.get("comment_count", 0) or 0
            total_likes += likes
            total_comments += comments

            scored.append({
                "shortcode": post.get("code", ""),
                "likes": likes,
                "comments": comments,
                "engagement": likes + comments,
            })

        n = len(posts)
        avg_likes = total_likes / n
        avg_comments = total_comments / n

        scored.sort(key=lambda p: p["engagement"], reverse=True)

        return {
            "avg_likes": round(avg_likes, 1),
            "avg_comments": round(avg_comments, 1),
            "score": round(avg_likes + avg_comments, 1),
            "top_posts": scored[:5],
        }

    @staticmethod
    def _extract_related(posts: List[Dict], exclude_tag: str) -> List[Dict[str, Any]]:
        """Extract related hashtags from post captions."""
        import re
        tag_counter: Counter = Counter()

        for post in posts:
            caption = post.get("caption", {})
            if isinstance(caption, dict):
                text = caption.get("text", "")
            else:
                text = str(caption or "")

            tags = re.findall(r"#(\w+)", text.lower())
            for t in tags:
                if t != exclude_tag and len(t) > 1:
                    tag_counter[t] += 1

        return [
            {"name": tag, "co_occurrence": count}
            for tag, count in tag_counter.most_common(50)
        ]

    def _calculate_difficulty(self, media_count: int) -> str:
        """Calculate hashtag difficulty based on post count."""
        for threshold, label in self.DIFFICULTY_THRESHOLDS:
            if media_count >= threshold:
                return label
        return "very_easy"

    @staticmethod
    def _competition_score(media_count: int) -> float:
        """0-1 competition score based on media count."""
        if media_count <= 0:
            return 0.0
        return min(1.0, math.log10(max(media_count, 1)) / 8)

    @staticmethod
    def _suggest_audience_size(media_count: int) -> str:
        """Suggest ideal account follower range for this hashtag."""
        if media_count > 5_000_000:
            return "500K+ followers"
        elif media_count > 1_000_000:
            return "100K-500K followers"
        elif media_count > 200_000:
            return "10K-100K followers"
        elif media_count > 50_000:
            return "1K-10K followers"
        else:
            return "0-1K followers"
