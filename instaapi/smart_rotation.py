"""
Smart Rotation Coordinator
===========================
Central brain that coordinates ALL rotation decisions:
  - Proxy rotation (weighted by success score)
  - Browser identity rotation (profile blacklisting)
  - TLS session rotation (curl_cffi impersonation)

Every request goes through this coordinator.
It tracks what combination was used and adjusts based on outcomes.

Architecture:
    ┌─────────────┐
    │  Coordinator │  ←  on_request_start() / on_request_success() / on_request_error()
    ├─────────────┤
    │  AntiDetect  │  ←  identity (UA, sec-ch-ua, platform)
    │  ProxyMgr    │  ←  proxy (IP rotation, scoring)
    │  TLS Session │  ←  curl_cffi impersonation
    └─────────────┘

Error → Action matrix:
    429 RateLimit       → rotate ALL (proxy+identity+TLS), pause, escalate
    Challenge/Checkpoint→ rotate identity+TLS, try auto-resolve
    NetworkError        → rotate proxy+TLS, keep identity
    LoginRequired       → keep proxy (it works), rotate identity
    NotFound/Private    → no rotation (valid response)
    3+ fails same proxy → blacklist proxy 5min
"""

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .anti_detect import AntiDetect
    from .proxy_manager import ProxyManager

logger = logging.getLogger("instaapi.rotation")


# ─── Rotation Context (one per request) ──────────────────────

@dataclass
class RotationContext:
    """
    Snapshot of everything used for ONE request.
    Created at request start, updated on success/error.
    Used for clear logging and smart decisions.
    """
    # Request info
    method: str = ""
    endpoint: str = ""
    attempt: int = 0
    max_attempts: int = 4
    start_time: float = field(default_factory=time.time)

    # What was used
    proxy_url: Optional[str] = None
    proxy_short: str = "direct"  # masked for logs: "185.x.x.x:8080"
    identity_browser: str = ""   # "Chrome 145"
    identity_platform: str = ""  # "Windows"
    impersonation: str = ""      # "chrome142"
    escalation: str = "NORMAL"   # current escalation level

    # Outcome (filled after request)
    status_code: int = 0
    elapsed_ms: float = 0
    error_type: str = ""
    error_message: str = ""
    action_taken: str = ""       # "ROTATE_ALL", "ROTATE_PROXY", etc.

    @property
    def endpoint_short(self) -> str:
        """Shortened endpoint for logs."""
        ep = self.endpoint
        if "instagram.com" in ep:
            ep = ep.split("instagram.com")[-1]
        if len(ep) > 50:
            ep = ep[:47] + "..."
        return ep

    def log_line(self, emoji: str, label: str) -> str:
        """Build rich one-line log string."""
        parts = [
            f"{emoji} {label}",
            f"│ {self.method} {self.endpoint_short}",
        ]
        if self.status_code:
            parts.append(f"│ HTTP {self.status_code}")
        parts.append(f"│ proxy={self.proxy_short}")
        parts.append(f"│ browser={self.identity_browser}/{self.identity_platform}")
        parts.append(f"│ attempt={self.attempt}/{self.max_attempts}")
        if self.elapsed_ms > 0:
            parts.append(f"│ {self.elapsed_ms:.0f}ms")
        if self.action_taken:
            parts.append(f"│ action={self.action_taken}")
        parts.append(f"│ mode={self.escalation}")
        return " ".join(parts)


def _mask_proxy(proxy_url: str) -> str:
    """Mask proxy URL for safe logging: 'http://user:pass@1.2.3.4:8080' → '1.2.x.x:8080'"""
    if not proxy_url:
        return "direct"
    try:
        # Extract host:port from URL
        url = proxy_url
        if "@" in url:
            url = url.split("@")[-1]
        if "://" in url:
            url = url.split("://")[-1]
        # Remove trailing slash
        url = url.rstrip("/")
        # Mask middle octets
        if ":" in url:
            host, port = url.rsplit(":", 1)
        else:
            host, port = url, "?"
        parts = host.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.x.x:{port}"
        return f"{host[:8]}..:{port}"
    except Exception:
        return "proxy:***"


# ─── Smart Rotation Coordinator ──────────────────────────────

class SmartRotationCoordinator:
    """
    Central rotation brain.
    Coordinates proxy, identity, and TLS session rotation.

    Usage:
        coord = SmartRotationCoordinator(anti_detect, proxy_mgr)

        # Before request:
        ctx = coord.on_request_start("GET", url, attempt, max_attempts)

        # After success:
        coord.on_request_success(ctx, status_code, elapsed)

        # After error:
        coord.on_request_error(ctx, error, status_code)
        # → returns action taken (for logging)
    """

    def __init__(
        self,
        anti_detect: "AntiDetect",
        proxy_manager: "ProxyManager",
    ):
        self._anti_detect = anti_detect
        self._proxy_mgr = proxy_manager
        self._lock = threading.Lock()

        # Stats
        self._total_requests: int = 0
        self._total_successes: int = 0
        self._total_errors: int = 0
        self._total_rotations: int = 0

        # Combo tracking: (proxy_hash, profile_idx) → {success, fail}
        self._combo_scores: Dict[str, Dict[str, int]] = {}

        # Proxy blacklist: proxy_url → unblock_time
        self._proxy_blacklist: Dict[str, float] = {}
        self._blacklist_duration: float = 300  # 5 min default

    # ─── Request Lifecycle ──────────────────────────────────

    def on_request_start(
        self,
        method: str,
        endpoint: str,
        attempt: int,
        max_attempts: int,
        proxy_url: Optional[str] = None,
    ) -> RotationContext:
        """
        Called BEFORE each request attempt.
        Returns RotationContext with all current state for logging.
        """
        with self._lock:
            self._total_requests += 1
            self._cleanup_blacklist()

        identity = self._anti_detect.get_identity()

        ctx = RotationContext(
            method=method,
            endpoint=endpoint,
            attempt=attempt,
            max_attempts=max_attempts,
            start_time=time.time(),
            proxy_url=proxy_url,
            proxy_short=_mask_proxy(proxy_url),
            identity_browser=f"{identity.browser_name.title()} {identity.browser_version}",
            identity_platform=identity.platform,
            impersonation=identity.impersonation,
            escalation=self._anti_detect.escalation_name,
        )

        return ctx

    def on_request_success(
        self,
        ctx: RotationContext,
        status_code: int = 200,
        elapsed_ms: float = 0,
    ) -> None:
        """Called after successful request."""
        ctx.status_code = status_code
        ctx.elapsed_ms = elapsed_ms

        with self._lock:
            self._total_successes += 1

        self._anti_detect.on_success()

        # Record combo success
        self._record_combo(ctx, success=True)

        # Log success (debug level — don't spam)
        logger.debug(ctx.log_line("✅", "OK"))

    def on_request_error(
        self,
        ctx: RotationContext,
        error: Exception,
        status_code: int = 0,
        rotate_proxy: bool = False,
        rotate_identity: bool = False,
        rotate_tls: bool = False,
        pause_seconds: float = 0,
    ) -> str:
        """
        Called after request error.
        Determines what to rotate based on error type.
        Returns action string for logging.

        The caller (client/_request) tells us what it considers appropriate,
        but we can override based on scoring data.
        """
        ctx.status_code = status_code
        ctx.elapsed_ms = (time.time() - ctx.start_time) * 1000
        ctx.error_type = type(error).__name__
        ctx.error_message = str(error)[:200]

        with self._lock:
            self._total_errors += 1

        # Record combo failure
        self._record_combo(ctx, success=False)

        # Build action description
        actions = []
        error_category = self._classify_error(error)

        # ─── Smart rotation decisions ────────────────────

        if error_category == "rate_limit":
            # Full rotation — change everything
            rotate_proxy = True
            rotate_identity = True
            rotate_tls = True
            self._anti_detect.on_error("rate_limit")
            actions.append("ROTATE_ALL")
            if pause_seconds > 0:
                actions.append(f"PAUSE_{pause_seconds:.0f}s")

        elif error_category == "challenge":
            # Identity is detected — switch identity + TLS
            rotate_identity = True
            rotate_tls = True
            self._anti_detect.on_error("challenge")
            actions.append("ROTATE_IDENTITY+TLS")

        elif error_category == "network":
            # Proxy problem — switch proxy + TLS, keep identity
            rotate_proxy = True
            rotate_tls = True
            self._anti_detect.on_error("network")
            actions.append("ROTATE_PROXY+TLS")

        elif error_category == "login":
            # Session dead — proxy still works, rotate identity
            rotate_identity = True
            self._anti_detect.on_error("login")
            actions.append("ROTATE_IDENTITY")

        elif error_category == "not_found":
            # Valid response, no rotation needed
            actions.append("NONE")

        elif error_category == "instagram_error":
            # Generic IG error — switch identity + TLS
            rotate_identity = True
            rotate_tls = True
            self._anti_detect.on_error("instagram")
            actions.append("ROTATE_IDENTITY+TLS")

        else:
            # Unknown — full rotation for safety
            rotate_proxy = True
            rotate_identity = True
            rotate_tls = True
            self._anti_detect.on_error("unknown")
            actions.append("ROTATE_ALL")

        # ─── Proxy blacklist check ───────────────────────
        if ctx.proxy_url and rotate_proxy:
            with self._lock:
                combo_key = self._combo_key(ctx)
                combo = self._combo_scores.get(combo_key, {"success": 0, "fail": 0})
                if combo["fail"] >= 3 and combo["success"] == 0:
                    self._proxy_blacklist[ctx.proxy_url] = time.time() + self._blacklist_duration
                    actions.append(f"BLACKLIST_PROXY_{self._blacklist_duration:.0f}s")
                    self._total_rotations += 1

        if rotate_proxy:
            if ctx.proxy_url:
                self._proxy_mgr.report_failure(ctx.proxy_url)

        if rotate_identity:
            with self._lock:
                self._total_rotations += 1

        action_str = "+".join(actions)
        ctx.action_taken = action_str

        # ─── Rich error logging ──────────────────────────
        emoji, label = self._error_label(error_category, status_code)
        log_msg = ctx.log_line(emoji, label)

        # Add error details
        if ctx.error_message:
            log_msg += f" │ detail={ctx.error_message[:100]}"

        # Choose log level based on severity
        if error_category in ("rate_limit", "challenge", "login"):
            logger.warning(log_msg)
        elif error_category == "network":
            logger.warning(log_msg)
        elif error_category == "not_found":
            logger.info(log_msg)
        else:
            logger.error(log_msg)

        return action_str

    # ─── Scoring ────────────────────────────────────────────

    def _combo_key(self, ctx: RotationContext) -> str:
        """Key for proxy+identity combo."""
        proxy_part = ctx.proxy_short if ctx.proxy_url else "direct"
        return f"{proxy_part}|{ctx.identity_browser}|{ctx.identity_platform}"

    def _record_combo(self, ctx: RotationContext, success: bool) -> None:
        """Record success/fail for proxy+identity combo."""
        key = self._combo_key(ctx)
        with self._lock:
            if key not in self._combo_scores:
                self._combo_scores[key] = {"success": 0, "fail": 0}
            if success:
                self._combo_scores[key]["success"] += 1
            else:
                self._combo_scores[key]["fail"] += 1

            # Cleanup old entries (keep last 50)
            if len(self._combo_scores) > 50:
                sorted_keys = sorted(
                    self._combo_scores.keys(),
                    key=lambda k: self._combo_scores[k]["success"] + self._combo_scores[k]["fail"],
                )
                for k in sorted_keys[:20]:
                    del self._combo_scores[k]

    def _cleanup_blacklist(self) -> None:
        """Remove expired blacklist entries."""
        now = time.time()
        expired = [url for url, unblock in self._proxy_blacklist.items() if unblock <= now]
        for url in expired:
            del self._proxy_blacklist[url]
            logger.info(f"🔓 Proxy un-blacklisted: {_mask_proxy(url)}")

    def is_proxy_blacklisted(self, proxy_url: str) -> bool:
        """Check if proxy is temporarily blacklisted."""
        with self._lock:
            return proxy_url in self._proxy_blacklist and self._proxy_blacklist[proxy_url] > time.time()

    # ─── Error Classification ───────────────────────────────

    @staticmethod
    def _classify_error(error: Exception) -> str:
        """Classify error into rotation category."""
        name = type(error).__name__
        if name == "RateLimitError":
            return "rate_limit"
        elif name in ("ChallengeRequired", "CheckpointRequired"):
            return "challenge"
        elif name == "LoginRequired":
            return "login"
        elif name == "NetworkError":
            return "network"
        elif name in ("NotFoundError", "PrivateAccountError"):
            return "not_found"
        elif name in ("ConsentRequired", "InstagramError"):
            return "instagram_error"
        else:
            return "unknown"

    @staticmethod
    def _error_label(category: str, status_code: int) -> tuple:
        """Return emoji + label for error category."""
        labels = {
            "rate_limit":      ("🚫", f"RATE LIMITED [{status_code or 429}]"),
            "challenge":       ("🔒", f"CHALLENGE [{status_code or 400}]"),
            "login":           ("🔑", f"LOGIN REQUIRED [{status_code or 401}]"),
            "network":         ("🌐", f"NETWORK ERROR [{status_code or 0}]"),
            "not_found":       ("🔍", f"NOT FOUND [{status_code or 404}]"),
            "instagram_error": ("⚠️", f"IG ERROR [{status_code or 400}]"),
            "unknown":         ("❌", f"UNKNOWN ERROR [{status_code or 0}]"),
        }
        return labels.get(category, ("❓", f"ERROR [{status_code}]"))

    # ─── Stats ──────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Get rotation statistics."""
        with self._lock:
            success_rate = (
                self._total_successes / self._total_requests * 100
                if self._total_requests > 0 else 0
            )
            return {
                "total_requests": self._total_requests,
                "total_successes": self._total_successes,
                "total_errors": self._total_errors,
                "success_rate": f"{success_rate:.1f}%",
                "total_rotations": self._total_rotations,
                "blacklisted_proxies": len(self._proxy_blacklist),
                "tracked_combos": len(self._combo_scores),
                "escalation": self._anti_detect.escalation_name,
                "identity": self._anti_detect.current_identity_info,
            }

    def get_summary_line(self) -> str:
        """One-line summary for periodic status logging."""
        stats = self.get_stats()
        return (
            f"📊 Rotation │ requests={stats['total_requests']} │ "
            f"success={stats['success_rate']} │ "
            f"rotations={stats['total_rotations']} │ "
            f"blacklisted={stats['blacklisted_proxies']} │ "
            f"mode={stats['escalation']}"
        )
