"""
AI Hashtag & Caption Suggester
===============================
AI-powered hashtag and caption suggestions based on
captions, hashtag analysis, and user profile data.

Usage:
    ig = Instagram.from_env(".env")

    # Suggest hashtags from caption text
    tags = ig.ai_suggest.hashtags_from_caption("Beautiful sunset at the beach")
    # → ["sunset", "beach", "nature", "photography", "golden_hour"]

    # Suggest hashtags based on a user's niche
    tags = ig.ai_suggest.hashtags_for_profile("cristiano")
    # → ["football", "soccer", "athlete", "sports", ...]

    # Generate caption ideas
    captions = ig.ai_suggest.caption_ideas("sunset", style="poetic")
    # → ["Chasing sunsets...", "Golden hour magic ✨", ...]

    # Optimal hashtag set for a post
    optimal = ig.ai_suggest.optimal_set("travel photography", count=30)
    # → Balanced mix of easy/medium/hard hashtags
"""

import logging
import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("instaapi.ai_suggest")


# ─── Built-in Niche Keywords Database ──────────────────────────
NICHE_KEYWORDS = {
    "fitness": ["fitness", "gym", "workout", "fitnessmotivation", "bodybuilding",
                "exercise", "training", "fitfam", "muscle", "gains", "health",
                "crossfit", "yoga", "running", "cardio", "personaltrainer"],
    "travel": ["travel", "wanderlust", "explore", "adventure", "travelgram",
               "instatravel", "travelphotography", "vacation", "trip",
               "traveltheworld", "backpacking", "tourism", "destination"],
    "food": ["food", "foodie", "foodporn", "cooking", "recipe", "delicious",
             "yummy", "homemade", "foodphotography", "chef", "baking",
             "healthyfood", "restaurant", "dinner", "lunch"],
    "fashion": ["fashion", "style", "ootd", "outfit", "streetstyle",
                "fashionblogger", "fashionista", "moda", "lookoftheday",
                "mensfashion", "womensfashion", "trendy", "shopping"],
    "photography": ["photography", "photo", "photographer", "photooftheday",
                    "canon", "nikon", "landscape", "portrait", "streetphotography",
                    "naturephotography", "goldenhour", "composition"],
    "beauty": ["beauty", "makeup", "skincare", "cosmetics", "beautyblogger",
               "mua", "lipstick", "eyeshadow", "foundation", "glam",
               "beautytips", "haircare", "nails"],
    "tech": ["tech", "technology", "programming", "coding", "developer",
             "software", "ai", "machinelearning", "startup", "innovation",
             "digital", "gadgets", "python", "javascript"],
    "business": ["business", "entrepreneur", "hustle", "success", "marketing",
                 "branding", "motivation", "money", "startup", "ceo",
                 "leadership", "growth", "strategy"],
    "nature": ["nature", "landscape", "naturephotography", "outdoors",
               "wildlife", "mountains", "ocean", "forest", "sunset",
               "sunrise", "flowers", "trees", "earth"],
    "art": ["art", "artist", "artwork", "painting", "drawing", "illustration",
            "digitalart", "sketch", "creative", "design", "abstract",
            "contemporaryart", "gallery"],
    "music": ["music", "musician", "song", "singer", "guitar", "hiphop",
              "rap", "producer", "beats", "studio", "concert", "live",
              "newmusic", "band"],
    "sports": ["sports", "football", "soccer", "basketball", "tennis",
               "athlete", "training", "game", "champion", "team",
               "winning", "competition"],
    "pets": ["pets", "dog", "cat", "puppy", "kitten", "dogsofinstagram",
             "catsofinstagram", "petlover", "animals", "cute", "paws"],
    "education": ["education", "learning", "study", "student", "teacher",
                  "knowledge", "school", "university", "course", "online",
                  "skills", "tutorial"],
}

# ─── Caption Templates ────────────────────────────────────────
CAPTION_TEMPLATES = {
    "inspirational": [
        "Believe in the power of {topic} ✨",
        "Every day is a new chance to embrace {topic} 🌟",
        "The journey of {topic} starts with a single step 💫",
        "{topic} is not just a passion, it's a lifestyle 🔥",
        "Dream big. Work hard. Stay focused on {topic} 💪",
    ],
    "casual": [
        "Just vibing with some {topic} 😎",
        "{topic} kinda day 🤙",
        "Can't get enough of {topic} ❤️",
        "This is what {topic} looks like 📸",
        "Living my best {topic} life 🙌",
    ],
    "professional": [
        "Excited to share my latest work on {topic}.",
        "A deep dive into {topic} — thoughts below 👇",
        "The future of {topic} is here, and it's exciting.",
        "Key insights on {topic} that every professional should know.",
        "Exploring new frontiers in {topic}.",
    ],
    "poetic": [
        "In the gentle embrace of {topic}, we find ourselves ✨",
        "Where words fail, {topic} speaks 🎶",
        "Lost in the beauty of {topic} 🌌",
        "A canvas painted with the colors of {topic} 🎨",
        "The whisper of {topic} in the wind 🍃",
    ],
    "funny": [
        "Me: I need to be productive. Also me: *scrolls through {topic}* 😂",
        "If {topic} was a person, we'd be best friends 🤝",
        "Currently accepting applications for {topic} partners 📋😄",
        "My relationship status: committed to {topic} 💍",
        "Adulting is hard, but {topic} makes it better 😅",
    ],
}


class AISuggestAPI:
    """
    AI-powered hashtag & caption suggester.

    Uses caption analysis, niche detection, trend awareness,
    and profile-based optimization. No external AI API needed.
    """

    def __init__(self, client, users_api, hashtags_api=None, hashtag_research_api=None):
        self._client = client
        self._users = users_api
        self._hashtags = hashtags_api
        self._research = hashtag_research_api

    # ═══════════════════════════════════════════════════════════
    # HASHTAGS FROM CAPTION
    # ═══════════════════════════════════════════════════════════

    def hashtags_from_caption(
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
            include_trending: Include trending/popular tags

        Returns:
            dict: {hashtags, niche, confidence, breakdown}
        """
        # Extract keywords from caption
        keywords = self._extract_keywords(caption)

        # Detect niche
        niche, confidence = self._detect_niche(keywords)

        # Build hashtag set
        hashtags = []

        # 1. Niche-specific tags (40%)
        niche_tags = self._get_niche_tags(niche, int(count * 0.4))
        hashtags.extend(niche_tags)

        # 2. Keyword-based tags (30%)
        keyword_tags = self._keywords_to_hashtags(keywords, int(count * 0.3))
        hashtags.extend(keyword_tags)

        # 3. High-engagement universal tags (15%)
        universal = self._get_universal_tags(int(count * 0.15))
        hashtags.extend(universal)

        # 4. Long-tail niche tags (15%)
        longtail = self._get_longtail_tags(keywords, niche, int(count * 0.15))
        hashtags.extend(longtail)

        # Deduplicate and limit
        seen = set()
        unique = []
        for tag in hashtags:
            t = tag.lower().strip()
            if t and t not in seen and len(t) > 1:
                seen.add(t)
                unique.append(t)

        result = {
            "hashtags": unique[:count],
            "niche": niche,
            "confidence": round(confidence, 2),
            "count": min(len(unique), count),
            "breakdown": {
                "niche_specific": len(niche_tags),
                "keyword_based": len(keyword_tags),
                "universal": len(universal),
                "long_tail": len(longtail),
            },
        }
        logger.info(f"🏷️ Suggested {len(unique[:count])} tags | niche={niche} ({confidence:.0%})")
        return result

    # ═══════════════════════════════════════════════════════════
    # HASHTAGS FOR PROFILE
    # ═══════════════════════════════════════════════════════════

    def hashtags_for_profile(
        self,
        username: str,
        count: int = 30,
    ) -> Dict[str, Any]:
        """
        Suggest hashtags based on a user's profile and content.

        Analyzes bio, recent posts, and existing hashtag usage.

        Args:
            username: Target username
            count: Hashtags to suggest

        Returns:
            dict: {hashtags, niche, already_using, new_suggestions}
        """
        user = self._users.get_by_username(username)
        bio = getattr(user, "biography", "") or (user.get("biography", "") if isinstance(user, dict) else "")
        user_id = getattr(user, "pk", None) or (user.get("pk") if isinstance(user, dict) else None)

        # Analyze bio keywords
        bio_keywords = self._extract_keywords(bio)
        niche, conf = self._detect_niche(bio_keywords)

        # Analyze recent posts for existing hashtags
        already_using: Set[str] = set()
        post_keywords: List[str] = []

        if user_id:
            try:
                result = self._client.request(
                    "GET", f"/api/v1/feed/user/{user_id}/",
                    params={"count": "20"},
                )
                if result and isinstance(result, dict):
                    for item in result.get("items", []):
                        cap = item.get("caption", {})
                        text = cap.get("text", "") if isinstance(cap, dict) else str(cap or "")
                        tags = re.findall(r"#(\w+)", text.lower())
                        already_using.update(tags)
                        post_keywords.extend(self._extract_keywords(text))
            except Exception:
                pass

        # Combined niche from bio + posts
        all_keywords = bio_keywords + post_keywords
        if post_keywords:
            niche, conf = self._detect_niche(all_keywords)

        # Get optimal tags
        optimal = self.optimal_set(niche, count=count * 2)
        all_tags = optimal.get("hashtags", [])

        # Separate new vs already using
        new_suggestions = [t for t in all_tags if t not in already_using]

        return {
            "hashtags": new_suggestions[:count],
            "niche": niche,
            "already_using": list(already_using)[:20],
            "new_suggestions": len(new_suggestions[:count]),
            "profile_analyzed": True,
        }

    # ═══════════════════════════════════════════════════════════
    # CAPTION IDEAS
    # ═══════════════════════════════════════════════════════════

    def caption_ideas(
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
        templates = CAPTION_TEMPLATES.get(style, CAPTION_TEMPLATES["casual"])
        captions = [t.format(topic=topic) for t in templates]
        return captions[:count]

    # ═══════════════════════════════════════════════════════════
    # OPTIMAL SET
    # ═══════════════════════════════════════════════════════════

    def optimal_set(
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
        topic_lower = topic.lower().strip("#")

        # Detect niche from topic
        niche, _ = self._detect_niche([topic_lower])

        # Get all available tags
        niche_tags = self._get_niche_tags(niche, 40)
        keyword_tags = self._keywords_to_hashtags([topic_lower], 20)
        longtail = self._get_longtail_tags([topic_lower], niche, 20)
        universal = self._get_universal_tags(10)

        all_tags = list(set(niche_tags + keyword_tags + longtail + universal))

        # Create balanced mix
        easy = int(count * 0.3)
        medium = int(count * 0.4)
        hard = int(count * 0.2)
        popular = count - easy - medium - hard

        selected = []
        # Distribute: longtail (easy) + niche (medium) + keyword (hard) + universal (popular)
        selected.extend(longtail[:easy])
        selected.extend(niche_tags[:medium])
        selected.extend(keyword_tags[:hard])
        selected.extend(universal[:popular])

        # Fill remaining
        for tag in all_tags:
            if tag not in selected and len(selected) < count:
                selected.append(tag)

        unique = list(dict.fromkeys(selected))[:count]

        return {
            "hashtags": unique,
            "topic": topic,
            "niche": niche,
            "count": len(unique),
            "difficulty_mix": {"easy": easy, "medium": medium, "hard": hard, "popular": popular},
        }

    # ═══════════════════════════════════════════════════════════
    # INTERNAL — NLP & ANALYSIS
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        # Remove hashtags, mentions, URLs
        text = re.sub(r"#\w+", "", text)
        text = re.sub(r"@\w+", "", text)
        text = re.sub(r"https?://\S+", "", text)

        # Tokenize and filter
        words = re.findall(r"[a-zA-Z]{3,}", text.lower())

        # Remove stopwords
        stopwords = {
            "the", "and", "for", "are", "but", "not", "you", "all", "can",
            "her", "was", "one", "our", "out", "has", "have", "had", "has",
            "this", "that", "with", "from", "been", "they", "will", "what",
            "when", "make", "like", "just", "over", "such", "take", "than",
            "them", "very", "some", "also", "into", "your", "more", "its",
            "about", "would", "there", "their", "which", "could", "other",
            "these", "then", "than", "each", "where", "those",
        }
        return [w for w in words if w not in stopwords and len(w) > 2]

    @staticmethod
    def _detect_niche(keywords: List[str]) -> tuple:
        """Detect content niche from keywords. Returns (niche_name, confidence)."""
        if not keywords:
            return "general", 0.0

        scores = {}
        keyword_set = set(keywords)

        for niche, niche_tags in NICHE_KEYWORDS.items():
            niche_set = set(niche_tags)
            overlap = keyword_set & niche_set
            # Also check partial matches
            partial = sum(1 for kw in keywords for nt in niche_tags if kw in nt or nt in kw)
            scores[niche] = len(overlap) * 3 + partial

        if not scores or max(scores.values()) == 0:
            return "general", 0.0

        best = max(scores, key=scores.get)
        total = sum(scores.values())
        confidence = scores[best] / max(total, 1)

        return best, min(confidence, 1.0)

    @staticmethod
    def _get_niche_tags(niche: str, count: int) -> List[str]:
        """Get tags for a specific niche."""
        tags = NICHE_KEYWORDS.get(niche, [])
        if not tags:
            # Try partial match
            for key, vals in NICHE_KEYWORDS.items():
                if niche in key or key in niche:
                    tags = vals
                    break
        return tags[:count]

    @staticmethod
    def _keywords_to_hashtags(keywords: List[str], count: int) -> List[str]:
        """Convert keywords to hashtag-style strings."""
        tags = []
        for kw in keywords:
            tags.append(kw)
            tags.append(f"{kw}life")
            tags.append(f"{kw}lover")
            tags.append(f"insta{kw}")
        return list(set(tags))[:count]

    @staticmethod
    def _get_universal_tags(count: int) -> List[str]:
        """High-engagement universal hashtags."""
        universal = [
            "instagood", "photooftheday", "love", "beautiful", "happy",
            "instadaily", "picoftheday", "follow", "like4like", "style",
            "amazing", "bestoftheday", "smile", "instalike", "life",
            "explore", "explorepage", "viral", "trending", "fyp",
            "reels", "instamood", "inspiration", "lifestyle", "goals",
        ]
        return universal[:count]

    @staticmethod
    def _get_longtail_tags(keywords: List[str], niche: str, count: int) -> List[str]:
        """Generate long-tail (less competitive) hashtags."""
        longtail = []
        prefixes = ["daily", "my", "love", "best", "insta"]
        suffixes = ["life", "vibes", "mood", "goals", "gram", "community", "world", "daily"]

        for kw in keywords[:5]:
            for prefix in prefixes:
                longtail.append(f"{prefix}{kw}")
            for suffix in suffixes:
                longtail.append(f"{kw}{suffix}")

        if niche and niche != "general":
            for suffix in suffixes:
                longtail.append(f"{niche}{suffix}")

        return list(set(longtail))[:count]
