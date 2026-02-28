"""
Notification Models
===================
Instagram notification (activity feed) models.

Parses /news/inbox/ response.

Story Types:
    101  — user_followed (Follow notification)
    13   — comment_like (Like on comment)
    60   — like (Like on post)
    12   — comment (Comment)
    1487 — ig_text_post_app_non_onboarded_daily_digest (Threads)
    1686 — ig_text_app_non_onboarded_unconnected_daily_digest (Threads)
    95008 — qp_ig_nf_generic (System/Meta notification)
"""

from typing import Any, Dict, List, Optional
from pydantic import Field, field_validator
from datetime import datetime

from .base import InstaModel


# ── SUB-MODELS ──────────────────────────────────────────


class NotifLink(InstaModel):
    """Link within rich text."""
    start: int = 0
    end: int = 0
    type: str = ""          # "user"
    id: str = ""
    username: Optional[str] = None


class NotifMedia(InstaModel):
    """Media (image) in notification."""
    id: str = ""
    image: str = ""
    shortcode: str = ""


class NotifFriendship(InstaModel):
    """Friendship status."""
    following: bool = False
    followed_by: bool = False
    blocking: bool = False
    muting: bool = False
    is_private: bool = False
    is_restricted: bool = False
    is_bestie: bool = False
    is_feed_favorite: bool = False
    incoming_request: bool = False
    outgoing_request: bool = False
    subscribed: bool = False
    is_muting_reel: bool = False
    is_blocking_reel: bool = False
    is_muting_notes: bool = False


class NotifUserInfo(InstaModel):
    """
    User info within a notification.
    In follow notifications, found inside inline_follow.user_info.
    """
    pk: str = ""
    id: str = ""
    username: str = ""
    full_name: str = ""
    is_verified: bool = False
    is_private: bool = False
    profile_pic_url: str = ""
    hd_profile_pic_url_info: Optional[Dict[str, Any]] = None
    friendship_status: Optional[NotifFriendship] = None

    @field_validator("pk", mode="before")
    @classmethod
    def coerce_pk(cls, v: Any) -> str:
        return str(v) if v else ""

    @property
    def hd_profile_pic(self) -> str:
        """HD profile picture URL."""
        if self.hd_profile_pic_url_info:
            return self.hd_profile_pic_url_info.get("url", self.profile_pic_url)
        return self.profile_pic_url


class NotifInlineFollow(InstaModel):
    """Full user + relationship data inside follow notification."""
    user_info: Optional[NotifUserInfo] = None
    following: bool = False
    outgoing_request: bool = False
    incoming_request: bool = False
    user_relationship: Optional[NotifFriendship] = None


# ── COUNTS MODEL ────────────────────────────────────────


class NotifCounts(InstaModel):
    """
    Notification counters — unread count by type.

    Usage:
        counts = ig.notifications.get_activity_counts_parsed()
        print(f"New likes: {counts.likes}")
        print(f"New followers: {counts.relationships}")
        print(f"Total unread: {counts.total}")
    """
    likes: int = 0
    comments: int = 0
    comment_likes: int = 0
    relationships: int = 0      # follow notifications
    usertags: int = 0
    photos_of_you: int = 0
    requests: int = 0           # follow requests (private accounts)
    new_posts: int = 0
    media_to_approve: int = 0
    promotional: int = 0
    fundraiser: int = 0
    shopping_notification: int = 0
    campaign_notification: int = 0
    activity_feed_dot_badge: int = 0
    activity_feed_dot_badge_only: int = 0

    @property
    def total(self) -> int:
        """Total unread notifications count."""
        return (
            self.likes + self.comments + self.comment_likes +
            self.relationships + self.usertags + self.photos_of_you +
            self.requests + self.new_posts
        )


# ── MAIN NOTIFICATION MODEL ────────────────────────────


class Notification(InstaModel):
    """
    Single notification (activity feed item).

    Fields:
        pk: Unique notification ID
        story_type: Notification type code (101=follow, 13=comment_like, ...)
        notif_name: Notification type name ("user_followed", "comment_like", ...)
        type: Display type (1, 3, 4, 13, 20)

        — Content —
        text: Plain text ("dris.oe started following you.")
        rich_text: Formatted text ({dris.oe|000000|1|...} started following you.)
        links: Links within rich text

        — Who —
        profile_id: From whom (user PK)
        profile_name: Username
        profile_image: Avatar URL

        — Where —
        destination: Navigation target (user?id=..., comments_v2?media_id=...)

        — When —
        timestamp: Unix time
        time_ago: Time in human readable format

        — Follow specific —
        inline_follow: Full user info + friendship in follow notifications
        extra_actions: ["hide", "block", "remove_follower"]

        — Media specific (like/comment) —
        media: Media images (id, image, shortcode)

    Usage:
        notifs = ig.notifications.get_all_parsed()
        for n in notifs:
            print(f"[{n.notif_name}] {n.text}")
            if n.is_follow:
                print(f"  → {n.follower_username} followed you")
            if n.is_like:
                print(f"  → {n.profile_name} liked your post")
    """
    pk: str = ""
    story_type: int = 0
    notif_name: str = ""
    type: int = 0

    # Content
    text: str = ""
    rich_text: str = ""
    links: List[NotifLink] = Field(default_factory=list)

    # Who
    profile_id: str = ""
    profile_name: str = ""
    profile_image: str = ""

    # Where
    destination: str = ""

    # When
    timestamp: float = 0.0

    # Follow specific
    inline_follow: Optional[NotifInlineFollow] = None
    extra_actions: List[str] = Field(default_factory=list)

    # Media specific
    media: List[NotifMedia] = Field(default_factory=list)

    # ─── Properties ──────────────────────────────────

    @property
    def is_follow(self) -> bool:
        """Follow notification."""
        return self.notif_name == "user_followed"

    @property
    def is_comment_like(self) -> bool:
        """Like on comment."""
        return self.notif_name == "comment_like"

    @property
    def is_like(self) -> bool:
        """Like on post."""
        return self.notif_name in ("like", "comment_like")

    @property
    def is_threads(self) -> bool:
        """Threads notification."""
        return "ig_text" in self.notif_name

    @property
    def is_system(self) -> bool:
        """System/Meta notification."""
        return self.notif_name == "qp_ig_nf_generic"

    @property
    def time_ago(self) -> str:
        """How long ago (human readable)."""
        if not self.timestamp:
            return ""
        delta = datetime.now().timestamp() - self.timestamp
        if delta < 60:
            return f"{int(delta)}s ago"
        elif delta < 3600:
            return f"{int(delta / 60)}m ago"
        elif delta < 86400:
            return f"{int(delta / 3600)}h ago"
        elif delta < 604800:
            return f"{int(delta / 86400)}d ago"
        elif delta < 2592000:
            return f"{int(delta / 604800)}w ago"
        else:
            return f"{int(delta / 2592000)}mo ago"

    @property
    def follower_username(self) -> str:
        """Follower's username if this is a follow notification."""
        if self.inline_follow and self.inline_follow.user_info:
            return self.inline_follow.user_info.username
        return self.profile_name

    @property
    def follower_info(self) -> Optional[NotifUserInfo]:
        """Full user info if this is a follow notification."""
        if self.inline_follow:
            return self.inline_follow.user_info
        return None

    @property
    def is_following_back(self) -> bool:
        """Am I following this follower back?"""
        if self.inline_follow:
            return self.inline_follow.following
        return False

    @property
    def media_shortcode(self) -> str:
        """Post shortcode (in like/comment notifications)."""
        if self.media:
            return self.media[0].shortcode
        return ""

    @property
    def media_image(self) -> str:
        """Post image URL (in like/comment notifications)."""
        if self.media:
            return self.media[0].image
        return ""

    # ─── Factory  ────────────────────────────────────

    @classmethod
    def from_story(cls, story: Dict[str, Any]) -> "Notification":
        """
        Create Notification from raw story dict.

        Handles:
            - Extracts all fields from args
            - Correctly parses sub-models
        """
        args = story.get("args", {})

        # Links
        links = [NotifLink(**l) for l in args.get("links", [])]

        # Media
        media_list = args.get("media", [])
        media = [NotifMedia(**m) for m in media_list]

        # Inline Follow
        inline_data = args.get("inline_follow")
        inline_follow = None
        if inline_data:
            user_info = None
            if inline_data.get("user_info"):
                # Friendship status
                fs_data = inline_data["user_info"].get("friendship_status")
                friendship = NotifFriendship(**fs_data) if fs_data else None

                user_info = NotifUserInfo(
                    **{k: v for k, v in inline_data["user_info"].items()
                       if k != "friendship_status"},
                    friendship_status=friendship,
                )

            # User relationship
            ur_data = inline_data.get("user_relationship")
            user_rel = NotifFriendship(**ur_data) if ur_data else None

            inline_follow = NotifInlineFollow(
                user_info=user_info,
                following=inline_data.get("following", False),
                outgoing_request=inline_data.get("outgoing_request", False),
                incoming_request=inline_data.get("incoming_request", False),
                user_relationship=user_rel,
            )

        return cls(
            pk=str(story.get("pk", "")),
            story_type=story.get("story_type", 0),
            notif_name=story.get("notif_name", ""),
            type=story.get("type", 0),
            text=args.get("text", ""),
            rich_text=args.get("rich_text", ""),
            links=links,
            profile_id=str(args.get("profile_id", "")),
            profile_name=args.get("profile_name", ""),
            profile_image=args.get("profile_image", ""),
            destination=args.get("destination", ""),
            timestamp=args.get("timestamp", 0.0),
            inline_follow=inline_follow,
            extra_actions=args.get("extra_actions", []),
            media=media,
        )


# ── INBOX RESPONSE ──────────────────────────────────────


class NotifInbox(InstaModel):
    """
    Full /news/inbox/ response model.

    Usage:
        inbox = ig.notifications.get_inbox_parsed()
        print(f"Unread: {inbox.counts.total}")
        for n in inbox.new_notifications:
            print(f"  NEW: {n.text}")
        for n in inbox.old_notifications:
            print(f"  OLD: {n.text}")
    """
    counts: NotifCounts = Field(default_factory=NotifCounts)
    last_checked: float = 0.0
    new_notifications: List[Notification] = Field(default_factory=list)
    old_notifications: List[Notification] = Field(default_factory=list)
    is_last_page: bool = True
    continuation_token: int = 0
    partition_headers: List[str] = Field(default_factory=list)

    @classmethod
    def from_response(cls, data: Dict[str, Any]) -> "NotifInbox":
        """Parse from raw /news/inbox/ response."""
        # Counts
        counts = NotifCounts(**data.get("counts", {}))

        # Parse stories
        new_stories = [
            Notification.from_story(s)
            for s in data.get("new_stories", [])
        ]
        old_stories = [
            Notification.from_story(s)
            for s in data.get("old_stories", [])
        ]

        # Partition headers
        partition = data.get("partition", {})
        headers = partition.get("time_bucket", {}).get("headers", [])

        return cls(
            counts=counts,
            last_checked=data.get("last_checked", 0.0),
            new_notifications=new_stories,
            old_notifications=old_stories,
            is_last_page=data.get("is_last_page", True),
            continuation_token=data.get("continuation_token", 0),
            partition_headers=headers,
        )

    @property
    def all_notifications(self) -> List[Notification]:
        """All notifications — new ones first."""
        return self.new_notifications + self.old_notifications

    @property
    def follows(self) -> List[Notification]:
        """Follow notifications only."""
        return [n for n in self.all_notifications if n.is_follow]

    @property
    def likes(self) -> List[Notification]:
        """Like notifications only."""
        return [n for n in self.all_notifications if n.is_like]

    @property
    def non_system(self) -> List[Notification]:
        """Real notifications excluding System/Threads."""
        return [
            n for n in self.all_notifications
            if not n.is_system and not n.is_threads
        ]
