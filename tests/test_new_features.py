"""
Deep Tests — Round 1: Export, Analytics, Scheduler, MultiAccount, Growth, Automation
=====================================================================================
Comprehensive unit tests for all new modules.
"""

import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock


# ═══════════════════════════════════════════════════════════
# TEST: ExportAPI & ExportFilter
# ═══════════════════════════════════════════════════════════

class TestExportFilter(unittest.TestCase):
    """Test ExportFilter data class."""

    def test_default_filter(self):
        from instaapi.api.export import ExportFilter
        f = ExportFilter()
        self.assertEqual(f.min_followers, 0)
        self.assertEqual(f.max_followers, 0)
        self.assertFalse(f.has_bio)
        self.assertFalse(f.is_verified)
        self.assertIsNone(f.is_private)

    def test_custom_filter(self):
        from instaapi.api.export import ExportFilter
        f = ExportFilter(min_followers=100, max_followers=5000, has_bio=True)
        self.assertEqual(f.min_followers, 100)
        self.assertEqual(f.max_followers, 5000)
        self.assertTrue(f.has_bio)

    def test_filter_match(self):
        from instaapi.api.export import ExportFilter
        f = ExportFilter(min_followers=10, max_followers=1000)
        # Mock user object
        user = {"follower_count": 500, "following_count": 200, "biography": "hey"}
        self.assertTrue(f.matches(user))

        user2 = {"follower_count": 5}
        self.assertFalse(f.matches(user2))


class TestExportAPI(unittest.TestCase):
    """Test ExportAPI initialization."""

    def test_init(self):
        from instaapi.api.export import ExportAPI
        client = MagicMock()
        users = MagicMock()
        friendships = MagicMock()
        media = MagicMock()
        hashtags = MagicMock()
        api = ExportAPI(client, users, friendships, media, hashtags)
        self.assertIsNotNone(api)
        self.assertEqual(api._client, client)
        self.assertEqual(api._users, users)


# ═══════════════════════════════════════════════════════════
# TEST: AnalyticsAPI
# ═══════════════════════════════════════════════════════════

class TestAnalyticsAPI(unittest.TestCase):
    """Test AnalyticsAPI methods."""

    def setUp(self):
        from instaapi.api.analytics import AnalyticsAPI
        self.client = MagicMock()
        self.users = MagicMock()
        self.media = MagicMock()
        self.feed = MagicMock()
        self.api = AnalyticsAPI(self.client, self.users, self.media, self.feed)

    def test_init(self):
        self.assertIsNotNone(self.api)

    def test_engagement_no_posts(self):
        """Test engagement rate with no posts."""
        user_mock = MagicMock()
        user_mock.pk = 123
        user_mock.followers = 1000
        user_mock.follower_count = 1000
        self.users.get_by_username.return_value = user_mock
        self.client.request.return_value = {"items": [], "more_available": False}

        result = self.api.engagement_rate("testuser")
        self.assertEqual(result["engagement_rate"], 0.0)
        self.assertEqual(result["rating"], "no_data")

    def test_engagement_with_posts(self):
        """Test engagement calculation."""
        user_mock = MagicMock()
        user_mock.pk = 123
        user_mock.followers = 1000
        user_mock.follower_count = 1000
        self.users.get_by_username.return_value = user_mock

        posts = [
            {"like_count": 100, "comment_count": 10, "taken_at": 1700000000},
            {"like_count": 200, "comment_count": 20, "taken_at": 1700100000},
        ]
        self.client.request.return_value = {"items": posts, "more_available": False}

        result = self.api.engagement_rate("testuser", post_count=2)
        self.assertGreater(result["engagement_rate"], 0)
        self.assertEqual(result["posts_analyzed"], 2)
        self.assertIn(result["rating"], ["excellent", "very_good", "good", "average", "low"])

    def test_compare_method(self):
        """Test competitor comparison."""
        user_mock = MagicMock()
        user_mock.pk = 123
        user_mock.followers = 5000
        user_mock.follower_count = 5000
        self.users.get_by_username.return_value = user_mock

        posts = [{"like_count": 500, "comment_count": 50,
                  "taken_at": 1700000000, "media_type": 1,
                  "code": "abc", "caption": {"text": "test"}}]
        self.client.request.return_value = {"items": posts, "more_available": False}

        result = self.api.compare(["user1", "user2"])
        self.assertIn("accounts", result)
        self.assertIn("rankings", result)
        self.assertIn("winner", result)
        self.assertEqual(len(result["accounts"]), 2)

    def test_helper_methods(self):
        """Test static helper methods."""
        from instaapi.api.analytics import AnalyticsAPI
        self.assertEqual(AnalyticsAPI._get_likes({"like_count": 50}), 50)
        self.assertEqual(AnalyticsAPI._get_comments({"comment_count": 10}), 10)
        self.assertEqual(AnalyticsAPI._get_timestamp({"taken_at": 100}), 100)
        self.assertEqual(AnalyticsAPI._get_caption({"caption": {"text": "hi"}}), "hi")
        self.assertEqual(AnalyticsAPI._get_media_type({"media_type": 1}), "photo")
        self.assertEqual(AnalyticsAPI._get_media_type({"media_type": 2}), "video")
        self.assertEqual(AnalyticsAPI._get_media_type({"media_type": 8}), "carousel")


# ═══════════════════════════════════════════════════════════
# TEST: SchedulerAPI
# ═══════════════════════════════════════════════════════════

class TestSchedulerAPI(unittest.TestCase):
    """Test SchedulerAPI."""

    def setUp(self):
        from instaapi.api.scheduler import SchedulerAPI
        self.upload = MagicMock()
        self.stories = MagicMock()
        self.api = SchedulerAPI(self.upload, self.stories)
        # Create real temp files for scheduler validation
        self._tmpfiles = []
        for ext in [".jpg", ".jpg", ".mp4"]:
            f = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            f.close()
            self._tmpfiles.append(f.name)
        self.photo = self._tmpfiles[0]
        self.story = self._tmpfiles[1]
        self.video = self._tmpfiles[2]

    def tearDown(self):
        for f in self._tmpfiles:
            if os.path.exists(f):
                os.unlink(f)

    def test_init(self):
        self.assertIsNotNone(self.api)
        self.assertFalse(self.api._running)

    def test_schedule_post(self):
        dt = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        job = self.api.post_at(dt, photo=self.photo, caption="Test!")
        self.assertIn("id", job)
        self.assertEqual(job["status"], "pending")

    def test_schedule_story(self):
        dt = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        job = self.api.story_at(dt, photo=self.story)
        self.assertIn("id", job)

    def test_schedule_reel(self):
        dt = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        job = self.api.reel_at(dt, video=self.video, caption="Reel!")
        self.assertIn("id", job)

    def test_list_jobs(self):
        dt = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        self.api.post_at(dt, photo=self.photo, caption="Test")
        jobs = self.api.list_jobs()
        self.assertGreater(len(jobs), 0)

    def test_cancel_job(self):
        dt = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        job = self.api.post_at(dt, photo=self.photo, caption="Test")
        result = self.api.cancel(job["id"])
        self.assertTrue(result)

    def test_start_stop(self):
        self.api.start()
        self.assertTrue(self.api._running)
        self.api.stop()
        self.assertFalse(self.api._running)

    def test_file_not_found(self):
        dt = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        with self.assertRaises(FileNotFoundError):
            self.api.post_at(dt, photo="nonexistent.jpg", caption="Nope")


# ═══════════════════════════════════════════════════════════
# TEST: MultiAccountManager
# ═══════════════════════════════════════════════════════════

class TestMultiAccountManager(unittest.TestCase):
    """Test MultiAccountManager."""

    def test_init_empty(self):
        from instaapi.multi_account import MultiAccountManager
        mgr = MultiAccountManager()
        self.assertEqual(mgr.count, 0)

    def test_add_instance(self):
        from instaapi.multi_account import MultiAccountManager
        mgr = MultiAccountManager()
        mock_ig = MagicMock()
        # Remove _session_mgr so AccountInfo falls back to source
        del mock_ig._session_mgr
        mgr.add_instance(mock_ig, "test_account")
        self.assertEqual(mgr.count, 1)

    def test_get_account(self):
        from instaapi.multi_account import MultiAccountManager, AccountInfo
        mgr = MultiAccountManager()
        mock_ig = MagicMock()
        # Ensure _session_mgr is None so AccountInfo falls back to source as username
        mock_ig._session_mgr = None
        mgr.add_instance(mock_ig, "acc1")
        result = mgr.get("acc1")
        self.assertEqual(result, mock_ig)

    def test_get_nonexistent(self):
        from instaapi.multi_account import MultiAccountManager
        mgr = MultiAccountManager()
        result = mgr.get("nonexistent")
        self.assertIsNone(result)


# ═══════════════════════════════════════════════════════════
# TEST: GrowthAPI
# ═══════════════════════════════════════════════════════════

class TestGrowthAPI(unittest.TestCase):
    """Test GrowthAPI."""

    def setUp(self):
        from instaapi.api.growth import GrowthAPI, GrowthFilters, GrowthLimits
        self.client = MagicMock()
        self.users = MagicMock()
        self.friendships = MagicMock()
        self.api = GrowthAPI(self.client, self.users, self.friendships)

    def test_init(self):
        self.assertIsNotNone(self.api)

    def test_growth_limits_defaults(self):
        from instaapi.api.growth import GrowthLimits
        limits = GrowthLimits()
        self.assertGreater(limits.max_per_hour, 0)
        self.assertGreater(limits.min_delay, 0)

    def test_growth_filters_defaults(self):
        from instaapi.api.growth import GrowthFilters
        filters = GrowthFilters()
        self.assertEqual(filters.min_followers, 0)

    def test_whitelist_blacklist(self):
        self.api.add_whitelist(["friend1", "friend2"])
        self.assertIn("friend1", self.api._whitelist)
        self.api.add_blacklist(["spammer"])
        self.assertIn("spammer", self.api._blacklist)


# ═══════════════════════════════════════════════════════════
# TEST: AutomationAPI & TemplateEngine
# ═══════════════════════════════════════════════════════════

class TestTemplateEngine(unittest.TestCase):
    """Test TemplateEngine."""

    def test_basic_template(self):
        from instaapi.api.automation import TemplateEngine
        result = TemplateEngine.render("Hello {username}!", {"username": "cristiano"})
        self.assertEqual(result, "Hello cristiano!")

    def test_template_with_name(self):
        from instaapi.api.automation import TemplateEngine
        result = TemplateEngine.render("Hi {name}", {"name": "Cristiano"})
        self.assertEqual(result, "Hi Cristiano")

    def test_random_placeholder(self):
        from instaapi.api.automation import TemplateEngine
        result = TemplateEngine.render("Hey {random}")
        self.assertNotEqual(result, "Hey {random}")
        self.assertGreater(len(result), 4)

    def test_empty_context(self):
        from instaapi.api.automation import TemplateEngine
        result = TemplateEngine.render("Hey {username}")
        self.assertIn("Hey", result)


class TestAutomationAPI(unittest.TestCase):
    """Test AutomationAPI."""

    def test_init(self):
        from instaapi.api.automation import AutomationAPI
        client = MagicMock()
        direct = MagicMock()
        media = MagicMock()
        friendships = MagicMock()
        stories = MagicMock()
        api = AutomationAPI(client, direct, media, friendships, stories)
        self.assertIsNotNone(api)


# ═══════════════════════════════════════════════════════════
# TEST: MonitorAPI & AccountWatcher
# ═══════════════════════════════════════════════════════════

class TestAccountWatcher(unittest.TestCase):
    """Test AccountWatcher."""

    def test_create_watcher(self):
        from instaapi.api.monitor import AccountWatcher
        w = AccountWatcher("cristiano")
        self.assertEqual(w.username, "cristiano")
        self.assertIsNone(w.user_id)
        self.assertFalse(w.is_initialized)

    def test_register_callbacks(self):
        from instaapi.api.monitor import AccountWatcher
        w = AccountWatcher("test")
        cb = lambda: None
        w.on_new_post(cb)
        w.on_follower_change(cb)
        w.on_bio_change(cb)
        self.assertEqual(len(w._on_new_post), 1)
        self.assertEqual(len(w._on_follower_change), 1)
        self.assertEqual(len(w._on_bio_change), 1)

    def test_chaining(self):
        from instaapi.api.monitor import AccountWatcher
        w = AccountWatcher("test")
        result = w.on_new_post(lambda: None).on_follower_change(lambda a,b: None)
        self.assertIsInstance(result, AccountWatcher)

    def test_fire_safe(self):
        """Callbacks should not crash on exception."""
        from instaapi.api.monitor import AccountWatcher
        w = AccountWatcher("test")
        def bad_cb(): raise ValueError("boom")
        w.on_new_post(bad_cb)
        # Should not raise
        w._fire(w._on_new_post)


class TestMonitorAPI(unittest.TestCase):
    """Test MonitorAPI."""

    def setUp(self):
        from instaapi.api.monitor import MonitorAPI
        self.client = MagicMock()
        self.users = MagicMock()
        self.api = MonitorAPI(self.client, self.users)

    def test_watch(self):
        w = self.api.watch("testuser")
        self.assertEqual(w.username, "testuser")
        self.assertIn("testuser", self.api.watched_accounts)

    def test_watch_dedup(self):
        w1 = self.api.watch("testuser")
        w2 = self.api.watch("testuser")
        self.assertIs(w1, w2)
        self.assertEqual(self.api.watcher_count, 1)

    def test_unwatch(self):
        self.api.watch("testuser")
        self.assertTrue(self.api.unwatch("testuser"))
        self.assertFalse(self.api.unwatch("nonexistent"))
        self.assertEqual(self.api.watcher_count, 0)

    def test_start_stop(self):
        self.api.watch("test")
        user_mock = MagicMock()
        user_mock.pk = 1
        user_mock.username = "test"
        user_mock.followers = 100
        user_mock.follower_count = 100
        user_mock.following = 50
        user_mock.following_count = 50
        user_mock.media_count = 10
        user_mock.biography = "hi"
        user_mock.full_name = "Test"
        user_mock.is_private = False
        user_mock.is_verified = False
        user_mock.profile_pic_url = ""
        user_mock.external_url = ""
        self.users.get_by_username.return_value = user_mock

        self.api.start(interval=60)
        self.assertTrue(self.api.is_running)
        time.sleep(0.5)
        self.api.stop()
        self.assertFalse(self.api.is_running)

    def test_extract_state_dict(self):
        from instaapi.api.monitor import MonitorAPI
        state = MonitorAPI._extract_state({"pk": 1, "username": "test", "follower_count": 500})
        self.assertEqual(state["followers"], 500)
        self.assertEqual(state["username"], "test")

    def test_get_stats(self):
        self.api.watch("u1")
        self.api.watch("u2")
        stats = self.api.get_stats()
        self.assertEqual(stats["watched_accounts"], 2)
        self.assertFalse(stats["is_running"])


# ═══════════════════════════════════════════════════════════
# TEST: BulkDownloadAPI
# ═══════════════════════════════════════════════════════════

class TestBulkDownloadAPI(unittest.TestCase):
    """Test BulkDownloadAPI."""

    def test_init(self):
        from instaapi.api.bulk_download import BulkDownloadAPI
        api = BulkDownloadAPI(MagicMock(), MagicMock(), MagicMock())
        self.assertIsNotNone(api)

    def test_extract_photo(self):
        from instaapi.api.bulk_download import BulkDownloadAPI
        item = {"media_type": 1, "image_versions2": {"candidates": [
            {"url": "http://example.com/img.jpg", "width": 1080, "height": 1080}
        ]}}
        urls = BulkDownloadAPI._extract_media_urls(item)
        self.assertEqual(len(urls), 1)
        self.assertIn(".jpg", urls[0][1])

    def test_extract_video(self):
        from instaapi.api.bulk_download import BulkDownloadAPI
        item = {"media_type": 2, "video_versions": [
            {"url": "http://example.com/vid.mp4", "width": 1080, "height": 1920}
        ]}
        urls = BulkDownloadAPI._extract_media_urls(item)
        self.assertEqual(len(urls), 1)
        self.assertIn(".mp4", urls[0][1])

    def test_extract_carousel(self):
        from instaapi.api.bulk_download import BulkDownloadAPI
        item = {"media_type": 8, "carousel_media": [
            {"media_type": 1, "image_versions2": {"candidates": [{"url": "http://a.com/1.jpg", "width": 1}]}},
            {"media_type": 1, "image_versions2": {"candidates": [{"url": "http://a.com/2.jpg", "width": 1}]}},
        ]}
        urls = BulkDownloadAPI._extract_media_urls(item)
        self.assertEqual(len(urls), 2)

    def test_extract_empty(self):
        from instaapi.api.bulk_download import BulkDownloadAPI
        urls = BulkDownloadAPI._extract_media_urls({})
        self.assertEqual(len(urls), 0)


# ═══════════════════════════════════════════════════════════
# TEST: HashtagResearchAPI
# ═══════════════════════════════════════════════════════════

class TestHashtagResearchAPI(unittest.TestCase):
    """Test HashtagResearchAPI."""

    def setUp(self):
        from instaapi.api.hashtag_research import HashtagResearchAPI
        self.client = MagicMock()
        self.hashtags = MagicMock()
        self.api = HashtagResearchAPI(self.client, self.hashtags)

    def test_difficulty(self):
        self.assertEqual(self.api._calculate_difficulty(10_000_000), "very_hard")
        self.assertEqual(self.api._calculate_difficulty(500_000), "medium")
        self.assertEqual(self.api._calculate_difficulty(10_000), "very_easy")

    def test_competition_score(self):
        score = self.api._competition_score(1_000_000)
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 1)
        self.assertEqual(self.api._competition_score(0), 0.0)

    def test_suggest_audience_size(self):
        self.assertIn("500K", self.api._suggest_audience_size(6_000_000))
        self.assertIn("0-1K", self.api._suggest_audience_size(1000))

    def test_analyze_engagement_empty(self):
        result = self.api._analyze_engagement([])
        self.assertEqual(result["avg_likes"], 0)
        self.assertEqual(result["score"], 0)

    def test_analyze_engagement_data(self):
        posts = [
            {"like_count": 100, "comment_count": 10, "code": "a"},
            {"like_count": 200, "comment_count": 20, "code": "b"},
        ]
        result = self.api._analyze_engagement(posts)
        self.assertEqual(result["avg_likes"], 150)
        self.assertEqual(result["avg_comments"], 15)

    def test_extract_related(self):
        posts = [
            {"caption": {"text": "hello #python #coding"}},
            {"caption": {"text": "#python #dev #coding"}},
        ]
        related = self.api._extract_related(posts, "python")
        names = [r["name"] for r in related]
        self.assertIn("coding", names)
        self.assertNotIn("python", names)  # Should exclude source tag


# ═══════════════════════════════════════════════════════════
# TEST: PipelineAPI (SQLite)
# ═══════════════════════════════════════════════════════════

class TestPipelineAPI(unittest.TestCase):
    """Test PipelineAPI."""

    def setUp(self):
        from instaapi.api.pipeline import PipelineAPI
        self.client = MagicMock()
        self.users = MagicMock()
        self.friendships = MagicMock()
        self.media = MagicMock()
        self.api = PipelineAPI(self.client, self.users, self.friendships, self.media)

    def test_create_tables(self):
        """Test SQLite table creation."""
        from instaapi.api.pipeline import PipelineAPI
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            PipelineAPI._create_tables(cursor)
            conn.commit()
            # Verify tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            self.assertIn("profiles", tables)
            self.assertIn("posts", tables)
            self.assertIn("followers", tables)
            self.assertIn("following", tables)
            conn.close()
        finally:
            os.unlink(db_path)

    def test_user_to_dict_obj(self):
        from instaapi.api.pipeline import PipelineAPI
        user = MagicMock()
        user.pk = 123
        user.username = "test"
        user.full_name = "Test User"
        user.followers = 100
        user.follower_count = 100
        user.following = 50
        user.following_count = 50
        user.media_count = 10
        user.is_private = False
        user.is_verified = False
        user.biography = "bio"
        user.external_url = ""
        result = PipelineAPI._user_to_dict(user)
        self.assertEqual(result["username"], "test")
        self.assertEqual(result["followers"], 100)

    def test_user_to_dict_dict(self):
        from instaapi.api.pipeline import PipelineAPI
        user = {"pk": 123, "username": "test", "follower_count": 500}
        result = PipelineAPI._user_to_dict(user)
        self.assertEqual(result["followers"], 500)

    def test_to_jsonl(self):
        """Test JSONL export."""
        user_mock = MagicMock()
        user_mock.pk = 123
        user_mock.username = "test"
        user_mock.full_name = "Test"
        user_mock.followers = 100
        user_mock.follower_count = 100
        user_mock.following = 50
        user_mock.following_count = 50
        user_mock.media_count = 0
        user_mock.is_private = False
        user_mock.is_verified = False
        user_mock.biography = ""
        user_mock.external_url = ""
        self.users.get_by_username.return_value = user_mock
        self.client.request.return_value = {"items": [], "more_available": False}
        self.friendships.get_followers.return_value = {"users": []}

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            path = f.name
        try:
            result = self.api.to_jsonl("test", path, include_posts=False, include_followers=False)
            self.assertEqual(result["lines_written"], 1)  # Just profile
            self.assertTrue(os.path.exists(path))
            with open(path, "r") as f:
                line = json.loads(f.readline())
                self.assertEqual(line["_type"], "profile")
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════
# TEST: AISuggestAPI
# ═══════════════════════════════════════════════════════════

class TestAISuggestAPI(unittest.TestCase):
    """Test AISuggestAPI."""

    def setUp(self):
        from instaapi.api.ai_suggest import AISuggestAPI
        self.api = AISuggestAPI(MagicMock(), MagicMock())

    def test_extract_keywords(self):
        from instaapi.api.ai_suggest import AISuggestAPI
        kw = AISuggestAPI._extract_keywords("Beautiful sunset at the beach #nofilter @user")
        self.assertIn("beautiful", kw)
        self.assertIn("sunset", kw)
        self.assertIn("beach", kw)
        self.assertNotIn("the", kw)  # stopword
        self.assertNotIn("nofilter", kw)  # hashtag removed

    def test_detect_niche_fitness(self):
        from instaapi.api.ai_suggest import AISuggestAPI
        niche, conf = AISuggestAPI._detect_niche(["gym", "workout", "fitness", "muscle"])
        self.assertEqual(niche, "fitness")
        self.assertGreater(conf, 0)

    def test_detect_niche_empty(self):
        from instaapi.api.ai_suggest import AISuggestAPI
        niche, conf = AISuggestAPI._detect_niche([])
        self.assertEqual(niche, "general")
        self.assertEqual(conf, 0.0)

    def test_hashtags_from_caption(self):
        result = self.api.hashtags_from_caption("Beautiful sunset at the beach", count=10)
        self.assertIn("hashtags", result)
        self.assertIn("niche", result)
        self.assertGreater(len(result["hashtags"]), 0)
        self.assertLessEqual(len(result["hashtags"]), 10)

    def test_caption_ideas(self):
        captions = self.api.caption_ideas("travel", style="casual", count=3)
        self.assertEqual(len(captions), 3)
        for c in captions:
            self.assertIn("travel", c.lower())

    def test_caption_ideas_all_styles(self):
        for style in ["inspirational", "casual", "professional", "poetic", "funny"]:
            captions = self.api.caption_ideas("test", style=style, count=2)
            self.assertGreater(len(captions), 0)

    def test_optimal_set(self):
        result = self.api.optimal_set("programming", count=15)
        self.assertIn("hashtags", result)
        self.assertIn("difficulty_mix", result)
        self.assertGreater(len(result["hashtags"]), 0)

    def test_universal_tags(self):
        from instaapi.api.ai_suggest import AISuggestAPI
        tags = AISuggestAPI._get_universal_tags(5)
        self.assertEqual(len(tags), 5)
        self.assertIn("instagood", tags)

    def test_longtail_tags(self):
        from instaapi.api.ai_suggest import AISuggestAPI
        tags = AISuggestAPI._get_longtail_tags(["travel"], "travel", 10)
        self.assertGreater(len(tags), 0)


# ═══════════════════════════════════════════════════════════
# TEST: AudienceAPI
# ═══════════════════════════════════════════════════════════

class TestAudienceAPI(unittest.TestCase):
    """Test AudienceAPI."""

    def test_init(self):
        from instaapi.api.audience import AudienceAPI
        api = AudienceAPI(MagicMock(), MagicMock(), MagicMock())
        self.assertIsNotNone(api)

    def test_quality_score(self):
        from instaapi.api.audience import AudienceAPI
        self.assertEqual(AudienceAPI._audience_quality_score(0.1, 0.2, 1000, 50), "excellent")
        self.assertEqual(AudienceAPI._audience_quality_score(0, 0.8, 10, 1), "low")

    def test_score_candidates(self):
        from instaapi.api.audience import AudienceAPI
        candidates = {
            "user1": {"username": "user1", "weight": 5, "followers": 5000, "is_verified": True},
            "user2": {"username": "user2", "weight": 1, "followers": 100, "is_verified": False},
        }
        scored = AudienceAPI._score_candidates(candidates, "source")
        self.assertEqual(len(scored), 2)
        self.assertGreater(scored[0]["relevance_score"], 0)


# ═══════════════════════════════════════════════════════════
# TEST: CommentManagerAPI
# ═══════════════════════════════════════════════════════════

class TestCommentManagerAPI(unittest.TestCase):
    """Test CommentManagerAPI."""

    def setUp(self):
        from instaapi.api.comment_manager import CommentManagerAPI
        self.api = CommentManagerAPI(MagicMock(), MagicMock())

    def test_spam_detection(self):
        self.assertTrue(self.api._is_spam("Follow me for follow back! f4f"))
        self.assertTrue(self.api._is_spam("Check my profile link in bio"))
        self.assertTrue(self.api._is_spam("Earn $500 daily online"))
        self.assertTrue(self.api._is_spam("https://spam-link.com"))
        self.assertFalse(self.api._is_spam("This is a great photo!"))
        self.assertFalse(self.api._is_spam("Love this content ❤️"))

    def test_spam_repeated_emojis(self):
        self.assertTrue(self.api._is_spam("🔥🔥🔥🔥🔥🔥"))

    def test_sentiment_positive(self):
        from instaapi.api.comment_manager import CommentManagerAPI
        self.assertEqual(CommentManagerAPI._quick_sentiment("This is amazing and beautiful!"), "positive")
        self.assertEqual(CommentManagerAPI._quick_sentiment("love this ❤️ 🔥"), "positive")

    def test_sentiment_negative(self):
        from instaapi.api.comment_manager import CommentManagerAPI
        self.assertEqual(CommentManagerAPI._quick_sentiment("This is ugly and terrible"), "negative")
        self.assertEqual(CommentManagerAPI._quick_sentiment("hate this garbage awful"), "negative")

    def test_sentiment_neutral(self):
        from instaapi.api.comment_manager import CommentManagerAPI
        self.assertEqual(CommentManagerAPI._quick_sentiment("ok"), "neutral")
        self.assertEqual(CommentManagerAPI._quick_sentiment(""), "neutral")


# ═══════════════════════════════════════════════════════════
# TEST: ABTestAPI
# ═══════════════════════════════════════════════════════════

class TestABTestAPI(unittest.TestCase):
    """Test ABTestAPI."""

    def setUp(self):
        from instaapi.api.ab_test import ABTestAPI
        self.api = ABTestAPI(MagicMock())
        self.api._storage_file = tempfile.mktemp(suffix=".json")
        self.api._tests = {}

    def tearDown(self):
        if os.path.exists(self.api._storage_file):
            os.unlink(self.api._storage_file)

    def test_create_test(self):
        test = self.api.create("test1", variants={
            "A": {"caption": "Short"},
            "B": {"caption": "Long caption with details"},
        })
        self.assertIn("id", test)
        self.assertEqual(test["name"], "test1")
        self.assertEqual(test["status"], "created")
        self.assertEqual(len(test["variants"]), 2)

    def test_record_results(self):
        test = self.api.create("test2", variants={
            "A": {"caption": "A"},
            "B": {"caption": "B"},
        })
        self.api.record(test["id"], "A", likes=100, comments=20)
        self.api.record(test["id"], "B", likes=200, comments=40)

        stored = self.api.get_test(test["id"])
        self.assertEqual(stored["variants"]["A"]["likes"], 100)
        self.assertEqual(stored["variants"]["B"]["likes"], 200)

    def test_results_analysis(self):
        test = self.api.create("test3", variants={
            "A": {"caption": "A"},
            "B": {"caption": "B"},
        })
        self.api.record(test["id"], "A", likes=100, comments=10)
        self.api.record(test["id"], "B", likes=300, comments=50)

        result = self.api.results(test["id"])
        self.assertEqual(result["winner"], "B")
        self.assertGreater(result["improvement_pct"], 0)
        self.assertIn(result["confidence"], ["high", "medium", "low"])

    def test_list_tests(self):
        self.api.create("t1", variants={"A": {}})
        self.api.create("t2", variants={"A": {}})
        self.assertEqual(len(self.api.list_tests()), 2)
        self.assertEqual(len(self.api.list_tests(status="created")), 2)

    def test_delete_test(self):
        test = self.api.create("t1", variants={"A": {}})
        self.assertTrue(self.api.delete_test(test["id"]))
        self.assertFalse(self.api.delete_test("nonexistent"))
        self.assertEqual(len(self.api.list_tests()), 0)

    def test_record_invalid_test(self):
        with self.assertRaises(ValueError):
            self.api.record("fake_id", "A", likes=50)

    def test_results_invalid_test(self):
        with self.assertRaises(ValueError):
            self.api.results("fake_id")


# ═══════════════════════════════════════════════════════════
# TEST: CLI Argument Parsing
# ═══════════════════════════════════════════════════════════

class TestCLI(unittest.TestCase):
    """Test CLI argument parsing."""

    def test_parser_creation(self):
        from instaapi.cli import create_parser
        parser = create_parser()
        self.assertIsNotNone(parser)

    def test_profile_command(self):
        from instaapi.cli import create_parser
        parser = create_parser()
        args = parser.parse_args(["profile", "cristiano"])
        self.assertEqual(args.command, "profile")
        self.assertEqual(args.username, "cristiano")

    def test_export_followers(self):
        from instaapi.cli import create_parser
        parser = create_parser()
        args = parser.parse_args(["export", "followers", "user1", "-o", "out.csv"])
        self.assertEqual(args.command, "export")
        self.assertEqual(args.export_type, "followers")
        self.assertEqual(args.output, "out.csv")

    def test_analytics_engagement(self):
        from instaapi.cli import create_parser
        parser = create_parser()
        args = parser.parse_args(["analytics", "engagement", "user1"])
        self.assertEqual(args.analytics_type, "engagement")

    def test_analytics_compare(self):
        from instaapi.cli import create_parser
        parser = create_parser()
        args = parser.parse_args(["analytics", "compare", "a", "b", "c"])
        self.assertEqual(args.analytics_type, "compare")
        self.assertEqual(args.usernames, ["a", "b", "c"])

    def test_hashtag_analyze(self):
        from instaapi.cli import create_parser
        parser = create_parser()
        args = parser.parse_args(["hashtag", "analyze", "python"])
        self.assertEqual(args.hashtag_type, "analyze")
        self.assertEqual(args.tag, "python")

    def test_download_all(self):
        from instaapi.cli import create_parser
        parser = create_parser()
        args = parser.parse_args(["download", "all", "user", "-o", "dl/"])
        self.assertEqual(args.download_type, "all")
        self.assertEqual(args.output, "dl/")

    def test_pipeline_sqlite(self):
        from instaapi.cli import create_parser
        parser = create_parser()
        args = parser.parse_args(["pipeline", "sqlite", "user", "-o", "data.db"])
        self.assertEqual(args.pipeline_type, "sqlite")


if __name__ == "__main__":
    unittest.main()
