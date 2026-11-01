"""Unit tests for schema generator."""

import json
import pytest
from backend.services import SchemaGenerator, PluginGenerator


# Test schema configuration
TEST_SCHEMA = {
    "main_table": "laporan",
    "main_columns": ["id", "nomor", "judul"],
    "children": [
        {
            "table": "laporan_isi",
            "fields": ["laporan_id", "isi", "apa", "mengapa"],
            "relationship": {
                "type": "one_to_many",
                "variant": "object",
                "foreign_key": {"parent": "id", "child": "laporan_id"},
            },
        }
    ],
    "fk_mappings": {
        "laporan_isi_id": {"table": "laporan_isi", "id_col": "id", "name_col": "isi"},
    },
}


class TestSchemaGenerator:
    """Test schema generation."""

    def test_generate_simple_schema(self):
        """Test generating simple schema without children."""
        config = {
            "name": "test",
            "source_pg_database": "test_db",
            "target_config": json.dumps({"type": "opensearch"}),
            "schema_config": json.dumps({
                "main_table": "laporan",
                "main_columns": ["id", "nomor"],
                "children": [],
            }),
        }

        gen = SchemaGenerator()
        schema = gen.generate(config)

        assert schema["database"] == "test_db"
        assert schema["index"] == "laporan"
        assert schema["nodes"]["table"] == "laporan"
        assert schema["nodes"]["columns"] == ["id", "nomor"]

    def test_generate_schema_with_children(self):
        """Test generating schema with child tables."""
        config = {
            "name": "test",
            "source_pg_database": "test_db",
            "target_config": json.dumps({"type": "opensearch"}),
            "schema_config": json.dumps(TEST_SCHEMA),
        }

        gen = SchemaGenerator()
        schema = gen.generate(config)

        assert len(schema["nodes"]["children"]) == 1
        assert schema["nodes"]["children"][0]["table"] == "laporan_isi"

    def test_mysql_database_is_applied_to_every_node(self):
        config = {
            "name": "mysql-search",
            "source_pg_database": "store",
            "source_type": "mysql",
            "target_config": json.dumps({"type": "opensearch"}),
            "schema_config": json.dumps({
                "main_table": "orders",
                "children": [{
                    "table": "items",
                    "relationship": {"foreign_key": {"child": "order_id", "parent": "id"}},
                    "children": [{"table": "variants"}],
                }],
            }),
        }

        schema = SchemaGenerator().generate(config)

        assert schema["nodes"]["schema"] == "store"
        assert schema["nodes"]["children"][0]["schema"] == "store"
        assert schema["nodes"]["children"][0]["children"][0]["schema"] == "store"

    def test_validate_valid_schema(self):
        """Test validation of valid schema."""
        config = {
            "name": "test",
            "source_pg_database": "test_db",
            "target_config": json.dumps({"type": "opensearch"}),
            "schema_config": json.dumps(TEST_SCHEMA),
        }

        gen = SchemaGenerator()
        schema = gen.generate(config)
        result = gen.validate(schema)

        assert result["is_valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_missing_columns(self):
        """Test validation warns about missing columns."""
        config = {
            "database": "test_db",
            "index": "laporan",
            "nodes": {
                "table": "laporan",
                "schema": "public",
                # Missing columns
            },
        }

        gen = SchemaGenerator()
        result = gen.validate(config)

        assert len(result["warnings"]) > 0


class TestPluginGenerator:
    """Test plugin code generation."""

    def test_generate_plugin_with_denormalization(self):
        """Test generating plugin with FK denormalization."""
        config = {
            "name": "laporan-sync",
            "source_pg_database": "test_db",
            "target_config": json.dumps({"type": "opensearch"}),
            "schema_config": json.dumps({
                "main_table": "laporan",
                "fk_mappings": {
                    "status_id": {
                        "table": "status",
                        "id_col": "id",
                        "name_col": "nama",
                    }
                },
            }),
        }

        gen = PluginGenerator()
        code = gen.generate(config)

        assert "LaporanSyncDenormalize" in code
        assert "class LaporanSyncDenormalize(Plugin)" in code
        assert "def transform" in code
        assert "status_id" in code

    def test_generate_plugin_no_denormalization(self):
        """Test plugin generation with no FK mappings."""
        config = {
            "name": "simple",
            "source_pg_database": "test_db",
            "target_config": json.dumps({"type": "opensearch"}),
            "schema_config": json.dumps({
                "main_table": "users",
                "fk_mappings": {},
            }),
        }

        gen = PluginGenerator()
        code = gen.generate(config)

        # Empty string for no denormalization
        assert code == ""
