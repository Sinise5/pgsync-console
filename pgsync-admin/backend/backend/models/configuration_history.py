"""SQLAlchemy configuration history model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.configuration import Base


class ConfigurationHistory(Base):
    """Configuration version history for rollback capability."""

    __tablename__ = "configuration_history"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to configuration
    config_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("configurations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Version number
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Snapshot of configuration at this version
    schema_config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    pgsync_schema_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plugin_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    change_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Constraints
    __table_args__ = (
        UniqueConstraint("config_id", "version", name="uq_config_version"),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<ConfigurationHistory(id={self.id}, config_id={self.config_id}, "
            f"version={self.version})>"
        )
