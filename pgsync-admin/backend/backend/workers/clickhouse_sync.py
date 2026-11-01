"""Run ClickHouse mirror bootstrap and initial backfill."""

import argparse
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


def run(schema_file: str) -> None:
    bootstrap = subprocess.run(["pgsync-clickhouse", "-c", schema_file, "--bootstrap"], check=False)
    if bootstrap.returncode:
        raise RuntimeError(f"ClickHouse bootstrap exited with status {bootstrap.returncode}")
    initial_sync = subprocess.run(["pgsync-clickhouse", "-c", schema_file], check=False)
    if initial_sync.returncode:
        raise RuntimeError(f"ClickHouse initial sync exited with status {initial_sync.returncode}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema-file", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        run(args.schema_file)
    except Exception as exc:
        logger.exception("ClickHouse sync failed: %s", exc)
        sys.exit(1)
