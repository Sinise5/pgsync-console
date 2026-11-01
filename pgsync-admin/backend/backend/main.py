"""PGSync Admin Backend - Robyn Application Entry Point."""

import json
import logging
from robyn import Robyn, Request, Response

from backend.config import settings
from backend.db import db
from backend.services.auth_service import auth_service
from backend.routes import (
    config_routes,
    discovery_routes,
    execution_routes,
    logs_routes,
    reports_routes,
    jobs_routes,
    notification_routes,
    error_recovery_routes,
    performance_routes,
    auth_routes,
    dashboard_routes,
    alerts_routes,
    lineage_routes,
    rbac_routes,
    audit_routes,
    tenant_routes,
    migration_routes,
    workflow_routes,
    clickhouse_migration_routes,
    cdc_routes,
)

logger = logging.getLogger(__name__)


def create_app() -> Robyn:
    """Create and configure Robyn application."""
    app = Robyn(__file__)

    # The Docker frontend container serves the built UI through Nginx.

    # Health check endpoint
    @app.get("/health")
    async def health(request: Request) -> Response:
        """Health check endpoint."""
        return Response(
            status_code=200,
            headers={"Content-Type": "application/json"},
            description=json.dumps({
                "status": "ok",
                "version": "0.6.0",
                "service": "pgsync-admin-backend",
            })
        )

    @app.before_request()
    async def authenticate_api_request(request: Request) -> Request | Response:
        """Require a valid bearer token for API routes except login."""
        path = request.url.path
        if not path.startswith("/api/") or path in {"/api/auth/login", "/api/auth/demo-credentials"}:
            return request

        authorization = request.headers.get("Authorization") or ""
        if not authorization.startswith("Bearer "):
            return Response(
                status_code=401,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Authentication required"}),
            )

        identity = auth_service.verify_token(authorization[7:])
        if not identity:
            return Response(
                status_code=401,
                headers={"Content-Type": "application/json"},
                description=json.dumps({"error": "Invalid or expired token"}),
            )

        return request

    @app.startup_handler
    async def startup_handler():
        """Initialize services on startup."""
        settings.validate_auth_config()
        logger.info("Starting PGSync Admin Backend v0.6.0")

        # Initialize database FIRST
        try:
            db.init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

        # Start scheduler AFTER DB ready
        from backend.services.scheduler_service import scheduler_service
        scheduler_service.start()
        logger.info("Scheduler service started")

    @app.shutdown_handler
    async def shutdown_handler():
        """Cleanup on shutdown."""
        logger.info("Shutting down PGSync Admin Backend")
        db.disconnect()

    # Register route groups
    config_routes(app)
    discovery_routes(app)
    execution_routes(app)
    logs_routes(app)
    reports_routes(app)
    jobs_routes(app)
    notification_routes(app)
    error_recovery_routes(app)
    performance_routes(app)
    auth_routes(app)
    dashboard_routes(app)
    alerts_routes(app)
    lineage_routes(app)
    rbac_routes(app)
    audit_routes(app)
    tenant_routes(app)
    migration_routes(app)
    workflow_routes(app)
    clickhouse_migration_routes(app)
    cdc_routes(app)

    logger.info(f"PGSync Admin API ready on {settings.api_host}:{settings.api_port}")
    return app


def main() -> None:
    """Entry point."""
    app = create_app()
    app.start(
        host=settings.api_host,
        port=settings.api_port,
    )


if __name__ == "__main__":
    main()
