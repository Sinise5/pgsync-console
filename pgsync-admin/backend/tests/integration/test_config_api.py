"""Integration tests for configuration API."""

import json
import pytest
from backend.models import Configuration


class TestConfigAPI:
    """Integration tests for config API."""

    def test_create_config_success(self, test_session):
        """Test creating configuration."""
        config = Configuration(
            name="test-config",
            description="Test",
            source_pg_host="localhost",
            source_pg_port=5432,
            source_pg_database="test_db",
            source_pg_user="postgres",
            source_pg_password="encrypted_password",
            target_type="opensearch",
            target_config=json.dumps({"host": "localhost"}),
            schema_config=json.dumps({"main_table": "users"}),
        )

        test_session.add(config)
        test_session.flush()
        test_session.refresh(config)

        assert config.id is not None
        assert config.name == "test-config"
        assert config.version == 1

    def test_list_configs(self, test_session):
        """Test listing configurations."""
        # Create test configs
        for i in range(3):
            config = Configuration(
                name=f"config-{i}",
                source_pg_host="localhost",
                source_pg_port=5432,
                source_pg_database=f"db_{i}",
                source_pg_user="postgres",
                source_pg_password="encrypted",
                target_type="opensearch",
                target_config=json.dumps({}),
                schema_config=json.dumps({}),
                is_active=True,
            )
            test_session.add(config)

        # Query
        configs = test_session.query(Configuration).filter(
            Configuration.is_active == True
        ).all()

        assert len(configs) == 3
