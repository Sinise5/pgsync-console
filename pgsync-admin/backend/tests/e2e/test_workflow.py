"""End-to-end persistence workflows without requiring external services."""

import asyncio
import json
from datetime import datetime


def make_config(test_session, name):
    from backend.models import Configuration

    config = Configuration(
        name=name,
        source_pg_host="localhost",
        source_pg_port=5432,
        source_pg_database="test_db",
        source_pg_user="tester",
        source_pg_password="encrypted-test-password",
        target_type="opensearch",
        target_config=json.dumps({"host": "http://localhost:9200"}),
        schema_config=json.dumps({"main_table": "users", "main_columns": ["id"]}),
    )
    test_session.add(config)
    test_session.flush()
    return config


class TestFullWorkflow:
    def test_workflow_discovery_to_config(self, test_session, mock_pg_introspector):
        from backend.models import Configuration

        tables = asyncio.run(mock_pg_introspector.list_tables())
        assert tables == [{"schema": "public", "table": "laporan", "columns": 100}]

        config = make_config(test_session, "e2e_discovery_config")
        assert isinstance(config, Configuration)
        assert config.id > 0
        assert json.loads(config.schema_config)["main_table"] == "users"

    def test_workflow_execution_cycle(self, test_session):
        from backend.models import Execution

        config = make_config(test_session, "e2e_execution_config")
        execution = Execution(config_id=config.id, type="batch", status="running", started_at=datetime.utcnow())
        test_session.add(execution)
        test_session.flush()

        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.synced_docs = 5000
        execution.progress_pct = 100
        test_session.flush()

        assert execution.status == "completed"
        assert execution.rows_processed == 5000
        assert execution.progress_pct == 100

    def test_workflow_failure_tracking(self, test_session):
        from backend.models import Execution, ExecutionFailure

        config = make_config(test_session, "e2e_failure_config")
        execution = Execution(config_id=config.id, type="batch", status="failed")
        test_session.add(execution)
        test_session.flush()
        failure = ExecutionFailure(
            execution_id=execution.id,
            config_id=config.id,
            error_type="ConnectionError",
            error_message="Connection timeout after 30s",
            is_retriable=True,
            status="pending",
        )
        test_session.add(failure)
        test_session.flush()

        assert failure.status == "pending"
        assert "timeout" in failure.error_message.lower()
        # A recorded failure remains pending until a retry is scheduled and started.
        assert failure.recovered_at is None


class TestMultiFeatureWorkflow:
    def test_workflow_with_jobs(self, test_session):
        from backend.models import Job

        config = make_config(test_session, "e2e_job_config")
        job = Job(
            name="e2e_job",
            config_id=config.id,
            cron_expression="0 */6 * * *",
            enabled=True,
            execution_type="batch",
        )
        test_session.add(job)
        test_session.flush()

        assert job.config_id == config.id
        assert job.enabled is True
        assert job.cron_expression == "0 */6 * * *"

    def test_workflow_alert_on_failure(self, test_session):
        from backend.models import AlertEvaluation, AlertRule

        rule = AlertRule(
            name="e2e_failure_alert",
            metric="execution_error_rate",
            condition="gt",
            threshold=5,
            enabled=True,
        )
        test_session.add(rule)
        test_session.flush()
        evaluation = AlertEvaluation(
            rule_id=rule.id,
            actual_value=8,
            metric="execution_error_rate",
            condition="gt",
            threshold=5,
            triggered=True,
            evaluated_at=datetime.utcnow(),
        )
        test_session.add(evaluation)
        test_session.flush()

        assert evaluation.triggered is True
        assert evaluation.actual_value > evaluation.threshold

    def test_workflow_full_lifecycle(self, test_session, mock_pg_introspector):
        from backend.models import Execution

        tables = asyncio.run(mock_pg_introspector.list_tables())
        assert tables
        config = make_config(test_session, "e2e_full_lifecycle")
        execution = Execution(config_id=config.id, type="cdc", status="running", started_at=datetime.utcnow())
        test_session.add(execution)
        test_session.flush()
        execution.status = "completed"
        execution.completed_at = datetime.utcnow()
        execution.synced_docs = len(tables) * 100
        execution.progress_pct = 100
        test_session.flush()

        assert execution.status == "completed"
        assert execution.synced_docs == 100
