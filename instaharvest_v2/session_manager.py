"""
Session Manager
===============
Multi-account session management.
Load from .env file, cookie rotation, session health checking.
AUTO-SAVE: Session is automatically saved to file after every N requests.
"""

import os
import json
import time
import random
import logging
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Callable

from dotenv import load_dotenv

logger = logging.getLogger("instaharvest_v2")


@dataclass
class SessionInfo:
    """Single Instagram session data"""

    session_id: str
    csrf_token: str
    ds_user_id: str
    mid: str = ""
    ig_did: str = ""
    datr: str = ""
    user_agent: str = ""
    dpr: str = "1.5"              # device pixel ratio
    screen_resolution: str = "1707x932"  # viewport wd cookie

    # Additional headers (from browser DevTools)
    ig_www_claim: str = ""       # for x-ig-www-claim header
    rur: str = ""                # rur cookie
    x_instagram_ajax: str = ""   # build/deploy hash header

    # State
    is_active: bool = True
    is_valid: bool = True
    last_used: float = 0.0
    total_requests: int = 0
    errors: int = 0
    username: str = ""

    # Auto-save tracking
    _requests_since_save: int = field(default=0, repr=False)
    _cookie_updates: int = field(default=0, repr=False)

    @property
    def jazoest(self) -> str:
        """Instagram jazoest token (CSRF additional protection based on csrf_token)."""
        if not self.csrf_token:
            return "2"
        return "2" + str(sum(ord(c) for c in self.csrf_token))

    @property
    def cookies(self) -> Dict[str, str]:
        """Cookies as dict"""
        c = {
            "sessionid": self.session_id,
            "csrftoken": self.csrf_token,
            "ds_user_id": self.ds_user_id,
        }
        if self.mid:
            c["mid"] = self.mid
        if self.ig_did:
            c["ig_did"] = self.ig_did
        if self.datr:
            c["datr"] = self.datr
        if self.rur:
            c["rur"] = self.rur
        return c

    @property
    def cookie_string(self) -> str:
        """
        Cookies as string — BROWSER 1:1 ORDER.

        Instagram validates cookie ordering!
        Order captured from real browser via mitmproxy:
        ig_did → mid → ig_nrcb → datr → dpr → ds_user_id →
        ps_l → ps_n → csrftoken → sessionid → rur → wd
        """
        parts = []
        # 1. Device identification cookies (persistent, set on first visit)
        if self.ig_did:
            parts.append(f"ig_did={self.ig_did}")
        if self.mid:
            parts.append(f"mid={self.mid}")
        parts.append("ig_nrcb=1")
        if self.datr:
            parts.append(f"datr={self.datr}")
        parts.append(f"dpr={self.dpr}")
        parts.append(f"ds_user_id={self.ds_user_id}")
        parts.append("ps_l=1")
        parts.append("ps_n=1")
        # 2. Session cookies (mutable, updated per response)
        parts.append(f"csrftoken={self.csrf_token}")
        parts.append(f"sessionid={self.session_id}")
        if self.rur:
            parts.append(f'rur="{self.rur}"')
        parts.append(f"wd={self.screen_resolution}")
        return "; ".join(parts)

    def to_dict(self) -> Dict:
        """Convert session data to dict (for saving)."""
        return {
            "session_id": self.session_id,
            "csrf_token": self.csrf_token,
            "ds_user_id": self.ds_user_id,
            "mid": self.mid,
            "ig_did": self.ig_did,
            "datr": self.datr,
            "rur": self.rur,
            "user_agent": self.user_agent,
            "ig_www_claim": self.ig_www_claim,
            "x_instagram_ajax": self.x_instagram_ajax,
            "username": self.username,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_requests": self.total_requests,
            "cookie_updates": self._cookie_updates,
        }


class SessionManager:
    """
    Multi-account session management system.

    AUTO-SAVE: Session is automatically saved to file every `auto_save_interval`
    requests. This persists changing fields like `csrftoken`, `rur`, `x-ig-www-claim`.

    Usage:
        sm = SessionManager(auto_save_path="session.json")
        sm.add_session(session_id='...', csrf_token='...', ds_user_id='...')
        session = sm.get_session()
    """

    def __init__(
        self,
        auto_save_path: Optional[str] = None,
        auto_save_interval: int = 20,
    ):
        self._sessions: List[SessionInfo] = []
        self._index = 0
        self._lock = threading.Lock()
        self._reactivation_count = 0
        self._max_reactivations = 3

        # Auto-save
        self._auto_save_path = auto_save_path
        self._auto_save_interval = auto_save_interval
        self._save_lock = threading.Lock()

    def load_from_env(self, env_path: str = ".env") -> "SessionManager":
        """
        Load sessions from .env file.
        Can load single or multiple sessions.
        """
        env_file = Path(env_path)
        if env_file.exists():
            load_dotenv(env_file, override=True)

        # Base session
        session_id = os.getenv("SESSION_ID", "")
        csrf_token = os.getenv("CSRF_TOKEN", "")
        ds_user_id = os.getenv("DS_USER_ID", "")

        if session_id and csrf_token and ds_user_id:
            self.add_session(
                session_id=session_id,
                csrf_token=csrf_token,
                ds_user_id=ds_user_id,
                mid=os.getenv("MID", ""),
                ig_did=os.getenv("IG_DID", ""),
                datr=os.getenv("DATR", ""),
                user_agent=os.getenv("USER_AGENT", ""),
                ig_www_claim=os.getenv("IG_WWW_CLAIM", ""),
                rur=os.getenv("RUR", ""),
                x_instagram_ajax=os.getenv("X_INSTAGRAM_AJAX", ""),
            )

        # Additional sessions (SESSION_ID_2, SESSION_ID_3, ...)
        idx = 2
        while True:
            sid = os.getenv(f"SESSION_ID_{idx}", "")
            csrf = os.getenv(f"CSRF_TOKEN_{idx}", "")
            ds_uid = os.getenv(f"DS_USER_ID_{idx}", "")
            if not (sid and csrf and ds_uid):
                break
            self.add_session(
                session_id=sid,
                csrf_token=csrf,
                ds_user_id=ds_uid,
                mid=os.getenv(f"MID_{idx}", ""),
                ig_did=os.getenv(f"IG_DID_{idx}", ""),
                datr=os.getenv(f"DATR_{idx}", ""),
                user_agent=os.getenv(f"USER_AGENT_{idx}", ""),
                ig_www_claim=os.getenv(f"IG_WWW_CLAIM_{idx}", ""),
                rur=os.getenv(f"RUR_{idx}", ""),
                x_instagram_ajax=os.getenv(f"X_INSTAGRAM_AJAX_{idx}", ""),
            )
            idx += 1

        return self

    def add_session(
        self,
        session_id: str,
        csrf_token: str,
        ds_user_id: str,
        mid: str = "",
        ig_did: str = "",
        datr: str = "",
        user_agent: str = "",
        ig_www_claim: str = "",
        rur: str = "",
        x_instagram_ajax: str = "",
    ) -> None:
        """Add a new session (thread-safe)."""
        session = SessionInfo(
            session_id=session_id,
            csrf_token=csrf_token,
            ds_user_id=ds_user_id,
            mid=mid,
            ig_did=ig_did,
            datr=datr,
            user_agent=user_agent,
            ig_www_claim=ig_www_claim,
            rur=rur,
            x_instagram_ajax=x_instagram_ajax,
        )
        with self._lock:
            self._sessions.append(session)

    def get_session(self) -> Optional[SessionInfo]:
        """
        Get next active session (round-robin).
        Reactivates deactivated (but valid) sessions up to max_reactivations times.
        """
        with self._lock:
            active = [s for s in self._sessions if s.is_active and s.is_valid]
            if not active:
                # Only reactivate if under the limit
                if self._reactivation_count < self._max_reactivations:
                    active = [s for s in self._sessions if s.is_valid]
                    for s in active:
                        s.is_active = True
                        s.errors = 0  # Reset error count on reactivation
                    self._reactivation_count += 1
                if not active:
                    return None

            self._index = self._index % len(active)
            session = active[self._index]
            self._index += 1

            session.last_used = time.time()
            session.total_requests += 1
            return session

    # ─── COOKIE UPDATE (from response) ──────────────────────

    def update_from_response(self, session: SessionInfo, response) -> None:
        """
        Update cookies and headers from response.

        REACTIVE APPROACH:
        - csrftoken   → updated after every POST
        - rur         → updated on every response
        - sessionid   → rarely rotated
        - x-ig-set-www-claim → updated when server provides it

        Args:
            session: Session to update
            response: curl_cffi response object
        """
        updated = []

        # ─── From Set-Cookie headers ─────────────────────
        try:
            cookies = response.cookies
            if cookies:
                for name, attr in [
                    ("csrftoken", "csrf_token"),
                    ("sessionid", "session_id"),
                    ("mid", "mid"),
                    ("ds_user_id", "ds_user_id"),
                    ("ig_did", "ig_did"),
                    ("datr", "datr"),
                ]:
                    value = cookies.get(name)
                    if value and value != getattr(session, attr):
                        setattr(session, attr, value)
                        session._cookie_updates += 1
                        updated.append(f"{name}={value[:15]}..."
                                       if len(value) > 15 else f"{name}={value}")

                # rur — handle separately (always updated)
                rur_val = cookies.get("rur")
                if rur_val:
                    # rur value comes in "LDC\054..." format, get only prefix
                    rur_clean = rur_val.split("\\")[0] if "\\" in rur_val else rur_val
                    if rur_clean != session.rur:
                        session.rur = rur_clean
                        updated.append("rur")
        except Exception:
            pass  # Never fail on cookie capture

        # ─── From response headers ───────────────────
        try:
            # x-ig-www-claim — server HMAC claim update
            www_claim = response.headers.get("x-ig-set-www-claim", "")
            if www_claim and www_claim != session.ig_www_claim:
                session.ig_www_claim = www_claim
                session._cookie_updates += 1
                updated.append(f"ig_www_claim={www_claim[:20]}...")
        except Exception:
            pass

        if updated:
            logger.debug(f"[Session] Updated: {', '.join(updated)}")

        # ─── Auto-save trigger ───────────────────────────
        session._requests_since_save += 1
        if (
            self._auto_save_path
            and session._requests_since_save >= self._auto_save_interval
        ):
            self._auto_save(session)

    # ─── AUTO-SAVE ──────────────────────────────────────────

    def _auto_save(self, session: SessionInfo) -> None:
        """
        Automatically save session to file.
        Thread-safe, non-blocking.
        """
        if not self._auto_save_path:
            return

        with self._save_lock:
            try:
                data = session.to_dict()
                with open(self._auto_save_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                session._requests_since_save = 0
                logger.debug(
                    f"[Auto-Save] Session saved to {self._auto_save_path} "
                    f"(requests: {session.total_requests}, "
                    f"cookie_updates: {session._cookie_updates})"
                )
            except Exception as e:
                logger.warning(f"[Auto-Save] Failed: {e}")

    def save_session(self, filepath: Optional[str] = None) -> bool:
        """
        Manually save session.

        Args:
            filepath: Save path (default: auto_save_path)

        Returns:
            bool: Successfully saved
        """
        path = filepath or self._auto_save_path
        if not path:
            logger.warning("No save path specified")
            return False

        # Access session directly without incrementing counter
        with self._lock:
            active = [s for s in self._sessions if s.is_active and s.is_valid]
            if not active:
                # Fallback: save any session even if invalid
                active = list(self._sessions)
            if not active:
                logger.warning("No sessions to save")
                return False
            session = active[0]

        with self._save_lock:
            try:
                data = session.to_dict()
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                session._requests_since_save = 0
                logger.info(f"Session saved to {path}")
                return True
            except Exception as e:
                logger.error(f"Save failed: {e}")
                return False

    # ─── ONE TAP WEB LOGIN (Session Refresh) ──────────────────

    def refresh_via_one_tap(self, session: SessionInfo) -> bool:
        """
        Get new sessionid when session has been rotated.

        Instagram calls `one_tap_web_login` in the browser:
        - When user is redirected to login page
        - Creates new session with existing cookies
        - Does not require password — existing cookies are sufficient

        Flow:
        1. POST /api/v1/web/accounts/one_tap_web_login/
        2. Get new Set-Cookie from response
        3. Update SessionInfo + auto-save

        Returns:
            bool: True if new session was obtained
        """
        try:
            from curl_cffi import requests as curl_requests

            logger.info("[Session Refresh] Calling one_tap_web_login...")

            s = curl_requests.Session(impersonate="chrome142")

            # Full browser-like headers
            headers = {
                "cookie": session.cookie_string,
                "x-csrftoken": session.csrf_token,
                "x-ig-app-id": "1217981644879628",
                "x-ig-www-claim": session.ig_www_claim or "0",
                "x-requested-with": "XMLHttpRequest",
                "referer": "https://www.instagram.com/",
                "origin": "https://www.instagram.com",
                "content-type": "application/x-www-form-urlencoded",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
            }
            if session.x_instagram_ajax:
                headers["x-instagram-ajax"] = session.x_instagram_ajax
            if session.user_agent:
                headers["user-agent"] = session.user_agent

            # Payload — user_id and nonce
            payload = f"user_id={session.ds_user_id}&login_nonce=-&jazoest={session.jazoest}"

            resp = s.post(
                "https://www.instagram.com/api/v1/web/accounts/one_tap_web_login/",
                headers=headers,
                data=payload,
                allow_redirects=False,
            )

            # Get new tokens from Set-Cookie
            updated = []
            new_sid = resp.cookies.get("sessionid")
            new_csrf = resp.cookies.get("csrftoken")
            new_rur = resp.cookies.get("rur")
            new_mid = resp.cookies.get("mid")
            new_claim = resp.headers.get("x-ig-set-www-claim", "")

            # PROTECTION: if sessionid=delete — server is trying to logout!
            if new_sid and new_sid.lower() in ("delete", "deleted", '""', ""):
                logger.error(
                    "[Session Refresh] Server returned sessionid=delete! "
                    "This session is invalidated. Ignoring."
                )
                s.close()
                return False

            if new_sid and new_sid != session.session_id:
                session.session_id = new_sid
                updated.append("sessionid")
            if new_csrf and new_csrf != session.csrf_token:
                session.csrf_token = new_csrf
                updated.append("csrftoken")
            if new_rur:
                rur_clean = new_rur.split("\\")[0] if "\\" in new_rur else new_rur
                session.rur = rur_clean
                updated.append("rur")
            if new_mid and new_mid != session.mid:
                session.mid = new_mid
                updated.append("mid")
            if new_claim and new_claim != session.ig_www_claim:
                session.ig_www_claim = new_claim
                updated.append("ig_www_claim")

            s.close()

            # Check response status
            status = "?"
            try:
                rj = resp.json()
                status = rj.get("status", rj.get("message", "?"))
            except Exception:
                pass

            if updated:
                logger.info(
                    f"[Session Refresh] OK! status={resp.status_code} "
                    f"api_status={status} | updated: {', '.join(updated)}"
                )
                session._cookie_updates += len(updated)
                # Auto-save immediately
                self._auto_save(session)
                return True
            else:
                logger.warning(
                    f"[Session Refresh] No new cookies received. "
                    f"status={resp.status_code} api_status={status}"
                )
                return False

        except Exception as e:
            logger.error(f"[Session Refresh] Failed: {e}")
            return False

    def reload_from_file(self, session: SessionInfo) -> bool:
        """
        Reload session from file (fallback).

        If one_tap_web_login fails — read updated
        cookies from session.json.

        Returns:
            bool: True if new data was obtained
        """
        if not self._auto_save_path:
            return False

        try:
            with open(self._auto_save_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            updated = []
            new_sid = data.get("session_id", "")
            new_csrf = data.get("csrf_token", "")

            if new_sid and new_sid != session.session_id:
                session.session_id = new_sid
                updated.append("sessionid")
            if new_csrf and new_csrf != session.csrf_token:
                session.csrf_token = new_csrf
                updated.append("csrftoken")

            # Other fields
            for key in ("mid", "ig_did", "datr", "rur", "ig_www_claim", "x_instagram_ajax"):
                file_val = data.get(key, "")
                if file_val and file_val != getattr(session, key, ""):
                    setattr(session, key, file_val)
                    updated.append(key)

            if updated:
                logger.info(f"[Session Reload] Updated from file: {', '.join(updated)}")
                return True

            return False

        except Exception as e:
            logger.warning(f"[Session Reload] Failed: {e}")
            return False

    # ─── ERROR / SUCCESS TRACKING ───────────────────────────

    def report_error(self, session: SessionInfo, is_login_error: bool = False) -> None:
        """Record session error."""
        with self._lock:
            session.errors += 1
            if is_login_error:
                session.is_valid = False
            elif session.errors >= 10:
                session.is_active = False

    def report_success(self, session: SessionInfo) -> None:
        """Record successful request."""
        session.errors = max(0, session.errors - 1)

    def invalidate(self, session: SessionInfo) -> None:
        """Completely invalidate a session."""
        session.is_valid = False
        session.is_active = False

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def active_count(self) -> int:
        return sum(1 for s in self._sessions if s.is_active and s.is_valid)

    def get_all_sessions(self) -> List[SessionInfo]:
        return list(self._sessions)
