"""Manage one-way PostgreSQL logical replication subscriptions."""

import json
import logging
from typing import Any

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from backend.models import Configuration
from backend.utils.crypto import CryptoService

logger = logging.getLogger(__name__)


class PostgresReplicationService:
    def __init__(self) -> None:
        self.crypto = CryptoService()

    @staticmethod
    def _names(config: Configuration) -> tuple[str, str]:
        return f"pgsync_pub_{config.id}", f"pgsync_sub_{config.id}"

    @staticmethod
    def _tables(schema_config: dict[str, Any]) -> list[tuple[str, str]]:
        root = schema_config.get("nodes") or schema_config
        schema = root.get("schema", schema_config.get("schema", "public"))
        names: list[tuple[str, str]] = []

        def visit(node: dict[str, Any], parent_schema: str) -> None:
            table = node.get("table")
            if table:
                names.append((node.get("schema", parent_schema), table))
            for child in node.get("children", []) or []:
                visit(child, parent_schema)

        if schema_config.get("main_table"):
            names.append((schema, schema_config["main_table"]))
            for child in schema_config.get("children", []) or []:
                visit(child, schema)
        else:
            visit(root, schema)
        return list(dict.fromkeys(names))

    def _source_connection(self, config: Configuration) -> dict[str, Any]:
        return {
            "host": config.source_pg_host,
            "port": config.source_pg_port,
            "dbname": config.source_pg_database,
            "user": config.source_pg_user,
            "password": self.crypto.decrypt(config.source_pg_password),
        }

    def _target_connection(self, config: Configuration) -> dict[str, Any]:
        target = json.loads(config.target_config or "{}")
        encrypted = target.get("password", "")
        password = self.crypto.decrypt(encrypted) if encrypted and encrypted != "***" else ""
        return {
            "host": target["host"], "port": int(target.get("port", 5432)),
            "dbname": target["database"], "user": target["user"], "password": password,
            "sslmode": target.get("sslmode", "prefer"),
        }

    def start(self, config: Configuration) -> str:
        """Create or enable the source publication and destination subscription."""
        schema_config = json.loads(config.schema_config or "{}")
        tables = self._tables(schema_config)
        if not tables:
            raise ValueError("Select at least one table in Schema Builder before starting replication")

        source = self._source_connection(config)
        target = self._target_connection(config)
        if (source["host"], source["port"], source["dbname"]) == (target["host"], target["port"], target["dbname"]):
            raise ValueError("Source and destination must be different PostgreSQL databases")

        publication_name, subscription_name = self._names(config)
        identifiers = [sql.Identifier(schema, table) for schema, table in tables]
        with psycopg.connect(**source) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_publication WHERE pubname = %s", (publication_name,))
            exists = cursor.fetchone() is not None
            if exists:
                cursor.execute(
                    sql.SQL("ALTER PUBLICATION {} SET TABLE {}").format(
                        sql.Identifier(publication_name), sql.SQL(", ").join(identifiers)
                    )
                )
            else:
                cursor.execute(
                    sql.SQL("CREATE PUBLICATION {} FOR TABLE {}").format(
                        sql.Identifier(publication_name), sql.SQL(", ").join(identifiers)
                    )
                )

        source_conninfo = make_conninfo(**source)
        with psycopg.connect(**target, autocommit=True) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_subscription WHERE subname = %s", (subscription_name,))
            exists = cursor.fetchone() is not None
            if exists:
                cursor.execute(sql.SQL("ALTER SUBSCRIPTION {} ENABLE").format(sql.Identifier(subscription_name)))
            else:
                cursor.execute(
                    sql.SQL("CREATE SUBSCRIPTION {} CONNECTION {} PUBLICATION {} WITH (copy_data = true)").format(
                        sql.Identifier(subscription_name), sql.Literal(source_conninfo), sql.Identifier(publication_name)
                    )
                )
        logger.info("Started PostgreSQL subscription %s for config %s", subscription_name, config.id)
        return subscription_name

    def stop(self, config: Configuration) -> str:
        """Pause replication while preserving the subscription and slot."""
        _, subscription_name = self._names(config)
        with psycopg.connect(**self._target_connection(config), autocommit=True) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_subscription WHERE subname = %s", (subscription_name,))
            if cursor.fetchone() is None:
                raise ValueError("Replication subscription is not configured")
            cursor.execute(sql.SQL("ALTER SUBSCRIPTION {} DISABLE").format(sql.Identifier(subscription_name)))
        logger.info("Paused PostgreSQL subscription %s", subscription_name)
        return subscription_name


postgres_replication_service = PostgresReplicationService()
