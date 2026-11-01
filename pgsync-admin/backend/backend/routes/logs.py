"""Logs and metrics API routes."""

import json
import logging
from typing import Any
from robyn import Request, Response
from typing import Any

from backend.services.clickhouse_client import clickhouse_client
from backend.services.log_streamer import log_streamer
from backend.services.auth_service import auth_service

logger = logging.getLogger(__name__)


def logs_routes(app: Any) -> None:
    """Register logs and metrics routes."""

    @app.get("/api/logs/:execution_id")
    async def get_execution_logs(request: Request) -> Response:
        """Get logs for an execution.

        GET /api/logs/{execution_id}?limit=100&level=INFO
        """
        try:
            execution_id = int(request.path_params.get("execution_id", 0))
            limit = int(request.query_params.get("limit", "100"))
            level = request.query_params.get("level", None)

            logs = clickhouse_client.query_logs(
                execution_id=execution_id,
                limit=limit,
                level=level,
            )

            return Response(
                status_code=200,
                body=json.dumps({"logs": logs, "count": len(logs)}),
            )

        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.get("/api/metrics/:execution_id")
    async def get_execution_metrics(request: Request) -> Response:
        """Get metrics for an execution.

        GET /api/metrics/{execution_id}?table_name=laporan
        """
        try:
            execution_id = int(request.path_params.get("execution_id", 0))
            table_name = request.query_params.get("table_name", None)

            metrics = clickhouse_client.query_metrics(
                execution_id=execution_id,
                table_name=table_name,
            )

            return Response(
                status_code=200,
                body=json.dumps({"metrics": metrics, "count": len(metrics)}),
            )

        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.get("/api/summary/:execution_id")
    async def get_execution_summary(request: Request) -> Response:
        """Get summary statistics for an execution.

        GET /api/summary/{execution_id}
        """
        try:
            execution_id = int(request.path_params.get("execution_id", 0))

            metrics = clickhouse_client.query_metrics(execution_id=execution_id)

            if not metrics:
                return Response(
                    status_code=404,
                    body=json.dumps({"error": "No metrics found"}),
                )

            total_rows = sum(m.get("row_count", 0) for m in metrics)
            total_errors = sum(m.get("error_count", 0) for m in metrics)
            avg_latency = (
                sum(m.get("latency_ms", 0) for m in metrics) / len(metrics)
                if metrics else 0
            )
            table_count = len(set(m.get("table_name", "") for m in metrics))

            return Response(
                status_code=200,
                body=json.dumps({
                    "execution_id": execution_id,
                    "total_rows": total_rows,
                    "total_errors": total_errors,
                    "avg_latency_ms": round(avg_latency, 2),
                    "table_count": table_count,
                    "metric_count": len(metrics),
                }),
            )

        except Exception as e:
            logger.error(f"Failed to get summary: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.websocket("/api/logs/:execution_id/stream")
    async def stream_logs(ws: Any, execution_id: str) -> None:
        """WebSocket endpoint for live log streaming."""
        handshake = await ws.receive()
        if not isinstance(handshake, str) or not handshake.startswith("auth:") or not auth_service.verify_token(handshake[5:]):
            logger.warning("Rejected unauthenticated live-log WebSocket")
            return

        exec_id = int(execution_id)
        logger.info(f"WebSocket connected for execution {exec_id}")

        log_streamer.subscribe(ws, exec_id)

        try:
            while True:
                message = await ws.receive()
                if message is None:
                    break
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            log_streamer.unsubscribe(ws, exec_id)
            logger.info(f"WebSocket disconnected for execution {exec_id}")
