"""
Common Models
=============
Shared types used across multiple model modules.
"""

from typing import List, Optional
from pydantic import Field

from .base import InstaModel


class ImageVersion(InstaModel):
    """Single image/video resource URL with dimensions."""
    width: int = 0
    height: int = 0
    url: str = ""


class Pagination(InstaModel):
    """Pagination info for paginated API responses."""
    has_more: bool = False
    next_cursor: Optional[str] = Field(default=None, alias="next_max_id")
    total_count: Optional[int] = None
