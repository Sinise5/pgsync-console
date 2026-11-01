"""Audit log query API routes."""

import json
import logging
from datetime import datetime, timedelta
from robyn import Request, Response

from backend.db import db
from backend.models import AuditLog

logger = logging.getLogger(__name__)


def audit_routes(app):
    """Register audit log routes."""

    @app.get("/api/audit/logs")
    async def list_audit_logs(request: Request) -> Response:
        """List audit logs with optional filters."""
        try:
            # Parse query params
            params = request.query_params
            limit = int(params.get("limit", 100))
            offset = int(params.get("offset", 0))
            user_id = params.get("user_id")
            resource_type = params.get("resource_type")
            action = params.get("action")
            days = int(params.get("days", 7))

            with db.get_session() as session:
                query = session.query(AuditLog)

                # Apply filters
                if user_id:
                    query = query.filter(AuditLog.user_id == int(user_id))
                if resource_type:
                    query = query.filter(AuditLog.resource_type == resource_type)
                if action:
                    query = query.filter(AuditLog.action == action)

                # Date filter
                cutoff = datetime.utcnow() - timedelta(days=days)
                query = query.filter(AuditLog.timestamp >= cutoff)

                # Order and paginate
                logs = (
                    query.order_by(AuditLog.timestamp.desc())
                    .limit(limit)
                    .offset(offset)
                    .all()
                )
                total = query.count()

                return Response(
                    status_code=200,
                    body=json.dumps({
                        "logs": [log.to_dict() for log in logs],
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                    }),
                )

        except Exception as e:
            logger.error(f"Failed to list audit logs: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.get("/api/audit/logs/:id")
    async def get_audit_log(request: Request) -> Response:
        """Get single audit log entry."""
        try:
            log_id = int(request.path_params.get("id"))

            with db.get_session() as session:
                log = session.query(AuditLog).filter_by(id=log_id).first()
                if not log:
                    return Response(
                        status_code=404,
                        body=json.dumps({"error": "Audit log not found"}),
                    )

                return Response(
                    status_code=200,
                    body=json.dumps(log.to_dict()),
                )

        except Exception as e:
            logger.error(f"Failed to get audit log: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.get("/api/audit/stats")
    async def get_audit_stats(request: Request) -> Response:
        """Get audit log statistics."""
        try:
            params = request.query_params
            days = int(params.get("days", 7))

            with db.get_session() as session:
                cutoff = datetime.utcnow() - timedelta(days=days)
                logs = session.query(AuditLog).filter(AuditLog.timestamp >= cutoff).all()

                # Aggregate stats
                stats = {
                    "total_events": len(logs),
                    "by_action": {},
                    "by_resource": {},
                    "by_user": {},
                    "by_status": {},
                }

                for log in logs:
                    # By action
                    stats["by_action"][log.action] = stats["by_action"].get(log.action, 0) + 1

                    # By resource
                    stats["by_resource"][log.resource_type] = (
                        stats["by_resource"].get(log.resource_type, 0) + 1
                    )

                    # By user
                    user_key = log.username or "unknown"
                    stats["by_user"][user_key] = stats["by_user"].get(user_key, 0) + 1

                    # By status
                    stats["by_status"][log.status] = stats["by_status"].get(log.status, 0) + 1

                return Response(
                    status_code=200,
                    body=json.dumps(stats),
                )

        except Exception as e:
            logger.error(f"Failed to get audit stats: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.get("/api/audit/timeline")
    async def get_audit_timeline(request: Request) -> Response:
        """Get audit activity timeline (events per hour)."""
        try:
            params = request.query_params
            hours = int(params.get("hours", 24))

            with db.get_session() as session:
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                logs = session.query(AuditLog).filter(AuditLog.timestamp >= cutoff).all()

                # Group by hour
                timeline = {}
                for log in logs:
                    hour_key = log.timestamp.strftime("%Y-%m-%d %H:00")
                    timeline[hour_key] = timeline.get(hour_key, 0) + 1

                # Fill missing hours with 0
                result = []
                for i in range(hours):
                    hour = datetime.utcnow() - timedelta(hours=i)
                    hour_key = hour.strftime("%Y-%m-%d %H:00")
                    result.append({
                        "hour": hour_key,
                        "count": timeline.get(hour_key, 0),
                    })

                result.reverse()

                return Response(
                    status_code=200,
                    body=json.dumps({"timeline": result}),
                )

        except Exception as e:
            logger.error(f"Failed to get audit timeline: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))
