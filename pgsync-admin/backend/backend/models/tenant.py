"""Multi-tenant workspace model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON

from backend.models.configuration import Base


class Tenant(Base):
    """Tenant/workspace for multi-organization isolation."""

    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    display_name = Column(String(255), nullable=False)
    status = Column(String(50), default="active")  # active, suspended, deleted
    settings = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Quotas
    max_configs = Column(Integer, default=100)
    max_executions_per_day = Column(Integer, default=1000)
    max_storage_gb = Column(Integer, default=50)

    def to_dict(self):
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "status": self.status,
            "settings": self.settings,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "max_configs": self.max_configs,
            "max_executions_per_day": self.max_executions_per_day,
            "max_storage_gb": self.max_storage_gb,
        }
