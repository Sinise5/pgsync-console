"""ClickHouse client for logs and metrics storage."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from clickhouse_driver import Client

from backend.config import settings

logger = logging.getLogger(__name__)


class ClickHouseClient:
    """ClickHouse client for telemetry data."""

    def __init__(self):
        self.client: Optional[Client] = None
        self.logger = logger
        self._ensure_connection()

    def _ensure_connection(self):
        """Ensure ClickHouse connection is established."""
        try:
            # First connect WITHOUT database to create it if needed
            init_client = Client(
                host=settings.clickhouse_host,
                port=settings.clickhouse_port,
                user=settings.clickhouse_user,
                password=settings.clickhouse_password,
                connect_timeout=2,
            )
            try:
                init_client.execute(f"CREATE DATABASE IF NOT EXISTS {settings.clickhouse_database}")
                logger.info(f"ClickHouse database '{settings.clickhouse_database}' ensured")
            except Exception as e:
                logger.warning(f"Could not create database (may already exist): {e}")

            # Now connect WITH database
            self.client = Client(
                host=settings.clickhouse_host,
                port=settings.clickhouse_port,
                user=settings.clickhouse_user,
                password=settings.clickhouse_password,
                database=settings.clickhouse_database,
                connect_timeout=2,
                send_receive_timeout=5,
            )
            logger.info(f"Connected to ClickHouse: {settings.clickhouse_host}:{settings.clickhouse_port}/{settings.clickhouse_database}")
            self._create_tables()
        except Exception as e:
            logger.warning(f"Failed to connect to ClickHouse (non-blocking): {e}")
            self.client = None

    def _create_tables(self):
        """Create logs and metrics tables if not exist."""
        if not self.client:
            return

        # Logs table
        logs_ddl = """
        CREATE TABLE IF NOT EXISTS pgsync_logs (
            timestamp DateTime,
            execution_id UInt32,
            level String,
            process String,
            table_name String,
            message String,
            context String
        ) ENGINE = MergeTree()
        ORDER BY (timestamp, execution_id)
        TTL timestamp + INTERVAL 90 DAY
        """

        # Metrics table
        metrics_ddl = """
        CREATE TABLE IF NOT EXISTS pgsync_metrics (
            timestamp DateTime,
            execution_id UInt32,
            table_name String,
            operation String,
            latency_ms Float32,
            row_count UInt32,
            error_count UInt32
        ) ENGINE = MergeTree()
        ORDER BY (timestamp, execution_id, table_name)
        TTL timestamp + INTERVAL 90 DAY
        """

        try:
            self.client.execute(logs_ddl)
            self.client.execute(metrics_ddl)
            logger.info("ClickHouse tables created/verified")
        except Exception as e:
            logger.error(f"Failed to create ClickHouse tables: {e}")

    async def insert_log(self, log_entry: Dict[str, Any]):
        """Insert log entry to ClickHouse."""
        if not self.client:
            return

        try:
            timestamp = datetime.fromisoformat(log_entry.get("timestamp", datetime.utcnow().isoformat()))

            self.client.execute(
                "INSERT INTO pgsync_logs VALUES",
                [(
                    timestamp,
                    log_entry.get("execution_id", 0),
                    log_entry.get("level", "INFO"),
                    log_entry.get("process", "pgsync"),
                    log_entry.get("table_name", ""),
                    log_entry.get("message", ""),
                    log_entry.get("context", ""),
                )]
            )
        except Exception as e:
            logger.error(f"Failed to insert log to ClickHouse: {e}")

    async def insert_metric(self, metric: Dict[str, Any]):
        """Insert metric entry to ClickHouse."""
        if not self.client:
            return

        try:
            timestamp = datetime.fromisoformat(metric.get("timestamp", datetime.utcnow().isoformat()))

            self.client.execute(
                "INSERT INTO pgsync_metrics VALUES",
                [(
                    timestamp,
                    metric.get("execution_id", 0),
                    metric.get("table_name", ""),
                    metric.get("operation", ""),
                    metric.get("latency_ms", 0.0),
                    metric.get("row_count", 0),
                    metric.get("error_count", 0),
                )]
            )
        except Exception as e:
            logger.error(f"Failed to insert metric to ClickHouse: {e}")

    def query_logs(
        self,
        execution_id: int,
        limit: int = 100,
        level: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query logs from ClickHouse."""
        if not self.client:
            return []

        try:
            where_clauses = [f"execution_id = {execution_id}"]
            if level:
                where_clauses.append(f"level = '{level}'")

            query = f"""
            SELECT timestamp, level, process, table_name, message, context
            FROM pgsync_logs
            WHERE {' AND '.join(where_clauses)}
            ORDER BY timestamp DESC
            LIMIT {limit}
            """

            result = self.client.execute(query)
            return [
                {
                    "timestamp": row[0].isoformat(),
                    "level": row[1],
                    "process": row[2],
                    "table_name": row[3],
                    "message": row[4],
                    "context": row[5],
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"Failed to query logs: {e}")
            return []

    def query_metrics(
        self,
        execution_id: int,
        table_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query metrics from ClickHouse."""
        if not self.client:
            return []

        try:
            where_clauses = [f"execution_id = {execution_id}"]
            if table_name:
                where_clauses.append(f"table_name = '{table_name}'")

            query = f"""
            SELECT timestamp, table_name, operation, latency_ms, row_count, error_count
            FROM pgsync_metrics
            WHERE {' AND '.join(where_clauses)}
            ORDER BY timestamp DESC
            LIMIT 1000
            """

            result = self.client.execute(query)
            return [
                {
                    "timestamp": row[0].isoformat(),
                    "table_name": row[1],
                    "operation": row[2],
                    "latency_ms": row[3],
                    "row_count": row[4],
                    "error_count": row[5],
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"Failed to query metrics: {e}")
            return []

    def query_daily_metrics(self, start_date: datetime.date, days: int) -> List[Dict[str, Any]]:
        """Get daily aggregated metrics."""
        try:
            if not self.client:
                return []

            query = """
            SELECT
                toDate(timestamp) AS date,
                count() AS total_logs,
                countIf(level = 'ERROR') AS errors,
                countIf(level = 'WARNING') AS warnings,
                countIf(level = 'INFO') AS info,
                uniqExact(execution_id) AS active_executions
            FROM pgsync_logs
            WHERE timestamp >= %(start)s
              AND timestamp < %(start)s + INTERVAL %(days)s DAY
            GROUP BY date
            ORDER BY date DESC
            LIMIT %(days)s
            """
            result = self.client.execute(
                query,
                {"start": start_date.isoformat(), "days": days},
            )
            return [
                {
                    "date": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
                    "total_logs": row[1],
                    "errors": row[2],
                    "warnings": row[3],
                    "info": row[4],
                    "active_executions": row[5],
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"Failed to query daily metrics: {e}")
            return []

    def query_weekly_metrics(self, start_date: datetime.date, weeks: int) -> List[Dict[str, Any]]:
        """Get weekly aggregated metrics."""
        try:
            if not self.client:
                return []

            query = """
            SELECT
                toWeek(timestamp) AS week_number,
                count() AS total_logs,
                countIf(level = 'ERROR') AS errors,
                countIf(level = 'WARNING') AS warnings,
                uniqExact(execution_id) AS active_executions
            FROM pgsync_logs
            WHERE timestamp >= %(start)s
            GROUP BY week_number
            ORDER BY week_number DESC
            LIMIT %(weeks)s
            """
            result = self.client.execute(
                query,
                {"start": start_date.isoformat(), "weeks": weeks},
            )
            return [
                {
                    "week": row[0],
                    "total_logs": row[1],
                    "errors": row[2],
                    "warnings": row[3],
                    "active_executions": row[4],
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"Failed to query weekly metrics: {e}")
            return []

    def query_table_stats(self, config_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get per-table lifetime statistics."""
        try:
            if not self.client:
                return []

            where = ""
            params = {}
            if config_id:
                where = "WHERE cast(execution_id, 'String') = %(config_id)s OR execution_id IN (SELECT id FROM pgsync_executions WHERE config_id = %(config_id)s)"
                params = {"config_id": config_id}

            query = f"""
            SELECT
                table_name,
                uniqExact(execution_id) AS executions,
                count() AS total_ops,
                countIf(operation = 'INSERT') AS inserts,
                countIf(operation = 'UPDATE') AS updates,
                countIf(operation = 'DELETE') AS deletes,
                avg(latency_ms) AS avg_latency,
                sum(row_count) AS total_rows,
                sum(error_count) AS total_errors
            FROM pgsync_metrics
            {where}
            GROUP BY table_name
            ORDER BY total_rows DESC
            """
            result = self.client.execute(query, params)
            return [
                {
                    "table_name": row[0],
                    "executions": row[1],
                    "total_ops": row[2],
                    "inserts": row[3],
                    "updates": row[4],
                    "deletes": row[5],
                    "avg_latency_ms": round(row[6], 2) if row[6] else 0,
                    "total_rows": row[7],
                    "total_errors": row[8],
                }
                for row in result
            ]
        except Exception as e:
            logger.error(f"Failed to query table stats: {e}")
            return []


# Singleton
clickhouse_client = ClickHouseClient()
# NOTE: _create_tables() called lazily on first connection, not at import time
