"""Alert rules and history API routes."""

import json
import logging
from datetime import datetime
from robyn import Request, Response

from backend.db import db
from backend.models import AlertRule, AlertEvaluation
from backend.services.anomaly_detector import anomaly_detector
from backend.services.clickhouse_client import clickhouse_client

logger = logging.getLogger(__name__)


def alerts_routes(app):
    """Register alert routes."""

    @app.get("/api/alerts/rules")
    async def list_alert_rules(request: Request) -> Response:
        """List all alert rules."""
        try:
            with db.get_session() as session:
                rules = session.query(AlertRule).order_by(AlertRule.created_at.desc()).all()
                return Response(
                    status_code=200,
                    body=json.dumps({"rules": [r.to_dict() for r in rules]}),
                )
        except Exception as e:
            logger.error(f"Failed to list alert rules: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.post("/api/alerts/rules")
    async def create_alert_rule(request: Request) -> Response:
        """Create new alert rule."""
        try:
            body = json.loads(request.body)
            required = ["name", "metric", "condition", "threshold"]
            for field in required:
                if field not in body:
                    return Response(
                        status_code=400,
                        body=json.dumps({"error": f"Field '{field}' is required"}),
                    )

            if not isinstance(body["name"], str) or not body["name"].strip():
                return Response(status_code=400, body=json.dumps({"error": "Rule name cannot be empty"}))
            try:
                threshold = float(body["threshold"])
                duration_seconds = int(body.get("duration_seconds", 300))
                cooldown_seconds = int(body.get("cooldown_seconds", 900))
            except (TypeError, ValueError):
                return Response(status_code=400, body=json.dumps({"error": "Threshold and timing values must be numbers"}))
            if duration_seconds < 0 or cooldown_seconds < 0:
                return Response(status_code=400, body=json.dumps({"error": "Alert durations cannot be negative"}))

            with db.get_session() as session:
                rule = AlertRule(
                    name=body["name"].strip(),
                    description=body.get("description", ""),
                    metric=body["metric"],
                    condition=body["condition"],
                    threshold=threshold,
                    duration_seconds=duration_seconds,
                    cooldown_seconds=cooldown_seconds,
                    config_ids=body.get("config_ids", []),
                    severity=body.get("severity", "warning"),
                    notification_channels=body.get("notification_channels", []),
                    enabled=bool(body.get("enabled", True)),
                )
                session.add(rule)
                session.commit()
                session.refresh(rule)
                return Response(
                    status_code=201,
                    body=json.dumps(rule.to_dict()),
                )
        except Exception as e:
            logger.error(f"Failed to create alert rule: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.put("/api/alerts/rules/:id")
    async def update_alert_rule(request: Request) -> Response:
        """Update alert rule."""
        try:
            rule_id = int(request.path_params.get("id"))
            body = json.loads(request.body)

            with db.get_session() as session:
                rule = session.query(AlertRule).filter_by(id=rule_id).first()
                if not rule:
                    return Response(
                        status_code=404,
                        body=json.dumps({"error": "Alert rule not found"}),
                    )

                updatable = ["name", "description", "metric", "condition", "threshold",
                             "duration_seconds", "cooldown_seconds", "config_ids",
                             "severity", "notification_channels", "enabled"]
                for field in updatable:
                    if field in body:
                        setattr(rule, field, body[field])

                session.commit()
                session.refresh(rule)
                return Response(
                    status_code=200,
                    body=json.dumps(rule.to_dict()),
                )
        except Exception as e:
            logger.error(f"Failed to update alert rule: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.delete("/api/alerts/rules/:id")
    async def delete_alert_rule(request: Request) -> Response:
        """Delete alert rule."""
        try:
            rule_id = int(request.path_params.get("id"))

            with db.get_session() as session:
                rule = session.query(AlertRule).filter_by(id=rule_id).first()
                if not rule:
                    return Response(
                        status_code=404,
                        body=json.dumps({"error": "Alert rule not found"}),
                    )
                session.delete(rule)
                session.commit()
                return Response(
                    status_code=200,
                    body=json.dumps({"message": "Alert rule deleted"}),
                )
        except Exception as e:
            logger.error(f"Failed to delete alert rule: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.post("/api/alerts/rules/:id/test")
    async def test_alert_rule(request: Request) -> Response:
        """Test alert rule against current metrics."""
        try:
            rule_id = int(request.path_params.get("id"))

            with db.get_session() as session:
                rule = session.query(AlertRule).filter_by(id=rule_id).first()
                if not rule:
                    return Response(
                        status_code=404,
                        body=json.dumps({"error": "Alert rule not found"}),
                    )

                # Get current metric value
                current_value = clickhouse_client.query_current_metric(rule.metric)
                if current_value is None:
                    return Response(
                        status_code=200,
                        body=json.dumps({
                            "triggered": False,
                            "message": f"No current data for metric: {rule.metric}",
                            "actual_value": None,
                        }),
                    )

                # Evaluate
                triggered, _ = anomaly_detector.evaluate_rule_condition(
                    rule.metric, current_value, rule.condition, rule.threshold
                )

                return Response(
                    status_code=200,
                    body=json.dumps({
                        "triggered": triggered,
                        "metric": rule.metric,
                        "actual_value": current_value,
                        "threshold": rule.threshold,
                        "condition": rule.condition,
                        "message": anomaly_detector.generate_message(
                            rule.name, rule.metric, current_value,
                            rule.threshold, rule.condition, rule.severity
                        ) if triggered else "No alert triggered",
                    }),
                )
        except Exception as e:
            logger.error(f"Failed to test alert rule: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.get("/api/alerts/history")
    async def list_alert_history(request: Request) -> Response:
        """List alert evaluation history."""
        try:
            with db.get_session() as session:
                evaluations = session.query(AlertEvaluation).order_by(
                    AlertEvaluation.evaluated_at.desc()
                ).limit(100).all()
                return Response(
                    status_code=200,
                    body=json.dumps({"evaluations": [e.to_dict() for e in evaluations]}),
                )
        except Exception as e:
            logger.error(f"Failed to list alert history: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.post("/api/alerts/:id/suppress")
    async def suppress_alert(request: Request) -> Response:
        """Suppress (silence) an alert evaluation."""
        try:
            eval_id = int(request.path_params.get("id"))
            body = json.loads(request.body or "{}")
            hours = body.get("hours", 24)

            with db.get_session() as session:
                evaluation = session.query(AlertEvaluation).filter_by(id=eval_id).first()
                if not evaluation:
                    return Response(
                        status_code=404,
                        body=json.dumps({"error": "Alert evaluation not found"}),
                    )

                evaluation.suppressed = True

                # If rule_id present, extend cooldown
                if evaluation.rule_id:
                    rule = session.query(AlertRule).filter_by(id=evaluation.rule_id).first()
                    if rule:
                        rule.cooldown_seconds = max(rule.cooldown_seconds, hours * 3600)

                session.commit()
                return Response(
                    status_code=200,
                    body=json.dumps({"message": f"Alert suppressed for {hours} hours"}),
                )
        except Exception as e:
            logger.error(f"Failed to suppress alert: {e}")
            return Response(status_code=500, body=json.dumps({"error": str(e)}))

    @app.get("/api/alerts/templates")
    async def list_alert_templates(request: Request) -> Response:
        """List pre-built alert templates."""
        templates = [
            {
                "name": "High Latency Warning",
                "metric": "latency",
                "condition": "gt",
                "threshold": 5000,  # 5 seconds
                "severity": "warning",
                "description": "Alert when sync latency exceeds 5 seconds",
            },
            {
                "name": "High Latency Critical",
                "metric": "latency",
                "condition": "gt",
                "threshold": 30000,  # 30 seconds
                "severity": "critical",
                "description": "Alert when sync latency exceeds 30 seconds",
            },
            {
                "name": "Error Rate Spike",
                "metric": "error_rate",
                "condition": "gt",
                "threshold": 0.05,  # 5% error rate
                "severity": "critical",
                "description": "Alert when error rate exceeds 5%",
            },
            {
                "name": "Throughput Drop",
                "metric": "throughput",
                "condition": "lt",
                "threshold": 10,  # 10 docs/sec
                "severity": "warning",
                "description": "Alert when throughput drops below 10 docs/sec",
            },
            {
                "name": "Batch Duration Spike",
                "metric": "batch_duration",
                "condition": "gt",
                "threshold": 3600,  # 1 hour
                "severity": "warning",
                "description": "Alert when batch takes longer than 1 hour",
            },
            {
                "name": "Anomaly Detection",
                "metric": "latency",
                "condition": "anomaly",
                "threshold": 2.0,
                "severity": "info",
                "description": "Detect anomalous latency patterns (z-score > 2.0)",
            },
        ]
        return Response(
            status_code=200,
            body=json.dumps({"templates": templates}),
        )
