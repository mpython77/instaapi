"""
Base Model
==========
Shared configuration and utilities for all instaharvest_v2 models.
"""

from pydantic import BaseModel, ConfigDict
from typing import Any, Dict


class InstaModel(BaseModel):
    """
    Base model for all Instagram data models.

    Features:
        - extra="allow": unknown Instagram fields are preserved, not discarded
        - populate_by_name=True: fields can be set by name or alias
        - Dict-like access: model["key"] works for backward compatibility
        - .to_dict(): convert back to plain dict
    """

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        from_attributes=True,
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to plain dict (backward compatibility)."""
        return self.model_dump(by_alias=False, exclude_none=True)

    def __getitem__(self, key: str) -> Any:
        """Dict-like access: model['field_name']."""
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like .get() method."""
        return getattr(self, key, default)
