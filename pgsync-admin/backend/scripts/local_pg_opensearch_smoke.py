"""Exercise the PGSync Admin connection and batch-sync path against local demo services."""

import json
import time
from pathlib import Path

import httpx

from backend.config import settings

API = "http://127.0.0.1:3505/api"
PG = {
    "type": "postgres",
    "host": "demo-postgres",
    "port": 5432,
    "database": "pgsync_demo",
    "user": "pgsync_demo",
    "password": "pgsync_demo_password",
}
OS = {
    "type": "opensearch",
    "host": "demo-opensearch",
    "port": 9200,
    "user": "",
    "password": "",
    "scheme": "http",
    "verify_certs": False,
}
CONFIG_NAME = "local_pg_to_opensearch_demo"
INDEX = "local_customers"


def require(response: httpx.Response, action: str) -> dict:
    if not response.is_success:
        raise RuntimeError(f"{action} failed ({response.status_code}): {response.text[:1200]}")
    return response.json() if response.content else {}


def main() -> None:
    if not settings.auth_admin_username or not settings.auth_admin_password:
        raise RuntimeError("Admin login credentials are not configured in the backend container")

    with httpx.Client(timeout=20) as client:
        login = require(client.post(f"{API}/auth/login", json={
            "username": settings.auth_admin_username,
            "password": settings.auth_admin_password,
        }), "Admin login")
        client.headers["Authorization"] = f"Bearer {login['token']}"
        print("PASS admin login")

        source_test = require(client.post(f"{API}/discover/test", json=PG), "PostgreSQL connection test")
        if source_test.get("status") != "connected":
            raise RuntimeError("PostgreSQL connection test did not return connected")
        print(f"PASS source connection ({source_test['server'].get('table_count')} tables)")

        target_test = require(client.post(f"{API}/discover/test-target", json=OS), "OpenSearch connection test")
        if target_test.get("status") != "connected":
            raise RuntimeError("OpenSearch connection test did not return connected")
        print(f"PASS destination connection (OpenSearch {target_test['server'].get('version')})")

        discovered = require(client.post(f"{API}/discover/schema", json={**PG, "schema": "public"}), "PostgreSQL schema discovery")
        table_names = {table["name"] for table in discovered.get("tables", [])}
        if not {"customers", "orders"}.issubset(table_names):
            raise RuntimeError(f"Expected demo tables were not discovered: {sorted(table_names)}")
        relation = next((item for item in discovered.get("relationships", [])
                         if item["source_table"] == "orders" and item["target_table"] == "customers"), None)
        if not relation:
            raise RuntimeError("The orders → customers foreign key was not discovered")
        print("PASS schema and foreign-key discovery")

        schema = {
            "index": INDEX,
            "main_table": "customers",
            "main_columns": ["id", "name", "email", "created_at", "updated_at"],
            "children": [{
                "table": "orders",
                "fields": ["id", "customer_id", "order_number", "total", "status", "created_at", "updated_at"],
                "relationship": {
                    "variant": "object",
                    "type": "one_to_many",
                    "foreign_key": {"child": relation["source_column"], "parent": relation["target_column"]},
                },
            }],
            "fk_mappings": {},
        }
        configs = require(client.get(f"{API}/config/list"), "Configuration list").get("configs", [])
        existing = next((item for item in configs if item["name"] == CONFIG_NAME), None)
        config_payload = {
            "name": CONFIG_NAME,
            "description": "Local PostgreSQL → OpenSearch smoke-test sample",
            "source": PG,
            "target": {**OS, "tables": []},
            "schema": {},
        }
        if existing:
            config_id = existing["id"]
            require(client.put(f"{API}/config/{config_id}", json={
                "source": PG,
                "target": {**OS, "tables": []},
                "schema_config": json.dumps(schema),
                "description": config_payload["description"],
            }), "Sample configuration update")
        else:
            created = require(client.post(f"{API}/config/new", json={**config_payload, "schema": schema}), "Sample configuration creation")
            config_id = created["id"]
            require(client.put(f"{API}/config/{config_id}", json={"schema_config": json.dumps(schema)}), "Sample schema save")
        require(client.get(f"{API}/config/{config_id}"), "Sample configuration readback")
        print(f"PASS configuration saved and read back (id={config_id})")

        execution = require(client.post(f"{API}/execution/batch", json={"config_id": config_id}), "PGSync batch start")
        execution_id = execution["execution_id"]
        deadline = time.monotonic() + 120
        status = "running"
        while time.monotonic() < deadline:
            status_data = require(client.get(f"{API}/execution/{execution_id}/status"), "Execution status")
            status = status_data.get("status", "unknown")
            if status in {"completed", "failed", "stopped", "paused"}:
                break
            time.sleep(2)

        log_path = Path(f"/tmp/pgsync-admin-execution-{execution_id}.log")
        log_tail = "\n".join(log_path.read_text(errors="replace").splitlines()[-35:]) if log_path.exists() else "(execution log not found)"
        if status != "completed":
            raise RuntimeError(f"PGSync execution {execution_id} ended as {status}. Recent log:\n{log_tail}")
        print(f"PASS PGSync execution completed (execution_id={execution_id})")

        deadline = time.monotonic() + 30
        hits = []
        while time.monotonic() < deadline:
            result = client.get(f"http://demo-opensearch:9200/{INDEX}/_search", params={"size": 10})
            if result.is_success:
                hits = result.json().get("hits", {}).get("hits", [])
                if len(hits) >= 3:
                    break
            time.sleep(1)
        if len(hits) < 3:
            raise RuntimeError(f"Expected 3 customer documents in OpenSearch, found {len(hits)}. Recent log:\n{log_tail}")
        if not any("orders" in hit.get("_source", {}) for hit in hits):
            raise RuntimeError("Customer documents were indexed, but no related orders were included")
        print(f"PASS OpenSearch contains {len(hits)} customer documents with related orders (index={INDEX})")
        print(f"Sample configuration is available at http://localhost:3507/config/{config_id}")


if __name__ == "__main__":
    main()
