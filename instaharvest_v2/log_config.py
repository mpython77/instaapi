"""
Logging Configuration + DebugLogger
====================================
Centralized logging setup for instaharvest_v2.
Configures console + file handlers with custom formatting.

DebugLogger — structured, emoji-coded debug output for developers.
Activated with debug=True in Instagram() constructor.
"""

import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any, List


# Default log format
DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Debug format — compact, emoji-friendly
DEBUG_FORMAT = "%(asctime)s %(message)s"
DEBUG_DATE_FORMAT = "%H:%M:%S"

# Root logger name — all child loggers inherit
ROOT_LOGGER = "instaharvest_v2"


class LogConfig:
    """
    Centralized logging configuration for instaharvest_v2.

    One-call setup for all 15+ instaapi loggers.
    Supports console (colored) and file (rotating) handlers.

    Usage:
        LogConfig.configure(level="DEBUG", filename="instaharvest_v2.log")
        LogConfig.configure(level="WARNING", console=False)
    """

    _configured: bool = False

    @classmethod
    def configure(
        cls,
        level: str = "INFO",
        format: Optional[str] = None,
        date_format: Optional[str] = None,
        filename: Optional[str] = None,
        console: bool = True,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 3,
    ) -> logging.Logger:
        """
        Configure logging for all instaapi modules.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            format: Custom log format string (default: timestamp + level + name + message)
            date_format: Custom date format (default: YYYY-MM-DD HH:MM:SS)
            filename: Log file path (None = no file logging)
            console: Enable console output (default: True)
            max_bytes: Max log file size before rotation (default: 10MB)
            backup_count: Number of backup log files (default: 3)

        Returns:
            Root instaapi logger instance
        """
        root = logging.getLogger(ROOT_LOGGER)
        root.setLevel(getattr(logging, level.upper(), logging.INFO))

        # Remove existing handlers
        root.handlers.clear()

        # Format
        fmt = format or DEFAULT_FORMAT
        dtfmt = date_format or DEFAULT_DATE_FORMAT
        formatter = logging.Formatter(fmt, datefmt=dtfmt)

        # Console handler
        if console:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setFormatter(formatter)
            root.addHandler(console_handler)

        # File handler (rotating)
        if filename:
            file_handler = RotatingFileHandler(
                filename,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)

        # Prevent double output
        root.propagate = False

        cls._configured = True
        return root

    @classmethod
    def configure_debug(cls, filename: Optional[str] = None) -> logging.Logger:
        """
        Configure logging in debug mode — compact format with timestamps.

        Args:
            filename: Optional log file path

        Returns:
            Root instaapi logger
        """
        return cls.configure(
            level="DEBUG",
            format=DEBUG_FORMAT,
            date_format=DEBUG_DATE_FORMAT,
            filename=filename,
            console=True,
        )

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Get a child logger under 'instaharvest_v2' namespace.

        Args:
            name: Logger name (e.g., 'client' → 'instaharvest_v2.client')

        Returns:
            Logger instance
        """
        if not name.startswith(ROOT_LOGGER):
            name = f"{ROOT_LOGGER}.{name}"
        return logging.getLogger(name)

    @classmethod
    def set_level(cls, level: str) -> None:
        """Change log level at runtime."""
        root = logging.getLogger(ROOT_LOGGER)
        root.setLevel(getattr(logging, level.upper(), logging.INFO))

    @classmethod
    def silence(cls) -> None:
        """Disable all logging output."""
        logging.getLogger(ROOT_LOGGER).setLevel(logging.CRITICAL + 1)

    @classmethod
    def is_configured(cls) -> bool:
        """Check if logging has been configured."""
        return cls._configured


class DebugLogger:
    """
    Structured debug logger for instaharvest_v2.

    Provides emoji-coded, human-readable debug output.
    Activated with debug=True in Instagram() constructor.

    Categories:
        🔵 REQUEST   — outgoing HTTP request details
        🟢 RESPONSE  — successful response info
        🔴 ERROR     — error details + diagnostics
        🟡 SESSION   — session state changes
        🟣 IDENTITY  — anti-detect identity rotation
        🚨 BLOCK     — challenge/checkpoint/consent detection
        🔄 RETRY     — retry attempt with backoff info
        ⚡ RATE      — rate limiter events
        🌐 PROXY     — proxy rotation/health
        💾 COOKIE    — cookie updates from response

    Usage:
        dbg = DebugLogger(enabled=True)
        dbg.request("GET", "/api/v1/users/...", session_id="ds_123")
        dbg.response(200, elapsed_ms=245, size_bytes=12300)
        dbg.error("RateLimitError", status_code=429, endpoint="/api/v1/...")
    """

    def __init__(self, enabled: bool = False, log_file: Optional[str] = None):
        self.enabled = enabled
        self._logger = logging.getLogger("instaharvest_v2.debug")
        if enabled:
            LogConfig.configure_debug(filename=log_file)

    @staticmethod
    def _mask(value: str, show: int = 6) -> str:
        """Mask sensitive values, showing only first N chars."""
        if not value:
            return "<empty>"
        if len(value) <= show:
            return value
        return value[:show] + "***"

    @staticmethod
    def _mask_cookie_string(cookie_str: str) -> str:
        """Mask cookie values for safe logging."""
        if not cookie_str:
            return "<no cookies>"
        parts = []
        for pair in cookie_str.split("; "):
            if "=" in pair:
                key, val = pair.split("=", 1)
                parts.append(f"{key}={DebugLogger._mask(val, 8)}")
            else:
                parts.append(pair)
        return "; ".join(parts)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human-readable size."""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f}MB"

    # ─── REQUEST ─────────────────────────────────────────────

    def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        session_id: str = "",
        proxy: str = "",
        attempt: int = 1,
        max_attempts: int = 4,
        has_data: bool = False,
    ) -> None:
        """Log outgoing HTTP request."""
        if not self.enabled:
            return

        # Shorten URL for display
        short_url = url.replace("https://www.instagram.com", "")

        parts = [f"🔵 REQUEST {method} {short_url}"]
        if params:
            safe_params = {k: (v[:30] + "..." if isinstance(v, str) and len(v) > 30 else v) for k, v in params.items()}
            parts.append(f"params={safe_params}")
        if session_id:
            parts.append(f"session={self._mask(session_id)}")
        if proxy:
            parts.append(f"proxy={self._mask(proxy, 20)}")
        if has_data:
            parts.append("body=POST_DATA")
        parts.append(f"attempt={attempt}/{max_attempts}")

        self._logger.debug(" | ".join(parts))

    # ─── RESPONSE ────────────────────────────────────────────

    def response(
        self,
        status_code: int,
        elapsed_ms: float,
        size_bytes: int = 0,
        url: str = "",
        cookies_updated: Optional[List[str]] = None,
    ) -> None:
        """Log successful HTTP response."""
        if not self.enabled:
            return

        short_url = url.replace("https://www.instagram.com", "") if url else ""

        status_emoji = "🟢" if 200 <= status_code < 300 else "🟡"
        parts = [f"{status_emoji} RESPONSE {status_code}"]
        if short_url:
            parts.append(short_url)
        parts.append(f"{elapsed_ms:.0f}ms")
        if size_bytes:
            parts.append(self._format_size(size_bytes))
        if cookies_updated:
            parts.append(f"cookies_updated={','.join(cookies_updated)}")

        self._logger.debug(" | ".join(parts))

    # ─── ERROR ───────────────────────────────────────────────

    def error(
        self,
        error_type: str,
        status_code: int = 0,
        endpoint: str = "",
        message: str = "",
        escalation: str = "",
        response_preview: str = "",
    ) -> None:
        """Log error with full diagnostics."""
        if not self.enabled:
            return

        parts = [f"🔴 ERROR {error_type}"]
        if status_code:
            parts.append(f"HTTP {status_code}")
        if endpoint:
            short = endpoint.replace("https://www.instagram.com", "")
            parts.append(short)
        if message:
            parts.append(f"msg={message[:120]}")
        if escalation:
            parts.append(f"escalation={escalation}")
        if response_preview:
            parts.append(f"body={response_preview[:200]}")

        self._logger.debug(" | ".join(parts))

    # ─── SESSION ─────────────────────────────────────────────

    def session_info(
        self,
        ds_user_id: str = "",
        csrf_token: str = "",
        ig_www_claim: str = "",
        session_id: str = "",
        user_agent: str = "",
    ) -> None:
        """Log session state for diagnostics."""
        if not self.enabled:
            return

        parts = ["🟡 SESSION"]
        if ds_user_id:
            parts.append(f"user={ds_user_id}")
        if session_id:
            parts.append(f"sid={self._mask(session_id)}")
        if csrf_token:
            parts.append(f"csrf={self._mask(csrf_token)}")
        if ig_www_claim:
            parts.append(f"claim={self._mask(ig_www_claim)}")
        if user_agent:
            parts.append(f"ua={user_agent[:50]}...")

        self._logger.debug(" | ".join(parts))

    # ─── IDENTITY ROTATION ──────────────────────────────────

    def identity_rotated(
        self,
        old_browser: str = "",
        old_platform: str = "",
        new_browser: str = "",
        new_platform: str = "",
        reason: str = "",
        escalation_before: str = "",
        escalation_after: str = "",
        new_impersonation: str = "",
        blacklisted_profiles: int = 0,
    ) -> None:
        """Log anti-detect identity rotation."""
        if not self.enabled:
            return

        parts = ["🟣 IDENTITY ROTATED"]
        if old_browser and new_browser:
            parts.append(f"{old_browser} {old_platform} → {new_browser} {new_platform}")
        elif new_browser:
            parts.append(f"→ {new_browser} {new_platform}")
        if new_impersonation:
            parts.append(f"tls={new_impersonation}")
        if reason:
            parts.append(f"reason={reason}")
        if escalation_before and escalation_after and escalation_before != escalation_after:
            parts.append(f"escalation={escalation_before}→{escalation_after}")
        if blacklisted_profiles:
            parts.append(f"blacklisted={blacklisted_profiles}")

        self._logger.debug(" | ".join(parts))

    # ─── BLOCK / CHALLENGE ──────────────────────────────────

    def block_detected(
        self,
        block_type: str,
        url: str = "",
        contact_point: str = "",
        message: str = "",
        status_code: int = 0,
    ) -> None:
        """Log challenge/checkpoint/consent block detection."""
        if not self.enabled:
            return

        parts = [f"🚨 {block_type.upper()}"]
        if status_code:
            parts.append(f"HTTP {status_code}")
        if url:
            parts.append(f"url={url[:80]}")
        if contact_point:
            parts.append(f"contact={contact_point}")
        if message:
            parts.append(f"msg={message[:100]}")

        self._logger.debug(" | ".join(parts))

    # ─── RETRY ───────────────────────────────────────────────

    def retry(
        self,
        attempt: int,
        max_attempts: int,
        backoff_seconds: float,
        reason: str = "",
        endpoint: str = "",
    ) -> None:
        """Log retry attempt."""
        if not self.enabled:
            return

        parts = [f"🔄 RETRY {attempt}/{max_attempts}"]
        parts.append(f"backoff={backoff_seconds:.1f}s")
        if reason:
            parts.append(f"reason={reason}")
        if endpoint:
            short = endpoint.replace("https://www.instagram.com", "")
            parts.append(short)

        self._logger.debug(" | ".join(parts))

    # ─── RATE LIMIT ──────────────────────────────────────────

    def rate_limit(
        self,
        category: str = "",
        pause_seconds: float = 0,
        message: str = "",
    ) -> None:
        """Log rate limiter events."""
        if not self.enabled:
            return

        parts = ["⚡ RATE LIMIT"]
        if category:
            parts.append(f"category={category}")
        if pause_seconds:
            parts.append(f"pause={pause_seconds:.0f}s")
        if message:
            parts.append(message)

        self._logger.debug(" | ".join(parts))

    # ─── PROXY ───────────────────────────────────────────────

    def proxy_event(
        self,
        action: str,
        proxy: str = "",
        elapsed_ms: float = 0,
        message: str = "",
    ) -> None:
        """Log proxy rotation/health events."""
        if not self.enabled:
            return

        parts = [f"🌐 PROXY {action.upper()}"]
        if proxy:
            parts.append(self._mask(proxy, 20))
        if elapsed_ms:
            parts.append(f"{elapsed_ms:.0f}ms")
        if message:
            parts.append(message)

        self._logger.debug(" | ".join(parts))

    # ─── COOKIE UPDATE ──────────────────────────────────────

    def cookie_update(
        self,
        updated_keys: List[str],
        session_id: str = "",
    ) -> None:
        """Log cookie updates from response."""
        if not self.enabled:
            return

        if not updated_keys:
            return

        parts = ["💾 COOKIE UPDATE"]
        parts.append(f"keys={','.join(updated_keys)}")
        if session_id:
            parts.append(f"session={self._mask(session_id)}")

        self._logger.debug(" | ".join(parts))

    # ─── REDIRECT ────────────────────────────────────────────

    def redirect(
        self,
        url: str,
        location: str,
        is_login_redirect: bool = False,
    ) -> None:
        """Log HTTP redirect."""
        if not self.enabled:
            return

        short_url = url.replace("https://www.instagram.com", "")
        emoji = "🔴" if is_login_redirect else "↪️"
        parts = [f"{emoji} REDIRECT {short_url}"]
        parts.append(f"→ {location[:80]}")
        if is_login_redirect:
            parts.append("⚠️ LOGIN REDIRECT — session expired!")

        self._logger.debug(" | ".join(parts))

    # ─── DELAY ───────────────────────────────────────────────

    def delay(
        self,
        delay_seconds: float,
        action_type: str = "default",
        escalation_level: int = 0,
    ) -> None:
        """Log anti-detect delay."""
        if not self.enabled:
            return

        escalation_names = {0: "NORMAL", 1: "CAUTIOUS", 2: "STEALTH", 3: "PARANOID"}
        parts = [f"⏳ DELAY {delay_seconds:.2f}s"]
        parts.append(f"type={action_type}")
        if escalation_level > 0:
            parts.append(f"escalation={escalation_names.get(escalation_level, '?')}")

        self._logger.debug(" | ".join(parts))

    # ─── SESSION REFRESH ────────────────────────────────────

    def session_refresh(self, success: bool, method: str = "") -> None:
        """Log session refresh attempt."""
        if not self.enabled:
            return

        emoji = "🟢" if success else "🔴"
        status = "SUCCESS" if success else "FAILED"
        parts = [f"{emoji} SESSION REFRESH {status}"]
        if method:
            parts.append(f"method={method}")

        self._logger.debug(" | ".join(parts))


# ─── Global debug logger singleton ────────────────────────────
# Shared across all modules. Set by Instagram(debug=True).
_debug_logger: Optional[DebugLogger] = None


def get_debug_logger() -> DebugLogger:
    """Get the global DebugLogger instance."""
    global _debug_logger
    if _debug_logger is None:
        _debug_logger = DebugLogger(enabled=False)
    return _debug_logger


def set_debug_logger(logger: DebugLogger) -> None:
    """Set the global DebugLogger instance."""
    global _debug_logger
    _debug_logger = logger
