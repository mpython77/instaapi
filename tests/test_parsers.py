"""
Tests for AnonClient parser methods and data helpers.
Pure unit tests — no network, no I/O. Tests _parse_* methods
that normalize Instagram API responses into clean dicts.
"""

import pytest
from instaharvest_v2.anon_client import AnonClient


@pytest.fixture
def client():
    """Create unlimited AnonClient (no delays for tests)."""
    return AnonClient(unlimited=True)


# ═══════════════════════════════════════════════════════════
# _parse_count
# ═══════════════════════════════════════════════════════════

class TestParseCount:
    """_parse_count converts follower count text to int."""

    def test_plain_number(self, client):
        assert client._parse_count("12345") == 12345

    def test_comma_separated(self, client):
        assert client._parse_count("1,234,567") == 1234567

    def test_k_suffix(self, client):
        assert client._parse_count("5.2K") == 5200

    def test_m_suffix(self, client):
        assert client._parse_count("1.5M") == 1500000

    def test_lowercase_k(self, client):
        assert client._parse_count("10k") == 10000

    def test_lowercase_m(self, client):
        assert client._parse_count("2.5m") == 2500000

    def test_invalid_returns_zero(self, client):
        assert client._parse_count("abc") == 0

    def test_empty_string(self, client):
        assert client._parse_count("") == 0

    def test_with_spaces(self, client):
        assert client._parse_count("  1.2K  ") == 1200


# ═══════════════════════════════════════════════════════════
# _parse_graphql_user
# ═══════════════════════════════════════════════════════════

class TestParseGraphqlUser:
    """_parse_graphql_user normalizes GraphQL user objects."""

    def test_basic_profile(self, client):
        user = {
            "id": "12345",
            "username": "testuser",
            "full_name": "Test User",
            "biography": "Hello world",
            "profile_pic_url": "https://pic.com/photo.jpg",
            "profile_pic_url_hd": "https://pic.com/photo_hd.jpg",
            "is_private": False,
            "is_verified": True,
            "is_business_account": True,
            "category_name": "Entertainment",
            "external_url": "https://example.com",
            "edge_followed_by": {"count": 1000000},
            "edge_follow": {"count": 500},
            "edge_owner_to_timeline_media": {"count": 200, "edges": []},
            "bio_links": [{"url": "https://link.com"}],
            "pronouns": ["he/him"],
            "highlight_reel_count": 5,
        }
        result = client._parse_graphql_user(user)

        assert result["user_id"] == "12345"
        assert result["username"] == "testuser"
        assert result["full_name"] == "Test User"
        assert result["biography"] == "Hello world"
        assert result["is_private"] is False
        assert result["is_verified"] is True
        assert result["is_business"] is True
        assert result["category"] == "Entertainment"
        assert result["followers"] == 1000000
        assert result["following"] == 500
        assert result["posts_count"] == 200
        assert result["highlight_count"] == 5
        assert result["recent_posts"] == []

    def test_minimal_profile(self, client):
        user = {"id": "99", "username": "min"}
        result = client._parse_graphql_user(user)
        assert result["user_id"] == "99"
        assert result["username"] == "min"
        assert result["followers"] is None
        assert result["is_private"] is False


# ═══════════════════════════════════════════════════════════
# _parse_timeline_edges
# ═══════════════════════════════════════════════════════════

class TestParseTimelineEdges:
    """_parse_timeline_edges parses GraphQL timeline edges -> posts."""

    def test_single_image_post(self, client):
        edges = [{
            "node": {
                "id": "111",
                "shortcode": "ABC123",
                "__typename": "GraphImage",
                "display_url": "https://img.com/photo.jpg",
                "thumbnail_src": "https://img.com/thumb.jpg",
                "is_video": False,
                "edge_liked_by": {"count": 5000},
                "edge_media_to_comment": {"count": 100},
                "edge_media_to_caption": {"edges": [{"node": {"text": "Hello"}}]},
                "taken_at_timestamp": 1700000000,
            }
        }]
        posts = client._parse_timeline_edges(edges)

        assert len(posts) == 1
        post = posts[0]
        assert post["pk"] == "111"
        assert post["shortcode"] == "ABC123"
        assert post["likes"] == 5000
        assert post["comments"] == 100
        assert post["caption"] == "Hello"
        assert post["is_video"] is False

    def test_video_post(self, client):
        edges = [{
            "node": {
                "id": "222",
                "shortcode": "VID456",
                "__typename": "GraphVideo",
                "is_video": True,
                "video_url": "https://vid.com/video.mp4",
                "video_view_count": 50000,
                "display_url": "https://img.com/thumb.jpg",
                "edge_liked_by": {"count": 3000},
                "edge_media_to_comment": {"count": 50},
                "edge_media_to_caption": {"edges": []},
            }
        }]
        posts = client._parse_timeline_edges(edges)
        post = posts[0]
        assert post["is_video"] is True
        assert post["video_url"] == "https://vid.com/video.mp4"
        assert post["video_views"] == 50000
        assert post["caption"] == ""

    def test_carousel_post(self, client):
        edges = [{
            "node": {
                "id": "333",
                "shortcode": "CAR789",
                "__typename": "GraphSidecar",
                "display_url": "https://img.com/main.jpg",
                "is_video": False,
                "edge_liked_by": {"count": 8000},
                "edge_media_to_comment": {"count": 200},
                "edge_media_to_caption": {"edges": [{"node": {"text": "Carousel!"}}]},
                "edge_sidecar_to_children": {
                    "edges": [
                        {"node": {"id": "c1", "display_url": "https://img.com/c1.jpg", "is_video": False, "display_resources": []}},
                        {"node": {"id": "c2", "display_url": "https://img.com/c2.jpg", "is_video": True, "video_url": "https://vid.com/c2.mp4", "display_resources": []}},
                    ]
                },
            }
        }]
        posts = client._parse_timeline_edges(edges)
        post = posts[0]
        assert post["carousel_count"] == 2
        assert len(post["carousel_media"]) == 2
        assert post["carousel_media"][1]["is_video"] is True

    def test_empty_edges(self, client):
        assert client._parse_timeline_edges([]) == []


# ═══════════════════════════════════════════════════════════
# _parse_mobile_feed_item
# ═══════════════════════════════════════════════════════════

class TestParseMobileFeedItem:
    """_parse_mobile_feed_item normalizes mobile API items."""

    def test_photo_item(self, client):
        item = {
            "pk": 111222333,
            "code": "ABC123",
            "media_type": 1,
            "like_count": 5000,
            "comment_count": 100,
            "caption": {"text": "Photo caption"},
            "taken_at": 1700000000,
            "image_versions2": {
                "candidates": [
                    {"url": "https://img.com/small.jpg", "width": 320, "height": 320},
                    {"url": "https://img.com/big.jpg", "width": 1080, "height": 1080},
                ]
            },
            "user": {"username": "testuser", "pk": 999, "is_verified": True, "profile_pic_url": "https://pic.com/u.jpg"},
        }
        result = client._parse_mobile_feed_item(item)

        assert str(result["pk"]) == "111222333"
        assert result["shortcode"] == "ABC123"
        assert result["media_type"] == "GraphImage"
        assert result["is_video"] is False
        assert result["likes"] == 5000
        assert result["comments"] == 100
        assert result["caption"] == "Photo caption"
        assert result["display_url"] == "https://img.com/big.jpg"  # biggest
        assert result["taken_at"] == 1700000000

    def test_video_item(self, client):
        item = {
            "pk": 444555666,
            "code": "VID789",
            "media_type": 2,
            "like_count": 10000,
            "comment_count": 200,
            "caption": {"text": "Video!"},
            "image_versions2": {"candidates": [{"url": "https://img.com/thumb.jpg", "width": 640, "height": 640}]},
            "video_versions": [{"url": "https://vid.com/video.mp4", "width": 1080}],
            "view_count": 50000,
            "video_duration": 30.5,
        }
        result = client._parse_mobile_feed_item(item)

        assert result["media_type"] == "GraphVideo"
        assert result["is_video"] is True
        assert result["video_url"] == "https://vid.com/video.mp4"
        assert result["video_views"] == 50000
        assert result["video_duration"] == 30.5

    def test_carousel_item(self, client):
        item = {
            "pk": 777888999,
            "code": "CAR456",
            "media_type": 8,
            "like_count": 2000,
            "comment_count": 50,
            "caption": {"text": "Carousel"},
            "image_versions2": {"candidates": [{"url": "https://img.com/main.jpg", "width": 1080, "height": 1080}]},
            "carousel_media": [
                {
                    "media_type": 1,
                    "image_versions2": {"candidates": [{"url": "https://img.com/c1.jpg", "width": 1080, "height": 1080}]},
                },
                {
                    "media_type": 2,
                    "image_versions2": {"candidates": [{"url": "https://img.com/c2.jpg", "width": 640, "height": 640}]},
                    "video_versions": [{"url": "https://vid.com/c2.mp4"}],
                },
            ],
        }
        result = client._parse_mobile_feed_item(item)

        assert result["media_type"] == "GraphSidecar"
        assert result["carousel_count"] == 2
        assert result["carousel_media"][0]["is_video"] is False
        assert result["carousel_media"][1]["is_video"] is True
        assert result["carousel_media"][1]["video_url"] == "https://vid.com/c2.mp4"

    def test_location_parsed(self, client):
        item = {
            "pk": 123, "code": "LOC", "media_type": 1,
            "caption": None,
            "image_versions2": {"candidates": []},
            "location": {"name": "Central Park", "city": "New York", "lat": 40.78, "lng": -73.97},
        }
        result = client._parse_mobile_feed_item(item)
        assert result["location"]["name"] == "Central Park"
        assert result["location"]["city"] == "New York"
        assert result["location"]["lat"] == 40.78

    def test_tagged_users(self, client):
        item = {
            "pk": 456, "code": "TAG", "media_type": 1,
            "caption": {"text": "Tags"},
            "image_versions2": {"candidates": []},
            "usertags": {"in": [
                {"user": {"username": "alice"}},
                {"user": {"username": "bob"}},
            ]},
        }
        result = client._parse_mobile_feed_item(item)
        assert result["tagged_users"] == ["alice", "bob"]

    def test_null_caption_handled(self, client):
        item = {
            "pk": 789, "code": "NOCAP", "media_type": 1,
            "caption": None,
            "image_versions2": {"candidates": []},
        }
        result = client._parse_mobile_feed_item(item)
        assert result["caption"] == ""

    def test_no_image_candidates(self, client):
        item = {
            "pk": 101, "code": "NOIMG", "media_type": 1,
            "caption": {"text": "test"},
            "image_versions2": {"candidates": []},
        }
        result = client._parse_mobile_feed_item(item)
        assert result["display_url"] == ""


# ═══════════════════════════════════════════════════════════
# _parse_embed_media
# ═══════════════════════════════════════════════════════════

class TestParseEmbedMedia:
    """_parse_embed_media normalizes embed endpoint data."""

    def test_basic_embed(self, client):
        media = {
            "id": "12345",
            "shortcode": "EMBED01",
            "__typename": "GraphImage",
            "is_video": False,
            "display_url": "https://img.com/embed.jpg",
            "edge_media_preview_like": {"count": 999},
            "edge_media_to_parent_comment": {"count": 50},
            "edge_media_to_caption": {"edges": [{"node": {"text": "Embed caption"}}]},
            "taken_at_timestamp": 1700000000,
            "owner": {"username": "embeduser", "id": "55", "is_verified": False},
            "display_resources": [
                {"src": "https://img.com/s.jpg", "config_width": 320, "config_height": 320},
                {"src": "https://img.com/l.jpg", "config_width": 1080, "config_height": 1080},
            ],
        }
        result = client._parse_embed_media(media)

        assert result["pk"] == "12345"
        assert result["shortcode"] == "EMBED01"
        assert result["likes"] == 999
        assert result["caption"] == "Embed caption"
        assert result["owner"]["username"] == "embeduser"
        assert len(result["images"]) == 3  # display_url + 2 resources


# ═══════════════════════════════════════════════════════════
# _parse_meta_tags
# ═══════════════════════════════════════════════════════════

class TestParseMetaTags:
    """_parse_meta_tags extracts data from HTML meta tags."""

    def test_basic_meta(self, client):
        html = '''
        <title>John Doe (@johndoe) • Instagram photos and videos</title>
        <meta content="1.5M Followers, 500 Following, 200 Posts" name="description">
        <meta property="og:image" content="https://pic.com/profile.jpg">
        '''
        result = client._parse_meta_tags(html)
        assert result["full_name"] == "John Doe"
        assert result["username"] == "johndoe"
        assert result["followers"] == 1500000
        assert result["following"] == 500
        assert result["posts_count"] == 200
        assert result["profile_pic_url"] == "https://pic.com/profile.jpg"

    def test_empty_html(self, client):
        result = client._parse_meta_tags("")
        assert result == {}
