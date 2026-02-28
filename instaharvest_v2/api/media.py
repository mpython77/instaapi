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

from ..client import HttpClient
from ..models.media import Media as MediaModel
from ..models.comment import Comment as CommentModel
from ..models.user import UserShort


class MediaAPI:
    """Instagram media (post) API"""

    def __init__(self, client: HttpClient):
        self._client = client

    # ─── Get data ─────────────────────────────────────

    def get_info(self, media_id: int | str) -> MediaModel:
        """
        Full post info.

        Args:
            media_id: Media PK (numeric)

        Returns:
            Media model
        """
        data = self._client.get(
            f"/media/{media_id}/info/",
            rate_category="get_default",
        )
        raw = data
        if "items" in data and data["items"]:
            raw = data["items"][0]
        return MediaModel.from_api(raw)

    def get_full_info(self, media_id: int | str) -> MediaModel:
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
        return self.get_info(media_id)

    def get_info_v2(self, media_id: int | str) -> Dict[str, Any]:
        """
        Full media info via /api/v1/media/{id}/info/ (REST v1 endpoint).
        Returns ALL available data in a structured dict.

        This is the most complete media info endpoint — returns
        engagement stats, image/video URLs, carousel items,
        music metadata, tagged users, location, and more.

        Args:
            media_id: Media PK (numeric, e.g. 3788237658380900437)

        Returns:
            dict: Complete media info with ALL fields:
                - pk, code, media_type, media_type_name
                - like_count, comment_count, play_count, view_count
                - caption, taken_at, user (owner)
                - images (all resolutions), videos (all qualities)
                - carousel (if carousel), tagged_users
                - location, music, coauthors
                - is_photo, is_video, is_carousel, is_reel
                - has_liked, has_saved, comments_disabled
        """
        from .graphql import GraphQLAPI

        data = self._client.get(
            f"/media/{media_id}/info/",
            rate_category="get_default",
            full_url=f"https://www.instagram.com/api/v1/media/{media_id}/info/",
        )

        items = data.get("items", [])
        if not items:
            return data

        return GraphQLAPI._parse_v2_media(items[0])

    def get_info_v2_raw(self, media_id: int | str) -> Dict[str, Any]:
        """
        Raw media info via /api/v1/media/{id}/info/.
        Returns the raw API response without parsing.

        Args:
            media_id: Media PK

        Returns:
            dict: Raw API response (items[0])
        """
        data = self._client.get(
            f"/media/{media_id}/info/",
            rate_category="get_default",
            full_url=f"https://www.instagram.com/api/v1/media/{media_id}/info/",
        )

        items = data.get("items", [])
        return items[0] if items else data

    def get_by_url_v2(self, url: str) -> Dict[str, Any]:
        """
        Get media info from an Instagram URL.

        Supports:
            - https://www.instagram.com/p/SHORTCODE/
            - https://www.instagram.com/reel/SHORTCODE/
            - https://www.instagram.com/tv/SHORTCODE/
            - https://instagram.com/p/SHORTCODE/

        Args:
            url: Instagram post/reel/tv URL

        Returns:
            dict: Full media info (same as get_info_v2)
        """
        shortcode = self._extract_shortcode(url)
        if not shortcode:
            raise ValueError(f"Invalid Instagram URL: {url}")

        media_id = self._shortcode_to_media_id(shortcode)
        return self.get_info_v2(media_id)

    @staticmethod
    def _extract_shortcode(url: str) -> Optional[str]:
        """Extract shortcode from Instagram URL."""
        match = re.search(r'instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
        return match.group(1) if match else None

    @staticmethod
    def _shortcode_to_media_id(shortcode: str) -> int:
        """
        Convert Instagram shortcode to media ID (PK).
        Uses base64-like decoding algorithm.
        """
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        media_id = 0
        for char in shortcode:
            media_id = media_id * 64 + alphabet.index(char)
        return media_id

    @staticmethod
    def _media_id_to_shortcode(media_id: int) -> str:
        """
        Convert media ID (PK) to Instagram shortcode.
        """
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        shortcode = ""
        while media_id > 0:
            shortcode = alphabet[media_id % 64] + shortcode
            media_id //= 64
        return shortcode


    # ─── Comments ───────────────────────────────────────────

    def get_comments(
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

        data = self._client.get(
            f"/media/{media_id}/comments/",
            params=params,
            rate_category="get_default",
        )
        return data

    def get_comments_parsed(
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
        raw = self.get_comments(media_id, min_id=min_id)

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

    def get_all_comments(
        self,
        media_id: int | str,
        max_pages: int = 10,
        parsed: bool = False,
    ) -> List[Dict]:
        """
        Get all comments (with pagination).

        Args:
            media_id: Media PK
            max_pages: Maximum number of pages
            parsed: True = structured, False = raw

        Returns:
            List of all comments
        """
        all_comments = []
        cursor = None

        for _ in range(max_pages):
            if parsed:
                data = self.get_comments_parsed(media_id, min_id=cursor)
                all_comments.extend(data["comments"])
                if not data["has_more"]:
                    break
                cursor = data["next_cursor"]
            else:
                data = self.get_comments(media_id, min_id=cursor)
                comments = data.get("comments", [])
                all_comments.extend(comments)
                if not data.get("has_more_comments") and not data.get("has_more_headload_comments"):
                    break
                cursor = data.get("next_min_id")

            if not cursor:
                break

        return all_comments

    def get_comment_replies(
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

        return self._client.get(
            f"/media/{media_id}/comments/{comment_id}/child_comments/",
            params=params,
            rate_category="get_default",
        )

    # ─── Likers ─────────────────────────────────────────────

    def get_likers(self, media_id: int | str) -> List[UserShort]:
        """
        Users who liked the post.

        Args:
            media_id: Media PK

        Returns:
            List of UserShort models
        """
        data = self._client.get(
            f"/media/{media_id}/likers/",
            rate_category="get_default",
        )
        return [UserShort(**u) for u in data.get("users", [])]

    # ─── Actions (like, comment, save) ──────────────────

    def like(self, media_id: int | str) -> Dict[str, Any]:
        """
        Like a post ❤️

        Args:
            media_id: Media PK
        """
        return self._client.post(
            f"/web/likes/{media_id}/like/",
            rate_category="post_like",
        )

    def unlike(self, media_id: int | str) -> Dict[str, Any]:
        """
        Unlike a post.

        Args:
            media_id: Media PK
        """
        return self._client.post(
            f"/web/likes/{media_id}/unlike/",
            rate_category="post_like",
        )

    def comment(self, media_id: int | str, text: str) -> Dict[str, Any]:
        """
        Post a comment.

        Uses /web/comments/{media_id}/add/ endpoint.
        HttpClient automatically adds all required headers:
        - x-ig-www-claim (HMAC)
        - x-instagram-ajax (build hash)
        - sec-fetch-* (browser security)
        - cookie string (full session)

        Args:
            media_id: Media PK
            text: Comment text

        Returns:
            dict: {id, from, text, created_time, status}
        """
        session = self._client.get_session()
        jazoest = session.jazoest if session else ""

        return self._client.post(
            f"/web/comments/{media_id}/add/",
            data={
                "comment_text": text,
                "jazoest": jazoest,
            },
            rate_category="post_comment",
        )

    def reply_to_comment(
        self,
        media_id: int | str,
        comment_id: int | str,
        text: str,
    ) -> Dict[str, Any]:
        """
        Reply to a comment.

        Uses /web/comments/{media_id}/add/ endpoint (same as comment).

        Args:
            media_id: Media PK
            comment_id: PK of comment being replied to
            text: Reply text
        """
        session = self._client.get_session()
        jazoest = session.jazoest if session else ""

        return self._client.post(
            f"/web/comments/{media_id}/add/",
            data={
                "comment_text": text,
                "replied_to_comment_id": str(comment_id),
                "jazoest": jazoest,
            },
            rate_category="post_comment",
        )

    def delete_comment(self, media_id: int | str, comment_id: int | str) -> Dict[str, Any]:
        """
        Delete a comment.

        Args:
            media_id: Media PK
            comment_id: Comment ID
        """
        return self._client.post(
            f"/media/{media_id}/comment/{comment_id}/delete/",
            rate_category="post_comment",
        )

    def like_comment(self, comment_id: int | str) -> Dict[str, Any]:
        """
        Like a comment.

        Args:
            comment_id: Comment PK
        """
        return self._client.post(
            f"/media/{comment_id}/comment_like/",
            rate_category="post_like",
        )

    # ─── SHORTCODE / EDIT / PIN ──────────────────────────────

    def get_by_shortcode(self, shortcode: str) -> MediaModel:
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
        return self.get_info(media_id)

    def edit_caption(self, media_id: int | str, caption: str) -> Dict[str, Any]:
        """
        Edit post caption.

        Args:
            media_id: Media PK
            caption: New caption text

        Returns:
            dict: Updated media data
        """
        return self._client.post(
            f"/media/{media_id}/edit_media/",
            data={"caption_text": caption},
            rate_category="post_default",
        )

    def disable_comments(self, media_id: int | str) -> Dict[str, Any]:
        """
        Disable comments.

        Args:
            media_id: Media PK
        """
        return self._client.post(
            f"/media/{media_id}/disable_comments/",
            rate_category="post_default",
        )

    def enable_comments(self, media_id: int | str) -> Dict[str, Any]:
        """
        Enable comments.

        Args:
            media_id: Media PK
        """
        return self._client.post(
            f"/media/{media_id}/enable_comments/",
            rate_category="post_default",
        )

    def pin_comment(self, media_id: int | str, comment_id: int | str) -> Dict[str, Any]:
        """
        Pin a comment.

        Args:
            media_id: Media PK
            comment_id: Comment PK to pin
        """
        return self._client.post(
            f"/media/{media_id}/comment/{comment_id}/pin/",
            rate_category="post_default",
        )

    def unpin_comment(self, media_id: int | str, comment_id: int | str) -> Dict[str, Any]:
        """
        Unpin a comment.

        Args:
            media_id: Media PK
            comment_id: Comment PK to unpin
        """
        return self._client.post(
            f"/media/{media_id}/comment/{comment_id}/unpin/",
            rate_category="post_default",
        )

    def report(self, media_id: int | str, reason: int = 1) -> Dict[str, Any]:
        """
        Report a post.

        Args:
            media_id: Media PK
            reason: Reason (1=spam, 2=inappropriate)
        """
        return self._client.post(
            f"/media/{media_id}/flag_media/",
            data={"reason_id": str(reason)},
            rate_category="post_default",
        )

    def unlike_comment(self, comment_id: int | str) -> Dict[str, Any]:
        """
        Unlike a comment.

        Args:
            comment_id: Comment PK
        """
        return self._client.post(
            f"/media/{comment_id}/comment_unlike/",
            rate_category="post_like",
        )

    def save(self, media_id: int | str) -> Dict[str, Any]:
        """
        Save post (bookmark).

        Args:
            media_id: Media PK
        """
        return self._client.post(
            f"/web/save/{media_id}/save/",
            rate_category="post_default",
        )

    def unsave(self, media_id: int | str) -> Dict[str, Any]:
        """
        Remove from bookmarks.

        Args:
            media_id: Media PK
        """
        return self._client.post(
            f"/web/save/{media_id}/unsave/",
            rate_category="post_default",
        )

    # ─── Web Endpoints (with jazoest) ──────────────────────
    #
    # Web endpoints optimized for browser and
    # use jazoest CSRF additional protection token.
    # Formula: jazoest = "2" + sum(ord(c) for c in csrf_token)

    def _get_jazoest(self) -> str:
        """Get jazoest token from current session."""
        return self._client.get_jazoest()

    def web_comment(self, media_id: int | str, text: str) -> Dict[str, Any]:
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
        return self._client.post(
            f"/web/comments/{media_id}/add/",
            data={
                "comment_text": text,
                "jazoest": self._get_jazoest(),
            },
            rate_category="post_comment",
        )

    def web_like(self, media_id: int | str) -> Dict[str, Any]:
        """
        Like via web endpoint ❤️

        /api/v1/web/likes/{media_id}/like/

        Args:
            media_id: Media PK
        """
        return self._client.post(
            f"/web/likes/{media_id}/like/",
            data={"jazoest": self._get_jazoest()},
            rate_category="post_like",
        )

    def web_unlike(self, media_id: int | str) -> Dict[str, Any]:
        """
        Unlike via web endpoint.

        Args:
            media_id: Media PK
        """
        return self._client.post(
            f"/web/likes/{media_id}/unlike/",
            data={"jazoest": self._get_jazoest()},
            rate_category="post_like",
        )

    def web_save(self, media_id: int | str) -> Dict[str, Any]:
        """
        Save post (bookmark) via web endpoint.

        Args:
            media_id: Media PK
        """
        return self._client.post(
            f"/web/save/{media_id}/save/",
            data={"jazoest": self._get_jazoest()},
            rate_category="post_default",
        )

    def web_unsave(self, media_id: int | str) -> Dict[str, Any]:
        """
        Remove bookmark via web endpoint.

        Args:
            media_id: Media PK
        """
        return self._client.post(
            f"/web/save/{media_id}/unsave/",
            data={"jazoest": self._get_jazoest()},
            rate_category="post_default",
        )

    def web_delete_comment(
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
        return self._client.post(
            f"/web/comments/{media_id}/delete/{comment_id}/",
            data={"jazoest": self._get_jazoest()},
            rate_category="post_comment",
        )

