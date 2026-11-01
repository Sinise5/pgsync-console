"""Test configuration and fixtures."""

import os
import sys
import pytest
import tempfile
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Mock clickhouse_driver before any test imports resolve it
sys.modules["clickhouse_driver"] = MagicMock()
sys.modules["clickhouse_driver.client"] = MagicMock()
sys.modules["clickhouse_driver.client"].Client = MagicMock()

from backend.models.configuration import Base
from backend.db.sqlite import SQLiteDB


@pytest.fixture(scope="session")
def test_db_path():
    """Create temporary test database."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture(scope="session")
def test_engine(test_db_path):
    """Create test database engine."""
    engine = create_engine(f"sqlite:///{test_db_path}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def test_session(test_engine):
    """Create test database session with automatic rollback."""
    connection = test_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def test_db(test_session, monkeypatch):
    """Mock database instance for tests."""
    class TestDatabase(SQLiteDB):
        def get_session(self):
            return test_session

    test_db_instance = TestDatabase()
    monkeypatch.setattr("backend.db.sqlite.db", test_db_instance)
    return test_db_instance


@pytest.fixture
def sample_config_data():
    """Sample configuration data for tests."""
    return {
        "name": "test_config",
        "source_host": "localhost",
        "source_port": 5432,
        "source_database": "siitpartisi",
        "source_user": "postgres",
        "source_tables": ["public.laporan"],
        "target_host": "localhost",
        "target_port": 9200,
        "target_index": "test_laporan",
    }


@pytest.fixture
def sample_job_data():
    """Sample job data for tests."""
    return {
        "name": "test_job",
        "job_type": "cron",
        "config_id": 1,
        "schedule": "0 * * * *",
        "enabled": True,
    }


@pytest.fixture
def mock_clickhouse(monkeypatch):
    """Mock ClickHouse client."""
    class MockClickHouseClient:
        def insert(self, table, data):
            return len(data)

        def query(self, sql):
            return []

    mock_client = MockClickHouseClient()
    monkeypatch.setattr(
        "backend.services.clickhouse_client.clickhouse_client",
        mock_client
    )
    return mock_client


@pytest.fixture
def mock_pg_introspector():
    """Mock PostgreSQL introspection calls without patching package exports."""
    class MockIntrospector:
        async def list_tables(self, schema="public"):
            return [
                {"schema": "public", "table": "laporan", "columns": 100}
            ]

        async def get_table_schema(self, table):
            return {
                "columns": [
                    {"name": "id", "type": "integer", "primary_key": True},
                    {"name": "created_at", "type": "timestamp"},
                ],
                "primary_keys": ["id"],
            }

    return MockIntrospector()
