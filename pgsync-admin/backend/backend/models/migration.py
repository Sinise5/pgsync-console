"""Migration model for batch data sync operations."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, Boolean, Text, Enum
import enum

from backend.models.configuration import Base


class MigrationStatus(str, enum.Enum):
    """Migration execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class MigrationBatchFrequency(str, enum.Enum):
    """Batch frequency for scheduled migrations."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class Migration(Base):
    """Migration execution tracking."""
    __tablename__ = "migrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)

    # Batch configuration
    frequency = Column(Enum(MigrationBatchFrequency), default=MigrationBatchFrequency.DAILY)
    date_column = Column(String(255), nullable=True)  # Which column to filter by date
    date_from = Column(DateTime, nullable=True)  # Filter: start date
    date_to = Column(DateTime, nullable=True)    # Filter: end date
    limit = Column(Integer, nullable=True)       # Limit docs (None = all)

    # Execution status
    status = Column(Enum(MigrationStatus), default=MigrationStatus.PENDING, index=True)
    progress_percent = Column(Float, default=0.0)

    # Metrics
    total_docs = Column(Integer, default=0)
    synced_docs = Column(Integer, default=0)
    failed_docs = Column(Integer, default=0)
    batch_count = Column(Integer, default=0)
    current_batch = Column(Integer, default=0)

    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)  # Store detailed errors per batch

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)

    # Control
    is_active = Column(Boolean, default=True)

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'config_id': self.config_id,
            'name': self.name,
            'frequency': self.frequency.value if self.frequency else None,
            'date_column': self.date_column,
            'date_from': self.date_from.isoformat() if self.date_from else None,
            'date_to': self.date_to.isoformat() if self.date_to else None,
            'limit': self.limit,
            'status': self.status.value if self.status else None,
            'progress_percent': self.progress_percent,
            'total_docs': self.total_docs,
            'synced_docs': self.synced_docs,
            'failed_docs': self.failed_docs,
            'batch_count': self.batch_count,
            'current_batch': self.current_batch,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'error_message': self.error_message,
            'error_details': self.error_details,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'is_active': self.is_active,
        }
