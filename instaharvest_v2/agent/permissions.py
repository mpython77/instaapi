"""
Permission System
=================
3-level permission control for AI Agent actions.

Levels:
    ASK_EVERY   — Ask user before every action
    ASK_ONCE    — Ask once per action type, then remember
    FULL_ACCESS — Never ask, execute everything

Action types:
    READ        — Get profile, posts, followers (safe)
    WRITE       — Like, follow, comment, DM (modifies account)
    EXPORT      — Save files to disk
    CODE_EXEC   — Execute generated code
    DELETE      — Unfollow, delete post (destructive)
"""

import logging
from enum import Enum
from typing import Callable, Dict, Optional, Set

logger = logging.getLogger("instaharvest_v2.agent.permissions")


class Permission(Enum):
    """Permission level for agent actions."""
    ASK_EVERY = "ask_every"
    ASK_ONCE = "ask_once"
    FULL_ACCESS = "full_access"


class ActionType(Enum):
    """Types of actions the agent can perform."""
    READ = "read"
    WRITE = "write"
    EXPORT = "export"
    CODE_EXEC = "code_exec"
    DELETE = "delete"


# Map instaharvest_v2 methods to action types
ACTION_CLASSIFICATION = {
    # READ — safe, information only
    "users.get_by_username": ActionType.READ,
    "users.get_by_id": ActionType.READ,
    "users.search": ActionType.READ,
    "users.get_full_profile": ActionType.READ,
    "users.parse_bio": ActionType.READ,
    "users.get_user_id": ActionType.READ,
    "feed.get_user_feed": ActionType.READ,
    "feed.get_all_posts": ActionType.READ,
    "feed.get_liked": ActionType.READ,
    "feed.get_saved": ActionType.READ,
    "feed.get_tag_feed": ActionType.READ,
    "feed.get_timeline": ActionType.READ,
    "media.get_info": ActionType.READ,
    "media.get_by_shortcode": ActionType.READ,
    "media.get_likers": ActionType.READ,
    "media.get_comments_parsed": ActionType.READ,
    "friendships.get_all_followers": ActionType.READ,
    "friendships.get_all_following": ActionType.READ,
    "friendships.get_mutual_followers": ActionType.READ,
    "stories.get_tray": ActionType.READ,
    "stories.get_user_stories": ActionType.READ,
    "stories.get_highlights_tray": ActionType.READ,
    "search.top_search": ActionType.READ,
    "search.search_users": ActionType.READ,
    "search.search_hashtags": ActionType.READ,
    "search.search_places": ActionType.READ,
    "direct.get_inbox": ActionType.READ,
    "account.get_current_user": ActionType.READ,
    "account.get_blocked_users": ActionType.READ,
    "account.get_login_activity": ActionType.READ,
    "hashtags.get_info": ActionType.READ,
    "insights.get_account_insights": ActionType.READ,
    "notifications.get_activity_feed": ActionType.READ,
    "graphql.get_followers": ActionType.READ,
    "location.search": ActionType.READ,
    "collections.get_list": ActionType.READ,
    "analytics.engagement_rate": ActionType.READ,
    "analytics.best_posting_times": ActionType.READ,
    "analytics.content_analysis": ActionType.READ,
    "analytics.profile_summary": ActionType.READ,
    "analytics.compare": ActionType.READ,
    "public.get_profile": ActionType.READ,
    "public.get_posts": ActionType.READ,

    # WRITE — modifies account state
    "media.like": ActionType.WRITE,
    "media.comment": ActionType.WRITE,
    "media.save": ActionType.WRITE,
    "media.edit_caption": ActionType.WRITE,
    "media.pin_comment": ActionType.WRITE,
    "friendships.follow": ActionType.WRITE,
    "friendships.block": ActionType.WRITE,
    "friendships.mute": ActionType.WRITE,
    "friendships.restrict": ActionType.WRITE,
    "friendships.add_close_friend": ActionType.WRITE,
    "stories.mark_seen": ActionType.WRITE,
    "stories.create_highlight": ActionType.WRITE,
    "stories.react_to_story": ActionType.WRITE,
    "direct.send_text": ActionType.WRITE,
    "direct.send_media": ActionType.WRITE,
    "direct.create_thread": ActionType.WRITE,
    "direct.send_link": ActionType.WRITE,
    "direct.send_reaction": ActionType.WRITE,
    "account.edit_profile": ActionType.WRITE,
    "account.set_private": ActionType.WRITE,
    "account.set_public": ActionType.WRITE,
    "upload.post_photo": ActionType.WRITE,
    "upload.post_video": ActionType.WRITE,
    "upload.post_story_photo": ActionType.WRITE,
    "upload.post_reel": ActionType.WRITE,
    "upload.post_carousel": ActionType.WRITE,
    "automation.dm_new_followers": ActionType.WRITE,
    "automation.comment_on_hashtag": ActionType.WRITE,
    "automation.auto_like_feed": ActionType.WRITE,
    "automation.auto_like_hashtag": ActionType.WRITE,
    "automation.watch_stories": ActionType.WRITE,

    # DELETE — destructive
    "friendships.unfollow": ActionType.DELETE,
    "friendships.remove_follower": ActionType.DELETE,
    "upload.delete_media": ActionType.DELETE,

    # EXPORT — file system writes
    "export.followers_to_csv": ActionType.EXPORT,
    "export.following_to_csv": ActionType.EXPORT,
    "export.to_json": ActionType.EXPORT,
    "export.to_jsonl": ActionType.EXPORT,
    "download.download_media": ActionType.EXPORT,
    "download.download_stories": ActionType.EXPORT,
    "download.download_profile_pic": ActionType.EXPORT,
    "download.download_user_posts": ActionType.EXPORT,
    "pipeline.to_sqlite": ActionType.EXPORT,
    "pipeline.to_jsonl": ActionType.EXPORT,
}


def classify_action(method_name: str) -> ActionType:
    """Classify an instaharvest_v2 method into an action type."""
    if method_name in ACTION_CLASSIFICATION:
        return ACTION_CLASSIFICATION[method_name]
    # Heuristic fallback
    if any(w in method_name for w in ("get_", "search", "list", "info", "parse")):
        return ActionType.READ
    if any(w in method_name for w in ("delete", "remove", "unfollow")):
        return ActionType.DELETE
    if any(w in method_name for w in ("download", "export", "save", "to_csv", "to_json", "to_sqlite")):
        return ActionType.EXPORT
    if any(w in method_name for w in ("post_", "send_", "like", "follow", "comment", "upload", "edit")):
        return ActionType.WRITE
    return ActionType.WRITE  # Default to WRITE (safer)


class PermissionManager:
    """
    Manages permission checks for agent actions.

    Args:
        level: Permission level (ASK_EVERY, ASK_ONCE, FULL_ACCESS)
        prompt_callback: Function to ask user (receives description, returns bool)
    """

    def __init__(
        self,
        level: Permission = Permission.ASK_EVERY,
        prompt_callback: Optional[Callable[[str, str], bool]] = None,
    ):
        self.level = level
        self._prompt = prompt_callback or self._default_prompt
        self._approved_types: Set[ActionType] = set()
        self._denied_types: Set[ActionType] = set()
        self._approved_specific: Set[str] = set()

    def check(self, method_name: str, description: str = "") -> bool:
        """
        Check if an action is permitted.

        Args:
            method_name: instaharvest_v2 method (e.g., "media.like")
            description: Human-readable description of what agent wants to do

        Returns:
            True if permitted, False if denied
        """
        action_type = classify_action(method_name)

        # FULL_ACCESS — always allow
        if self.level == Permission.FULL_ACCESS:
            logger.debug(f"✅ Auto-approved (FULL_ACCESS): {method_name}")
            return True

        # READ actions — always allow (even in ASK_EVERY)
        if action_type == ActionType.READ:
            logger.debug(f"✅ Auto-approved (READ): {method_name}")
            return True

        # ASK_ONCE — check if type already approved
        if self.level == Permission.ASK_ONCE:
            if action_type in self._approved_types:
                logger.debug(f"✅ Previously approved ({action_type.value}): {method_name}")
                return True
            if action_type in self._denied_types:
                logger.debug(f"❌ Previously denied ({action_type.value}): {method_name}")
                return False

        # ASK_EVERY — check if specific action was approved
        if self.level == Permission.ASK_EVERY:
            if method_name in self._approved_specific:
                # Already asked about this exact method in this session
                pass  # Still ask again

        # Ask user
        type_label = {
            ActionType.WRITE: "WRITE",
            ActionType.DELETE: "DELETE",
            ActionType.EXPORT: "EXPORT",
            ActionType.CODE_EXEC: "CODE EXECUTION",
        }.get(action_type, "UNKNOWN")

        desc = description or method_name
        prompt_text = f"{type_label}: {desc}"

        approved = self._prompt(prompt_text, action_type.value)

        if approved:
            if self.level == Permission.ASK_ONCE:
                self._approved_types.add(action_type)
            self._approved_specific.add(method_name)
            logger.info(f"✅ User approved: {method_name}")
        else:
            if self.level == Permission.ASK_ONCE:
                self._denied_types.add(action_type)
            logger.info(f"❌ User denied: {method_name}")

        return approved

    def check_code_execution(self, code: str) -> bool:
        """Check permission for code execution."""
        if self.level == Permission.FULL_ACCESS:
            return True
        if ActionType.CODE_EXEC in self._approved_types:
            return True
        if ActionType.CODE_EXEC in self._denied_types:
            return False

        # Show code preview
        preview = code[:200] + ("..." if len(code) > 200 else "")
        desc = f"Agent wants to execute the following code:\n{preview}"
        approved = self._prompt(desc, ActionType.CODE_EXEC.value)

        if approved and self.level == Permission.ASK_ONCE:
            self._approved_types.add(ActionType.CODE_EXEC)
        elif not approved and self.level == Permission.ASK_ONCE:
            self._denied_types.add(ActionType.CODE_EXEC)

        return approved

    def reset(self) -> None:
        """Reset all remembered permissions."""
        self._approved_types.clear()
        self._denied_types.clear()
        self._approved_specific.clear()

    @staticmethod
    def _default_prompt(description: str, action_type: str) -> bool:
        """Default terminal prompt for permission."""
        print(f"\nAgent is requesting permission:")
        print(f"   {description}")
        while True:
            answer = input("   Allow? [y/n/always]: ").strip().lower()
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            if answer in ("always", "a"):
                return True
            print("   Enter y (yes) / n (no) / always")
