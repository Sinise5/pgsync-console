"""Tests for the scheduled job model and cron validation."""

from datetime import datetime

from backend.services.auth_service import InputValidator


def make_job(name="test_job", config_id=1, enabled=True):
    from backend.models import Job

    return Job(
        name=name,
        config_id=config_id,
        cron_expression="0 * * * *",
        enabled=enabled,
        execution_type="batch",
        max_retries=3,
        timeout_seconds=3600,
    )


class TestSchedulerService:
    def test_job_create_and_serialize(self, test_session):
        job = make_job()
        test_session.add(job)
        test_session.flush()

        data = job.to_dict()
        assert job.id > 0
        assert data["name"] == "test_job"
        assert data["cron_expression"] == "0 * * * *"
        assert data["execution_type"] == "batch"
        assert data["max_retries"] == 3

    def test_job_enabled_and_run_tracking(self, test_session):
        enabled = make_job("enabled")
        disabled = make_job("disabled", enabled=False)
        test_session.add_all([enabled, disabled])
        test_session.flush()

        now = datetime.utcnow()
        enabled.last_run = now
        enabled.run_count += 1
        test_session.flush()

        assert test_session.query(type(enabled)).filter_by(enabled=True).count() == 1
        assert test_session.query(type(disabled)).filter_by(enabled=False).count() == 1
        assert enabled.last_run == now
        assert enabled.run_count == 1

    def test_cron_validation_uses_scheduler_parser(self):
        assert InputValidator.validate_cron_expression("*/5 * * * *") is True
        assert InputValidator.validate_cron_expression("0 9 * * 1-5") is True
        assert InputValidator.validate_cron_expression("invalid") is False
        assert InputValidator.validate_cron_expression("0 25 * * *") is False
