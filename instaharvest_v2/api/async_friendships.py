"""
Friendships API
===============
Follow, unfollow, block, followers/following lists, friendship status.
"""

from typing import Any, Dict, List, Optional
import json

from ..async_client import AsyncHttpClient
from ..models.user import UserShort


class AsyncFriendshipsAPI:
    """Instagram Friendships API"""

    def __init__(self, client: AsyncHttpClient):
        self._client = client

    async def get_followers(
        self,
        user_id: int | str,
        count: int = 50,
        max_id: Optional[str] = None,
        search_surface: str = "",
    ) -> Dict[str, Any]:
        """
        Followers list.

        Args:
            user_id: User PK
            count: How many to get
            max_id: Pagination cursor

        Returns:
            Followers and pagination
        """
        params = {"count": str(count)}
        if max_id:
            params["max_id"] = max_id
        if search_surface:
            params["search_surface"] = search_surface

        return await self._client.get(
            f"/friendships/{user_id}/followers/",
            params=params,
            rate_category="get_followers",
        )

    async def get_all_followers(
        self,
        user_id: int | str,
        max_count: int = 1000,
        count_per_page: int = 50,
    ) -> List[UserShort]:
        """
        Get all followers (with pagination).

        Args:
            user_id: User PK
            max_count: Maximum count
            count_per_page: Per page

        Returns:
            List of UserShort models
        """
        all_followers = []
        max_id = None

        while len(all_followers) < max_count:
            data = await self.get_followers(user_id, count=count_per_page, max_id=max_id)
            users = data.get("users", [])
            all_followers.extend([UserShort(**u) for u in users])

            if not data.get("has_more"):
                break

            max_id = data.get("next_max_id")
            if not max_id:
                break

        return all_followers[:max_count]

    async def get_following(
        self,
        user_id: int | str,
        count: int = 50,
        max_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Following list.

        Args:
            user_id: User PK
            count: How many to get
            max_id: Pagination cursor

        Returns:
            Following list and pagination
        """
        params = {"count": str(count)}
        if max_id:
            params["max_id"] = max_id

        return await self._client.get(
            f"/friendships/{user_id}/following/",
            params=params,
            rate_category="get_followers",
        )

    async def get_all_following(
        self,
        user_id: int | str,
        max_count: int = 1000,
        count_per_page: int = 50,
    ) -> List[UserShort]:
        """
        Get all following.

        Args:
            user_id: User PK
            max_count: Maximum count

        Returns:
            List of UserShort models
        """
        all_following = []
        max_id = None

        while len(all_following) < max_count:
            data = await self.get_following(user_id, count=count_per_page, max_id=max_id)
            users = data.get("users", [])
            all_following.extend([UserShort(**u) for u in users])

            if not data.get("has_more"):
                break

            max_id = data.get("next_max_id")
            if not max_id:
                break

        return all_following[:max_count]

    async def show(self, user_id: int | str) -> Dict[str, Any]:
        """
        Relationship between me and user.
        (did I follow? did they follow me? did I block?)

        Args:
            user_id: User PK

        Returns:
            Friendship state (following, followed_by, blocking, ...)
        """
        return await self._client.get(
            f"/friendships/show/{user_id}/",
            rate_category="get_default",
        )

    async def follow(self, user_id: int | str) -> Dict[str, Any]:
        """
        Follow a user.

        Args:
            user_id: User PK
        """
        return await self._client.post(
            f"/web/friendships/{user_id}/follow/",
            rate_category="post_follow",
        )

    async def unfollow(self, user_id: int | str) -> Dict[str, Any]:
        """
        Unfollow a user.

        Args:
            user_id: User PK
        """
        return await self._client.post(
            f"/web/friendships/{user_id}/unfollow/",
            rate_category="post_follow",
        )

    async def block(self, user_id: int | str) -> Dict[str, Any]:
        """
        Block a user.

        Args:
            user_id: User PK
        """
        return await self._client.post(
            f"/web/friendships/{user_id}/block/",
            rate_category="post_default",
        )

    async def unblock(self, user_id: int | str) -> Dict[str, Any]:
        """
        Unblock a user.

        Args:
            user_id: User PK
        """
        return await self._client.post(
            f"/web/friendships/{user_id}/unblock/",
            rate_category="post_default",
        )

    # ─── FOLLOWER MANAGEMENT ─────────────────────────────────

    async def remove_follower(self, user_id: int | str) -> Dict[str, Any]:
        """
        Remove a follower (someone who follows you).

        Args:
            user_id: User PK
        """
        return await self._client.post(
            f"/web/friendships/{user_id}/remove_follower/",
            rate_category="post_follow",
        )

    async def get_pending_requests(self) -> Dict[str, Any]:
        """
        Pending follow requests (for private accounts).

        Returns:
            dict: {users: [...], status}
        """
        return await self._client.get(
            "/friendships/pending/",
            rate_category="get_default",
        )

    async def approve_request(self, user_id: int | str) -> Dict[str, Any]:
        """
        Approve follow request.

        Args:
            user_id: PK of user who sent the request
        """
        return await self._client.post(
            f"/web/friendships/{user_id}/approve/",
            rate_category="post_follow",
        )

    async def reject_request(self, user_id: int | str) -> Dict[str, Any]:
        """
        Reject follow request.

        Args:
            user_id: PK of user who sent the request
        """
        return await self._client.post(
            f"/web/friendships/{user_id}/ignore/",
            rate_category="post_follow",
        )

    # ─── MUTE / RESTRICT ────────────────────────────────────

    async def mute(self, user_id: int | str, mute_posts: bool = True, mute_stories: bool = True) -> Dict[str, Any]:
        """
        Mute a user.

        Args:
            user_id: User PK
            mute_posts: Hide posts
            mute_stories: Hide stories
        """
        data = {"target_user_id": str(user_id)}
        if mute_posts:
            data["target_posts_author_id"] = str(user_id)
        if mute_stories:
            data["target_reel_author_id"] = str(user_id)
        return await self._client.post(
            f"/friendships/mute_posts_or_story_from_follow/",
            data=data,
            rate_category="post_default",
        )

    async def unmute(self, user_id: int | str, unmute_posts: bool = True, unmute_stories: bool = True) -> Dict[str, Any]:
        """
        Unmute a user.

        Args:
            user_id: User PK
            unmute_posts: Show posts
            unmute_stories: Show stories
        """
        data = {"target_user_id": str(user_id)}
        if unmute_posts:
            data["target_posts_author_id"] = str(user_id)
        if unmute_stories:
            data["target_reel_author_id"] = str(user_id)
        return await self._client.post(
            f"/friendships/unmute_posts_or_story_from_follow/",
            data=data,
            rate_category="post_default",
        )

    async def restrict(self, user_id: int | str) -> Dict[str, Any]:
        """
        Restrict a user.

        Args:
            user_id: User PK
        """
        return await self._client.post(
            "/restrict_action/restrict/",
            data={"target_user_id": str(user_id)},
            rate_category="post_default",
        )

    async def unrestrict(self, user_id: int | str) -> Dict[str, Any]:
        """
        Unrestrict a user.

        Args:
            user_id: User PK
        """
        return await self._client.post(
            "/restrict_action/unrestrict/",
            data={"target_user_id": str(user_id)},
            rate_category="post_default",
        )

    # ─── CLOSE FRIENDS ──────────────────────────────────────

    async def get_close_friends(self) -> Dict[str, Any]:
        """
        Close friends list.

        Returns:
            dict: {users: [...]}
        """
        return await self._client.get(
            "/friendships/besties/",
            rate_category="get_default",
        )

    async def add_close_friend(self, user_id: int | str) -> Dict[str, Any]:
        """
        Add to close friends.

        Args:
            user_id: User PK
        """
        return await self._client.post(
            "/friendships/set_besties/",
            data={"add": json.dumps([str(user_id)]), "remove": json.dumps([])},
            rate_category="post_default",
        )

    async def remove_close_friend(self, user_id: int | str) -> Dict[str, Any]:
        """
        Remove from close friends.

        Args:
            user_id: User PK
        """
        return await self._client.post(
            "/friendships/set_besties/",
            data={"add": json.dumps([]), "remove": json.dumps([str(user_id)])},
            rate_category="post_default",
        )

    async def get_mutual_followers(self, user_id: int | str) -> Dict[str, Any]:
        """
        Mutual followers (people you both follow).

        Args:
            user_id: User PK

        Returns:
            dict: {users: [...], status}
        """
        return await self._client.get(
            f"/friendships/{user_id}/mutual_followers/",
            rate_category="get_default",
        )

    # ─── CLOSE FRIENDS (extended) ────────────────────────────

    async def set_close_friends(
        self,
        add_user_ids: Optional[List[int | str]] = None,
        remove_user_ids: Optional[List[int | str]] = None,
    ) -> Dict[str, Any]:
        """
        Batch add/remove close friends in one API call.

        Args:
            add_user_ids: User IDs to add
            remove_user_ids: User IDs to remove

        Returns:
            API response dict
        """
        add_ids = [str(uid) for uid in (add_user_ids or [])]
        remove_ids = [str(uid) for uid in (remove_user_ids or [])]
        return await self._client.post(
            "/friendships/set_besties/",
            data={
                "add": json.dumps(add_ids),
                "remove": json.dumps(remove_ids),
            },
            rate_category="post_default",
        )

    async def is_close_friend(self, user_id: int | str) -> bool:
        """
        Check if a user is in your close friends list.

        Args:
            user_id: User PK

        Returns:
            True if user is in close friends
        """
        status = await self.show(user_id)
        return status.get("is_bestie", False)

    async def get_close_friends_suggestions(
        self,
        max_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get suggested users to add to close friends.

        Args:
            max_id: Pagination cursor

        Returns:
            dict: {users: [...], next_max_id, status}
        """
        params = {}
        if max_id:
            params["max_id"] = max_id
        return await self._client.get(
            "/friendships/besties_suggestions/",
            params=params or None,
            rate_category="get_default",
        )

    async def get_all_close_friends(
        self,
        max_count: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Get full close friends list with pagination.

        Args:
            max_count: Maximum number of users to fetch

        Returns:
            List of close friend user dicts
        """
        all_users = []
        max_id = None

        while len(all_users) < max_count:
            result = await self._client.get(
                "/friendships/besties/",
                params={"max_id": max_id} if max_id else None,
                rate_category="get_default",
            )
            users = result.get("users", [])
            if not users:
                break
            all_users.extend(users)
            max_id = result.get("next_max_id")
            if not max_id:
                break

        return all_users[:max_count]
