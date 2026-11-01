"""Unit tests for validators."""

import pytest
from backend.utils.validators import validate_config_name, validate_db_connection_params


class TestValidators:
    """Test validation functions."""

    def test_validate_config_name_valid(self):
        """Test valid config names."""
        assert validate_config_name("my-config") == "my-config"
        assert validate_config_name("config_123") == "config_123"
        assert validate_config_name("Config") == "Config"

    def test_validate_config_name_invalid(self):
        """Test invalid config names."""
        with pytest.raises(ValueError):
            validate_config_name("")  # Empty

        with pytest.raises(ValueError):
            validate_config_name("a" * 129)  # Too long

        with pytest.raises(ValueError):
            validate_config_name("config@invalid")  # Invalid chars

        with pytest.raises(ValueError):
            validate_config_name("config name")  # Space

    def test_validate_db_connection_params_valid(self):
        """Test valid connection params."""
        params = {
            "host": "localhost",
            "port": 5432,
            "database": "mydb",
            "user": "postgres",
            "password": "password",
        }
        result = validate_db_connection_params(params)

        assert result["host"] == "localhost"
        assert result["port"] == 5432
        assert result["database"] == "mydb"

    def test_validate_db_connection_params_missing_field(self):
        """Test missing required fields."""
        params = {
            "host": "localhost",
            "port": 5432,
            # Missing database, user, password
        }

        with pytest.raises(ValueError):
            validate_db_connection_params(params)

    def test_validate_db_connection_params_invalid_port(self):
        """Test invalid port."""
        params = {
            "host": "localhost",
            "port": 99999,  # Out of range
            "database": "mydb",
            "user": "postgres",
            "password": "password",
        }

        with pytest.raises(ValueError):
            validate_db_connection_params(params)

    def test_validate_db_connection_params_port_string(self):
        """Test port as string."""
        params = {
            "host": "localhost",
            "port": "5432",  # String should be converted
            "database": "mydb",
            "user": "postgres",
            "password": "password",
        }

        result = validate_db_connection_params(params)
        assert result["port"] == 5432
        assert isinstance(result["port"], int)
