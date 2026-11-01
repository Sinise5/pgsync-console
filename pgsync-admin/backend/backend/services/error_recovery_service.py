"""Error recovery and resilience service."""

import logging
import asyncio
import json
import threading
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum

from backend.db import db
from backend.models import ExecutionFailure, Execution, Job, Configuration
from backend.services.execution_orchestrator import orchestrator

logger = logging.getLogger(__name__)


class ErrorType(str, Enum):
    """Categorized error types."""
    CONNECTION_ERROR = "ConnectionError"
    TIMEOUT_ERROR = "TimeoutError"
    SCHEMA_ERROR = "SchemaError"
    PERMISSION_ERROR = "PermissionError"
    UNKNOWN_ERROR = "UnknownError"


class RecoveryStrategy(str, Enum):
    """Recovery strategies for different error types."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    IMMEDIATE_RETRY = "immediate_retry"
    MANUAL_RECOVERY = "manual_recovery"


class ErrorRecoveryService:
    """Manage execution failures and recovery strategies."""

    def __init__(self):
        self.retry_tasks: Dict[int, asyncio.Task] = {}
        self.retry_timers: Dict[int, threading.Timer] = {}

    async def record_failure(
        self,
        execution_id: int,
        job_id: Optional[int],
        config_id: int,
        error: Exception,
        max_retries: int = 3,
    ) -> ExecutionFailure:
        """Record an execution failure."""
        try:
            error_type = self._categorize_error(error)
            failure = ExecutionFailure(
                execution_id=execution_id,
                job_id=job_id,
                config_id=config_id,
                error_type=error_type.value,
                error_message=str(error),
                error_traceback=traceback.format_exc(),
                max_retries=max_retries,
                is_retriable=self._is_retriable(error_type),
                status="pending" if self._is_retriable(error_type) else "dead_letter",
            )

            with db.get_session() as session:
                session.add(failure)
                session.commit()
                session.refresh(failure)
                logger.info(f"Recorded failure for execution {execution_id}: {error_type.value}")
                return failure
        except Exception as e:
            logger.error(f"Failed to record failure: {e}")
            raise

    def _categorize_error(self, error: Exception) -> ErrorType:
        """Categorize error by type."""
        error_name = type(error).__name__
        if "Connection" in error_name:
            return ErrorType.CONNECTION_ERROR
        elif "Timeout" in error_name:
            return ErrorType.TIMEOUT_ERROR
        elif "Schema" in error_name:
            return ErrorType.SCHEMA_ERROR
        elif "Permission" in error_name or "Unauthorized" in error_name:
            return ErrorType.PERMISSION_ERROR
        return ErrorType.UNKNOWN_ERROR

    def _is_retriable(self, error_type: ErrorType) -> bool:
        """Determine if error type is retriable."""
        non_retriable = {ErrorType.PERMISSION_ERROR, ErrorType.SCHEMA_ERROR}
        return error_type not in non_retriable

    def schedule_retry(
        self,
        failure_id: int,
        strategy: RecoveryStrategy | str = RecoveryStrategy.EXPONENTIAL_BACKOFF,
    ) -> bool:
        """Schedule a real execution retry using a timer safe for scheduler threads."""
        try:
            strategy = RecoveryStrategy(strategy)
            if strategy == RecoveryStrategy.MANUAL_RECOVERY:
                raise ValueError("manual_recovery cannot be scheduled")
            with db.get_session() as session:
                failure = session.query(ExecutionFailure).filter_by(id=failure_id).first()
                if not failure or not failure.is_retriable:
                    return False
                config = session.query(Configuration).filter_by(id=failure.config_id).first()
                if not config or not config.is_active or not config.pgsync_schema_json:
                    return False
                if failure.status == "retrying" and failure_id in self.retry_timers:
                    return False
                if failure.attempt_number >= failure.max_retries:
                    failure.status = "dead_letter"
                    session.commit()
                    return False

                delay = self._calculate_backoff(failure.attempt_number, strategy)
                failure.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
                failure.status = "retrying"
                session.commit()

            timer = threading.Timer(delay, self._retry_after_delay, args=(failure_id, strategy))
            timer.daemon = True
            self.retry_timers[failure_id] = timer
            timer.start()
            logger.info("Scheduled retry for failure %s in %ss", failure_id, delay)
            return True
        except ValueError:
            raise
        except Exception:
            logger.exception("Failed to schedule retry for failure %s", failure_id)
            return False

    def _calculate_backoff(self, attempt: int, strategy: RecoveryStrategy) -> int:
        """Calculate backoff time in seconds."""
        if strategy == RecoveryStrategy.EXPONENTIAL_BACKOFF:
            return min(2 ** (attempt - 1) * 60, 3600)  # Cap at 1 hour
        elif strategy == RecoveryStrategy.LINEAR_BACKOFF:
            return attempt * 300  # 5 min increments
        else:
            return 0  # Immediate

    def _retry_after_delay(self, failure_id: int, strategy: RecoveryStrategy):
        """Retry after delay."""
        self.retry_timers.pop(failure_id, None)
        succeeded = self.attempt_recovery(failure_id)
        if not succeeded:
            with db.get_session() as session:
                failure = session.query(ExecutionFailure).filter_by(id=failure_id).first()
                if failure and failure.status == "pending" and failure.attempt_number < failure.max_retries:
                    self.schedule_retry(failure_id, strategy)

    def attempt_recovery(self, failure_id: int) -> bool:
        """Create and start a new batch or CDC execution for a failure."""
        try:
            with db.get_session() as session:
                failure = session.query(ExecutionFailure).filter(ExecutionFailure.id == failure_id).first()
                if not failure or not failure.is_retriable:
                    return False
                if failure.attempt_number >= failure.max_retries:
                    failure.status = "dead_letter"
                    session.commit()
                    return False

                config = session.query(Configuration).filter_by(id=failure.config_id).first()
                original = session.query(Execution).filter_by(id=failure.execution_id).first()
                job = session.query(Job).filter_by(id=failure.job_id).first() if failure.job_id else None
                schema_json = config.pgsync_schema_json if config else None
                if not config or not config.is_active or not schema_json:
                    failure.status = "dead_letter"
                    failure.recovery_notes = "Retry requires an active configuration with a generated PGSync schema."
                    session.commit()
                    return False
                execution_type = job.execution_type if job else (original.type if original else "batch")
                try:
                    schema = json.loads(schema_json)
                except (TypeError, json.JSONDecodeError):
                    failure.status = "dead_letter"
                    failure.recovery_notes = "Stored PGSync schema is invalid JSON."
                    session.commit()
                    return False

                retry_execution = Execution(
                    config_id=config.id,
                    type=execution_type,
                    status="pending",
                )
                session.add(retry_execution)
                session.flush()
                failure.attempt_number += 1
                failure.status = "retrying"
                failure.next_retry_at = None
                failure.recovery_notes = f"Started retry execution {retry_execution.id}."
                retry_execution_id = retry_execution.id
                config_id = config.id
                session.commit()

            if execution_type == "batch":
                orchestrator.start_batch_migration(retry_execution_id, config_id, schema)
            elif execution_type == "cdc":
                orchestrator.start_cdc_process(retry_execution_id, config_id, schema)
            else:
                raise ValueError(f"Unsupported execution type: {execution_type}")

            monitor = threading.Timer(5, self._check_retry_result, args=(failure_id, retry_execution_id))
            monitor.daemon = True
            self.retry_timers[failure_id] = monitor
            monitor.start()
            return True
        except Exception as e:
            logger.exception("Recovery attempt failed for failure %s", failure_id)
            with db.get_session() as session:
                failure = session.query(ExecutionFailure).filter_by(id=failure_id).first()
                retry_execution = session.query(Execution).filter_by(id=retry_execution_id).first() if "retry_execution_id" in locals() else None
                if retry_execution:
                    retry_execution.status = "failed"
                    retry_execution.error_message = str(e)
                    retry_execution.completed_at = datetime.utcnow()
                if failure:
                    failure.status = "pending" if failure.attempt_number < failure.max_retries else "dead_letter"
                    failure.recovery_notes = str(e)
                session.commit()
            return False

    def _check_retry_result(self, failure_id: int, execution_id: int) -> None:
        """Resolve a retry after a batch exits or leave a healthy CDC process running."""
        status = orchestrator.get_process_status(execution_id)
        with db.get_session() as session:
            failure = session.query(ExecutionFailure).filter_by(id=failure_id).first()
            execution = session.query(Execution).filter_by(id=execution_id).first()
            if not failure or not execution:
                return
            if status == "completed" or (status == "running" and execution.type == "cdc"):
                failure.status = "resolved"
                failure.recovered_at = datetime.utcnow()
                failure.recovery_notes = f"Recovered by execution {execution_id}."
                session.commit()
                self.retry_timers.pop(failure_id, None)
                return
            if status == "failed":
                failure.status = "pending" if failure.attempt_number < failure.max_retries else "dead_letter"
                failure.recovery_notes = f"Retry execution {execution_id} failed."
                session.commit()
                strategy = RecoveryStrategy.EXPONENTIAL_BACKOFF
                should_retry = failure.status == "pending"
                should_monitor = False
            else:
                should_retry = False
                should_monitor = status == "running" and execution.type == "batch"
        if should_retry:
            self.schedule_retry(failure_id, strategy)
        elif should_monitor:
            monitor = threading.Timer(5, self._check_retry_result, args=(failure_id, execution_id))
            monitor.daemon = True
            self.retry_timers[failure_id] = monitor
            monitor.start()

    def get_failures(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get failures by status."""
        try:
            with db.get_session() as session:
                query = session.query(ExecutionFailure)
                if status:
                    query = query.filter(ExecutionFailure.status == status)
                failures = query.order_by(ExecutionFailure.created_at.desc()).limit(limit).all()
                return [f.to_dict() for f in failures]
        except Exception as e:
            logger.error(f"Failed to get failures: {e}")
            return []

    def get_failure(self, failure_id: int) -> Optional[Dict[str, Any]]:
        """Get one failure by its identifier."""
        try:
            with db.get_session() as session:
                failure = session.query(ExecutionFailure).filter_by(id=failure_id).first()
                return failure.to_dict() if failure else None
        except Exception:
            logger.exception("Failed to get failure %s", failure_id)
            return None

    def acknowledge_failure(self, failure_id: int, notes: str = "") -> bool:
        """Mark failure as manually acknowledged/resolved."""
        try:
            timer = self.retry_timers.pop(failure_id, None)
            if timer:
                timer.cancel()
            with db.get_session() as session:
                failure = session.query(ExecutionFailure).filter(ExecutionFailure.id == failure_id).first()
                if not failure:
                    return False
                failure.status = "resolved"
                failure.recovered_at = datetime.utcnow()
                failure.recovery_notes = notes
                session.commit()
                logger.info(f"Failure {failure_id} marked as resolved")
                return True
        except Exception as e:
            logger.error(f"Failed to acknowledge failure: {e}")
            return False


import traceback

# Singleton
error_recovery_service = ErrorRecoveryService()
