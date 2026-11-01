# PGSync Admin - Backend

**Version:** 0.6.0 (see `pyproject.toml`)
**Framework:** Robyn 0.86+
**Databases:** SQLite (config + jobs + alerts) + ClickHouse (metrics + logs) + OpenSearch (sync target)
**Port:** 3505 (dev and Docker)

---

## Quick Start

### 1. Install Dependencies

```bash
uv sync
```

### 2. Configure Environment

```bash
cp .env.example .env
nano .env  # Set ENCRYPTION_KEY

# Generate encryption key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate JWT signing key:
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set `JWT_SECRET` to the generated value and configure `AUTH_ADMIN_USERNAME` plus a unique `AUTH_ADMIN_PASSWORD` of at least 16 characters. The API refuses to start when these credentials are missing or still use the template values. The frontend login stores the bearer token in browser local storage; signing out removes it from that browser.

For local demos only, `DEMO_LOGIN_CREDENTIALS=true` displays the configured username and password on the login page. Keep it `false` in shared or production environments.

### 3. Initialize Database

```bash
uv run python -m backend.db.init_db
```

### 4. Run Server

```bash
# Development mode
uv run python -m backend.main

```

Server: `http://localhost:3505`

## Configure pipeline types

The Configure form supports four pipeline modes. Test both connections before saving, then use Schema Builder to select tables.

| Mode | Source → destination | Run behavior |
|------|----------------------|--------------|
| Search sync | PostgreSQL, MySQL, or MariaDB → OpenSearch or Elasticsearch | Batch bootstrap or continuous CDC |
| ClickHouse analytics | PostgreSQL → ClickHouse | One source table mirrored to one ClickHouse table; CDC uses the connector daemon |
| Continuous PostgreSQL replication | PostgreSQL → PostgreSQL | Native logical replication through a publication and subscription |
| PostgreSQL table copy | PostgreSQL → PostgreSQL | One-time batch copy or a scheduled batch job |

### Requirements and behavior

- MySQL/MariaDB sources use port `3306` by default; PostgreSQL sources and destinations use `5432`; ClickHouse HTTP uses `8123`.
- Continuous PostgreSQL replication requires logical replication on the source (`wal_level=logical`), source permissions to create a publication, and a target that can connect back to the source. Create compatible destination tables first and leave them empty for the initial copy. Schema definitions are not replicated by PostgreSQL subscriptions.
- Stopping a PostgreSQL subscription pauses it and leaves its replication slot in place. Drop the subscription/publication only after intentionally retiring the pipeline; an inactive slot can retain source WAL.
- PostgreSQL table copy reads complete selected tables. The destination database must already exist. It replaces matching table objects, so the Configure form requires an explicit replacement acknowledgement before the run is enabled. Scheduled copies use the batch job type.
- ClickHouse mirror mode supports one source table per configuration. Relational denormalization into a wide ClickHouse table requires the separate PGSync ClickHouse Pro package.
- Search sync supports multiple related tables where Schema Builder can find the foreign-key path from the selected primary table. MySQL/MariaDB table discovery uses the selected database as its schema.

The root `uv.lock` pins PGSync `7.3.0` because the ClickHouse connector requires that release line. Re-run `uv lock` from the repository root after changing workspace dependencies.

---

## Project Structure

```
backend/
├── main.py                  # Robyn app entry point
├── config.py                # Settings
├── models/                  # SQLAlchemy models (shared Base)
│   ├── __init__.py
│   ├── base.py              # Shared declarative Base
│   ├── configuration.py
│   ├── configuration_history.py
│   ├── execution.py
│   ├── job.py
│   ├── cdc.py               # CDC state tracking
│   ├── migration.py         # Migration model
│   ├── dashboard.py
│   ├── dashboard_widget.py
│   ├── alert_rule.py
│   ├── alert_history.py
│   └── alert_template.py
├── routes/                  # API endpoints
│   ├── config.py
│   ├── discovery.py
│   ├── execution.py
│   ├── logs.py
│   ├── metrics.py
│   ├── summary.py
│   ├── reports.py
│   ├── jobs.py
│   ├── migrations.py
│   ├── dashboards.py
│   ├── alerts.py
│   ├── cdc.py
│   ├── lineage.py
│   └── help.py
├── services/                # Business logic
│   ├── pg_introspector.py
│   ├── schema_generator.py
│   ├── plugin_generator.py
│   ├── migration_service.py
│   ├── execution_service.py
│   ├── job_scheduler.py
│   ├── clickhouse_client.py  # CH auto-connect + DB creation
│   ├── alert_service.py
│   └── lineage_discovery.py
├── db/                      # Database connection
│   ├── sqlite.py            # Single Base.metadata.create_all()
│   └── clickhouse.py
├── scheduler/               # Cron job scheduler
│   └── cron.py
└── utils/                   # Utilities
    ├── crypto.py
    └── validators.py
```

---

## API Reference

All `/api/*` endpoints require a bearer token except `POST /api/auth/login` and the demo-credentials endpoint when `DEMO_LOGIN_CREDENTIALS=true`. The frontend sends the token after login and returns to the login screen when the token expires. `/health` remains public.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Create an admin session using `AUTH_ADMIN_USERNAME` and `AUTH_ADMIN_PASSWORD` |
| `/api/auth/demo-credentials` | GET | Return configured demo credentials only when demo mode is enabled |
| `/health` | GET | Public service health check |

Other API route groups are registered in `backend/routes/`; the list below is a feature summary, not an exhaustive OpenAPI specification.

### Config
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/config/new` | POST | Create config |
| `/api/config/list` | GET | List all configs |
| `/api/config/:id` | GET | Get config detail |
| `/api/config/:id` | PUT | Update config |
| `/api/config/:id` | DELETE | Delete config |

### Discovery
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/discover/test` | POST | Test PG + OpenSearch connectivity |
| `/api/discover/tables` | POST | Discover tables from PostgreSQL |
| `/api/discover/schema` | POST | Get table schema |
| `/api/discover/relationships` | POST | Discover foreign-key relationships |

### Execution
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/execution` | GET | List executions |
| `/api/execution/batch` | POST | Start batch sync |
| `/api/execution/cdc` | POST | Start CDC execution |
| `/api/execution/:id/stop` | POST | Stop execution |
| `/api/execution/:id/status` | GET | Get execution status |

### Logs / Metrics / Reports
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/logs/:execution_id` | GET | Fetch logs (filter by level) |
| `/api/metrics/:execution_id` | GET | Per-table metrics |
| `/api/summary/:execution_id` | GET | Execution summary |
| `/api/reports/daily` | GET | Daily report (default 7 days) |
| `/api/reports/weekly` | GET | Weekly report (default 4 weeks) |
| `/api/reports/table-stats` | GET | Per-table sync stats |
| `/api/reports/export/:format` | GET | CSV/JSON export |

### Jobs
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs` | GET | List jobs |
| `/api/jobs` | POST | Create job |
| `/api/jobs/:id` | PATCH | Update job |
| `/api/jobs/:id` | DELETE | Delete job |
| `/api/jobs/:id/pause` | POST | Pause job |
| `/api/jobs/:id/resume` | POST | Resume job |
| `/api/jobs/:id/run` | POST | Trigger immediate run |

### CDC
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cdc/:config_id/start` | POST | Start CDC |
| `/api/cdc/:config_id/stop` | POST | Stop CDC |
| `/api/cdc/:config_id/status` | GET | Get CDC status |
| `/api/cdc/:config_id/logs` | GET | Get CDC logs |

### Migrations
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/migrations` | GET | List migrations |
| `/api/migrations` | POST | Create migration |
| `/api/migrations/:id` | GET | Get migration detail |
| `/api/migrations/:id/cancel` | POST | Cancel migration |
| `/api/migrations/:id/errors` | GET | Get migration errors |
| `/api/migrations/:id` | DELETE | Delete migration |
| `/api/migrations/preview-schema` | POST | Preview mapping schema |

### Dashboards
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboards` | GET | List dashboards |
| `/api/dashboards` | POST | Create dashboard |
| `/api/dashboards/:id` | GET | Get dashboard |
| `/api/dashboards/:id` | PUT | Update dashboard |
| `/api/dashboards/:id` | DELETE | Delete dashboard |
| `/api/dashboards/:id/widgets` | POST | Add widget |
| `/api/dashboards/:id/widgets/:wid` | PUT | Update widget |
| `/api/dashboards/:id/widgets/:wid` | DELETE | Delete widget |

### Alerts
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/alerts/rules` | GET | List alert rules |
| `/api/alerts/rules` | POST | Create alert rule |
| `/api/alerts/rules/:id` | PUT | Update rule |
| `/api/alerts/rules/:id` | DELETE | Delete rule |
| `/api/alerts/rules/:id/test` | POST | Test notification |
| `/api/alerts/history` | GET | Alert history |
| `/api/alerts/:id/suppress` | POST | Suppress alert for N hours |
| `/api/alerts/templates` | GET | List alert templates |

### Failure recovery
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/failures` | GET | List failed executions (`limit` 1–1000; optional status filter) |
| `/api/failures/:id` | GET | Fetch one failure by ID |
| `/api/failures/:id/retry` | POST | Schedule an actual retry with a backoff strategy |
| `/api/failures/:id/acknowledge` | POST | Mark a failure resolved manually |

### Lineage
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/lineage/graph` | GET | Full lineage graph |
| `/api/lineage/:config_id` | GET | Per-config lineage |
| `/api/lineage/:config_id/discover` | POST | Discover per-config |
| `/api/lineage/discover-all` | POST | Discover all lineage |

---

## Key Technical Details

- **Robyn 0.86+:** Removed `log_level` arg from `app.start()`, removed `configure_static_directory()`
- **SQLAlchemy shared Base:** All models (`Configuration`, `Execution`, `Job`, `CDCState`, `Migration`, `Dashboard`, `AlertRule`, `AlertHistory`) share a single `declarative_base()` from `models/base.py`
- **SQLite init:** `db/sqlite.py` calls `Base.metadata.create_all()` which covers ALL models
- **ClickHouse:** Auto-connects, creates `pgsync_admin` database + `pgsync_logs` + `pgsync_metrics` tables if missing
- **Encryption:** Fernet key-based encryption for stored DB passwords
- **Cron scheduler:** Internal async scheduler for recurring jobs
- **Automatic failure retry:** Retries create a new batch/CDC execution after backoff. The configuration must be active and have a generated PGSync schema; unavailable prerequisites move the failure to dead-letter.
- **Docker:** Includes `pgsync==7.0.5` and `psycopg2-binary` for the batch/CDC subprocess, plus `libpq5` for psycopg v3.

---

## Development

```bash
# Run the backend from this directory
uv run python -m backend.main

# From the repository root, install the backend's test tools and run all tests
uv sync --package pgsync-admin-backend --extra dev
uv run --package pgsync-admin-backend --extra dev pytest pgsync-admin/backend/tests
```

Route integration tests use a temporary SQLite database; they do not need a live PostgreSQL or OpenSearch service. Tests that exercise real sync connections should use dedicated disposable services and credentials.

---

**Maintainer:** QTI Research

## License

This component is covered by the repository [MIT License](../../LICENSE).
