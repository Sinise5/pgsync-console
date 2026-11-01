"""Notification service for job/execution alerts."""

import logging
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import json

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    """Supported notification channels."""
    TELEGRAM = "telegram"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"


@dataclass
class NotificationPayload:
    """Standard notification payload."""
    channel: NotificationChannel
    title: str
    message: str
    details: Dict[str, Any] = None
    severity: str = "info"  # info, warning, error


class NotificationProvider(ABC):
    """Base notification provider."""

    @abstractmethod
    async def send(self, payload: NotificationPayload) -> bool:
        """Send notification. Return True on success."""
        pass


class TelegramNotifier(NotificationProvider):
    """Telegram notification handler."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"

    async def send(self, payload: NotificationPayload) -> bool:
        """Send Telegram message."""
        try:
            import aiohttp

            text = f"🔔 *{payload.title}*\n\n{payload.message}"
            if payload.details:
                text += "\n\n" + json.dumps(payload.details, indent=2)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/sendMessage",
                    json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")
            return False


class EmailNotifier(NotificationProvider):
    """Email notification handler."""

    def __init__(self, smtp_host: str, smtp_port: int, sender: str, password: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender = sender
        self.password = password

    async def send(self, payload: NotificationPayload) -> bool:
        """Send email."""
        try:
            import aiosmtplib
            from email.mime.text import MIMEText

            msg = MIMEText(payload.message)
            msg["Subject"] = payload.title
            msg["From"] = self.sender

            async with aiosmtplib.SMTP(hostname=self.smtp_host, port=self.smtp_port) as smtp:
                await smtp.login(self.sender, self.password)
                await smtp.send_message(msg)
                return True
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            return False


class WebhookNotifier(NotificationProvider):
    """Webhook notification handler."""

    def __init__(self, url: str, headers: Dict[str, str] = None):
        self.url = url
        self.headers = headers or {}

    async def send(self, payload: NotificationPayload) -> bool:
        """Send webhook."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.url,
                    json=payload.__dict__,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    return resp.status in [200, 201, 202, 204]
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")
            return False


class SlackNotifier(NotificationProvider):
    """Slack notification handler."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, payload: NotificationPayload) -> bool:
        """Send Slack message."""
        try:
            import aiohttp

            color_map = {"info": "#36a64f", "warning": "#ff9900", "error": "#ff0000"}

            slack_msg = {
                "attachments": [
                    {
                        "color": color_map.get(payload.severity, "#36a64f"),
                        "title": payload.title,
                        "text": payload.message,
                        "fields": [
                            {"title": k, "value": str(v), "short": True}
                            for k, v in (payload.details or {}).items()
                        ],
                    }
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=slack_msg,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            return False


class NotificationManager:
    """Manages multi-channel notifications."""

    def __init__(self):
        self.providers: Dict[NotificationChannel, NotificationProvider] = {}

    def register_provider(self, channel: NotificationChannel, provider: NotificationProvider):
        """Register notification provider."""
        self.providers[channel] = provider
        logger.info(f"Registered provider: {channel.value}")

    async def notify(self, payload: NotificationPayload) -> bool:
        """Send notification via registered provider."""
        if payload.channel not in self.providers:
            logger.warning(f"No provider for channel: {payload.channel.value}")
            return False

        provider = self.providers[payload.channel]
        return await provider.send(payload)

    async def notify_all(
        self, channels: List[NotificationChannel], payload: NotificationPayload
    ) -> Dict[NotificationChannel, bool]:
        """Send to multiple channels."""
        results = {}
        for channel in channels:
            payload_copy = NotificationPayload(
                channel=channel,
                title=payload.title,
                message=payload.message,
                details=payload.details,
                severity=payload.severity,
            )
            results[channel] = await self.notify(payload_copy)
        return results


# Singleton instance
notification_manager = NotificationManager()
