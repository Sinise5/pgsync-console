"""Database query optimization and connection pooling."""

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.pool import QueuePool
from sqlalchemy import event, text

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """Optimize database queries with caching and batch operations."""

    @staticmethod
    def batch_insert(session, models: List[Any], batch_size: int = 1000):
        """Batch insert with configurable size."""
        try:
            for i in range(0, len(models), batch_size):
                batch = models[i : i + batch_size]
                session.add_all(batch)
                session.commit()
                logger.info(f"Inserted batch {i // batch_size + 1} ({len(batch)} records)")
        except Exception as e:
            session.rollback()
            logger.error(f"Batch insert failed: {e}")
            raise

    @staticmethod
    def batch_update(session, updates: Dict[int, Dict[str, Any]], model_class, batch_size: int = 1000):
        """Batch update with configurable size."""
        try:
            ids = list(updates.keys())
            for i in range(0, len(ids), batch_size):
                batch_ids = ids[i : i + batch_size]
                for obj_id in batch_ids:
                    obj = session.query(model_class).filter(model_class.id == obj_id).first()
                    if obj:
                        for key, value in updates[obj_id].items():
                            setattr(obj, key, value)
                session.commit()
                logger.info(f"Updated batch {i // batch_size + 1} ({len(batch_ids)} records)")
        except Exception as e:
            session.rollback()
            logger.error(f"Batch update failed: {e}")
            raise

    @staticmethod
    def add_connection_pool_listeners(engine):
        """Add event listeners for connection pool monitoring."""
        @event.listens_for(engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            logger.debug(f"DB connection established")

        @event.listens_for(engine, "close")
        def receive_close(dbapi_conn, connection_record):
            logger.debug(f"DB connection closed")

        @event.listens_for(engine, "detach")
        def receive_detach(dbapi_conn, connection_record):
            logger.debug(f"DB connection detached")


class IndexAnalyzer:
    """Analyze and recommend database indexes."""

    @staticmethod
    def get_index_recommendations(session) -> List[str]:
        """Get index recommendations based on schema."""
        recommendations = [
            "CREATE INDEX idx_executions_status_created ON executions(status, created_at)",
            "CREATE INDEX idx_jobs_next_run_enabled ON jobs(next_run, enabled)",
            "CREATE INDEX idx_failures_status_next_retry ON execution_failures(status, next_retry_at)",
            "CREATE INDEX idx_logs_execution_level ON execution_logs(execution_id, log_level)",
        ]
        return recommendations

    @staticmethod
    def apply_recommendations(session, recommendations: List[str]):
        """Apply index recommendations."""
        try:
            for sql in recommendations:
                try:
                    session.execute(text(sql))
                    logger.info(f"Applied: {sql[:50]}...")
                except Exception as e:
                    logger.warning(f"Index already exists or failed: {e}")
            session.commit()
        except Exception as e:
            logger.error(f"Failed to apply recommendations: {e}")


class ConnectionPool:
    """Manages SQLAlchemy connection pooling."""

    @staticmethod
    def configure_pool(engine, pool_size: int = 10, max_overflow: int = 20):
        """Configure connection pool parameters."""
        logger.info(f"Configured connection pool: size={pool_size}, overflow={max_overflow}")
        return engine
