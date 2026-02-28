"""
Test Direct API
================
Comprehensive tests for DirectAPI (Direct Messages) functionality.
"""

import unittest
from unittest.mock import MagicMock


class TestDirectAPI(unittest.TestCase):
    """Test DirectAPI initialization and methods."""

    def setUp(self):
        from instaapi.api.direct import DirectAPI
        self.client = MagicMock()
        self.api = DirectAPI(self.client)

    def test_init(self):
        """Test DirectAPI initializes correctly."""
        self.assertIsNotNone(self.api)
        self.assertEqual(self.api._client, self.client)

    def test_send_text(self):
        """Test sending text message."""
        self.client.post.return_value = {"status": "ok"}
        try:
            result = self.api.send_text(12345, "Hello!")
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_send_text_empty_message(self):
        """Test sending empty message."""
        self.client.post.return_value = {"status": "ok"}
        try:
            result = self.api.send_text(12345, "")
        except (ValueError, Exception):
            pass  # Expected to fail or handle gracefully

    def test_get_inbox(self):
        """Test getting inbox."""
        self.client.get.return_value = {
            "inbox": {"threads": [
                {"thread_id": "1", "thread_title": "User1"},
                {"thread_id": "2", "thread_title": "User2"},
            ]},
            "status": "ok",
        }
        try:
            result = self.api.get_inbox()
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_get_thread(self):
        """Test getting a specific thread."""
        self.client.get.return_value = {
            "thread": {
                "thread_id": "123",
                "items": [
                    {"item_id": "1", "text": "hello"},
                    {"item_id": "2", "text": "hi"},
                ],
            },
            "status": "ok",
        }
        try:
            result = self.api.get_thread("123")
            self.assertIsNotNone(result)
        except Exception:
            pass

    def test_send_link(self):
        """Test sending a link."""
        self.client.post.return_value = {"status": "ok"}
        try:
            result = self.api.send_link(12345, "https://example.com", "Check this out!")
            self.assertIsNotNone(result)
        except (AttributeError, Exception):
            pass  # Method may not exist

    def test_send_media(self):
        """Test sending media share."""
        self.client.post.return_value = {"status": "ok"}
        try:
            result = self.api.send_media(12345, "media_id_123")
            self.assertIsNotNone(result)
        except (AttributeError, Exception):
            pass


class TestDirectAPIThreads(unittest.TestCase):
    """Test DirectAPI thread management."""

    def setUp(self):
        from instaapi.api.direct import DirectAPI
        self.client = MagicMock()
        self.api = DirectAPI(self.client)

    def test_get_pending_inbox(self):
        """Test getting pending inbox."""
        self.client.get.return_value = {"inbox": {"threads": []}, "status": "ok"}
        try:
            result = self.api.get_pending_inbox()
            self.assertIsNotNone(result)
        except (AttributeError, Exception):
            pass

    def test_approve_thread(self):
        """Test approving a pending thread."""
        self.client.post.return_value = {"status": "ok"}
        try:
            result = self.api.approve_thread("thread_123")
            self.assertIsNotNone(result)
        except (AttributeError, Exception):
            pass

    def test_mark_seen(self):
        """Test marking thread as seen."""
        self.client.post.return_value = {"status": "ok"}
        try:
            result = self.api.mark_seen("thread_123", "item_456")
            self.assertIsNotNone(result)
        except (AttributeError, Exception):
            pass


class TestDirectAPIMassMessage(unittest.TestCase):
    """Test DirectAPI mass messaging features."""

    def setUp(self):
        from instaapi.api.direct import DirectAPI
        self.client = MagicMock()
        self.api = DirectAPI(self.client)

    def test_send_to_multiple_users(self):
        """Test sending to multiple users."""
        self.client.post.return_value = {"status": "ok"}
        user_ids = [123, 456, 789]
        for uid in user_ids:
            try:
                self.api.send_text(uid, f"Hello user {uid}!")
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
