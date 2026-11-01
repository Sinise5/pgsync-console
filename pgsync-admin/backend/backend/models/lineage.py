"""Data lineage tracking models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey

from backend.models.configuration import Base


class DataLineage(Base):
    """Track data lineage and dependencies."""

    __tablename__ = "data_lineage"

    id = Column(Integer, primary_key=True)
    config_id = Column(Integer, ForeignKey("configurations.id"), nullable=False)

    # Source
    source_type = Column(String(50), nullable=False)  # postgresql
    source_name = Column(String(255), nullable=False)  # database.schema.table
    source_columns = Column(JSON, default=list)

    # Target
    target_type = Column(String(50), nullable=False)  # elasticsearch, opensearch
    target_name = Column(String(255), nullable=False)  # index name
    target_fields = Column(JSON, default=list)

    # Transformations
    transform_rules = Column(JSON, default=list)  # list of transform operations
    dependencies = Column(JSON, default=list)  # upstream table dependencies

    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    discovered_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "config_id": self.config_id,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "source_columns": self.source_columns,
            "target_type": self.target_type,
            "target_name": self.target_name,
            "target_fields": self.target_fields,
            "transform_rules": self.transform_rules,
            "dependencies": self.dependencies,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "discovered_at": self.discovered_at.isoformat() if self.discovered_at else None,
        }
