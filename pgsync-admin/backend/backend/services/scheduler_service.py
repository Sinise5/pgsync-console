"""APScheduler-based job scheduler service."""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from backend.db import db
from backend.models import Job, Execution, Configuration
from backend.services.execution_orchestrator import orchestrator
from backend.services.notification_service import notification_manager, NotificationPayload, NotificationChannel
from backend.services.error_recovery_service import error_recovery_service

logger = logging.getLogger(__name__)


class SchedulerService:
    """Manage scheduled job execution."""

    def __init__(self):
        self.scheduler = BackgroundScheduler(daemon=True)
        self.jobs_map: Dict[int, Any] = {}  # APScheduler job objects
        # NOTE: _load_jobs() called in start() to wait for DB connection

    def start(self):
        """Start the scheduler and load jobs."""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                logger.info("Scheduler started")
                # Load jobs AFTER scheduler running (DB ready)
                self._load_jobs()
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    def _load_jobs(self):
        """Load all enabled jobs from database."""
        try:
            with db.get_session() as session:
                jobs = session.query(Job).filter(Job.enabled == True).all()
                for job in jobs:
                    self._schedule_job(job, session)
                logger.info(f"Loaded {len(jobs)} jobs")
        except Exception as e:
            logger.error(f"Failed to load jobs: {e}")

    def _schedule_job(self, job: Job, session=None):
        """Schedule a single job."""
        try:
            trigger = CronTrigger.from_crontab(job.cron_expression, timezone=job.timezone)
            ap_job = self.scheduler.add_job(
                self._execute_job,
                trigger=trigger,
                args=[job.id],
                id=f"job_{job.id}",
                replace_existing=True,
                max_instances=1,
            )
            self.jobs_map[job.id] = ap_job
            logger.info(f"Scheduled job {job.id}: {job.name}")
        except Exception as e:
            logger.error(f"Failed to schedule job {job.id}: {e}")

    def _execute_job(self, job_id: int):
        """Execute a job and track execution."""
        try:
            with db.get_session() as session:
                job = session.query(Job).filter(Job.id == job_id).first()
                if not job:
                    logger.error(f"Job {job_id} not found")
                    return

                config = session.query(Configuration).filter(Configuration.id == job.config_id).first()
                if not config:
                    logger.error(f"Config {job.config_id} not found")
                    return

                # Create execution record
                execution = Execution(
                    config_id=config.id,
                    execution_type=job.execution_type,
                    status="running",
                )
                session.add(execution)
                session.commit()

                try:
                    # Start execution
                    if job.execution_type == "batch":
                        import json
                        schema = json.loads(config.pgsync_schema_json or "{}")
                        orchestrator.start_batch_migration(execution.id, config.id, schema)
                    elif job.execution_type == "cdc":
                        import json
                        schema = json.loads(config.pgsync_schema_json or "{}")
                        orchestrator.start_cdc_process(execution.id, config.id, schema)

                    # Update job stats
                    job.last_run = datetime.utcnow()
                    job.last_status = "success"
                    job.run_count += 1
                    session.commit()

                    logger.info(f"Job {job_id} executed successfully (execution {execution.id})")

                except Exception as exec_err:
                    logger.error(f"Job {job_id} execution failed: {exec_err}")

                    # Record failure for recovery
                    failure = asyncio.run(
                        error_recovery_service.record_failure(
                            execution_id=execution.id,
                            job_id=job_id,
                            config_id=config.id,
                            error=exec_err,
                            max_retries=job.max_retries,
                        )
                    )
                    if job.retry_on_failure:
                        error_recovery_service.schedule_retry(failure.id)

                    job.last_status = "failure"
                    job.failure_count += 1

                    # Send failure notification
                    if job.notify_on_failure and job.notifications:
                        payload = NotificationPayload(
                            channel=NotificationChannel(job.notifications[0]) if job.notifications else NotificationChannel.WEBHOOK,
                            title=f"Job Failed: {job.name}",
                            message=f"Job execution {execution.id} failed after {job.failure_count} attempts",
                            details={"job_id": job_id, "config_id": config.id, "error": str(exec_err)},
                            severity="error",
                        )
                        asyncio.run(notification_manager.notify(payload))

                    if job.failure_count >= job.max_retries:
                        job.enabled = False
                        logger.warning(f"Job {job_id} disabled after {job.max_retries} failures")
                    session.commit()

        except Exception as e:
            logger.error(f"Error executing job {job_id}: {e}")

    def create_job(self, name: str, config_id: int, cron_expr: str, **kwargs) -> Job:
        """Create a new scheduled job."""
        try:
            timezone = kwargs.get("timezone", "UTC")
            if not name or not name.strip():
                raise ValueError("Job name is required")
            if not isinstance(config_id, int) or config_id < 1:
                raise ValueError("A valid configuration is required")
            if kwargs.get("execution_type", "batch") not in {"batch", "cdc"}:
                raise ValueError("Execution type must be batch or cdc")
            if not 0 <= int(kwargs.get("max_retries", 3)) <= 20:
                raise ValueError("Maximum retries must be between 0 and 20")
            if not 1 <= int(kwargs.get("timeout_seconds", 3600)) <= 86400:
                raise ValueError("Timeout must be between 1 and 86400 seconds")
            try:
                trigger = CronTrigger.from_crontab(cron_expr, timezone=timezone)
            except Exception as e:
                raise ValueError(f"Invalid cron expression or timezone: {e}") from e

            job = Job(
                name=name.strip(),
                config_id=config_id,
                cron_expression=cron_expr,
                **kwargs
            )
            with db.get_session() as session:
                config = session.query(Configuration).filter(
                    Configuration.id == config_id,
                    Configuration.is_active == True,
                ).first()
                if not config:
                    raise ValueError("Active configuration not found")
                execution_type = kwargs.get("execution_type", "batch")
                if config.pipeline_type == "pg_copy" and execution_type != "batch":
                    raise ValueError("PostgreSQL table copy supports batch schedules only")
                if config.pipeline_type == "pg_replication" and execution_type != "cdc":
                    raise ValueError("Continuous PostgreSQL replication supports CDC schedules only")
                session.add(job)
                session.commit()
                session.refresh(job)
                try:
                    self.scheduler.add_job(
                        self._execute_job,
                        trigger=trigger,
                        args=[job.id],
                        id=f"job_{job.id}",
                        replace_existing=True,
                        max_instances=1,
                    )
                    self.jobs_map[job.id] = self.scheduler.get_job(f"job_{job.id}")
                except Exception:
                    session.delete(job)
                    session.commit()
                    raise
                return job
        except Exception as e:
            logger.error(f"Failed to create job: {e}")
            raise

    def update_job(self, job_id: int, **kwargs) -> Optional[Job]:
        """Update a job configuration."""
        try:
            with db.get_session() as session:
                job = session.query(Job).filter(Job.id == job_id).first()
                if not job:
                    return None

                config_id = kwargs.get("config_id", job.config_id)
                execution_type = kwargs.get("execution_type", job.execution_type)
                config = session.query(Configuration).filter(
                    Configuration.id == config_id,
                    Configuration.is_active == True,
                ).first()
                if not config:
                    raise ValueError("Active configuration not found")
                if config.pipeline_type == "pg_copy" and execution_type != "batch":
                    raise ValueError("PostgreSQL table copy supports batch schedules only")
                if config.pipeline_type == "pg_replication" and execution_type != "cdc":
                    raise ValueError("Continuous PostgreSQL replication supports CDC schedules only")

                cron_expression = kwargs.get("cron_expression", job.cron_expression)
                timezone = kwargs.get("timezone", job.timezone)
                if "cron_expression" in kwargs or "timezone" in kwargs:
                    try:
                        CronTrigger.from_crontab(cron_expression, timezone=timezone)
                    except Exception as e:
                        raise ValueError(f"Invalid cron expression or timezone: {e}") from e

                for key, value in kwargs.items():
                    if hasattr(job, key):
                        setattr(job, key, value)

                session.commit()
                session.refresh(job)

                # Reschedule if cron changed
                if "cron_expression" in kwargs or "enabled" in kwargs:
                    if job.id in self.jobs_map:
                        self.scheduler.remove_job(f"job_{job.id}")
                        del self.jobs_map[job.id]
                    if job.enabled:
                        self._schedule_job(job, session)

                return job
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            raise

    def delete_job(self, job_id: int) -> bool:
        """Delete a scheduled job."""
        try:
            if job_id in self.jobs_map:
                self.scheduler.remove_job(f"job_{job_id}")
                del self.jobs_map[job_id]

            with db.get_session() as session:
                job = session.query(Job).filter(Job.id == job_id).first()
                if job:
                    session.delete(job)
                    session.commit()
                    logger.info(f"Job {job_id} deleted")
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            raise

    def get_job(self, job_id: int) -> Optional[Job]:
        """Get a job by ID."""
        try:
            with db.get_session() as session:
                job = session.query(Job).filter(Job.id == job_id).first()
                return job.to_dict() if job else None
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None

    def list_jobs(self, config_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all jobs, optionally filtered by config."""
        try:
            with db.get_session() as session:
                query = session.query(Job)
                if config_id:
                    query = query.filter(Job.config_id == config_id)
                jobs = query.all()
                return [job.to_dict() for job in jobs]
        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            return []

    def pause_job(self, job_id: int) -> bool:
        """Pause a job (disable it)."""
        try:
            return self.update_job(job_id, enabled=False) is not None
        except Exception as e:
            logger.error(f"Failed to pause job {job_id}: {e}")
            return False

    def resume_job(self, job_id: int) -> bool:
        """Resume a paused job."""
        try:
            return self.update_job(job_id, enabled=True) is not None
        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
            return False

    def trigger_now(self, job_id: int) -> bool:
        """Trigger a job immediately."""
        try:
            self._execute_job(job_id)
            return True
        except Exception as e:
            logger.error(f"Failed to trigger job {job_id}: {e}")
            return False


# Singleton
scheduler_service = SchedulerService()
