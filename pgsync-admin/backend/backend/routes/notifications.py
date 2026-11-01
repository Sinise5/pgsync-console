"""Notification routes for managing notification providers."""

import json
import logging
from robyn import Request, Response

from backend.services.notification_service import (
    notification_manager,
    NotificationChannel,
    NotificationPayload,
    TelegramNotifier,
    WebhookNotifier,
)

logger = logging.getLogger(__name__)


def notification_routes(app):
    """Register notification management routes."""

    @app.post("/api/notifications/test")
    async def test_notification(request: Request) -> Response:
        """Send a test notification."""
        try:
            body = json.loads(request.body)
            channel = body.get("channel")
            title = body.get("title", "Test Notification")
            message = body.get("message", "This is a test notification from PGSync Admin")

            if not channel:
                return Response(
                    status_code=400,
                    body=json.dumps({"error": "Channel is required"}),
                )

            payload = NotificationPayload(
                channel=NotificationChannel(channel),
                title=title,
                message=message,
                severity="info",
            )

            success = await notification_manager.notify(payload)

            return Response(
                status_code=200 if success else 500,
                body=json.dumps({"success": success}),
            )
        except Exception as e:
            logger.error(f"Failed to send test notification: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/notifications/providers/telegram")
    async def register_telegram(request: Request) -> Response:
        """Register Telegram notification provider."""
        try:
            body = json.loads(request.body)
            bot_token = body.get("bot_token")
            chat_id = body.get("chat_id")

            if not all([bot_token, chat_id]):
                return Response(
                    status_code=400,
                    body=json.dumps({"error": "bot_token and chat_id are required"}),
                )

            provider = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
            notification_manager.register_provider(NotificationChannel.TELEGRAM, provider)

            return Response(
                status_code=200,
                body=json.dumps({"message": "Telegram provider registered"}),
            )
        except Exception as e:
            logger.error(f"Failed to register Telegram provider: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/notifications/providers/webhook")
    async def register_webhook(request: Request) -> Response:
        """Register Webhook notification provider."""
        try:
            body = json.loads(request.body)
            url = body.get("url")
            headers = body.get("headers", {})

            if not url:
                return Response(
                    status_code=400,
                    body=json.dumps({"error": "url is required"}),
                )

            provider = WebhookNotifier(url=url, headers=headers)
            notification_manager.register_provider(NotificationChannel.WEBHOOK, provider)

            return Response(
                status_code=200,
                body=json.dumps({"message": "Webhook provider registered"}),
            )
        except Exception as e:
            logger.error(f"Failed to register Webhook provider: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )
