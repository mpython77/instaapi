"""
Public Data Models
==================
Pydantic models for Instagram Public Data analytics.

Based on Supermetrics Instagram Public Data connector fields:
- Profile Info (followers, following, posts, bio, etc.)
- Profile Posts (likes, comments, media type, caption, etc.)
- Post Search / Hashtags (top posts, recent posts, matching hashtags)

Usage:
    from instaapi.models.public_data import PublicProfile, PublicPost

    profile = PublicProfile.from_api(raw_data)
    print(f"@{profile.username} — {profile.followers:,} followers")
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import Field, field_validator, computed_field

from .base import InstaModel


class PublicProfile(InstaModel):
    """
    Public profile data model — maps to Supermetrics 'Profile Info' query type.

    Contains current snapshot of publicly available account information.
    Historical data is NOT available — only current values.

    Fields:
        username: Instagram handle (case-sensitive)
        name: Display name
        ig_id: Instagram numeric ID
        biography: Bio text
        website: External URL
        profile_pic_url: Profile picture URL
        followers: Follower count (current)
        following: Following count (current)
        posts_count: Total published posts
        is_verified: Blue badge
        is_private: Private account
        is_business: Business/Creator account
        category: Account category (e.g. "Athlete", "Artist")
    """

    # Identity
    username: str = ""
    name: str = ""
    ig_id: str = ""

    # Bio
    biography: str = ""
    website: str = ""
    profile_pic_url: str = ""

    # Counters (Supermetrics: Profile followers, Profile follows, Profile post count)
    followers: int = 0
    following: int = 0
    posts_count: int = 0

    # Flags
    is_verified: bool = False
    is_private: bool = False
    is_business: bool = False
    category: str = ""

    # Metadata
    fetched_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    @field_validator("ig_id", mode="before")
    @classmethod
    def coerce_ig_id(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)

    @field_validator("followers", "following", "posts_count", mode="before")
    @classmethod
    def coerce_int(cls, v: Any) -> int:
        if v is None:
            return 0
        if isinstance(v, dict):
            return v.get("count", 0)
        return int(v)

    @field_validator("biography", "website", "name", "username", "category",
                     "profile_pic_url", mode="before")
    @classmethod
    def coerce_str(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)

    @computed_field
    @property
    def profile_url(self) -> str:
        """Full Instagram profile URL."""
        if self.username:
            return f"https://www.instagram.com/{self.username}/"
        return ""

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "PublicProfile":
        """
        Create PublicProfile from raw API response.

        Handles both web_profile_info and mobile API formats.
        """
        # Handle nested user dict
        user = data.get("user", data)

        # Handle web format (edge_followed_by) vs mobile format (follower_count)
        followers = (
            user.get("edge_followed_by", {}).get("count")
            or user.get("follower_count")
            or user.get("followers")
            or 0
        )
        following = (
            user.get("edge_follow", {}).get("count")
            or user.get("following_count")
            or user.get("following")
            or 0
        )
        posts_count = (
            user.get("edge_owner_to_timeline_media", {}).get("count")
            or user.get("media_count")
            or user.get("posts_count")
            or 0
        )

        return cls(
            username=user.get("username", ""),
            name=user.get("full_name", "") or user.get("name", ""),
            ig_id=str(user.get("pk") or user.get("id", "")),
            biography=user.get("biography", ""),
            website=user.get("external_url", "") or user.get("website", ""),
            profile_pic_url=(
                user.get("profile_pic_url_hd", "")
                or user.get("profile_pic_url", "")
            ),
            followers=followers,
            following=following,
            posts_count=posts_count,
            is_verified=user.get("is_verified", False),
            is_private=user.get("is_private", False),
            is_business=(
                user.get("is_business_account", False)
                or user.get("is_business", False)
            ),
            category=(
                user.get("category_name", "")
                or user.get("category", "")
            ),
        )

    def __repr__(self) -> str:
        v = " [verified]" if self.is_verified else ""
        return (
            f"<PublicProfile @{self.username}{v} "
            f"followers={self.followers:,} "
            f"posts={self.posts_count:,}>"
        )


class PublicPost(InstaModel):
    """
    Public post data model — maps to Supermetrics 'Profile Posts' query type.

    Contains post metrics and content data publicly available.

    Fields:
        post_id: Media numeric ID
        shortcode: URL shortcode (e.g. "ABC123")
        username: Post owner username
        media_type: "image", "video", or "carousel"
        caption: Post caption text
        likes: Like count
        comments: Comment count
        reels_views: Reels view count (added Jan 2026)
        post_url: Direct link to post
        image_url: First image URL (for carousel: first image)
        media_url: Media file URL (video/image)
        hashtags: Extracted hashtags from caption
        created_at: Post creation timestamp
    """

    # Identity
    post_id: str = ""
    shortcode: str = ""
    username: str = ""

    # Content
    media_type: str = "image"  # image, video, carousel
    caption: str = ""

    # Metrics (Supermetrics: Likes, Comments, Reels views)
    likes: int = 0
    comments: int = 0
    reels_views: int = 0

    # URLs (Supermetrics: Link to post, Image, Media URL)
    post_url: str = ""
    image_url: str = ""
    media_url: str = ""

    # Hashtags (Supermetrics: Hashtags, Number of hashtags)
    hashtags: List[str] = Field(default_factory=list)

    # Time (Supermetrics: Post created)
    created_at: Optional[datetime] = None

    @field_validator("post_id", mode="before")
    @classmethod
    def coerce_post_id(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)

    @field_validator("likes", "comments", "reels_views", mode="before")
    @classmethod
    def coerce_int(cls, v: Any) -> int:
        if v is None:
            return 0
        return int(v)

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, (int, float)):
            return datetime.utcfromtimestamp(v)
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        return None

    @computed_field
    @property
    def hashtag_count(self) -> int:
        """Number of hashtags in Caption (Supermetrics: Number of hashtags)."""
        return len(self.hashtags)

    @computed_field
    @property
    def engagement(self) -> int:
        """Total engagement (likes + comments)."""
        return self.likes + self.comments

    @property
    def likes_per_post(self) -> float:
        """Supermetrics: Likes per post (same as likes for single post)."""
        return float(self.likes)

    @property
    def comments_per_post(self) -> float:
        """Supermetrics: Comments per post (same as comments for single post)."""
        return float(self.comments)

    @classmethod
    def extract_hashtags(cls, text: str) -> List[str]:
        """Extract hashtags from caption text."""
        if not text:
            return []
        return re.findall(r"#(\w+)", text)

    @classmethod
    def from_api(cls, data: Dict[str, Any], username: str = "") -> "PublicPost":
        """
        Create PublicPost from raw Instagram API response.

        Handles both web and mobile API formats.
        """
        # Caption
        caption_data = data.get("caption", {})
        if isinstance(caption_data, dict):
            caption_text = caption_data.get("text", "")
        elif isinstance(caption_data, str):
            caption_text = caption_data
        else:
            caption_text = ""

        # Edge caption (web format)
        if not caption_text:
            edges = data.get("edge_media_to_caption", {}).get("edges", [])
            if edges:
                caption_text = edges[0].get("node", {}).get("text", "")

        # Media type
        media_type_raw = data.get("media_type", 1)
        if isinstance(media_type_raw, int):
            type_map = {1: "image", 2: "video", 8: "carousel"}
            media_type = type_map.get(media_type_raw, "image")
        else:
            media_type = str(media_type_raw).lower()

        # Shortcode
        shortcode = data.get("code", "") or data.get("shortcode", "")

        # Image URL
        image_url = ""
        img_versions = data.get("image_versions2", {})
        if isinstance(img_versions, dict):
            candidates = img_versions.get("candidates", [])
            if candidates:
                image_url = candidates[0].get("url", "")
        if not image_url:
            image_url = data.get("display_url", "") or data.get("thumbnail_src", "")

        # Video URL
        media_url = data.get("video_url", "") or image_url

        # User
        post_user = data.get("user", {})
        post_username = ""
        if isinstance(post_user, dict):
            post_username = post_user.get("username", "")
        if not post_username:
            post_username = data.get("owner", {}).get("username", "") or username

        # Likes
        likes = (
            data.get("like_count")
            or data.get("edge_media_preview_like", {}).get("count")
            or data.get("likes", 0)
            or 0
        )

        # Comments
        comments = (
            data.get("comment_count")
            or data.get("edge_media_to_comment", {}).get("count")
            or data.get("comments", 0)
            or 0
        )

        # Timestamp
        taken_at = data.get("taken_at") or data.get("taken_at_timestamp")

        # Hashtags from caption
        hashtags = cls.extract_hashtags(caption_text)

        return cls(
            post_id=str(data.get("pk", "") or data.get("id", "")),
            shortcode=shortcode,
            username=post_username,
            media_type=media_type,
            caption=caption_text,
            likes=likes,
            comments=comments,
            reels_views=data.get("play_count", 0) or data.get("view_count", 0) or 0,
            post_url=f"https://www.instagram.com/p/{shortcode}/" if shortcode else "",
            image_url=image_url,
            media_url=media_url,
            hashtags=hashtags,
            created_at=taken_at,
        )

    def __repr__(self) -> str:
        return (
            f"<PublicPost @{self.username} "
            f"likes={self.likes:,} comments={self.comments:,} "
            f"type={self.media_type}>"
        )


class HashtagPost(InstaModel):
    """
    Hashtag search result post — maps to Supermetrics 'Post Search' query type.

    Extends PublicPost with hashtag-specific matching data.

    Fields:
        post: The underlying PublicPost data
        search_hashtag: The hashtag that was searched
        matching_hashtags: Hashtags matching the search query
        search_type: "top" or "recent"
    """

    post: PublicPost = Field(default_factory=PublicPost)
    search_hashtag: str = ""
    matching_hashtags: List[str] = Field(default_factory=list)
    search_type: str = "top"  # "top" or "recent"

    @computed_field
    @property
    def is_top(self) -> bool:
        """Whether this is from Top search."""
        return self.search_type == "top"

    @computed_field
    @property
    def is_recent(self) -> bool:
        """Whether this is from Recent search."""
        return self.search_type == "recent"

    def __repr__(self) -> str:
        return (
            f"<HashtagPost #{self.search_hashtag} "
            f"type={self.search_type} "
            f"likes={self.post.likes:,}>"
        )


class ProfileSnapshot(InstaModel):
    """
    Point-in-time snapshot of profile metrics — for tracking growth over time.

    Since Instagram Public Data only returns current values (no historical),
    snapshots let you build historical data via periodic captures.
    """

    username: str = ""
    followers: int = 0
    following: int = 0
    posts_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def from_profile(cls, profile: PublicProfile) -> "ProfileSnapshot":
        """Create snapshot from a PublicProfile."""
        return cls(
            username=profile.username,
            followers=profile.followers,
            following=profile.following,
            posts_count=profile.posts_count,
        )

    def growth_since(self, other: "ProfileSnapshot") -> Dict[str, Any]:
        """Calculate growth compared to an older snapshot."""
        time_diff = (self.timestamp - other.timestamp).total_seconds()
        hours = max(time_diff / 3600, 1)

        follower_diff = self.followers - other.followers
        posts_diff = self.posts_count - other.posts_count

        return {
            "follower_change": follower_diff,
            "follower_growth_rate": round(follower_diff / hours, 2),
            "posts_change": posts_diff,
            "hours_elapsed": round(hours, 1),
            "followers_per_day": round(follower_diff / (hours / 24), 1) if hours >= 24 else None,
        }

    def __repr__(self) -> str:
        return (
            f"<ProfileSnapshot @{self.username} "
            f"followers={self.followers:,} "
            f"at={self.timestamp.isoformat()}>"
        )


class PublicDataReport(InstaModel):
    """
    Aggregated Public Data report container.

    Combines profile info, posts, hashtag results, and computed metrics
    into a single exportable report.

    Maps to Supermetrics data warehouse table groups:
    - PROFILES table → profiles field
    - POSTS table → posts field
    - HASHTAGS table → hashtag_posts field
    """

    # Data
    profiles: List[PublicProfile] = Field(default_factory=list)
    posts: List[PublicPost] = Field(default_factory=list)
    hashtag_posts: List[HashtagPost] = Field(default_factory=list)
    snapshots: List[ProfileSnapshot] = Field(default_factory=list)

    # Query metadata (Supermetrics: QUERY dimensions)
    query_type: str = ""  # "profile_info", "profile_posts", "post_search"
    query_start: Optional[datetime] = None
    query_end: Optional[datetime] = None
    query_duration_seconds: float = 0.0
    usernames_queried: List[str] = Field(default_factory=list)
    hashtags_queried: List[str] = Field(default_factory=list)

    @computed_field
    @property
    def total_profiles(self) -> int:
        return len(self.profiles)

    @computed_field
    @property
    def total_posts(self) -> int:
        return len(self.posts)

    @computed_field
    @property
    def total_hashtag_posts(self) -> int:
        return len(self.hashtag_posts)

    @computed_field
    @property
    def avg_likes(self) -> float:
        """Average likes across all posts."""
        if not self.posts:
            return 0.0
        return round(sum(p.likes for p in self.posts) / len(self.posts), 2)

    @computed_field
    @property
    def avg_comments(self) -> float:
        """Average comments across all posts."""
        if not self.posts:
            return 0.0
        return round(sum(p.comments for p in self.posts) / len(self.posts), 2)

    @computed_field
    @property
    def total_engagement(self) -> int:
        """Total engagement (likes + comments) across all posts."""
        return sum(p.likes + p.comments for p in self.posts)

    def to_profiles_table(self) -> List[Dict[str, Any]]:
        """Export as Supermetrics PROFILES table format."""
        return [
            {
                "username": p.username,
                "name": p.name,
                "profile_followers": p.followers,
                "profile_follows": p.following,
                "biography": p.biography,
                "instagram_account_id": p.ig_id,
                "profile_pic_url": p.profile_pic_url,
                "profile_post_count": p.posts_count,
                "website": p.website,
                "date": (p.fetched_at or datetime.utcnow()).strftime("%Y-%m-%d"),
            }
            for p in self.profiles
        ]

    def to_posts_table(self) -> List[Dict[str, Any]]:
        """Export as Supermetrics POSTS table format."""
        return [
            {
                "likes_per_post": p.likes_per_post,
                "caption": p.caption,
                "comments_per_post": p.comments_per_post,
                "username": p.username,
                "likes": p.likes,
                "media_type": p.media_type,
                "comments": p.comments,
                "image": p.image_url,
                "link_to_post": p.post_url,
                "post_created": p.created_at.isoformat() if p.created_at else "",
                "hashtags": ", ".join(p.hashtags),
                "reels_views": p.reels_views,
                "date": p.created_at.strftime("%Y-%m-%d") if p.created_at else "",
            }
            for p in self.posts
        ]

    def to_hashtags_table(self) -> List[Dict[str, Any]]:
        """Export as Supermetrics HASHTAGS table format."""
        return [
            {
                "likes": hp.post.likes,
                "comments": hp.post.comments,
                "caption": hp.post.caption,
                "username": hp.post.username,
                "number_of_hashtags": hp.post.hashtag_count,
                "hashtags": ", ".join(hp.post.hashtags),
                "matching_hashtags": ", ".join(hp.matching_hashtags),
                "reels_views": hp.post.reels_views,
                "media_type": hp.post.media_type,
                "image": hp.post.image_url,
                "link_to_post": hp.post.post_url,
                "post_created": hp.post.created_at.isoformat() if hp.post.created_at else "",
                "media_url": hp.post.media_url,
                "date": hp.post.created_at.strftime("%Y-%m-%d") if hp.post.created_at else "",
            }
            for hp in self.hashtag_posts
        ]

    def __repr__(self) -> str:
        return (
            f"<PublicDataReport "
            f"profiles={self.total_profiles} "
            f"posts={self.total_posts} "
            f"hashtag_posts={self.total_hashtag_posts} "
            f"query={self.query_type}>"
        )
