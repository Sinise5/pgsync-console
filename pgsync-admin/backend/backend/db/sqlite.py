"""SQLite database connection and initialization."""

import logging
from pathlib import Path
from sqlalchemy import create_engine, Engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session

from backend.config import settings
from backend.models import Configuration, ConfigurationHistory, Execution, Migration
from backend.models.configuration import Base

logger = logging.getLogger(__name__)


class SQLiteDB:
    """SQLite database connection manager."""

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file (default from config)
        """
        self.db_path = db_path or settings.sqlite_db_path
        self.engine: Engine | None = None
        self.SessionLocal: sessionmaker | None = None

    def connect(self) -> None:
        """Create database connection and tables."""
        db_url = f"sqlite:///{self.db_path}"
        logger.info(f"Connecting to SQLite: {self.db_path}")

        self.engine = create_engine(db_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Create all tables from shared Base
        Base.metadata.create_all(self.engine)
        # create_all does not add columns to databases created by older versions.
        if "executions" in inspect(self.engine).get_table_names():
            columns = {column["name"] for column in inspect(self.engine).get_columns("executions")}
            if "pid" not in columns:
                with self.engine.begin() as connection:
                    connection.execute(text("ALTER TABLE executions ADD COLUMN pid INTEGER"))
        if "configurations" in inspect(self.engine).get_table_names():
            columns = {column["name"] for column in inspect(self.engine).get_columns("configurations")}
            with self.engine.begin() as connection:
                if "source_type" not in columns:
                    connection.execute(text(
                        "ALTER TABLE configurations ADD COLUMN source_type VARCHAR(20) NOT NULL DEFAULT 'postgres'"
                    ))
                if "pipeline_type" not in columns:
                    connection.execute(text(
                        "ALTER TABLE configurations ADD COLUMN pipeline_type VARCHAR(32) NOT NULL DEFAULT 'pg_search'"
                    ))
        logger.info("Database tables created/verified")

    def get_session(self) -> Session:
        """Get database session.

        Returns:
            SQLAlchemy session

        Raises:
            RuntimeError: If not connected
        """
        if not self.SessionLocal:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self.SessionLocal()

    def disconnect(self) -> None:
        """Close database connection."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database disconnected")

    def init_db(self) -> None:
        """Initialize database schema."""
        self.connect()
        logger.info("Database initialized")


# Global database instance
db = SQLiteDB()
