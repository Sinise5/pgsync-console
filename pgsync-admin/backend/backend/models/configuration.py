"""SQLAlchemy configuration model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


class Configuration(Base):
    """PGSync configuration storage."""

    __tablename__ = "configurations"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Metadata
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Source PostgreSQL connection
    source_pg_host: Mapped[str] = mapped_column(String(256), nullable=False)
    source_pg_port: Mapped[int] = mapped_column(Integer, nullable=False, default=5432)
    source_pg_database: Mapped[str] = mapped_column(String(128), nullable=False)
    source_pg_user: Mapped[str] = mapped_column(String(128), nullable=False)
    source_pg_password: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted

    # Generic values above retain their legacy names; source_type selects the dialect.
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="postgres")
    pipeline_type: Mapped[str] = mapped_column(String(32), nullable=False, default="pg_search")

    # Target storage
    target_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="opensearch"
    )  # opensearch, elasticsearch, redis
    target_config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string

    # Schema configuration (user selections)
    schema_config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string

    # Generated artifacts
    pgsync_schema_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plugin_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Versioning
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('opensearch', 'elasticsearch', 'redis')",
            name="ck_target_type",
        ),
        CheckConstraint(
            "source_pg_port > 0 AND source_pg_port < 65536",
            name="ck_pg_port_range",
        ),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Configuration(id={self.id}, name='{self.name}', "
            f"version={self.version}, active={self.is_active})>"
        )
