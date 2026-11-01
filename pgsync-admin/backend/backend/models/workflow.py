"""Job dependency model for DAG workflows."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint

from backend.models.configuration import Base


class JobDependency(Base):
    """Job dependency edge for workflow DAG."""

    __tablename__ = "job_dependencies"

    id = Column(Integer, primary_key=True)
    parent_job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    child_job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    # Condition (optional)
    condition = Column(String(100), nullable=True)  # on_success, on_failure, always

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("parent_job_id", "child_job_id", name="uq_job_dependency"),
    )

    def to_dict(self):
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "parent_job_id": self.parent_job_id,
            "child_job_id": self.child_job_id,
            "condition": self.condition,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class WorkflowTemplate(Base):
    """Reusable workflow template with predefined DAG."""

    __tablename__ = "workflow_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(String(500), nullable=True)

    # DAG definition (JSON)
    dag_config = Column(String, nullable=False)  # JSON string with nodes + edges

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100), default="system")

    def to_dict(self):
        """Serialize to dictionary."""
        import json
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "dag_config": json.loads(self.dag_config) if self.dag_config else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
        }
