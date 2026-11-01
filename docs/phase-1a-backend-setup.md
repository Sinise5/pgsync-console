# Phase 1a: Backend Setup + Config Management

**Version:** v0.6.0
**Duration:** 2 weeks
**Target:** 2026-07-10
**Status:** 🔄 In Progress

---

## Overview

Build Robyn-based backend API for PGSync configuration management with:
- PostgreSQL schema introspection
- Auto-generate PGSync JSON schema + plugin code
- Config versioning & rollback
- SQLite persistence

---

## Architecture

```
pgsync-admin/backend/
├── main.py                    # Robyn app entry point
├── config.py                  # Settings (env vars)
├── models/                    # SQLAlchemy ORM
│   ├── __init__.py
│   ├── configuration.py       # Config model
│   ├── configuration_history.py
│   └── execution.py
├── routes/                    # API endpoints
│   ├── __init__.py
│   ├── config.py              # CRUD /api/config/*
│   └── discovery.py           # /api/discover/*
├── services/                  # Business logic
│   ├── __init__.py
│   ├── pg_introspector.py     # Schema discovery
│   ├── schema_generator.py    # Auto-gen PGSync JSON
│   └── plugin_generator.py    # Auto-gen plugin code
├── db/
│   ├── __init__.py
│   └── sqlite.py              # Connection pool
└── utils/
    ├── __init__.py
    ├── crypto.py              # Password encryption
    └── validators.py          # Input validation
```

---

## Database Schema (SQLite)

### Table: `configurations`

Stores PGSync configuration state.

```sql
CREATE TABLE configurations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT,

  -- Source PostgreSQL
  source_pg_host TEXT NOT NULL,
  source_pg_port INTEGER NOT NULL DEFAULT 5432,
  source_pg_database TEXT NOT NULL,
  source_pg_user TEXT NOT NULL,
  source_pg_password TEXT NOT NULL,  -- encrypted with Fernet

  -- Target storage
  target_type TEXT NOT NULL,  -- opensearch, elasticsearch, redis
  target_config TEXT NOT NULL,  -- JSON string

  -- Schema config (user selections)
  schema_config TEXT NOT NULL,  -- JSON: {main_table, children, fields, fk_mappings}

  -- Generated artifacts
  pgsync_schema_json TEXT,      -- Generated PGSync schema
  plugin_code TEXT,              -- Generated plugin Python code

  -- Versioning
  version INTEGER DEFAULT 1,

  -- Metadata
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  is_active INTEGER DEFAULT 1,

  -- Constraints
  CHECK (target_type IN ('opensearch', 'elasticsearch', 'redis')),
  CHECK (source_pg_port > 0 AND source_pg_port < 65536)
);

CREATE INDEX idx_configurations_name ON configurations(name);
CREATE INDEX idx_configurations_active ON configurations(is_active);
```

### Table: `configuration_history`

Version history for rollback capability.

```sql
CREATE TABLE configuration_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  config_id INTEGER NOT NULL,
  version INTEGER NOT NULL,

  -- Snapshot of config at this version
  schema_config TEXT NOT NULL,
  pgsync_schema_json TEXT,
  plugin_code TEXT,

  -- Metadata
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  created_by TEXT,  -- Future: user ID
  change_description TEXT,

  FOREIGN KEY (config_id) REFERENCES configurations(id) ON DELETE CASCADE,
  UNIQUE(config_id, version)
);

CREATE INDEX idx_history_config ON configuration_history(config_id, version DESC);
```

### Table: `executions`

Track batch/CDC execution state.

```sql
CREATE TABLE executions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  config_id INTEGER NOT NULL,

  type TEXT NOT NULL,  -- batch, cdc
  status TEXT NOT NULL,  -- pending, running, completed, failed, paused

  -- Timing
  started_at TEXT,
  completed_at TEXT,

  -- Progress
  progress_pct REAL DEFAULT 0,
  total_docs INTEGER DEFAULT 0,
  synced_docs INTEGER DEFAULT 0,

  -- Error handling
  error_message TEXT,
  error_stack TEXT,

  -- Checkpoint (for resume)
  checkpoint TEXT,  -- JSON: {last_processed_id, table, timestamp}

  FOREIGN KEY (config_id) REFERENCES configurations(id) ON DELETE CASCADE,
  CHECK (type IN ('batch', 'cdc')),
  CHECK (status IN ('pending', 'running', 'completed', 'failed', 'paused'))
);

CREATE INDEX idx_executions_config ON executions(config_id);
CREATE INDEX idx_executions_status ON executions(status);
```

---

## API Endpoints Specification

### 1. Config Management

#### `POST /api/config/new`

Create new configuration.

**Request:**
```json
{
  "name": "laporan-production",
  "description": "Production sync for laporan table",
  "source": {
    "host": "localhost",
    "port": 5432,
    "database": "siitpartisi",
    "user": "postgres",
    "password": "***"
  },
  "target": {
    "type": "opensearch",
    "host": "localhost",
    "port": 9200,
    "user": "admin",
    "password": "***",
    "use_ssl": true,
    "verify_certs": false
  },
  "schema": {
    "main_table": "laporan",
    "children": [
      {
        "table": "laporan_isi",
        "fields": ["isi", "apa", "mengapa", "bagaimana", "kapan"],
        "relationship": {
          "foreign_key": {"parent": "id", "child": "laporan_id"},
          "type": "one_to_many",
          "variant": "object"
        }
      }
    ],
    "fk_mappings": {
      "jenis_id": {"table": "referensi", "output_key": "jenis"},
      "klasifikasi_id": {"table": "referensi", "output_key": "klasifikasi"}
    }
  }
}
```

**Response (201):**
```json
{
  "id": 1,
  "name": "laporan-production",
  "version": 1,
  "created_at": "2026-06-19T10:00:00Z",
  "pgsync_schema_json": "...",  // Generated schema
  "plugin_code": "..."           // Generated plugin
}
```

**Errors:**
- `400` — Validation error (missing fields, invalid port)
- `409` — Config name already exists
- `500` — Internal error

---

#### `GET /api/config/:id`

Get configuration by ID.

**Response (200):**
```json
{
  "id": 1,
  "name": "laporan-production",
  "description": "...",
  "source": { "host": "...", "database": "..." },
  "target": { "type": "opensearch", "host": "..." },
  "schema": { "main_table": "laporan", "children": [...] },
  "version": 1,
  "created_at": "2026-06-19T10:00:00Z",
  "updated_at": "2026-06-19T10:00:00Z",
  "is_active": true
}
```

**Note:** Passwords are **NEVER** returned in API responses.

---

#### `PUT /api/config/:id`

Update configuration (creates new version in history).

**Request:**
```json
{
  "description": "Updated description",
  "schema": {
    "main_table": "laporan",
    "children": [
      {
        "table": "laporan_isi",
        "fields": ["isi", "apa", "mengapa"]  // Reduced fields
      }
    ]
  }
}
```

**Response (200):**
```json
{
  "id": 1,
  "version": 2,  // Incremented
  "updated_at": "2026-06-19T11:00:00Z",
  "pgsync_schema_json": "...",  // Regenerated
  "plugin_code": "..."
}
```

---

#### `DELETE /api/config/:id`

Soft delete (set `is_active = 0`).

**Response (204):** No content

---

#### `GET /api/config/list`

List all active configurations.

**Query params:**
- `page` (default: 1)
- `size` (default: 20)
- `include_inactive` (default: false)

**Response (200):**
```json
{
  "total": 5,
  "page": 1,
  "size": 20,
  "configs": [
    {
      "id": 1,
      "name": "laporan-production",
      "description": "...",
      "source_database": "siitpartisi",
      "target_type": "opensearch",
      "version": 2,
      "created_at": "2026-06-19T10:00:00Z",
      "is_active": true
    }
  ]
}
```

---

#### `POST /api/config/:id/rollback`

Rollback to previous version.

**Request:**
```json
{
  "target_version": 1
}
```

**Response (200):**
```json
{
  "id": 1,
  "version": 3,  // New version created from v1 snapshot
  "rolled_back_from": 2,
  "rolled_back_to": 1,
  "updated_at": "2026-06-19T12:00:00Z"
}
```

---

### 2. Schema Discovery

#### `POST /api/discover/test-connection`

Test PostgreSQL connection.

**Request:**
```json
{
  "host": "localhost",
  "port": 5432,
  "database": "siitpartisi",
  "user": "postgres",
  "password": "***"
}
```

**Response (200):**
```json
{
  "success": true,
  "server_version": "15.14",
  "database_size": "450GB",
  "table_count": 89
}
```

**Error (400):**
```json
{
  "success": false,
  "error": "Connection timeout",
  "details": "Host unreachable"
}
```

---

#### `GET /api/discover/tables`

List all tables in database.

**Headers:**
- `X-Connection-Id: <temp_conn_id>` (from test-connection)

**Query params:**
- `schema` (default: public)
- `search` (filter by name)

**Response (200):**
```json
{
  "tables": [
    {
      "name": "laporan",
      "schema": "public",
      "row_count": 4400000,
      "size": "12GB",
      "has_primary_key": true,
      "columns": [
        {"name": "id", "type": "integer", "nullable": false, "is_pk": true},
        {"name": "nomor", "type": "character varying", "nullable": true},
        {"name": "judul", "type": "text", "nullable": true}
      ]
    }
  ]
}
```

---

#### `GET /api/discover/schema/:table`

Get table schema + detected relationships.

**Response (200):**
```json
{
  "table": "laporan",
  "columns": [
    {"name": "id", "type": "integer", "nullable": false, "is_pk": true},
    {"name": "jenis_id", "type": "integer", "nullable": true, "is_fk": true}
  ],
  "foreign_keys": [
    {
      "column": "jenis_id",
      "references": {"table": "referensi", "column": "id"}
    }
  ],
  "children": [
    {
      "table": "laporan_isi",
      "foreign_key": {"parent": "id", "child": "laporan_id"},
      "columns": ["id", "laporan_id", "isi", "apa", "mengapa"]
    }
  ]
}
```

---
