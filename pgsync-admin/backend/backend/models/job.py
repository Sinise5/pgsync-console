"""Job model for scheduled executions."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON

from backend.models.configuration import Base


class Job(Base):
    """Scheduled job configuration."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    config_id = Column(Integer, ForeignKey("configurations.id"), nullable=False, index=True)

    # Scheduling
    cron_expression = Column(String(100), nullable=False)
    timezone = Column(String(50), default="UTC")
    enabled = Column(Boolean, default=True, index=True)

    # Priority (for workflow ordering)
    priority = Column(Integer, default=5)  # 1=highest, 10=lowest
    workflow_id = Column(Integer, nullable=True)  # Optional workflow grouping

    # Execution tracking
    next_run = Column(DateTime, nullable=True, index=True)
    last_run = Column(DateTime, nullable=True)
    last_status = Column(String(20), nullable=True)  # success, failure, running
    run_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)

    # Retry configuration
    retry_on_failure = Column(Boolean, default=True)
    max_retries = Column(Integer, default=3)
    retry_delay_seconds = Column(Integer, default=60)

    # Notifications
    notifications = Column(JSON, default=list)
    notify_on_success = Column(Boolean, default=False)
    notify_on_failure = Column(Boolean, default=True)

    # Execution options
    execution_type = Column(String(20), default="batch")  # batch, cdc
    timeout_seconds = Column(Integer, default=3600)
    concurrent_allowed = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100), default="system")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "config_id": self.config_id,
            "cron_expression": self.cron_expression,
            "timezone": self.timezone,
            "enabled": self.enabled,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_status": self.last_status,
            "run_count": self.run_count,
            "failure_count": self.failure_count,
            "retry_on_failure": self.retry_on_failure,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "notification_channels": self.notifications,
            "notify_on_success": self.notify_on_success,
            "notify_on_failure": self.notify_on_failure,
            "execution_type": self.execution_type,
            "timeout_seconds": self.timeout_seconds,
            "concurrent_allowed": self.concurrent_allowed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
        }
