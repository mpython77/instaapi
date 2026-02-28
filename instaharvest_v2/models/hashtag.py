"""
Hashtag Models
==============
Models for hashtag search results with pagination support.
"""

from typing import Any, Dict, List, Optional
from pydantic import Field

from .base import InstaModel
from .user import UserShort
from .media import Media


class HashtagSearchResult(InstaModel):
    """
    Hashtag search result — one or multiple pages.

    Contains all data:
    - posts: Media models (caption, like, comment, image, video)
    - users: Unique profiles dict (post owners + tagged users)
    - Pagination: has_more, next_max_id, rank_token

    Usage:
        result = ig.search.hashtag_search("#programmer", max_pages=5)

        # Posts
        for post in result.posts:
            print(f"{post.user.username}: {post.like_count} likes")
            print(f"  URL: {post.url}")
            print(f"  Caption: {post.caption_text[:100]}")

        # Unique profiles
        for username, user in result.users.items():
            verified = "✅" if user.is_verified else ""
            print(f"@{username} {verified} — {user.full_name}")

        # Continue pagination
        if result.has_more:
            next_result = ig.search.hashtag_search(
                "#programmer",
                next_max_id=result.next_max_id,
                rank_token=result.rank_token,
            )
    """

    # Posts (Media model — pk, code, user, caption, likes, images, etc.)
    posts: List[Media] = Field(default_factory=list)

    # Unique profiles — {username: UserShort}
    # Contains post owner + tagged users
    users: Dict[str, UserShort] = Field(default_factory=dict)

    # Pagination
    has_more: bool = False
    next_max_id: Optional[str] = None
    rank_token: Optional[str] = None
    search_session_id: Optional[str] = None

    # Statistika
    total_posts: int = 0
    total_users: int = 0
    pages_fetched: int = 0

    @property
    def post_count(self) -> int:
        """Total number of posts."""
        return len(self.posts)

    @property
    def user_count(self) -> int:
        """Number of unique profiles."""
        return len(self.users)

    @property
    def verified_users(self) -> Dict[str, UserShort]:
        """Only verified profiles."""
        return {
            u: info for u, info in self.users.items()
            if info.is_verified
        }

    @property
    def public_users(self) -> Dict[str, UserShort]:
        """Only public profiles."""
        return {
            u: info for u, info in self.users.items()
            if not info.is_private
        }

    @property
    def private_users(self) -> Dict[str, UserShort]:
        """Only private profiles."""
        return {
            u: info for u, info in self.users.items()
            if info.is_private
        }

    def merge(self, other: "HashtagSearchResult") -> "HashtagSearchResult":
        """
        Merge two results (for pagination).

        Removes duplicate posts (by pk).
        """
        existing_pks = {p.pk for p in self.posts}
        new_posts = [p for p in other.posts if p.pk not in existing_pks]

        return HashtagSearchResult(
            posts=self.posts + new_posts,
            users={**self.users, **other.users},
            has_more=other.has_more,
            next_max_id=other.next_max_id,
            rank_token=other.rank_token or self.rank_token,
            search_session_id=other.search_session_id or self.search_session_id,
            total_posts=len(self.posts) + len(new_posts),
            total_users=len({**self.users, **other.users}),
            pages_fetched=self.pages_fetched + other.pages_fetched,
        )

    def __repr__(self) -> str:
        verified = len(self.verified_users)
        return (
            f"<HashtagSearchResult "
            f"posts={self.post_count} "
            f"users={self.user_count} "
            f"(verified={verified}) "
            f"pages={self.pages_fetched} "
            f"has_more={self.has_more}>"
        )
