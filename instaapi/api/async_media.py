"""
Media API
=========
Post operations: full info, like, unlike, comment, save, 
get likers and comments.

Media info response structure:
    - pk (int): Media PK
    - id (str): "pk_user_pk" format
    - code (str): Shortcode (for URLs)
    - media_type (int): 1=photo, 2=video, 8=carousel
    - taken_at (int): Unix timestamp
    - like_count, comment_count, play_count, view_count, share_count
    - caption: {text, created_at, user_id, pk}
    - user: {username, pk, full_name, is_verified, is_private, profile_pic_url}
    - location: {name, address, city, lat, lng, pk, facebook_places_id}
    - usertags: {in: [{user: {username, pk}, position: [x, y]}]}
    - carousel_media: [{media_type, pk, image_versions2, video_versions, usertags}]
    - image_versions2: {candidates: [{width, height, url}]}
    - video_versions: [{width, height, url, type}]
    - music_metadata: {music_info: {music_asset_info: {title, display_artist, duration_in_ms}}}
    - clips_metadata: Additional for reels
    - facepile_top_likers: [{username, ...}]

Comments response structure:
    - comments: [{
        pk, text, user: {username, pk, ...}, 
        comment_like_count, child_comment_count,
        created_at, is_ranked_comment, is_edited,
        preview_child_comments: [{text, user, ...}],
        share_enabled, status
      }]
    - comment_count: int
    - has_more_comments: bool
    - has_more_headload_comments: bool
    - next_min_id: str (pagination)
    - sort_options: Sorting options
"""

import re
from typing import Any, Dict, List, Optional

from ..async_client import AsyncHttpClient
from ..models.media import Media as MediaModel
from ..models.comment import Comment as CommentModel
from ..models.user import UserShort


class AsyncMediaAPI:
    """Instagram media (post) API"""

    def __init__(self, client: AsyncHttpClient):
        self._client = client

    # ─── Get data ─────────────────────────────────────

    async def get_info(self, media_id: int | str) -> MediaModel:
        """
        Full post info.

        Args:
            media_id: Media PK (numeric)

        Returns:
            Media model
        """
        data = await self._client.get(
            f"/media/{media_id}/info/",
            rate_category="get_default",
        )
        raw = data
        if "items" in data and data["items"]:
            raw = data["items"][0]
        return MediaModel.from_api(raw)

    async def get_full_info(self, media_id: int | str) -> MediaModel:
        """
        Get full post info in structured format.

        Args:
            media_id: Media PK

        Returns:
            dict:
                - pk, code, media_type
                - likes, comments_count, plays, views, shares
                - caption: {text, hashtags, mentions, created_at}
                - owner: {username, pk, full_name, is_verified}
                - location: {name, address, city, lat, lng}
                - tagged_users: [{username, pk, position}]
                - media_urls: {images: [...], videos: [...]}
                - carousel: [{type, images, videos, tagged}]
                - music: {title, artist, duration_ms}
                - top_likers: [username1, ...]
                - is_video, is_carousel, is_photo
        """
        return await self.get_info(media_id)

    async def get_info_v2(self, media_id: int | str) -> Dict[str, Any]:
        """
        Full media info via /api/v1/media/{id}/info/ (REST v1 endpoint).
        Returns ALL available data in a structured dict.

        Args:
            media_id: Media PK (numeric)

        Returns:
            dict: Complete media info with ALL fields
        """
        from .graphql import GraphQLAPI

        data = await self._client.get(
            f"/media/{media_id}/info/",
            rate_category="get_default",
            full_url=f"https://www.instagram.com/api/v1/media/{media_id}/info/",
        )

        items = data.get("items", [])
        if not items:
            return data

        return GraphQLAPI._parse_v2_media(items[0])

    async def get_info_v2_raw(self, media_id: int | str) -> Dict[str, Any]:
        """
        Raw media info via /api/v1/media/{id}/info/.

        Args:
            media_id: Media PK

        Returns:
            dict: Raw API response (items[0])
        """
        data = await self._client.get(
            f"/media/{media_id}/info/",
            rate_category="get_default",
            full_url=f"https://www.instagram.com/api/v1/media/{media_id}/info/",
        )

        items = data.get("items", [])
        return items[0] if items else data

    async def get_by_url_v2(self, url: str) -> Dict[str, Any]:
        """
        Get media info from an Instagram URL.

        Args:
            url: Instagram post/reel/tv URL

        Returns:
            dict: Full media info (same as get_info_v2)
        """
        from .media import MediaAPI

        shortcode = MediaAPI._extract_shortcode(url)
        if not shortcode:
            raise ValueError(f"Invalid Instagram URL: {url}")

        media_id = MediaAPI._shortcode_to_media_id(shortcode)
        return await self.get_info_v2(media_id)

    # ─── Comments ───────────────────────────────────────────

    async def get_comments(
        self,
        media_id: int | str,
        can_support_threading: bool = True,
        permalink_enabled: bool = False,
        min_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Post comments (with threading).

        Args:
            media_id: Media PK
            can_support_threading: Threaded comments (replies)
            permalink_enabled: Permalink mode
            min_id: Cursor for pagination

        Returns:
            dict:
                - comments: [{
                    pk, text, user, comment_like_count,
                    child_comment_count, preview_child_comments,
                    created_at, is_ranked_comment, is_edited,
                    share_enabled
                  }]
                - comment_count: int
                - has_more_comments: bool
                - has_more_headload_comments: bool
                - next_min_id: str
                - sort_options: list
        """
        params = {
            "can_support_threading": str(can_support_threading).lower(),
            "permalink_enabled": str(permalink_enabled).lower(),
        }
        if min_id:
            params["min_id"] = min_id

        data = await self._client.get(
            f"/media/{media_id}/comments/",
            params=params,
            rate_category="get_default",
        )
        return data

    async def get_comments_parsed(
        self,
        media_id: int | str,
        min_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get comments in structured format.

        Args:
            media_id: Media PK
            min_id: Pagination cursor

        Returns:
            dict:
                - total_count: int
                - comments: List[Comment] models
                - has_more: bool
                - next_cursor: str
        """
        raw = await self.get_comments(media_id, min_id=min_id)

        comments = [
            CommentModel.from_api(c) for c in raw.get("comments", [])
        ]

        return {
            "total_count": raw.get("comment_count", 0),
            "comments": comments,
            "has_more": bool(
                raw.get("has_more_comments")
                or raw.get("has_more_headload_comments")
            ),
            "next_cursor": raw.get("next_min_id"),
        }

    async def get_all_comments(
        self,
        media_id: int | str,
        max_pages: int = 10,
        parsed: bool = False,
    ) -> List:
        """
        Get all comments (with pagination).

        Args:
            media_id: Media PK
            max_pages: Maximum number of pages
            parsed: True = Comment models, False = raw

        Returns:
            List of all comments
        """
        all_comments = []
        cursor = None

        for _ in range(max_pages):
            if parsed:
                data = await self.get_comments_parsed(media_id, min_id=cursor)
                all_comments.extend(data["comments"])
                if not data["has_more"]:
                    break
                cursor = data["next_cursor"]
            else:
                data = await self.get_comments(media_id, min_id=cursor)
                comments = data.get("comments", [])
                all_comments.extend(comments)
                if not data.get("has_more_comments") and not data.get("has_more_headload_comments"):
                    break
                cursor = data.get("next_min_id")

            if not cursor:
                break

        return all_comments

    async def get_comment_replies(
        self,
        media_id: int | str,
        comment_id: int | str,
        min_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get comment replies.

        Args:
            media_id: Media PK
            comment_id: Parent comment PK
            min_id: Pagination cursor

        Returns:
            dict: Reply comments
        """
        params = {}
        if min_id:
            params["min_id"] = min_id

        return await self._client.get(
            f"/media/{media_id}/comments/{comment_id}/child_comments/",
            params=params,
            rate_category="get_default",
        )

    # ─── Likers ─────────────────────────────────────────────

    async def get_likers(self, media_id: int | str) -> List[UserShort]:
        """
        Users who liked the post.

        Args:
            media_id: Media PK

        Returns:
            List of UserShort models
        """
        data = await self._client.get(
            f"/media/{media_id}/likers/",
            rate_category="get_default",
        )
        return [UserShort(**u) for u in data.get("users", [])]

    # ─── Actions (like, comment, save) ──────────────────

    async def like(self, media_id: int | str) -> Dict[str, Any]:
        """
        Like a post ❤️

        Args:
            media_id: Media PK
        """
        return await self._client.post(
            f"/media/{media_id}/like/",
            rate_category="post_like",
        )

    async def unlike(self, media_id: int | str) -> Dict[str, Any]:
        """
        Unlike a post.

        Args:
            media_id: Media PK
        """
        return await self._client.post(
            f"/media/{media_id}/unlike/",
            rate_category="post_like",
        )

    async def comment(self, media_id: int | str, text: str) -> Dict[str, Any]:
        """
        Post a comment.

        Args:
            media_id: Media PK
            text: Comment text
        """
        return await self._client.post(
            f"/media/{media_id}/comment/",
            data={"comment_text": text},
            rate_category="post_comment",
        )

    async def reply_to_comment(
        self,
        media_id: int | str,
        comment_id: int | str,
        text: str,
    ) -> Dict[str, Any]:
        """
        Reply to a comment.

        Args:
            media_id: Media PK
            comment_id: PK of comment being replied to
            text: Reply text
        """
        return await self._client.post(
            f"/media/{media_id}/comment/",
            data={
                "comment_text": text,
                "replied_to_comment_id": str(comment_id),
            },
            rate_category="post_comment",
        )

    async def delete_comment(self, media_id: int | str, comment_id: int | str) -> Dict[str, Any]:
        """
        Delete a comment.

        Args:
            media_id: Media PK
            comment_id: Comment ID
        """
        return await self._client.post(
            f"/media/{media_id}/comment/{comment_id}/delete/",
            rate_category="post_comment",
        )

    async def like_comment(self, comment_id: int | str) -> Dict[str, Any]:
        """
        Like a comment.

        Args:
            comment_id: Comment PK
        """
        return await self._client.post(
            f"/media/{comment_id}/comment_like/",
            rate_category="post_like",
        )

    # ─── SHORTCODE / EDIT / PIN ──────────────────────────────

    async def get_by_shortcode(self, shortcode: str) -> MediaModel:
        """
        Get media by shortcode.

        Shortcode — the code in Instagram URLs.
        Example: instagram.com/p/ABC123 -> shortcode = "ABC123"

        Args:
            shortcode: URL shortcode (after p/, reel/, tv/)

        Returns:
            Media model
        """
        # shortcode -> media_id conversion (Instagram algorithm)
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        media_id = 0
        for char in shortcode:
            media_id = media_id * 64 + alphabet.index(char)
        return await self.get_info(media_id)

    async def edit_caption(self, media_id: int | str, caption: str) -> Dict[str, Any]:
        """
        Edit post caption.

        Args:
            media_id: Media PK
            caption: New caption text

        Returns:
            dict: Updated media data
        """
        return await self._client.post(
            f"/media/{media_id}/edit_media/",
            data={"caption_text": caption},
            rate_category="post_default",
        )

    async def disable_comments(self, media_id: int | str) -> Dict[str, Any]:
        """
        Disable comments.

        Args:
            media_id: Media PK
        """
        return await self._client.post(
            f"/media/{media_id}/disable_comments/",
            rate_category="post_default",
        )

    async def enable_comments(self, media_id: int | str) -> Dict[str, Any]:
        """
        Enable comments.

        Args:
            media_id: Media PK
        """
        return await self._client.post(
            f"/media/{media_id}/enable_comments/",
            rate_category="post_default",
        )

    async def pin_comment(self, media_id: int | str, comment_id: int | str) -> Dict[str, Any]:
        """
        Pin a comment.

        Args:
            media_id: Media PK
            comment_id: Comment PK to pin
        """
        return await self._client.post(
            f"/media/{media_id}/comment/{comment_id}/pin/",
            rate_category="post_default",
        )

    async def unpin_comment(self, media_id: int | str, comment_id: int | str) -> Dict[str, Any]:
        """
        Unpin a comment.

        Args:
            media_id: Media PK
            comment_id: Comment PK to unpin
        """
        return await self._client.post(
            f"/media/{media_id}/comment/{comment_id}/unpin/",
            rate_category="post_default",
        )

    async def report(self, media_id: int | str, reason: int = 1) -> Dict[str, Any]:
        """
        Report a post.

        Args:
            media_id: Media PK
            reason: Reason (1=spam, 2=inappropriate)
        """
        return await self._client.post(
            f"/media/{media_id}/flag_media/",
            data={"reason_id": str(reason)},
            rate_category="post_default",
        )

    async def unlike_comment(self, comment_id: int | str) -> Dict[str, Any]:
        """
        Unlike a comment.

        Args:
            comment_id: Comment PK
        """
        return await self._client.post(
            f"/media/{comment_id}/comment_unlike/",
            rate_category="post_like",
        )

    async def save(self, media_id: int | str) -> Dict[str, Any]:
        """
        Save post (bookmark).

        Args:
            media_id: Media PK
        """
        return await self._client.post(
            f"/web/save/{media_id}/save/",
            rate_category="post_default",
        )

    async def unsave(self, media_id: int | str) -> Dict[str, Any]:
        """
        Remove from bookmarks.

        Args:
            media_id: Media PK
        """
        return await self._client.post(
            f"/web/save/{media_id}/unsave/",
            rate_category="post_default",
        )

    # ─── Web Endpoints (with jazoest) ──────────────────────
    #
    # Web endpoints optimized for browser and
    # use jazoest CSRF additional protection token.
    # Formula: jazoest = "2" + sum(ord(c) for c in csrf_token)

    async def _get_jazoest(self) -> str:
        """Get jazoest token from current session."""
        return await self._client.get_jazoest()

    async def web_comment(self, media_id: int | str, text: str) -> Dict[str, Any]:
        """
        Post comment via web endpoint.

        /api/v1/web/comments/{media_id}/add/
        With jazoest and comment_text parameters.

        Args:
            media_id: Media PK
            text: Comment text

        Returns:
            dict:
                - id: Comment ID
                - text: Comment text
                - from: {username, id, full_name, profile_picture}
                - created_time: Unix timestamp
                - status: "ok"
        """
        return await self._client.post(
            f"/web/comments/{media_id}/add/",
            data={
                "comment_text": text,
                "jazoest": self._get_jazoest(),
            },
            rate_category="post_comment",
        )

    async def web_like(self, media_id: int | str) -> Dict[str, Any]:
        """
        Like via web endpoint ❤️

        /api/v1/web/likes/{media_id}/like/

        Args:
            media_id: Media PK
        """
        return await self._client.post(
            f"/web/likes/{media_id}/like/",
            data={"jazoest": self._get_jazoest()},
            rate_category="post_like",
        )

    async def web_unlike(self, media_id: int | str) -> Dict[str, Any]:
        """
        Unlike via web endpoint.

        Args:
            media_id: Media PK
        """
        return await self._client.post(
            f"/web/likes/{media_id}/unlike/",
            data={"jazoest": self._get_jazoest()},
            rate_category="post_like",
        )

    async def web_save(self, media_id: int | str) -> Dict[str, Any]:
        """
        Save post (bookmark) via web endpoint.

        Args:
            media_id: Media PK
        """
        return await self._client.post(
            f"/web/save/{media_id}/save/",
            data={"jazoest": self._get_jazoest()},
            rate_category="post_default",
        )

    async def web_unsave(self, media_id: int | str) -> Dict[str, Any]:
        """
        Remove bookmark via web endpoint.

        Args:
            media_id: Media PK
        """
        return await self._client.post(
            f"/web/save/{media_id}/unsave/",
            data={"jazoest": self._get_jazoest()},
            rate_category="post_default",
        )

    async def web_delete_comment(
        self,
        media_id: int | str,
        comment_id: int | str,
    ) -> Dict[str, Any]:
        """
        Delete comment via web endpoint.

        Args:
            media_id: Media PK
            comment_id: Comment ID
        """
        return await self._client.post(
            f"/web/comments/{media_id}/delete/{comment_id}/",
            data={"jazoest": self._get_jazoest()},
            rate_category="post_comment",
        )

