"""
Agent Streaming — Real-time Response Output
=============================================
Stream AI responses in real-time instead of waiting for completion.

Features:
    - Character-by-character or chunk-based streaming
    - Callback-based architecture (works with CLI and Web)
    - Progress indicators for long operations
    - Compatible with all providers that support streaming
"""

import logging
import sys
import time
from typing import Any, Callable, Dict, Generator, Optional

logger = logging.getLogger("instaapi.agent.streaming")


class StreamHandler:
    """
    Manages streaming output for agent responses.

    Usage:
        # CLI streaming
        handler = StreamHandler(mode="cli")
        handler.on_text("Hello ")
        handler.on_text("world!")
        handler.on_done()

        # Custom callback
        handler = StreamHandler(callback=my_func)
    """

    def __init__(
        self,
        mode: str = "cli",
        callback: Optional[Callable[[str, str], None]] = None,
        show_progress: bool = True,
    ):
        """
        Args:
            mode: Output mode — 'cli', 'web', 'callback', 'buffer'
            callback: Custom callback(event_type, data)
            show_progress: Show progress indicators
        """
        self._mode = mode
        self._callback = callback
        self._show_progress = show_progress
        self._buffer = []
        self._started = False
        self._start_time = 0

    def on_start(self):
        """Called when streaming starts."""
        self._started = True
        self._start_time = time.time()
        self._buffer.clear()
        self._emit("start", "")

    def on_text(self, text: str):
        """Called for each text chunk."""
        self._buffer.append(text)
        self._emit("text", text)

    def on_tool_call(self, tool_name: str, description: str = ""):
        """Called when agent makes a tool call."""
        self._emit("tool_call", f"{tool_name}: {description}")

    def on_tool_result(self, tool_name: str, result: str):
        """Called when a tool returns a result."""
        self._emit("tool_result", f"{tool_name}: {result[:200]}")

    def on_error(self, error: str):
        """Called on error."""
        self._emit("error", error)

    def on_step(self, step: int, total: int = 0):
        """Called at each agent step."""
        self._emit("step", f"{step}/{total}" if total else str(step))

    def on_done(self, summary: str = ""):
        """Called when streaming completes."""
        duration = time.time() - self._start_time if self._started else 0
        self._emit("done", f"{summary} ({duration:.1f}s)")
        self._started = False

    def get_buffer(self) -> str:
        """Get all buffered text."""
        return "".join(self._buffer)

    def _emit(self, event_type: str, data: str):
        """Emit an event based on mode."""
        if self._callback:
            self._callback(event_type, data)
            return

        if self._mode == "cli":
            self._cli_emit(event_type, data)
        elif self._mode == "buffer":
            pass  # Just buffer, no output
        # Web mode handled by callback

    def _cli_emit(self, event_type: str, data: str):
        """CLI output handler."""
        if event_type == "text":
            sys.stdout.write(data)
            sys.stdout.flush()
        elif event_type == "start":
            if self._show_progress:
                sys.stdout.write("\n🤖 ")
                sys.stdout.flush()
        elif event_type == "tool_call":
            if self._show_progress:
                print(f"\n  🔧 {data}")
        elif event_type == "tool_result":
            if self._show_progress:
                print(f"  ✅ {data[:100]}")
        elif event_type == "error":
            print(f"\n  ❌ {data}")
        elif event_type == "step":
            if self._show_progress:
                sys.stdout.write(f"\r  📍 Step {data}...")
                sys.stdout.flush()
        elif event_type == "done":
            if self._show_progress:
                print(f"\n✅ {data}")


class WebStreamHandler(StreamHandler):
    """
    Streaming handler for Web UI (SSE-compatible).

    Outputs events in Server-Sent Events format for real-time
    web streaming.
    """

    def __init__(self):
        super().__init__(mode="web")
        self._events = []

    def _emit(self, event_type: str, data: str):
        self._events.append({
            "event": event_type,
            "data": data,
            "timestamp": time.time(),
        })
        self._buffer.append(data if event_type == "text" else "")

    def get_events(self) -> list:
        """Get all events (for polling)."""
        events = self._events.copy()
        self._events.clear()
        return events

    def iter_events(self) -> Generator:
        """Iterate over events as SSE format."""
        for event in self._events:
            yield f"event: {event['event']}\ndata: {event['data']}\n\n"
