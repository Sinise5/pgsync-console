"""Workflow and job dependency API routes."""

import json
import logging
from robyn import Request, Response

from backend.db import db
from backend.models.workflow import JobDependency, WorkflowTemplate
from backend.services.workflow_engine import workflow_engine

logger = logging.getLogger(__name__)


def workflow_routes(app):
    """Register workflow management routes."""

    @app.post("/api/workflows/dependencies")
    async def add_dependency(request: Request) -> Response:
        """Add job dependency edge."""
        try:
            payload = json.loads(request.body)
            parent_id = payload["parent_job_id"]
            child_id = payload["child_job_id"]
            condition = payload.get("condition", "on_success")

            success = workflow_engine.add_dependency(parent_id, child_id, condition)
            if success:
                return Response(
                    status_code=201,
                    body=json.dumps(
                        {
                            "status": "success",
                            "message": f"Dependency added: {parent_id} -> {child_id}",
                        }
                    ),
                )
            else:
                return Response(
                    status_code=400,
                    body=json.dumps(
                        {
                            "status": "error",
                            "message": "Failed to add dependency (cycle detected?)",
                        }
                    ),
                )
        except Exception as e:
            logger.error(f"Error adding dependency: {e}")
            return Response(
                status_code=400,
                body=json.dumps({"status": "error", "message": str(e)}),
            )

    @app.delete("/api/workflows/dependencies")
    async def remove_dependency(request: Request) -> Response:
        """Remove job dependency edge."""
        try:
            payload = json.loads(request.body)
            parent_id = payload["parent_job_id"]
            child_id = payload["child_job_id"]

            success = workflow_engine.remove_dependency(parent_id, child_id)
            if success:
                return Response(
                    status_code=200,
                    body=json.dumps(
                        {
                            "status": "success",
                            "message": f"Dependency removed: {parent_id} -> {child_id}",
                        }
                    ),
                )
            else:
                return Response(
                    status_code=404,
                    body=json.dumps(
                        {
                            "status": "error",
                            "message": "Dependency not found",
                        }
                    ),
                )
        except Exception as e:
            logger.error(f"Error removing dependency: {e}")
            return Response(
                status_code=400,
                body=json.dumps({"status": "error", "message": str(e)}),
            )

    @app.post("/api/workflows/validate")
    async def validate_dag(request: Request) -> Response:
        """Validate workflow DAG (check for cycles)."""
        try:
            payload = json.loads(request.body)
            job_ids = payload["job_ids"]

            validation = workflow_engine.validate_dag(job_ids)
            status_code = 200 if validation["valid"] else 400

            return Response(
                status_code=status_code,
                body=json.dumps(
                    {
                        "status": "success" if validation["valid"] else "error",
                        "data": validation,
                    }
                ),
            )
        except Exception as e:
            logger.error(f"Error validating DAG: {e}")
            return Response(
                status_code=400,
                body=json.dumps({"status": "error", "message": str(e)}),
            )

    @app.get("/api/workflows/:workflow_id/execution-order")
    async def get_execution_order(request: Request) -> Response:
        """Get topological sort of jobs in workflow."""
        try:
            workflow_id = int(request.path_params["workflow_id"])

            # Get all job IDs in workflow
            from backend.models.job import Job
            session = db.get_session()
            jobs = session.query(Job).filter_by(workflow_id=workflow_id).all()
            job_ids = [j.id for j in jobs]

            sorted_jobs = workflow_engine.topological_sort(job_ids)
            if sorted_jobs is None:
                return Response(
                    status_code=400,
                    body=json.dumps(
                        {
                            "status": "error",
                            "message": "Cycle detected in workflow",
                        }
                    ),
                )

            return Response(
                status_code=200,
                body=json.dumps(
                    {
                        "status": "success",
                        "data": {
                            "workflow_id": workflow_id,
                            "execution_order": sorted_jobs,
                        },
                    }
                ),
            )
        except Exception as e:
            logger.error(f"Error getting execution order: {e}")
            return Response(
                status_code=400,
                body=json.dumps({"status": "error", "message": str(e)}),
            )

    @app.get("/api/workflows/templates")
    async def list_templates(request: Request) -> Response:
        """List workflow templates."""
        try:
            session = db.get_session()
            templates = session.query(WorkflowTemplate).all()
            return Response(
                status_code=200,
                body=json.dumps(
                    {
                        "status": "success",
                        "data": [t.to_dict() for t in templates],
                    }
                ),
            )
        except Exception as e:
            logger.error(f"Error listing templates: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"status": "error", "message": str(e)}),
            )

    @app.post("/api/workflows/templates")
    async def create_template(request: Request) -> Response:
        """Create workflow template."""
        try:
            payload = json.loads(request.body)
            template = WorkflowTemplate(
                name=payload["name"],
                description=payload.get("description"),
                dag_config=json.dumps(payload["dag_config"]),
                created_by=payload.get("created_by", "system"),
            )
            session = db.get_session()
            session.add(template)
            session.commit()
            session.refresh(template)

            return Response(
                status_code=201,
                body=json.dumps(
                    {
                        "status": "success",
                        "data": template.to_dict(),
                    }
                ),
            )
        except Exception as e:
            logger.error(f"Error creating template: {e}")
            return Response(
                status_code=400,
                body=json.dumps({"status": "error", "message": str(e)}),
            )
