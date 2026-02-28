"""
Direct Message Models
=====================
Instagram DM thread and message data models.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import Field, field_validator

from .base import InstaModel
from .user import UserShort


class DirectMessage(InstaModel):
    """Single DM message."""
    item_id: str = ""
    item_type: str = ""  # text, media, link, profile, reaction, etc.
    text: str = ""
    timestamp: Optional[datetime] = None
    user_id: int = 0
    is_sent_by_viewer: bool = False

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            # Instagram DM timestamps are in microseconds
            if v > 1e15:
                v = v / 1_000_000
            return datetime.fromtimestamp(v)
        return v


class DirectThread(InstaModel):
    """DM conversation thread."""
    thread_id: str = ""
    thread_title: str = ""
    users: List[UserShort] = Field(default_factory=list)
    items: List[DirectMessage] = Field(default_factory=list)
    is_group: bool = False
    is_muted: bool = Field(default=False, alias="muted")
    has_older: bool = False
    last_activity_at: Optional[datetime] = None
    unread_count: int = Field(default=0, alias="read_state")

    @field_validator("last_activity_at", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            if v > 1e15:
                v = v / 1_000_000
            return datetime.fromtimestamp(v)
        return v
