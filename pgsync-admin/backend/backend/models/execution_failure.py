"""Execution failure and retry tracking model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, JSON

from backend.models.configuration import Base


class ExecutionFailure(Base):
    """Track execution failures for recovery."""

    __tablename__ = "execution_failures"

    id = Column(Integer, primary_key=True)
    execution_id = Column(Integer, ForeignKey("executions.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True, index=True)
    config_id = Column(Integer, ForeignKey("configurations.id"), nullable=False, index=True)

    # Error details
    error_type = Column(String(100), nullable=False)  # ConnectionError, TimeoutError, etc.
    error_message = Column(Text, nullable=False)
    error_traceback = Column(Text, nullable=True)

    # Retry info
    attempt_number = Column(Integer, default=1)
    max_retries = Column(Integer, default=3)
    retry_after_seconds = Column(Integer, default=300)  # 5 min backoff
    next_retry_at = Column(DateTime, nullable=True, index=True)
    is_retriable = Column(Boolean, default=True)

    # Recovery status
    status = Column(String(20), default="pending")  # pending, retrying, dead_letter, resolved
    recovered_at = Column(DateTime, nullable=True)
    recovery_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            "config_id": self.config_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "attempt_number": self.attempt_number,
            "max_retries": self.max_retries,
            "status": self.status,
            "is_retriable": self.is_retriable,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
