"""Authentication and authorization routes."""

import json
import logging
import secrets
from robyn import Request, Response

from backend.config import settings
from backend.services.auth_service import auth_service, InputValidator

logger = logging.getLogger(__name__)


def auth_routes(app):
    """Register authentication routes."""

    @app.get("/api/auth/demo-credentials")
    async def demo_credentials(request: Request) -> Response:
        """Expose the configured account only when local demo mode is explicitly enabled."""
        if not settings.demo_login_credentials:
            return Response(status_code=404, body=json.dumps({"error": "Not found"}))

        return Response(
            status_code=200,
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
            body=json.dumps({
                "username": settings.auth_admin_username,
                "password": settings.auth_admin_password,
            }),
        )

    @app.post("/api/auth/login")
    async def login(request: Request) -> Response:
        """User login."""
        try:
            body = json.loads(request.body)
            username = body.get("username")
            password = body.get("password")

            if not isinstance(username, str) or not isinstance(password, str) or not username or not password:
                return Response(
                    status_code=400,
                    body=json.dumps({"error": "Username and password required"}),
                )

            username_matches = secrets.compare_digest(
                username.encode("utf-8"), settings.auth_admin_username.encode("utf-8")
            )
            password_matches = secrets.compare_digest(
                password.encode("utf-8"), settings.auth_admin_password.encode("utf-8")
            )
            if username_matches and password_matches:
                token = auth_service.generate_token(
                    user_id=1,
                    username=username,
                    roles=["admin"],
                )
                session_id = auth_service.create_session(1, username, ["admin"])

                return Response(
                    status_code=200,
                    body=json.dumps({
                        "token": token,
                        "session_id": session_id,
                        "user": {
                            "id": 1,
                            "username": username,
                            "roles": ["admin"],
                        },
                    }),
                )
            else:
                return Response(
                    status_code=401,
                    body=json.dumps({"error": "Invalid credentials"}),
                )
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": "Login could not be completed"}),
            )

    @app.post("/api/auth/logout")
    async def logout(request: Request) -> Response:
        """User logout."""
        try:
            body = json.loads(request.body or "{}")
            session_id = body.get("session_id")

            if session_id:
                auth_service.revoke_session(session_id)

            return Response(
                status_code=200,
                body=json.dumps({"message": "Logged out successfully"}),
            )
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.get("/api/auth/verify")
    async def verify_token(request: Request) -> Response:
        """Verify JWT token."""
        try:
            auth_header = request.headers.get("Authorization") or ""
            if not auth_header.startswith("Bearer "):
                return Response(
                    status_code=401,
                    body=json.dumps({"error": "Missing or invalid authorization header"}),
                )

            token = auth_header[7:]
            payload = auth_service.verify_token(token)

            if not payload:
                return Response(
                    status_code=401,
                    body=json.dumps({"error": "Invalid or expired token"}),
                )

            return Response(
                status_code=200,
                body=json.dumps({"valid": True, "payload": payload}),
            )
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.get("/api/auth/sessions")
    async def list_sessions(request: Request) -> Response:
        """List active sessions (admin only)."""
        try:
            sessions = [
                {
                    "session_id": sid,
                    "username": data["username"],
                    "roles": data["roles"],
                    "created_at": data["created_at"].isoformat(),
                    "last_accessed": data["last_accessed"].isoformat(),
                }
                for sid, data in auth_service.sessions.items()
            ]

            return Response(
                status_code=200,
                body=json.dumps({"sessions": sessions}),
            )
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/auth/sessions/cleanup")
    async def cleanup_sessions(request: Request) -> Response:
        """Cleanup expired sessions."""
        try:
            body = json.loads(request.body or "{}")
            max_age = body.get("max_age", 3600)

            auth_service.cleanup_expired_sessions(max_age)

            return Response(
                status_code=200,
                body=json.dumps({"message": "Sessions cleaned up"}),
            )
        except Exception as e:
            logger.error(f"Failed to cleanup sessions: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )
