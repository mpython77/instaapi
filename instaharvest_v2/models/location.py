"""
Location Models
===============
Instagram location data models.
"""

from typing import Any, Optional
from pydantic import Field

from .base import InstaModel


class Location(InstaModel):
    """Instagram location/place."""
    pk: int = 0
    name: str = ""
    address: str = ""
    city: str = ""
    short_name: str = ""
    lat: Optional[float] = Field(default=None, alias="lat")
    lng: Optional[float] = Field(default=None, alias="lng")
    external_source: str = ""
    facebook_places_id: Optional[int] = None
