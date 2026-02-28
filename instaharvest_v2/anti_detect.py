"""
Anti-Detection System v2
========================
Full protection against Instagram bot detection.

Core principles:
    1. INSTANT IDENTITY SWITCH — on error or detection,
       next requests come from a completely different identity
    2. COHERENT FINGERPRINTS — User-Agent, Sec-Ch-Ua, Platform
       are consistent (Chrome 131 UA + Chrome 131 sec-ch-ua)
    3. NATURAL BEHAVIOR — Gaussian distributed delays, session aging
    4. ERROR ESCALATION — protection increases as error count grows

Rotation triggers:
    - Every 20-80 requests (normal)
    - 429 RateLimit response -> INSTANTLY rotated
    - ChallengeRequired -> INSTANTLY rotated
    - Any Instagram error -> INSTANTLY rotated
    - Proxy failure -> fingerprint + curl session rotated
"""

import random
import time
import hashlib
import uuid
import math
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .config import (
    USER_AGENTS,
    ACCEPT_LANGUAGES,
    SEC_CH_UA_VARIANTS,
    BROWSER_IMPERSONATIONS,
    REQUEST_DELAYS,
    IG_APP_ID,
)


def _dbg():
    """Lazy import to avoid circular dependency."""
    from .log_config import get_debug_logger
    return get_debug_logger()


@dataclass
class BrowserIdentity:
    """
    Complete browser identity.
    All headers must be consistent with each other.
    """
    user_agent: str
    sec_ch_ua: str
    sec_ch_ua_mobile: str
    sec_ch_ua_platform: str
    accept_language: str
    viewport_width: int
    viewport_height: int
    platform: str  # internal: Windows, macOS, Linux
    browser_name: str  # chrome, safari, firefox
    browser_version: str
    impersonation: str  # curl_cffi impersonation key
    device_id: str
    # Unique per-identity
    x_mid: str  # machine ID
    window_id: str  # browser tab ID


# ──────────────────────────────────────────────────────────
# Coherent browser profiles
# Each profile has matching User-Agent, sec-ch-ua, impersonation
# IMPORTANT: impersonation must match curl_cffi's TLS fingerprint
# Available: chrome142 (newest), chrome136, chrome131
# ──────────────────────────────────────────────────────────
BROWSER_PROFILES: List[Dict] = [
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Not A Brand";v="99", "Google Chrome";v="142", "Chromium";v="142"',
        "platform": "Windows",
        "browser": "chrome",
        "version": "142",
        "impersonation": "chrome142",
        "mobile": False,
    },
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Not A Brand";v="99", "Google Chrome";v="142", "Chromium";v="142"',
        "platform": "macOS",
        "browser": "chrome",
        "version": "142",
        "impersonation": "chrome142",
        "mobile": False,
    },
    {
        "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Not A Brand";v="99", "Google Chrome";v="142", "Chromium";v="142"',
        "platform": "Linux",
        "browser": "chrome",
        "version": "142",
        "impersonation": "chrome142",
        "mobile": False,
    },
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Chromium";v="136", "Not A Brand";v="99", "Google Chrome";v="136"',
        "platform": "Windows",
        "browser": "chrome",
        "version": "136",
        "impersonation": "chrome136",
        "mobile": False,
    },
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Chromium";v="136", "Not A Brand";v="99", "Google Chrome";v="136"',
        "platform": "macOS",
        "browser": "chrome",
        "version": "136",
        "impersonation": "chrome136",
        "mobile": False,
    },
]

VIEWPORTS = [
    (1920, 1080), (1366, 768), (1536, 864), (1440, 900),
    (1280, 720), (2560, 1440), (1680, 1050), (1600, 900),
    (1920, 1200), (1280, 800),
]

TIMEZONE_OFFSETS = [-480, -420, -360, -300, -240, 0, 60, 120, 180, 300, 330, 540]
SCREEN_DENSITIES = [1.0, 1.25, 1.5, 1.75, 2.0]


class AntiDetect:
    """
    Smart anti-detection system.

    Features:
        1. COHERENT identity — UA, sec-ch-ua, platform always consistent
        2. INSTANT SWITCH — instantly switch to another identity on error
        3. NATURAL timing — Gaussian delay + session aging
        4. ADAPTIVE — protection escalates with more errors
        5. ERROR-AWARE — different strategy per error type
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._last_request_time: float = 0
        self._request_count: int = 0
        self._error_count: int = 0
        self._consecutive_errors: int = 0

        # Identity
        self._current_identity: Optional[BrowserIdentity] = None
        self._identity_uses: int = 0
        self._identity_max_uses: int = random.randint(20, 80)
        self._identity_created_at: float = 0

        # Identity history (to avoid repetition)
        self._used_profiles: List[int] = []

        # Error escalation
        self._escalation_level: int = 0  # 0=normal, 1=cautious, 2=stealth, 3=paranoid

        # ─── Profile Scoring ────────────────────────────
        # Track success/fail per profile index
        self._profile_scores: Dict[int, Dict[str, int]] = {}
        # Temporarily blocked profiles: idx → unblock_time
        self._profile_blacklist: Dict[int, float] = {}
        self._profile_blacklist_duration: float = 300  # 5 min

    # ─── IDENTITY MANAGEMENT ───────────────────────────────

    def get_identity(self, force_new: bool = False) -> BrowserIdentity:
        """
        Get current browser identity.
        Creates a new identity when needed.
        Thread-safe — uses internal lock.

        force_new=True — immediately create new identity (on error)
        """
        with self._lock:
            should_rotate = (
                force_new
                or self._current_identity is None
                or self._identity_uses >= self._identity_max_uses
                or (time.time() - self._identity_created_at > random.uniform(180, 600))
            )

            if should_rotate:
                self._current_identity = self._create_identity()
                self._identity_uses = 0
                self._identity_created_at = time.time()
                # New max uses
                if self._escalation_level >= 2:
                    self._identity_max_uses = random.randint(5, 15)
                elif self._escalation_level >= 1:
                    self._identity_max_uses = random.randint(10, 30)
                else:
                    self._identity_max_uses = random.randint(20, 80)

            self._identity_uses += 1
            return self._current_identity

    def _create_identity(self) -> BrowserIdentity:
        """Create a new fully coherent browser identity with scoring."""
        now = time.time()

        # Clean up expired blacklist entries
        expired = [idx for idx, t in self._profile_blacklist.items() if t <= now]
        for idx in expired:
            del self._profile_blacklist[idx]

        # Select profile — weighted by score, exclude blacklisted
        available = []
        for i in range(len(BROWSER_PROFILES)):
            if i in self._profile_blacklist:
                continue
            # Exclude recently used (last 3)
            if i in self._used_profiles[-3:] and len(BROWSER_PROFILES) > 3:
                continue
            available.append(i)

        # Fallback if all blocked
        if not available:
            available = list(range(len(BROWSER_PROFILES)))

        # Weighted selection by score
        weights = []
        for i in available:
            scores = self._profile_scores.get(i, {"success": 1, "fail": 0})
            total = scores["success"] + scores["fail"]
            if total > 0:
                weight = max(0.1, scores["success"] / total)
            else:
                weight = 1.0  # new profiles get full weight
            weights.append(weight)

        # Weighted random choice
        total_w = sum(weights)
        r = random.random() * total_w
        cumulative = 0
        idx = available[0]
        for i, w in zip(available, weights):
            cumulative += w
            if r <= cumulative:
                idx = i
                break

        self._used_profiles.append(idx)
        if len(self._used_profiles) > 10:
            self._used_profiles = self._used_profiles[-5:]

        profile = BROWSER_PROFILES[idx]
        viewport = random.choice(VIEWPORTS)

        # Platform string
        plat = profile["platform"]
        sec_platform = f'"{plat}"'

        return BrowserIdentity(
            user_agent=profile["ua"],
            sec_ch_ua=profile["sec_ch_ua"],
            sec_ch_ua_mobile="?1" if profile.get("mobile") else "?0",
            sec_ch_ua_platform=sec_platform,
            accept_language=random.choice(ACCEPT_LANGUAGES),
            viewport_width=viewport[0],
            viewport_height=viewport[1],
            platform=plat,
            browser_name=profile["browser"],
            browser_version=profile["version"],
            impersonation=profile["impersonation"],
            device_id=self._generate_device_id(),
            x_mid=self._generate_mid(),
            window_id=str(random.randint(1, 999999)),
        )

    # ─── ERROR HANDLING — INSTANT ROTATION ──────────────────

    def on_error(self, error_type: str = "unknown") -> None:
        """
        Called on error.
        Instantly switches identity and raises protection level.
        Thread-safe.

        error_type:
            "rate_limit"  — 429 response (serious)
            "challenge"   — captcha/challenge (very serious)
            "login"       — session dead
            "network"     — network error
            "unknown"     — other error
        """
        with self._lock:
            self._error_count += 1
            self._consecutive_errors += 1

            # Score the current profile as failed
            if self._current_identity:
                current_idx = self._used_profiles[-1] if self._used_profiles else 0
                if current_idx not in self._profile_scores:
                    self._profile_scores[current_idx] = {"success": 0, "fail": 0}
                self._profile_scores[current_idx]["fail"] += 1

                # Blacklist profile if too many failures
                scores = self._profile_scores[current_idx]
                if scores["fail"] >= 3 and scores["success"] == 0:
                    self._profile_blacklist[current_idx] = (
                        time.time() + self._profile_blacklist_duration
                    )

            # Determine escalation level
            if error_type in ("challenge", "checkpoint"):
                self._escalation_level = min(3, self._escalation_level + 2)
            elif error_type == "rate_limit":
                self._escalation_level = min(3, self._escalation_level + 1)
            elif self._consecutive_errors >= 3:
                self._escalation_level = min(3, self._escalation_level + 1)

            # Immediately create new identity
            old_identity = self._current_identity
            old_escalation = self.escalation_name
            self._current_identity = self._create_identity()
            self._identity_uses = 0
            self._identity_created_at = time.time()

            # Build rotation summary
            new_i = self._current_identity
            rotation_summary = {
                "old_browser": f"{old_identity.browser_name} {old_identity.browser_version}" if old_identity else "",
                "old_platform": old_identity.platform if old_identity else "",
                "new_browser": f"{new_i.browser_name} {new_i.browser_version}",
                "new_platform": new_i.platform,
                "new_impersonation": new_i.impersonation,
                "reason": error_type,
                "escalation_before": old_escalation,
                "escalation_after": self.escalation_name,
                "blacklisted_profiles": len(self._profile_blacklist),
            }

            # Debug: log identity rotation + escalation change
            _dbg().identity_rotated(**rotation_summary)

            return rotation_summary

    def on_success(self) -> None:
        """Successful request — reduce escalation, score profile. Thread-safe."""
        with self._lock:
            self._consecutive_errors = 0

            # Score current profile as successful
            if self._used_profiles:
                current_idx = self._used_profiles[-1]
                if current_idx not in self._profile_scores:
                    self._profile_scores[current_idx] = {"success": 0, "fail": 0}
                self._profile_scores[current_idx]["success"] += 1

            # Gradually return to normal state
            if self._request_count % 50 == 0 and self._escalation_level > 0:
                self._escalation_level = max(0, self._escalation_level - 1)

    # ─── HEADER GENERATION ──────────────────────────────────

    def get_request_headers(
        self,
        csrf_token: str,
        extra_headers: Optional[Dict] = None,
    ) -> Dict[str, str]:
        """
        Full request headers.
        Coherent headers are generated from the identity.
        """
        identity = self.get_identity()

        headers = {
            "user-agent": identity.user_agent,
            "accept": "*/*",
            "accept-language": identity.accept_language,
            "accept-encoding": "gzip, deflate, br",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            # Instagram-specific
            "x-csrftoken": csrf_token,
            "x-ig-app-id": IG_APP_ID,
            "x-requested-with": "XMLHttpRequest",
            # x-ig-www-claim — only added if present in session
            "x-instagram-ajax": "1033859812",
            "referer": "https://www.instagram.com/",
            "origin": "https://www.instagram.com",
        }

        # Chrome and Edge have sec-ch-ua, Safari and Firefox don't
        if identity.sec_ch_ua:
            headers["sec-ch-ua"] = identity.sec_ch_ua
            headers["sec-ch-ua-mobile"] = identity.sec_ch_ua_mobile
            headers["sec-ch-ua-platform"] = identity.sec_ch_ua_platform
            headers["sec-ch-ua-full-version-list"] = identity.sec_ch_ua

        # Additional headers in paranoid mode
        if self._escalation_level >= 2:
            headers["x-asbd-id"] = str(random.randint(100000, 999999))
        else:
            headers["x-asbd-id"] = "359341"

        if extra_headers:
            headers.update(extra_headers)

        return headers

    def get_post_headers(
        self,
        csrf_token: str,
        extra_headers: Optional[Dict] = None,
    ) -> Dict[str, str]:
        """Special headers for POST requests."""
        headers = self.get_request_headers(csrf_token, extra_headers)
        headers["content-type"] = "application/x-www-form-urlencoded"
        return headers

    def get_browser_impersonation(self) -> str:
        """Get curl_cffi impersonation matching current identity."""
        identity = self.get_identity()
        return identity.impersonation

    # ─── TIMING ─────────────────────────────────────────────

    def human_delay(self, action_type: str = "default") -> None:
        """
        Human-like delay (Gaussian distribution).
        Delay increases with higher protection levels.
        Thread-safe — calculates delay under lock, sleeps outside.
        """
        delay = self.get_delay(action_type)
        time.sleep(delay)

    def get_delay(self, action_type: str = "default") -> float:
        """
        Calculate human-like delay WITHOUT sleeping.
        For async clients that need the value to await asyncio.sleep().
        Thread-safe.

        Returns:
            Delay in seconds
        """
        with self._lock:
            now = time.time()

            if action_type == "after_action":
                delays = REQUEST_DELAYS["after_action"]
            elif action_type == "after_error":
                delays = REQUEST_DELAYS["after_error"]
            elif action_type == "after_rate_limit":
                delays = REQUEST_DELAYS["after_rate_limit"]
            else:
                delays = {"min": REQUEST_DELAYS["min"], "max": REQUEST_DELAYS["max"]}

            escalation_multiplier = 1.0 + (self._escalation_level * 0.5)
            min_d = delays["min"] * escalation_multiplier
            max_d = delays["max"] * escalation_multiplier

            mean_delay = (min_d + max_d) / 2
            std_dev = (max_d - min_d) / 4
            delay = max(min_d, random.gauss(mean_delay, std_dev))
            delay = min(delay, max_d * 1.5)

            elapsed = now - self._last_request_time
            if elapsed >= delay and action_type == "default":
                delay = random.uniform(0.05, 0.2)

            if random.random() < 0.03:
                delay += random.uniform(2.0, 5.0)

            self._last_request_time = time.time()
            self._request_count += 1

            # Debug: log delay
            _dbg().delay(
                delay_seconds=delay,
                action_type=action_type,
                escalation_level=self._escalation_level,
            )
            return delay

    # ─── UTILITY ────────────────────────────────────────────

    def _generate_device_id(self) -> str:
        """Generate random device ID."""
        return hashlib.md5(
            f"{time.time()}{random.random()}{uuid.uuid4()}".encode()
        ).hexdigest()[:16].upper()

    def _generate_mid(self) -> str:
        """Generate token similar to Instagram mid cookie."""
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        return "".join(random.choices(chars, k=28))

    def rotate_identity(self) -> None:
        """Force identity rotation (for external callers). Thread-safe."""
        with self._lock:
            self._current_identity = self._create_identity()
            self._identity_uses = 0
            self._identity_created_at = time.time()

    # ─── STATS ──────────────────────────────────────────────

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def escalation_level(self) -> int:
        return self._escalation_level

    @property
    def escalation_name(self) -> str:
        names = {0: "NORMAL", 1: "CAUTIOUS", 2: "STEALTH", 3: "PARANOID"}
        return names.get(self._escalation_level, "UNKNOWN")

    @property
    def current_identity_info(self) -> Dict:
        """Current identity info (for debugging)."""
        if not self._current_identity:
            return {}
        i = self._current_identity
        return {
            "browser": f"{i.browser_name} {i.browser_version}",
            "platform": i.platform,
            "impersonation": i.impersonation,
            "viewport": f"{i.viewport_width}x{i.viewport_height}",
            "uses": self._identity_uses,
            "max_uses": self._identity_max_uses,
            "age_sec": int(time.time() - self._identity_created_at),
            "escalation": self.escalation_name,
        }

    def get_rotation_context(self) -> Dict:
        """Full rotation state for SmartRotationCoordinator."""
        with self._lock:
            return {
                "identity": self.current_identity_info,
                "escalation_level": self._escalation_level,
                "escalation_name": self.escalation_name,
                "error_count": self._error_count,
                "consecutive_errors": self._consecutive_errors,
                "request_count": self._request_count,
                "profile_scores": dict(self._profile_scores),
                "blacklisted_profiles": list(self._profile_blacklist.keys()),
            }
