"""CDC (Change Data Capture) service — on-demand sync."""

import json
import logging
import threading
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional, List

from opensearchpy import OpenSearch
import psycopg

from backend.db.sqlite import db
from backend.models.configuration import Configuration
from backend.models.cdc import CDCState, CDCStatus
from backend.utils.crypto import CryptoService

logger = logging.getLogger(__name__)


class CDCService:
    """CDC service with on-demand sync."""

    def __init__(self):
        self.crypto = CryptoService()
        self.execution_logs: Dict[int, List[str]] = {}  # config_id -> logs
        self.sync_threads: Dict[int, threading.Thread] = {}  # config_id -> thread
        self.stop_events: Dict[int, threading.Event] = {}  # config_id -> cooperative cancellation

    def _log(self, config_id: int, message: str):
        """Add log message for config."""
        if config_id not in self.execution_logs:
            self.execution_logs[config_id] = []
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_msg = f"[{timestamp}] {message}"
        self.execution_logs[config_id].append(log_msg)
        logger.info(f"CDC[{config_id}]: {message}")
        print(f"[CDC-{config_id}] {message}")  # Force stdout

    def get_logs(self, config_id: int) -> List[str]:
        """Get execution logs for config."""
        return self.execution_logs.get(config_id, [])

    def record_log(self, config_id: int, message: str) -> None:
        """Append an operational message from another CDC runner."""
        self._log(config_id, message)

    def get_status(self, config_id: int) -> dict:
        """Get CDC status for config."""
        with db.get_session() as session:
            cdc = session.query(CDCState).filter_by(config_id=config_id).first()
            if not cdc:
                return {"config_id": config_id, "status": "not_found"}
            return {
                "id": cdc.id,
                "config_id": cdc.config_id,
                "status": cdc.status,
                "last_sync_time": cdc.last_sync_time.isoformat() if cdc.last_sync_time else None,
                "docs_synced": cdc.docs_synced,
                "error_count": cdc.error_count,
                "last_error": cdc.last_error,
            }

    def start_sync(self, config_id: int) -> dict:
        """Trigger one-time sync for config (background thread)."""
        # Check if already running
        if config_id in self.sync_threads and self.sync_threads[config_id].is_alive():
            return {
                "status": "already_running",
                "config_id": config_id,
                "message": "Sync already in progress",
            }

        self._log(config_id, "=== START CDC SYNC (BACKGROUND) ===")

        # Clear old logs
        self.execution_logs[config_id] = []

        with db.get_session() as session:
            cdc = session.query(CDCState).filter_by(config_id=config_id).first()
            if not cdc:
                self._log(config_id, f"Creating new CDC state")
                cdc = CDCState(
                    config_id=config_id,
                    status=CDCStatus.RUNNING.value,
                    started_at=datetime.utcnow(),
                )
                session.add(cdc)
                session.commit()
            else:
                self._log(config_id, f"Resetting CDC state (prev status: {cdc.status})")
                cdc.status = CDCStatus.RUNNING.value
                cdc.last_sync_time = None
                cdc.error_count = 0
                cdc.last_error = None
                session.commit()

        # Launch background thread
        stop_event = threading.Event()
        self.stop_events[config_id] = stop_event
        thread = threading.Thread(target=self._sync_worker, args=(config_id,), daemon=True)
        self.sync_threads[config_id] = thread
        thread.start()

        return {
            "status": "started",
            "config_id": config_id,
            "message": "Sync started in background. Poll /status for progress.",
        }

    def _sync_worker(self, config_id: int):
        """Background worker for sync."""
        try:
            rows_synced = self._poll_and_sync(config_id)
            stopped = self.stop_events.get(config_id, threading.Event()).is_set()
            self._log(config_id, f"{'Sync stopped' if stopped else '✓ SYNC COMPLETED'}: {rows_synced} rows")

            # Update final status
            with db.get_session() as session:
                cdc = session.query(CDCState).filter_by(config_id=config_id).first()
                if cdc:
                    cdc.status = CDCStatus.STOPPED.value  # Mark as stopped after completion
                    cdc.stopped_at = datetime.utcnow()
                    session.commit()

        except Exception as e:
            self._log(config_id, f"✗ ERROR: {str(e)}")
            logger.error(f"CDC sync error for config {config_id}: {e}")
            with db.get_session() as session:
                cdc = session.query(CDCState).filter_by(config_id=config_id).first()
                if cdc:
                    cdc.status = CDCStatus.ERROR.value
                    cdc.error_count = (cdc.error_count or 0) + 1
                    cdc.last_error = str(e)
                    cdc.last_error_time = datetime.utcnow()
                    session.commit()
        finally:
            self.stop_events.pop(config_id, None)

    def stop_sync(self, config_id: int) -> dict:
        """Request a safe stop; the worker updates persisted status when it exits."""
        thread = self.sync_threads.get(config_id)
        stop_event = self.stop_events.get(config_id)
        if thread and thread.is_alive() and stop_event:
            stop_event.set()
            self._log(config_id, "Stop requested; finishing the current document")
            return {"status": "stopping", "config_id": config_id}

        with db.get_session() as session:
            cdc = session.query(CDCState).filter_by(config_id=config_id).first()
            if cdc:
                cdc.status = CDCStatus.STOPPED.value
                cdc.stopped_at = datetime.utcnow()
                session.commit()
            return {"status": "stopped", "config_id": config_id}

    def _poll_and_sync(self, config_id: int) -> int:
        """Poll PostgreSQL → index to OpenSearch."""
        stop_event = self.stop_events.get(config_id)
        with db.get_session() as session:
            config = session.query(Configuration).filter_by(id=config_id).first()
            if not config:
                raise ValueError(f"Configuration {config_id} not found")

            self._log(config_id, f"Loading config: {config.name}")

            # Parse schema to get table → index mapping
            try:
                schema = json.loads(config.schema_config) if config.schema_config else {}
                schema_root = schema.get("nodes") or schema
                pg_table = schema.get("main_table") or schema_root.get("table")
                os_index = schema.get("index")
                self._log(config_id, f"Schema mapping: PG table '{pg_table}' → OS index '{os_index}'")
            except Exception as e:
                self._log(config_id, f"⊘ Failed to parse schema: {e}, using default mapping")
                pg_table = None
                os_index = None

            # Decrypt PG password
            try:
                pg_password = self.crypto.decrypt(config.source_pg_password)
                if not pg_password or pg_password == "***":
                    raise ValueError("PG password is masked - cannot decrypt")
                self._log(config_id, "✓ PG password decrypted")
            except Exception as e:
                self._log(config_id, f"✗ Failed to decrypt PG password: {e}")
                raise ValueError(f"Cannot decrypt source database password: {e}")

            # Decrypt OS password
            target = json.loads(config.target_config)
            raw_password = target.get("password", "")
            if raw_password == "***":
                raise ValueError("OpenSearch password is masked - please edit config")

            try:
                if raw_password:
                    os_password = self.crypto.decrypt(raw_password)
                else:
                    os_password = None
                self._log(config_id, "✓ OpenSearch credentials prepared")
            except Exception as e:
                self._log(config_id, f"✗ Failed to decrypt OS password: {e}")
                raise ValueError(f"Cannot decrypt OpenSearch password: {e}")

            # Build PG connection string
            pg_dsn = f"host={config.source_pg_host} port={config.source_pg_port} dbname={config.source_pg_database} user={config.source_pg_user} password={pg_password}"
            self._log(config_id, f"Connecting to PostgreSQL: {config.source_pg_host}:{config.source_pg_port}/{config.source_pg_database}")

            # Test PG connection
            try:
                with psycopg.connect(pg_dsn) as pg_conn:
                    with pg_conn.cursor() as cur:
                        cur.execute("SELECT 1")
                    self._log(config_id, "✓ PostgreSQL connection OK")
            except Exception as e:
                self._log(config_id, f"✗ PostgreSQL connection FAILED: {e}")
                raise ValueError(f"Cannot connect to PostgreSQL: {e}")

            # Connect to OpenSearch
            try:
                os_client = OpenSearch(
                    hosts=[{
                        "host": target["host"],
                        "port": int(target.get("port", 9200)),
                        "scheme": target.get("scheme", "https"),
                    }],
                    http_auth=(target["user"], os_password) if target.get("user") and os_password else None,
                    use_ssl=target.get("scheme", "https") == "https",
                    verify_certs=bool(target.get("verify_certs", True)),
                    timeout=30,
                )
                # Test connection
                os_client.info()
                self._log(config_id, f"✓ OpenSearch connection OK ({target['host']})")
            except Exception as e:
                self._log(config_id, f"✗ OpenSearch connection FAILED: {e}")
                raise ValueError(f"Cannot connect to OpenSearch: {e}")

            # Get table list from target config
            tables = target.get("tables", [])
            self._log(config_id, f"Tables to sync: {', '.join(tables) if tables else 'NONE'}")

            if not tables:
                schema_root = schema.get("nodes") or schema
                if pg_table:
                    tables = [pg_table, *(child.get("table") for child in schema_root.get("children", []) if child.get("table"))]
                else:
                    with psycopg.connect(pg_dsn) as pg_conn:
                        with pg_conn.cursor() as cur:
                            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                            tables = [r[0] for r in cur.fetchall()]
                target["tables"] = tables
                config.target_config = json.dumps(target)
                session.commit()
                self._log(config_id, f"Auto-detected {len(tables)} tables")

            rows_synced = 0

            for table in tables:
                if stop_event and stop_event.is_set():
                    break
                self._log(config_id, f"Processing table: {table}")

                # Determine OpenSearch index name
                # If schema mapping exists and table matches, use schema.index
                # Otherwise use table name as index
                if pg_table and table == pg_table and os_index:
                    index_name = os_index
                    self._log(config_id, f"  Using schema-mapped index: {index_name}")
                else:
                    index_name = table
                    self._log(config_id, f"  Using table name as index: {index_name}")

                # Get last sync checkpoint
                with db.get_session() as s:
                    cdc_state = s.query(CDCState).filter_by(config_id=config_id).first()
                    checkpoint = cdc_state.last_sync_time if cdc_state and cdc_state.last_sync_time else datetime(2000, 1, 1)

                try:
                    with psycopg.connect(pg_dsn) as pg_conn:
                        with pg_conn.cursor() as cur:
                            # Find timestamp column
                            cur.execute("""
                                SELECT column_name FROM information_schema.columns
                                WHERE table_name = %s
                                AND data_type IN ('timestamp without time zone','timestamp with time zone','timestamp','date','datetime')
                                ORDER BY CASE
                                  WHEN column_name IN ('updated_date','updated_at','updated_time') THEN 1
                                  WHEN column_name IN ('modified_date','modified_at') THEN 2
                                  WHEN column_name IN ('created_date','created_at','tanggal_laporan') THEN 3
                                  ELSE 4
                                END
                                LIMIT 1
                            """, (table,))
                            ts_col = cur.fetchone()
                            if not ts_col:
                                self._log(config_id, f"⊘ No timestamp column found, skipping {table}")
                                continue
                            ts_col = ts_col[0]
                            self._log(config_id, f"  Timestamp column: {ts_col}")

                            # Query changed rows
                            self._log(config_id, f"  Querying rows since checkpoint: {checkpoint}")
                            cur.execute(f"""
                                SELECT * FROM "{table}"
                                WHERE "{ts_col}" > %s
                                ORDER BY "{ts_col}" ASC
                                LIMIT 1000
                            """, (checkpoint,))
                            columns = [desc[0] for desc in cur.description]
                            rows = cur.fetchall()
                            self._log(config_id, f"  Found {len(rows)} rows")

                    if not rows:
                        self._log(config_id, f"  → No new rows (checkpoint: {checkpoint})")
                        continue

                    # Index each row to OpenSearch (using mapped index name)
                    table_rows_synced = 0
                    for row in rows:
                        if stop_event and stop_event.is_set():
                            break
                        doc = {col: row[i] for i, col in enumerate(columns)}
                        # Remove Decimal types + truncate long text fields
                        for k, v in doc.items():
                            if isinstance(v, Decimal):
                                doc[k] = float(v)
                            elif isinstance(v, str) and len(v.encode('utf-8')) > 30000:
                                # Truncate to 30KB to avoid OpenSearch byte limit (max 32766)
                                truncated = v.encode('utf-8')[:30000].decode('utf-8', errors='ignore')
                                self._log(config_id, f"  ✂ Truncated field '{k}' from {len(v.encode('utf-8'))} bytes to 30000 bytes")
                                doc[k] = truncated
                        doc_id = doc.get("id") or hex(hash(json.dumps(dict(doc), sort_keys=True, default=str)))[2:]
                        os_client.index(index=index_name, id=str(doc_id), body=doc)
                        rows_synced += 1
                        table_rows_synced += 1

                    self._log(config_id, f"  → Indexed {table_rows_synced} rows to OpenSearch index '{index_name}'")

                    # Update checkpoint
                    latest_ts = rows[table_rows_synced - 1][columns.index(ts_col)] if table_rows_synced else checkpoint
                    with db.get_session() as s:
                        cdc_state = s.query(CDCState).filter_by(config_id=config_id).first()
                        if cdc_state:
                            cdc_state.last_sync_time = latest_ts.replace(tzinfo=None) if hasattr(latest_ts, 'tzinfo') and latest_ts.tzinfo else latest_ts
                            cdc_state.docs_synced = (cdc_state.docs_synced or 0) + table_rows_synced
                            cdc_state.status = CDCStatus.RUNNING.value
                            s.commit()
                            self._log(config_id, f"  → Checkpoint updated: {cdc_state.last_sync_time}")

                except Exception as e:
                    self._log(config_id, f"✗ Error syncing {table}: {e}")
                    logger.error(f"CDC error syncing table {table}: {e}")

            os_client.close()
            self._log(config_id, f"Total rows synced: {rows_synced}")
            return rows_synced


cdc_service = CDCService()
