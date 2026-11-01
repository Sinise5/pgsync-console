"""Database initialization script.

Usage:
    uv run python -m backend.db.init_db

    With custom path:
    SQLITE_DB_PATH=/path/to/db.db uv run python -m backend.db.init_db
"""

import logging
import sys
from pathlib import Path

from backend.db import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> int:
    """Initialize database and exit."""
    db_path = db.db_path

    logger.info(f"Initializing database at: {db_path}")

    try:
        db.init_db()
        logger.info(f"Database initialized successfully at: {db_path}")
        return 0
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
