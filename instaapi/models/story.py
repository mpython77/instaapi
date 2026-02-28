"""
Story Models
============
Instagram story and highlight data models.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import Field, field_validator

from .base import InstaModel
from .user import UserShort


class StorySticker(InstaModel):
    """Story interactive sticker."""
    type: str = ""  # mention, hashtag, location, poll, quiz, question, link, countdown
    value: str = ""  # sticker content
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


class Story(InstaModel):
    """
    Instagram story item model.

    Fields:
        pk: Story numeric ID
        media_type: 1=photo, 2=video
        taken_at: Story timestamp
        expiring_at: Story expiration time
        user: Story author
        image_url: Story image URL
        video_url: Story video URL (if video)
        duration: Video duration in seconds
        stickers: Interactive stickers
        mentions: Mentioned users
        hashtags: Hashtags in story
        viewer_count: Number of viewers
    """
    pk: int = 0
    id: str = ""
    media_type: int = 1

    # Timing
    taken_at: Optional[datetime] = None
    expiring_at: Optional[datetime] = None

    # Author
    user: Optional[UserShort] = None

    # Resources
    image_url: str = ""
    video_url: str = ""
    duration: float = 0.0

    # Interactive elements
    stickers: List[StorySticker] = Field(default_factory=list)
    mentions: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    locations: List[Dict[str, Any]] = Field(default_factory=list)

    # Stats
    viewer_count: int = 0

    # Flags
    is_video: bool = False

    @field_validator("pk", mode="before")
    @classmethod
    def coerce_pk(cls, v: Any) -> int:
        if v is None:
            return 0
        return int(v)

    @field_validator("taken_at", "expiring_at", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v)
        return v


class Highlight(InstaModel):
    """Instagram highlight (collection of stories)."""
    id: str = ""
    title: str = ""
    media_count: int = 0
    cover_url: str = ""
    created_at: Optional[datetime] = None
    items: List[Story] = Field(default_factory=list)

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v)
        return v
