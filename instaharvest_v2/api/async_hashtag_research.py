"""
Async Hashtag Research Tool
============================
Async version of HashtagResearchAPI. Full feature parity.
"""

import logging
import math
from collections import Counter
from typing import Any, Dict, List, Optional

logger = logging.getLogger("instaharvest_v2.hashtag_research")


class AsyncHashtagResearchAPI:
    """
    Async hashtag research and analysis.

    Composes: AsyncHashtagsAPI, async client direct requests.
    """

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

    async def analyze(
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
                - difficulty: easy/medium/hard/very_hard
                - competition_score: 0-1
                - engagement: avg likes/comments from sample
                - related: related hashtags found in posts
                - suggested_size: ideal follower range for this hashtag
        """
        tag = tag.lstrip("#").strip().lower()
        info = await self._get_hashtag_info(tag)
        media_count = info.get("media_count", 0)
        difficulty = self._calculate_difficulty(media_count)
        competition = self._competition_score(media_count)

        posts = await self._sample_posts(tag, sample_posts)
        engagement = self._analyze_engagement(posts)
        related = self._extract_related(posts, tag)

        return {
            "name": tag,
            "media_count": media_count,
            "difficulty": difficulty,
            "competition_score": round(competition, 2),
            "engagement": engagement,
            "related": related[:20],
            "suggested_size": self._suggest_audience_size(media_count),
        }

    async def related(self, tag: str, count: int = 30) -> List[Dict]:
        """
        Find related hashtags that appear together.

        Args:
            tag: Source hashtag
            count: Max related tags to return

        Returns:
            List of {name, co_occurrence} dicts
        """
        tag = tag.lstrip("#").strip().lower()
        posts = await self._sample_posts(tag, 50)
        return self._extract_related(posts, tag)[:count]

    async def suggest(
        self,
        seed_tag: str,
        count: int = 20,
        mix: str = "balanced",
    ) -> List[Dict]:
        """
        Smart hashtag suggestions based on a seed tag.

        Args:
            seed_tag: Starting hashtag
            count: Total suggestions needed
            mix: 'easy', 'balanced', 'competitive'

        Returns:
            List of {name, media_count, difficulty, reason} dicts
        """
        seed_tag = seed_tag.lstrip("#").strip().lower()
        related_tags = await self.related(seed_tag, count=count * 2)
        suggestions = []

        for tag_info in related_tags:
            tag_name = tag_info.get("name", "")
            if not tag_name:
                continue
            try:
                info = await self._get_hashtag_info(tag_name)
                mc = info.get("media_count", 0)
                d = self._calculate_difficulty(mc)
                suggestions.append({
                    "name": tag_name,
                    "media_count": mc,
                    "difficulty": d,
                    "reason": f"Related to #{seed_tag}",
                })
            except Exception:
                continue

        # Sort by mix preference
        if mix == "easy":
            suggestions.sort(key=lambda x: x.get("media_count", 0))
        elif mix == "competitive":
            suggestions.sort(key=lambda x: x.get("media_count", 0), reverse=True)
        else:
            # balanced — mix of difficulties
            easy = [s for s in suggestions if s["difficulty"] in ("very_easy", "easy")]
            medium = [s for s in suggestions if s["difficulty"] == "medium"]
            hard = [s for s in suggestions if s["difficulty"] in ("hard", "very_hard")]
            suggestions = []
            for group in [easy, medium, hard]:
                suggestions.extend(group[:count // 3 + 1])

        return suggestions[:count]

    async def compare(self, tags: List[str]) -> List[Dict]:
        """
        Compare multiple hashtags side by side.

        Args:
            tags: List of hashtags to compare

        Returns:
            List of analysis results, one per tag
        """
        results = []
        for tag in tags:
            try:
                result = await self.analyze(tag)
                results.append(result)
            except Exception as e:
                results.append({"name": tag, "error": str(e)})
        return results

    # ─── Internal helpers ──────────────────────────────────────

    async def _get_hashtag_info(self, tag: str) -> Dict:
        """Get basic hashtag info."""
        try:
            data = await self._hashtags.info(tag)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {"name": tag, "media_count": 0}

    async def _sample_posts(self, tag: str, count: int) -> List[Dict]:
        """Sample recent posts from a hashtag."""
        posts = []
        try:
            result = await self._hashtags.get_recent_media(tag)
            if isinstance(result, dict):
                items = result.get("items", [])
                posts.extend(items)

            if len(posts) < count:
                result = await self._hashtags.get_sections(tag, tab="recent")
                if isinstance(result, dict):
                    for sec in result.get("sections", []):
                        for m in sec.get("layout_content", {}).get("medias", []):
                            media = m.get("media", {})
                            if media:
                                posts.append(media)
        except Exception as e:
            logger.debug(f"Sample posts error for #{tag}: {e}")

        return posts[:count]

    @staticmethod
    def _analyze_engagement(posts: List[Dict]) -> Dict[str, Any]:
        """Analyze engagement from post samples."""
        if not posts:
            return {"avg_likes": 0, "avg_comments": 0, "sample_size": 0}

        total_likes = 0
        total_comments = 0
        for p in posts:
            total_likes += p.get("like_count", 0) or 0
            total_comments += p.get("comment_count", 0) or 0

        count = len(posts)
        return {
            "avg_likes": round(total_likes / count, 1),
            "avg_comments": round(total_comments / count, 1),
            "sample_size": count,
        }

    @staticmethod
    def _extract_related(posts: List[Dict], exclude_tag: str) -> List[Dict]:
        """Extract related hashtags from post captions."""
        import re
        counter: Counter = Counter()
        for p in posts:
            cap = p.get("caption")
            text = cap.get("text", "") if isinstance(cap, dict) else (cap or "")
            tags = re.findall(r"#(\w+)", text.lower())
            for t in tags:
                if t != exclude_tag:
                    counter[t] += 1

        return [{"name": tag, "co_occurrence": cnt} for tag, cnt in counter.most_common(50)]

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
        return min(1.0, math.log10(media_count + 1) / 8)

    @staticmethod
    def _suggest_audience_size(media_count: int) -> Dict[str, int]:
        """Suggest ideal account follower range for this hashtag."""
        if media_count > 5_000_000:
            return {"min": 50_000, "max": 1_000_000}
        elif media_count > 1_000_000:
            return {"min": 10_000, "max": 100_000}
        elif media_count > 200_000:
            return {"min": 1_000, "max": 50_000}
        elif media_count > 50_000:
            return {"min": 100, "max": 10_000}
        return {"min": 0, "max": 5_000}
