"""CDC API routes for configured continuous pipelines."""

import json
import logging
from datetime import datetime
from typing import Any

from robyn import Request, Response

from backend.db import db
from backend.models import CDCState, CDCStatus, Configuration, Execution
from backend.services.cdc_service import cdc_service
from backend.services.execution_orchestrator import orchestrator

logger = logging.getLogger(__name__)


def _json(status_code: int, data: dict[str, Any]) -> Response:
    return Response(
        status_code=status_code,
        headers={"Content-Type": "application/json"},
        description=json.dumps(data),
    )


def cdc_routes(app: Any) -> None:
    """Register CDC start, stop, status, and logs routes."""

    @app.post("/api/cdc/:config_id/start")
    async def start_cdc(request: Request) -> Response:
        try:
            config_id = int(request.path_params.get("config_id"))
            with db.get_session() as session:
                config = session.query(Configuration).filter_by(id=config_id, is_active=True).first()
                if not config:
                    return _json(404, {"error": "Configuration not found"})
                if config.pipeline_type == "pg_copy":
                    return _json(400, {"error": "PostgreSQL copy is a batch operation; use Run batch or create a schedule."})

                state = session.query(CDCState).filter_by(config_id=config_id).first()
                if state and state.status in {CDCStatus.STARTING.value, CDCStatus.RUNNING.value, CDCStatus.STOPPING.value}:
                    return _json(200, {"status": "already_running", "config_id": config_id})

                execution = Execution(config_id=config_id, execution_type="cdc", status="pending")
                session.add(execution)
                session.commit()
                session.refresh(execution)
                execution_id = execution.id

            try:
                pid = orchestrator.start_cdc_process(execution_id, config_id)
            except Exception as exc:
                with db.get_session() as session:
                    execution = session.query(Execution).filter_by(id=execution_id).first()
                    if execution:
                        execution.status = "failed"
                        execution.error_message = str(exc)
                        execution.completed_at = datetime.utcnow()
                    state = session.query(CDCState).filter_by(config_id=config_id).first()
                    if not state:
                        state = CDCState(config_id=config_id)
                        session.add(state)
                    state.status = CDCStatus.ERROR.value
                    state.last_error = str(exc)
                    state.last_error_time = datetime.utcnow()
                    state.error_count = (state.error_count or 0) + 1
                    session.commit()
                raise

            with db.get_session() as session:
                state = session.query(CDCState).filter_by(config_id=config_id).first()
                if not state:
                    state = CDCState(config_id=config_id)
                    session.add(state)
                state.status = CDCStatus.RUNNING.value
                state.started_at = datetime.utcnow()
                state.stopped_at = None
                state.last_error = None
                state.error_count = 0
                session.commit()
            if pid is None:
                cdc_service.record_log(config_id, "Started PostgreSQL logical replication subscription")
            return _json(200, {"status": "started", "config_id": config_id, "execution_id": execution_id, "pid": pid})
        except ValueError as exc:
            return _json(400, {"error": str(exc)})
        except Exception as exc:
            logger.exception("Failed to start CDC")
            return _json(500, {"error": str(exc)})

    @app.post("/api/cdc/:config_id/stop")
    async def stop_cdc(request: Request) -> Response:
        try:
            config_id = int(request.path_params.get("config_id"))
            with db.get_session() as session:
                state = session.query(CDCState).filter_by(config_id=config_id).first()
                execution = (
                    session.query(Execution).filter_by(config_id=config_id, execution_type="cdc")
                    .order_by(Execution.id.desc()).first()
                )
                if not state and not execution:
                    return _json(404, {"error": "CDC execution not found"})
                execution_id = execution.id if execution and execution.status in {"pending", "running"} else None

            if execution_id is not None:
                if not orchestrator.stop_process(execution_id):
                    return _json(409, {"error": "Could not stop CDC execution"})
                with db.get_session() as session:
                    execution = session.query(Execution).filter_by(id=execution_id).first()
                    if execution:
                        execution.status = "paused"
                        execution.completed_at = datetime.utcnow()
                    session.commit()
                cdc_service.record_log(config_id, "CDC stop requested and runner stopped")

            with db.get_session() as session:
                state = session.query(CDCState).filter_by(config_id=config_id).first()
                if state:
                    state.status = CDCStatus.STOPPED.value
                    state.stopped_at = datetime.utcnow()
                session.commit()
            return _json(200, {"status": "stopped", "config_id": config_id})
        except ValueError as exc:
            return _json(400, {"error": str(exc)})
        except Exception as exc:
            logger.exception("Failed to stop CDC")
            return _json(500, {"error": str(exc)})

    @app.get("/api/cdc/:config_id/status")
    async def get_cdc_status(request: Request) -> Response:
        try:
            config_id = int(request.path_params.get("config_id"))
            with db.get_session() as session:
                state = session.query(CDCState).filter_by(config_id=config_id).first()
                if not state:
                    return _json(200, {"config_id": config_id, "status": "not_found"})
                execution = (
                    session.query(Execution).filter_by(config_id=config_id, execution_type="cdc")
                    .order_by(Execution.id.desc()).first()
                )
                process_status = orchestrator.get_process_status(execution.id) if execution else None
                if process_status in {"completed", "failed"} and state.status == CDCStatus.RUNNING.value:
                    state.status = CDCStatus.STOPPED.value if process_status == "completed" else CDCStatus.ERROR.value
                    state.stopped_at = datetime.utcnow()
                    if execution:
                        execution.status = process_status
                        execution.completed_at = datetime.utcnow()
                        if process_status == "failed":
                            state.last_error = execution.error_message or "CDC runner exited with an error; inspect recent logs."
                            state.last_error_time = datetime.utcnow()
                            state.error_count = (state.error_count or 0) + 1
                    session.commit()
                result = state.to_dict()
            return _json(200, result)
        except ValueError as exc:
            return _json(400, {"error": str(exc)})
        except Exception as exc:
            logger.exception("Failed to get CDC status")
            return _json(500, {"error": str(exc)})

    @app.get("/api/cdc/:config_id/logs")
    async def get_cdc_logs(request: Request) -> Response:
        try:
            config_id = int(request.path_params.get("config_id"))
            with db.get_session() as session:
                execution = (
                    session.query(Execution).filter_by(config_id=config_id, execution_type="cdc")
                    .order_by(Execution.id.desc()).first()
                )
                execution_id = execution.id if execution else None
            logs = orchestrator.get_process_logs(execution_id) if execution_id else cdc_service.get_logs(config_id)
            if not logs:
                logs = cdc_service.get_logs(config_id)
            return _json(200, {"logs": logs})
        except ValueError as exc:
            return _json(400, {"error": str(exc)})
        except Exception as exc:
            logger.exception("Failed to get CDC logs")
            return _json(500, {"error": str(exc)})
