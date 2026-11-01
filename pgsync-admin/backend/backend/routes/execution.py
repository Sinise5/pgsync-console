"""Execution management API routes."""

import json
import logging
from typing import Any
from datetime import datetime
from robyn import Request, Response

from backend.db import db
from backend.models import Configuration, Execution
from backend.services.execution_orchestrator import orchestrator
from backend.services.clickhouse_client import clickhouse_client

logger = logging.getLogger(__name__)


def execution_routes(app: Any) -> None:
    """Register execution management routes."""

    @app.get("/api/execution")
    async def list_executions(request: Request) -> Response:
        """List all executions with basic info."""
        try:
            with db.get_session() as session:
                executions = (
                    session.query(Execution)
                    .order_by(Execution.started_at.desc())
                    .limit(50)
                    .all()
                )

                results = []
                for exec in executions:
                    process_status = orchestrator.get_process_status(exec.id)
                    if process_status and process_status != exec.status:
                        exec.status = process_status
                        if process_status in {"completed", "failed", "stopped"}:
                            exec.completed_at = datetime.utcnow()
                    # Get config name
                    config = session.query(Configuration).filter_by(id=exec.config_id).first()
                    results.append({
                        "id": exec.id,
                        "config_id": exec.config_id,
                        "config_name": config.name if config else "Unknown",
                        "type": exec.execution_type,
                        "status": exec.status,
                        "pid": exec.pid,
                        "started_at": exec.started_at.isoformat() if exec.started_at else None,
                        "completed_at": exec.completed_at.isoformat() if exec.completed_at else None,
                        "error_message": exec.error_message,
                        "rows_processed": exec.rows_processed or 0,
                    })

                session.commit()

                return Response(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    body=json.dumps({"executions": results}),
                )
        except Exception as e:
            logger.error(f"List executions error: {e}")
            return Response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/execution/batch")
    async def start_batch_migration(request: Request) -> Response:
        """Start batch migration for a configuration.

        POST /api/execution/batch
        {
            "config_id": 1,
            "pgsync_schema": { ... }
        }
        """
        try:
            body = json.loads(request.body)
            config_id = body.get("config_id")
            pgsync_schema = body.get("pgsync_schema")

            if not config_id:
                return Response(
                    status_code=400,
                    body=json.dumps({"error": "config_id required"}),
                )

            session = db.get_session()
            try:
                # Create execution record
                execution = Execution(
                    config_id=config_id,
                    execution_type="batch",
                    status="pending",
                )
                session.add(execution)
                session.commit()
                session.refresh(execution)

                # Start orchestration
                try:
                    pid = orchestrator.start_batch_migration(execution.id, config_id, pgsync_schema)
                except Exception as exc:
                    execution.status = "failed"
                    execution.error_message = str(exc)
                    execution.completed_at = datetime.utcnow()
                    session.commit()
                    raise

                return Response(
                    status_code=200,
                    body=json.dumps({
                        "execution_id": execution.id,
                        "pid": pid,
                        "status": "running",
                    }),
                )
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to start batch migration: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/execution/cdc")
    async def start_cdc_process(request: Request) -> Response:
        """Start CDC process for a configuration.

        POST /api/execution/cdc
        {
            "config_id": 1,
            "pgsync_schema": { ... }
        }
        """
        try:
            body = json.loads(request.body)
            config_id = body.get("config_id")
            pgsync_schema = body.get("pgsync_schema")

            if not config_id:
                return Response(
                    status_code=400,
                    body=json.dumps({"error": "config_id required"}),
                )

            session = db.get_session()
            try:
                execution = Execution(
                    config_id=config_id,
                    execution_type="cdc",
                    status="pending",
                )
                session.add(execution)
                session.commit()
                session.refresh(execution)

                try:
                    pid = orchestrator.start_cdc_process(execution.id, config_id, pgsync_schema)
                except Exception as exc:
                    execution.status = "failed"
                    execution.error_message = str(exc)
                    execution.completed_at = datetime.utcnow()
                    session.commit()
                    raise

                return Response(
                    status_code=200,
                    body=json.dumps({
                        "execution_id": execution.id,
                        "pid": pid,
                        "status": "running",
                    }),
                )
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to start CDC process: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/execution/:execution_id/stop")
    async def stop_execution(request: Request) -> Response:
        """Stop running execution.

        POST /api/execution/{execution_id}/stop
        """
        try:
            execution_id = int(request.path_params.get("execution_id", 0))

            if orchestrator.stop_process(execution_id):
                session = db.get_session()
                try:
                    execution = session.query(Execution).filter(
                        Execution.id == execution_id
                    ).first()

                    if execution:
                        execution.status = "stopped"
                        session.commit()
                finally:
                    session.close()

                return Response(
                    status_code=200,
                    body=json.dumps({"status": "stopped"}),
                )
            else:
                return Response(
                    status_code=404,
                    body=json.dumps({"error": "Execution not found"}),
                )

        except Exception as e:
            logger.error(f"Failed to stop execution: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.get("/api/execution/:execution_id/status")
    async def get_execution_status(request: Request) -> Response:
        """Get execution status and metrics.

        GET /api/execution/{execution_id}/status
        """
        try:
            execution_id = int(request.path_params.get("execution_id", 0))

            session = db.get_session()
            try:
                execution = session.query(Execution).filter(
                    Execution.id == execution_id
                ).first()

                if not execution:
                    return Response(
                        status_code=404,
                        body=json.dumps({"error": "Execution not found"}),
                    )

                status = orchestrator.get_process_status(execution_id)
                process_info = None

                if execution.process_pid:
                    process_info = orchestrator.get_process_info(execution.process_pid)

                return Response(
                    status_code=200,
                    body=json.dumps({
                        "id": execution.id,
                        "config_id": execution.config_id,
                        "type": execution.execution_type,
                        "status": status or execution.status,
                        "pid": execution.process_pid,
                        "started_at": execution.started_at.isoformat() if execution.started_at else None,
                        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                        "process_info": process_info,
                    }),
                )
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to get execution status: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )
