"""
Auth API
========
Instagram login, logout, 2FA, and challenge resolver.
Web login flow with NaCl crypto_box seal encryption.

Login flow:
    1. GET login page -> fetch encryption keys
    2. Encrypt password with NaCl crypto_box seal
    3. POST /accounts/login/ajax/ -> get sessionid
    4. Handle 2FA/challenge if required

Dependency: pip install pynacl
"""

import json
import time
import logging
import re
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("instaharvest_v2")

# Login endpoints
LOGIN_URL = "https://www.instagram.com/api/v1/web/accounts/login/ajax/"
TWO_FACTOR_URL = "https://www.instagram.com/api/v1/web/accounts/login/ajax/two_factor/"
LOGOUT_URL = "https://www.instagram.com/api/v1/web/accounts/logout/ajax/"
SHARED_DATA_URL = "https://www.instagram.com/data/shared_data/"


class AsyncAuthAPI:
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

    async def _get_encryption_keys(self) -> Dict[str, str]:
        """
        Fetch encryption keys from Instagram login page.
        Returns: {key_id, public_key, version}
        """
        if self._encryption_keys:
            return self._encryption_keys

        session = await self._client._get_curl_session()

        # Try shared data endpoint first
        try:
            resp = session.get(
                SHARED_DATA_URL,
                headers={
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
                    "referer": "https://www.instagram.com/accounts/login/",
                },
                timeout=15,
            )
            data = resp.json()
            encryption = data.get("encryption", {})
            if encryption.get("public_key"):
                self._encryption_keys = encryption
                logger.info(f"Encryption keys fetched: key_id={encryption.get('key_id')}, version={encryption.get('version')}")
                return encryption
        except Exception as e:
            logger.debug(f"shared_data error: {e}")

        # Fallback: parse _sharedData from login page
        try:
            resp = session.get(
                "https://www.instagram.com/accounts/login/",
                headers={
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
                },
                timeout=15,
            )
            match = re.search(r'window\._sharedData\s*=\s*({.+?});', resp.text)
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
            logger.warning(f"Failed to fetch keys from login page: {e}")

        raise Exception("Instagram encryption keys not found! The page structure may have changed.")

    async def _encrypt_password(self, password: str) -> str:
        """
        Encrypt password for Instagram login.
        Uses NaCl crypto_box seal (Curve25519 + XSalsa20-Poly1305).

        Returns:
            str: "#PWD_INSTAGRAM_BROWSER:{version}:{timestamp}:{encrypted}"
        """
        try:
            from nacl.public import PublicKey, SealedBox
        except ImportError:
            raise ImportError(
                "pynacl is required! Install it: pip install pynacl"
            )

        keys = await self._get_encryption_keys()
        key_id = keys["key_id"]
        pub_key_hex = keys["public_key"]
        version = keys.get("version", "10")

        timestamp = str(int(time.time()))

        # Convert hex public key to bytes
        pub_key_bytes = bytes.fromhex(pub_key_hex)

        # Create NaCl public key and sealed box
        nacl_key = PublicKey(pub_key_bytes)
        sealed_box = SealedBox(nacl_key)

        # Encrypt the password
        encrypted = sealed_box.encrypt(password.encode("utf-8"))

        # Build Instagram format payload
        import base64
        payload = (
            b"\x01"  # version byte
            + int(key_id).to_bytes(1, byteorder="big")
            + b"\x00" * 2  # padding
            + bytes.fromhex(format(int(timestamp), "x").zfill(8) if len(format(int(timestamp), "x")) < 8 else format(int(timestamp), "x"))[-4:]
            + encrypted
        )

        enc_b64 = base64.b64encode(payload).decode("utf-8")

        return f"#PWD_INSTAGRAM_BROWSER:{version}:{timestamp}:{enc_b64}"

    async def login(
        self,
        username: str,
        password: str,
        verification_code: str | None = None,
        two_factor_callback: Optional[Callable[[], str]] = None,
    ) -> Dict[str, Any]:
        """
        Login to Instagram with username and password.

        Args:
            username: Instagram username
            password: Account password
            verification_code: 2FA code (if known in advance)
            two_factor_callback: Callback function to request 2FA code from user.
                                 Example: lambda: input("Enter 2FA code: ")

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
            CheckpointRequired: Security checkpoint triggered
        """
        session = await self._client._get_curl_session()

        # 1. Get CSRF token from login page cookies
        try:
            login_page = session.get(
                "https://www.instagram.com/accounts/login/",
                headers={
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
                },
                timeout=15,
            )
            csrf_token = None
            for cookie_name, cookie_value in session.cookies.items():
                if cookie_name == "csrftoken":
                    csrf_token = cookie_value
                    break

            if not csrf_token:
                csrf_token = login_page.headers.get("x-csrftoken", "")
                if not csrf_token:
                    match = re.search(r'"csrf_token":"([^"]+)"', login_page.text)
                    if match:
                        csrf_token = match.group(1)

            if not csrf_token:
                csrf_token = "missing"
                logger.warning("CSRF token not found, login may fail")

        except Exception as e:
            raise Exception(f"Failed to connect to login page: {e}")

        # 2. Encrypt password
        try:
            enc_password = await self._encrypt_password(password)
        except Exception as e:
            logger.warning(f"Password encryption failed: {e}. Using plain password fallback.")
            enc_password = f"#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{password}"

        # 3. POST login request
        login_headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
            "x-csrftoken": csrf_token,
            "x-requested-with": "XMLHttpRequest",
            "x-ig-app-id": "936619743392459",
            "x-instagram-ajax": "1",
            "referer": "https://www.instagram.com/accounts/login/",
            "origin": "https://www.instagram.com",
            "content-type": "application/x-www-form-urlencoded",
        }

        login_data = {
            "username": username,
            "enc_password": enc_password,
            "queryParams": "{}",
            "optIntoOneTap": "false",
            "trustedDeviceRecords": "{}",
        }

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
            raise Exception(f"Failed to parse login response: {resp.text[:200]}")

        # 4. Handle result
        if result.get("authenticated"):
            return await self._handle_login_success(session, result, username)

        if result.get("two_factor_required"):
            two_factor_info = result.get("two_factor_info", {})
            identifier = two_factor_info.get("two_factor_identifier", "")

            if verification_code:
                return self._verify_two_factor(session, username, identifier, verification_code, csrf_token, login_headers)
            elif two_factor_callback:
                code = two_factor_callback()
                return self._verify_two_factor(session, username, identifier, code, csrf_token, login_headers)
            else:
                raise TwoFactorRequired(
                    f"Two-factor authentication required. "
                    f"Provide verification_code or two_factor_callback parameter. "
                    f"Identifier: {identifier}"
                )

        if result.get("checkpoint_url"):
            raise CheckpointRequired(
                f"Instagram security checkpoint triggered. "
                f"URL: {result.get('checkpoint_url')}. "
                f"Please open instagram.com in a browser, complete the verification, "
                f"then try again."
            )

        message = result.get("message", "")
        if "incorrect" in message.lower() or result.get("status") == "fail":
            raise LoginError(f"Incorrect username or password: {message}")

        raise LoginError(f"Login failed: {json.dumps(result, ensure_ascii=False)}")

    async def _handle_login_success(self, session, result: dict, username: str) -> Dict[str, Any]:
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
        await self._client._session_mgr.add_session(
            session_id=session_id,
            csrf_token=csrf_token,
            ds_user_id=ds_user_id,
            mid=mid,
            ig_did=ig_did,
            datr=datr,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
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

    async def _verify_two_factor(
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
            return await self._handle_login_success(session, result, username)

        raise LoginError(f"2FA verification failed: {result.get('message', 'Invalid code')}")

    async def logout(self) -> Dict[str, Any]:
        """
        Logout from Instagram.
        Invalidates the current session.
        """
        try:
            result = await self._client.post(
                "/accounts/logout/",
                data={"one_tap_app_login": "0"},
                rate_category="post_default",
            )
            logger.info("Logout successful")
            return result
        except Exception as e:
            logger.warning(f"Logout error (session may already be invalid): {e}")
            return {"status": "ok", "message": "session cleared"}

    async def validate_session(self) -> bool:
        """
        Check if the current session is still valid.

        Returns:
            bool: True if session works, False if re-login needed
        """
        try:
            result = await self._client.get(
                "/accounts/current_user/",
                rate_category="get_profile",
            )
            return result.get("status") == "ok" or "user" in result
        except Exception:
            return False

    async def save_session(self, filepath: str) -> None:
        """
        Save current session cookies to a file.
        No re-login needed next time.

        Args:
            filepath: File path to save to (e.g. "session.json")
        """
        sess = await self._client._session_mgr.get_session()
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

    async def load_session(self, filepath: str) -> bool:
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

        await self._client._session_mgr.add_session(
            session_id=data["session_id"],
            csrf_token=data["csrf_token"],
            ds_user_id=data["ds_user_id"],
            mid=data.get("mid", ""),
            ig_did=data.get("ig_did", ""),
            datr=data.get("datr", ""),
            user_agent=data.get("user_agent", ""),
        )

        is_valid = await self.validate_session()
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
