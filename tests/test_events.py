"""
Tests for EventEmitter: on/off/emit, sync/async callbacks, EventData.
"""

import pytest
from instaapi.events import EventEmitter, EventType, EventData


class TestEventType:
    """Test EventType enum values."""

    def test_values(self):
        assert EventType.RATE_LIMIT == "rate_limit"
        assert EventType.CHALLENGE == "challenge"
        assert EventType.LOGIN_REQUIRED == "login_required"
        assert EventType.NETWORK_ERROR == "network_error"
        assert EventType.RETRY == "retry"
        assert EventType.REQUEST == "request"
        assert EventType.SESSION_REFRESH == "session_refresh"

    def test_from_string(self):
        assert EventType("rate_limit") == EventType.RATE_LIMIT


class TestEventData:
    """Test EventData dataclass."""

    def test_defaults(self):
        event = EventData(event_type=EventType.RATE_LIMIT)
        assert event.event_type == EventType.RATE_LIMIT
        assert event.attempt == 0
        assert event.endpoint == ""
        assert event.error is None
        assert isinstance(event.extra, dict)

    def test_with_fields(self):
        err = ValueError("test")
        event = EventData(
            event_type=EventType.RETRY,
            attempt=3,
            endpoint="/users/123/",
            error=err,
            extra={"backoff": 4.5},
        )
        assert event.attempt == 3
        assert event.endpoint == "/users/123/"
        assert event.error is err
        assert event.extra["backoff"] == 4.5

    def test_repr(self):
        event = EventData(event_type=EventType.RETRY, endpoint="/test/")
        r = repr(event)
        assert "retry" in r
        assert "/test/" in r


class TestEventEmitter:
    """Test EventEmitter on/off/emit."""

    def test_on_and_emit(self):
        emitter = EventEmitter()
        received = []
        emitter.on(EventType.RATE_LIMIT, lambda e: received.append(e))
        emitter.emit(EventType.RATE_LIMIT, endpoint="/test/")
        assert len(received) == 1
        assert received[0].endpoint == "/test/"

    def test_multiple_listeners(self):
        emitter = EventEmitter()
        results = []
        emitter.on(EventType.RETRY, lambda e: results.append("a"))
        emitter.on(EventType.RETRY, lambda e: results.append("b"))
        emitter.emit(EventType.RETRY)
        assert results == ["a", "b"]

    def test_off(self):
        emitter = EventEmitter()
        results = []
        handler = lambda e: results.append("called")
        emitter.on(EventType.ERROR, handler)
        emitter.off(EventType.ERROR, handler)
        emitter.emit(EventType.ERROR)
        assert results == []

    def test_on_all(self):
        emitter = EventEmitter()
        received = []
        emitter.on_all(lambda e: received.append(e.event_type))
        emitter.emit(EventType.RATE_LIMIT)
        emitter.emit(EventType.RETRY)
        assert received == [EventType.RATE_LIMIT, EventType.RETRY]

    def test_off_all(self):
        emitter = EventEmitter()
        emitter.on(EventType.RETRY, lambda e: None)
        emitter.on(EventType.ERROR, lambda e: None)
        assert emitter.listener_count == 2
        emitter.off_all()
        assert emitter.listener_count == 0

    def test_off_all_specific(self):
        emitter = EventEmitter()
        emitter.on(EventType.RETRY, lambda e: None)
        emitter.on(EventType.ERROR, lambda e: None)
        emitter.off_all(EventType.RETRY)
        assert emitter.listener_count == 1

    def test_has_listeners(self):
        emitter = EventEmitter()
        assert emitter.has_listeners(EventType.RETRY) is False
        emitter.on(EventType.RETRY, lambda e: None)
        assert emitter.has_listeners(EventType.RETRY) is True

    def test_string_event_type(self):
        emitter = EventEmitter()
        received = []
        emitter.on("rate_limit", lambda e: received.append(True))
        emitter.emit("rate_limit")
        assert received == [True]

    def test_chaining(self):
        emitter = EventEmitter()
        result = emitter.on(EventType.RETRY, lambda e: None)
        assert result is emitter

    def test_callback_error_safety(self):
        emitter = EventEmitter()
        results = []
        emitter.on(EventType.ERROR, lambda e: 1/0)  # will raise ZeroDivisionError
        emitter.on(EventType.ERROR, lambda e: results.append("ok"))
        emitter.emit(EventType.ERROR)
        assert results == ["ok"]  # second callback still called

    def test_listener_count(self):
        emitter = EventEmitter()
        emitter.on(EventType.RETRY, lambda e: None)
        emitter.on(EventType.ERROR, lambda e: None)
        emitter.on_all(lambda e: None)
        assert emitter.listener_count == 3
