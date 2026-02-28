"""
Event System
=============
Webhook/Event system for instaharvest_v2.
Emit events on errors, retries, rate limits, etc.
Supports both sync and async callbacks.
"""

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


logger = logging.getLogger("instaharvest_v2.events")


class EventType(str, Enum):
    """Event types emitted by instaharvest_v2."""

    # Error events
    RATE_LIMIT = "rate_limit"
    CHALLENGE = "challenge"
    LOGIN_REQUIRED = "login_required"
    NETWORK_ERROR = "network_error"
    ERROR = "error"

    # Flow events
    RETRY = "retry"
    REQUEST = "request"
    SESSION_REFRESH = "session_refresh"

    # Info events
    SESSION_ROTATE = "session_rotate"
    PROXY_ROTATE = "proxy_rotate"


@dataclass
class EventData:
    """
    Event payload passed to callbacks.

    Attributes:
        event_type: Type of event
        timestamp: Unix timestamp when event occurred
        attempt: Current retry attempt number (0-indexed)
        endpoint: API endpoint that triggered the event
        error: Exception that caused the event (if error event)
        status_code: HTTP status code (if available)
        extra: Additional context data
    """

    event_type: EventType
    timestamp: float = field(default_factory=time.time)
    attempt: int = 0
    endpoint: str = ""
    error: Optional[Exception] = None
    status_code: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        parts = [f"EventData({self.event_type.value}"]
        if self.endpoint:
            parts.append(f", endpoint={self.endpoint!r}")
        if self.attempt:
            parts.append(f", attempt={self.attempt}")
        if self.error:
            parts.append(f", error={self.error!r}")
        parts.append(")")
        return "".join(parts)


# Callback type: sync or async function that takes EventData
EventCallback = Callable[[EventData], Any]


class EventEmitter:
    """
    Event emitter for instaharvest_v2.

    Register callbacks for specific events. Supports both
    sync and async callbacks.

    Usage:
        emitter = EventEmitter()
        emitter.on(EventType.RATE_LIMIT, lambda e: print(f"Rate limit on {e.endpoint}!"))
        emitter.on(EventType.RETRY, my_retry_handler)
        emitter.emit(EventType.RATE_LIMIT, endpoint="/users/123/info/")

    Async usage:
        async def handler(event: EventData):
            await send_telegram(f"Error: {event.error}")
        emitter.on(EventType.ERROR, handler)
    """

    def __init__(self):
        self._listeners: Dict[EventType, List[EventCallback]] = {}
        self._global_listeners: List[EventCallback] = []

    def on(self, event_type: Union[EventType, str], callback: EventCallback) -> "EventEmitter":
        """
        Register a callback for an event type.

        Args:
            event_type: Event to listen for (EventType enum or string)
            callback: Function(EventData) to call. Can be sync or async.

        Returns:
            self (for chaining)
        """
        if isinstance(event_type, str):
            event_type = EventType(event_type)

        if event_type not in self._listeners:
            self._listeners[event_type] = []

        self._listeners[event_type].append(callback)
        return self

    def on_all(self, callback: EventCallback) -> "EventEmitter":
        """Register a callback for ALL events."""
        self._global_listeners.append(callback)
        return self

    def off(self, event_type: Union[EventType, str], callback: EventCallback) -> "EventEmitter":
        """
        Remove a callback for an event type.

        Args:
            event_type: Event type to remove callback from
            callback: The callback function to remove

        Returns:
            self (for chaining)
        """
        if isinstance(event_type, str):
            event_type = EventType(event_type)

        listeners = self._listeners.get(event_type, [])
        if callback in listeners:
            listeners.remove(callback)
        return self

    def off_all(self, event_type: Optional[Union[EventType, str]] = None) -> "EventEmitter":
        """Remove all callbacks for a given event type, or all events."""
        if event_type is None:
            self._listeners.clear()
            self._global_listeners.clear()
        else:
            if isinstance(event_type, str):
                event_type = EventType(event_type)
            self._listeners.pop(event_type, None)
        return self

    def emit(self, event_type: Union[EventType, str], **kwargs) -> None:
        """
        Emit an event synchronously.

        Creates EventData from kwargs and calls all registered listeners.
        Async callbacks are scheduled if an event loop is running.

        Args:
            event_type: Event type to emit
            **kwargs: Fields for EventData (endpoint, attempt, error, etc.)
        """
        if isinstance(event_type, str):
            event_type = EventType(event_type)

        event = EventData(event_type=event_type, **kwargs)
        callbacks = self._listeners.get(event_type, []) + self._global_listeners

        for cb in callbacks:
            try:
                if inspect.iscoroutinefunction(cb):
                    # Schedule async callback safely
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(cb(event))
                    except RuntimeError:
                        # No running loop — skip async callback silently
                        # (it's a sync emit context, async callbacks won't work)
                        logger.debug(
                            f"Skipped async callback in sync context: {cb.__name__}"
                        )
                else:
                    cb(event)
            except Exception as e:
                logger.warning(f"Event callback error ({event_type.value}): {e}")

    async def emit_async(self, event_type: Union[EventType, str], **kwargs) -> None:
        """
        Emit an event asynchronously.

        Args:
            event_type: Event type to emit
            **kwargs: Fields for EventData
        """
        if isinstance(event_type, str):
            event_type = EventType(event_type)

        event = EventData(event_type=event_type, **kwargs)
        callbacks = self._listeners.get(event_type, []) + self._global_listeners

        for cb in callbacks:
            try:
                if inspect.iscoroutinefunction(cb):
                    await cb(event)
                else:
                    cb(event)
            except Exception as e:
                logger.warning(f"Async event callback error ({event_type.value}): {e}")

    @property
    def listener_count(self) -> int:
        """Total number of registered listeners."""
        count = len(self._global_listeners)
        for listeners in self._listeners.values():
            count += len(listeners)
        return count

    def has_listeners(self, event_type: Union[EventType, str]) -> bool:
        """Check if any listeners registered for event type."""
        if isinstance(event_type, str):
            event_type = EventType(event_type)
        return bool(self._listeners.get(event_type)) or bool(self._global_listeners)
