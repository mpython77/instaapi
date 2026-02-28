"""
Account API
============
Account management: profile editing, picture change, privacy.
"""

import json
from typing import Any, Dict, Optional

from ..client import HttpClient


class AccountAPI:
    """Instagram account management API"""

    def __init__(self, client: HttpClient):
        self._client = client

    def get_current_user(self) -> Dict[str, Any]:
        """
        Current (logged in) account data.
        Web-compatible: uses /users/web_profile_info/.

        Returns:
            Full profile data of the current user
        """
        try:
            sess = self._client.get_session()
            # Method 1: web_profile_info with username (most reliable)
            if sess and sess.ds_user_id:
                # Try fetching via web_profile_info
                try:
                    data = self._client.get(
                        "/users/web_profile_info/",
                        params={"username": getattr(sess, '_username', '')},
                        rate_category="get_profile",
                    )
                    user_data = data.get("data", {}).get("user", {})
                    if user_data and user_data.get("username"):
                        return user_data
                except Exception:
                    pass

                # Method 2: REST /accounts/current_user/
                try:
                    data = self._client.get(
                        "/accounts/current_user/?edit=true",
                        rate_category="get_profile",
                    )
                    return data.get("user", data)
                except Exception:
                    pass

                # Method 3: user info by ID
                try:
                    data = self._client.get(
                        f"/users/{sess.ds_user_id}/info/",
                        rate_category="get_profile",
                    )
                    return data.get("user", data)
                except Exception:
                    pass

            return {"status": "fail", "message": "current_user requires active web session"}
        except Exception:
            return {"status": "fail", "message": "current_user requires active web session"}

    def edit_profile(
        self,
        biography: Optional[str] = None,
        full_name: Optional[str] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
        phone_number: Optional[str] = None,
        external_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Edit profile.

        Args:
            biography: New bio
            full_name: New name
            username: New username
            email: New email
            phone_number: New phone number
            external_url: New website URL
        """
        # First get current info
        current = self.get_current_user()

        form_data = {
            "biography": biography if biography is not None else current.get("biography", ""),
            "first_name": full_name if full_name is not None else current.get("full_name", ""),
            "username": username if username is not None else current.get("username", ""),
            "email": email if email is not None else current.get("email", ""),
            "phone_number": phone_number if phone_number is not None else current.get("phone_number", ""),
            "external_url": external_url if external_url is not None else current.get("external_url", ""),
        }

        return self._client.post(
            "/accounts/edit/",
            data=form_data,
            rate_category="post_default",
        )

    def change_profile_picture(self, image_data: bytes) -> Dict[str, Any]:
        """
        Change profile picture.

        Args:
            image_data: Image bytes (JPEG/PNG)
        """
        # This endpoint requires multipart/form-data
        # For now, simple POST with
        return self._client.post(
            "/accounts/change_profile_picture/",
            data={"profile_pic": image_data},
            rate_category="post_default",
        )

    def set_private(self) -> Dict[str, Any]:
        """Set account to private."""
        return self._client.post(
            "/accounts/set_private/",
            rate_category="post_default",
        )

    def set_public(self) -> Dict[str, Any]:
        """Set account to public."""
        return self._client.post(
            "/accounts/set_public/",
            rate_category="post_default",
        )

    def get_privacy_settings(self) -> Dict[str, Any]:
        """
        Privacy settings.

        Returns:
            Privacy and security data
        """
        return self._client.get(
            "/accounts/privacy_and_security_info/",
            rate_category="get_default",
        )

    # ─── ADDITIONAL ─────────────────────────────────────────

    def get_blocked_users(self) -> Dict[str, Any]:
        """
        Blocked users list.

        Returns:
            dict: {blocked_list: [{user_id, username, ...}]}
        """
        return self._client.get(
            "/users/blocked_list/",
            rate_category="get_default",
        )

    def get_restricted_users(self) -> Dict[str, Any]:
        """
        Restricted users.

        Returns:
            dict: {users: [...]}
        """
        return self._client.get(
            "/restrict_action/restricted_users/",
            rate_category="get_default",
        )

    def delete_profile_picture(self) -> Dict[str, Any]:
        """Delete profile picture (reset to default)."""
        return self._client.post(
            "/accounts/remove_profile_picture/",
            rate_category="post_default",
        )

    def get_login_activity(self) -> Dict[str, Any]:
        """
        Login history (where and when accessed).

        Returns:
            dict: Login sessions list
        """
        return self._client.get(
            "/session/login_activity/",
            rate_category="get_default",
        )

    def get_account_info(self) -> Dict[str, Any]:
        """
        Account phone/email/birthday.

        Returns:
            dict: Personal information
        """
        return self._client.get(
            "/accounts/account_information_settings/",
            rate_category="get_default",
        )
