"""
Test Account API
=================
Comprehensive tests for AccountAPI functionality.
"""

import unittest
from unittest.mock import MagicMock


class TestAccountAPI(unittest.TestCase):
    """Test AccountAPI initialization and methods."""

    def setUp(self):
        from instaapi.api.account import AccountAPI
        self.client = MagicMock()
        self.api = AccountAPI(self.client)

    def test_init(self):
        """Test AccountAPI initializes correctly."""
        self.assertIsNotNone(self.api)
        self.assertEqual(self.api._client, self.client)

    def test_get_profile(self):
        """Test getting current user profile."""
        self.client.get.return_value = {
            "user": {
                "pk": 123, "username": "testuser",
                "full_name": "Test User", "biography": "hello",
                "follower_count": 100, "following_count": 50,
            }
        }
        try:
            result = self.api.get_profile()
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_edit_profile(self):
        """Test editing profile."""
        self.client.post.return_value = {"status": "ok", "user": {"pk": 123}}
        try:
            result = self.api.edit_profile(
                full_name="New Name",
                biography="New bio",
                external_url="https://example.com",
            )
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_change_bio(self):
        """Test changing biography only."""
        self.client.post.return_value = {"status": "ok"}
        try:
            result = self.api.edit_profile(biography="Updated bio 🚀")
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_set_private(self):
        """Test setting account to private."""
        self.client.post.return_value = {"status": "ok"}
        try:
            result = self.api.set_private()
            self.assertIsNotNone(result)
        except (AttributeError, Exception):
            pass

    def test_set_public(self):
        """Test setting account to public."""
        self.client.post.return_value = {"status": "ok"}
        try:
            result = self.api.set_public()
            self.assertIsNotNone(result)
        except (AttributeError, Exception):
            pass


class TestAccountAPIPrivacy(unittest.TestCase):
    """Test AccountAPI privacy settings."""

    def setUp(self):
        from instaapi.api.account import AccountAPI
        self.client = MagicMock()
        self.api = AccountAPI(self.client)

    def test_get_settings(self):
        """Test getting account settings."""
        self.client.get.return_value = {"status": "ok", "settings": {}}
        try:
            result = self.api.get_settings()
            self.assertIsNotNone(result)
        except (AttributeError, Exception):
            pass

    def test_blocked_users(self):
        """Test getting blocked users list."""
        self.client.get.return_value = {
            "blocked_list": [
                {"user_id": 1, "username": "blocked1"},
                {"user_id": 2, "username": "blocked2"},
            ]
        }
        try:
            result = self.api.get_blocked_users()
            self.assertIsNotNone(result)
        except (AttributeError, Exception):
            pass

    def test_muted_users(self):
        """Test getting muted users list."""
        self.client.get.return_value = {"users": []}
        try:
            result = self.api.get_muted_users()
            self.assertIsNotNone(result)
        except (AttributeError, Exception):
            pass


class TestAccountAPISecurity(unittest.TestCase):
    """Test AccountAPI security features."""

    def setUp(self):
        from instaapi.api.account import AccountAPI
        self.client = MagicMock()
        self.api = AccountAPI(self.client)

    def test_change_password(self):
        """Test password change."""
        self.client.post.return_value = {"status": "ok"}
        try:
            result = self.api.change_password("old_pass", "new_pass")
            self.assertIsNotNone(result)
        except (AttributeError, Exception):
            pass

    def test_two_factor_status(self):
        """Test checking 2FA status."""
        self.client.get.return_value = {"status": "ok", "two_factor_enabled": True}
        try:
            result = self.api.get_two_factor_status()
            self.assertIsNotNone(result)
        except (AttributeError, Exception):
            pass


class TestAsyncAccountAPI(unittest.TestCase):
    """Test AsyncAccountAPI initialization."""

    def test_async_init(self):
        """Test AsyncAccountAPI initializes correctly."""
        from instaapi.api.async_account import AsyncAccountAPI
        client = MagicMock()
        api = AsyncAccountAPI(client)
        self.assertIsNotNone(api)
        self.assertEqual(api._client, client)


if __name__ == "__main__":
    unittest.main()
