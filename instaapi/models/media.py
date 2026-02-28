"""
Media Models
============
Instagram post/media data models.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import Field, field_validator

from .base import InstaModel
from .user import UserShort
from .common import ImageVersion


class Caption(InstaModel):
    """Post caption with parsed metadata."""
    text: str = ""
    pk: int = 0
    created_at: Optional[datetime] = None
    user: Optional[UserShort] = None

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v)
        return v


class Media(InstaModel):
    """
    Full media (post) model.

    Fields:
        pk: Media numeric ID
        code: URL shortcode (e.g. "DVDk2dSjcq_")
        media_type: 1=photo, 2=video, 8=carousel
        caption_text: Post caption text
        like_count: Number of likes
        comment_count: Number of comments
        play_count: Video play count (video/reel only)
        view_count: View count
        taken_at: Post timestamp
        user: Author (UserShort)
        image_versions: Available image resolutions
        video_versions: Available video resolutions
        carousel_media: Child items (carousel only)
        location: Location data (if tagged)
        is_video: True if video/reel
        is_carousel: True if carousel/album
    """
    # Identity
    pk: int = Field(default=0)
    id: str = ""
    code: str = ""
    media_type: int = 1

    # Content
    caption_text: str = ""
    caption: Optional[Caption] = None

    # Counters
    like_count: int = 0
    comment_count: int = 0
    play_count: int = 0
    view_count: int = 0
    reshare_count: int = 0

    # Timing
    taken_at: Optional[datetime] = None

    # Author
    user: Optional[UserShort] = None

    # Resources
    image_versions: List[ImageVersion] = Field(default_factory=list)
    video_versions: List[ImageVersion] = Field(default_factory=list)

    # Carousel
    carousel_media: List["Media"] = Field(default_factory=list)
    carousel_media_count: int = 0

    # Location
    location: Optional[Dict[str, Any]] = None

    # Flags
    has_liked: bool = False
    has_saved: bool = False

    # Music
    music_title: str = ""
    music_artist: str = ""
    music_duration_ms: int = 0
    music_cover_url: str = ""

    # Top likers
    top_likers: List[str] = Field(default_factory=list)

    # Coauthors (collab posts)
    coauthor_producers: List[UserShort] = Field(default_factory=list)

    # Tagged users (usertags)
    tagged_users: List[UserShort] = Field(default_factory=list)

    # Additional info
    accessibility_caption: str = ""
    product_type: str = ""  # feed, clips, carousel_container
    is_paid_partnership: bool = False
    owner_username: str = ""
    owner_full_name: str = ""

    @field_validator("pk", mode="before")
    @classmethod
    def coerce_pk(cls, v: Any) -> int:
        if v is None:
            return 0
        return int(v)

    @field_validator("taken_at", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v)
        return v

    @property
    def is_video(self) -> bool:
        return self.media_type == 2

    @property
    def is_carousel(self) -> bool:
        return self.media_type == 8

    @property
    def is_photo(self) -> bool:
        return self.media_type == 1

    @property
    def url(self) -> str:
        """Instagram post URL."""
        if self.code:
            return f"https://www.instagram.com/p/{self.code}/"
        return ""

    @property
    def best_image_url(self) -> str:
        """Highest resolution image URL."""
        if self.image_versions:
            return max(self.image_versions, key=lambda x: x.width).url
        return ""

    @property
    def best_video_url(self) -> str:
        """Highest resolution video URL."""
        if self.video_versions:
            return max(self.video_versions, key=lambda x: x.width).url
        return ""

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Media":
        """Create Media from /media/{id}/info/ or feed response."""
        # Parse caption
        caption_data = data.get("caption")
        caption_text = ""
        caption_obj = None
        if isinstance(caption_data, dict):
            caption_text = caption_data.get("text", "")
            caption_obj = Caption(
                text=caption_text,
                pk=caption_data.get("pk", 0),
                created_at=caption_data.get("created_at"),
                user=UserShort(**caption_data["user"]) if caption_data.get("user") else None,
            )
        elif isinstance(caption_data, str):
            caption_text = caption_data

        # Parse images
        img_versions = []
        img_v2 = data.get("image_versions2", {})
        for candidate in img_v2.get("candidates", []):
            img_versions.append(ImageVersion(
                width=candidate.get("width", 0),
                height=candidate.get("height", 0),
                url=candidate.get("url", ""),
            ))

        # Parse videos
        vid_versions = []
        for vid in data.get("video_versions", []):
            vid_versions.append(ImageVersion(
                width=vid.get("width", 0),
                height=vid.get("height", 0),
                url=vid.get("url", ""),
            ))

        # Parse carousel
        carousel = []
        for item in data.get("carousel_media", []):
            carousel.append(Media.from_api(item))

        # Parse user
        user_data = data.get("user")
        user = UserShort(**user_data) if isinstance(user_data, dict) else None

        # Parse music
        music_meta = data.get("music_metadata")
        music_title = ""
        music_artist = ""
        music_duration_ms = 0
        music_cover_url = ""
        if isinstance(music_meta, dict):
            music_info = music_meta.get("music_info", {})
            asset = music_info.get("music_asset_info", {}) if isinstance(music_info, dict) else {}
            music_title = asset.get("title", "")
            music_artist = asset.get("display_artist", "")
            music_duration_ms = asset.get("duration_in_ms", 0)
            music_cover_url = asset.get("cover_artwork_uri", "")

        # Top likers
        top_likers = [
            u.get("username", "") for u in data.get("facepile_top_likers", [])
            if isinstance(u, dict)
        ]

        # Coauthor producers (collab posts)
        coauthors = []
        for coauth in data.get("coauthor_producers", []):
            if isinstance(coauth, dict) and coauth.get("username"):
                try:
                    coauthors.append(UserShort(**coauth))
                except Exception:
                    pass

        # Tagged users (usertags)
        tagged = []
        usertags_data = data.get("usertags", {})
        if isinstance(usertags_data, dict):
            for tag_item in usertags_data.get("in", []):
                tag_user = tag_item.get("user", {})
                if isinstance(tag_user, dict) and tag_user.get("username"):
                    try:
                        tagged.append(UserShort(**tag_user))
                    except Exception:
                        pass

        # Owner info
        owner_data = data.get("owner", {})
        owner_username = ""
        owner_full_name = ""
        if isinstance(owner_data, dict):
            owner_username = owner_data.get("username", "")
            owner_full_name = owner_data.get("full_name", "")

        return cls(
            pk=data.get("pk", 0),
            id=data.get("id", ""),
            code=data.get("code", ""),
            media_type=data.get("media_type", 1),
            caption_text=caption_text,
            caption=caption_obj,
            like_count=data.get("like_count", 0),
            comment_count=data.get("comment_count", 0),
            play_count=data.get("play_count", 0) or data.get("view_count", 0),
            view_count=data.get("view_count", 0),
            reshare_count=data.get("reshare_count", 0),
            taken_at=data.get("taken_at"),
            user=user,
            image_versions=img_versions,
            video_versions=vid_versions,
            carousel_media=carousel,
            carousel_media_count=data.get("carousel_media_count", len(carousel)),
            location=data.get("location"),
            has_liked=data.get("has_liked", False),
            has_saved=data.get("has_viewer_saved", False),
            music_title=music_title,
            music_artist=music_artist,
            music_duration_ms=music_duration_ms,
            music_cover_url=music_cover_url,
            top_likers=top_likers,
            coauthor_producers=coauthors,
            tagged_users=tagged,
            accessibility_caption=data.get("accessibility_caption", ""),
            product_type=data.get("product_type", ""),
            is_paid_partnership=data.get("is_paid_partnership", False),
            owner_username=owner_username,
            owner_full_name=owner_full_name,
        )
