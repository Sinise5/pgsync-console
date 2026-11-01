"""Audit logging service."""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from backend.db import db
from backend.models import AuditLog

logger = logging.getLogger(__name__)


class AuditLogger:
    """Centralized audit logging service."""

    def log(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Log an audit event."""
        try:
            with db.get_session() as session:
                log_entry = AuditLog(
                    user_id=user_id,
                    username=username or "system",
                    ip_address=ip_address,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    old_value=old_value,
                    new_value=new_value,
                    status=status,
                    error_message=error_message,
                    request_id=request_id,
                    session_id=session_id,
                )
                session.add(log_entry)
                session.commit()

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def log_config_create(self, config_id: int, config_data: Dict, user: str = "system") -> None:
        """Log configuration creation."""
        self.log(
            action="create",
            resource_type="configuration",
            resource_id=config_id,
            username=user,
            new_value=config_data,
        )

    def log_config_update(
        self, config_id: int, old_data: Dict, new_data: Dict, user: str = "system"
    ) -> None:
        """Log configuration update."""
        self.log(
            action="update",
            resource_type="configuration",
            resource_id=config_id,
            username=user,
            old_value=old_data,
            new_value=new_data,
        )

    def log_config_delete(self, config_id: int, config_data: Dict, user: str = "system") -> None:
        """Log configuration deletion."""
        self.log(
            action="delete",
            resource_type="configuration",
            resource_id=config_id,
            username=user,
            old_value=config_data,
        )

    def log_execution_start(self, config_id: int, execution_id: int, user: str = "system") -> None:
        """Log execution start."""
        self.log(
            action="execute",
            resource_type="execution",
            resource_id=execution_id,
            username=user,
            new_value={"config_id": config_id},
        )

    def log_execution_complete(
        self, execution_id: int, status: str, stats: Dict, user: str = "system"
    ) -> None:
        """Log execution completion."""
        self.log(
            action="complete",
            resource_type="execution",
            resource_id=execution_id,
            username=user,
            status=status,
            new_value=stats,
        )

    def log_job_create(self, job_id: int, job_data: Dict, user: str = "system") -> None:
        """Log job creation."""
        self.log(
            action="create",
            resource_type="job",
            resource_id=job_id,
            username=user,
            new_value=job_data,
        )

    def log_alert_trigger(self, rule_id: int, alert_data: Dict, user: str = "system") -> None:
        """Log alert trigger."""
        self.log(
            action="trigger",
            resource_type="alert",
            resource_id=rule_id,
            username=user,
            new_value=alert_data,
        )

    def log_user_login(self, user_id: int, username: str, ip: str, success: bool) -> None:
        """Log user login attempt."""
        self.log(
            action="login",
            resource_type="auth",
            user_id=user_id,
            username=username,
            ip_address=ip,
            status="success" if success else "failure",
        )


audit_logger = AuditLogger()
