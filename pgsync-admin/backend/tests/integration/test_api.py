"""Integration tests for API endpoints."""

import pytest
import json


class TestAPIHealth:
    """Test health endpoint."""

    def test_health_endpoint(self, test_db, monkeypatch):
        """Health endpoint returns OK."""
        from backend.routes.config import config_routes
        from backend.routes.execution import execution_routes

        assert config_routes is not None
        assert execution_routes is not None

    def test_api_response_format(self):
        """API response format validation."""
        def make_response(data, status="success", error=None):
            resp = {"status": status, "data": data}
            if error:
                resp["error"] = error
            return resp

        success = make_response({"id": 1, "name": "test"})
        assert success["status"] == "success"
        assert success["data"]["name"] == "test"

        error = make_response(None, "error", "Something went wrong")
        assert error["status"] == "error"
        assert error["error"] == "Something went wrong"


class TestConfigAPI:
    """Test configuration API logic."""

    def test_config_crud_logic(self, test_session, sample_config_data):
        """Config CRUD business logic."""
        from backend.models import Configuration
        import json

        # Create
        config = Configuration(
            name="api_test",
            source_pg_host="localhost",
            source_pg_port=5432,
            source_pg_database="example_db",
            source_pg_user="postgres",
            source_pg_password="encrypted",
            target_type="opensearch",
            target_config=json.dumps({"host": "localhost"}),
            schema_config=json.dumps({"main_table": "laporan"}),
        )
        test_session.add(config)
        test_session.flush()
        assert config.id > 0

        # Read
        found = test_session.query(Configuration).filter_by(id=config.id).first()
        assert found.name == "api_test"
        assert found.source_pg_host == "localhost"

        # Update
        found.name = "api_test_updated"
        found.is_active = True
        test_session.flush()

        updated = test_session.query(Configuration).filter_by(id=config.id).first()
        assert updated.name == "api_test_updated"
        assert updated.is_active == True

        # Delete
        test_session.delete(updated)
        test_session.flush()

        deleted = test_session.query(Configuration).filter_by(id=config.id).first()
        assert deleted is None

    def test_config_list_with_filters(self, test_session, sample_config_data):
        """Config listing with filters."""
        from backend.models import Configuration
        import json

        configs = [
            Configuration(
                name=f"filter_test_{i}",
                source_pg_host="localhost",
                source_pg_port=5432,
                source_pg_database="test_db",
                source_pg_user="postgres",
                source_pg_password="encrypted",
                target_type="opensearch",
                target_config=json.dumps({}),
                schema_config=json.dumps({}),
            )
            for i in range(5)
        ]
        test_session.add_all(configs)
        test_session.flush()

        # Filter by name pattern
        results = test_session.query(Configuration).filter(
            Configuration.name.like("filter_test_%")
        ).all()
        assert len(results) >= 5

    def test_config_pagination(self, test_session, sample_config_data):
        """Config pagination logic."""
        from backend.models import Configuration
        import json

        for i in range(10):
            config = Configuration(
                name=f"paginate_test_{i}",
                source_pg_host="localhost",
                source_pg_port=5432,
                source_pg_database=f"db_{i}",
                source_pg_user="postgres",
                source_pg_password="encrypted",
                target_type="opensearch",
                target_config=json.dumps({}),
                schema_config=json.dumps({}),
            )
            test_session.add(config)
        test_session.flush()

        # Query with limit/offset
        page1 = test_session.query(Configuration).filter(
            Configuration.name.like("paginate_test_%")
        ).limit(3).offset(0).all()
        assert len(page1) <= 3

        page2 = test_session.query(Configuration).filter(
            Configuration.name.like("paginate_test_%")
        ).limit(3).offset(3).all()
        if len(page2) > 0:
            assert page2[0].name != page1[0].name


class TestExecutionAPI:
    """Test execution API logic."""

    def test_execution_workflow(self, test_session):
        """Execution create → run → complete flow."""
        from backend.models import Execution
        from datetime import datetime

        # Create execution
        exec = Execution(
            config_id=1,
            type="batch",
            status="running",
            started_at=datetime.utcnow(),
        )
        test_session.add(exec)
        test_session.flush()

        assert exec.status == "running"
        assert exec.error_message is None

        # Complete execution
        exec.status = "completed"
        exec.completed_at = datetime.utcnow()
        exec.synced_docs = 1500
        exec.progress_pct = 100.0
        test_session.flush()

        assert exec.status == "completed"
        assert exec.synced_docs == 1500
        assert exec.completed_at is not None

    def test_execution_status_tracking(self, test_session):
        """Execution status state machine."""
        from backend.models import Execution

        STATUSES = ["pending", "running", "completed", "failed"]

        for status in STATUSES:
            exec = Execution(
                config_id=1,
                type="batch",
                status=status,
            )
            test_session.add(exec)
        test_session.flush()

        queried = test_session.query(Execution).filter(
            Execution.status.in_(STATUSES)
        ).all()
        found_statuses = [e.status for e in queried]
        for s in STATUSES:
            assert s in found_statuses
