"""RBAC service for permission checking and enforcement."""

import logging
from typing import List, Optional, Set
from functools import wraps

from backend.db import db
from backend.models import User, Role, Permission

logger = logging.getLogger(__name__)


class RBACService:
    """Role-Based Access Control service."""

    # Default system roles
    DEFAULT_ROLES = {
        "admin": {
            "description": "Full system access",
            "permissions": ["*:*"],  # All permissions
        },
        "operator": {
            "description": "Can manage configurations and executions",
            "permissions": [
                "config:read",
                "config:update",
                "execution:read",
                "execution:execute",
                "job:read",
                "job:create",
            ],
        },
        "viewer": {
            "description": "Read-only access",
            "permissions": [
                "config:read",
                "execution:read",
                "job:read",
                "dashboard:read",
                "alert:read",
                "lineage:read",
            ],
        },
    }

    def init_default_roles(self) -> None:
        """Initialize default system roles."""
        try:
            with db.get_session() as session:
                for role_name, role_data in self.DEFAULT_ROLES.items():
                    existing = session.query(Role).filter_by(name=role_name).first()
                    if existing:
                        continue

                    role = Role(
                        name=role_name,
                        description=role_data["description"],
                        is_system=True,
                    )
                    session.add(role)
                    session.flush()

                    # Create and assign permissions
                    for perm_pattern in role_data["permissions"]:
                        if perm_pattern == "*:*":
                            # Admin gets all permissions
                            perms = session.query(Permission).all()
                            for perm in perms:
                                if perm not in role.permissions:
                                    role.permissions.append(perm)
                        else:
                            resource, action = perm_pattern.split(":")
                            perm = session.query(Permission).filter_by(
                                resource=resource, action=action
                            ).first()
                            if perm and perm not in role.permissions:
                                role.permissions.append(perm)

                session.commit()
                logger.info("Default RBAC roles initialized")

        except Exception as e:
            logger.error(f"Failed to init default roles: {e}")

    def check_permission(self, user_id: int, resource: str, action: str) -> bool:
        """Check if user has permission for resource+action."""
        try:
            with db.get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    return False

                if not user.is_active:
                    return False

                # Collect all permissions from user's roles
                perms: Set[str] = set()
                for role in user.roles:
                    for perm in role.permissions:
                        perm_key = f"{perm.resource}:{perm.action}"
                        perms.add(perm_key)

                # Check for exact match or wildcard
                return (
                    f"{resource}:{action}" in perms
                    or f"{resource}:*" in perms
                    or "*:*" in perms
                )

        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            return False

    def get_user_permissions(self, user_id: int) -> Set[str]:
        """Get all permissions for a user."""
        try:
            with db.get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    return set()

                perms: Set[str] = set()
                for role in user.roles:
                    for perm in role.permissions:
                        perms.add(f"{perm.resource}:{perm.action}")

                return perms

        except Exception as e:
            logger.error(f"Failed to get user permissions: {e}")
            return set()

    def assign_role(self, user_id: int, role_id: int) -> bool:
        """Assign a role to a user."""
        try:
            with db.get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                role = session.query(Role).filter_by(id=role_id).first()

                if not user or not role:
                    return False

                if role not in user.roles:
                    user.roles.append(role)
                    session.commit()

                return True

        except Exception as e:
            logger.error(f"Failed to assign role: {e}")
            return False

    def revoke_role(self, user_id: int, role_id: int) -> bool:
        """Revoke a role from a user."""
        try:
            with db.get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                role = session.query(Role).filter_by(id=role_id).first()

                if not user or not role:
                    return False

                if role in user.roles:
                    user.roles.remove(role)
                    session.commit()

                return True

        except Exception as e:
            logger.error(f"Failed to revoke role: {e}")
            return False


rbac_service = RBACService()
