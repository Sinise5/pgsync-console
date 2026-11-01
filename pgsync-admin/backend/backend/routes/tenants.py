"""Tenant management API routes."""

import json
import logging
from robyn import Request, Response

from backend.db import db
from backend.models.tenant import Tenant
from backend.services.tenant_service import tenant_service

logger = logging.getLogger(__name__)


def tenant_routes(app):
    """Register tenant management routes."""

    @app.get("/api/tenants")
    async def list_tenants(request: Request) -> Response:
        """List all tenants."""
        try:
            status_filter = request.query.get("status")
            tenants = tenant_service.list_tenants(status=status_filter)
            data = [t.to_dict() for t in tenants]
            return Response(
                status_code=200,
                body=json.dumps({"status": "success", "data": data}),
            )
        except Exception as e:
            logger.error(f"Error listing tenants: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"status": "error", "message": str(e)}),
            )

    @app.post("/api/tenants")
    async def create_tenant(request: Request) -> Response:
        """Create new tenant."""
        try:
            payload = json.loads(request.body)
            tenant = tenant_service.create_tenant(
                name=payload["name"],
                display_name=payload.get("display_name", payload["name"]),
                settings=payload.get("settings", {}),
            )
            return Response(
                status_code=201,
                body=json.dumps({"status": "success", "data": tenant.to_dict()}),
            )
        except Exception as e:
            logger.error(f"Error creating tenant: {e}")
            return Response(
                status_code=400,
                body=json.dumps({"status": "error", "message": str(e)}),
            )

    @app.get("/api/tenants/:tenant_id")
    async def get_tenant(request: Request) -> Response:
        """Get tenant by ID."""
        try:
            tenant_id = int(request.path_params["tenant_id"])
            tenant = tenant_service.get_tenant(tenant_id)
            if not tenant:
                return Response(
                    status_code=404,
                    body=json.dumps({"status": "error", "message": "Tenant not found"}),
                )
            return Response(
                status_code=200,
                body=json.dumps({"status": "success", "data": tenant.to_dict()}),
            )
        except Exception as e:
            logger.error(f"Error fetching tenant: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"status": "error", "message": str(e)}),
            )

    @app.put("/api/tenants/:tenant_id")
    async def update_tenant(request: Request) -> Response:
        """Update tenant settings."""
        try:
            tenant_id = int(request.path_params["tenant_id"])
            payload = json.loads(request.body)
            tenant = tenant_service.update_tenant(tenant_id, **payload)
            if not tenant:
                return Response(
                    status_code=404,
                    body=json.dumps({"status": "error", "message": "Tenant not found"}),
                )
            return Response(
                status_code=200,
                body=json.dumps({"status": "success", "data": tenant.to_dict()}),
            )
        except Exception as e:
            logger.error(f"Error updating tenant: {e}")
            return Response(
                status_code=400,
                body=json.dumps({"status": "error", "message": str(e)}),
            )

    @app.post("/api/tenants/:tenant_id/suspend")
    async def suspend_tenant(request: Request) -> Response:
        """Suspend tenant."""
        try:
            tenant_id = int(request.path_params["tenant_id"])
            success = tenant_service.suspend_tenant(tenant_id)
            if not success:
                return Response(
                    status_code=404,
                    body=json.dumps({"status": "error", "message": "Tenant not found"}),
                )
            tenant = tenant_service.get_tenant(tenant_id)
            return Response(
                status_code=200,
                body=json.dumps({"status": "success", "data": tenant.to_dict()}),
            )
        except Exception as e:
            logger.error(f"Error suspending tenant: {e}")
            return Response(
                status_code=400,
                body=json.dumps({"status": "error", "message": str(e)}),
            )

    @app.post("/api/tenants/:tenant_id/activate")
    async def activate_tenant(request: Request) -> Response:
        """Activate tenant."""
        try:
            tenant_id = int(request.path_params["tenant_id"])
            success = tenant_service.activate_tenant(tenant_id)
            if not success:
                return Response(
                    status_code=404,
                    body=json.dumps({"status": "error", "message": "Tenant not found"}),
                )
            tenant = tenant_service.get_tenant(tenant_id)
            return Response(
                status_code=200,
                body=json.dumps({"status": "success", "data": tenant.to_dict()}),
            )
        except Exception as e:
            logger.error(f"Error activating tenant: {e}")
            return Response(
                status_code=400,
                body=json.dumps({"status": "error", "message": str(e)}),
            )

    @app.get("/api/tenants/:tenant_id/quota")
    async def check_quota(request: Request) -> Response:
        """Check tenant quota usage."""
        try:
            tenant_id = int(request.path_params["tenant_id"])
            quota_type = request.query.get("type", "configs")
            current = int(request.query.get("current", 0))

            within_quota = tenant_service.check_quota(tenant_id, quota_type, current)
            return Response(
                status_code=200,
                body=json.dumps(
                    {
                        "status": "success",
                        "data": {
                            "tenant_id": tenant_id,
                            "quota_type": quota_type,
                            "current_usage": current,
                            "within_quota": within_quota,
                        },
                    }
                ),
            )
        except Exception as e:
            logger.error(f"Error checking quota: {e}")
            return Response(
                status_code=400,
                body=json.dumps({"status": "error", "message": str(e)}),
            )
