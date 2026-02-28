"""
Pytest fixtures for InstaAPI tests.
"""

import pytest
from instaharvest_v2.models.user import User, UserShort
from instaharvest_v2.models.media import Media
from instaharvest_v2.models.comment import Comment


# ─── Sample Data ─────────────────────────────────────────────

@pytest.fixture
def raw_user_web():
    """Raw user data from web_profile_info endpoint."""
    return {
        "id": "123456789",
        "username": "testuser",
        "full_name": "Test User",
        "biography": "Hello world 🌍\nLink: example.com",
        "edge_followed_by": {"count": 1500},
        "edge_follow": {"count": 300},
        "edge_owner_to_timeline_media": {"count": 42},
        "is_private": False,
        "is_verified": True,
        "profile_pic_url_hd": "https://example.com/pic.jpg",
        "external_url": "https://example.com",
    }


@pytest.fixture
def raw_user_api():
    """Raw user data from /users/{pk}/info/ endpoint."""
    return {
        "user": {
            "pk": 123456789,
            "username": "testuser",
            "full_name": "Test User",
            "biography": "Hello world",
            "follower_count": 1500,
            "following_count": 300,
            "media_count": 42,
            "is_private": False,
            "is_verified": True,
            "profile_pic_url": "https://example.com/pic.jpg",
        }
    }


@pytest.fixture
def raw_media_item():
    """Raw media item from API."""
    return {
        "pk": 3456789012345,
        "id": "3456789012345_123456789",
        "code": "ABC123xyz",
        "media_type": 1,
        "taken_at": 1708000000,
        "caption": {
            "text": "Test caption 🎉",
            "pk": "111222333",
        },
        "like_count": 500,
        "comment_count": 25,
        "user": {
            "pk": 123456789,
            "username": "testuser",
            "full_name": "Test User",
            "is_verified": True,
            "profile_pic_url": "https://example.com/pic.jpg",
        },
        "image_versions2": {
            "candidates": [
                {"url": "https://example.com/img_1080.jpg", "width": 1080, "height": 1080},
                {"url": "https://example.com/img_640.jpg", "width": 640, "height": 640},
            ]
        },
    }


@pytest.fixture
def raw_comment():
    """Raw comment from API."""
    return {
        "pk": "17890012345",
        "text": "Great post! 🔥",
        "created_at": 1708001000,
        "user": {
            "pk": 987654321,
            "username": "commenter",
            "full_name": "Comment User",
            "is_verified": False,
            "profile_pic_url": "https://example.com/commenter.jpg",
        },
        "comment_like_count": 12,
        "child_comment_count": 3,
    }


@pytest.fixture
def challenge_response_email():
    """Challenge response with email verification."""
    return {
        "step_name": "select_verify_method",
        "step_data": {
            "contact_point": "t***@gmail.com",
            "email": "t***@gmail.com",
        },
        "challenge_context": "email challenge",
        "status": "ok",
    }


@pytest.fixture
def challenge_response_sms():
    """Challenge response with SMS verification."""
    return {
        "step_name": "verify_phone",
        "step_data": {
            "contact_point": "+1 *** ***42",
            "phone_number": "+1 *** ***42",
        },
        "status": "ok",
    }
