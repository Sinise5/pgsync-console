"""Tests for the PostgreSQL copy table selection and identifier handling."""

from backend.workers.pg_copy import _pgdump_pattern, _tables


def test_copy_collects_distinct_selected_tables_from_schema_tree():
    schema = {
        "schema": "public",
        "main_table": "orders",
        "children": [{"table": "items"}, {"table": "orders"}],
    }

    assert _tables(schema) == [("public", "orders"), ("public", "items")]


def test_pg_dump_pattern_quotes_identifiers():
    assert _pgdump_pattern('odd"schema', 'order"items') == '"odd""schema"."order""items"'
