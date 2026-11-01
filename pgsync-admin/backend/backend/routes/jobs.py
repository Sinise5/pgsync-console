"""Job scheduling API routes."""

import json
import logging
from typing import Optional
from robyn import Request, Response

from backend.db import db
from backend.models import Job, Configuration
from backend.services.scheduler_service import scheduler_service

logger = logging.getLogger(__name__)


def jobs_routes(app):
    """Register job management routes."""

    @app.get("/api/jobs")
    async def list_jobs(request: Request) -> Response:
        """List all scheduled jobs."""
        try:
            config_id = request.query_params.get("config_id", None)
            jobs = scheduler_service.list_jobs(
                config_id=int(config_id) if config_id else None
            )
            return Response(
                status_code=200,
                body=json.dumps({"jobs": jobs}),
            )
        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.get("/api/jobs/:job_id")
    async def get_job(request: Request) -> Response:
        """Get job details."""
        try:
            job_id = int(request.path_params.get("job_id", 0))
            job = scheduler_service.get_job(job_id)
            if not job:
                return Response(
                    status_code=404,
                    body=json.dumps({"error": "Job not found"}),
                )
            return Response(
                status_code=200,
                body=json.dumps({"job": job}),
            )
        except Exception as e:
            logger.error(f"Failed to get job: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/jobs")
    async def create_job(request: Request) -> Response:
        """Create a new scheduled job."""
        try:
            body = json.loads(request.body)
            name = body.get("name")
            config_id = body.get("config_id")
            cron_expression = body.get("cron_expression")

            if not all([name, config_id, cron_expression]):
                return Response(
                    status_code=400,
                    body=json.dumps({"error": "Missing required fields"}),
                )

            job = scheduler_service.create_job(
                name=name,
                config_id=config_id,
                cron_expr=cron_expression,
                timezone=body.get("timezone", "UTC"),
                execution_type=body.get("execution_type", "batch"),
                retry_on_failure=body.get("retry_on_failure", True),
                max_retries=body.get("max_retries", 3),
                timeout_seconds=body.get("timeout_seconds", 3600),
                notifications=body.get("notifications", []),
                notify_on_success=body.get("notify_on_success", False),
                notify_on_failure=body.get("notify_on_failure", True),
            )

            return Response(
                status_code=201,
                body=json.dumps({"job": job.to_dict()}),
            )
        except ValueError as e:
            return Response(status_code=400, body=json.dumps({"error": str(e)}))
        except Exception as e:
            logger.error(f"Failed to create job: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.patch("/api/jobs/:job_id")
    async def update_job(request: Request) -> Response:
        """Update a job configuration."""
        try:
            job_id = int(request.path_params.get("job_id", 0))
            body = json.loads(request.body)

            job = scheduler_service.update_job(job_id, **body)
            if not job:
                return Response(
                    status_code=404,
                    body=json.dumps({"error": "Job not found"}),
                )

            return Response(
                status_code=200,
                body=json.dumps({"job": job.to_dict()}),
            )
        except ValueError as e:
            return Response(status_code=400, body=json.dumps({"error": str(e)}))
        except Exception as e:
            logger.error(f"Failed to update job: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.delete("/api/jobs/:job_id")
    async def delete_job(request: Request) -> Response:
        """Delete a scheduled job."""
        try:
            job_id = int(request.path_params.get("job_id", 0))
            success = scheduler_service.delete_job(job_id)

            if not success:
                return Response(
                    status_code=404,
                    body=json.dumps({"error": "Job not found"}),
                )

            return Response(
                status_code=200,
                body=json.dumps({"message": "Job deleted"}),
            )
        except Exception as e:
            logger.error(f"Failed to delete job: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/jobs/:job_id/pause")
    async def pause_job(request: Request) -> Response:
        """Pause (disable) a job."""
        try:
            job_id = int(request.path_params.get("job_id", 0))
            success = scheduler_service.pause_job(job_id)

            if not success:
                return Response(
                    status_code=404,
                    body=json.dumps({"error": "Job not found"}),
                )

            return Response(
                status_code=200,
                body=json.dumps({"message": "Job paused"}),
            )
        except Exception as e:
            logger.error(f"Failed to pause job: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/jobs/:job_id/resume")
    async def resume_job(request: Request) -> Response:
        """Resume a paused job."""
        try:
            job_id = int(request.path_params.get("job_id", 0))
            success = scheduler_service.resume_job(job_id)

            if not success:
                return Response(
                    status_code=404,
                    body=json.dumps({"error": "Job not found"}),
                )

            return Response(
                status_code=200,
                body=json.dumps({"message": "Job resumed"}),
            )
        except Exception as e:
            logger.error(f"Failed to resume job: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/jobs/:job_id/run")
    async def trigger_job(request: Request) -> Response:
        """Trigger a job immediately."""
        try:
            job_id = int(request.path_params.get("job_id", 0))
            success = scheduler_service.trigger_now(job_id)

            if not success:
                return Response(
                    status_code=404,
                    body=json.dumps({"error": "Job not found"}),
                )

            return Response(
                status_code=202,
                body=json.dumps({"message": "Job triggered"}),
            )
        except Exception as e:
            logger.error(f"Failed to trigger job: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )
