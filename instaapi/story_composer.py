"""
Story Composer
==============
Builder-pattern story creation with text, mentions, stickers.

Usage:
    story = StoryComposer(ig) \
        .image("photo.jpg") \
        .text("Hello!", position=(0.5, 0.5)) \
        .mention("@username", position=(0.5, 0.8)) \
        .hashtag("#travel") \
        .location(location_id) \
        .link("https://example.com") \
        .build()

    result = story.publish()
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("instaapi.story_composer")


@dataclass
class StoryElement:
    """Single story element (text, mention, hashtag, etc)."""

    type: str  # "text", "mention", "hashtag", "location", "link", "poll", "question"
    content: str = ""
    position: Tuple[float, float] = (0.5, 0.5)  # (x, y) normalized 0-1
    scale: float = 1.0
    rotation: float = 0.0
    font_size: int = 24
    color: str = "#ffffff"
    background_color: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StoryDraft:
    """Compiled story ready for publishing."""

    image_path: Optional[str] = None
    video_path: Optional[str] = None
    elements: List[StoryElement] = field(default_factory=list)
    _ig: Any = field(default=None, repr=False)

    def publish(self) -> dict:
        """
        Publish the story to Instagram.

        Returns:
            API response dict
        """
        if not self._ig:
            raise ValueError("No Instagram instance — use StoryComposer(ig)")

        # Build upload kwargs
        upload_data = self._build_upload_data()

        if self.image_path:
            return self._ig.upload.upload_story_photo(
                photo_path=self.image_path,
                **upload_data,
            )
        elif self.video_path:
            return self._ig.upload.upload_story_video(
                video_path=self.video_path,
                **upload_data,
            )
        else:
            raise ValueError("No image or video set — use .image() or .video()")

    def _build_upload_data(self) -> dict:
        """Build story_sticker_ids and reel_share data."""
        data = {}
        stickers = []
        mentions = []
        hashtags = []
        links = []

        for el in self.elements:
            if el.type == "mention":
                mentions.append({
                    "user_id": el.extra.get("user_id", ""),
                    "username": el.content.lstrip("@"),
                    "x": el.position[0],
                    "y": el.position[1],
                    "width": el.extra.get("width", 0.64),
                    "height": el.extra.get("height", 0.125),
                    "rotation": el.rotation,
                })
            elif el.type == "hashtag":
                hashtags.append({
                    "tag_name": el.content.lstrip("#"),
                    "x": el.position[0],
                    "y": el.position[1],
                    "width": el.extra.get("width", 0.5),
                    "height": el.extra.get("height", 0.1),
                })
            elif el.type == "location":
                data["location_id"] = el.extra.get("location_id", "")
                stickers.append({
                    "type": "location",
                    "location_id": el.extra.get("location_id", ""),
                    "x": el.position[0],
                    "y": el.position[1],
                })
            elif el.type == "link":
                links.append({
                    "url": el.content,
                    "x": el.position[0],
                    "y": el.position[1],
                })
            elif el.type == "poll":
                stickers.append({
                    "type": "poll",
                    "question": el.content,
                    "tallies": el.extra.get("options", ["Yes", "No"]),
                    "x": el.position[0],
                    "y": el.position[1],
                })
            elif el.type == "question":
                stickers.append({
                    "type": "question",
                    "question": el.content,
                    "x": el.position[0],
                    "y": el.position[1],
                })

        if mentions:
            data["reel_mentions"] = json.dumps(mentions)
        if hashtags:
            data["story_hashtags"] = json.dumps(hashtags)
        if links:
            data["story_cta"] = json.dumps([{"links": links}])
        if stickers:
            data["story_sticker_ids"] = json.dumps(
                [s.get("type", "custom") for s in stickers]
            )
            data["story_stickers"] = json.dumps(stickers)

        return data

    def to_dict(self) -> dict:
        """Export story as dict for debugging."""
        return {
            "image": self.image_path,
            "video": self.video_path,
            "elements": [
                {
                    "type": e.type,
                    "content": e.content,
                    "position": e.position,
                    "font_size": e.font_size,
                    "color": e.color,
                }
                for e in self.elements
            ],
        }


class StoryComposer:
    """
    Builder-pattern story creator.

    Usage:
        story = StoryComposer(ig) \
            .image("sunset.jpg") \
            .text("Beautiful day! 🌅", position=(0.5, 0.3)) \
            .mention("@friend", position=(0.5, 0.7)) \
            .hashtag("#sunset") \
            .build()

        result = story.publish()
    """

    def __init__(self, ig=None):
        self._ig = ig
        self._image_path: Optional[str] = None
        self._video_path: Optional[str] = None
        self._elements: List[StoryElement] = []

    def image(self, path: str) -> "StoryComposer":
        """Set story background image."""
        self._image_path = path
        return self

    def video(self, path: str) -> "StoryComposer":
        """Set story background video."""
        self._video_path = path
        return self

    def text(
        self,
        content: str,
        position: Tuple[float, float] = (0.5, 0.5),
        font_size: int = 24,
        color: str = "#ffffff",
        background_color: str = "",
    ) -> "StoryComposer":
        """Add text overlay."""
        self._elements.append(StoryElement(
            type="text",
            content=content,
            position=position,
            font_size=font_size,
            color=color,
            background_color=background_color,
        ))
        return self

    def mention(
        self,
        username: str,
        position: Tuple[float, float] = (0.5, 0.8),
        user_id: str = "",
    ) -> "StoryComposer":
        """Add @mention sticker."""
        self._elements.append(StoryElement(
            type="mention",
            content=username,
            position=position,
            extra={"user_id": user_id},
        ))
        return self

    def hashtag(
        self,
        tag: str,
        position: Tuple[float, float] = (0.5, 0.9),
    ) -> "StoryComposer":
        """Add #hashtag sticker."""
        self._elements.append(StoryElement(
            type="hashtag",
            content=tag,
            position=position,
        ))
        return self

    def location(
        self,
        location_id: str,
        position: Tuple[float, float] = (0.5, 0.1),
    ) -> "StoryComposer":
        """Add location sticker."""
        self._elements.append(StoryElement(
            type="location",
            content="",
            position=position,
            extra={"location_id": location_id},
        ))
        return self

    def link(
        self,
        url: str,
        position: Tuple[float, float] = (0.5, 0.95),
    ) -> "StoryComposer":
        """Add link sticker (swipe up / link sticker)."""
        self._elements.append(StoryElement(
            type="link",
            content=url,
            position=position,
        ))
        return self

    def poll(
        self,
        question: str,
        options: List[str] = None,
        position: Tuple[float, float] = (0.5, 0.6),
    ) -> "StoryComposer":
        """Add poll sticker."""
        self._elements.append(StoryElement(
            type="poll",
            content=question,
            position=position,
            extra={"options": options or ["Yes", "No"]},
        ))
        return self

    def question(
        self,
        question: str,
        position: Tuple[float, float] = (0.5, 0.5),
    ) -> "StoryComposer":
        """Add question sticker (ask me anything)."""
        self._elements.append(StoryElement(
            type="question",
            content=question,
            position=position,
        ))
        return self

    def build(self) -> StoryDraft:
        """
        Compile story into StoryDraft ready for publishing.

        Returns:
            StoryDraft instance with .publish() method
        """
        draft = StoryDraft(
            image_path=self._image_path,
            video_path=self._video_path,
            elements=list(self._elements),
            _ig=self._ig,
        )
        logger.debug(f"Story built: {len(self._elements)} elements")
        return draft

    def __repr__(self) -> str:
        media = self._image_path or self._video_path or "no media"
        return f"StoryComposer({media}, {len(self._elements)} elements)"
