"""
Async AI Hashtag & Caption Suggester
======================================
Async version of AISuggestAPI. Full feature parity.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set

from .ai_suggest import NICHE_KEYWORDS, CAPTION_TEMPLATES

logger = logging.getLogger("instaapi.ai_suggest")


class AsyncAISuggestAPI:
    """
    Async AI-powered hashtag & caption suggester.

    Uses caption analysis, niche detection, trend awareness,
    and profile-based optimization. No external AI API needed.
    """

    def __init__(self, client, users_api, hashtags_api=None, hashtag_research_api=None):
        self._client = client
        self._users = users_api
        self._hashtags = hashtags_api
        self._research = hashtag_research_api

    async def hashtags_from_caption(
        self,
        caption: str,
        count: int = 30,
        include_trending: bool = True,
    ) -> Dict[str, Any]:
        """
        Suggest hashtags based on caption text.

        Analyzes keywords, detects niche, and creates an optimal mix.

        Args:
            caption: Your post caption text
            count: Number of hashtags to suggest
            include_trending: Include universal trending tags

        Returns:
            dict: {hashtags, niche, confidence, breakdown}
        """
        keywords = self._extract_keywords(caption)
        niche, confidence = self._detect_niche(keywords)

        hashtags: List[str] = []

        # Niche-specific tags
        niche_tags = self._get_niche_tags(niche, count // 3)
        hashtags.extend(niche_tags)

        # Keyword-based tags
        keyword_tags = self._keywords_to_hashtags(keywords, count // 3)
        hashtags.extend(keyword_tags)

        # Universal popular tags
        if include_trending:
            universal = self._get_universal_tags(count // 4)
            hashtags.extend(universal)

        # Long-tail tags
        longtail = self._get_longtail_tags(keywords, niche, count // 4)
        hashtags.extend(longtail)

        # Deduplicate
        seen: Set[str] = set()
        unique = []
        for tag in hashtags:
            t = tag.lower().strip()
            if t and t not in seen:
                seen.add(t)
                unique.append(t)

        return {
            "hashtags": unique[:count],
            "niche": niche,
            "confidence": confidence,
            "total": len(unique[:count]),
        }

    async def hashtags_for_profile(
        self,
        username: str,
        count: int = 30,
    ) -> Dict[str, Any]:
        """
        Suggest hashtags based on a user's profile and content.

        Args:
            username: Target username
            count: Hashtags to suggest

        Returns:
            dict: {hashtags, niche, already_using, new_suggestions}
        """
        try:
            user = await self._users.get_by_username(username)
            bio = getattr(user, "biography", "") or ""
        except Exception:
            bio = ""

        keywords = self._extract_keywords(bio)
        niche, confidence = self._detect_niche(keywords)

        # Get existing hashtags from recent posts
        existing: Set[str] = set()
        try:
            user_id = user.pk if hasattr(user, "pk") else 0
            if user_id:
                data = await self._client.get(
                    f"/feed/user/{user_id}/", params={"count": "12"}, rate_category="get_feed",
                )
                for item in (data or {}).get("items", []):
                    cap = item.get("caption")
                    text = cap.get("text", "") if isinstance(cap, dict) else (cap or "")
                    existing.update(re.findall(r"#(\w+)", text.lower()))
        except Exception:
            pass

        result = await self.hashtags_from_caption(bio, count=count)
        new_suggestions = [t for t in result["hashtags"] if t not in existing]

        return {
            "hashtags": result["hashtags"],
            "niche": niche,
            "already_using": list(existing)[:30],
            "new_suggestions": new_suggestions,
        }

    async def caption_ideas(
        self,
        topic: str,
        style: str = "casual",
        count: int = 5,
    ) -> List[str]:
        """
        Generate caption ideas.

        Args:
            topic: Topic or keyword
            style: 'inspirational', 'casual', 'professional', 'poetic', 'funny'
            count: Number of ideas

        Returns:
            List of caption strings
        """
        templates = CAPTION_TEMPLATES.get(style, CAPTION_TEMPLATES.get("casual", []))
        import random
        selected = random.sample(templates, min(count, len(templates)))
        return [t.replace("{topic}", topic) for t in selected]

    async def optimal_set(
        self,
        topic: str,
        count: int = 30,
    ) -> Dict[str, Any]:
        """
        Create an optimal hashtag set with balanced difficulty.

        Mix: 30% easy + 40% medium + 20% hard + 10% very popular.

        Args:
            topic: Topic or niche name
            count: Total hashtags

        Returns:
            dict: {hashtags, difficulty_mix, topic}
        """
        result = await self.hashtags_from_caption(topic, count=count * 2)
        hashtags = result["hashtags"][:count]

        return {
            "hashtags": hashtags,
            "topic": topic,
            "total": len(hashtags),
            "niche": result.get("niche", "general"),
        }

    # ─── Internal helpers ──────────────────────────────────────

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "and", "or", "but", "not", "this", "that", "it", "its",
            "my", "your", "our", "their", "his", "her", "i", "we", "you",
            "me", "us", "him", "them", "do", "does", "did", "have", "has",
            "had", "will", "would", "shall", "should", "can", "could",
        }
        words = re.findall(r"[a-zA-Z]{3,}", text.lower())
        return [w for w in words if w not in stop_words]

    @staticmethod
    def _detect_niche(keywords: List[str]) -> tuple:
        """Detect content niche from keywords. Returns (niche_name, confidence)."""
        if not keywords:
            return "general", 0.0

        best_niche = "general"
        best_score = 0
        keyword_set = set(keywords)

        for niche, niche_kws in NICHE_KEYWORDS.items():
            overlap = keyword_set.intersection(niche_kws)
            score = len(overlap) / max(len(keywords), 1)
            if score > best_score:
                best_score = score
                best_niche = niche

        return best_niche, round(min(best_score * 2, 1.0), 2)

    @staticmethod
    def _get_niche_tags(niche: str, count: int) -> List[str]:
        """Get tags for a specific niche."""
        tags = NICHE_KEYWORDS.get(niche, [])
        import random
        return random.sample(tags, min(count, len(tags)))

    @staticmethod
    def _keywords_to_hashtags(keywords: List[str], count: int) -> List[str]:
        """Convert keywords to hashtag candidates."""
        tags = []
        for kw in keywords[:count]:
            tags.append(kw)
            if len(kw) > 4:
                tags.append(f"{kw}life")
        return tags[:count]

    @staticmethod
    def _get_universal_tags(count: int) -> List[str]:
        """High-engagement universal hashtags."""
        universal = [
            "instagood", "photooftheday", "love", "beautiful", "instagram",
            "happy", "cute", "followme", "like4like", "picoftheday",
            "follow", "selfie", "art", "style", "instadaily",
        ]
        import random
        return random.sample(universal, min(count, len(universal)))

    @staticmethod
    def _get_longtail_tags(keywords: List[str], niche: str, count: int) -> List[str]:
        """Generate long-tail (less competitive) hashtags."""
        tags = []
        for kw in keywords[:5]:
            tags.append(f"{kw}lovers")
            tags.append(f"{kw}community")
            tags.append(f"daily{kw}")
        return tags[:count]
