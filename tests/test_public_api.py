"""
Tests for PublicAPI and AsyncPublicAPI high-level methods.
Mocks the underlying AnonClient/AsyncAnonClient.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

from instaharvest_v2.anon_client import AnonClient
from instaharvest_v2.async_anon_client import AsyncAnonClient
from instaharvest_v2.api.public import PublicAPI
from instaharvest_v2.api.async_public import AsyncPublicAPI


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def mock_anon():
    """Mocked sync AnonClient."""
    client = AnonClient(unlimited=True)
    return client


@pytest.fixture
def public(mock_anon):
    """PublicAPI with mocked client."""
    return PublicAPI(mock_anon)


@pytest.fixture
def async_anon():
    """Mocked async AnonClient."""
    return AsyncAnonClient(unlimited=True)


@pytest.fixture
def async_public(async_anon):
    """AsyncPublicAPI with mocked async client."""
    return AsyncPublicAPI(async_anon)


# ═══════════════════════════════════════════════════════════
# Sync PublicAPI — search
# ═══════════════════════════════════════════════════════════

class TestPublicSearch:
    def test_search_returns_results(self, public):
        mock_data = {
            "users": [{"username": "nike", "follower_count": 300000000}],
            "hashtags": [{"name": "nike"}],
            "places": [],
        }
        with patch.object(public._client, 'search_web', return_value=mock_data):
            result = public.search("nike")
        assert len(result["users"]) == 1
        assert result["users"][0]["username"] == "nike"

    def test_search_returns_empty_on_fail(self, public):
        with patch.object(public._client, 'search_web', return_value=None):
            result = public.search("nonexo222")
        assert result == {"users": [], "hashtags": [], "places": []}


class TestPublicReels:
    def test_reels_returns_items(self, public):
        with patch.object(public, 'get_user_id', return_value=123):
            with patch.object(public._client, 'get_user_reels', return_value={"items": [{"pk": 1}, {"pk": 2}]}):
                result = public.get_reels("testuser", max_count=5)
        assert len(result) == 2

    def test_reels_no_user_id(self, public):
        with patch.object(public, 'get_user_id', return_value=None):
            result = public.get_reels("nonexist")
        assert result == []


class TestPublicFeed:
    def test_feed_returns_items(self, public):
        mock_feed = {"items": [{"pk": 1}, {"pk": 2}], "more_available": True, "next_max_id": "cursor"}
        with patch.object(public._client, 'get_user_feed_mobile', return_value=mock_feed):
            result = public.get_feed(123)
        assert len(result["items"]) == 2
        assert result["more_available"] is True

    def test_feed_empty(self, public):
        with patch.object(public._client, 'get_user_feed_mobile', return_value=None):
            result = public.get_feed(123)
        assert result["items"] == []


class TestPublicHashtagV2:
    def test_hashtag_v2_returns(self, public):
        mock_data = {"tag_name": "football", "posts": [{"pk": 1}, {"pk": 2}, {"pk": 3}], "more_available": True, "media_count": 500000}
        with patch.object(public._client, 'get_hashtag_sections', return_value=mock_data):
            result = public.get_hashtag_posts_v2("football", max_count=2)
        assert len(result["posts"]) == 2  # trimmed to max_count
        assert result["media_count"] == 500000

    def test_hashtag_v2_empty(self, public):
        with patch.object(public._client, 'get_hashtag_sections', return_value=None):
            result = public.get_hashtag_posts_v2("#empty")
        assert result["posts"] == []


class TestPublicLocation:
    def test_location_returns(self, public):
        mock_data = {"location": {"name": "NYC"}, "posts": [{"pk": 1}], "more_available": False, "media_count": 100}
        with patch.object(public._client, 'get_location_sections', return_value=mock_data):
            result = public.get_location_posts(123)
        assert result["location"]["name"] == "NYC"

    def test_location_empty(self, public):
        with patch.object(public._client, 'get_location_sections', return_value=None):
            result = public.get_location_posts(999)
        assert result["location"] is None
        assert result["posts"] == []


class TestPublicSimilar:
    def test_similar_returns(self, public):
        mock_data = [{"username": "adidas"}, {"username": "puma"}]
        with patch.object(public, 'get_user_id', return_value=123):
            with patch.object(public._client, 'get_similar_accounts', return_value=mock_data):
                result = public.get_similar_accounts("nike")
        assert len(result) == 2

    def test_similar_no_user_id(self, public):
        with patch.object(public, 'get_user_id', return_value=None):
            result = public.get_similar_accounts("nonexist")
        assert result == []


class TestPublicHighlights:
    def test_highlights_returns(self, public):
        mock_data = [{"title": "Travel", "media_count": 10}]
        with patch.object(public, 'get_user_id', return_value=123):
            with patch.object(public._client, 'get_highlights_tray', return_value=mock_data):
                result = public.get_highlights("nike")
        assert len(result) == 1
        assert result[0]["title"] == "Travel"


class TestPublicBulkProfiles:
    def test_bulk_profiles(self, public):
        def fake_profile(u):
            return {"username": u, "followers": 1000}
        with patch.object(public, 'get_profile', side_effect=lambda u: fake_profile(u)):
            result = public.bulk_profiles(["nike", "adidas"])
        assert len(result) == 2
        assert "nike" in result
        assert "adidas" in result

    def test_bulk_profiles_handles_error(self, public):
        with patch.object(public, 'get_profile', side_effect=Exception("fail")):
            result = public.bulk_profiles(["error_user"])
        assert result["error_user"] is None


class TestPublicBulkFeeds:
    def test_bulk_feeds(self, public):
        mock_feed = {"items": [{"pk": 1}], "more_available": False, "next_max_id": None}
        with patch.object(public, 'get_feed', return_value=mock_feed):
            result = public.bulk_feeds([123, 456])
        assert len(result) == 2


# ═══════════════════════════════════════════════════════════
# Async PublicAPI
# ═══════════════════════════════════════════════════════════

class TestAsyncPublicSearch:
    @pytest.mark.asyncio
    async def test_search(self, async_public):
        mock_data = {"users": [{"username": "nike"}], "hashtags": [], "places": []}
        with patch.object(async_public._client, 'search_web', new_callable=AsyncMock, return_value=mock_data):
            result = await async_public.search("nike")
        assert result["users"][0]["username"] == "nike"

    @pytest.mark.asyncio
    async def test_search_empty(self, async_public):
        with patch.object(async_public._client, 'search_web', new_callable=AsyncMock, return_value=None):
            result = await async_public.search("nope")
        assert result == {"users": [], "hashtags": [], "places": []}


class TestAsyncPublicReels:
    @pytest.mark.asyncio
    async def test_reels(self, async_public):
        with patch.object(async_public, 'get_user_id', new_callable=AsyncMock, return_value=123):
            with patch.object(async_public._client, 'get_user_reels', new_callable=AsyncMock, return_value={"items": [{"pk": 1}]}):
                result = await async_public.get_reels("testuser")
        assert len(result) == 1


class TestAsyncPublicFeed:
    @pytest.mark.asyncio
    async def test_feed(self, async_public):
        mock = {"items": [{"pk": 1}], "more_available": True, "next_max_id": "c"}
        with patch.object(async_public._client, 'get_user_feed_mobile', new_callable=AsyncMock, return_value=mock):
            result = await async_public.get_feed(123)
        assert len(result["items"]) == 1


class TestAsyncPublicBulkProfiles:
    @pytest.mark.asyncio
    async def test_bulk_profiles(self, async_public):
        async def fake(u):
            return {"username": u, "followers": 100}
        with patch.object(async_public, 'get_profile', new_callable=AsyncMock, side_effect=lambda u: fake(u)):
            result = await async_public.bulk_profiles(["a", "b"])
        assert len(result) == 2


class TestAsyncPublicHighlights:
    @pytest.mark.asyncio
    async def test_highlights(self, async_public):
        with patch.object(async_public, 'get_user_id', new_callable=AsyncMock, return_value=123):
            with patch.object(async_public._client, 'get_highlights_tray', new_callable=AsyncMock, return_value=[{"title": "T"}]):
                result = await async_public.get_highlights("test")
        assert len(result) == 1


class TestAsyncPublicSimilar:
    @pytest.mark.asyncio
    async def test_similar(self, async_public):
        with patch.object(async_public, 'get_user_id', new_callable=AsyncMock, return_value=123):
            with patch.object(async_public._client, 'get_similar_accounts', new_callable=AsyncMock, return_value=[{"username": "x"}]):
                result = await async_public.get_similar_accounts("test")
        assert len(result) == 1


class TestAsyncPublicHashtag:
    @pytest.mark.asyncio
    async def test_hashtag_v2(self, async_public):
        mock = {"tag_name": "test", "posts": [{"pk": 1}], "more_available": False, "media_count": 100}
        with patch.object(async_public._client, 'get_hashtag_sections', new_callable=AsyncMock, return_value=mock):
            result = await async_public.get_hashtag_posts_v2("test")
        assert result["tag_name"] == "test"


class TestAsyncPublicLocation:
    @pytest.mark.asyncio
    async def test_location(self, async_public):
        mock = {"location": {"name": "NY"}, "posts": [{"pk": 1}], "more_available": False, "media_count": 50}
        with patch.object(async_public._client, 'get_location_sections', new_callable=AsyncMock, return_value=mock):
            result = await async_public.get_location_posts(123)
        assert result["location"]["name"] == "NY"
