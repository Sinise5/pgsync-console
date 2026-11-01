"""Migration service for batch data synchronization."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import json

import psycopg
from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk

from backend.db import db
from backend.models import Migration, MigrationStatus, MigrationBatchFrequency, Configuration
from backend.utils.crypto import CryptoService

logger = logging.getLogger(__name__)


class MigrationService:
    """Service for executing batch migrations."""

    def __init__(self):
        self.crypto = CryptoService()
        self.running_migrations: Dict[int, asyncio.Task] = {}

    async def create_migration(
        self,
        config_id: int,
        name: str,
        frequency: str = "daily",
        date_column: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Migration:
        """Create a new migration record."""
        migration = Migration(
            config_id=config_id,
            name=name,
            frequency=MigrationBatchFrequency(frequency),
            date_column=date_column,
            date_from=datetime.fromisoformat(date_from) if date_from else None,
            date_to=datetime.fromisoformat(date_to) if date_to else None,
            limit=limit,
            status=MigrationStatus.PENDING,
        )

        with db.get_session() as session:
            session.add(migration)
            session.commit()
            session.refresh(migration)
            return migration

    async def start_migration(self, migration_id: int) -> None:
        """Start migration execution in background."""
        if migration_id in self.running_migrations:
            raise ValueError(f"Migration {migration_id} is already running")

        task = asyncio.create_task(self._execute_migration(migration_id))
        self.running_migrations[migration_id] = task

    async def _execute_migration(self, migration_id: int) -> None:
        """Execute migration (runs in background)."""
        try:
            # Update status to RUNNING
            self._update_status(migration_id, MigrationStatus.RUNNING, started_at=datetime.utcnow())

            # Load migration + config
            with db.get_session() as session:
                migration = session.query(Migration).filter_by(id=migration_id).first()
                if not migration:
                    raise ValueError(f"Migration {migration_id} not found")

                config = session.query(Configuration).filter_by(id=migration.config_id).first()
                if not config:
                    raise ValueError(f"Config {migration.config_id} not found")

                # Decrypt PG password (skip if masked)
                # Get credentials
                try:
                    pg_password = self.crypto.decrypt(config.source_pg_password)
                    if not pg_password or pg_password == '***':
                        raise ValueError("PG password is masked - cannot decrypt")
                except Exception as decrypt_err:
                    logger.error(f"Failed to decrypt PG password for config {config.id}: {decrypt_err}")
                    raise ValueError(f"Cannot decrypt source database password: {decrypt_err}")

                # Parse target config
                target_config = json.loads(config.target_config) if isinstance(config.target_config, str) else config.target_config
                os_host = target_config.get('host')
                os_port = target_config.get('port', 9200)
                os_user = target_config.get('user')
                verify_certs = bool(target_config.get('verify_certs', True))

                # Decrypt OS password only if exists and not masked
                raw_password = target_config.get('password', '')
                if raw_password == '***':
                    raise ValueError(
                        f"Configuration '{config.name}' has masked OpenSearch password. "
                        "Please edit the config and update the target password before running migration."
                    )

                try:
                    os_password = self.crypto.decrypt(raw_password) if raw_password else None
                except Exception as decrypt_err:
                    raise ValueError(f"Cannot decrypt OpenSearch password for config '{config.name}': {decrypt_err}")

                # Build connection strings
                pg_dsn = f"host={config.source_pg_host} port={config.source_pg_port} dbname={config.source_pg_database} user={config.source_pg_user} password={pg_password}"

            # Parse schema
            schema_config = json.loads(config.schema_config) if isinstance(config.schema_config, str) else config.schema_config
            schema_root = schema_config.get('nodes') or schema_config
            main_table = schema_config.get('main_table') or schema_root.get('table')
            if not main_table:
                raise ValueError("No main table in schema")

            # Execute sync
            self._sync_data(
                migration_id=migration_id,
                pg_dsn=pg_dsn,
                main_table=main_table,
                os_host=os_host,
                os_port=os_port,
                os_user=os_user,
                os_password=os_password,
                verify_certs=verify_certs,
                index_name=schema_config.get('index', main_table.lower()),
                date_from=migration.date_from,
                date_to=migration.date_to,
                limit=migration.limit,
                frequency=migration.frequency,
            )

            # Mark as completed
            self._update_status(
                migration_id,
                MigrationStatus.COMPLETED,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Migration {migration_id} failed: {e}\n{tb}", exc_info=True)
            self._update_status(
                migration_id,
                MigrationStatus.FAILED,
                error_message=str(e) or "Unknown error (empty exception)",
                error_details=tb,
                completed_at=datetime.utcnow(),
            )
        finally:
            if migration_id in self.running_migrations:
                del self.running_migrations[migration_id]

    def _ensure_index_exists(
        self,
        os_client: OpenSearch,
        index_name: str,
        main_table: str,
        schema_config: dict,
    ) -> bool:
        """Check if index exists, create if missing with proper mappings."""
        try:
            # Check if index exists
            if os_client.indices.exists(index=index_name):
                logger.info(f"Index '{index_name}' already exists")
                return True

            # Get columns from schema
            columns = schema_config.get('nodes', {}).get('columns', [])
            primary_key = schema_config.get('nodes', {}).get('primary_key', [])

            # Build mappings
            properties = {}
            for col in columns:
                if col:
                    # Default to keyword, can be refined per column
                    properties[col] = {"type": "keyword"}

            # Create index with mappings
            body = {
                "mappings": {
                    "properties": properties
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                }
            }

            os_client.indices.create(index=index_name, body=body)
            logger.info(f"Created index '{index_name}' with {len(properties)} fields")
            return True

        except Exception as e:
            logger.error(f"Failed to ensure index exists: {e}")
            raise ValueError(f"Cannot create index '{index_name}': {e}")

    def _sync_data(
        self,
        migration_id: int,
        pg_dsn: str,
        main_table: str,
        os_host: str,
        os_port: int,
        os_user: str,
        os_password: str,
        verify_certs: bool,
        index_name: str,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        limit: Optional[int],
        frequency: MigrationBatchFrequency,
    ) -> None:
        """Sync data from PostgreSQL to OpenSearch."""
        # OpenSearch client (sync)
        os_client = OpenSearch(
            hosts=[{'host': os_host, 'port': os_port}],
            http_auth=(os_user, os_password) if os_user and os_password else None,
            use_ssl=True,
            verify_certs=verify_certs,
            ssl_show_warn=False,
        )

        try:
            # Get schema config for index creation
            with db.get_session() as session:
                migration = session.query(Migration).filter_by(id=migration_id).first()
                config = session.query(Configuration).filter_by(id=migration.config_id).first()
                schema_config = json.loads(config.schema_config) if isinstance(config.schema_config, str) else config.schema_config

            # Ensure index exists before syncing
            self._ensure_index_exists(os_client, index_name, main_table, schema_config)

            # PostgreSQL connection (sync)
            conn = psycopg.connect(pg_dsn)
            try:
                cur = conn.cursor()
                # Build query with optional date filtering
                query = f'SELECT * FROM "{main_table}"'
                where_clauses = []

                # Add date filter if date_column specified
                if date_from and date_to:
                    with db.get_session() as session:
                        migration = session.query(Migration).filter_by(id=migration_id).first()
                        date_col = migration.date_column if migration else None

                    if date_col:
                        where_clauses.append(
                            f'"{date_col}" BETWEEN \'{date_from.isoformat()}\' AND \'{date_to.isoformat()}\''
                        )

                if where_clauses:
                    query += ' WHERE ' + ' AND '.join(where_clauses)

                if limit:
                    query += f" LIMIT {limit}"

                cur.execute(query)

                # Fetch column names
                columns = [desc[0] for desc in cur.description]

                # Batch sync
                batch_size = 100
                batch = []
                total_synced = 0
                total_failed = 0

                for row in cur:
                    doc = dict(zip(columns, row))

                    # Convert datetime objects to ISO strings
                    for key, value in doc.items():
                        if isinstance(value, datetime):
                            doc[key] = value.isoformat()

                    batch.append({
                        '_index': index_name,
                        '_id': doc.get('id'),
                        '_source': doc,
                    })

                    if len(batch) >= batch_size:
                        success, failed = self._bulk_index(os_client, batch)
                        total_synced += success
                        total_failed += failed

                        # Update progress
                        self._update_progress(migration_id, total_synced, total_failed)

                        batch = []

                # Final batch
                if batch:
                    success, failed = self._bulk_index(os_client, batch)
                    total_synced += success
                    total_failed += failed
                    self._update_progress(migration_id, total_synced, total_failed)

                cur.close()
            finally:
                conn.close()

        finally:
            os_client.close()

    def _bulk_index(self, client: OpenSearch, batch: List[Dict]) -> tuple:
        """Bulk index documents to OpenSearch."""
        try:
            success, errors = bulk(
                client,
                batch,
                raise_on_error=False,
                raise_on_exception=False,
            )
            failed = len(errors) if errors else 0

            # Log first few errors for debugging
            if errors:
                sample_errors = errors[:3]  # First 3 errors
                for err in sample_errors:
                    logger.error(f"OpenSearch bulk error: {err}")

            return success, failed
        except Exception as e:
            logger.error(f"Bulk index exception: {e}", exc_info=True)
            return 0, len(batch)

    def _update_status(
        self,
        migration_id: int,
        status: MigrationStatus,
        error_message: Optional[str] = None,
        error_details: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """Update migration status."""
        with db.get_session() as session:
            migration = session.query(Migration).filter_by(id=migration_id).first()
            if migration:
                migration.status = status
                if error_message is not None:
                    migration.error_message = error_message
                if error_details is not None:
                    migration.error_details = error_details
                if started_at:
                    migration.started_at = started_at
                if completed_at:
                    migration.completed_at = completed_at
                    if migration.started_at:
                        migration.duration_seconds = (completed_at - migration.started_at).total_seconds()
                session.commit()

    def _update_progress(self, migration_id: int, synced: int, failed: int) -> None:
        """Update migration progress."""
        with db.get_session() as session:
            migration = session.query(Migration).filter_by(id=migration_id).first()
            if migration:
                migration.synced_docs = synced
                migration.failed_docs = failed
                migration.total_docs = synced + failed
                if migration.total_docs > 0:
                    migration.progress_percent = (synced / migration.total_docs) * 100
                session.commit()

    def get_migration(self, migration_id: int) -> Optional[Migration]:
        """Get migration by ID."""
        with db.get_session() as session:
            return session.query(Migration).filter_by(id=migration_id).first()

    def list_migrations(self, config_id: Optional[int] = None) -> List[Migration]:
        """List migrations."""
        with db.get_session() as session:
            query = session.query(Migration)
            if config_id:
                query = query.filter_by(config_id=config_id)
            return query.order_by(Migration.created_at.desc()).all()


# Singleton instance
migration_service = MigrationService()
