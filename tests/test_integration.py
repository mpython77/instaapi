"""
Integration Tests — Mock-based full flow testing.
Tests the entire pipeline: Instagram → client → response handler → models.
"""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from instaapi.events import EventEmitter, EventType, EventData
from instaapi.retry import RetryConfig
from instaapi.log_config import LogConfig
from instaapi.dashboard import Dashboard
from instaapi.plugin import Plugin, PluginManager
from instaapi.story_composer import StoryComposer, StoryDraft, StoryElement
from instaapi.proxy_manager import ProxyManager, ProxyInfo
from instaapi.proxy_health import ProxyHealthChecker


# ─── DASHBOARD TESTS ──────────────────────────────────────

class TestDashboard:
    """Test Dashboard statistics."""

    def test_initial_status(self):
        dashboard = Dashboard()
        status = dashboard.status()
        assert status["total_requests"] == 0
        assert status["total_errors"] == 0

    def test_manual_increment(self):
        dashboard = Dashboard()
        dashboard._inc("requests")
        dashboard._inc("requests")
        dashboard._inc("errors")
        assert dashboard._total_requests == 2
        assert dashboard._total_errors == 1

    def test_reset(self):
        dashboard = Dashboard()
        dashboard._inc("requests")
        dashboard.reset()
        assert dashboard._total_requests == 0

    def test_format_uptime(self):
        assert Dashboard._format_uptime(30) == "30s"
        assert Dashboard._format_uptime(90) == "1m 30s"
        assert Dashboard._format_uptime(3661) == "1h 1m 1s"

    def test_show_returns_string(self):
        dashboard = Dashboard()
        output = dashboard.show()
        assert "InstaAPI Dashboard" in output

    def test_repr(self):
        dashboard = Dashboard()
        assert "requests=0" in repr(dashboard)

    def test_event_tracking(self):
        emitter = EventEmitter()
        dashboard = Dashboard(event_emitter=emitter)
        emitter.emit(EventType.RETRY)
        assert dashboard._total_retries == 1


# ─── PLUGIN TESTS ─────────────────────────────────────────

class TestPlugin:
    """Test Plugin system."""

    def test_base_plugin(self):
        p = Plugin()
        assert p.name == "unnamed_plugin"
        assert p.version == "1.0.0"

    def test_custom_plugin(self):
        class MyPlugin(Plugin):
            name = "test_plugin"
            version = "2.0.0"
            description = "A test plugin"

        p = MyPlugin()
        assert p.name == "test_plugin"
        assert "test_plugin" in repr(p)

    def test_plugin_manager_install(self):
        pm = PluginManager()
        p = Plugin()
        p.name = "test"
        pm.install(p)
        assert pm.count == 1
        assert "test" in pm

    def test_plugin_manager_uninstall(self):
        pm = PluginManager()
        p = Plugin()
        p.name = "test"
        pm.install(p)
        assert pm.uninstall("test") is True
        assert pm.count == 0

    def test_uninstall_nonexistent(self):
        pm = PluginManager()
        assert pm.uninstall("nope") is False

    def test_list_plugins(self):
        pm = PluginManager()
        p = Plugin()
        p.name = "test"
        pm.install(p)
        plugins = pm.list_plugins()
        assert len(plugins) == 1
        assert plugins[0]["name"] == "test"

    def test_get_plugin(self):
        pm = PluginManager()
        p = Plugin()
        p.name = "test"
        pm.install(p)
        assert pm.get_plugin("test") is p
        assert pm.get_plugin("nope") is None

    def test_on_install_called(self):
        called = []

        class TestPlugin(Plugin):
            name = "test"
            def on_install(self, ig):
                called.append(ig)

        pm = PluginManager()
        pm.install(TestPlugin(), ig="mock_ig")
        assert called == ["mock_ig"]

    def test_on_uninstall_called(self):
        called = []

        class TestPlugin(Plugin):
            name = "test"
            def on_uninstall(self):
                called.append(True)

        pm = PluginManager()
        pm.install(TestPlugin())
        pm.uninstall("test")
        assert called == [True]

    def test_repr(self):
        pm = PluginManager()
        assert "PluginManager" in repr(pm)


# ─── STORY COMPOSER TESTS ─────────────────────────────────

class TestStoryComposer:
    """Test StoryComposer builder."""

    def test_image(self):
        sc = StoryComposer()
        result = sc.image("test.jpg")
        assert result is sc  # chaining
        assert sc._image_path == "test.jpg"

    def test_video(self):
        sc = StoryComposer()
        sc.video("test.mp4")
        assert sc._video_path == "test.mp4"

    def test_text(self):
        sc = StoryComposer()
        sc.text("Hello!", position=(0.3, 0.4), font_size=32)
        assert len(sc._elements) == 1
        assert sc._elements[0].type == "text"
        assert sc._elements[0].content == "Hello!"
        assert sc._elements[0].font_size == 32

    def test_mention(self):
        sc = StoryComposer()
        sc.mention("@user", position=(0.5, 0.8))
        assert sc._elements[0].type == "mention"
        assert sc._elements[0].content == "@user"

    def test_hashtag(self):
        sc = StoryComposer()
        sc.hashtag("#travel")
        assert sc._elements[0].type == "hashtag"

    def test_location(self):
        sc = StoryComposer()
        sc.location("12345")
        assert sc._elements[0].extra["location_id"] == "12345"

    def test_link(self):
        sc = StoryComposer()
        sc.link("https://example.com")
        assert sc._elements[0].content == "https://example.com"

    def test_poll(self):
        sc = StoryComposer()
        sc.poll("Best language?", options=["Python", "JS"])
        assert sc._elements[0].extra["options"] == ["Python", "JS"]

    def test_question(self):
        sc = StoryComposer()
        sc.question("Ask me anything!")
        assert sc._elements[0].type == "question"

    def test_chaining(self):
        sc = StoryComposer()
        result = sc.image("test.jpg").text("Hi").mention("@user").hashtag("#tag")
        assert result is sc
        assert len(sc._elements) == 3

    def test_build(self):
        sc = StoryComposer()
        sc.image("test.jpg").text("Hello")
        draft = sc.build()
        assert isinstance(draft, StoryDraft)
        assert draft.image_path == "test.jpg"
        assert len(draft.elements) == 1

    def test_draft_to_dict(self):
        sc = StoryComposer()
        sc.image("test.jpg").text("Hello")
        draft = sc.build()
        d = draft.to_dict()
        assert d["image"] == "test.jpg"
        assert len(d["elements"]) == 1

    def test_publish_no_ig_raises(self):
        draft = StoryDraft(image_path="test.jpg")
        with pytest.raises(ValueError, match="No Instagram"):
            draft.publish()

    def test_publish_no_media_raises(self):
        draft = StoryDraft(_ig=MagicMock())
        with pytest.raises(ValueError, match="No image"):
            draft.publish()

    def test_build_upload_data(self):
        sc = StoryComposer()
        sc.mention("@user", user_id="123")
        sc.hashtag("#tag")
        sc.link("https://x.com")
        draft = sc.build()
        data = draft._build_upload_data()
        assert "reel_mentions" in data
        assert "story_hashtags" in data
        assert "story_cta" in data

    def test_repr(self):
        sc = StoryComposer()
        sc.image("test.jpg").text("Hi")
        assert "test.jpg" in repr(sc)
        assert "1 elements" in repr(sc)


# ─── PROXY HEALTH TESTS ───────────────────────────────────

class TestProxyHealthChecker:
    """Test ProxyHealthChecker basics."""

    def test_init(self):
        pm = ProxyManager()
        checker = ProxyHealthChecker(pm)
        assert checker.is_running is False

    def test_start_stop(self):
        pm = ProxyManager()
        checker = ProxyHealthChecker(pm, interval=1)
        checker.start()
        assert checker.is_running is True
        checker.stop()
        assert checker.is_running is False

    def test_double_start(self):
        pm = ProxyManager()
        checker = ProxyHealthChecker(pm, interval=1)
        checker.start()
        checker.start()  # should not create second thread
        assert checker.is_running is True
        checker.stop()


# ─── EVENT INTEGRATION TESTS ──────────────────────────────

class TestEventIntegration:
    """Test event flow integration."""

    def test_emit_rate_limit_tracked_by_dashboard(self):
        emitter = EventEmitter()
        dashboard = Dashboard(event_emitter=emitter)
        emitter.emit(EventType.RATE_LIMIT, endpoint="/test/")
        assert dashboard._rate_limits_hit == 1

    def test_plugin_receives_events(self):
        received = []

        class TrackPlugin(Plugin):
            name = "tracker"
            def on_retry(self, event):
                received.append(event)

        emitter = EventEmitter()
        pm = PluginManager(event_emitter=emitter)
        pm.install(TrackPlugin())
        emitter.emit(EventType.RETRY, endpoint="/test/", attempt=1)
        assert len(received) == 1
        assert received[0].attempt == 1

    def test_full_event_chain(self):
        """Dashboard + Plugin both receive same event."""
        emitter = EventEmitter()
        dashboard = Dashboard(event_emitter=emitter)
        plugin_received = []

        class LogPlugin(Plugin):
            name = "log"
            def on_error(self, event):
                plugin_received.append(event)

        pm = PluginManager(event_emitter=emitter)
        pm.install(LogPlugin())
        emitter.emit(EventType.ERROR, error=ValueError("test"))

        assert dashboard._total_errors == 1
        assert len(plugin_received) == 1
