"""Tenant isolation and context management service."""

import logging
from typing import Optional
from contextvars import ContextVar

from backend.db import db
from backend.models.tenant import Tenant

logger = logging.getLogger(__name__)

# Thread-local tenant context
_tenant_context: ContextVar[Optional[int]] = ContextVar("tenant_context", default=None)


class TenantService:
    """Manage tenant isolation and context."""

    @staticmethod
    def set_tenant_context(tenant_id: int):
        """Set current tenant context for request."""
        _tenant_context.set(tenant_id)
        logger.debug(f"Tenant context set to {tenant_id}")

    @staticmethod
    def get_tenant_context() -> Optional[int]:
        """Get current tenant ID from context."""
        return _tenant_context.get()

    @staticmethod
    def clear_tenant_context():
        """Clear tenant context."""
        _tenant_context.set(None)

    @staticmethod
    def create_tenant(name: str, display_name: str, settings: dict = None) -> Tenant:
        """Create new tenant."""
        tenant = Tenant(
            name=name,
            display_name=display_name,
            settings=settings or {},
            status="active",
        )
        session = db.get_session()
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
        logger.info(f"Created tenant: {name} (ID: {tenant.id})")
        return tenant

    @staticmethod
    def get_tenant(tenant_id: int) -> Optional[Tenant]:
        """Get tenant by ID."""
        session = db.get_session()
        return session.query(Tenant).filter_by(id=tenant_id).first()

    @staticmethod
    def list_tenants(status: str = None) -> list[Tenant]:
        """List all tenants, optionally filtered by status."""
        session = db.get_session()
        query = session.query(Tenant)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(Tenant.created_at.desc()).all()

    @staticmethod
    def update_tenant(tenant_id: int, **kwargs) -> Optional[Tenant]:
        """Update tenant fields."""
        session = db.get_session()
        tenant = session.query(Tenant).filter_by(id=tenant_id).first()
        if not tenant:
            return None

        for key, value in kwargs.items():
            if hasattr(tenant, key):
                setattr(tenant, key, value)

        session.commit()
        session.refresh(tenant)
        logger.info(f"Updated tenant {tenant_id}: {kwargs}")
        return tenant

    @staticmethod
    def suspend_tenant(tenant_id: int) -> bool:
        """Suspend tenant (prevents new operations)."""
        tenant = TenantService.update_tenant(tenant_id, status="suspended")
        if tenant:
            logger.warning(f"Tenant {tenant_id} suspended")
            return True
        return False

    @staticmethod
    def activate_tenant(tenant_id: int) -> bool:
        """Activate suspended tenant."""
        tenant = TenantService.update_tenant(tenant_id, status="active")
        if tenant:
            logger.info(f"Tenant {tenant_id} activated")
            return True
        return False

    @staticmethod
    def check_quota(tenant_id: int, quota_type: str, current_usage: int) -> bool:
        """Check if tenant is within quota limits."""
        tenant = TenantService.get_tenant(tenant_id)
        if not tenant:
            return False

        quota_map = {
            "configs": tenant.max_configs,
            "executions": tenant.max_executions_per_day,
            "storage": tenant.max_storage_gb,
        }

        limit = quota_map.get(quota_type)
        if limit is None:
            return True  # No limit set

        within_quota = current_usage < limit
        if not within_quota:
            logger.warning(
                f"Tenant {tenant_id} exceeded {quota_type} quota: {current_usage}/{limit}"
            )
        return within_quota


tenant_service = TenantService()
