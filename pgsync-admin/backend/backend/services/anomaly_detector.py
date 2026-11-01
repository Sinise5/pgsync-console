"""Anomaly detection service for alerting."""

import logging
import statistics
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detect anomalies in metrics using statistical methods."""

    def __init__(self, window_size: int = 20, z_score_threshold: float = 2.0):
        self.window_size = window_size
        self.z_score_threshold = z_score_threshold
        self.historical_data: Dict[str, deque] = {}  # config_id -> deque of values

    def _get_key(self, config_id: int, metric: str) -> str:
        return f"{config_id}:{metric}"

    def record_value(self, config_id: int, metric: str, value: float) -> None:
        """Record a metric value for historical analysis."""
        key = self._get_key(config_id, metric)

        if key not in self.historical_data:
            self.historical_data[key] = deque(maxlen=self.window_size)

        self.historical_data[key].append(value)

    def check_anomaly(self, config_id: int, metric: str, value: float) -> Tuple[bool, float]:
        """Check if a value is anomalous using z-score method."""
        key = self._get_key(config_id, metric)

        if key not in self.historical_data or len(self.historical_data[key]) < 5:
            # Not enough data for anomaly detection
            return False, 0.0

        values = list(self.historical_data[key])
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 1.0

        if stdev == 0:
            return False, 0.0

        z_score = abs((value - mean) / stdev)

        return z_score > self.z_score_threshold, z_score

    def check_threshold(self, value: float, condition: str, threshold: float) -> bool:
        """Check if value violates a threshold condition."""
        if condition == "gt":
            return value > threshold
        elif condition == "gte":
            return value >= threshold
        elif condition == "lt":
            return value < threshold
        elif condition == "lte":
            return value <= threshold
        elif condition == "eq":
            return value == threshold
        return False

    def evaluate_rule_condition(self, metric: str, actual_value: float, condition: str,
                                threshold: float) -> Tuple[bool, float]:
        """Evaluate a complete rule condition (threshold + anomaly)."""
        triggered = False

        if condition == "anomaly":
            triggered, _ = self.check_anomaly(0, metric, actual_value)
        else:
            triggered = self.check_threshold(actual_value, condition, threshold)

        return triggered, actual_value

    def generate_message(self, rule_name: str, metric: str, actual: float,
                         threshold: float, condition: str, severity: str) -> str:
        """Generate human-readable alert message."""
        op_map = {
            "gt": "exceeded", "gte": "reached or exceeded",
            "lt": "below", "lte": "at or below",
            "eq": "equals", "anomaly": "is anomalous"
        }
        op_str = op_map.get(condition, condition)

        return (
            f"[{severity.upper()}] Alert: [{rule_name}] - "
            f"[{metric}] {actual:.2f} {op_str} threshold [{threshold:.2f}]"
        )


anomaly_detector = AnomalyDetector()
