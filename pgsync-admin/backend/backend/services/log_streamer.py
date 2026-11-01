"""Log streaming service — real-time log capture and WebSocket broadcast."""

import asyncio
import logging
from typing import Set, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class LogStreamer:
    """Capture subprocess logs and broadcast via WebSocket."""

    def __init__(self):
        self.active_streams: Set[int] = set()  # execution_ids
        self.websocket_clients: Set[Any] = set()
        self.logger = logger

    async def stream_logs(self, execution_id: int, process):
        """Stream logs from subprocess stdout/stderr."""
        self.active_streams.add(execution_id)

        try:
            # Read stdout line by line
            while True:
                line = process.stdout.readline()
                if not line:
                    if process.poll() is not None:
                        break
                    await asyncio.sleep(0.1)
                    continue

                log_entry = {
                    "execution_id": execution_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": "INFO",
                    "message": line.strip(),
                }

                # Broadcast to WebSocket clients
                await self.broadcast_log(log_entry)

                # Store to ClickHouse (async)
                await self.store_log(log_entry)

        except Exception as e:
            logger.error(f"Log streaming error (execution {execution_id}): {e}")
        finally:
            self.active_streams.remove(execution_id)

    async def broadcast_log(self, log_entry: dict):
        """Broadcast log entry to all connected WebSocket clients."""
        import json
        message = json.dumps(log_entry)

        for ws in list(self.websocket_clients):
            try:
                await ws.send(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket client: {e}")
                self.websocket_clients.discard(ws)

    async def store_log(self, log_entry: dict):
        """Store log entry to ClickHouse (async, non-blocking)."""
        try:
            from backend.services.clickhouse_client import clickhouse_client
            await clickhouse_client.insert_log(log_entry)
        except Exception as e:
            logger.error(f"Failed to store log to ClickHouse: {e}")

    def register_websocket(self, ws):
        """Register new WebSocket client."""
        self.websocket_clients.add(ws)
        logger.info(f"WebSocket client registered (total: {len(self.websocket_clients)})")

    def unregister_websocket(self, ws):
        """Unregister WebSocket client."""
        self.websocket_clients.discard(ws)
        logger.info(f"WebSocket client unregistered (remaining: {len(self.websocket_clients)})")

    def subscribe(self, ws, execution_id: int):
        """Subscribe WebSocket to execution logs."""
        self.register_websocket(ws)

    def unsubscribe(self, ws, execution_id: int):
        """Unsubscribe WebSocket from execution logs."""
        self.unregister_websocket(ws)


# Singleton
log_streamer = LogStreamer()
