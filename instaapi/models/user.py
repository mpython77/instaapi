"""
User Models
===========
Instagram user data models.
Handles both web_profile_info and user/info/ API response formats.
"""

from typing import Any, Dict, List, Optional
from pydantic import Field, field_validator

from .base import InstaModel


class Contact(InstaModel):
    """User contact information (business/creator accounts)."""
    email: str = ""
    phone: str = ""
    phone_country_code: str = ""
    city: str = ""
    address: str = ""


class BioParsed(InstaModel):
    """Parsed bio data with mentions, hashtags, URLs."""
    biography: str = ""
    bio_mentions: List[str] = Field(default_factory=list)
    bio_hashtags: List[str] = Field(default_factory=list)
    bio_urls: List[str] = Field(default_factory=list)
    bio_emails: List[str] = Field(default_factory=list)
    bio_phones: List[str] = Field(default_factory=list)
    bio_links: List[Any] = Field(default_factory=list)
    bio_entities: List[Dict[str, Any]] = Field(default_factory=list)


class UserShort(InstaModel):
    """
    Compact user model — used in likers, followers, comments, etc.

    Fields:
        pk: User numeric ID
        username: Instagram handle
        full_name: Display name
        is_verified: Blue badge
        is_private: Private account
        profile_pic_url: Profile picture URL
    """
    pk: int = Field(default=0, alias="pk")
    username: str = ""
    full_name: str = ""
    is_verified: bool = False
    is_private: bool = False
    profile_pic_url: str = ""

    @field_validator("pk", mode="before")
    @classmethod
    def coerce_pk(cls, v: Any) -> int:
        """Handle pk coming as string or from 'id' field."""
        if v is None:
            return 0
        return int(v)


class User(InstaModel):
    """
    Full user profile model.
    Normalizes differences between web_profile_info and user/info/ responses.

    Fields:
        pk: User numeric ID
        username: Instagram handle
        full_name: Display name
        biography: Bio text
        is_verified, is_private, is_business, is_professional
        followers: Follower count
        following: Following count
        posts_count: Total media count
        profile_pic_url: Standard profile pic
        profile_pic_url_hd: HD profile pic
        external_url: Website link
        category: Account category
        contact: Contact info (email, phone, city)
        bio: Parsed bio data
        highlight_count, pronouns, fbid
        mutual_followers_count
    """
    # Identity
    pk: int = Field(default=0, alias="pk")
    username: str = ""
    full_name: str = ""

    # Flags
    is_verified: bool = False
    is_private: bool = False
    is_business: bool = Field(default=False, alias="is_business_account")
    is_professional: bool = Field(default=False, alias="is_professional_account")

    # Bio
    biography: str = ""
    external_url: str = ""
    category: str = ""

    @field_validator("biography", "external_url", "category", "profile_pic_url", "profile_pic_url_hd", "username", "full_name", mode="before")
    @classmethod
    def coerce_none_str(cls, v: Any) -> str:
        """Instagram sometimes returns null for string fields."""
        if v is None:
            return ""
        return str(v)

    # Counters (handle both web and mobile API formats)
    followers: int = 0
    following: int = 0
    posts_count: int = Field(default=0, alias="media_count")

    # Images
    profile_pic_url: str = ""
    profile_pic_url_hd: str = ""

    # Contact
    contact: Contact = Field(default_factory=Contact)

    # Bio parsed
    bio: BioParsed = Field(default_factory=BioParsed)

    # Additional
    highlight_count: int = Field(default=0, alias="highlight_reel_count")
    pronouns: List[str] = Field(default_factory=list)
    fbid: Optional[str] = None
    mutual_followers_count: int = 0
    is_threads_user: bool = Field(default=False, alias="is_active_on_text_post_app")
    total_clips: int = Field(default=0, alias="total_clips_count")

    @field_validator("pk", mode="before")
    @classmethod
    def coerce_pk(cls, v: Any) -> int:
        if v is None:
            return 0
        return int(v)

    @field_validator("followers", mode="before")
    @classmethod
    def parse_followers(cls, v: Any) -> int:
        """Handle edge_followed_by.count format."""
        if isinstance(v, dict):
            return v.get("count", 0)
        return int(v) if v else 0

    @field_validator("following", mode="before")
    @classmethod
    def parse_following(cls, v: Any) -> int:
        """Handle edge_follow.count format."""
        if isinstance(v, dict):
            return v.get("count", 0)
        return int(v) if v else 0

    @field_validator("posts_count", mode="before")
    @classmethod
    def parse_posts(cls, v: Any) -> int:
        """Handle edge_owner_to_timeline_media.count format."""
        if isinstance(v, dict):
            return v.get("count", 0)
        return int(v) if v else 0

    @classmethod
    def from_web_profile(cls, data: Dict[str, Any]) -> "User":
        """
        Create User from web_profile_info response.
        Normalizes web-specific field names to unified format.
        """
        return cls(
            pk=data.get("pk") or data.get("id", 0),
            username=data.get("username", ""),
            full_name=data.get("full_name", ""),
            is_verified=data.get("is_verified", False),
            is_private=data.get("is_private", False),
            is_business=data.get("is_business_account", False),
            is_professional=data.get("is_professional_account", False),
            biography=data.get("biography", ""),
            external_url=data.get("external_url", ""),
            category=data.get("category_name", ""),
            followers=data.get("edge_followed_by", {}).get("count", 0),
            following=data.get("edge_follow", {}).get("count", 0),
            posts_count=data.get("edge_owner_to_timeline_media", {}).get("count", 0),
            profile_pic_url=data.get("profile_pic_url", ""),
            profile_pic_url_hd=data.get("profile_pic_url_hd", ""),
            highlight_count=data.get("highlight_reel_count", 0),
            pronouns=data.get("pronouns", []),
            fbid=str(data["fbid"]) if data.get("fbid") else None,
        )

    @classmethod
    def from_api_info(cls, data: Dict[str, Any]) -> "User":
        """
        Create User from /users/{id}/info/ response.
        Normalizes mobile API field names.
        """
        hd_pic = data.get("hd_profile_pic_url_info", {})
        return cls(
            pk=data.get("pk", 0),
            username=data.get("username", ""),
            full_name=data.get("full_name", ""),
            is_verified=data.get("is_verified", False),
            is_private=data.get("is_private", False),
            is_business=data.get("is_business", False),
            biography=data.get("biography", ""),
            external_url=data.get("external_url", ""),
            category=data.get("category") or data.get("account_category", ""),
            followers=data.get("follower_count", 0),
            following=data.get("following_count", 0),
            posts_count=data.get("media_count", 0),
            profile_pic_url=data.get("profile_pic_url", ""),
            profile_pic_url_hd=hd_pic.get("url", "") if isinstance(hd_pic, dict) else "",
            contact=Contact(
                email=data.get("public_email", ""),
                phone=data.get("public_phone_number", ""),
                phone_country_code=data.get("public_phone_country_code", ""),
                city=data.get("city_name", ""),
                address=data.get("address_street", ""),
            ),
            highlight_count=data.get("highlight_reel_count", 0),
            mutual_followers_count=data.get("mutual_followers_count", 0),
            is_threads_user=data.get("is_active_on_text_post_app", False),
            total_clips=data.get("total_clips_count", 0),
        )
