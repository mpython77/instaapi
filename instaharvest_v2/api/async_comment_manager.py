"""
Async Comment Manager
======================
Async version of CommentManagerAPI. Full feature parity.
"""

import asyncio
import logging
import random
import re
from typing import Any, Dict, List, Optional

from .comment_manager import SPAM_PATTERNS, POSITIVE_WORDS, NEGATIVE_WORDS

logger = logging.getLogger("instaharvest_v2.comment_manager")


class AsyncCommentManagerAPI:
    """Async comment management: filter, reply, spam detection, sentiment."""

    def __init__(self, client, media_api):
        self._client = client
        self._media = media_api

    async def get_comments(self, media_id, count: int = 50, sort: str = "newest") -> Dict[str, Any]:
        """Get comments with metadata."""
        try:
            result = await self._media.get_comments(media_id, count=count)
            comments = result.get("comments", []) if isinstance(result, dict) else []
            enriched = []
            for c in comments:
                text = c.get("text", "")
                enriched.append({
                    "id": c.get("pk"), "text": text,
                    "username": c.get("user", {}).get("username", ""),
                    "user_id": c.get("user", {}).get("pk"),
                    "likes": c.get("comment_like_count", 0),
                    "created_at": c.get("created_at", 0),
                    "is_spam": self._is_spam(text),
                    "sentiment": self._quick_sentiment(text),
                })
            if sort == "oldest":
                enriched.sort(key=lambda x: x.get("created_at", 0))
            elif sort == "top":
                enriched.sort(key=lambda x: x.get("likes", 0), reverse=True)
            else:
                enriched.sort(key=lambda x: x.get("created_at", 0), reverse=True)
            return {"comments": enriched[:count], "count": len(enriched), "has_more": result.get("has_more_comments", False) if isinstance(result, dict) else False}
        except Exception as e:
            return {"comments": [], "count": 0, "error": str(e)}

    async def auto_reply(self, media_id, keyword: str = "", reply: str = "", max_count: int = 20, skip_own: bool = True, delay: tuple = (3, 8)) -> Dict[str, Any]:
        """Auto-reply to comments containing a keyword."""
        result = await self.get_comments(media_id, count=100)
        comments = result.get("comments", [])
        replied = skipped = errors = 0
        sm = getattr(self._client, "_session_mgr", None)
        my_id = str(getattr(sm.get_session(), "ds_user_id", "")) if sm else ""
        for comment in comments:
            if replied >= max_count:
                break
            if skip_own and str(comment.get("user_id")) == my_id:
                skipped += 1; continue
            if keyword and keyword.lower() not in comment.get("text", "").lower():
                skipped += 1; continue
            reply_text = reply.replace("{username}", f"@{comment.get('username', '')}")
            try:
                await self._media.comment(media_id, reply_text, reply_to_comment_id=comment.get("id"))
                replied += 1
                await asyncio.sleep(random.uniform(*delay))
            except Exception:
                errors += 1
        return {"replied": replied, "skipped": skipped, "errors": errors}

    async def delete_spam(self, media_id, max_delete: int = 50, custom_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """Detect and delete spam comments."""
        result = await self.get_comments(media_id, count=200)
        comments = result.get("comments", [])
        deleted = 0; spam_users = set()
        extra = [re.compile(p, re.IGNORECASE) for p in (custom_patterns or [])]
        for comment in comments:
            if deleted >= max_delete:
                break
            text = comment.get("text", "")
            is_spam = self._is_spam(text) or any(p.search(text) for p in extra)
            if is_spam:
                try:
                    await self._media.delete_comment(media_id, comment.get("id"))
                    deleted += 1; spam_users.add(comment.get("username", ""))
                except Exception:
                    pass
        return {"deleted": deleted, "scanned": len(comments), "spam_users": list(spam_users)}

    async def sentiment(self, media_id, count: int = 100) -> Dict[str, Any]:
        """Sentiment analysis of post comments."""
        result = await self.get_comments(media_id, count=count)
        comments = result.get("comments", [])
        pos = neg = neu = 0
        for c in comments:
            s = c.get("sentiment", "neutral")
            if s == "positive": pos += 1
            elif s == "negative": neg += 1
            else: neu += 1
        total = len(comments) or 1
        return {"positive": pos, "negative": neg, "neutral": neu, "positive_rate": round(pos/total*100, 1), "overall": "positive" if pos > neg else ("negative" if neg > pos else "neutral"), "analyzed": len(comments)}

    def _is_spam(self, text: str) -> bool:
        if not text: return False
        return any(re.search(p, text, re.IGNORECASE) for p in SPAM_PATTERNS)

    @staticmethod
    def _quick_sentiment(text: str) -> str:
        if not text: return "neutral"
        words = set(text.lower().split())
        pos = len(words & POSITIVE_WORDS); neg = len(words & NEGATIVE_WORDS)
        return "positive" if pos > neg else ("negative" if neg > pos else "neutral")
