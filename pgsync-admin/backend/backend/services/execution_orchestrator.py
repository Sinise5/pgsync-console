"""Execution orchestration for PGSync and PostgreSQL transfer pipelines."""

import json
import logging
import os
import subprocess
import sys
import tempfile
from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional

import psutil

from backend.db import db
from backend.models import Configuration, Execution
from backend.services.postgres_replication_service import postgres_replication_service
from backend.utils.crypto import CryptoService

logger = logging.getLogger(__name__)


class ExecutionOrchestrator:
    """Start, stop, and monitor all configured pipeline processes."""

    def __init__(self):
        self.processes: Dict[int, subprocess.Popen] = {}
        self.log_paths: Dict[int, str] = {}
        self.crypto = CryptoService()

    def _config(self, config_id: int) -> Configuration:
        with db.get_session() as session:
            config = session.query(Configuration).filter_by(id=config_id).first()
            if not config:
                raise ValueError(f"Configuration {config_id} not found")
            session.expunge(config)
            return config

    def _environment(self, config: Configuration) -> dict[str, str]:
        source_password = self.crypto.decrypt(config.source_pg_password)
        target = json.loads(config.target_config or "{}")
        encrypted_target_password = target.get("password", "")
        target_password = self.crypto.decrypt(encrypted_target_password) if encrypted_target_password and encrypted_target_password != "***" else ""
        env = os.environ.copy()
        env.update({
            "PG_HOST": config.source_pg_host,
            "PG_PORT": str(config.source_pg_port),
            "PG_DATABASE": config.source_pg_database,
            "PG_USER": config.source_pg_user,
            "PG_PASSWORD": source_password,
            "PG_DRIVER": "psycopg2" if config.source_type == "postgres" else "pymysql",
            "MYSQL_DATABASE": config.source_pg_database,
            "ELASTICSEARCH_HOST": str(target.get("host", "localhost")),
            "ELASTICSEARCH_PORT": str(target.get("port", 9200)),
            "ELASTICSEARCH_USER": str(target.get("user") or ""),
            "ELASTICSEARCH_PASSWORD": target_password,
            "ELASTICSEARCH_SCHEME": str(target.get("scheme", "http")),
            "ELASTICSEARCH_USE_SSL": str(target.get("scheme") == "https").lower(),
            "ELASTICSEARCH_VERIFY_CERTS": str(bool(target.get("verify_certs", True))).lower(),
            "ELASTICSEARCH": str(target.get("type") == "elasticsearch").lower(),
            "OPENSEARCH": str(target.get("type") == "opensearch").lower(),
            "CLICKHOUSE_HOST": str(target.get("host", "localhost")),
            "CLICKHOUSE_PORT": str(target.get("port", 8123)),
            "CLICKHOUSE_USER": str(target.get("user") or "default"),
            "CLICKHOUSE_PASSWORD": target_password,
            "CLICKHOUSE_DATABASE": str(target.get("database") or "default"),
            "CLICKHOUSE_SECURE": str(bool(target.get("secure", target.get("scheme") == "https"))).lower(),
            "CLICKHOUSE_VERIFY": str(bool(target.get("verify_certs", True))).lower(),
        })
        return env

    @staticmethod
    def _schema(config: Configuration, supplied: Dict[str, Any] | None) -> Dict[str, Any]:
        if supplied:
            return supplied
        schema_config = json.loads(config.schema_config or "{}")
        if config.pipeline_type in {"pg_copy", "pg_replication"}:
            return schema_config
        from backend.services.schema_generator import SchemaGenerator
        return SchemaGenerator().generate({
            "name": config.name,
            "source_pg_database": config.source_pg_database,
            "source_type": config.source_type,
            "target_config": config.target_config,
            "schema_config": config.schema_config,
        })

    @staticmethod
    def _schema_file(config_id: int, execution_id: int, schema: Dict[str, Any]) -> str:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
            prefix=f"pgsync_{config_id}_{execution_id}_",
        ) as schema_file:
            # PGSync's config loader expects a JSON array of schema documents.
            json.dump([schema], schema_file)
            return schema_file.name

    def _start_process(self, execution_id: int, config_id: int, schema: Dict[str, Any] | None, cdc: bool) -> Optional[int]:
        config = self._config(config_id)
        schema = self._schema(config, schema)
        if config.pipeline_type == "pg_replication":
            if not cdc:
                raise ValueError("Continuous PostgreSQL replication must be started as CDC")
            postgres_replication_service.start(config)
            pid = None
        else:
            env = self._environment(config)
            if config.pipeline_type == "pg_copy":
                if cdc:
                    raise ValueError("PostgreSQL copy is a batch operation; create a scheduled batch job for recurring copies")
                if not json.loads(config.target_config or "{}").get("allow_replace"):
                    raise ValueError("Enable the destination replacement acknowledgement before copying")
                cmd = [sys.executable, "-m", "backend.workers.pg_copy", "--config-id", str(config_id)]
            else:
                schema_file = self._schema_file(config_id, execution_id, schema)
                if config.pipeline_type == "pg_clickhouse":
                    cmd = [sys.executable, "-m", "backend.workers.clickhouse_sync", "--schema-file", schema_file] if not cdc else ["pgsync-clickhouse", "-c", schema_file, "--daemon"]
                elif config.pipeline_type == "pg_search":
                    cmd = ["pgsync", "--config", schema_file, "--wal" if cdc else "--bootstrap"]
                else:
                    raise ValueError(f"Unsupported pipeline type: {config.pipeline_type}")
            log_path = os.path.join(tempfile.gettempdir(), f"pgsync-admin-execution-{execution_id}.log")
            with open(log_path, "a", encoding="utf-8") as log_file:
                proc = subprocess.Popen(cmd, env=env, stdout=log_file, stderr=subprocess.STDOUT)
            self.processes[execution_id] = proc
            self.log_paths[execution_id] = log_path
            pid = proc.pid

        with db.get_session() as session:
            execution = session.query(Execution).filter_by(id=execution_id).first()
            if execution:
                execution.status = "running"
                execution.process_pid = pid
                execution.started_at = datetime.utcnow()
                session.commit()
        logger.info("Started %s execution %s (pid=%s)", config.pipeline_type, execution_id, pid)
        return pid

    def get_process_logs(self, execution_id: int, limit: int = 200) -> list[str]:
        """Return recent output from a runner log file."""
        path = self.log_paths.get(execution_id) or os.path.join(
            tempfile.gettempdir(), f"pgsync-admin-execution-{execution_id}.log"
        )
        try:
            with open(path, encoding="utf-8", errors="replace") as log_file:
                return [line.rstrip("\n") for line in deque(log_file, maxlen=max(1, limit))]
        except FileNotFoundError:
            return []

    def start_batch_migration(self, execution_id: int, config_id: int, pgsync_schema: Dict[str, Any] | None = None) -> Optional[int]:
        return self._start_process(execution_id, config_id, pgsync_schema, cdc=False)

    def start_cdc_process(self, execution_id: int, config_id: int, pgsync_schema: Dict[str, Any] | None = None) -> Optional[int]:
        return self._start_process(execution_id, config_id, pgsync_schema, cdc=True)

    def stop_process(self, execution_id: int) -> bool:
        proc = self.processes.get(execution_id)
        try:
            with db.get_session() as session:
                execution = session.query(Execution).filter_by(id=execution_id).first()
                config = session.query(Configuration).filter_by(id=execution.config_id).first() if execution else None
                pipeline_type = config.pipeline_type if config else None
                pid = execution.process_pid if execution else None
                if config and pipeline_type == "pg_replication":
                    postgres_replication_service.stop(config)
                    return True
            if not proc:
                if not pid:
                    logger.warning("No process for execution %s", execution_id)
                    return False
                proc = psutil.Process(pid)
                command = " ".join(proc.cmdline()).lower()
                if not any(token in command for token in ("pgsync", "backend.workers.pg_copy", "backend.workers.clickhouse_sync")):
                    logger.warning("Refusing to stop PID %s because it no longer matches execution %s", pid, execution_id)
                    return False
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except psutil.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                return True
            if proc.poll() is not None:
                return True
            proc.terminate()
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:
            logger.exception("Failed to stop execution %s", execution_id)
            return False
        return True

    def get_process_status(self, execution_id: int) -> Optional[str]:
        proc = self.processes.get(execution_id)
        if proc:
            if proc.poll() is None:
                return "running"
            return "completed" if proc.returncode == 0 else "failed"
        try:
            with db.get_session() as session:
                execution = session.query(Execution).filter_by(id=execution_id).first()
                pid = execution.process_pid if execution else None
        except RuntimeError:
            return None
        if not pid:
            return None
        try:
            process = psutil.Process(pid)
            command = " ".join(process.cmdline()).lower()
            if process.is_running() and any(
                token in command for token in ("pgsync", "backend.workers.pg_copy", "backend.workers.clickhouse_sync")
            ):
                return "running"
        except psutil.NoSuchProcess:
            pass
        return "failed"

    def get_process_info(self, pid: int) -> Optional[Dict[str, Any]]:
        try:
            process = psutil.Process(pid)
            return {
                "pid": pid,
                "cpu_percent": process.cpu_percent(interval=0.1),
                "memory_mb": process.memory_info().rss / 1024 / 1024,
                "status": process.status(),
            }
        except psutil.NoSuchProcess:
            return None


orchestrator = ExecutionOrchestrator()
