"""
Comment Manager
================
Filter, auto-reply, sentiment analysis, spam detection.

Usage:
    ig = Instagram.from_env(".env")

    # Auto reply to comments with keyword
    ig.comment_manager.auto_reply(media_id, keyword="price", reply="DM us! 💬")

    # Get and filter comments
    comments = ig.comment_manager.get_comments(media_id, sort="top")

    # Delete spam comments
    ig.comment_manager.delete_spam(media_id)

    # Bulk reply
    ig.comment_manager.bulk_reply(media_id, reply="Thanks! ❤️", max_count=20)

    # Sentiment analysis
    analysis = ig.comment_manager.sentiment(media_id)
"""

import logging
import re
import time
import random
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger("instaharvest_v2.comment_manager")

# ─── Built-in Spam Patterns ──────────────────────────────────
SPAM_PATTERNS = [
    r"follow\s*(me|back|4follow)",
    r"f4f|l4l|s4s",
    r"check\s*(my|out)\s*(profile|page|bio|link)",
    r"(dm|message)\s*me\s*(for|to)",
    r"free\s*(followers|likes|money)",
    r"(earn|make)\s*\$?\d+\s*(daily|per\s*day|online)",
    r"click\s*(the|my)?\s*link",
    r"go\s*to\s*(my|the)?\s*(bio|profile|link)",
    r"(www\.|https?://|bit\.ly|t\.co)\S+",
    r"🔥{3,}|❤️{5,}",
]

# ─── Sentiment Keywords ─────────────────────────────────────
POSITIVE_WORDS = {
    "love", "amazing", "beautiful", "great", "awesome", "perfect", "best",
    "wonderful", "fantastic", "incredible", "stunning", "gorgeous", "excellent",
    "brilliant", "superb", "cute", "adorable", "nice", "cool", "wow",
    "fire", "lit", "goat", "king", "queen", "legend", "inspiration",
}

NEGATIVE_WORDS = {
    "hate", "ugly", "bad", "worst", "terrible", "horrible", "disgusting",
    "awful", "pathetic", "stupid", "fake", "trash", "garbage", "boring",
    "overrated", "cringe", "lame", "sucks", "disappointing",
}


class CommentManagerAPI:
    """
    Comment management: filter, reply, spam detection, sentiment.

    Composes: MediaAPI, client direct requests.
    """

    def __init__(self, client, media_api):
        self._client = client
        self._media = media_api
        self._spam_patterns = [re.compile(p, re.IGNORECASE) for p in SPAM_PATTERNS]

    # ═══════════════════════════════════════════════════════════
    # GET COMMENTS
    # ═══════════════════════════════════════════════════════════

    def get_comments(
        self,
        media_id,
        count: int = 50,
        sort: str = "newest",
    ) -> Dict[str, Any]:
        """
        Get comments with metadata.

        Args:
            media_id: Post media ID
            count: Max comments to fetch
            sort: 'newest', 'oldest', 'top'

        Returns:
            dict: {comments, count, has_more}
        """
        all_comments: list = []
        cursor = None

        while len(all_comments) < count:
            try:
                params = {"count": str(min(count - len(all_comments), 50))}
                if cursor:
                    params["min_id"] = cursor
                result = self._client.request(
                    "GET", f"/api/v1/media/{media_id}/comments/",
                    params=params,
                )
            except Exception as e:
                logger.debug(f"Comments fetch error: {e}")
                break

            if not result or not isinstance(result, dict):
                break

            comments = result.get("comments", [])
            if not comments:
                break

            for c in comments:
                all_comments.append({
                    "pk": c.get("pk"),
                    "text": c.get("text", ""),
                    "username": c.get("user", {}).get("username", ""),
                    "user_id": c.get("user", {}).get("pk"),
                    "likes": c.get("comment_like_count", 0),
                    "created_at": c.get("created_at", 0),
                    "is_spam": self._is_spam(c.get("text", "")),
                    "sentiment": self._quick_sentiment(c.get("text", "")),
                })

            cursor = result.get("next_min_id")
            if not cursor or not result.get("has_more_comments", False):
                break

        # Sort
        if sort == "top":
            all_comments.sort(key=lambda c: c.get("likes", 0), reverse=True)
        elif sort == "oldest":
            all_comments.sort(key=lambda c: c.get("created_at", 0))

        return {
            "comments": all_comments[:count],
            "count": len(all_comments[:count]),
            "has_more": cursor is not None,
        }

    # ═══════════════════════════════════════════════════════════
    # AUTO REPLY
    # ═══════════════════════════════════════════════════════════

    def auto_reply(
        self,
        media_id,
        keyword: str = "",
        reply: str = "",
        max_count: int = 20,
        skip_own: bool = True,
        delay: tuple = (3, 8),
    ) -> Dict[str, Any]:
        """
        Auto-reply to comments containing a keyword.

        Args:
            media_id: Post media ID
            keyword: Keyword to match (empty = reply to all)
            reply: Reply text. Use {username} for commenter's name
            max_count: Max replies
            skip_own: Skip own comments
            delay: (min, max) seconds between replies

        Returns:
            dict: {replied, skipped, errors}
        """
        comments = self.get_comments(media_id, count=100)
        replied = 0
        skipped = 0
        errors = 0

        for c in comments.get("comments", []):
            if replied >= max_count:
                break

            text = c.get("text", "").lower()
            username = c.get("username", "")

            # Keyword filter
            if keyword and keyword.lower() not in text:
                skipped += 1
                continue

            # Skip spam
            if c.get("is_spam"):
                skipped += 1
                continue

            # Build reply
            actual_reply = reply.replace("{username}", f"@{username}")
            comment_pk = c.get("pk")

            try:
                self._client.request(
                    "POST", f"/api/v1/media/{media_id}/comment/",
                    data={
                        "comment_text": actual_reply,
                        "replied_to_comment_id": str(comment_pk) if comment_pk else "",
                    },
                )
                replied += 1
                logger.debug(f"💬 Replied to @{username}: {actual_reply[:50]}")
            except Exception as e:
                errors += 1
                logger.debug(f"Reply error: {e}")

            time.sleep(random.uniform(delay[0], delay[1]))

        logger.info(f"💬 Auto-reply: {replied} sent, {skipped} skipped, {errors} errors")
        return {"replied": replied, "skipped": skipped, "errors": errors}

    # ═══════════════════════════════════════════════════════════
    # BULK REPLY
    # ═══════════════════════════════════════════════════════════

    def bulk_reply(
        self,
        media_id,
        reply: str,
        max_count: int = 20,
        skip_spam: bool = True,
        delay: tuple = (3, 8),
    ) -> Dict[str, Any]:
        """
        Reply to all recent comments.

        Args:
            media_id: Post media ID
            reply: Reply text ({username} supported)
            max_count: Max replies
            skip_spam: Skip detected spam
            delay: Delay range

        Returns:
            dict: {replied, skipped}
        """
        return self.auto_reply(
            media_id, keyword="", reply=reply,
            max_count=max_count, delay=delay,
        )

    # ═══════════════════════════════════════════════════════════
    # DELETE SPAM
    # ═══════════════════════════════════════════════════════════

    def delete_spam(
        self,
        media_id,
        max_delete: int = 50,
        custom_patterns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Detect and delete spam comments.

        Args:
            media_id: Post media ID
            max_delete: Max spam comments to delete
            custom_patterns: Extra regex patterns to match spam

        Returns:
            dict: {deleted, scanned, spam_users}
        """
        extra_patterns = []
        if custom_patterns:
            extra_patterns = [re.compile(p, re.IGNORECASE) for p in custom_patterns]

        comments = self.get_comments(media_id, count=200, sort="newest")
        deleted = 0
        spam_users = set()

        for c in comments.get("comments", []):
            if deleted >= max_delete:
                break

            text = c.get("text", "")
            is_spam = self._is_spam(text)

            # Also check custom patterns
            if not is_spam and extra_patterns:
                for p in extra_patterns:
                    if p.search(text):
                        is_spam = True
                        break

            if is_spam:
                comment_pk = c.get("pk")
                try:
                    self._client.request(
                        "POST", f"/api/v1/media/{media_id}/comment/{comment_pk}/delete/",
                    )
                    deleted += 1
                    spam_users.add(c.get("username", ""))
                except Exception:
                    pass
                time.sleep(random.uniform(1, 3))

        logger.info(f"🗑️ Spam cleanup: {deleted} deleted from {len(comments.get('comments', []))} scanned")
        return {
            "deleted": deleted,
            "scanned": len(comments.get("comments", [])),
            "spam_users": list(spam_users),
        }

    # ═══════════════════════════════════════════════════════════
    # SENTIMENT ANALYSIS
    # ═══════════════════════════════════════════════════════════

    def sentiment(
        self,
        media_id,
        count: int = 100,
    ) -> Dict[str, Any]:
        """
        Sentiment analysis of post comments.

        Args:
            media_id: Post media ID
            count: Comments to analyze

        Returns:
            dict: {positive, negative, neutral, overall, top_positive, top_negative}
        """
        comments = self.get_comments(media_id, count=count)
        items = comments.get("comments", [])

        positive = []
        negative = []
        neutral = []

        for c in items:
            s = c.get("sentiment", "neutral")
            if s == "positive":
                positive.append(c)
            elif s == "negative":
                negative.append(c)
            else:
                neutral.append(c)

        total = len(items) or 1
        pos_pct = len(positive) / total * 100
        neg_pct = len(negative) / total * 100

        if pos_pct >= 60:
            overall = "very_positive"
        elif pos_pct >= 40:
            overall = "positive"
        elif neg_pct >= 40:
            overall = "negative"
        else:
            overall = "neutral"

        return {
            "total_analyzed": len(items),
            "positive": len(positive),
            "negative": len(negative),
            "neutral": len(neutral),
            "positive_pct": round(pos_pct, 1),
            "negative_pct": round(neg_pct, 1),
            "overall": overall,
            "top_positive": sorted(positive, key=lambda c: c.get("likes", 0), reverse=True)[:3],
            "top_negative": sorted(negative, key=lambda c: c.get("likes", 0), reverse=True)[:3],
        }

    # ═══════════════════════════════════════════════════════════
    # FILTER COMMENTS
    # ═══════════════════════════════════════════════════════════

    def filter_comments(
        self,
        media_id,
        keyword: str = "",
        sentiment_filter: str = "",
        min_likes: int = 0,
        exclude_spam: bool = True,
    ) -> List[Dict]:
        """
        Filter comments by criteria.

        Args:
            media_id: Post ID
            keyword: Include only comments with this keyword
            sentiment_filter: 'positive', 'negative', 'neutral'
            min_likes: Minimum likes on comment
            exclude_spam: Skip spam comments

        Returns:
            Filtered list of comments
        """
        comments = self.get_comments(media_id, count=200)
        filtered = []

        for c in comments.get("comments", []):
            if exclude_spam and c.get("is_spam"):
                continue
            if keyword and keyword.lower() not in c.get("text", "").lower():
                continue
            if sentiment_filter and c.get("sentiment") != sentiment_filter:
                continue
            if c.get("likes", 0) < min_likes:
                continue
            filtered.append(c)

        return filtered

    # ═══════════════════════════════════════════════════════════
    # INTERNAL
    # ═══════════════════════════════════════════════════════════

    def _is_spam(self, text: str) -> bool:
        """Detect if comment is spam."""
        if not text:
            return False
        for pattern in self._spam_patterns:
            if pattern.search(text):
                return True
        # Very short repetitive (e.g., "🔥🔥🔥🔥🔥")
        if len(set(text)) <= 2 and len(text) > 3:
            return True
        return False

    @staticmethod
    def _quick_sentiment(text: str) -> str:
        """Quick sentiment analysis using keyword matching."""
        if not text:
            return "neutral"
        words = set(re.findall(r"[a-zA-Z]+", text.lower()))
        emojis = re.findall(r"[❤️💕💖😍🥰🔥💯👏🙌✨💪🏆👑⭐😊😎]", text)

        pos = len(words & POSITIVE_WORDS) + len(emojis)
        neg = len(words & NEGATIVE_WORDS)
        neg_emojis = len(re.findall(r"[😡🤮👎💩😤😠🤢]", text))
        neg += neg_emojis

        if pos > neg:
            return "positive"
        elif neg > pos:
            return "negative"
        return "neutral"
