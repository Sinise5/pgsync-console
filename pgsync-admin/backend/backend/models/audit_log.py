"""Audit log model for tracking user actions."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey

from backend.models.configuration import Base


class AuditLog(Base):
    """Audit log entry for tracking user actions."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)

    # Who
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(100))
    ip_address = Column(String(50))

    # What
    action = Column(String(100), nullable=False)  # create, update, delete, execute
    resource_type = Column(String(50), nullable=False)  # config, execution, job, etc.
    resource_id = Column(Integer, nullable=True)

    # Details
    old_value = Column(JSON, nullable=True)  # Before state
    new_value = Column(JSON, nullable=True)  # After state
    status = Column(String(20), default="success")  # success, failure, error
    error_message = Column(Text, nullable=True)

    # When
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Metadata
    request_id = Column(String(100), nullable=True)
    session_id = Column(String(100), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "ip_address": self.ip_address,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "status": self.status,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "request_id": self.request_id,
            "session_id": self.session_id,
        }
