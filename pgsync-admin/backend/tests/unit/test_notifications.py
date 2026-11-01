"""Tests for notification channel dispatch."""

import asyncio

import pytest

from backend.services.notification_service import (
    NotificationChannel,
    NotificationManager,
    NotificationPayload,
)


class FakeProvider:
    def __init__(self, result=True):
        self.result = result
        self.payloads = []

    async def send(self, payload):
        self.payloads.append(payload)
        return self.result


class TestNotificationService:
    def test_supported_channels(self):
        assert NotificationChannel("telegram") is NotificationChannel.TELEGRAM
        assert NotificationChannel("webhook") is NotificationChannel.WEBHOOK
        with pytest.raises(ValueError):
            NotificationChannel("unknown")

    def test_notify_dispatches_to_provider(self):
        manager = NotificationManager()
        provider = FakeProvider()
        manager.register_provider(NotificationChannel.WEBHOOK, provider)
        payload = NotificationPayload(
            channel=NotificationChannel.WEBHOOK,
            title="Test alert",
            message="A sync failed",
            details={"execution_id": 7},
            severity="error",
        )

        result = asyncio.run(manager.notify(payload))
        assert result is True
        assert provider.payloads == [payload]

    def test_notify_without_provider_returns_false(self):
        manager = NotificationManager()
        payload = NotificationPayload(
            channel=NotificationChannel.EMAIL,
            title="Test",
            message="No provider configured",
        )
        assert asyncio.run(manager.notify(payload)) is False
