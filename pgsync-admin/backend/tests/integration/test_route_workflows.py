"""Route-level integration tests using a temporary SQLite database."""

import asyncio
import importlib
import json
import re
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.configuration import Base


class RouteRegistry:
    """Small Robyn registration adapter for invoking the real route handlers."""

    def __init__(self):
        self.routes = []

    def _register(self, method, route):
        def decorator(handler):
            self.routes.append((method, route, handler))
            return handler
        return decorator

    def get(self, route):
        return self._register("GET", route)

    def post(self, route):
        return self._register("POST", route)

    def put(self, route):
        return self._register("PUT", route)

    def patch(self, route):
        return self._register("PATCH", route)

    def delete(self, route):
        return self._register("DELETE", route)

    def websocket(self, route):
        return self._register("WEBSOCKET", route)

    async def request(self, method, path, payload=None, query=None):
        path_only = path.split("?", 1)[0]
        for registered_method, route, handler in self.routes:
            if method != registered_method:
                continue
            names = re.findall(r":([A-Za-z_]+)|\{([A-Za-z_]+)\}", route)
            route_pattern = re.sub(r":([A-Za-z_]+)|\{([A-Za-z_]+)\}", r"([^/]+)", route)
            match = re.fullmatch(route_pattern, path_only)
            if not match:
                continue
            keys = [next(name for name in pair if name) for pair in names]
            params = dict(zip(keys, match.groups()))
            class QueryParams(dict):
                def get(self, key, default):
                    if default is not None and not isinstance(default, str):
                        raise TypeError("query parameter defaults must be strings")
                    return super().get(key, default)

            request = SimpleNamespace(
                body=json.dumps(payload or {}).encode(),
                path_params=params,
                query_params=QueryParams(query or {}),
                url=SimpleNamespace(path=path_only),
                headers={},
            )
            return await handler(request)
        raise AssertionError(f"No handler registered for {method} {path_only}")


@pytest.fixture
def route_api(tmp_path, monkeypatch):
    """Register route groups against an isolated SQLite database."""
    engine = create_engine(f"sqlite:///{tmp_path / 'routes.db'}")
    import backend.models  # Register every table on the shared declarative Base.
    Base.metadata.create_all(engine)
    db = SimpleNamespace(get_session=sessionmaker(bind=engine))

    from backend.routes import config as config_routes_module
    from backend.routes import dashboards as dashboards_routes_module
    from backend.routes import execution as execution_routes_module
    from backend.routes import alerts as alerts_routes_module
    from backend.routes import cdc as cdc_routes_module
    from backend.routes import discovery as discovery_routes_module
    from backend.routes import jobs as jobs_routes_module
    from backend.routes import error_recovery as recovery_routes_module
    from backend.routes.config import config_routes
    from backend.routes.dashboards import dashboard_routes
    from backend.routes.execution import execution_routes
    from backend.routes.logs import logs_routes
    from backend.routes.reports import reports_routes
    from backend.routes.alerts import alerts_routes
    from backend.routes.cdc import cdc_routes
    from backend.routes.discovery import discovery_routes
    from backend.routes.jobs import jobs_routes
    from backend.routes.error_recovery import error_recovery_routes
    from backend.services.error_recovery_service import ErrorRecoveryService
    recovery_service_module = importlib.import_module("backend.services.error_recovery_service")
    from backend.services.scheduler_service import SchedulerService
    scheduler_service_module = importlib.import_module("backend.services.scheduler_service")

    monkeypatch.setattr(config_routes_module, "db", db)
    monkeypatch.setattr(dashboards_routes_module, "db", db)
    monkeypatch.setattr(execution_routes_module, "db", db)
    monkeypatch.setattr(cdc_routes_module, "db", db)
    monkeypatch.setattr(alerts_routes_module, "db", db)
    monkeypatch.setattr(scheduler_service_module, "db", db)
    monkeypatch.setattr(recovery_service_module, "db", db)
    scheduler = SchedulerService()
    recovery_service = ErrorRecoveryService()
    monkeypatch.setattr(jobs_routes_module, "scheduler_service", scheduler)
    monkeypatch.setattr(recovery_routes_module, "error_recovery_service", recovery_service)

    app = RouteRegistry()
    app.db = db
    app.recovery_service = recovery_service
    config_routes(app)
    dashboard_routes(app)
    execution_routes(app)
    cdc_routes(app)
    discovery_routes(app)
    logs_routes(app)
    reports_routes(app)
    alerts_routes(app)
    jobs_routes(app)
    error_recovery_routes(app)
    yield app
    engine.dispose()


def invoke(app, method, path, payload=None, query=None):
    return asyncio.run(app.request(method, path, payload, query))


def response_json(response):
    return json.loads(response.description)


def create_configuration(app, name="integration-config"):
    response = invoke(app, "POST", "/api/config/new", {
        "name": name,
        "source": {
            "host": "localhost", "port": 5432, "database": "test_db",
            "user": "tester", "password": "source-secret",
        },
        "target": {"type": "opensearch", "host": "http://localhost:9200", "password": "target-secret"},
        "schema": {"main_table": "users", "main_columns": ["id"]},
    })
    assert response.status_code == 201
    return response_json(response)


def test_configuration_route_create_read_update_and_delete(route_api):
    created = create_configuration(route_api)
    config_id = created["id"]

    listed = invoke(route_api, "GET", "/api/config/list")
    assert listed.status_code == 200
    assert response_json(listed)["configs"][0]["is_active"] is True

    detail = invoke(route_api, "GET", f"/api/config/{config_id}")
    assert detail.status_code == 200
    detail_data = response_json(detail)
    assert detail_data["source"]["password"] == "***"
    assert detail_data["schema"]["main_table"] == "users"

    updated = invoke(route_api, "PUT", f"/api/config/{config_id}", {
        "name": "integration-config-renamed",
        "target": {"password": "", "host": "http://localhost:9201"},
    })
    assert updated.status_code == 200

    after_update = response_json(invoke(route_api, "GET", f"/api/config/{config_id}"))
    assert after_update["name"] == "integration-config-renamed"
    assert after_update["target"]["password"] == "***"

    deleted = invoke(route_api, "DELETE", f"/api/config/{config_id}")
    assert deleted.status_code == 200
    assert response_json(invoke(route_api, "GET", "/api/config/list"))["configs"] == []


@pytest.mark.parametrize(("name", "pipeline", "source_type", "target"), [
    ("mysql-search", "pg_search", "mysql", {"type": "elasticsearch", "host": "search", "port": 9200}),
    ("pg-clickhouse", "pg_clickhouse", "postgres", {"type": "clickhouse", "host": "ch", "port": 8123, "database": "analytics"}),
    ("pg-continuous", "pg_replication", "postgres", {"type": "postgres", "host": "target", "port": 5432, "database": "replica", "user": "writer", "password": "secret"}),
    ("pg-copy", "pg_copy", "postgres", {"type": "postgres", "host": "target", "port": 5432, "database": "copy", "user": "writer", "password": "secret", "allow_replace": True}),
])
def test_configuration_accepts_each_supported_pipeline(route_api, name, pipeline, source_type, target):
    source_port = 3306 if source_type == "mysql" else 5432
    response = invoke(route_api, "POST", "/api/config/new", {
        "name": name,
        "pipeline_type": pipeline,
        "source": {"type": source_type, "host": "source", "port": source_port,
                    "database": "app", "user": "reader", "password": "secret"},
        "target": target,
        "schema": {"main_table": "orders", "main_columns": ["id"], "children": []},
    })

    assert response.status_code == 201
    detail = response_json(invoke(route_api, "GET", f"/api/config/{response_json(response)['id']}"))
    assert detail["pipeline_type"] == pipeline
    assert detail["source"]["type"] == source_type
    assert detail["target"]["type"] == target["type"]


def test_postgres_copy_cannot_start_from_continuous_sync_route(route_api):
    created = invoke(route_api, "POST", "/api/config/new", {
        "name": "copy-no-cdc", "pipeline_type": "pg_copy",
        "source": {"host": "source", "port": 5432, "database": "app", "user": "reader", "password": "secret"},
        "target": {"type": "postgres", "host": "target", "port": 5432, "database": "copy", "user": "writer", "password": "secret", "allow_replace": True},
    })
    assert created.status_code == 201
    config_id = response_json(created)["id"]

    response = invoke(route_api, "POST", f"/api/cdc/{config_id}/start")

    assert response.status_code == 400
    assert "batch operation" in response_json(response)["error"]


def test_postgres_copy_schedule_rejects_cdc_execution(route_api):
    created = invoke(route_api, "POST", "/api/config/new", {
        "name": "copy-scheduled", "pipeline_type": "pg_copy",
        "source": {"host": "source", "port": 5432, "database": "app", "user": "reader", "password": "secret"},
        "target": {"type": "postgres", "host": "target", "port": 5432, "database": "copy", "user": "writer", "password": "secret", "allow_replace": True},
    })
    config_id = response_json(created)["id"]

    response = invoke(route_api, "POST", "/api/jobs", {
        "name": "invalid-copy-cdc", "config_id": config_id,
        "cron_expression": "0 2 * * *", "execution_type": "cdc",
    })

    assert response.status_code == 400
    assert "batch schedules only" in response_json(response)["error"]


def test_cdc_route_starts_and_stops_configured_pipeline(route_api, monkeypatch):
    import backend.routes.cdc as cdc_module

    created = invoke(route_api, "POST", "/api/config/new", {
        "name": "clickhouse-cdc", "pipeline_type": "pg_clickhouse",
        "source": {"host": "source", "port": 5432, "database": "app", "user": "reader", "password": "secret"},
        "target": {"type": "clickhouse", "host": "ch", "port": 8123, "database": "analytics"},
        "schema": {"main_table": "orders", "main_columns": ["id"], "children": []},
    })
    config_id = response_json(created)["id"]
    monkeypatch.setattr(cdc_module.orchestrator, "start_cdc_process", lambda execution_id, config_id: 4321)
    monkeypatch.setattr(cdc_module.orchestrator, "stop_process", lambda execution_id: True)

    started = invoke(route_api, "POST", f"/api/cdc/{config_id}/start")
    stopped = invoke(route_api, "POST", f"/api/cdc/{config_id}/stop")

    assert started.status_code == 200
    assert response_json(started)["pid"] == 4321
    assert stopped.status_code == 200
    assert response_json(invoke(route_api, "GET", f"/api/cdc/{config_id}/status"))["status"] == "stopped"


def test_postgres_copy_batch_endpoint_starts_selected_pipeline(route_api, monkeypatch):
    import backend.routes.execution as execution_module

    created = invoke(route_api, "POST", "/api/config/new", {
        "name": "copy-one-time", "pipeline_type": "pg_copy",
        "source": {"host": "source", "port": 5432, "database": "app", "user": "reader", "password": "secret"},
        "target": {"type": "postgres", "host": "target", "port": 5432, "database": "copy", "user": "writer", "password": "secret", "allow_replace": True},
        "schema": {"main_table": "orders", "children": []},
    })
    config_id = response_json(created)["id"]
    monkeypatch.setattr(execution_module.orchestrator, "start_batch_migration", lambda execution_id, config_id, schema: 4321)

    response = invoke(route_api, "POST", "/api/execution/batch", {"config_id": config_id})

    assert response.status_code == 200
    assert response_json(response)["pid"] == 4321


def test_mysql_source_connection_route_selects_mysql_introspector(route_api, monkeypatch):
    import backend.routes.discovery as discovery_module

    observed = {}

    class FakeMySQLIntrospector:
        def __init__(self, params):
            observed.update(params)

        async def test_connection(self):
            return {"server_version": "MySQL 8", "database_size": 10, "table_count": 2}

        async def disconnect(self):
            pass

    monkeypatch.setattr(discovery_module, "MySQLIntrospector", FakeMySQLIntrospector)

    response = invoke(route_api, "POST", "/api/discover/test", {
        "type": "mysql", "host": "mysql", "port": 3306,
        "database": "store", "user": "reader", "password": "secret",
    })

    assert response.status_code == 200
    assert observed["port"] == 3306
    assert response_json(response)["server"]["table_count"] == 2


def test_dashboard_and_widget_route_lifecycle(route_api):
    created = invoke(route_api, "POST", "/api/dashboards", {
        "name": "Integration dashboard", "description": "Route test", "is_shared": True,
    })
    assert created.status_code == 201
    dashboard_id = response_json(created)["id"]

    widget = invoke(route_api, "POST", f"/api/dashboards/{dashboard_id}/widgets", {
        "widget_type": "metric", "title": "Rows synced", "config": {"metric": "rows"},
    })
    assert widget.status_code == 201
    widget_id = response_json(widget)["id"]

    listed = response_json(invoke(route_api, "GET", "/api/dashboards"))["dashboards"]
    assert listed[0]["widgets"][0]["title"] == "Rows synced"
    assert listed[0]["share_token"]

    removed = invoke(route_api, "DELETE", f"/api/dashboards/{dashboard_id}/widgets/{widget_id}")
    assert removed.status_code == 200
    deleted = invoke(route_api, "DELETE", f"/api/dashboards/{dashboard_id}")
    assert deleted.status_code == 200
    assert invoke(route_api, "GET", f"/api/dashboards/{dashboard_id}").status_code == 404


def test_execution_list_serializes_model_contract(route_api):
    config = create_configuration(route_api, "execution-config")
    from backend.models import Execution

    with route_api.db.get_session() as session:
        execution = Execution(config_id=config["id"], execution_type="batch", status="pending")
        execution.process_pid = 4321
        execution.rows_processed = 12
        session.add(execution)
        session.commit()
        execution_id = execution.id

    response = invoke(route_api, "GET", "/api/execution")
    assert response.status_code == 200
    item = response_json(response)["executions"][0]
    assert item["type"] == "batch"
    assert item["pid"] == 4321
    assert item["rows_processed"] == 12
    status = invoke(route_api, "GET", f"/api/execution/{execution_id}/status")
    assert status.status_code == 200
    assert response_json(status)["type"] == "batch"


def test_job_routes_create_pause_resume_and_delete(route_api):
    config = create_configuration(route_api, "job-route-config")
    payload = {
        "name": "Nightly sync", "config_id": config["id"],
        "cron_expression": "0 2 * * *", "timezone": "UTC",
        "execution_type": "batch", "max_retries": 2,
        "timeout_seconds": 1200, "notifications": [],
    }
    created = invoke(route_api, "POST", "/api/jobs", payload)
    assert created.status_code == 201
    job_id = response_json(created)["job"]["id"]

    invalid = invoke(route_api, "POST", "/api/jobs", {**payload, "cron_expression": "not cron"})
    assert invalid.status_code == 400

    assert invoke(route_api, "POST", f"/api/jobs/{job_id}/pause").status_code == 200
    paused = response_json(invoke(route_api, "GET", "/api/jobs"))["jobs"][0]
    assert paused["enabled"] is False
    assert invoke(route_api, "POST", f"/api/jobs/{job_id}/resume").status_code == 200
    assert invoke(route_api, "DELETE", f"/api/jobs/{job_id}").status_code == 200


def test_alert_rule_routes_validate_and_persist(route_api):
    payload = {
        "name": "High error rate", "metric": "error_rate", "condition": "gt",
        "threshold": 5, "duration_seconds": 60, "cooldown_seconds": 300,
        "severity": "critical", "notification_channels": ["webhook"], "enabled": True,
    }
    invalid = invoke(route_api, "POST", "/api/alerts/rules", {**payload, "name": "  "})
    assert invalid.status_code == 400

    created = invoke(route_api, "POST", "/api/alerts/rules", payload)
    assert created.status_code == 201
    rule_id = response_json(created)["id"]
    updated = invoke(route_api, "PUT", f"/api/alerts/rules/{rule_id}", {"enabled": False})
    assert response_json(updated)["enabled"] is False
    rules = response_json(invoke(route_api, "GET", "/api/alerts/rules"))["rules"]
    assert rules[0]["name"] == "High error rate"
    assert invoke(route_api, "DELETE", f"/api/alerts/rules/{rule_id}").status_code == 200


def test_failure_retry_route_schedules_and_validates(route_api, monkeypatch):
    from backend.models import Configuration, Execution, ExecutionFailure
    from backend.services.error_recovery_service import RecoveryStrategy

    class Timer:
        def __init__(self, *args, **kwargs):
            self.daemon = False
        def start(self):
            pass

    recovery_module = importlib.import_module("backend.services.error_recovery_service")
    monkeypatch.setattr(recovery_module.threading, "Timer", Timer)
    config = create_configuration(route_api, "retry-route-config")
    with route_api.db.get_session() as session:
        saved_config = session.query(Configuration).filter_by(id=config["id"]).one()
        saved_config.pgsync_schema_json = json.dumps({"database": {"host": "localhost"}})
        execution = Execution(config_id=config["id"], type="batch", status="failed")
        session.add(execution)
        session.flush()
        failure = ExecutionFailure(
            execution_id=execution.id, config_id=config["id"], error_type="ConnectionError",
            error_message="connection lost", is_retriable=True, status="pending",
        )
        session.add(failure)
        session.commit()
        failure_id = failure.id

    invalid = invoke(route_api, "POST", f"/api/failures/{failure_id}/retry", {"strategy": "unknown"})
    assert invalid.status_code == 400
    scheduled = invoke(route_api, "POST", f"/api/failures/{failure_id}/retry", {
        "strategy": RecoveryStrategy.IMMEDIATE_RETRY.value,
    })
    assert scheduled.status_code == 202
    duplicate = invoke(route_api, "POST", f"/api/failures/{failure_id}/retry", {
        "strategy": RecoveryStrategy.IMMEDIATE_RETRY.value,
    })
    assert duplicate.status_code == 409


def test_execution_log_and_metric_routes_accept_omitted_filters(route_api):
    logs = invoke(route_api, "GET", "/api/logs/123")
    metrics = invoke(route_api, "GET", "/api/metrics/123")
    assert logs.status_code == 200
    assert response_json(logs)["logs"] == []
    assert metrics.status_code == 200
    assert response_json(metrics)["metrics"] == []


def test_report_export_route_matches_dynamic_format(route_api):
    response = invoke(route_api, "GET", "/api/reports/export/json", query={"days": "7"})
    assert response.status_code == 200
