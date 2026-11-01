"""Minimal test server for dashboard API debugging."""

import json
import logging
from robyn import Robyn, Request, Response

from backend.config import settings
from backend.db import db
from backend.models import Dashboard
from backend.services.auth_service import auth_service
from backend.routes.auth import auth_routes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Robyn(__file__)


@app.before_request()
async def authenticate_api_request(request: Request) -> Request | Response:
    if not request.url.path.startswith("/api/") or request.url.path == "/api/auth/login":
        return request
    authorization = request.headers.get("Authorization") or ""
    if not authorization.startswith("Bearer ") or not auth_service.verify_token(authorization[7:]):
        return Response(
            status_code=401,
            headers={"Content-Type": "application/json"},
            description=json.dumps({"error": "Authentication required"}),
        )
    return request

# Initialize DB
db.connect()
logger.info("Database connected")

# Health check
@app.get("/health")
async def health(request: Request) -> Response:
    return Response(
        status_code=200,
        description=json.dumps({"status": "ok", "service": "pgsync-admin-test"}),
    )

# Dashboards endpoint
@app.get("/api/dashboards")
async def list_dashboards(request: Request) -> Response:
    try:
        with db.get_session() as session:
            dashboards = session.query(Dashboard).order_by(Dashboard.created_at.desc()).all()
            return Response(
                status_code=200,
                description=json.dumps({"dashboards": [d.to_dict() for d in dashboards]}),
                headers={"Content-Type": "application/json"},
            )
    except Exception as e:
        logger.error(f"Failed to list dashboards: {e}")
        return Response(
            status_code=500,
            description=json.dumps({"error": str(e)}),
            headers={"Content-Type": "application/json"},
        )


auth_routes(app)

if __name__ == "__main__":
    settings.validate_auth_config()
    logger.info(f"Starting test server on {settings.api_host}:{settings.api_port}")
    app.start(host=settings.api_host, port=settings.api_port)
