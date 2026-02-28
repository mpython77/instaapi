"""
Comment Models
==============
Instagram comment data models.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import Field, field_validator

from .base import InstaModel
from .user import UserShort


class Comment(InstaModel):
    """
    Instagram comment model.

    Fields:
        pk: Comment numeric ID
        text: Comment text
        user: Author (UserShort)
        like_count: Number of likes on comment
        reply_count: Number of replies
        created_at: Timestamp
        is_ranked: Instagram ranked this comment
        replies: Nested reply comments
    """
    pk: int = 0
    text: str = ""
    user: Optional[UserShort] = None
    like_count: int = Field(default=0, alias="comment_like_count")
    reply_count: int = Field(default=0, alias="child_comment_count")
    created_at: Optional[datetime] = None
    is_ranked: bool = Field(default=False, alias="is_ranked_comment")
    is_edited: bool = False

    # Nested replies
    replies: List["Comment"] = Field(default_factory=list)

    # Parsed metadata
    mentions: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)

    @field_validator("pk", mode="before")
    @classmethod
    def coerce_pk(cls, v: Any) -> int:
        if v is None:
            return 0
        return int(v)

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v)
        return v

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Comment":
        """Create Comment from API response."""
        import re

        text = data.get("text", "")
        user_data = data.get("user")
        user = UserShort(**user_data) if isinstance(user_data, dict) else None

        # Parse replies
        replies = []
        for reply in data.get("preview_child_comments", []):
            replies.append(Comment.from_api(reply))

        return cls(
            pk=data.get("pk", 0),
            text=text,
            user=user,
            like_count=data.get("comment_like_count", 0),
            reply_count=data.get("child_comment_count", 0),
            created_at=data.get("created_at"),
            is_ranked=data.get("is_ranked_comment", False),
            is_edited=data.get("is_edited", False),
            replies=replies,
            mentions=re.findall(r"@([\w.]+)", text),
            hashtags=re.findall(r"#(\w+)", text),
        )
