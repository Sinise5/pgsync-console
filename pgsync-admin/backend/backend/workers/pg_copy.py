"""Copy selected PostgreSQL tables with pg_dump/pg_restore."""

import argparse
import json
import logging
import os
import subprocess
import sys

from backend.db import db
from backend.models import Configuration
from backend.utils.crypto import CryptoService

logger = logging.getLogger(__name__)


def _tables(schema_config: dict) -> list[tuple[str, str]]:
    root = schema_config.get("nodes") or schema_config
    schema = root.get("schema", schema_config.get("schema", "public"))
    selected = []

    def visit(node: dict, default_schema: str) -> None:
        if node.get("table"):
            selected.append((node.get("schema", default_schema), node["table"]))
        for child in node.get("children", []) or []:
            visit(child, default_schema)

    if schema_config.get("main_table"):
        selected.append((schema, schema_config["main_table"]))
        for child in schema_config.get("children", []) or []:
            visit(child, schema)
    else:
        visit(root, schema)
    return list(dict.fromkeys(selected))


def _pgdump_pattern(schema: str, table: str) -> str:
    quote = lambda value: '"' + value.replace('"', '""') + '"'
    return f"{quote(schema)}.{quote(table)}"


def run(config_id: int) -> None:
    crypto = CryptoService()
    db.init_db()
    try:
        with db.get_session() as session:
            config = session.query(Configuration).filter_by(id=config_id).first()
            if not config:
                raise ValueError(f"Configuration {config_id} not found")
            if config.pipeline_type != "pg_copy":
                raise ValueError("Configuration is not a PostgreSQL copy pipeline")
            schema_config = json.loads(config.schema_config or "{}")
            tables = _tables(schema_config)
            if not tables:
                raise ValueError("Select at least one table in Schema Builder before copying")
            target = json.loads(config.target_config or "{}")
            if not target.get("allow_replace"):
                raise ValueError("Enable the destination replacement acknowledgement before copying")
            if (config.source_pg_host, config.source_pg_port, config.source_pg_database) == (
                target.get("host"), int(target.get("port", 5432)), target.get("database")
            ):
                raise ValueError("Source and destination must be different PostgreSQL databases")

            source_password = crypto.decrypt(config.source_pg_password)
            encrypted_target_password = target.get("password", "")
            target_password = crypto.decrypt(encrypted_target_password) if encrypted_target_password else ""
            source = {
                "PGHOST": config.source_pg_host, "PGPORT": str(config.source_pg_port),
                "PGDATABASE": config.source_pg_database, "PGUSER": config.source_pg_user,
                "PGPASSWORD": source_password,
            }
            destination = {
                "PGHOST": target["host"], "PGPORT": str(target.get("port", 5432)),
                "PGDATABASE": target["database"], "PGUSER": target["user"],
                "PGPASSWORD": target_password,
            }
            if target.get("sslmode"):
                destination["PGSSLMODE"] = target["sslmode"]

        dump_env = {**os.environ, **source}
        restore_env = {**os.environ, **destination}
        dump_cmd = ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--dbname", source["PGDATABASE"]]
        for schema, table in tables:
            dump_cmd.extend(["--table", _pgdump_pattern(schema, table)])
        restore_cmd = [
            "pg_restore", "--clean", "--if-exists", "--no-owner", "--no-privileges",
            "--single-transaction", "--exit-on-error", "--dbname", destination["PGDATABASE"], "-",
        ]
        dump = subprocess.Popen(dump_cmd, env=dump_env, stdout=subprocess.PIPE)
        assert dump.stdout is not None
        try:
            restore = subprocess.Popen(restore_cmd, env=restore_env, stdin=dump.stdout)
        except Exception:
            dump.kill()
            raise
        dump.stdout.close()
        restore_code = restore.wait()
        dump_code = dump.wait()
        if dump_code or restore_code:
            raise RuntimeError(f"pg_dump exited {dump_code}; pg_restore exited {restore_code}")
        logger.info("Copied %s selected tables for configuration %s", len(tables), config_id)
    finally:
        db.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-id", required=True, type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        run(args.config_id)
    except Exception as exc:
        logger.exception("PostgreSQL copy failed: %s", exc)
        sys.exit(1)
