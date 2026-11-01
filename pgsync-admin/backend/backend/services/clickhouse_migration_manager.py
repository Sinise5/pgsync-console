"""ClickHouse migration manager for schema versioning."""

import logging
from typing import List, Dict, Optional
from datetime import datetime
import os
from pathlib import Path

from backend.services.clickhouse_client import clickhouse_client

logger = logging.getLogger(__name__)


class ClickHouseMigrationManager:
    """Manage ClickHouse schema migrations."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        """Initialize migration manager."""
        if hasattr(self, '_initialized') and self._initialized:
            return
        self.migrations_dir = Path(__file__).parent.parent.parent / "clickhouse_migrations"
        self.migrations_dir.mkdir(exist_ok=True)
        self._ensure_version_table()
        self._initialized = True

    def _ensure_version_table(self):
        """Create migration version tracking table."""
        try:
            if not clickhouse_client.client:
                logger.warning("ClickHouse client not connected — skipping migration_versions table")
                return

            clickhouse_client.client.execute("""
                CREATE TABLE IF NOT EXISTS migration_versions (
                    version String,
                    name String,
                    applied_at DateTime DEFAULT now(),
                    checksum String
                ) ENGINE = MergeTree()
                ORDER BY applied_at
            """)
            logger.info("ClickHouse migration_versions table ensured")
        except Exception as e:
            logger.warning(f"Could not create migration_versions table: {e} — will retry on use")

    def get_current_version(self) -> Optional[str]:
        """Get current ClickHouse schema version."""
        try:
            if not clickhouse_client.client:
                return None

            result = clickhouse_client.client.execute("""
                SELECT version FROM migration_versions
                ORDER BY applied_at DESC
                LIMIT 1
            """)
            return result[0][0] if result else None
        except Exception as e:
            logger.error(f"Failed to get current version: {e}")
            return None

    def get_history(self, limit: int = 10) -> List[Dict]:
        """Get migration history."""
        try:
            if not clickhouse_client.client:
                return []

            result = clickhouse_client.client.execute(f"""
                SELECT version, name, applied_at, checksum
                FROM migration_versions
                ORDER BY applied_at DESC
                LIMIT {limit}
            """)

            history = []
            for row in result:
                history.append({
                    "version": row[0],
                    "name": row[1],
                    "applied_at": row[2].isoformat() if row[2] else None,
                    "checksum": row[3],
                })
            return history
        except Exception as e:
            logger.error(f"Failed to get migration history: {e}")
            return []

    def apply_migration(self, version: str) -> bool:
        """Apply specific migration."""
        try:
            if not clickhouse_client.client:
                logger.error("ClickHouse client not connected")
                return False

            # Find migration file
            migration_files = sorted(self.migrations_dir.glob(f"{version}_*.sql"))
            if not migration_files:
                logger.error(f"Migration {version} not found")
                return False

            migration_file = migration_files[0]

            # Read migration SQL
            with open(migration_file) as f:
                content = f.read()

            # Extract actual SQL (skip comments)
            sql_statements = []
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("--"):
                    sql_statements.append(line)

            sql = "\n".join(sql_statements)

            # Execute migration
            clickhouse_client.client.execute(sql)

            # Record migration
            import hashlib
            checksum = hashlib.md5(content.encode()).hexdigest()

            clickhouse_client.client.execute(
                """INSERT INTO migration_versions (version, name, checksum) VALUES""",
                [(version, migration_file.stem.replace(f"{version}_", ""), checksum)]
            )

            logger.info(f"Applied ClickHouse migration: {version}")
            return True
        except Exception as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            return False

    def upgrade_all(self) -> Dict:
        """Apply all pending migrations."""
        try:
            if not clickhouse_client.client:
                logger.error("ClickHouse client not connected")
                return {"applied": [], "failed": [], "count": 0, "error": "Not connected"}

            current_version = self.get_current_version()

            # Get all migration files
            all_migrations = sorted(self.migrations_dir.glob("*.sql"))

            # Filter pending migrations
            pending = []
            for mig_file in all_migrations:
                version = mig_file.stem.split("_")[0]
                if not current_version or version > current_version:
                    pending.append(version)

            # Apply each
            applied = []
            failed = []
            for version in pending:
                if self.apply_migration(version):
                    applied.append(version)
                else:
                    failed.append(version)
                    break  # Stop on first failure

            return {
                "applied": applied,
                "failed": failed,
                "count": len(applied),
            }
        except Exception as e:
            logger.error(f"Failed to upgrade: {e}")
            return {"applied": [], "failed": [], "count": 0, "error": str(e)}

    def rollback_migration(self, version: str) -> bool:
        """Rollback specific migration (manual intervention required)."""
        logger.warning("ClickHouse DDL migrations cannot be rolled back automatically; apply a compensating migration manually")
        return False

    def create_initial_migration(self) -> Dict:
        """Create initial migration for existing tables."""
        # Initial migration already exists at:
        # clickhouse_migrations/20260619_initial_schema.sql
        return {
            "status": "initial_migration_created",
            "version": "20260619",
            "name": "initial_schema",
            "path": str(self.migrations_dir / "20260619_initial_schema.sql"),
        }


# Lazy singleton instance
_clickhouse_migration_manager_instance = None


def get_clickhouse_migration_manager() -> ClickHouseMigrationManager:
    """Get or create singleton ClickHouseMigrationManager instance."""
    global _clickhouse_migration_manager_instance
    if _clickhouse_migration_manager_instance is None:
        _clickhouse_migration_manager_instance = ClickHouseMigrationManager()
    return _clickhouse_migration_manager_instance


# For backward compatibility, expose function directly
clickhouse_migration_manager = get_clickhouse_migration_manager
