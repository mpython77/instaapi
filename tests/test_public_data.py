"""
Deep Tests — Instagram Public Data API
=========================================
Comprehensive unit tests for all Public Data models and API methods.

Tests cover:
  - Pydantic models: PublicProfile, PublicPost, HashtagPost, ProfileSnapshot, PublicDataReport
  - API methods: get_profile_info, get_profile_posts, search_hashtag_top/recent
  - Extended: compare_profiles, engagement_analysis, track_profile, export_report
  - HashtagQuotaTracker: quota limits and validation
"""

import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from instaapi.models.public_data import (
    PublicProfile,
    PublicPost,
    HashtagPost,
    ProfileSnapshot,
    PublicDataReport,
)
from instaapi.api.public_data import PublicDataAPI, HashtagQuotaTracker


# ═══════════════════════════════════════════════════════════
# Sample Data Fixtures
# ═══════════════════════════════════════════════════════════

SAMPLE_WEB_PROFILE = {
    "id": "173560420",
    "username": "cristiano",
    "full_name": "Cristiano Ronaldo",
    "biography": "Football legend 🏆⚽\nwww.ronaldo.com",
    "edge_followed_by": {"count": 650000000},
    "edge_follow": {"count": 580},
    "edge_owner_to_timeline_media": {"count": 3800},
    "is_private": False,
    "is_verified": True,
    "is_business_account": True,
    "profile_pic_url": "https://example.com/cr7.jpg",
    "profile_pic_url_hd": "https://example.com/cr7_hd.jpg",
    "external_url": "https://www.ronaldo.com",
    "category_name": "Athlete",
}

SAMPLE_MOBILE_PROFILE = {
    "user": {
        "pk": 173560420,
        "username": "messi",
        "full_name": "Leo Messi",
        "biography": "⚽ Inter Miami CF & Argentina 🇦🇷",
        "follower_count": 500000000,
        "following_count": 350,
        "media_count": 1100,
        "is_private": False,
        "is_verified": True,
        "is_business": True,
        "profile_pic_url": "https://example.com/messi.jpg",
        "external_url": "https://www.messi.com",
        "category": "Athlete",
    }
}

SAMPLE_POST_WEB = {
    "id": "3456789012345_173560420",
    "shortcode": "ABC123xyz",
    "media_type": 1,
    "taken_at": 1708000000,
    "caption": {"text": "Training day 💪 #cr7 #football #training"},
    "like_count": 5000000,
    "comment_count": 25000,
    "user": {"pk": 173560420, "username": "cristiano"},
    "image_versions2": {
        "candidates": [
            {"url": "https://example.com/img_1080.jpg", "width": 1080, "height": 1080},
        ]
    },
}

SAMPLE_POST_VIDEO = {
    "pk": 9876543210,
    "code": "DEF456abc",
    "media_type": 2,
    "taken_at": 1709000000,
    "caption": {"text": "Amazing goal! #football #reels"},
    "like_count": 8000000,
    "comment_count": 40000,
    "play_count": 50000000,
    "user": {"pk": 173560420, "username": "cristiano"},
    "video_url": "https://example.com/video.mp4",
    "image_versions2": {
        "candidates": [
            {"url": "https://example.com/thumb.jpg", "width": 1080, "height": 1920},
        ]
    },
}

SAMPLE_POST_CAROUSEL = {
    "pk": 1111222233,
    "code": "GHI789def",
    "media_type": 8,
    "taken_at": 1710000000,
    "caption": {"text": "Best moments of the year 🏆"},
    "like_count": 3000000,
    "comment_count": 15000,
    "user": {"pk": 173560420, "username": "cristiano"},
    "image_versions2": {
        "candidates": [
            {"url": "https://example.com/carousel1.jpg", "width": 1080, "height": 1080},
        ]
    },
}


# ═══════════════════════════════════════════════════════════
# TEST: PublicProfile Model
# ═══════════════════════════════════════════════════════════

class TestPublicProfile(unittest.TestCase):
    """Test PublicProfile model creation, validation, and factory methods."""

    def test_default(self):
        profile = PublicProfile()
        self.assertEqual(profile.username, "")
        self.assertEqual(profile.followers, 0)
        self.assertEqual(profile.following, 0)
        self.assertEqual(profile.posts_count, 0)
        self.assertFalse(profile.is_verified)

    def test_from_web_data(self):
        profile = PublicProfile.from_api(SAMPLE_WEB_PROFILE)
        self.assertEqual(profile.username, "cristiano")
        self.assertEqual(profile.name, "Cristiano Ronaldo")
        self.assertEqual(profile.followers, 650000000)
        self.assertEqual(profile.following, 580)
        self.assertEqual(profile.posts_count, 3800)
        self.assertTrue(profile.is_verified)
        self.assertTrue(profile.is_business)
        self.assertEqual(profile.website, "https://www.ronaldo.com")
        self.assertEqual(profile.category, "Athlete")
        self.assertEqual(profile.ig_id, "173560420")

    def test_from_mobile_data(self):
        profile = PublicProfile.from_api(SAMPLE_MOBILE_PROFILE)
        self.assertEqual(profile.username, "messi")
        self.assertEqual(profile.name, "Leo Messi")
        self.assertEqual(profile.followers, 500000000)
        self.assertEqual(profile.following, 350)
        self.assertEqual(profile.posts_count, 1100)
        self.assertTrue(profile.is_verified)
        self.assertTrue(profile.is_business)

    def test_profile_url(self):
        profile = PublicProfile(username="nike")
        self.assertEqual(profile.profile_url, "https://www.instagram.com/nike/")

    def test_profile_url_empty(self):
        profile = PublicProfile()
        self.assertEqual(profile.profile_url, "")

    def test_none_handling(self):
        """Test that None values are coerced properly."""
        profile = PublicProfile.from_api({
            "username": None,
            "full_name": None,
            "biography": None,
            "profile_pic_url": None,
            "external_url": None,
        })
        self.assertEqual(profile.username, "")
        self.assertEqual(profile.name, "")
        self.assertEqual(profile.biography, "")

    def test_to_dict(self):
        profile = PublicProfile(username="test", followers=100)
        d = profile.to_dict()
        self.assertEqual(d["username"], "test")
        self.assertEqual(d["followers"], 100)

    def test_repr(self):
        profile = PublicProfile(username="test", followers=100, is_verified=True)
        r = repr(profile)
        self.assertIn("@test", r)
        self.assertIn("[verified]", r)
        self.assertIn("100", r)


# ═══════════════════════════════════════════════════════════
# TEST: PublicPost Model
# ═══════════════════════════════════════════════════════════

class TestPublicPost(unittest.TestCase):
    """Test PublicPost model with engagement metrics and hashtag parsing."""

    def test_default(self):
        post = PublicPost()
        self.assertEqual(post.likes, 0)
        self.assertEqual(post.comments, 0)
        self.assertEqual(post.media_type, "image")
        self.assertEqual(post.hashtag_count, 0)
        self.assertEqual(post.engagement, 0)

    def test_from_web_post(self):
        post = PublicPost.from_api(SAMPLE_POST_WEB, username="cristiano")
        self.assertEqual(post.username, "cristiano")
        self.assertEqual(post.likes, 5000000)
        self.assertEqual(post.comments, 25000)
        self.assertEqual(post.shortcode, "ABC123xyz")
        self.assertEqual(post.media_type, "image")
        self.assertIn("cr7", post.hashtags)
        self.assertIn("football", post.hashtags)
        self.assertIn("training", post.hashtags)
        self.assertEqual(post.hashtag_count, 3)

    def test_video_post(self):
        post = PublicPost.from_api(SAMPLE_POST_VIDEO)
        self.assertEqual(post.media_type, "video")
        self.assertEqual(post.reels_views, 50000000)
        self.assertIn("football", post.hashtags)

    def test_carousel_post(self):
        post = PublicPost.from_api(SAMPLE_POST_CAROUSEL)
        self.assertEqual(post.media_type, "carousel")
        self.assertEqual(post.likes, 3000000)

    def test_engagement_calculation(self):
        post = PublicPost(likes=100, comments=20)
        self.assertEqual(post.engagement, 120)
        self.assertEqual(post.likes_per_post, 100.0)
        self.assertEqual(post.comments_per_post, 20.0)

    def test_post_url_generation(self):
        post = PublicPost.from_api(SAMPLE_POST_WEB)
        self.assertEqual(post.post_url, "https://www.instagram.com/p/ABC123xyz/")

    def test_extract_hashtags(self):
        tags = PublicPost.extract_hashtags("Hello #world #python #ai")
        self.assertEqual(tags, ["world", "python", "ai"])

    def test_extract_hashtags_empty(self):
        tags = PublicPost.extract_hashtags("")
        self.assertEqual(tags, [])

    def test_extract_hashtags_none(self):
        tags = PublicPost.extract_hashtags(None)
        self.assertEqual(tags, [])

    def test_timestamp_parsing(self):
        post = PublicPost.from_api(SAMPLE_POST_WEB)
        self.assertIsNotNone(post.created_at)
        self.assertIsInstance(post.created_at, datetime)

    def test_timestamp_iso_string(self):
        post = PublicPost(created_at="2024-01-15T10:30:00Z")
        self.assertIsNotNone(post.created_at)

    def test_none_caption(self):
        data = {**SAMPLE_POST_WEB, "caption": None}
        post = PublicPost.from_api(data)
        self.assertEqual(post.caption, "")
        self.assertEqual(post.hashtags, [])

    def test_string_caption(self):
        data = {**SAMPLE_POST_WEB, "caption": "Direct string caption #test"}
        post = PublicPost.from_api(data)
        self.assertEqual(post.caption, "Direct string caption #test")
        self.assertIn("test", post.hashtags)

    def test_repr(self):
        post = PublicPost(username="test", likes=500, comments=10, media_type="video")
        r = repr(post)
        self.assertIn("@test", r)
        self.assertIn("500", r)
        self.assertIn("video", r)


# ═══════════════════════════════════════════════════════════
# TEST: HashtagPost Model
# ═══════════════════════════════════════════════════════════

class TestHashtagPost(unittest.TestCase):
    """Test HashtagPost model."""

    def test_default(self):
        hp = HashtagPost()
        self.assertEqual(hp.search_hashtag, "")
        self.assertEqual(hp.search_type, "top")
        self.assertTrue(hp.is_top)
        self.assertFalse(hp.is_recent)

    def test_with_post(self):
        post = PublicPost(likes=1000, comments=50, username="testuser")
        hp = HashtagPost(
            post=post,
            search_hashtag="fitness",
            matching_hashtags=["fitness"],
            search_type="top",
        )
        self.assertEqual(hp.post.likes, 1000)
        self.assertEqual(hp.search_hashtag, "fitness")
        self.assertTrue(hp.is_top)
        self.assertEqual(hp.matching_hashtags, ["fitness"])

    def test_recent_type(self):
        hp = HashtagPost(search_type="recent")
        self.assertTrue(hp.is_recent)
        self.assertFalse(hp.is_top)

    def test_repr(self):
        post = PublicPost(likes=500)
        hp = HashtagPost(post=post, search_hashtag="python", search_type="top")
        r = repr(hp)
        self.assertIn("#python", r)
        self.assertIn("top", r)


# ═══════════════════════════════════════════════════════════
# TEST: ProfileSnapshot Model
# ═══════════════════════════════════════════════════════════

class TestProfileSnapshot(unittest.TestCase):
    """Test ProfileSnapshot model and growth calculation."""

    def test_from_profile(self):
        profile = PublicProfile(username="test", followers=1000, following=100, posts_count=50)
        snapshot = ProfileSnapshot.from_profile(profile)
        self.assertEqual(snapshot.username, "test")
        self.assertEqual(snapshot.followers, 1000)
        self.assertEqual(snapshot.following, 100)
        self.assertEqual(snapshot.posts_count, 50)
        self.assertIsInstance(snapshot.timestamp, datetime)

    def test_growth_since(self):
        old = ProfileSnapshot(
            username="test",
            followers=1000,
            posts_count=50,
            timestamp=datetime.utcnow() - timedelta(hours=24),
        )
        new = ProfileSnapshot(
            username="test",
            followers=1100,
            posts_count=52,
            timestamp=datetime.utcnow(),
        )
        growth = new.growth_since(old)
        self.assertEqual(growth["follower_change"], 100)
        self.assertEqual(growth["posts_change"], 2)
        self.assertIsNotNone(growth["followers_per_day"])
        self.assertGreater(growth["hours_elapsed"], 0)

    def test_growth_short_period(self):
        """Growth within less than 24 hours."""
        old = ProfileSnapshot(
            username="test",
            followers=1000,
            timestamp=datetime.utcnow() - timedelta(hours=2),
        )
        new = ProfileSnapshot(
            username="test",
            followers=1010,
            timestamp=datetime.utcnow(),
        )
        growth = new.growth_since(old)
        self.assertEqual(growth["follower_change"], 10)
        self.assertIsNone(growth["followers_per_day"])  # Less than 24h

    def test_repr(self):
        s = ProfileSnapshot(username="test", followers=500)
        r = repr(s)
        self.assertIn("@test", r)
        self.assertIn("500", r)


# ═══════════════════════════════════════════════════════════
# TEST: PublicDataReport Model
# ═══════════════════════════════════════════════════════════

class TestPublicDataReport(unittest.TestCase):
    """Test PublicDataReport aggregation and export methods."""

    def setUp(self):
        self.profiles = [
            PublicProfile(username="user1", followers=1000),
            PublicProfile(username="user2", followers=2000),
        ]
        self.posts = [
            PublicPost(username="user1", likes=100, comments=10, shortcode="a", created_at=1708000000),
            PublicPost(username="user1", likes=200, comments=20, shortcode="b", created_at=1708100000),
            PublicPost(username="user2", likes=300, comments=30, shortcode="c", created_at=1708200000),
        ]

    def test_empty_report(self):
        report = PublicDataReport()
        self.assertEqual(report.total_profiles, 0)
        self.assertEqual(report.total_posts, 0)
        self.assertEqual(report.avg_likes, 0.0)
        self.assertEqual(report.avg_comments, 0.0)
        self.assertEqual(report.total_engagement, 0)

    def test_with_data(self):
        report = PublicDataReport(
            profiles=self.profiles,
            posts=self.posts,
            query_type="profile_posts",
        )
        self.assertEqual(report.total_profiles, 2)
        self.assertEqual(report.total_posts, 3)
        self.assertEqual(report.avg_likes, 200.0)
        self.assertEqual(report.avg_comments, 20.0)
        self.assertEqual(report.total_engagement, 660)

    def test_to_profiles_table(self):
        report = PublicDataReport(profiles=self.profiles)
        table = report.to_profiles_table()
        self.assertEqual(len(table), 2)
        self.assertEqual(table[0]["username"], "user1")
        self.assertEqual(table[0]["profile_followers"], 1000)
        self.assertIn("date", table[0])

    def test_to_posts_table(self):
        report = PublicDataReport(posts=self.posts)
        table = report.to_posts_table()
        self.assertEqual(len(table), 3)
        self.assertEqual(table[0]["likes"], 100)
        self.assertEqual(table[0]["comments"], 10)
        self.assertIn("link_to_post", table[0])

    def test_to_hashtags_table(self):
        post = PublicPost(likes=50, comments=5, hashtags=["python"])
        hp = HashtagPost(post=post, search_hashtag="python", matching_hashtags=["python"])
        report = PublicDataReport(hashtag_posts=[hp])
        table = report.to_hashtags_table()
        self.assertEqual(len(table), 1)
        self.assertEqual(table[0]["likes"], 50)
        self.assertEqual(table[0]["matching_hashtags"], "python")

    def test_repr(self):
        report = PublicDataReport(
            profiles=self.profiles,
            posts=self.posts,
            query_type="profile_posts",
        )
        r = repr(report)
        self.assertIn("profiles=2", r)
        self.assertIn("posts=3", r)


# ═══════════════════════════════════════════════════════════
# TEST: HashtagQuotaTracker
# ═══════════════════════════════════════════════════════════

class TestHashtagQuotaTracker(unittest.TestCase):
    """Test hashtag quota tracking and limits."""

    def setUp(self):
        self.tracker = HashtagQuotaTracker(max_per_profile=3, window_days=7)

    def test_initial_quota(self):
        self.assertTrue(self.tracker.can_search("test"))
        self.assertEqual(self.tracker.get_remaining_quota(), 3)

    def test_search_reduces_quota(self):
        self.tracker.record_search("tag1")
        self.assertEqual(self.tracker.get_remaining_quota(), 2)
        self.tracker.record_search("tag2")
        self.assertEqual(self.tracker.get_remaining_quota(), 1)

    def test_same_hashtag_no_extra_cost(self):
        """Re-searching the same hashtag doesn't count as additional."""
        self.tracker.record_search("tag1")
        self.tracker.record_search("tag1")
        self.tracker.record_search("tag1")
        self.assertEqual(self.tracker.get_remaining_quota(), 2)

    def test_quota_exceeded(self):
        self.tracker.record_search("a")
        self.tracker.record_search("b")
        self.tracker.record_search("c")
        self.assertFalse(self.tracker.can_search("d"))
        self.assertEqual(self.tracker.get_remaining_quota(), 0)

    def test_existing_hashtag_still_allowed(self):
        self.tracker.record_search("a")
        self.tracker.record_search("b")
        self.tracker.record_search("c")
        self.assertTrue(self.tracker.can_search("a"))  # Already searched

    def test_multi_profile_quota(self):
        self.tracker.record_search("a")
        self.tracker.record_search("b")
        self.tracker.record_search("c")
        # With 2 profiles, quota = 6
        self.assertTrue(self.tracker.can_search("d", profile_count=2))
        self.assertEqual(self.tracker.get_remaining_quota(profile_count=2), 3)

    def test_reset(self):
        self.tracker.record_search("a")
        self.tracker.record_search("b")
        self.tracker.reset()
        self.assertEqual(self.tracker.get_remaining_quota(), 3)


# ═══════════════════════════════════════════════════════════
# TEST: PublicDataAPI Initialization
# ═══════════════════════════════════════════════════════════

class TestPublicDataAPIInit(unittest.TestCase):
    """Test PublicDataAPI initialization."""

    def test_init(self):
        mock_public = MagicMock()
        api = PublicDataAPI(mock_public)
        self.assertIsNotNone(api._public)
        self.assertIsNotNone(api._quota)

    def test_repr(self):
        mock_public = MagicMock()
        api = PublicDataAPI(mock_public)
        r = repr(api)
        self.assertIn("PublicDataAPI", r)
        self.assertIn("hashtag_quota", r)

    def test_constants(self):
        self.assertEqual(PublicDataAPI.MAX_HASHTAG_PER_PROFILE, 30)
        self.assertEqual(PublicDataAPI.MAX_HASHTAG_PER_REQUEST, 100)
        self.assertEqual(PublicDataAPI.HASHTAG_WINDOW_DAYS, 7)
        self.assertEqual(PublicDataAPI.HISTORY_RANGE_YEARS, 2)
        self.assertEqual(PublicDataAPI.RECENT_SEARCH_HOURS, 24)
        self.assertEqual(PublicDataAPI.RECENT_SEARCH_MAX, 250)
        self.assertEqual(PublicDataAPI.TOP_SEARCH_MAX, 100)


# ═══════════════════════════════════════════════════════════
# TEST: Profile Info Query Type
# ═══════════════════════════════════════════════════════════

class TestProfileInfoQuery(unittest.TestCase):
    """Test get_profile_info (Supermetrics: Profile Info query type)."""

    def setUp(self):
        self.mock_public = MagicMock()
        self.api = PublicDataAPI(self.mock_public)

    def test_single_profile(self):
        self.mock_public.get_profile.return_value = SAMPLE_WEB_PROFILE
        profile = self.api.get_profile_info("cristiano")
        self.assertIsInstance(profile, PublicProfile)
        self.assertEqual(profile.username, "cristiano")
        self.assertEqual(profile.followers, 650000000)
        self.mock_public.get_profile.assert_called_once_with("cristiano")

    def test_multiple_profiles(self):
        self.mock_public.get_profile.side_effect = [
            SAMPLE_WEB_PROFILE,
            SAMPLE_MOBILE_PROFILE.get("user"),
        ]
        profiles = self.api.get_profile_info(["cristiano", "messi"])
        self.assertEqual(len(profiles), 2)
        self.assertIsInstance(profiles[0], PublicProfile)
        self.assertIsInstance(profiles[1], PublicProfile)

    def test_profile_not_found(self):
        self.mock_public.get_profile.return_value = None
        profile = self.api.get_profile_info("nonexistent_user_xxx")
        self.assertIsInstance(profile, PublicProfile)  # Returns empty profile
        self.assertEqual(profile.followers, 0)

    def test_at_symbol_stripped(self):
        self.mock_public.get_profile.return_value = SAMPLE_WEB_PROFILE
        self.api.get_profile_info("@cristiano")
        self.mock_public.get_profile.assert_called_with("cristiano")

    def test_empty_username_raises(self):
        with self.assertRaises(ValueError):
            self.api.get_profile_info("")

    def test_error_handling(self):
        self.mock_public.get_profile.side_effect = Exception("Network error")
        profile = self.api.get_profile_info("test")
        self.assertIsInstance(profile, PublicProfile)
        self.assertEqual(profile.followers, 0)


# ═══════════════════════════════════════════════════════════
# TEST: Profile Posts Query Type
# ═══════════════════════════════════════════════════════════

class TestProfilePostsQuery(unittest.TestCase):
    """Test get_profile_posts (Supermetrics: Profile Posts query type)."""

    def setUp(self):
        self.mock_public = MagicMock()
        self.api = PublicDataAPI(self.mock_public)

    def test_basic_fetch(self):
        self.mock_public.get_posts.return_value = [SAMPLE_POST_WEB, SAMPLE_POST_VIDEO]
        posts = self.api.get_profile_posts("cristiano", max_count=10)
        self.assertEqual(len(posts), 2)
        self.assertIsInstance(posts[0], PublicPost)
        self.assertEqual(posts[0].likes, 5000000)

    def test_date_filtering(self):
        self.mock_public.get_posts.return_value = [
            SAMPLE_POST_WEB,  # taken_at=1708000000 => 2024-02-15
            SAMPLE_POST_VIDEO,  # taken_at=1709000000 => 2024-02-27
        ]
        # Only posts after Feb 20
        posts = self.api.get_profile_posts(
            "cristiano",
            date_from=datetime(2024, 2, 20),
        )
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].shortcode, "DEF456abc")

    def test_multiple_usernames(self):
        self.mock_public.get_posts.side_effect = [
            [SAMPLE_POST_WEB],
            [SAMPLE_POST_VIDEO],
        ]
        posts = self.api.get_profile_posts(["user1", "user2"])
        self.assertEqual(len(posts), 2)

    def test_empty_result(self):
        self.mock_public.get_posts.return_value = []
        posts = self.api.get_profile_posts("test")
        self.assertEqual(len(posts), 0)

    def test_large_count_uses_get_all_posts(self):
        self.mock_public.get_all_posts.return_value = [SAMPLE_POST_WEB] * 20
        posts = self.api.get_profile_posts("cristiano", max_count=20)
        self.assertEqual(len(posts), 20)
        self.mock_public.get_all_posts.assert_called_once()

    def test_error_handling(self):
        self.mock_public.get_posts.side_effect = Exception("Error")
        posts = self.api.get_profile_posts("test")
        self.assertEqual(len(posts), 0)


# ═══════════════════════════════════════════════════════════
# TEST: Hashtag Search Query Type
# ═══════════════════════════════════════════════════════════

class TestHashtagSearchQuery(unittest.TestCase):
    """Test search_hashtag_top and search_hashtag_recent."""

    def setUp(self):
        self.mock_public = MagicMock()
        self.api = PublicDataAPI(self.mock_public)

    def test_top_search(self):
        self.mock_public.get_hashtag_posts.return_value = [SAMPLE_POST_WEB]
        results = self.api.search_hashtag_top("football")
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], HashtagPost)
        self.assertEqual(results[0].search_type, "top")
        self.assertEqual(results[0].search_hashtag, "football")

    def test_recent_search(self):
        self.mock_public.get_hashtag_posts.return_value = [SAMPLE_POST_WEB]
        results = self.api.search_hashtag_recent("football")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].search_type, "recent")

    def test_hash_symbol_stripped(self):
        self.mock_public.get_hashtag_posts.return_value = [SAMPLE_POST_WEB]
        self.api.search_hashtag_top("#football")
        self.mock_public.get_hashtag_posts.assert_called_with("football", max_count=12)

    def test_multiple_hashtags(self):
        self.mock_public.get_hashtag_posts.side_effect = [
            [SAMPLE_POST_WEB],
            [SAMPLE_POST_VIDEO],
        ]
        results = self.api.search_hashtag_top(["football", "soccer"])
        self.assertEqual(len(results), 2)

    def test_matching_hashtags_populated(self):
        post_data = {
            **SAMPLE_POST_WEB,
            "caption": {"text": "Love #football and #soccer!"},
        }
        self.mock_public.get_hashtag_posts.return_value = [post_data]
        results = self.api.search_hashtag_top(["football", "soccer"])
        # The post contains both searched hashtags
        for r in results:
            self.assertGreater(len(r.matching_hashtags), 0)

    def test_empty_hashtag_raises(self):
        with self.assertRaises(ValueError):
            self.api.search_hashtag_top("")

    def test_too_many_hashtags_raises(self):
        many = [f"tag{i}" for i in range(101)]
        with self.assertRaises(ValueError):
            self.api.search_hashtag_top(many)

    def test_quota_tracking(self):
        """Verify searches are tracked in quota."""
        self.mock_public.get_hashtag_posts.return_value = []
        initial = self.api.get_hashtag_quota()["remaining"]
        self.api.search_hashtag_top("newtag")
        after = self.api.get_hashtag_quota()["remaining"]
        self.assertEqual(after, initial - 1)

    def test_error_handling(self):
        self.mock_public.get_hashtag_posts.side_effect = Exception("API Error")
        results = self.api.search_hashtag_top("test")
        self.assertEqual(len(results), 0)


# ═══════════════════════════════════════════════════════════
# TEST: Compare Profiles
# ═══════════════════════════════════════════════════════════

class TestCompareProfiles(unittest.TestCase):
    """Test compare_profiles method."""

    def setUp(self):
        self.mock_public = MagicMock()
        self.api = PublicDataAPI(self.mock_public)

    def test_basic_comparison(self):
        # Profile info calls
        self.mock_public.get_profile.side_effect = [
            {**SAMPLE_WEB_PROFILE, "username": "nike",
             "edge_followed_by": {"count": 200000000}},
            {**SAMPLE_WEB_PROFILE, "username": "adidas",
             "edge_followed_by": {"count": 100000000}},
        ]
        # Posts calls
        self.mock_public.get_posts.side_effect = [
            [SAMPLE_POST_WEB],
            [SAMPLE_POST_VIDEO],
        ]

        result = self.api.compare_profiles(["nike", "adidas"])
        self.assertIn("accounts", result)
        self.assertIn("rankings", result)
        self.assertIn("winner", result)
        self.assertEqual(len(result["accounts"]), 2)

    def test_minimum_accounts_required(self):
        with self.assertRaises(ValueError):
            self.api.compare_profiles(["only_one"])


# ═══════════════════════════════════════════════════════════
# TEST: Engagement Analysis
# ═══════════════════════════════════════════════════════════

class TestEngagementAnalysis(unittest.TestCase):
    """Test engagement_analysis method."""

    def setUp(self):
        self.mock_public = MagicMock()
        self.api = PublicDataAPI(self.mock_public)

    def test_basic_analysis(self):
        self.mock_public.get_profile.return_value = SAMPLE_WEB_PROFILE
        self.mock_public.get_posts.return_value = [
            SAMPLE_POST_WEB,
            SAMPLE_POST_VIDEO,
        ]

        result = self.api.engagement_analysis("cristiano")
        self.assertEqual(result["username"], "cristiano")
        self.assertIn("avg_likes", result)
        self.assertIn("avg_comments", result)
        self.assertIn("engagement_rate", result)
        self.assertIn("rating", result)
        self.assertIn("content_type_breakdown", result)
        self.assertIn("top_hashtags", result)
        self.assertIn("top_posts", result)
        self.assertIn("posts_per_week", result)

    def test_no_posts(self):
        self.mock_public.get_profile.return_value = SAMPLE_WEB_PROFILE
        self.mock_public.get_posts.return_value = []

        result = self.api.engagement_analysis("cristiano")
        self.assertIn("error", result)

    def test_engagement_rating_excellent(self):
        """High engagement should be rated excellent."""
        self.mock_public.get_profile.return_value = {
            "username": "micro_influencer",
            "edge_followed_by": {"count": 1000},
        }
        self.mock_public.get_posts.return_value = [
            {"pk": 1, "code": "a", "like_count": 100, "comment_count": 10, "media_type": 1,
             "taken_at": 1708000000, "caption": {"text": ""}, "user": {"username": "micro_influencer"}},
        ]
        result = self.api.engagement_analysis("micro_influencer")
        self.assertEqual(result["rating"], "excellent")


# ═══════════════════════════════════════════════════════════
# TEST: Export Report
# ═══════════════════════════════════════════════════════════

class TestExportReport(unittest.TestCase):
    """Test report export to JSON, CSV, JSONL."""

    def setUp(self):
        self.mock_public = MagicMock()
        self.api = PublicDataAPI(self.mock_public)
        self.report = PublicDataReport(
            profiles=[PublicProfile(username="test", followers=1000)],
            posts=[
                PublicPost(username="test", likes=100, comments=10, shortcode="a",
                           created_at=1708000000, media_type="image"),
            ],
            query_type="profile_posts",
        )

    def test_json_export(self):
        data = self.api.export_report(self.report, "json")
        self.assertIsInstance(data, dict)
        self.assertIn("profiles", data)
        self.assertIn("posts", data)
        self.assertIn("metadata", data)
        self.assertEqual(len(data["profiles"]), 1)
        self.assertEqual(len(data["posts"]), 1)

    def test_json_file_export(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            self.api.export_report(self.report, "json", path)
            with open(path, "r") as f:
                data = json.load(f)
            self.assertIn("profiles", data)
        finally:
            os.unlink(path)

    def test_csv_export(self):
        result = self.api.export_report(self.report, "csv")
        self.assertIsInstance(result, str)
        self.assertIn("likes", result)
        self.assertIn("comments", result)

    def test_csv_file_export(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            path = f.name
        try:
            self.api.export_report(self.report, "csv", path)
            with open(path, "r") as f:
                content = f.read()
            self.assertIn("likes", content)
        finally:
            os.unlink(path)

    def test_jsonl_export(self):
        result = self.api.export_report(self.report, "jsonl")
        self.assertIsInstance(result, str)
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 1)
        parsed = json.loads(lines[0])
        self.assertIn("likes", parsed)

    def test_unsupported_format(self):
        with self.assertRaises(ValueError):
            self.api.export_report(self.report, "xml")


# ═══════════════════════════════════════════════════════════
# TEST: Profile Tracking
# ═══════════════════════════════════════════════════════════

class TestProfileTracking(unittest.TestCase):
    """Test track_profile and growth tracking."""

    def setUp(self):
        self.mock_public = MagicMock()
        self.api = PublicDataAPI(self.mock_public)

    def test_first_snapshot(self):
        self.mock_public.get_profile.return_value = SAMPLE_WEB_PROFILE
        result = self.api.track_profile("cristiano")
        self.assertIn("profile", result)
        self.assertIn("snapshot", result)
        self.assertEqual(result["total_snapshots"], 1)
        self.assertNotIn("growth", result)

    def test_growth_tracking(self):
        # First snapshot
        self.mock_public.get_profile.return_value = {
            "username": "testuser",
            "edge_followed_by": {"count": 1000},
            "edge_follow": {"count": 50},
            "edge_owner_to_timeline_media": {"count": 20},
        }
        self.api.track_profile("testuser")

        # Second snapshot — followers grew
        self.mock_public.get_profile.return_value = {
            "username": "testuser",
            "edge_followed_by": {"count": 1050},
            "edge_follow": {"count": 52},
            "edge_owner_to_timeline_media": {"count": 21},
        }
        result = self.api.track_profile("testuser")
        self.assertEqual(result["total_snapshots"], 2)
        self.assertIn("growth", result)
        self.assertEqual(result["growth"]["follower_change"], 50)
        self.assertEqual(result["growth"]["posts_change"], 1)

    def test_history_retrieval(self):
        self.mock_public.get_profile.return_value = {
            "username": "test",
            "edge_followed_by": {"count": 100},
        }
        self.api.track_profile("test")
        self.api.track_profile("test")
        history = self.api.get_tracking_history("test")
        self.assertEqual(len(history), 2)

    def test_empty_history(self):
        history = self.api.get_tracking_history("nonexistent")
        self.assertEqual(history, [])


# ═══════════════════════════════════════════════════════════
# TEST: Build Report
# ═══════════════════════════════════════════════════════════

class TestBuildReport(unittest.TestCase):
    """Test build_report method."""

    def setUp(self):
        self.mock_public = MagicMock()
        self.api = PublicDataAPI(self.mock_public)

    def test_profile_report(self):
        self.mock_public.get_profile.return_value = SAMPLE_WEB_PROFILE
        self.mock_public.get_posts.return_value = [SAMPLE_POST_WEB]

        report = self.api.build_report(usernames=["cristiano"])
        self.assertIsInstance(report, PublicDataReport)
        self.assertEqual(report.total_profiles, 1)
        self.assertEqual(report.total_posts, 1)
        self.assertEqual(report.query_type, "profile_posts")
        self.assertIsNotNone(report.query_start)
        self.assertIsNotNone(report.query_end)
        self.assertGreaterEqual(report.query_duration_seconds, 0)

    def test_hashtag_report(self):
        self.mock_public.get_hashtag_posts.return_value = [SAMPLE_POST_WEB]
        report = self.api.build_report(hashtags=["football"])
        self.assertIsInstance(report, PublicDataReport)
        self.assertGreater(report.total_hashtag_posts, 0)
        self.assertEqual(report.query_type, "post_search")

    def test_combined_report(self):
        self.mock_public.get_profile.return_value = SAMPLE_WEB_PROFILE
        self.mock_public.get_posts.return_value = [SAMPLE_POST_WEB]
        self.mock_public.get_hashtag_posts.return_value = [SAMPLE_POST_VIDEO]

        report = self.api.build_report(
            usernames=["cristiano"],
            hashtags=["football"],
        )
        self.assertGreater(report.total_profiles, 0)
        self.assertGreater(report.total_posts, 0)
        self.assertGreater(report.total_hashtag_posts, 0)


if __name__ == "__main__":
    unittest.main()
