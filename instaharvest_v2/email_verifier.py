"""
Email Verifier
==============
Auto-read Instagram verification codes from Gmail via IMAP.

Used during login when Instagram sends a verification code
to the user's email (challenge/checkpoint flow).

Usage:
    verifier = EmailVerifier("user@gmail.com", "app-password")
    code = verifier.get_instagram_code(max_wait=60)
"""

import imaplib
import email as email_lib
from email.header import decode_header
import re
import time
import logging
import datetime
from typing import Optional

logger = logging.getLogger("instaharvest_v2")


class EmailVerifier:
    """
    Read Instagram verification codes from Gmail via IMAP.

    Requires Gmail App Password (not regular password):
        1. Go to https://myaccount.google.com/apppasswords
        2. Generate an app password
        3. Use that 16-char password here

    Example:
        verifier = EmailVerifier("you@gmail.com", "xxxx xxxx xxxx xxxx")
        code = verifier.get_instagram_code(max_wait=60)
    """

    # Instagram sender addresses
    INSTAGRAM_SENDERS = [
        "security@mail.instagram.com",
        "no-reply@mail.instagram.com",
        "noreply@mail.instagram.com",
    ]

    # Subjects that contain verification codes
    CODE_SUBJECTS = [
        "verify your account",
        "verification code",
        "confirm your identity",
        "security code",
        "login code",
        "confirmation code",
    ]

    # Regex to find 6-digit code in email body
    CODE_PATTERN = re.compile(r'\b(\d{6})\b')

    def __init__(
        self,
        email_address: str,
        email_password: str,
        imap_server: str = "imap.gmail.com",
        imap_port: int = 993,
    ):
        self.email_address = email_address
        self.email_password = email_password
        self.imap_server = imap_server
        self.imap_port = imap_port
        self._mail: Optional[imaplib.IMAP4_SSL] = None

    def _connect(self) -> imaplib.IMAP4_SSL:
        """Connect to IMAP server."""
        if self._mail is None:
            logger.debug(f"[EmailVerifier] Connecting to {self.imap_server}...")
            self._mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self._mail.login(self.email_address, self.email_password)
            logger.debug("[EmailVerifier] Connected OK")
        return self._mail

    def _disconnect(self):
        """Disconnect from IMAP server."""
        if self._mail:
            try:
                self._mail.logout()
            except Exception:
                pass
            self._mail = None

    def _get_email_body(self, msg) -> str:
        """Extract text body from email message."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        body += payload.decode(charset, errors="replace")
                    except Exception:
                        pass
                elif content_type == "text/html" and not body:
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        body += payload.decode(charset, errors="replace")
                    except Exception:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace")
            except Exception:
                pass
        return body

    def _extract_code(self, body: str) -> Optional[str]:
        """Extract 6-digit verification code from email body."""
        lines = body.split("\n")
        for line in lines:
            line_lower = line.lower().strip()
            if not line_lower:
                continue
            if any(kw in line_lower for kw in [
                "code", "kod", "verify", "confirm", "tasdiqlash",
                "use", "enter", "kiriting",
            ]):
                match = self.CODE_PATTERN.search(line)
                if match:
                    return match.group(1)

        # Fallback: find any 6-digit number in body
        all_codes = self.CODE_PATTERN.findall(body)
        if all_codes:
            for code in all_codes:
                year = int(code[:4]) if len(code) >= 4 else 0
                if not (1990 <= year <= 2030):
                    return code
            return all_codes[0]

        return None

    def _is_instagram_email(self, msg) -> bool:
        """Check if email is from Instagram."""
        from_header = msg.get("From", "").lower()
        return any(sender in from_header for sender in self.INSTAGRAM_SENDERS)

    def _is_code_email(self, msg) -> bool:
        """Check if email subject relates to verification."""
        subject = ""
        raw_subject = msg.get("Subject", "")
        try:
            decoded, enc = decode_header(raw_subject)[0]
            if isinstance(decoded, bytes):
                subject = decoded.decode(enc or "utf-8", errors="replace")
            else:
                subject = decoded
        except Exception:
            subject = raw_subject

        subject_lower = subject.lower()
        return any(kw in subject_lower for kw in self.CODE_SUBJECTS)

    def get_instagram_code(
        self,
        max_wait: int = 90,
        poll_interval: int = 5,
        since_minutes: int = 5,
    ) -> Optional[str]:
        """
        Wait for and read Instagram verification code from email.

        IMPORTANT: Only returns codes from emails that arrive AFTER
        this method is called (prevents stale code reuse).

        Args:
            max_wait: Maximum seconds to wait for code (default 90)
            poll_interval: Seconds between inbox checks (default 5)
            since_minutes: Unused, kept for API compatibility

        Returns:
            str: 6-digit verification code, or None if timeout
        """
        logger.info(f"[EmailVerifier] Waiting for Instagram code (max {max_wait}s)...")
        start_time = time.time()

        # Step 1: Snapshot existing email IDs BEFORE waiting
        # This way we ONLY look at emails that arrive AFTER the challenge
        existing_ids = set()
        try:
            mail = self._connect()
            mail.select("inbox")
            status, messages = mail.search(None, "ALL")
            if status == "OK" and messages[0]:
                existing_ids = set(messages[0].split())
            logger.debug(f"[EmailVerifier] {len(existing_ids)} existing emails to skip")
            self._disconnect()
        except Exception as e:
            logger.debug(f"[EmailVerifier] Pre-scan failed: {e}")
            self._disconnect()

        # Step 2: Poll for NEW emails only
        while time.time() - start_time < max_wait:
            try:
                # Reconnect each poll to get fresh mailbox state
                self._disconnect()
                mail = self._connect()
                mail.select("inbox")

                status, messages = mail.search(None, "ALL")
                if status != "OK":
                    time.sleep(poll_interval)
                    continue

                email_ids = messages[0].split() if messages[0] else []

                # Only check NEW emails (not in existing_ids snapshot)
                new_ids = [eid for eid in email_ids if eid not in existing_ids]

                if not new_ids:
                    elapsed = time.time() - start_time
                    remaining = max_wait - elapsed
                    if remaining > poll_interval:
                        logger.debug(
                            f"[EmailVerifier] No new emails, "
                            f"retry in {poll_interval}s "
                            f"({remaining:.0f}s left)"
                        )
                        time.sleep(poll_interval)
                    continue

                # Check new emails (newest first)
                for email_id in reversed(new_ids):
                    status, msg_data = mail.fetch(email_id, "(RFC822)")
                    if status != "OK":
                        continue

                    for part in msg_data:
                        if not isinstance(part, tuple):
                            continue

                        msg = email_lib.message_from_bytes(part[1])

                        # Check if from Instagram
                        if not self._is_instagram_email(msg):
                            # Mark as checked so we don't re-fetch
                            existing_ids.add(email_id)
                            continue

                        # Check if it's a verification email
                        if not self._is_code_email(msg):
                            existing_ids.add(email_id)
                            continue

                        # Extract code
                        body = self._get_email_body(msg)
                        code = self._extract_code(body)

                        if code:
                            elapsed = time.time() - start_time
                            logger.info(
                                f"[EmailVerifier] Found NEW code: {code} "
                                f"({elapsed:.1f}s)"
                            )
                            return code

                # Mark all checked
                existing_ids.update(new_ids)

                elapsed = time.time() - start_time
                remaining = max_wait - elapsed
                if remaining > poll_interval:
                    time.sleep(poll_interval)

            except imaplib.IMAP4.error as e:
                logger.warning(f"[EmailVerifier] IMAP error: {e}")
                self._disconnect()
                time.sleep(poll_interval)
            except Exception as e:
                logger.warning(f"[EmailVerifier] Error: {e}")
                self._disconnect()
                time.sleep(poll_interval)

        logger.warning(
            f"[EmailVerifier] Timeout: no NEW code received in {max_wait}s"
        )
        return None

    def get_latest_instagram_code(self) -> Optional[str]:
        """
        Get the verification code from the most recent Instagram email.
        Does not wait — returns immediately.

        Returns:
            str: 6-digit code or None
        """
        try:
            mail = self._connect()
            mail.select("inbox")

            status, messages = mail.search(None, "ALL")
            if status != "OK":
                return None

            email_ids = messages[0].split()
            if not email_ids:
                return None

            # Check last 10 emails (newest first)
            for email_id in reversed(email_ids[-10:]):
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                if status != "OK":
                    continue

                for part in msg_data:
                    if not isinstance(part, tuple):
                        continue

                    msg = email_lib.message_from_bytes(part[1])

                    if not self._is_instagram_email(msg):
                        continue

                    if not self._is_code_email(msg):
                        continue

                    body = self._get_email_body(msg)
                    code = self._extract_code(body)
                    if code:
                        return code

            return None
        except Exception as e:
            logger.error(f"[EmailVerifier] Error: {e}")
            return None
        finally:
            self._disconnect()
