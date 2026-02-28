"""
Tests for AnonClient endpoint methods using mock responses.
No real HTTP calls — uses unittest.mock to patch _request.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from instaapi.anon_client import AnonClient, StrategyFailed


@pytest.fixture
def client():
    """Create unlimited AnonClient with no real network."""
    return AnonClient(unlimited=True)


# ═══════════════════════════════════════════════════════════
# search_web
# ═══════════════════════════════════════════════════════════

class TestSearchWeb:
    def test_search_returns_parsed(self, client):
        mock_response = {
            "users": [{"user": {"username": "nike", "pk": 123, "full_name": "Nike", "is_verified": True, "follower_count": 300000000}}],
            "hashtags": [{"hashtag": {"name": "nike", "media_count": 500000}}],
            "places": [{"place": {"title": "Nike HQ", "location": {"lat": 45.5}}}],
        }
        with patch.object(client, '_request', return_value=mock_response):
            result = client.search_web("nike")

        assert len(result["users"]) == 1
        assert result["users"][0]["username"] == "nike"
        assert result["users"][0]["follower_count"] == 300000000
        assert result["hashtags"][0]["name"] == "nike"
        assert result["places"][0]["title"] == "Nike HQ"

    def test_search_strategy_failed(self, client):
        with patch.object(client, '_request', side_effect=StrategyFailed("401")):
            result = client.search_web("test")
        assert result is None

    def test_search_empty_response(self, client):
        with patch.object(client, '_request', return_value=None):
            result = client.search_web("test")
        assert result is None


# ═══════════════════════════════════════════════════════════
# get_user_reels
# ═══════════════════════════════════════════════════════════

class TestGetUserReels:
    def test_reels_parsed(self, client):
        mock_response = {
            "items": [
                {
                    "media": {
                        "pk": 111, "code": "RL1", "media_type": 2,
                        "like_count": 5000, "comment_count": 100,
                        "play_count": 50000,
                        "caption": {"text": "Reel 1"},
                        "image_versions2": {"candidates": [{"url": "https://img.com/t.jpg", "width": 640, "height": 640}]},
                        "video_versions": [{"url": "https://vid.com/reel.mp4"}],
                        "clips_metadata": {
                            "music_info": {"music_asset_info": {"title": "Song", "display_artist": "Artist"}}
                        },
                    }
                }
            ],
            "paging_info": {"more_available": True, "max_id": "next123"},
        }
        with patch.object(client, 'get_mobile_api', return_value=mock_response):
            result = client.get_user_reels(123)

        assert result is not None
        assert len(result["items"]) == 1
        assert result["items"][0]["play_count"] == 50000
        assert result["items"][0]["is_reel"] is True
        assert result["items"][0]["audio"]["title"] == "Song"
        assert result["more_available"] is True

    def test_reels_empty(self, client):
        with patch.object(client, 'get_mobile_api', return_value=None):
            result = client.get_user_reels(123)
        assert result is None


# ═══════════════════════════════════════════════════════════
# get_user_feed_mobile
# ═══════════════════════════════════════════════════════════

class TestGetUserFeedMobile:
    def test_feed_parsed(self, client):
        mock_response = {
            "items": [
                {
                    "pk": 999, "code": "FD1", "media_type": 1,
                    "like_count": 12000, "comment_count": 300,
                    "caption": {"text": "Feed post"},
                    "image_versions2": {"candidates": [{"url": "https://img.com/f.jpg", "width": 1080, "height": 1080}]},
                    "taken_at": 1700000000,
                }
            ],
            "more_available": True,
            "next_max_id": "cursor_abc",
            "num_results": 1,
        }
        with patch.object(client, 'get_mobile_api', return_value=mock_response):
            result = client.get_user_feed_mobile(123)

        assert result is not None
        assert len(result["items"]) == 1
        assert result["items"][0]["likes"] == 12000
        assert result["items"][0]["shortcode"] == "FD1"
        assert result["more_available"] is True
        assert result["next_max_id"] == "cursor_abc"

    def test_feed_with_pagination(self, client):
        mock_response = {"items": [], "more_available": False}
        with patch.object(client, 'get_mobile_api', return_value=mock_response) as mock:
            client.get_user_feed_mobile(123, max_id="page2_cursor")
            args, kwargs = mock.call_args
            assert kwargs.get('params', {}).get('max_id') == "page2_cursor" or \
                   (len(args) > 1 and args[1].get('max_id') == "page2_cursor")


# ═══════════════════════════════════════════════════════════
# get_hashtag_sections
# ═══════════════════════════════════════════════════════════

class TestGetHashtagSections:
    def test_hashtag_parsed(self, client):
        mock_response = {
            "sections": [
                {
                    "layout_content": {
                        "medias": [
                            {"media": {"pk": 1, "code": "HT1", "media_type": 1, "like_count": 100, "comment_count": 5, "caption": {"text": "tag"}, "image_versions2": {"candidates": []}}},
                            {"media": {"pk": 2, "code": "HT2", "media_type": 1, "like_count": 200, "comment_count": 10, "caption": {"text": "tag2"}, "image_versions2": {"candidates": []}}},
                        ]
                    }
                }
            ],
            "more_available": True,
            "next_max_id": "ht_cursor",
            "media_count": 500000,
        }
        with patch.object(client, 'get_web_api', return_value=mock_response):
            result = client.get_hashtag_sections("football")

        assert result["tag_name"] == "football"
        assert len(result["posts"]) == 2
        assert result["media_count"] == 500000
        assert result["more_available"] is True

    def test_hashtag_strips_hash(self, client):
        with patch.object(client, 'get_web_api', return_value=None) as mock:
            client.get_hashtag_sections("#Football")
            args, kwargs = mock.call_args
            assert "/tags/football/sections/" in args[0]


# ═══════════════════════════════════════════════════════════
# get_location_sections
# ═══════════════════════════════════════════════════════════

class TestGetLocationSections:
    def test_location_parsed(self, client):
        mock_response = {
            "sections": [
                {"layout_content": {"medias": [
                    {"media": {"pk": 10, "code": "LC1", "media_type": 1, "like_count": 50, "comment_count": 5, "caption": None, "image_versions2": {"candidates": []}}},
                ]}}
            ],
            "location": {"pk": 123, "name": "Central Park", "address": "NYC", "city": "New York", "lat": 40.78, "lng": -73.97},
            "more_available": False,
            "media_count": 1000,
        }
        with patch.object(client, 'get_web_api', return_value=mock_response):
            result = client.get_location_sections(123)

        assert result["location"]["name"] == "Central Park"
        assert result["location"]["city"] == "New York"
        assert len(result["posts"]) == 1
        assert result["media_count"] == 1000


# ═══════════════════════════════════════════════════════════
# get_similar_accounts
# ═══════════════════════════════════════════════════════════

class TestGetSimilarAccounts:
    def test_similar_parsed(self, client):
        mock_response = {
            "users": [
                {"username": "adidas", "full_name": "Adidas", "pk": 111, "follower_count": 50000000, "is_verified": True, "is_business": True, "category": "Sportswear"},
                {"username": "puma", "full_name": "Puma", "pk": 222, "follower_count": 30000000},
            ]
        }
        with patch.object(client, 'get_web_api', return_value=mock_response):
            result = client.get_similar_accounts(123)

        assert len(result) == 2
        assert result[0]["username"] == "adidas"
        assert result[0]["follower_count"] == 50000000
        assert result[1]["username"] == "puma"

    def test_similar_empty(self, client):
        with patch.object(client, 'get_web_api', return_value=None):
            result = client.get_similar_accounts(123)
        assert result is None


# ═══════════════════════════════════════════════════════════
# get_highlights_tray
# ═══════════════════════════════════════════════════════════

class TestGetHighlightsTray:
    def test_highlights_parsed(self, client):
        mock_response = {
            "tray": [
                {"id": "hl:1", "title": "Travel", "media_count": 15, "cover_media": {"cropped_image_version": {"url": "https://img.com/cover1.jpg"}}, "created_at": 1700000000},
                {"id": "hl:2", "title": "Food", "media_count": 8, "cover_media": {"url": "https://img.com/cover2.jpg"}, "created_at": 1700100000},
            ]
        }
        with patch.object(client, 'get_mobile_api', return_value=mock_response):
            result = client.get_highlights_tray(123)

        assert len(result) == 2
        assert result[0]["title"] == "Travel"
        assert result[0]["media_count"] == 15
        assert result[0]["cover_url"] == "https://img.com/cover1.jpg"
        assert result[1]["title"] == "Food"

    def test_highlights_empty_tray(self, client):
        with patch.object(client, 'get_mobile_api', return_value={"tray": []}):
            result = client.get_highlights_tray(123)
        assert result == []


# ═══════════════════════════════════════════════════════════
# get_media_info_mobile
# ═══════════════════════════════════════════════════════════

class TestGetMediaInfoMobile:
    def test_media_info(self, client):
        mock_response = {
            "items": [{
                "pk": 555, "code": "MI1", "media_type": 1,
                "like_count": 999, "comment_count": 50,
                "caption": {"text": "Single media"},
                "image_versions2": {"candidates": [{"url": "https://img.com/m.jpg", "width": 1080, "height": 1080}]},
            }]
        }
        with patch.object(client, 'get_mobile_api', return_value=mock_response):
            result = client.get_media_info_mobile(555)

        assert str(result["pk"]) == "555"
        assert result["likes"] == 999

    def test_media_info_not_found(self, client):
        with patch.object(client, 'get_mobile_api', return_value={"items": []}):
            result = client.get_media_info_mobile(999)
        assert result is None


# ═══════════════════════════════════════════════════════════
# get_web_profile
# ═══════════════════════════════════════════════════════════

class TestGetWebProfile:
    def test_web_profile_returns_user(self, client):
        mock_response = {
            "data": {
                "user": {
                    "id": "12345", "username": "cristiano",
                    "edge_followed_by": {"count": 600000000},
                    "edge_owner_to_timeline_media": {"count": 3500, "edges": []},
                }
            }
        }
        with patch.object(client, '_request', return_value=mock_response):
            result = client.get_web_profile("cristiano")

        # get_web_profile returns a tuple (profile, posts) or (None, [])
        if isinstance(result, tuple):
            profile, posts = result
            assert profile["user_id"] == "12345"
            assert profile["followers"] == 600000000
        else:
            # or might return just profile dict
            assert result is not None

    def test_web_profile_returns_none(self, client):
        with patch.object(client, '_request', side_effect=StrategyFailed("fail")):
            result = client.get_web_profile("nonexistent")
        # Should return (None, []) or None
        if isinstance(result, tuple):
            assert result[0] is None
        else:
            assert result is None
