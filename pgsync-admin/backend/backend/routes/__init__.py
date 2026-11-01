"""Routes package initialization — lazy-loaded to avoid import-time blocking."""

__all__ = [
    "config_routes",
    "discovery_routes",
    "execution_routes",
    "logs_routes",
    "reports_routes",
    "jobs_routes",
    "notification_routes",
    "error_recovery_routes",
    "performance_routes",
    "auth_routes",
    "dashboard_routes",
    "alerts_routes",
    "lineage_routes",
    "rbac_routes",
    "audit_routes",
    "tenant_routes",
    "migration_routes",
    "workflow_routes",
    "clickhouse_migration_routes",
    "cdc_routes",
]


def __getattr__(name: str):
    """Lazy-load route functions on first access."""
    if name == "config_routes":
        from backend.routes.config import config_routes
        return config_routes
    elif name == "discovery_routes":
        from backend.routes.discovery import discovery_routes
        return discovery_routes
    elif name == "execution_routes":
        from backend.routes.execution import execution_routes
        return execution_routes
    elif name == "logs_routes":
        from backend.routes.logs import logs_routes
        return logs_routes
    elif name == "reports_routes":
        from backend.routes.reports import reports_routes
        return reports_routes
    elif name == "jobs_routes":
        from backend.routes.jobs import jobs_routes
        return jobs_routes
    elif name == "notification_routes":
        from backend.routes.notifications import notification_routes
        return notification_routes
    elif name == "error_recovery_routes":
        from backend.routes.error_recovery import error_recovery_routes
        return error_recovery_routes
    elif name == "performance_routes":
        from backend.routes.performance import performance_routes
        return performance_routes
    elif name == "auth_routes":
        from backend.routes.auth import auth_routes
        return auth_routes
    elif name == "dashboard_routes":
        from backend.routes.dashboards import dashboard_routes
        return dashboard_routes
    elif name == "alerts_routes":
        from backend.routes.alerts import alerts_routes
        return alerts_routes
    elif name == "lineage_routes":
        from backend.routes.lineage import lineage_routes
        return lineage_routes
    elif name == "rbac_routes":
        from backend.routes.rbac import rbac_routes
        return rbac_routes
    elif name == "audit_routes":
        from backend.routes.audit import audit_routes
        return audit_routes
    elif name == "tenant_routes":
        from backend.routes.tenants import tenant_routes
        return tenant_routes
    elif name == "migration_routes":
        from backend.routes.migrations import migration_routes
        return migration_routes
    elif name == "workflow_routes":
        from backend.routes.workflows import workflow_routes
        return workflow_routes
    elif name == "clickhouse_migration_routes":
        from backend.routes.clickhouse_migrations import clickhouse_migration_routes
        return clickhouse_migration_routes
    elif name == "cdc_routes":
        from backend.routes.cdc import cdc_routes
        return cdc_routes
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
