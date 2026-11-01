"""ClickHouse migration API routes."""

import json
import logging
from robyn import Request, Response

from backend.services.clickhouse_migration_manager import get_clickhouse_migration_manager

logger = logging.getLogger(__name__)


def clickhouse_migration_routes(app):
    """Register ClickHouse migration routes."""

    # Get manager instance lazily
    manager = get_clickhouse_migration_manager()

    @app.get("/api/clickhouse/migrations/current")
    async def get_clickhouse_current(request: Request) -> Response:
        """Get current ClickHouse schema version."""
        try:
            version = manager.get_current_version()
            return Response(
                status_code=200,
                body=json.dumps({
                    "status": "success",
                    "data": {"version": version},
                }),
            )
        except Exception as e:
            logger.error(f"Error getting ClickHouse version: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"status": "error", "message": str(e)}),
            )

    @app.get("/api/clickhouse/migrations/history")
    async def get_clickhouse_history(request: Request) -> Response:
        """Get ClickHouse migration history."""
        try:
            limit = int(request.query_params.get("limit", "10"))
            history = manager.get_history(limit)
            return Response(
                status_code=200,
                body=json.dumps({
                    "status": "success",
                    "data": {"migrations": history},
                }),
            )
        except Exception as e:
            logger.error(f"Error getting ClickHouse history: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"status": "error", "message": str(e)}),
            )

    @app.post("/api/clickhouse/migrations/upgrade")
    async def upgrade_clickhouse(request: Request) -> Response:
        """Apply all pending ClickHouse migrations."""
        try:
            result = manager.upgrade_all()
            status_code = 200 if not result["failed"] else 400

            return Response(
                status_code=status_code,
                body=json.dumps({
                    "status": "success" if not result["failed"] else "partial",
                    "data": result,
                }),
            )
        except Exception as e:
            logger.error(f"Error upgrading ClickHouse: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"status": "error", "message": str(e)}),
            )

    @app.post("/api/clickhouse/migrations/rollback")
    async def rollback_clickhouse(request: Request) -> Response:
        """Rollback ClickHouse migration (manual intervention required)."""
        try:
            payload = json.loads(request.body)
            version = payload.get("version")

            if not version:
                return Response(
                    status_code=400,
                    body=json.dumps({
                        "status": "error",
                        "message": "version required",
                    }),
                )

            success = manager.rollback_migration(version)
            status_code = 200 if success else 400

            return Response(
                status_code=status_code,
                body=json.dumps({
                    "status": "success" if success else "error",
                    "message": f"Rollback for {version} {'completed' if success else 'is not supported automatically; apply a compensating migration manually'}",
                }),
            )
        except Exception as e:
            logger.error(f"Error rolling back ClickHouse: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"status": "error", "message": str(e)}),
            )
