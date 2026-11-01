"""Safety checks for ClickHouse migration rollback behavior."""

from backend.services import clickhouse_migration_manager as manager_module


def test_rollback_does_not_delete_migration_history(monkeypatch):
    class Client:
        def __init__(self):
            self.calls = []

        def execute(self, query):
            self.calls.append(query)

    client = Client()
    monkeypatch.setattr(manager_module.clickhouse_client, "client", client)
    manager = object.__new__(manager_module.ClickHouseMigrationManager)

    assert manager.rollback_migration("20260619") is False
    assert client.calls == []
