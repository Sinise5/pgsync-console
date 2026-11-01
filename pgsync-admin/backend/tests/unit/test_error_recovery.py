"""Tests for retry scheduling and execution dispatch."""

import json
import importlib
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.configuration import Base
from backend.models import Configuration, Execution, ExecutionFailure
from backend.services.error_recovery_service import ErrorRecoveryService, RecoveryStrategy

service_module = importlib.import_module("backend.services.error_recovery_service")


class FakeTimer:
    instances = []

    def __init__(self, delay, function, args=()):
        self.delay = delay
        self.function = function
        self.args = args
        self.started = False
        self.daemon = False
        self.instances.append(self)

    def start(self):
        self.started = True


@pytest.fixture
def recovery_env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'recovery.db'}")
    import backend.models  # Register all tables on Base.
    Base.metadata.create_all(engine)
    db = SimpleNamespace(get_session=sessionmaker(bind=engine))
    monkeypatch.setattr(service_module, "db", db)
    monkeypatch.setattr(service_module.threading, "Timer", FakeTimer)
    FakeTimer.instances.clear()

    with db.get_session() as session:
        config = Configuration(
            name="retry-config", source_pg_host="localhost", source_pg_port=5432,
            source_pg_database="test", source_pg_user="user", source_pg_password="enc",
            target_type="opensearch", target_config="{}", schema_config="{}",
            pgsync_schema_json=json.dumps({"database": {"host": "localhost"}}),
        )
        session.add(config)
        session.flush()
        execution = Execution(config_id=config.id, type="batch", status="failed")
        session.add(execution)
        session.flush()
        failure = ExecutionFailure(
            execution_id=execution.id, config_id=config.id, error_type="ConnectionError",
            error_message="connection lost", is_retriable=True, attempt_number=1, max_retries=3,
            status="pending",
        )
        session.add(failure)
        session.commit()
        config_id, execution_id, failure_id = config.id, execution.id, failure.id

    yield ErrorRecoveryService(), db, config_id, execution_id, failure_id
    engine.dispose()


def test_schedule_retry_sets_state_and_backoff(recovery_env):
    service, db, _, _, failure_id = recovery_env
    scheduled = service.schedule_retry(failure_id, RecoveryStrategy.EXPONENTIAL_BACKOFF)

    assert scheduled is True
    assert FakeTimer.instances[-1].delay == 60
    assert FakeTimer.instances[-1].started is True
    with db.get_session() as session:
        failure = session.query(ExecutionFailure).filter_by(id=failure_id).one()
        assert failure.status == "retrying"
        assert failure.next_retry_at is not None


def test_schedule_retry_rejects_invalid_and_duplicate(recovery_env):
    service, _, _, _, failure_id = recovery_env
    with pytest.raises(ValueError):
        service.schedule_retry(failure_id, "made_up")
    assert service.schedule_retry(failure_id, RecoveryStrategy.IMMEDIATE_RETRY) is True
    assert service.schedule_retry(failure_id, RecoveryStrategy.IMMEDIATE_RETRY) is False


def test_attempt_recovery_starts_a_new_execution(recovery_env, monkeypatch):
    service, db, config_id, _, failure_id = recovery_env
    calls = []

    def start_batch(execution_id, requested_config_id, schema):
        calls.append((execution_id, requested_config_id, schema))
        with db.get_session() as session:
            execution = session.query(Execution).filter_by(id=execution_id).one()
            execution.status = "running"
            execution.pid = 12345
            session.commit()
        return 12345

    monkeypatch.setattr(service_module, "orchestrator", SimpleNamespace(start_batch_migration=start_batch))
    assert service.attempt_recovery(failure_id) is True
    assert calls[0][1:] == (config_id, {"database": {"host": "localhost"}})
    assert FakeTimer.instances[-1].delay == 5  # Monitor the spawned batch process.
    with db.get_session() as session:
        failure = session.query(ExecutionFailure).filter_by(id=failure_id).one()
        retry = session.query(Execution).filter(Execution.id != failure.execution_id).one()
        assert failure.attempt_number == 2
        assert failure.status == "retrying"
        assert retry.status == "running"
        assert retry.pid == 12345


def test_attempt_recovery_dead_letters_missing_schema(recovery_env, monkeypatch):
    service, db, _, _, failure_id = recovery_env
    monkeypatch.setattr(service_module, "orchestrator", SimpleNamespace())
    with db.get_session() as session:
        config = session.query(Configuration).first()
        config.pgsync_schema_json = None
        session.commit()

    assert service.attempt_recovery(failure_id) is False
    with db.get_session() as session:
        failure = session.query(ExecutionFailure).filter_by(id=failure_id).one()
        assert failure.status == "dead_letter"
        assert "generated PGSync schema" in failure.recovery_notes
