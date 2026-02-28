"""
Agent Memory — Conversation Persistence
========================================
Save and load conversation history for continuity across sessions.

Features:
    - Save chat history to JSON files
    - Load previous sessions automatically
    - Search through past conversations
    - Configurable retention (max sessions, max age)
    - Compact storage (deduplicate system prompts)
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("instaapi.agent.memory")

DEFAULT_MEMORY_DIR = ".instaapi_memory"
MAX_SESSIONS = 50
MAX_HISTORY_SIZE = 100  # messages per session


class AgentMemory:
    """
    Persistent memory for agent conversations.

    Stores conversation history as JSON files, enabling the agent
    to recall past interactions and maintain context across sessions.

    Usage:
        memory = AgentMemory()
        memory.save_session("sess_001", messages, metadata)
        old = memory.load_session("sess_001")
        results = memory.search("cristiano followers")
    """

    def __init__(
        self,
        memory_dir: Optional[str] = None,
        max_sessions: int = MAX_SESSIONS,
        max_history: int = MAX_HISTORY_SIZE,
    ):
        self._dir = Path(memory_dir or DEFAULT_MEMORY_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max_sessions = max_sessions
        self._max_history = max_history
        self._index_path = self._dir / "index.json"
        self._index = self._load_index()

    # ═══════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════

    def save_session(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        metadata: Optional[Dict] = None,
    ) -> str:
        """Save conversation to disk."""
        # Filter out system prompts (save space)
        filtered = [m for m in messages if m.get("role") != "system"]

        # Truncate if too long
        if len(filtered) > self._max_history:
            filtered = filtered[-self._max_history:]

        session_data = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "message_count": len(filtered),
            "messages": filtered,
            "metadata": metadata or {},
        }

        # Generate summary from last user message
        summary = self._extract_summary(filtered)
        session_data["summary"] = summary

        # Save session file
        filepath = self._dir / f"{session_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

        # Update index
        self._index[session_id] = {
            "created_at": session_data["created_at"],
            "summary": summary,
            "message_count": len(filtered),
            "metadata": metadata or {},
        }
        self._save_index()
        self._cleanup_old_sessions()

        logger.info(f"Session saved: {session_id} ({len(filtered)} messages)")
        return filepath.as_posix()

    def load_session(self, session_id: str) -> Optional[Dict]:
        """Load a saved session."""
        filepath = self._dir / f"{session_id}.json"
        if not filepath.exists():
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    def load_latest(self) -> Optional[Dict]:
        """Load the most recent session."""
        if not self._index:
            return None

        latest_id = max(
            self._index.keys(),
            key=lambda k: self._index[k].get("created_at", ""),
        )
        return self.load_session(latest_id)

    def list_sessions(self, limit: int = 20) -> List[Dict]:
        """List saved sessions (newest first)."""
        sessions = []
        for sid, info in sorted(
            self._index.items(),
            key=lambda x: x[1].get("created_at", ""),
            reverse=True,
        ):
            sessions.append({
                "session_id": sid,
                **info,
            })
            if len(sessions) >= limit:
                break
        return sessions

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """Search through past conversations."""
        query_lower = query.lower()
        results = []

        for sid in self._index:
            session = self.load_session(sid)
            if not session:
                continue

            score = 0
            matching_messages = []

            for msg in session.get("messages", []):
                content = msg.get("content", "")
                if isinstance(content, str) and query_lower in content.lower():
                    score += 1
                    matching_messages.append({
                        "role": msg["role"],
                        "snippet": content[:200],
                    })

            if score > 0:
                results.append({
                    "session_id": sid,
                    "score": score,
                    "summary": session.get("summary", ""),
                    "created_at": session.get("created_at", ""),
                    "matches": matching_messages[:3],
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def get_context_messages(self, limit: int = 10) -> List[Dict]:
        """Get recent messages from last session for context injection."""
        latest = self.load_latest()
        if not latest:
            return []

        messages = latest.get("messages", [])
        # Return last N messages (user + assistant only)
        relevant = [
            m for m in messages
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        return relevant[-limit:]

    def clear(self):
        """Clear all saved sessions."""
        import shutil
        if self._dir.exists():
            shutil.rmtree(self._dir)
            self._dir.mkdir(parents=True, exist_ok=True)
        self._index = {}
        self._save_index()
        logger.info("Memory cleared")

    @property
    def session_count(self) -> int:
        return len(self._index)

    # ═══════════════════════════════════════════════════════
    # INTERNAL
    # ═══════════════════════════════════════════════════════

    def _load_index(self) -> Dict:
        if self._index_path.exists():
            try:
                with open(self._index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_index(self):
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)

    def _cleanup_old_sessions(self):
        """Remove oldest sessions if over limit."""
        if len(self._index) <= self._max_sessions:
            return

        sorted_ids = sorted(
            self._index.keys(),
            key=lambda k: self._index[k].get("created_at", ""),
        )

        to_remove = sorted_ids[:len(sorted_ids) - self._max_sessions]
        for sid in to_remove:
            filepath = self._dir / f"{sid}.json"
            if filepath.exists():
                filepath.unlink()
            del self._index[sid]

        self._save_index()

    @staticmethod
    def _extract_summary(messages: List[Dict]) -> str:
        """Extract a summary from conversation messages."""
        user_messages = [
            m.get("content", "")
            for m in messages
            if m.get("role") == "user" and isinstance(m.get("content"), str)
        ]
        if user_messages:
            # Use first user message as summary
            first = user_messages[0][:150]
            return first.strip()
        return "Empty session"

    @staticmethod
    def generate_session_id() -> str:
        """Generate a unique session ID."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        rand = hashlib.md5(str(time.time()).encode()).hexdigest()[:6]
        return f"sess_{ts}_{rand}"
