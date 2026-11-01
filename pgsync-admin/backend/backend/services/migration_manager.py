"""Migration service for schema versioning and rollback."""

import logging
import subprocess
from typing import Optional, List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manage database migrations using Alembic."""

    def __init__(self, alembic_dir: str = "alembic"):
        """Initialize migration manager."""
        self.alembic_dir = alembic_dir
        self.alembic_path = Path(alembic_dir)

    def init_migrations(self) -> bool:
        """Initialize Alembic (one-time setup)."""
        try:
            result = subprocess.run(
                ["alembic", "init", "-t", "generic", self.alembic_dir],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info(f"Alembic initialized in {self.alembic_dir}")
                return True
            else:
                logger.error(f"Alembic init failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error initializing Alembic: {e}")
            return False

    def create_migration(
        self, message: str, autogenerate: bool = True
    ) -> Optional[str]:
        """Create new migration revision."""
        try:
            cmd = ["alembic", "revision"]
            if autogenerate:
                cmd.append("--autogenerate")
            cmd.extend(["-m", message])

            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
            if result.returncode == 0:
                # Extract revision ID from output
                for line in result.stdout.split("\n"):
                    if "Generating" in line:
                        logger.info(f"Created migration: {message}")
                        return message
            else:
                logger.error(f"Migration creation failed: {result.stderr}")
            return None
        except Exception as e:
            logger.error(f"Error creating migration: {e}")
            return None

    def upgrade(self, revision: str = "head") -> bool:
        """Apply migrations up to revision."""
        try:
            result = subprocess.run(
                ["alembic", "upgrade", revision],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info(f"Upgraded to {revision}")
                return True
            else:
                logger.error(f"Upgrade failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error upgrading: {e}")
            return False

    def downgrade(self, revision: str) -> bool:
        """Rollback migrations to revision."""
        try:
            result = subprocess.run(
                ["alembic", "downgrade", revision],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info(f"Downgraded to {revision}")
                return True
            else:
                logger.error(f"Downgrade failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error downgrading: {e}")
            return False

    def current(self) -> Optional[str]:
        """Get current revision."""
        try:
            result = subprocess.run(
                ["alembic", "current"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            logger.error(f"Error getting current revision: {e}")
            return None

    def history(self, limit: int = 10) -> List[Dict[str, str]]:
        """Get migration history."""
        try:
            result = subprocess.run(
                ["alembic", "history"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")[-limit:]
                return [{"revision": line} for line in lines if line.strip()]
            return []
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []


migration_manager = MigrationManager()
