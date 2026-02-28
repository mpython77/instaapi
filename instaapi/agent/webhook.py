"""
Agent Webhook — Notification Delivery
=======================================
Send agent results to external services.

Supported channels:
    - Telegram Bot
    - Discord Webhook
    - Email (SMTP)
    - Custom HTTP webhook
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

logger = logging.getLogger("instaapi.agent.webhook")


class WebhookNotifier:
    """
    Send notifications to external services.

    Usage:
        notifier = WebhookNotifier()
        notifier.add_telegram(bot_token="...", chat_id="...")
        notifier.add_discord(webhook_url="...")
        notifier.notify("Task complete!", data={...})
    """

    def __init__(self):
        self._channels: List[Dict] = []

    # ═══════════════════════════════════════════════════════
    # CHANNEL REGISTRATION
    # ═══════════════════════════════════════════════════════

    def add_telegram(self, bot_token: str, chat_id: str) -> "WebhookNotifier":
        """Add Telegram bot notification channel."""
        self._channels.append({
            "type": "telegram",
            "bot_token": bot_token,
            "chat_id": chat_id,
        })
        return self

    def add_discord(self, webhook_url: str) -> "WebhookNotifier":
        """Add Discord webhook notification channel."""
        self._channels.append({
            "type": "discord",
            "webhook_url": webhook_url,
        })
        return self

    def add_email(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        to_email: str,
        from_email: Optional[str] = None,
    ) -> "WebhookNotifier":
        """Add email notification channel."""
        self._channels.append({
            "type": "email",
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "username": username,
            "password": password,
            "to_email": to_email,
            "from_email": from_email or username,
        })
        return self

    def add_custom(self, url: str, headers: Optional[Dict] = None) -> "WebhookNotifier":
        """Add custom HTTP webhook."""
        self._channels.append({
            "type": "custom",
            "url": url,
            "headers": headers or {},
        })
        return self

    # ═══════════════════════════════════════════════════════
    # SEND NOTIFICATIONS
    # ═══════════════════════════════════════════════════════

    def notify(
        self,
        message: str,
        title: str = "InstaAPI Agent",
        data: Optional[Dict] = None,
    ) -> Dict[str, bool]:
        """Send notification to all registered channels."""
        results = {}

        for channel in self._channels:
            ch_type = channel["type"]
            try:
                if ch_type == "telegram":
                    success = self._send_telegram(channel, message, title)
                elif ch_type == "discord":
                    success = self._send_discord(channel, message, title, data)
                elif ch_type == "email":
                    success = self._send_email(channel, message, title)
                elif ch_type == "custom":
                    success = self._send_custom(channel, message, title, data)
                else:
                    success = False

                results[ch_type] = success
            except Exception as e:
                logger.error(f"Notification failed ({ch_type}): {e}")
                results[ch_type] = False

        return results

    @property
    def channel_count(self) -> int:
        return len(self._channels)

    def clear(self):
        """Remove all channels."""
        self._channels.clear()

    # ═══════════════════════════════════════════════════════
    # CHANNEL HANDLERS
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def _send_telegram(channel: Dict, message: str, title: str) -> bool:
        """Send Telegram message."""
        bot_token = channel["bot_token"]
        chat_id = channel["chat_id"]

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = json.dumps({
            "chat_id": chat_id,
            "text": f"🤖 {title}\n\n{message}",
            "parse_mode": "Markdown",
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200

    @staticmethod
    def _send_discord(channel: Dict, message: str, title: str, data: Any = None) -> bool:
        """Send Discord webhook message."""
        url = channel["webhook_url"]

        embed = {
            "title": f"🤖 {title}",
            "description": message[:4096],
            "color": 5814783,  # Blue
        }

        if data:
            fields = []
            for key, val in list(data.items())[:10]:
                fields.append({
                    "name": str(key),
                    "value": str(val)[:1024],
                    "inline": True,
                })
            embed["fields"] = fields

        payload = json.dumps({
            "embeds": [embed],
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 204)

    @staticmethod
    def _send_email(channel: Dict, message: str, title: str) -> bool:
        """Send email via SMTP."""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg["From"] = channel["from_email"]
        msg["To"] = channel["to_email"]
        msg["Subject"] = f"🤖 {title}"

        body = f"{title}\n{'=' * 40}\n\n{message}"
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(channel["smtp_host"], channel["smtp_port"]) as server:
            server.starttls()
            server.login(channel["username"], channel["password"])
            server.send_message(msg)

        return True

    @staticmethod
    def _send_custom(channel: Dict, message: str, title: str, data: Any = None) -> bool:
        """Send custom HTTP webhook."""
        url = channel["url"]
        headers = channel.get("headers", {})

        payload = json.dumps({
            "title": title,
            "message": message,
            "data": data,
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        for key, val in headers.items():
            req.add_header(key, val)

        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201, 204)
