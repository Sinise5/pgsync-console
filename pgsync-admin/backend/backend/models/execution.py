"""SQLAlchemy execution tracking model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text, DateTime, Float, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, synonym

from backend.models.configuration import Base


class Execution(Base):
    """Track batch/CDC execution state."""

    __tablename__ = "executions"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Foreign key to configuration
    config_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("configurations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Execution type
    type: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # batch, cdc

    # Status
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )  # pending, running, completed, failed, paused

    # Process metadata. `pid` is persisted so execution status survives API reloads.
    pid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Progress tracking
    progress_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_docs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_docs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Compatibility names used by the API and scheduler.
    execution_type = synonym("type")
    process_pid = synonym("pid")
    rows_processed = synonym("synced_docs")

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_stack: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Checkpoint for resume capability
    checkpoint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "type IN ('batch', 'cdc')",
            name="ck_execution_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'paused')",
            name="ck_execution_status",
        ),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Execution(id={self.id}, config_id={self.config_id}, "
            f"type='{self.type}', status='{self.status}')>"
        )
