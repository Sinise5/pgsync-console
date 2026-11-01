"""Tests for the current configuration persistence contract."""

import json

import pytest
from sqlalchemy.exc import IntegrityError


def make_config(name):
    from backend.models import Configuration

    return Configuration(
        name=name,
        source_pg_host="localhost",
        source_pg_port=5432,
        source_pg_database="test_db",
        source_pg_user="tester",
        source_pg_password="encrypted-value",
        target_type="opensearch",
        target_config=json.dumps({"host": "http://localhost:9200"}),
        schema_config=json.dumps({"main_table": "users", "main_columns": ["id"]}),
    )


class TestConfiguration:
    def test_config_create_and_defaults(self, test_session):
        config = make_config("test_config")
        test_session.add(config)
        test_session.flush()

        assert config.id > 0
        assert config.name == "test_config"
        assert config.target_type == "opensearch"
        assert config.version == 1
        assert config.is_active is True
        assert config.created_at is not None

    def test_config_update_and_query(self, test_session):
        config = make_config("before_update")
        test_session.add(config)
        test_session.flush()

        config.name = "after_update"
        config.schema_config = json.dumps({"main_table": "orders"})
        test_session.flush()

        loaded = test_session.query(type(config)).filter_by(name="after_update").one()
        assert json.loads(loaded.schema_config)["main_table"] == "orders"
        assert test_session.query(type(config)).filter_by(name="missing").first() is None

    def test_config_name_must_be_unique(self, test_session):
        from backend.models import Configuration

        test_session.add(make_config("unique_name"))
        test_session.flush()
        with pytest.raises(IntegrityError):
            with test_session.begin_nested():
                test_session.add(make_config("unique_name"))
                test_session.flush()

    def test_config_soft_delete_flag(self, test_session):
        config = make_config("soft_delete")
        test_session.add(config)
        test_session.flush()
        config.is_active = False
        test_session.flush()

        loaded = test_session.query(type(config)).filter_by(id=config.id).one()
        assert loaded.is_active is False

    def test_config_connection_validation(self):
        from backend.utils import validate_db_connection_params

        valid = validate_db_connection_params({
            "host": "localhost", "port": "5432", "database": "test_db",
            "user": "tester", "password": "secret",
        })
        assert valid["port"] == 5432
        with pytest.raises(ValueError):
            validate_db_connection_params({"host": "localhost", "port": 70000})
