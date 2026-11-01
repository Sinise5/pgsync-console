"""MySQL/MariaDB schema discovery for search pipelines."""

import asyncio
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, URL


class MySQLIntrospector:
    """Expose MySQL metadata in the shape consumed by Schema Builder."""

    def __init__(self, conn_params: dict[str, Any]):
        self.conn_params = conn_params
        self.engine: Engine | None = None

    async def connect(self) -> None:
        await asyncio.to_thread(self._connect)

    def _connect(self) -> None:
        url = URL.create(
            "mysql+pymysql",
            username=self.conn_params.get("user"),
            password=self.conn_params.get("password"),
            host=self.conn_params.get("host"),
            port=int(self.conn_params.get("port", 3306)),
            database=self.conn_params.get("database"),
        )
        self.engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 8})
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    async def disconnect(self) -> None:
        if self.engine:
            await asyncio.to_thread(self.engine.dispose)
            self.engine = None

    async def test_connection(self) -> dict[str, Any]:
        if not self.engine:
            await self.connect()
        return await asyncio.to_thread(self._test_connection)

    def _test_connection(self) -> dict[str, Any]:
        assert self.engine
        with self.engine.connect() as connection:
            version = connection.execute(text("SELECT VERSION()")).scalar_one()
            size = connection.execute(text(
                "SELECT COALESCE(SUM(data_length + index_length), 0) "
                "FROM information_schema.tables WHERE table_schema = :db"
            ), {"db": self.conn_params["database"]}).scalar_one()
            count = connection.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = :db AND table_type = 'BASE TABLE'"
            ), {"db": self.conn_params["database"]}).scalar_one()
        return {"server_version": version, "database_size": int(size or 0), "table_count": int(count or 0)}

    async def get_full_schema(self, schema: str | None = None) -> dict[str, Any]:
        if not self.engine:
            await self.connect()
        return await asyncio.to_thread(self._get_full_schema)

    async def discover_tables(self, schema: str | None = None) -> list[str]:
        if not self.engine:
            await self.connect()
        return await asyncio.to_thread(lambda: inspect(self.engine).get_table_names(schema=self.conn_params["database"]))

    async def get_table_columns(self, table_name: str, schema: str | None = None) -> list[dict[str, Any]]:
        if not self.engine:
            await self.connect()
        return await asyncio.to_thread(self._get_table_columns, table_name)

    def _get_table_columns(self, table_name: str) -> list[dict[str, Any]]:
        assert self.engine
        columns = inspect(self.engine).get_columns(table_name, schema=self.conn_params["database"])
        for position, column in enumerate(columns, 1):
            column.update({
                "column_name": column["name"],
                "data_type": str(column["type"]),
                "is_nullable": "YES" if column.get("nullable", True) else "NO",
                "column_default": column.get("default"),
                "ordinal_position": position,
            })
        return columns

    async def get_primary_key(self, table_name: str, schema: str | None = None) -> list[str]:
        if not self.engine:
            await self.connect()
        return await asyncio.to_thread(
            lambda: inspect(self.engine).get_pk_constraint(table_name, schema=self.conn_params["database"]).get("constrained_columns") or []
        )

    async def get_foreign_keys(self, table_name: str, schema: str | None = None) -> list[dict[str, Any]]:
        if not self.engine:
            await self.connect()
        return await asyncio.to_thread(self._get_foreign_keys, table_name)

    def _get_foreign_keys(self, table_name: str) -> list[dict[str, Any]]:
        assert self.engine
        keys = inspect(self.engine).get_foreign_keys(table_name, schema=self.conn_params["database"])
        return [
            {
                "constraint_name": item.get("name"),
                "table_name": table_name,
                "column_name": source,
                "referenced_table_name": item.get("referred_table"),
                "referenced_column_name": target,
            }
            for item in keys
            for source, target in zip(item.get("constrained_columns") or [], item.get("referred_columns") or [])
        ]

    def _get_full_schema(self) -> dict[str, Any]:
        assert self.engine
        inspector = inspect(self.engine)
        database = self.conn_params["database"]
        tables = []
        relationships = []
        for table_name in inspector.get_table_names(schema=database):
            columns = inspector.get_columns(table_name, schema=database)
            primary_key = inspector.get_pk_constraint(table_name, schema=database).get("constrained_columns") or []
            for position, column in enumerate(columns, 1):
                column["column_name"] = column["name"]
                column["data_type"] = str(column["type"])
                column["is_nullable"] = "YES" if column.get("nullable", True) else "NO"
                column["column_default"] = column.get("default")
                column["ordinal_position"] = position
            with self.engine.connect() as connection:
                row_count = connection.execute(text(
                    "SELECT table_rows FROM information_schema.tables "
                    "WHERE table_schema = :db AND table_name = :table"
                ), {"db": database, "table": table_name}).scalar_one_or_none()
            tables.append({"name": table_name, "columns": columns, "primary_key": primary_key, "row_count": row_count or 0})
            for foreign_key in inspector.get_foreign_keys(table_name, schema=database):
                for source_column, target_column in zip(
                    foreign_key.get("constrained_columns") or [],
                    foreign_key.get("referred_columns") or [],
                ):
                    relationships.append({
                        "source_table": table_name,
                        "source_column": source_column,
                        "target_table": foreign_key.get("referred_table"),
                        "target_column": target_column,
                    })
        return {"tables": tables, "relationships": relationships, "schema": database}
