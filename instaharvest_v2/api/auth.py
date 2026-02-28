"""
Auth API
========
Instagram login, logout, 2FA, and challenge resolver.
Web login flow using wbloks/fetch endpoint — 1:1 real browser emulation.

Login flow (captured from real Samsung Browser via mitmproxy):
    1. Load device cookies (if saved) → Instagram recognizes device
    2. Warm-up: GET instagram.com → GET /accounts/login/ (human-like)
       Extract: csrftoken, lsd, __rev, __hsi, __dyn, __csr, __bkv
    3. Encrypt password → #PWD_BROWSER:5:{timestamp}:{encrypted}
    4. Step 1: POST wbloks/fetch (send_login_request) → get auth params
    5. Step 2: POST wbloks/fetch (auth_login_request) → get sessionid
    6. Handle 2FA/challenge automatically if required
    7. Save device cookies + session for next time

Dependency: pip install pynacl cryptography
"""

import json
import os
import time
import random
import logging
import re
import hashlib
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("instaharvest_v2")

# Login endpoints — wbloks/fetch (real browser uses this, NOT web_login_ajax)
WBLOKS_BASE = "https://www.instagram.com/async/wbloks/fetch/"
LOGIN_APPID = "com.bloks.www.bloks.caa.login.async.send_login_request"
AUTH_LOGIN_APPID = "com.bloks.www.bloks.caa.login.async.auth_login_request"

# Legacy endpoints (for 2FA and logout)
LOGIN_URL = "https://www.instagram.com/api/v1/web/accounts/login/ajax/"
TWO_FACTOR_URL = "https://www.instagram.com/api/v1/web/accounts/login/ajax/two_factor/"
LOGOUT_URL = "https://www.instagram.com/api/v1/web/accounts/logout/ajax/"
SHARED_DATA_URL = "https://www.instagram.com/data/shared_data/"

# Device cookies to persist (these make us a "known device")
DEVICE_COOKIES = ["mid", "ig_did", "ig_nrcb", "datr", "csrftoken"]

# Browser User-Agent (must match curl_cffi impersonation version)
WEB_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/142.0.0.0 Safari/537.36"
)

# Chrome version constant for sec-ch-ua headers
CHROME_VERSION = "142"
SEC_CH_UA = f'"Not A Brand";v="99", "Google Chrome";v="{CHROME_VERSION}", "Chromium";v="{CHROME_VERSION}"'


class AuthAPI:
    """
    Instagram login/logout API.

    Usage:
        from instaharvest_v2 import Instagram
        ig = Instagram()
        ig.auth.login("username", "password")
        # Now ig.users, ig.media, ... are ready

        # Save session:
        ig.auth.save_session("session.json")

        # Load session next time:
        ig.auth.load_session("session.json")
    """

    def __init__(self, client):
        self._client = client
        self._encryption_keys = None
        self._device_cookies_file = "device_cookies.json"
        self._server_revision = ""  # Dynamic x-instagram-ajax (__rev)
        # Wbloks dynamic params (extracted from login page HTML)
        self._wbloks_params = {
            "lsd": "",
            "__rev": "",
            "__hsi": "",
            "__dyn": "",
            "__csr": "",
            "__bkv": "",
            "__spin_b": "trunk",
            "__spin_t": "",
            "__hs": "",
        }

    @property
    def user_id(self) -> Optional[str]:
        """Get current logged-in user ID from session."""
        sess = self._client.get_session()
        if sess and hasattr(sess, 'ds_user_id') and sess.ds_user_id:
            return str(sess.ds_user_id)
        return None

    # Alias for backward compatibility
    _user_id = user_id

    # ═══════════════════════════════════════════════════════════
    # LAYER 1: BROWSER WARM-UP (anti-challenge)
    # ═══════════════════════════════════════════════════════════

    def _warm_up_session(self, session) -> str:
        """
        Warm up the session like a real browser before login.
        Extracts wbloks dynamic params needed for the login request.

        Flow:
            1. Load saved device cookies (if exist)
            2. GET instagram.com (collect mid, ig_did, datr)
            3. Wait 2-3s (human-like)
            4. GET /accounts/login/ (collect csrftoken + wbloks params)
            5. Wait 1-2s

        Extracts from HTML:
            - csrftoken (cookie)
            - lsd, __rev, __hsi, __dyn, __csr, __bkv, __hs, __spin_t

        Returns:
            str: CSRF token
        """
        # Load previously saved device cookies (Layer 2)
        self._load_device_cookies(session)

        # Step 1: Visit instagram.com main page
        logger.info("[Auth] Warming up session — visiting instagram.com...")
        try:
            session.get(
                "https://www.instagram.com/",
                headers={
                    "user-agent": WEB_USER_AGENT,
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "accept-language": "en-US,en;q=0.9",
                    "sec-ch-ua": SEC_CH_UA,
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "document",
                    "sec-fetch-mode": "navigate",
                    "sec-fetch-site": "none",
                    "sec-fetch-user": "?1",
                    "upgrade-insecure-requests": "1",
                },
                timeout=15,
            )
            logger.debug(f"[Auth] Main page cookies: {list(session.cookies.keys())}")
        except Exception as e:
            logger.warning(f"[Auth] Main page visit failed: {e}")

        # Human-like delay: 2-3 seconds
        delay1 = random.uniform(2.0, 3.5)
        logger.debug(f"[Auth] Waiting {delay1:.1f}s before login page...")
        time.sleep(delay1)

        # Step 2: Visit login page (this sets csrftoken + contains wbloks params)
        logger.info("[Auth] Visiting login page...")
        csrf_token = None
        try:
            login_page = session.get(
                "https://www.instagram.com/accounts/login/",
                headers={
                    "user-agent": WEB_USER_AGENT,
                    "referer": "https://www.instagram.com/",
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "sec-ch-ua": SEC_CH_UA,
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "document",
                    "sec-fetch-mode": "navigate",
                    "sec-fetch-site": "same-origin",
                },
                timeout=15,
            )

            page_html = login_page.text

            # Extract CSRF token
            for name, value in session.cookies.items():
                if name == "csrftoken":
                    csrf_token = value
                    break

            if not csrf_token:
                csrf_token = login_page.headers.get("x-csrftoken", "")
            if not csrf_token:
                match = re.search(r'"csrf_token":"([^"]+)"', page_html)
                if match:
                    csrf_token = match.group(1)

            # ── Extract wbloks dynamic params from login page HTML ──
            # These are embedded in script tags as JS variables or JSON config

            # __rev (server_revision) — also used as x-instagram-ajax
            rev_match = re.search(r'"server_revision":(\d+)', page_html)
            if rev_match:
                self._server_revision = rev_match.group(1)
                self._wbloks_params["__rev"] = rev_match.group(1)
            else:
                spin_match = re.search(r'__spin_r":(\d+)', page_html)
                if spin_match:
                    self._server_revision = spin_match.group(1)
                    self._wbloks_params["__rev"] = spin_match.group(1)

            # lsd token (anti-CSRF for wbloks)
            lsd_match = re.search(r'"LSD",\[\],\{"token":"([^"]+)"', page_html)
            if not lsd_match:
                lsd_match = re.search(r'"lsd"[,:]"([^"]+)"', page_html, re.IGNORECASE)
            if not lsd_match:
                lsd_match = re.search(r'name="lsd"\s+value="([^"]+)"', page_html)
            if lsd_match:
                self._wbloks_params["lsd"] = lsd_match.group(1)
                logger.debug(f"[Auth] lsd: {lsd_match.group(1)[:20]}...")

            # __hsi (host session ID)
            hsi_match = re.search(r'"hsi":"(\d+)"', page_html)
            if not hsi_match:
                hsi_match = re.search(r'__hsi":(\d+)', page_html)
            if hsi_match:
                self._wbloks_params["__hsi"] = hsi_match.group(1)

            # __dyn (dynamic modules hash)
            dyn_match = re.search(r'"__dyn":"([^"]+)"', page_html)
            if dyn_match:
                self._wbloks_params["__dyn"] = dyn_match.group(1)

            # __csr (client-side rendering hash)
            csr_match = re.search(r'"__csr":"([^"]+)"', page_html)
            if csr_match:
                self._wbloks_params["__csr"] = csr_match.group(1)

            # __bkv (bloks versioning ID — critical for wbloks/fetch URL!)
            # In HTML it appears as: versioningID","[],{"versioningID":"29d0fd2d..."
            bkv_match = re.search(r'versioningID":"([a-f0-9]{64})', page_html)
            if not bkv_match:
                bkv_match = re.search(r'"bloks_versioning_id":"([^"]+)"', page_html)
            if not bkv_match:
                bkv_match = re.search(r'__bkv["\s:]+([a-f0-9]{40,})', page_html)
            if bkv_match:
                self._wbloks_params["__bkv"] = bkv_match.group(1)
                logger.info(f"[Auth] __bkv: {bkv_match.group(1)[:30]}...")
            else:
                # Hardcoded fallback from captured traffic (Feb 2026)
                self._wbloks_params["__bkv"] = "29d0fd2d0bf67787771d758433b17814a729d9b4a57b07a39f1cc6507b480e39"
                logger.warning("[Auth] __bkv not found in HTML, using hardcoded fallback")

            # __hs (host segment)
            hs_match = re.search(r'"__hs":"([^"]+)"', page_html)
            if hs_match:
                self._wbloks_params["__hs"] = hs_match.group(1)

            # __spin_t (spin timestamp)
            spin_t_match = re.search(r'__spin_t":(\d+)', page_html)
            if spin_t_match:
                self._wbloks_params["__spin_t"] = spin_t_match.group(1)

            logger.info(f"[Auth] server_revision (__rev): {self._server_revision}")
            logger.info(f"[Auth] Wbloks params extracted: {[k for k,v in self._wbloks_params.items() if v]}")

        except Exception as e:
            logger.warning(f"[Auth] Login page visit failed: {e}")

        if not csrf_token:
            csrf_token = "missing"
            logger.warning("[Auth] CSRF token not found")

        # Save device cookies after warm-up (for next time)
        self._save_device_cookies(session)

        # Human-like delay before login POST
        delay2 = random.uniform(1.5, 2.5)
        logger.debug(f"[Auth] Waiting {delay2:.1f}s before login POST...")
        time.sleep(delay2)

        logger.info(f"[Auth] Warm-up complete. Cookies: {list(session.cookies.keys())}")
        return csrf_token

    # ═══════════════════════════════════════════════════════════
    # LAYER 2: DEVICE COOKIE PERSISTENCE
    # ═══════════════════════════════════════════════════════════

    def _save_device_cookies(self, session) -> None:
        """Save device-identifying cookies for future sessions."""
        cookies = {}
        for name, value in session.cookies.items():
            if name in DEVICE_COOKIES:
                cookies[name] = value

        if cookies:
            data = {
                "cookies": cookies,
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "user_agent": WEB_USER_AGENT,
            }
            try:
                with open(self._device_cookies_file, "w") as f:
                    json.dump(data, f, indent=2)
                logger.info(f"[Auth] Device cookies saved: {list(cookies.keys())}")
            except Exception as e:
                logger.warning(f"[Auth] Failed to save device cookies: {e}")

    def _load_device_cookies(self, session) -> bool:
        """Load saved device cookies into session."""
        if not os.path.exists(self._device_cookies_file):
            logger.debug("[Auth] No saved device cookies found")
            return False

        try:
            with open(self._device_cookies_file) as f:
                data = json.load(f)

            cookies = data.get("cookies", {})
            for name, value in cookies.items():
                session.cookies.set(name, value, domain=".instagram.com")

            logger.info(f"[Auth] Device cookies loaded: {list(cookies.keys())}")
            return True
        except Exception as e:
            logger.warning(f"[Auth] Failed to load device cookies: {e}")
            return False

    def _get_encryption_keys(self) -> Dict[str, str]:
        """
        Fetch encryption keys from Instagram.
        
        Priority order (to match real browser behavior):
        1. Cached keys (from _warm_up_session)
        2. Login page HTML inline keys (what real browsers use)
        3. Response headers (ig-set-password-encryption-*)
        4. shared_data API (fallback — may return different key_id!)
        
        Returns: {key_id, public_key, version}
        """
        if self._encryption_keys:
            return self._encryption_keys

        session = self._client._get_curl_session()

        # Method 1: Parse keys from login page HTML (matches real browser)
        try:
            resp = session.get(
                "https://www.instagram.com/accounts/login/",
                headers={"user-agent": WEB_USER_AGENT},
                timeout=15,
            )
            html = resp.text
            
            # Try inline JSON: {"key_id":"243","public_key":"9c24..."}
            key_id_match = re.search(r'"key_id"\s*:\s*"?(\d+)"?', html)
            pub_key_match = re.search(r'"public_key"\s*:\s*"([a-f0-9]{64})"', html)
            
            if key_id_match and pub_key_match:
                self._encryption_keys = {
                    "key_id": key_id_match.group(1),
                    "public_key": pub_key_match.group(1),
                    "version": "10",
                }
                logger.info(
                    f"[Auth] Encryption keys from HTML: key_id={key_id_match.group(1)}, "
                    f"pub_key={pub_key_match.group(1)[:20]}..."
                )
                return self._encryption_keys
            
            # Try _sharedData embedded in HTML
            match = re.search(r'window\._sharedData\s*=\s*({.+?});', html)
            if match:
                shared_data = json.loads(match.group(1))
                encryption = shared_data.get("encryption", {})
                if encryption.get("public_key"):
                    self._encryption_keys = encryption
                    return encryption
            
            # Try response headers
            key_id = resp.headers.get("ig-set-password-encryption-key-id")
            pub_key = resp.headers.get("ig-set-password-encryption-pub-key")
            version = resp.headers.get("ig-set-password-encryption-web-key-version")
            if key_id and pub_key:
                self._encryption_keys = {
                    "key_id": key_id,
                    "public_key": pub_key,
                    "version": version or "10",
                }
                return self._encryption_keys

        except Exception as e:
            logger.debug(f"HTML key extraction error: {e}")

        # Method 2: shared_data API (fallback)
        try:
            resp = session.get(
                SHARED_DATA_URL,
                headers={
                    "user-agent": WEB_USER_AGENT,
                    "referer": "https://www.instagram.com/accounts/login/",
                },
                timeout=15,
            )
            data = resp.json()
            encryption = data.get("encryption", {})
            if encryption.get("public_key"):
                self._encryption_keys = encryption
                logger.info(f"[Auth] Encryption keys from API: key_id={encryption.get('key_id')}")
                return encryption
        except Exception as e:
            logger.debug(f"shared_data error: {e}")

        raise Exception("Instagram encryption keys not found!")

    def _encrypt_password(self, password: str) -> str:
        """
        Encrypt password for Instagram login.
        Uses AES-GCM-256 + NaCl crypto_box_seal hybrid encryption.

        Flow:
            1. Generate random 32-byte AES key (IV = 12 zero bytes)
            2. Encrypt password with AES-GCM-256 (AAD = timestamp)
            3. Encrypt AES key with NaCl SealedBox (Instagram's public key)
            4. Combine into Instagram's binary format

        Returns:
            str: "#PWD_BROWSER:10:{timestamp}:{encrypted_b64}"
        """
        try:
            from nacl.public import PublicKey, SealedBox
        except ImportError:
            raise ImportError(
                "pynacl is required! Install it: pip install pynacl"
            )

        import base64
        import struct
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        keys = self._get_encryption_keys()
        key_id = int(keys["key_id"])
        pub_key_hex = keys["public_key"]
        version = keys.get("version", "10")

        timestamp = str(int(time.time()))

        # Convert Instagram's hex public key to NaCl PublicKey
        pub_key_bytes = bytes.fromhex(pub_key_hex)
        nacl_key = PublicKey(pub_key_bytes)
        sealed_box = SealedBox(nacl_key)

        # Step 1: Generate random AES-256 key (32 bytes)
        # IV is fixed to 12 zero bytes (Instagram's #PWD_BROWSER:10 specification)
        aes_key = os.urandom(32)
        iv = bytes(12)  # 12 zero bytes (matches Instagram's EnvelopeEncryption JS)

        # Step 2: Encrypt password with AES-GCM-256
        # AAD (Additional Authenticated Data) = timestamp string
        aes_gcm = AESGCM(aes_key)
        password_bytes = password.encode("utf-8")
        aad = timestamp.encode("utf-8")
        encrypted = aes_gcm.encrypt(iv, password_bytes, aad)

        # AES-GCM output: ciphertext + 16-byte auth tag (Python AESGCM order)
        # Instagram expects: tag FIRST, then ciphertext
        aes_tag = encrypted[-16:]
        aes_ciphertext = encrypted[:-16]

        # Step 3: Encrypt only AES key with NaCl SealedBox
        # (sealed_key = 32 bytes plaintext + 48 bytes NaCl overhead = 80 bytes)
        sealed_key = sealed_box.encrypt(aes_key)

        # Step 4: Build Instagram binary format (verified from JS EnvelopeEncryption source)
        # Format: [1:version][1:key_id][2:sealed_key_size_LE][sealed_key][16:tag][ciphertext]
        # NOTE: tag comes BEFORE ciphertext (opposite of Python AESGCM output order)
        payload = b""
        payload += b"\x01"  # version byte (always 1 in binary)
        payload += struct.pack("<B", key_id)  # key_id (1 byte)
        payload += struct.pack("<H", len(sealed_key))  # sealed key size (2 bytes, little-endian)
        payload += sealed_key  # NaCl sealed AES key (80 bytes)
        payload += aes_tag  # 16-byte GCM auth tag (BEFORE ciphertext!)
        payload += aes_ciphertext  # AES-GCM ciphertext (encrypted password)

        enc_b64 = base64.b64encode(payload).decode("utf-8")

        # Instagram uses version from shared_data (currently 10)
        # CAAWebPasswordEncryption reads version from cr:4552.getVersion()
        enc_version = int(version) if version else 10
        return f"#PWD_BROWSER:{enc_version}:{timestamp}:{enc_b64}"

    def _build_wbloks_form(self, params_json: str, csrf_token: str) -> Dict[str, str]:
        """
        Build the complete form data for wbloks/fetch POST request.
        These params are sent with EVERY wbloks request (captured from real browser).

        Args:
            params_json: The 'params' value — already JSON-encoded inner params string
            csrf_token: Current CSRF token

        Returns:
            dict: Complete form data matching real browser 1:1
        """
        # Calculate jazoest from csrf_token (same algorithm as SessionInfo.jazoest)
        jazoest_val = "2" + str(sum(ord(c) for c in csrf_token))

        # Fallback values from captured real browser traffic
        # Instagram returns 500 if __dyn or __csr are empty!
        dyn_fallback = (
            "7xeUjG1mxu1syUbFp41twpUnwgU29zEdEc8co2qwJw5ux609vCwjE1EE2Cw8G1Qw5Mx62G3i1ywOwv89k2C1Fwc60"
            "D82Ixe0EUjwGzEaE2iwNwmE2eUlwhEe87q0oa2-azo7u3u2C2O0Lo6-3u2WE5B0bK1Iwqo5p0qZ6goK1sAwHxW1o"
            "wLwlE2xyUC4o1oE3Dw"
        )
        csr_fallback = (
            "hAIIl4OguiinblmxcBjvp2lFIiDlBAqAyf-AjDye4qnXyRVVG_-iifz4dxi-nwBgCHyogBK48aohxe6e6UliQh6xu"
            "dDyVXx6Q2nAy99bwFxq5ooGqcg888UkyFUWUWim5UydG78qyUV2HzEWUG58jy8x0jVU1jk0To01wU8eHBw1zi261"
            "qXw19Ra580ZYE0QO1hG0l20"
        )

        form = {
            "__d": "www",
            "__user": "0",
            "__a": "1",
            "__req": "e",
            "__hs": self._wbloks_params.get("__hs", "20511.HYP:instagram_web_pkg.2.1...0"),
            "dpr": "3",
            "__ccg": "GOOD",
            "__rev": self._wbloks_params.get("__rev", self._server_revision or "1034162388"),
            "__s": "",
            "__hsi": self._wbloks_params.get("__hsi", str(int(time.time() * 1000000))),
            "__dyn": self._wbloks_params.get("__dyn", "") or dyn_fallback,
            "__csr": self._wbloks_params.get("__csr", "") or csr_fallback,
            "__comet_req": "7",
            "lsd": self._wbloks_params.get("lsd", ""),
            "jazoest": jazoest_val,
            "__spin_r": self._wbloks_params.get("__rev", self._server_revision or "1034162388"),
            "__spin_b": self._wbloks_params.get("__spin_b", "trunk"),
            "__spin_t": self._wbloks_params.get("__spin_t", str(int(time.time()))),
            "__crn": "comet.igweb.PolarisWebBloksLoginRoute",
            "params": params_json,
        }

        return form

    def _build_wbloks_url(self, appid: str) -> str:
        """Build the wbloks/fetch URL with appid and __bkv params."""
        bkv = self._wbloks_params.get("__bkv", "")
        url = f"{WBLOKS_BASE}?appid={appid}&type=action"
        if bkv:
            url += f"&__bkv={bkv}"
        return url

    def login(
        self,
        username: str,
        password: str,
        verification_code: str = None,
        two_factor_callback: Optional[Callable[[], str]] = None,
        challenge_callback: Optional[Callable] = None,
        email_credentials: Optional[Tuple[str, str]] = None,
        device_cookies_file: str = "device_cookies.json",
    ) -> Dict[str, Any]:
        """
        Login to Instagram with username and password.

        Includes anti-challenge protection:
        - Browser warm-up (visits main page first)
        - Device cookie persistence (remembers device)
        - Automatic challenge resolution
        - Auto email code reading via IMAP

        Args:
            username: Instagram username
            password: Account password
            verification_code: 2FA code (if known in advance)
            two_factor_callback: Callback for 2FA code.
                Example: lambda: input("Enter 2FA code: ")
            challenge_callback: Callback for challenge verification code.
                Example: lambda ctx: input(f"Code sent to {ctx.contact_point}: ")
            email_credentials: Tuple of (email, app_password) for auto-reading
                Instagram verification codes from Gmail via IMAP.
                Example: ("user@gmail.com", "xxxx xxxx xxxx xxxx")
            device_cookies_file: Path to save device cookies (default: device_cookies.json)

        Returns:
            dict: {
                status: "ok",
                authenticated: True,
                user_id: "...",
                session_id: "...",
            }

        Raises:
            LoginError: Login failed
            TwoFactorRequired: 2FA code needed (no callback provided)
            CheckpointRequired: Challenge could not be auto-resolved
        """
        # Save email_credentials for re-login after challenge resolution
        self._email_credentials = email_credentials

        # Auto-create challenge_callback from email_credentials
        if email_credentials and not challenge_callback:
            from ..email_verifier import EmailVerifier
            email_addr, email_pass = email_credentials
            verifier = EmailVerifier(email_addr, email_pass)

            def _auto_email_callback(ctx=None):
                logger.info("[Auth] Auto-reading verification code from email...")
                code = verifier.get_instagram_code(max_wait=90, poll_interval=5)
                if code:
                    logger.info(f"[Auth] Got verification code from email: {code}")
                    return code
                raise LoginError("Verification code not found in email within 90 seconds")

            challenge_callback = _auto_email_callback

        self._device_cookies_file = device_cookies_file
        session = self._client._get_curl_session()

        # ─── Layer 1: Warm-up (prevents "unusual login" challenges) ───
        logger.info(f"[Auth] Starting login for @{username}")
        csrf_token = self._warm_up_session(session)

        # ─── Encrypt password ───
        # Instagram uses #PWD_BROWSER:10 (encrypted) — version 10 with NaCl SealedBox + AES-GCM
        try:
            enc_password = self._encrypt_password(password)
            logger.info("[Auth] Password encrypted with #PWD_BROWSER:10")
        except Exception as e:
            logger.warning(f"[Auth] Encryption failed, using plaintext: {e}")
            enc_password = f"#PWD_BROWSER:0:{int(time.time())}:{password}"

        # Dynamic x-instagram-ajax (extracted from login page)
        x_instagram_ajax = self._server_revision or "1034162388"

        # ─── Build wbloks login params (1:1 real browser) ───
        # Get device IDs from cookies
        mid_value = ""
        for name, value in session.cookies.items():
            if name == "mid":
                mid_value = value
                break

        import uuid
        waterfall_id = str(uuid.uuid4())

        # Build the params JSON (matches real browser traffic exactly)
        login_params = {
            "server_params": {
                "credential_type": "password",
                "username_text_input_id": f"login:{random.randint(10,99)}",
                "password_text_input_id": f"login:{random.randint(100,199)}",
                "login_source": "Login",
                "login_credential_type": "none",
                "server_login_source": "login",
                "ar_event_source": "login_home_page",
                "should_trigger_override_login_success_action": 0,
                "should_trigger_override_login_2fa_action": 0,
                "is_caa_perf_enabled": 1,
                "reg_flow_source": "aymh_single_profile_native_integration_point",
                "caller": "gslr",
                "is_from_landing_page": 0,
                "is_from_empty_password": 0,
                "is_from_aymh": 0,
                "is_from_password_entry_page": 0,
                "is_from_assistive_id": 0,
                "is_from_msplit_fallback": 0,
                "two_step_login_type": "one_step_login",
                "is_vanilla_password_page_empty_password": 0,
                "left_nav_button_action": "BACK",
                "INTERNAL__latency_qpl_marker_id": 36707139,
                "INTERNAL__latency_qpl_instance_id": str(random.randint(10**13, 10**14)),
                "device_id": mid_value,
                "family_device_id": None,
                "waterfall_id": waterfall_id,
                "offline_experiment_group": None,
                "layered_homepage_experiment_group": None,
                "is_platform_login": 0,
                "is_from_logged_in_switcher": 0,
                "is_from_logged_out": 0,
                "access_flow_version": "pre_mt_behavior",
                "login_surface": "login_home",
            },
            "client_input_params": {
                "machine_id": "",
                "cloud_trust_token": None,
                "block_store_machine_id": "",
                "zero_balance_state": "",
                "contact_point": username,
                "password": enc_password,
                "accounts_list": [],
                "fb_ig_device_id": [],
                "secure_family_device_id": "",
                "encrypted_msisdn": "",
                "headers_infra_flow_id": "",
                "try_num": 1,
                "login_attempt_count": 1,
                "event_flow": "login_manual",
                "event_step": "home_page",
                "openid_tokens": {},
                "auth_secure_device_id": "",
                "client_known_key_hash": "",
                "has_whatsapp_installed": 0,
                "sso_token_map_json_string": "",
                "should_show_nested_nta_from_aymh": 0,
            },
        }

        params_json = json.dumps({"params": json.dumps(login_params)})
        wbloks_form = self._build_wbloks_form(params_json, csrf_token)
        wbloks_url = self._build_wbloks_url(LOGIN_APPID)

        # ─── POST login (wbloks/fetch) ───
        login_headers = {
            "user-agent": WEB_USER_AGENT,
            "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
            "origin": "https://www.instagram.com",
            "referer": "https://www.instagram.com/accounts/login/",
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "sec-ch-ua": SEC_CH_UA,
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        }

        logger.info(f"[Auth] Sending wbloks login request to {wbloks_url[:80]}...")

        resp = session.post(
            wbloks_url,
            headers=login_headers,
            data=wbloks_form,
            timeout=30,
            allow_redirects=False,
        )

        resp_text = resp.text
        logger.debug(f"[Auth] Wbloks response ({resp.status_code}): {resp_text[:500]}")

        # Parse wbloks response (format: for (;;);{...json...})
        result = {}
        try:
            # Strip the "for (;;);" prefix if present
            json_text = resp_text
            if json_text.startswith("for (;;);"):
                json_text = json_text[len("for (;;);"):]
            result = json.loads(json_text)
        except Exception:
            # Try to detect success from Set-Cookie headers
            pass

        # Check if login succeeded via Set-Cookie (ds_user_id cookie = success)
        ds_user_id_cookie = None
        session_id_cookie = None
        new_csrf = None
        for name, value in session.cookies.items():
            if name == "ds_user_id" and value:
                ds_user_id_cookie = value
            elif name == "sessionid" and value:
                session_id_cookie = value
            elif name == "csrftoken" and value:
                new_csrf = value

        # ─── Handle: SUCCESS via cookies (wbloks returns complex payload) ───
        if ds_user_id_cookie and session_id_cookie:
            logger.info(f"[Auth] ✅ Login success! ds_user_id={ds_user_id_cookie}")
            login_result = {
                "status": "ok",
                "authenticated": True,
                "user_id": ds_user_id_cookie,
                "session_id": session_id_cookie,
                "username": username,
            }
            self._handle_login_success(session, login_result, username)
            self._save_device_cookies(session)
            return login_result

        # ─── Handle: Wbloks auth_login_request (2-step flow) ───
        # If send_login_request succeeded but didn't set cookies,
        # the response may contain auth params for step 2
        auth_encrypted_params = ""
        nonce = ""
        user_id_from_resp = ""

        payload = result.get("payload", {})
        payload_str = json.dumps(payload) if payload else resp_text

        # Extract auth params from the complex wbloks response
        if "auth_login_request_encrypted_params" in payload_str:
            enc_match = re.search(r'auth_login_request_encrypted_params["\\:]+\s*["\\]+(Ac[A-Za-z0-9_-]+)', payload_str)
            if enc_match:
                auth_encrypted_params = enc_match.group(1)

        if "nonce" in payload_str:
            nonce_match = re.search(r'"nonce"["\\:]+\s*["\\]+([A-Za-z0-9+/=]+)', payload_str)
            if nonce_match:
                nonce = nonce_match.group(1)

        if "user_id" in payload_str:
            uid_match = re.search(r'"user_id"["\\:]+\s*["\\]+(\d+)', payload_str)
            if uid_match:
                user_id_from_resp = uid_match.group(1)

        # Step 2: auth_login_request (if we got auth params)
        if auth_encrypted_params and nonce:
            logger.info("[Auth] Step 2: Sending auth_login_request...")

            auth_params = {
                "server_params": {
                    "credentials": [],
                    "login_source": "AccountsYouMayHave",
                    "auth_login_request_encrypted_params": auth_encrypted_params,
                    "INTERNAL__latency_qpl_marker_id": 36707139,
                    "INTERNAL__latency_qpl_instance_id": str(random.randint(10**13, 10**14)),
                    "device_id": mid_value,
                    "family_device_id": None,
                    "waterfall_id": str(uuid.uuid4()),
                    "offline_experiment_group": None,
                    "layered_homepage_experiment_group": None,
                    "is_platform_login": 0,
                    "is_from_logged_in_switcher": 0,
                    "is_from_logged_out": 0,
                    "access_flow_version": "pre_mt_behavior",
                    "login_surface": "unknown",
                },
                "client_input_params": {
                    "cloud_trust_token": None,
                    "block_store_machine_id": "",
                    "user_id": user_id_from_resp,
                    "nonce": nonce,
                    "network_bssid": None,
                    "lois_settings": {"lois_token": ""},
                    "aac": "",
                },
            }

            auth_params_json = json.dumps({"params": json.dumps(auth_params)})
            auth_form = self._build_wbloks_form(auth_params_json, new_csrf or csrf_token)
            auth_url = self._build_wbloks_url(AUTH_LOGIN_APPID)

            resp2 = session.post(
                auth_url,
                headers=login_headers,
                data=auth_form,
                timeout=30,
                allow_redirects=False,
            )

            logger.debug(f"[Auth] Auth login response ({resp2.status_code}): {resp2.text[:500]}")

            # Check cookies after step 2
            for name, value in session.cookies.items():
                if name == "ds_user_id" and value:
                    ds_user_id_cookie = value
                elif name == "sessionid" and value:
                    session_id_cookie = value

            if ds_user_id_cookie and session_id_cookie:
                logger.info(f"[Auth] ✅ Login success (step 2)! ds_user_id={ds_user_id_cookie}")
                login_result = {
                    "status": "ok",
                    "authenticated": True,
                    "user_id": ds_user_id_cookie,
                    "session_id": session_id_cookie,
                    "username": username,
                }
                self._handle_login_success(session, login_result, username)
                self._save_device_cookies(session)
                return login_result

        # ─── Fallback: Try legacy web_login_ajax endpoint ───
        logger.warning("[Auth] Wbloks login did not yield session — falling back to legacy endpoint")
        login_data = {
            "username": username,
            "enc_password": enc_password,
            "queryParams": "{}",
            "optIntoOneTap": "false",
            "trustedDeviceRecords": "{}",
        }
        login_headers["x-csrftoken"] = new_csrf or csrf_token
        login_headers["x-requested-with"] = "XMLHttpRequest"
        login_headers["x-ig-app-id"] = "1217981644879628"
        login_headers["x-instagram-ajax"] = x_instagram_ajax

        resp = session.post(
            LOGIN_URL,
            headers=login_headers,
            data=login_data,
            timeout=30,
            allow_redirects=False,
        )

        try:
            result = resp.json()
        except Exception:
            raise LoginError(f"Failed to parse login response: {resp.text[:200]}")

        logger.debug(f"[Auth] Legacy login response: {json.dumps(result, ensure_ascii=False)[:300]}")

        # ─── Handle: SUCCESS ───
        if result.get("authenticated"):
            login_result = self._handle_login_success(session, result, username)
            # Save device cookies after successful login (Layer 2)
            self._save_device_cookies(session)
            return login_result

        # ─── Handle: TWO-FACTOR ───
        if result.get("two_factor_required"):
            two_factor_info = result.get("two_factor_info", {})
            identifier = two_factor_info.get("two_factor_identifier", "")

            if verification_code:
                tfa_result = self._verify_two_factor(session, username, identifier, verification_code, csrf_token, login_headers)
                self._save_device_cookies(session)
                return tfa_result
            elif two_factor_callback:
                code = two_factor_callback()
                tfa_result = self._verify_two_factor(session, username, identifier, code, csrf_token, login_headers)
                self._save_device_cookies(session)
                return tfa_result
            else:
                raise TwoFactorRequired(
                    f"Two-factor authentication required. "
                    f"Provide verification_code or two_factor_callback parameter. "
                    f"Identifier: {identifier}"
                )

        # ─── Handle: CHECKPOINT (Layer 3 — auto-resolve) ───
        checkpoint_url = result.get("checkpoint_url")
        if not checkpoint_url and result.get("message") == "checkpoint_required":
            # Some checkpoint responses have the URL in flow_render_data or need probing
            checkpoint_url = result.get("flow_render_data", {}).get("checkpoint_url", "")
        if checkpoint_url:
            logger.info(f"[Auth] Checkpoint triggered: {checkpoint_url}")
            return self._resolve_checkpoint(
                session, checkpoint_url, csrf_token,
                challenge_callback, username, password,
            )

        # ─── Handle: checkpoint_required without URL ───
        if result.get("message") == "checkpoint_required":
            logger.info("[Auth] checkpoint_required but no URL — probing for challenge...")
            challenge_url = self._probe_for_challenge(session, csrf_token, login_headers, login_data)
            if challenge_url:
                logger.info(f"[Auth] Challenge found: {challenge_url}")
                return self._resolve_checkpoint(
                    session, challenge_url, csrf_token,
                    challenge_callback, username, password,
                )
            raise LoginError(
                f"Checkpoint required but could not find challenge URL. "
                f"Please login via browser first to resolve the challenge."
            )

        # ─── Handle: AuthPlatformLoginChallengeException ───
        exception_name = result.get("exception_name", "")
        error_type = result.get("error_type", "")
        is_auth_platform = (
            "AuthPlatform" in exception_name
            or error_type == "AuthPlatformLoginChallengeException"
        )
        if is_auth_platform:
            # Use checkpoint_url if it has apc parameter, otherwise fallback
            ap_url = result.get("checkpoint_url", "/auth_platform/")
            logger.info(f"[Auth] AuthPlatform challenge detected: {ap_url[:80]}...")
            return self._resolve_checkpoint(
                session, ap_url,
                csrf_token, challenge_callback, username, password,
            )

        # ─── Handle: UserInvalidCredentials (might be a masked challenge!) ───
        error_type = result.get("error_type", "")
        user_exists = result.get("user", False)

        if error_type == "UserInvalidCredentials" and user_exists:
            # User exists but "invalid credentials" — could be active challenge
            # blocking login. Try to detect and auto-resolve.
            logger.info("[Auth] UserInvalidCredentials with user=true — probing for hidden challenge...")

            challenge_url = self._probe_for_challenge(session, csrf_token, login_headers, login_data)

            if challenge_url:
                logger.info(f"[Auth] Hidden challenge found: {challenge_url}")
                resolve_result = self._resolve_checkpoint(
                    session, challenge_url, csrf_token,
                    challenge_callback, username, password,
                )
                # If challenge resolved, retry login
                if resolve_result.get("authenticated"):
                    return resolve_result
                # Challenge resolved but need to re-login
                logger.info("[Auth] Challenge resolved — retrying login...")
                time.sleep(2)
                return self.login(
                    username, password,
                    two_factor_callback=two_factor_callback,
                    challenge_callback=challenge_callback,
                    email_credentials=getattr(self, '_email_credentials', None),
                    device_cookies_file=self._device_cookies_file,
                )

            # No challenge found — password is genuinely wrong
            raise LoginError(
                f"Incorrect username or password for @{username}."
            )

        if error_type == "UserInvalidCredentials":
            raise LoginError(f"Username @{username} not found or password incorrect.")

        # ─── Handle: user=true, authenticated=false (needs checkpoint) ───
        if result.get("user") and not result.get("authenticated"):
            logger.info("[Auth] Password accepted but not authenticated — probing...")
            challenge_url = self._probe_for_challenge(session, csrf_token, login_headers, login_data)
            if challenge_url:
                return self._resolve_checkpoint(
                    session, challenge_url, csrf_token,
                    challenge_callback, username, password,
                )
            # Try auth_platform as fallback
            logger.info("[Auth] No challenge URL — trying auth_platform...")
            return self._resolve_checkpoint(
                session, "/auth_platform/", csrf_token,
                challenge_callback, username, password,
            )

        raise LoginError(f"Login failed: {json.dumps(result, ensure_ascii=False)}")

    def _probe_for_challenge(
        self,
        session,
        csrf_token: str,
        login_headers: dict,
        login_data: dict,
    ) -> Optional[str]:
        """
        Probe for an active hidden challenge.

        When Instagram returns UserInvalidCredentials but user exists,
        there might be an unresolved challenge blocking all logins.

        Strategy:
            1. Re-send login with allow_redirects=True → check for challenge redirect
            2. Check response headers for checkpoint location
            3. Try the /challenge/ web endpoint
            4. Try /accounts/login/ and check for challenge redirect

        Returns:
            str: Challenge URL if found, None otherwise
        """
        import random

        # Strategy 1: Re-POST login with allow_redirects=True
        logger.debug("[Auth] Probe strategy 1: POST login with redirects...")
        try:
            resp = session.post(
                LOGIN_URL,
                headers=login_headers,
                data=login_data,
                timeout=30,
                allow_redirects=True,
            )

            # Check final URL for challenge
            final_url = str(resp.url) if hasattr(resp, 'url') else ""
            if "/challenge/" in final_url:
                logger.info(f"[Auth] Challenge redirect detected: {final_url}")
                return final_url

            # Check response for checkpoint_url
            try:
                data = resp.json()
                cp_url = data.get("checkpoint_url")
                if cp_url:
                    return cp_url
            except Exception:
                # HTML response — check for challenge patterns
                if "/challenge/" in resp.text:
                    import re
                    match = re.search(r'(/challenge/[^"\'>\s]+)', resp.text)
                    if match:
                        return f"https://www.instagram.com{match.group(1)}"

            # Check Location header
            location = resp.headers.get("Location", resp.headers.get("location", ""))
            if "/challenge/" in location:
                return location if location.startswith("http") else f"https://www.instagram.com{location}"

        except Exception as e:
            logger.debug(f"[Auth] Probe strategy 1 failed: {e}")

        time.sleep(random.uniform(1.0, 2.0))

        # Strategy 2: Visit login page and check for challenge redirect
        logger.debug("[Auth] Probe strategy 2: GET login page with redirects...")
        try:
            resp = session.get(
                "https://www.instagram.com/accounts/login/",
                headers={
                    "user-agent": WEB_USER_AGENT,
                    "referer": "https://www.instagram.com/",
                },
                timeout=15,
                allow_redirects=True,
            )

            final_url = str(resp.url) if hasattr(resp, 'url') else ""
            if "/challenge/" in final_url:
                return final_url

            # Check HTML for challenge forms/links
            if "/challenge/" in resp.text:
                import re
                match = re.search(r'(/challenge/[^"\'>\s]+)', resp.text)
                if match:
                    return f"https://www.instagram.com{match.group(1)}"

        except Exception as e:
            logger.debug(f"[Auth] Probe strategy 2 failed: {e}")

        time.sleep(random.uniform(1.0, 2.0))

        # Strategy 3: Try the challenge API endpoint directly
        logger.debug("[Auth] Probe strategy 3: Direct /challenge/ access...")
        try:
            resp = session.get(
                "https://www.instagram.com/challenge/",
                headers={
                    "user-agent": WEB_USER_AGENT,
                    "x-csrftoken": csrf_token,
                    "referer": "https://www.instagram.com/accounts/login/",
                },
                timeout=15,
                allow_redirects=True,
            )

            final_url = str(resp.url) if hasattr(resp, 'url') else ""
            if "/challenge/" in final_url and final_url != "https://www.instagram.com/challenge/":
                return final_url

            # Check for challenge content
            if "This Was Me" in resp.text or "unusual" in resp.text.lower() or "suspicious" in resp.text.lower():
                return str(resp.url) if hasattr(resp, 'url') else "https://www.instagram.com/challenge/"

        except Exception as e:
            logger.debug(f"[Auth] Probe strategy 3 failed: {e}")

        # Strategy 4: Try Instagram's private API challenge endpoint
        logger.debug("[Auth] Probe strategy 4: Private API challenge check...")
        try:
            resp = session.get(
                "https://i.instagram.com/api/v1/challenge/",
                headers={
                    "user-agent": WEB_USER_AGENT,
                    "x-csrftoken": csrf_token,
                    "x-ig-app-id": "1217981644879628",
                },
                timeout=15,
            )

            try:
                data = resp.json()
                challenge_url = data.get("challenge", {}).get("url", "")
                if challenge_url:
                    return challenge_url
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"[Auth] Probe strategy 4 failed: {e}")

        logger.warning("[Auth] No hidden challenge found — credentials may be wrong")
        return None

    # ═══════════════════════════════════════════════════════════
    # LAYER 3: CHALLENGE AUTO-RESOLUTION
    # ═══════════════════════════════════════════════════════════

    def _resolve_checkpoint(
        self,
        session,
        checkpoint_url: str,
        csrf_token: str,
        challenge_callback: Optional[Callable] = None,
        username: str = "",
        password: str = "",
    ) -> Dict[str, Any]:
        """
        Auto-resolve a checkpoint/challenge.

        Tries:
            1. ChallengeHandler (if callback provided)
            2. "This Was Me" auto-confirm
            3. Raise CheckpointRequired as last resort
        """
        from ..challenge import ChallengeHandler, ChallengeType

        # Normalize URL
        if not checkpoint_url.startswith("http"):
            checkpoint_url = f"https://www.instagram.com{checkpoint_url}"

        # auth_platform challenges use new Instagram flow
        if "/auth_platform/" in checkpoint_url or "auth_platform" in checkpoint_url:
            logger.info("[Auth] auth_platform challenge detected")
            return self._resolve_auth_platform(
                session, checkpoint_url, csrf_token,
                challenge_callback, username, password,
            )

        # Try approach 1: GET the checkpoint page to see what type it is
        logger.info(f"[Auth] Fetching checkpoint: {checkpoint_url}")
        try:
            resp = session.get(
                checkpoint_url,
                headers={
                    "user-agent": WEB_USER_AGENT,
                    "x-csrftoken": csrf_token,
                    "referer": "https://www.instagram.com/accounts/login/",
                },
                timeout=15,
            )

            # Check if it's a "This Was Me" page
            page_text = resp.text
            if "This Was Me" in page_text or "this-was-me" in page_text or "it_was_me" in page_text:
                logger.info("[Auth] 'This Was Me' challenge detected — auto-confirming...")
                # Try to auto-confirm "This Was Me"
                confirm_resp = session.post(
                    checkpoint_url,
                    headers={
                        "user-agent": WEB_USER_AGENT,
                        "x-csrftoken": csrf_token,
                        "x-requested-with": "XMLHttpRequest",
                        "referer": checkpoint_url,
                        "origin": "https://www.instagram.com",
                        "content-type": "application/x-www-form-urlencoded",
                    },
                    data={"choice": "0"},  # 0 = "This Was Me" / approve
                    timeout=15,
                )
                try:
                    confirm_result = confirm_resp.json()
                    if confirm_result.get("status") == "ok" or confirm_result.get("logged_in_user"):
                        logger.info("[Auth] 'This Was Me' confirmed! ✅")
                        # Save cookies and return success
                        self._save_device_cookies(session)
                        user_id = confirm_result.get("logged_in_user", {}).get("pk", "")
                        return {
                            "status": "ok",
                            "authenticated": True,
                            "user_id": str(user_id),
                            "username": username,
                            "challenge_resolved": True,
                        }
                except Exception:
                    pass  # Fall through to ChallengeHandler

        except Exception as e:
            logger.warning(f"[Auth] Checkpoint page fetch failed: {e}")

        # Try approach 2: Use ChallengeHandler with callback
        if challenge_callback:
            logger.info("[Auth] Using ChallengeHandler to resolve...")
            handler = ChallengeHandler(code_callback=challenge_callback)
            result = handler.resolve(session, checkpoint_url, csrf_token, WEB_USER_AGENT)

            if result.success:
                logger.info("[Auth] Challenge resolved! ✅")
                self._save_device_cookies(session)
                return {
                    "status": "ok",
                    "authenticated": True,
                    "username": username,
                    "challenge_resolved": True,
                    "challenge_type": result.challenge_type.value,
                }

            logger.warning(f"[Auth] Challenge resolution failed: {result.message}")

        # Last resort: raise exception
        raise CheckpointRequired(
            f"Instagram security checkpoint triggered.\n"
            f"URL: {checkpoint_url}\n"
            f"Options:\n"
            f"  1. Open the URL in browser → click 'This Was Me' → retry login\n"
            f"  2. Provide challenge_callback to auto-resolve\n"
            f"  3. Wait 15-30 min and retry"
        )

    def _resolve_auth_platform(
        self,
        session,
        checkpoint_url: str,
        csrf_token: str,
        challenge_callback: Optional[Callable] = None,
        username: str = "",
        password: str = "",
    ) -> Dict[str, Any]:
        """
        Resolve auth_platform challenge using GraphQL API.
        Delegates to auth_platform module.

        After challenge resolution, re-POSTs login on the SAME session
        (a fresh self.login() would create a new session and trigger
        another challenge — infinite loop).
        """
        from ..auth_platform import resolve_auth_platform as _resolve_ap

        result = _resolve_ap(
            session, checkpoint_url, csrf_token, WEB_USER_AGENT,
            challenge_callback, username,
        )

        if result and result.get("authenticated"):
            self._save_device_cookies(session)
            return result

        # If challenge resolved but not authenticated, try to get session
        if result and result.get("challenge_resolved"):
            logger.info("[Auth] Challenge resolved — trying to complete login...")
            time.sleep(2)

            # Update CSRF token from session cookies
            new_csrf = session.cookies.get("csrftoken", csrf_token)

            # Step A: Visit Instagram homepage — browser does this after challenge
            # Instagram may set session cookies on this navigation
            logger.info("[Auth] Visiting instagram.com to check for session...")
            try:
                home_resp = session.get(
                    "https://www.instagram.com/",
                    headers={
                        "user-agent": WEB_USER_AGENT,
                        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "referer": checkpoint_url if checkpoint_url.startswith("http") else f"https://www.instagram.com{checkpoint_url}",
                        "sec-fetch-dest": "document",
                        "sec-fetch-mode": "navigate",
                        "sec-fetch-site": "same-origin",
                    },
                    timeout=15,
                    allow_redirects=True,
                )
                logger.info(f"[Auth] Homepage status: {home_resp.status_code}, cookies: {list(session.cookies.keys())}")
            except Exception as e:
                logger.debug(f"[Auth] Homepage visit failed: {e}")

            # Check if homepage gave us session
            if session.cookies.get("sessionid"):
                logger.info("[Auth] Session cookie found after homepage visit! ✅")
                ds_user_id = session.cookies.get("ds_user_id", "")
                self._client._session_mgr.add_session(
                    session_id=session.cookies.get("sessionid", ""),
                    csrf_token=session.cookies.get("csrftoken", new_csrf),
                    ds_user_id=ds_user_id,
                    mid=session.cookies.get("mid", ""),
                    ig_did=session.cookies.get("ig_did", ""),
                    datr=session.cookies.get("datr", ""),
                    user_agent=WEB_USER_AGENT,
                )
                self._save_device_cookies(session)
                return {
                    "status": "ok",
                    "authenticated": True,
                    "user_id": ds_user_id,
                    "username": username,
                    "challenge_resolved": True,
                }

            # Step B: Re-POST login on same session
            logger.info("[Auth] No session from homepage — re-posting login...")
            enc_password = f"#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{password}"

            login_headers = {
                "user-agent": WEB_USER_AGENT,
                "x-csrftoken": new_csrf,
                "x-requested-with": "XMLHttpRequest",
                "x-ig-app-id": "1217981644879628",
                "x-instagram-ajax": self._server_revision or "1033859812",
                "referer": "https://www.instagram.com/accounts/login/",
                "origin": "https://www.instagram.com",
                "content-type": "application/x-www-form-urlencoded",
                "sec-ch-ua": SEC_CH_UA,
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
            }

            login_data = {
                "username": username,
                "enc_password": enc_password,
                "queryParams": "{}",
                "optIntoOneTap": "false",
                "trustedDeviceRecords": "{}",
            }

            try:
                resp = session.post(
                    LOGIN_URL,
                    headers=login_headers,
                    data=login_data,
                    timeout=30,
                    allow_redirects=True,
                )

                # Check cookies first (might have session from redirect)
                if session.cookies.get("sessionid"):
                    logger.info("[Auth] Session from re-login redirect! ✅")
                    ds_user_id = session.cookies.get("ds_user_id", "")
                    self._client._session_mgr.add_session(
                        session_id=session.cookies.get("sessionid", ""),
                        csrf_token=session.cookies.get("csrftoken", new_csrf),
                        ds_user_id=ds_user_id,
                        mid=session.cookies.get("mid", ""),
                        ig_did=session.cookies.get("ig_did", ""),
                        datr=session.cookies.get("datr", ""),
                        user_agent=WEB_USER_AGENT,
                    )
                    self._save_device_cookies(session)
                    return {
                        "status": "ok",
                        "authenticated": True,
                        "user_id": ds_user_id,
                        "username": username,
                        "challenge_resolved": True,
                    }

                try:
                    login_result = resp.json()
                except Exception:
                    logger.warning(f"[Auth] Re-login response not JSON: {resp.text[:200]}")
                    raise LoginError(f"Re-login after challenge failed: {resp.text[:200]}")

                logger.info(f"[Auth] Re-login response: {json.dumps(login_result, ensure_ascii=False)[:300]}")

                # SUCCESS
                if login_result.get("authenticated"):
                    auth_result = self._handle_login_success(session, login_result, username)
                    self._save_device_cookies(session)
                    return auth_result

                # STILL checkpoint (different type maybe)
                cp_url = login_result.get("checkpoint_url", "")
                if cp_url and "/auth_platform/" not in cp_url:
                    logger.info(f"[Auth] Different checkpoint after challenge: {cp_url}")
                    return self._resolve_checkpoint(
                        session, cp_url, new_csrf,
                        challenge_callback, username, password,
                    )

                # 2FA
                if login_result.get("two_factor_required"):
                    two_factor_info = login_result.get("two_factor_info", {})
                    identifier = two_factor_info.get("two_factor_identifier", "")
                    raise TwoFactorRequired(
                        f"Two-factor required after challenge. Identifier: {identifier}"
                    )

                logger.warning(f"[Auth] Re-login after challenge failed: {json.dumps(login_result)[:300]}")

            except (LoginError, TwoFactorRequired):
                raise
            except Exception as e:
                logger.warning(f"[Auth] Re-login POST failed: {e}")

        # Challenge failed
        if not challenge_callback:
            from ..exceptions import CheckpointRequired
            raise CheckpointRequired(
                "Email verification needed.\n"
                'Use: ig.login("user", "pass", email_credentials=("email", "app_pass"))'
            )

        raise LoginError("auth_platform challenge could not be resolved")

    def _handle_login_success(self, session, result: dict, username: str) -> Dict[str, Any]:
        """Extract and save session cookies after successful login."""
        user_id = str(result.get("userId", result.get("user_id", "")))

        cookies = {}
        for name, value in session.cookies.items():
            cookies[name] = value

        session_id = cookies.get("sessionid", "")
        csrf_token = cookies.get("csrftoken", "")
        mid = cookies.get("mid", "")
        ig_did = cookies.get("ig_did", "")
        datr = cookies.get("datr", "")
        ds_user_id = cookies.get("ds_user_id", user_id)

        if not session_id:
            raise LoginError("Login reported success, but sessionid cookie not found!")

        # Register session
        self._client._session_mgr.add_session(
            session_id=session_id,
            csrf_token=csrf_token,
            ds_user_id=ds_user_id,
            mid=mid,
            ig_did=ig_did,
            datr=datr,
            user_agent=WEB_USER_AGENT,
        )

        logger.info(f"Login successful! User: {username} (ID: {ds_user_id})")

        return {
            "status": "ok",
            "authenticated": True,
            "user_id": ds_user_id,
            "username": username,
            "session_id": session_id,
            "csrf_token": csrf_token,
        }

    def _verify_two_factor(
        self,
        session,
        username: str,
        identifier: str,
        code: str,
        csrf_token: str,
        headers: dict,
    ) -> Dict[str, Any]:
        """Verify two-factor authentication code."""
        data = {
            "username": username,
            "verificationCode": code,
            "identifier": identifier,
            "queryParams": "{}",
            "trustedDeviceRecords": "{}",
        }

        resp = session.post(
            TWO_FACTOR_URL,
            headers={**headers, "x-csrftoken": csrf_token},
            data=data,
            timeout=30,
            allow_redirects=False,
        )

        try:
            result = resp.json()
        except Exception:
            raise LoginError(f"Failed to parse 2FA response: {resp.text[:200]}")

        if result.get("authenticated"):
            return self._handle_login_success(session, result, username)

        raise LoginError(f"2FA verification failed: {result.get('message', 'Invalid code')}")

    def logout(self) -> Dict[str, Any]:
        """
        Logout from Instagram.
        Invalidates the current session.
        """
        try:
            result = self._client.post(
                "/accounts/logout/",
                data={"one_tap_app_login": "0"},
                rate_category="post_default",
            )
            logger.info("Logout successful")
            return result
        except Exception as e:
            logger.warning(f"Logout error (session may already be invalid): {e}")
            return {"status": "ok", "message": "session cleared"}

    def validate_session(self) -> bool:
        """
        Check if the current session is still valid.

        Returns:
            bool: True if session works, False if re-login needed
        """
        try:
            result = self._client.get(
                "/accounts/current_user/",
                rate_category="get_profile",
            )
            return result.get("status") == "ok" or "user" in result
        except Exception:
            return False

    def save_session(self, filepath: str) -> None:
        """
        Save current session cookies to a file.
        No re-login needed next time.

        Args:
            filepath: File path to save to (e.g. "session.json")
        """
        sess = self._client._session_mgr.get_session()
        if not sess:
            raise Exception("No active session to save!")

        data = {
            "session_id": sess.session_id,
            "csrf_token": sess.csrf_token,
            "ds_user_id": sess.ds_user_id,
            "mid": sess.mid or "",
            "ig_did": sess.ig_did or "",
            "datr": sess.datr or "",
            "user_agent": sess.user_agent or "",
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Session saved: {filepath}")

    def load_session(self, filepath: str) -> bool:
        """
        Load a previously saved session.

        Args:
            filepath: Session file path

        Returns:
            bool: True if session loaded and valid
        """
        import os
        if not os.path.exists(filepath):
            logger.warning(f"Session file not found: {filepath}")
            return False

        with open(filepath, "r") as f:
            data = json.load(f)

        self._client._session_mgr.add_session(
            session_id=data["session_id"],
            csrf_token=data["csrf_token"],
            ds_user_id=data.get("ds_user_id", data.get("user_id", "")),
            mid=data.get("mid", ""),
            ig_did=data.get("ig_did", ""),
            datr=data.get("datr", ""),
            user_agent=data.get("user_agent", ""),
            ig_www_claim=data.get("ig_www_claim", ""),
            rur=data.get("rur", ""),
        )

        is_valid = self.validate_session()
        if is_valid:
            logger.info(f"Session loaded and valid: {filepath}")
        else:
            logger.warning(f"Session loaded but invalid: {filepath}. Re-login needed.")

        return is_valid


# ─── EXCEPTIONS ──────────────────────────────────────────────

class LoginError(Exception):
    """Login error"""
    pass


class TwoFactorRequired(LoginError):
    """Two-factor authentication required"""
    pass


class CheckpointRequired(LoginError):
    """Instagram security checkpoint triggered"""
    pass
