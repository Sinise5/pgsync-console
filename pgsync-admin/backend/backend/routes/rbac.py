"""User and role management routes."""

import json
import logging
from robyn import Request, Response

from backend.db import db
from backend.models import User, Role, Permission
from backend.services.rbac_service import rbac_service

logger = logging.getLogger(__name__)


def rbac_routes(app):
    """Register RBAC routes."""

    @app.get("/api/rbac/users")
    async def list_users(request: Request) -> Response:
        """List all users."""
        try:
            with db.get_session() as session:
                users = session.query(User).all()
                return Response(
                    status_code=200,
                    body=json.dumps({"users": [u.to_dict() for u in users]}),
                )
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.post("/api/rbac/users")
    async def create_user(request: Request) -> Response:
        """Create new user."""
        try:
            body = json.loads(request.body)
            required = ["username", "email", "password"]
            for field in required:
                if field not in body:
                    return Response(
                        status_code=400,
                        body=json.dumps({"error": f"Field '{field}' is required"}),
                    )

            with db.get_session() as session:
                existing = session.query(User).filter_by(username=body["username"]).first()
                if existing:
                    return Response(
                        status_code=409,
                        body=json.dumps({"error": "Username already exists"}),
                    )

                from backend.services.auth_service import auth_service

                user = User(
                    username=body["username"],
                    email=body["email"],
                    password_hash=auth_service.hash_password(body["password"]),
                    is_active=True,
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                return Response(status_code=201, body=json.dumps(user.to_dict()))

        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.put("/api/rbac/users/:id/roles")
    async def update_user_roles(request: Request) -> Response:
        """Update user's roles."""
        try:
            user_id = int(request.path_params.get("id"))
            body = json.loads(request.body)
            role_ids = body.get("role_ids", [])

            with db.get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    return Response(
                        status_code=404,
                        body=json.dumps({"error": "User not found"}),
                    )

                # Clear existing roles
                user.roles.clear()

                # Assign new roles
                for role_id in role_ids:
                    role = session.query(Role).filter_by(id=role_id).first()
                    if role:
                        user.roles.append(role)

                session.commit()
                return Response(
                    status_code=200,
                    body=json.dumps({"message": "Roles updated"}),
                )

        except Exception as e:
            logger.error(f"Failed to update user roles: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.get("/api/rbac/roles")
    async def list_roles(request: Request) -> Response:
        """List all roles."""
        try:
            with db.get_session() as session:
                roles = session.query(Role).all()
                return Response(
                    status_code=200,
                    body=json.dumps({"roles": [r.to_dict() for r in roles]}),
                )
        except Exception as e:
            logger.error(f"Failed to list roles: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.post("/api/rbac/roles")
    async def create_role(request: Request) -> Response:
        """Create new role."""
        try:
            body = json.loads(request.body)
            if "name" not in body:
                return Response(
                    status_code=400,
                    body=json.dumps({"error": "Field 'name' is required"}),
                )

            with db.get_session() as session:
                role = Role(
                    name=body["name"],
                    description=body.get("description", ""),
                    is_system=False,
                )
                session.add(role)
                session.commit()
                session.refresh(role)
                return Response(status_code=201, body=json.dumps(role.to_dict()))

        except Exception as e:
            logger.error(f"Failed to create role: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.get("/api/rbac/permissions")
    async def list_permissions(request: Request) -> Response:
        """List all permissions."""
        try:
            with db.get_session() as session:
                perms = session.query(Permission).all()
                return Response(
                    status_code=200,
                    body=json.dumps({"permissions": [p.to_dict() for p in perms]}),
                )
        except Exception as e:
            logger.error(f"Failed to list permissions: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.get("/api/rbac/users/:id/permissions")
    async def get_user_permissions(request: Request) -> Response:
        """Get permissions for a user."""
        try:
            user_id = int(request.path_params.get("id"))
            perms = rbac_service.get_user_permissions(user_id)
            return Response(
                status_code=200,
                body=json.dumps({"permissions": sorted(list(perms))}),
            )
        except Exception as e:
            logger.error(f"Failed to get user permissions: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))
