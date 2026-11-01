"""PostgreSQL schema introspection service (async)."""

import logging
from typing import Optional, Dict, List, Any
import psycopg
from psycopg import AsyncConnection, sql
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


class PGIntrospector:
    """Discover PostgreSQL schema metadata (async)."""

    def __init__(self, conn_params: Dict[str, Any]) -> None:
        """Initialize introspector with connection parameters.

        Args:
            conn_params: PostgreSQL connection parameters
                {host, port, database, user, password}
        """
        self.conn_params = conn_params
        self.conn: Optional[AsyncConnection] = None

    async def connect(self) -> None:
        """Establish async PostgreSQL connection."""
        try:
            self.conn = await psycopg.AsyncConnection.connect(
                host=self.conn_params.get("host", "localhost"),
                port=self.conn_params.get("port", 5432),
                dbname=self.conn_params.get("database"),
                user=self.conn_params.get("user"),
                password=self.conn_params.get("password"),
            )
            logger.info(f"Connected to PG: {self.conn_params.get('host')}:{self.conn_params.get('port')}/{self.conn_params.get('database')}")
        except Exception as e:
            logger.error(f"PG connection failed: {e}")
            raise

    async def disconnect(self) -> None:
        """Close async PostgreSQL connection."""
        if self.conn:
            await self.conn.close()
            logger.info("PG connection closed")

    async def test_connection(self) -> Dict[str, Any]:
        """Test connection and return server info."""
        if not self.conn:
            await self.connect()

        try:
            async with self.conn.cursor() as cursor:
                # Get version
                await cursor.execute("SELECT version();")
                version = await cursor.fetchone()

                # Get database size
                await cursor.execute("""
                    SELECT sum(pg_database_size(datname))
                    FROM pg_database;
                """)
                db_size = await cursor.fetchone()

                # Get table count
                await cursor.execute("""
                    SELECT count(*) FROM information_schema.tables
                    WHERE table_schema = 'public';
                """)
                table_count = await cursor.fetchone()

                return {
                    "server_version": version[0] if version else None,
                    "database_size": db_size[0] or 0 if db_size else 0,
                    "table_count": table_count[0] if table_count else 0,
                    "status": "connected",
                }
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            raise

    async def list_tables(self, schema: str = "public") -> List[Dict[str, Any]]:
        """List all tables with metadata.

        Args:
            schema: Database schema (default: public)

        Returns:
            List of table metadata dicts
        """
        if not self.conn:
            await self.connect()

        try:
            async with self.conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute("""
                    SELECT
                      t.tablename,
                      obj_description((t.schemaname||'.'||t.tablename)::regclass) AS description,
                      (SELECT count(*) FROM information_schema.columns
                       WHERE table_schema = t.schemaname AND table_name = t.tablename) AS column_count,
                      (SELECT count(*) FROM information_schema.table_constraints
                       WHERE table_schema = t.schemaname AND table_name = t.tablename AND constraint_type = 'PRIMARY KEY') AS has_primary_key
                    FROM pg_tables t
                    WHERE t.schemaname = %s
                    ORDER BY t.tablename;
                """, (schema,))

                tables = await cursor.fetchall()
                return [dict(row) for row in tables]
        except Exception as e:
            logger.error(f"Failed to list tables: {e}")
            raise

    async def discover_tables(self, schema: str = "public") -> List[str]:
        """Get list of table names."""
        if not self.conn:
            await self.connect()

        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = %s
                    ORDER BY tablename;
                """, (schema,))

                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Failed to discover tables: {e}")
            raise

    async def get_table_columns(self, table_name: str, schema: str = "public") -> List[Dict[str, Any]]:
        """Get columns for a specific table.

        Args:
            table_name: Table name
            schema: Schema name (default: public)

        Returns:
            List of column metadata dicts
        """
        if not self.conn:
            await self.connect()

        try:
            async with self.conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute("""
                    SELECT
                      column_name,
                      data_type,
                      is_nullable,
                      column_default,
                      ordinal_position
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position;
                """, (schema, table_name))

                columns = await cursor.fetchall()
                return [dict(row) for row in columns]
        except Exception as e:
            logger.error(f"Failed to get table columns: {e}")
            raise

    async def get_primary_key(self, table_name: str, schema: str = "public") -> List[str]:
        """Get primary key columns for a table."""
        if not self.conn:
            await self.connect()

        try:
            full_name = f"{schema}.{table_name}"
            async with self.conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid
                    AND a.attnum = ANY(i.indkey)
                    WHERE i.indisprimary
                    AND i.indrelid = %s::regclass;
                """, (full_name,))

                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Failed to get primary key for {schema}.{table_name}: {e}")
            return []

    async def get_foreign_keys(self, table_name: str, schema: str = "public") -> List[Dict[str, Any]]:
        """Get foreign key relationships."""
        if not self.conn:
            await self.connect()

        try:
            async with self.conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute("""
                    SELECT
                        tc.constraint_name,
                        kcu.table_name,
                        kcu.column_name,
                        ccu.table_name AS referenced_table_name,
                        ccu.column_name AS referenced_column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu ON
                        tc.constraint_name = kcu.constraint_name AND
                        tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage ccu ON
                        ccu.constraint_name = tc.constraint_name AND
                        ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND kcu.table_schema = %s
                    AND kcu.table_name = %s;
                """, (schema, table_name))

                fks = await cursor.fetchall()
                return [dict(row) for row in fks]
        except Exception as e:
            logger.error(f"Failed to get foreign keys for {schema}.{table_name}: {e}")
            return []

    async def get_full_schema(self, schema: str = "public") -> Dict[str, Any]:
        """Get complete schema with all tables, columns, PKs, and FKs.

        Returns:
            {
              "tables": [
                {
                  "name": "users",
                  "columns": [...],
                  "primary_key": ["id"],
                  "row_count": 1000
                }
              ],
              "relationships": [
                {
                  "source_table": "orders",
                  "source_column": "user_id",
                  "target_table": "users",
                  "target_column": "id"
                }
              ]
            }
        """
        if not self.conn:
            await self.connect()

        try:
            # Get all tables (just names)
            tables = await self.discover_tables(schema)

            result = {
                "tables": [],
                "relationships": [],
                "schema": schema
            }

            all_relationships = [
                {
                    "source_table": relationship["table_name"],
                    "source_column": relationship["column_name"],
                    "target_table": relationship["referenced_table_name"],
                    "target_column": relationship["referenced_column_name"],
                }
                for relationship in await self.discover_relationships(schema)
            ]

            # Collect table details; foreign keys are returned separately below.
            for table in tables:
                try:
                    columns = await self.get_table_columns(table, schema)
                    pk = await self.get_primary_key(table, schema)

                    # Get row count
                    async with self.conn.cursor() as cursor:
                        count_query = sql.SQL("SELECT count(*) FROM {schema}.{table}").format(
                            schema=sql.Identifier(schema),
                            table=sql.Identifier(table)
                        )
                        await cursor.execute(count_query)
                        row = await cursor.fetchone()
                        row_count = row[0] if row else 0

                    result["tables"].append({
                        "name": table,
                        "columns": columns,
                        "primary_key": pk,
                        "row_count": row_count
                    })
                except Exception as e:
                    logger.warning(f"Skipping table {schema}.{table}: {e}")
                    try:
                        await self.conn.rollback()
                    except Exception:
                        pass
                    continue

            result["relationships"] = all_relationships
            return result

        except Exception as e:
            logger.error(f"Failed to get full schema: {e}")
            raise

    async def get_indexes(self, table_name: str, schema: str = "public") -> List[Dict[str, Any]]:
        """Get indexes for a table."""
        if not self.conn:
            await self.connect()

        try:
            async with self.conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute("""
                    SELECT
                      indexname,
                      indexdef,
                      idx_scan,
                      idx_tup_read,
                      idx_tup_fetch
                    FROM pg_indexes
                    LEFT JOIN pg_stat_user_indexes ON pg_indexes.indexname = pg_stat_user_indexes.indexrelname
                    WHERE schemaname = %s AND tablename = %s;
                """, (schema, table_name))

                indexes = await cursor.fetchall()
                return [dict(row) for row in indexes]
        except Exception as e:
            logger.error(f"Failed to get indexes: {e}")
            return []

    async def get_table_stats(self, table_name: str, schema: str = "public") -> Dict[str, Any]:
        """Get table statistics."""
        if not self.conn:
            await self.connect()

        try:
            async with self.conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute("""
                    SELECT
                      schemaname,
                      relname,
                      n_live_tup,
                      n_dead_tup,
                      last_vacuum,
                      last_autovacuum,
                      last_analyze,
                      last_autoanalyze
                    FROM pg_stat_user_tables
                    WHERE schemaname = %s AND relname = %s;
                """, (schema, table_name))

                row = await cursor.fetchone()
                return dict(row) if row else {}
        except Exception as e:
            logger.error(f"Failed to get table stats: {e}")
            return {}

    async def discover_relationships(self, schema: str = "public") -> List[Dict[str, Any]]:
        """Discover all foreign key relationships in schema."""
        if not self.conn:
            await self.connect()

        try:
            async with self.conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute("""
                    SELECT
                      tc.constraint_name,
                      tc.table_name,
                      kcu.column_name,
                      ccu.table_name AS referenced_table_name,
                      ccu.column_name AS referenced_column_name
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = %s;
                """, (schema,))

                rels = await cursor.fetchall()
                return [dict(row) for row in rels]
        except Exception as e:
            logger.error(f"Failed to discover relationships: {e}")
            return []


# Global singleton instance
pg_introspector: Optional[PGIntrospector] = None
