"""Error recovery and failure management routes."""

import json
import logging
from robyn import Request, Response

from backend.services.error_recovery_service import error_recovery_service

logger = logging.getLogger(__name__)


def error_recovery_routes(app):
    """Register error recovery routes."""

    @app.get("/api/failures")
    async def list_failures(request: Request) -> Response:
        """List execution failures."""
        try:
            status = request.query_params.get("status", None)
            limit = max(1, min(int(request.query_params.get("limit", "100")), 1000))

            failures = error_recovery_service.get_failures(status=status, limit=limit)

            return Response(
                status_code=200,
                body=json.dumps({"failures": failures}),
            )
        except ValueError:
            return Response(status_code=400, body=json.dumps({"error": "limit must be an integer"}))
        except Exception as e:
            logger.error(f"Failed to list failures: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.get("/api/failures/:failure_id")
    async def get_failure(request: Request) -> Response:
        """Get failure details."""
        try:
            failure_id = int(request.path_params.get("failure_id", 0))
            failure = error_recovery_service.get_failure(failure_id)

            if not failure:
                return Response(
                    status_code=404,
                    body=json.dumps({"error": "Failure not found"}),
                )

            return Response(
                status_code=200,
                body=json.dumps({"failure": failure}),
            )
        except Exception as e:
            logger.error(f"Failed to get failure: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/failures/:failure_id/retry")
    async def retry_failure(request: Request) -> Response:
        """Schedule an execution retry with the requested backoff policy."""
        try:
            failure_id = int(request.path_params.get("failure_id", 0))
            body = json.loads(request.body or "{}")
            strategy = body.get("strategy", "exponential_backoff")
            scheduled = error_recovery_service.schedule_retry(failure_id, strategy)
            if not scheduled:
                failure = error_recovery_service.get_failure(failure_id)
                if not failure:
                    return Response(status_code=404, body=json.dumps({"error": "Failure not found"}))
                return Response(
                    status_code=409,
                    body=json.dumps({
                        "error": "Failure cannot be retried; check its retryability, retry limit, and generated configuration schema",
                    }),
                )
            return Response(
                status_code=202,
                body=json.dumps({"message": "Retry scheduled", "failure_id": failure_id}),
            )
        except ValueError as e:
            return Response(status_code=400, body=json.dumps({"error": str(e)}))
        except Exception as e:
            logger.error(f"Failed to schedule retry: {e}")
            return Response(status_code=500, body=json.dumps({"error": "Retry could not be scheduled"}))

    @app.post("/api/failures/:failure_id/acknowledge")
    async def acknowledge_failure(request: Request) -> Response:
        """Mark failure as resolved."""
        try:
            failure_id = int(request.path_params.get("failure_id", 0))
            body = json.loads(request.body or "{}")
            notes = body.get("notes", "")

            success = error_recovery_service.acknowledge_failure(failure_id, notes)

            if not success:
                return Response(
                    status_code=404,
                    body=json.dumps({"error": "Failure not found"}),
                )

            return Response(
                status_code=200,
                body=json.dumps({"message": "Failure acknowledged"}),
            )
        except Exception as e:
            logger.error(f"Failed to acknowledge failure: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.get("/api/failures/stats")
    async def failure_stats(request: Request) -> Response:
        """Get failure statistics."""
        try:
            all_failures = error_recovery_service.get_failures(limit=1000)

            stats = {
                "total": len(all_failures),
                "pending": sum(1 for f in all_failures if f["status"] == "pending"),
                "retrying": sum(1 for f in all_failures if f["status"] == "retrying"),
                "dead_letter": sum(1 for f in all_failures if f["status"] == "dead_letter"),
                "resolved": sum(1 for f in all_failures if f["status"] == "resolved"),
                "by_error_type": {},
            }

            for failure in all_failures:
                error_type = failure["error_type"]
                stats["by_error_type"][error_type] = stats["by_error_type"].get(error_type, 0) + 1

            return Response(
                status_code=200,
                body=json.dumps({"stats": stats}),
            )
        except Exception as e:
            logger.error(f"Failed to get failure stats: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )
