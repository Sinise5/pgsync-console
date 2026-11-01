"""Dashboard model for custom analytics views."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON, ForeignKey

from backend.models.configuration import Base


class Dashboard(Base):
    """User-created custom dashboards."""

    __tablename__ = "dashboards"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    created_by = Column(Integer)  # User ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_shared = Column(Boolean, default=False)
    share_token = Column(String(255), unique=True)
    layout_config = Column(JSON, default={})  # grid layout info

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_shared": self.is_shared,
            "share_token": self.share_token,
            "layout_config": self.layout_config,
        }


class DashboardWidget(Base):
    """Widgets within dashboards."""

    __tablename__ = "dashboard_widgets"

    id = Column(Integer, primary_key=True)
    dashboard_id = Column(Integer, ForeignKey("dashboards.id"), nullable=False)
    widget_type = Column(String(50), nullable=False)  # metric, chart, table, gauge, kpi
    title = Column(String(255), nullable=False)
    config = Column(JSON, default={})  # widget-specific configuration
    position = Column(Integer, default=0)  # order in dashboard
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "dashboard_id": self.dashboard_id,
            "widget_type": self.widget_type,
            "title": self.title,
            "config": self.config,
            "position": self.position,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
