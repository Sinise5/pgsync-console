"""Alert rule and history models."""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON, Float, ForeignKey

from backend.models.configuration import Base


class AlertRule(Base):
    """Alert rule definition."""

    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Rule configuration
    metric = Column(String(100), nullable=False)  # latency, throughput, error_rate, docs_count
    condition = Column(String(50), nullable=False)  # gt, lt, gte, lte, eq, anomaly
    threshold = Column(Float, nullable=False)
    duration_seconds = Column(Integer, default=300)  # evaluation window
    cooldown_seconds = Column(Integer, default=900)  # silence between alerts

    # Targets
    config_ids = Column(JSON, default=list)  # which configs to monitor
    severity = Column(String(20), default="warning")  # critical, warning, info
    notification_channels = Column(JSON, default=list)  # telegram, email, webhook

    # State
    enabled = Column(Boolean, default=True)
    last_evaluated = Column(DateTime)
    last_triggered = Column(DateTime)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, default=1)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "metric": self.metric,
            "condition": self.condition,
            "threshold": self.threshold,
            "duration_seconds": self.duration_seconds,
            "cooldown_seconds": self.cooldown_seconds,
            "config_ids": self.config_ids,
            "severity": self.severity,
            "notification_channels": self.notification_channels,
            "enabled": self.enabled,
            "last_evaluated": self.last_evaluated.isoformat() if self.last_evaluated else None,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
        }


class AlertEvaluation(Base):
    """Alert evaluation history."""

    __tablename__ = "alert_evaluations"

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False)
    triggered = Column(Boolean, default=False)

    # Evaluation result
    actual_value = Column(Float)
    threshold = Column(Float)
    metric = Column(String(100))
    condition = Column(String(50))

    # Context
    config_id = Column(Integer, nullable=True)
    message = Column(Text)
    severity = Column(String(20))

    # Notification status
    notif_sent = Column(Boolean, default=False)
    notif_channels = Column(JSON, default=list)
    suppressed = Column(Boolean, default=False)

    # Timestamp
    evaluated_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "triggered": self.triggered,
            "actual_value": self.actual_value,
            "threshold": self.threshold,
            "metric": self.metric,
            "condition": self.condition,
            "config_id": self.config_id,
            "message": self.message,
            "severity": self.severity,
            "notif_sent": self.notif_sent,
            "suppressed": self.suppressed,
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
