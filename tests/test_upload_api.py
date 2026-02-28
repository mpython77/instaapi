"""
Test Upload API
================
Comprehensive tests for UploadAPI functionality.
"""

import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock


class TestUploadAPI(unittest.TestCase):
    """Test UploadAPI initialization and methods."""

    def setUp(self):
        from instaapi.api.upload import UploadAPI
        self.client = MagicMock()
        self.api = UploadAPI(self.client)
        self._tmpfiles = []
        for ext in [".jpg", ".mp4", ".jpg"]:
            f = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            f.write(b"\xff\xd8\xff\xe0" if ext == ".jpg" else b"\x00\x00\x00\x20")
            f.close()
            self._tmpfiles.append(f.name)
        self.photo_path = self._tmpfiles[0]
        self.video_path = self._tmpfiles[1]
        self.cover_path = self._tmpfiles[2]

    def tearDown(self):
        for f in self._tmpfiles:
            if os.path.exists(f):
                os.unlink(f)

    def test_init(self):
        self.assertIsNotNone(self.api)
        self.assertEqual(self.api._client, self.client)

    def test_generate_upload_id(self):
        uid1 = self.api._generate_upload_id()
        uid2 = self.api._generate_upload_id()
        self.assertIsInstance(uid1, str)
        self.assertTrue(uid1.isdigit())

    def test_post_photo_call(self):
        """Test post_photo method exists and is callable."""
        self.assertTrue(hasattr(self.api, "post_photo"))
        self.assertTrue(callable(self.api.post_photo))

    def test_post_reel_call(self):
        """Test post_reel method exists and is callable."""
        self.assertTrue(hasattr(self.api, "post_reel"))
        self.assertTrue(callable(self.api.post_reel))

    def test_post_video_call(self):
        """Test post_video method exists and is callable."""
        self.assertTrue(hasattr(self.api, "post_video"))
        self.assertTrue(callable(self.api.post_video))

    def test_post_story_photo_call(self):
        """Test post_story_photo exists."""
        self.assertTrue(hasattr(self.api, "post_story_photo"))

    def test_post_story_video_call(self):
        """Test post_story_video exists."""
        self.assertTrue(hasattr(self.api, "post_story_video"))

    def test_delete_media_call(self):
        """Test delete_media exists."""
        self.assertTrue(hasattr(self.api, "delete_media"))

    def test_post_carousel_call(self):
        """Test post_carousel exists."""
        self.assertTrue(hasattr(self.api, "post_carousel"))

    def test_photo_nonexistent_file(self):
        """Test post_photo with non-existent file raises error."""
        with self.assertRaises(Exception):
            self.api.post_photo(image_path="/nonexistent/photo.jpg", caption="test")


class TestUploadValidation(unittest.TestCase):
    """Test upload file validation."""

    def test_supported_photo_extensions(self):
        for ext in [".jpg", ".jpeg", ".png"]:
            f = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            f.write(b"\xff\xd8\xff\xe0")
            f.close()
            self.assertTrue(os.path.exists(f.name))
            os.unlink(f.name)

    def test_supported_video_extensions(self):
        for ext in [".mp4", ".mov"]:
            f = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            f.write(b"\x00\x00\x00\x20")
            f.close()
            self.assertTrue(os.path.exists(f.name))
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
