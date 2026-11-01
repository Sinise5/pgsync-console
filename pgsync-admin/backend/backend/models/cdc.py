"""CDC (Change Data Capture) models for real-time sync."""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text

from backend.models.configuration import Base


class CDCStatus(str, Enum):
    """CDC runner status."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    STOPPING = "stopping"


class CDCState(Base):
    """CDC state tracking per configuration."""
    __tablename__ = "cdc_states"

    id = Column(Integer, primary_key=True)
    config_id = Column(Integer, nullable=False, unique=True)

    # Status
    status = Column(String(20), default=CDCStatus.STOPPED.value)

    # Progress tracking
    last_lsn = Column(String(255), nullable=True)  # PostgreSQL LSN checkpoint
    last_sync_time = Column(DateTime, nullable=True)
    docs_synced = Column(Integer, default=0)

    # Performance metrics
    throughput = Column(Float, default=0.0)  # docs/sec
    lag_seconds = Column(Float, default=0.0)  # how far behind real-time

    # Error tracking
    error_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    last_error_time = Column(DateTime, nullable=True)

    # Lifecycle
    started_at = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """Serialize to dict."""
        return {
            "id": self.id,
            "config_id": self.config_id,
            "status": self.status,
            "last_lsn": self.last_lsn,
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "docs_synced": self.docs_synced,
            "throughput": self.throughput,
            "lag_seconds": self.lag_seconds,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
