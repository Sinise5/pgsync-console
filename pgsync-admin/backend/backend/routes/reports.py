"""Reports and analytics API routes."""

import json
import logging
from typing import Any
from datetime import datetime, timedelta
from robyn import Request, Response

from backend.services.clickhouse_client import clickhouse_client

logger = logging.getLogger(__name__)


def reports_routes(app: Any) -> None:
    """Register reports and analytics routes."""

    @app.get("/api/reports/daily")
    async def get_daily_report(request: Request) -> Response:
        """Get daily aggregated metrics.

        GET /api/reports/daily?days=7
        """
        try:
            days = int(request.query_params.get("days", "7"))
            start_date = (datetime.utcnow() - timedelta(days=days)).date()

            report = clickhouse_client.query_daily_metrics(start_date, days)

            return Response(
                status_code=200,
                headers={"Content-Type": "application/json"},
                body=json.dumps({
                    "period_days": days,
                    "start_date": start_date.isoformat(),
                    "data": report,
                }),
            )

        except Exception as e:
            logger.error(f"Failed to get daily report: {e}")
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                body=json.dumps({"error": str(e)}),
            )

    @app.get("/api/reports/weekly")
    async def get_weekly_report(request: Request) -> Response:
        """Get weekly aggregated metrics.

        GET /api/reports/weekly?weeks=4
        """
        try:
            weeks = int(request.query_params.get("weeks", "4"))
            start_date = (datetime.utcnow() - timedelta(weeks=weeks)).date()

            report = clickhouse_client.query_weekly_metrics(start_date, weeks)

            return Response(
                status_code=200,
                headers={"Content-Type": "application/json"},
                body=json.dumps({
                    "period_weeks": weeks,
                    "start_date": start_date.isoformat(),
                    "data": report,
                }),
            )

        except Exception as e:
            logger.error(f"Failed to get weekly report: {e}")
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                body=json.dumps({"error": str(e)}),
            )

    @app.get("/api/reports/table-stats")
    async def get_table_stats(request: Request) -> Response:
        """Get per-table statistics (lifetime).

        GET /api/reports/table-stats?config_id=1
        """
        try:
            config_id = request.query_params.get("config_id", None)

            stats = clickhouse_client.query_table_stats(config_id)

            return Response(
                status_code=200,
                headers={"Content-Type": "application/json"},
                body=json.dumps({
                    "config_id": config_id,
                    "tables": stats,
                    "count": len(stats),
                }),
            )

        except Exception as e:
            logger.error(f"Failed to get table stats: {e}")
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                body=json.dumps({"error": str(e)}),
            )

    @app.get("/api/reports/export/:format")
    async def export_report(request: Request) -> Response:
        """Export metrics as CSV or JSON.

        GET /api/reports/export/csv?days=7
        GET /api/reports/export/json?days=7
        """
        try:
            format_type = request.path_params.get("format", "json").lower()
            days = int(request.query_params.get("days", "7"))
            start_date = (datetime.utcnow() - timedelta(days=days)).date()

            data = clickhouse_client.query_daily_metrics(start_date, days)

            if format_type == "csv":
                # Convert to CSV
                import csv
                import io
                output = io.StringIO()
                if data:
                    writer = csv.DictWriter(output, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)

                return Response(
                    status_code=200,
                    headers={
                        "Content-Type": "text/csv",
                        "Content-Disposition": 'attachment; filename="report.csv"',
                    },
                    body=output.getvalue(),
                )
            else:
                # JSON export
                return Response(
                    status_code=200,
                    headers={
                        "Content-Type": "application/json",
                        "Content-Disposition": 'attachment; filename="report.json"',
                    },
                    body=json.dumps(data),
                )

        except Exception as e:
            logger.error(f"Failed to export report: {e}")
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                body=json.dumps({"error": str(e)}),
            )
