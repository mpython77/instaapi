"""
Tests for Pydantic models: User, UserShort, Media, Comment.
"""

import pytest
from instaapi.models.user import User, UserShort
from instaapi.models.media import Media
from instaapi.models.comment import Comment


class TestUserModel:
    """Test User model creation and factory methods."""

    def test_from_web_profile(self, raw_user_web):
        user = User.from_web_profile(raw_user_web)
        assert user.username == "testuser"
        assert user.full_name == "Test User"
        assert user.followers == 1500
        assert user.following == 300
        assert user.posts_count == 42
        assert user.is_verified is True
        assert user.is_private is False

    def test_dict_access(self, raw_user_web):
        user = User.from_web_profile(raw_user_web)
        assert user["username"] == "testuser"
        assert user["followers"] == 1500

    def test_to_dict(self, raw_user_web):
        user = User.from_web_profile(raw_user_web)
        d = user.to_dict()
        assert isinstance(d, dict)
        assert d["username"] == "testuser"

    def test_extra_fields_preserved(self):
        user = User(
            pk=1, username="test",
            some_new_field="surprise"
        )
        assert user.some_new_field == "surprise"


class TestUserShortModel:
    """Test UserShort model."""

    def test_creation(self):
        user = UserShort(
            pk=123, username="short",
            full_name="Short User",
            is_verified=False,
        )
        assert user.pk == 123
        assert user.username == "short"

    def test_dict_like(self):
        user = UserShort(pk=1, username="test")
        assert user["username"] == "test"


class TestMediaModel:
    """Test Media model and factory methods."""

    def test_from_api(self, raw_media_item):
        media = Media.from_api(raw_media_item)
        assert media.pk == 3456789012345
        assert media.code == "ABC123xyz"
        assert media.media_type == 1
        assert media.like_count == 500
        assert media.comment_count == 25

    def test_caption_text(self, raw_media_item):
        media = Media.from_api(raw_media_item)
        assert media.caption_text == "Test caption 🎉"

    def test_owner_info(self, raw_media_item):
        media = Media.from_api(raw_media_item)
        assert media.user is not None
        assert media.user.username == "testuser"

    def test_image_url(self, raw_media_item):
        media = Media.from_api(raw_media_item)
        assert media.best_image_url != ""
        assert "1080" in media.best_image_url

    def test_dict_access(self, raw_media_item):
        media = Media.from_api(raw_media_item)
        assert media["code"] == "ABC123xyz"

    def test_to_dict(self, raw_media_item):
        media = Media.from_api(raw_media_item)
        d = media.to_dict()
        assert isinstance(d, dict)
        assert d["pk"] == 3456789012345


class TestCommentModel:
    """Test Comment model."""

    def test_from_api(self, raw_comment):
        comment = Comment.from_api(raw_comment)
        assert comment.text == "Great post! 🔥"
        assert comment.like_count == 12

    def test_user_info(self, raw_comment):
        comment = Comment.from_api(raw_comment)
        assert comment.user is not None
        assert comment.user.username == "commenter"
