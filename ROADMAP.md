# PGSync Admin - Product Roadmap

## Vision
**Enterprise-grade visual configuration & monitoring platform for PGSync CDC pipelines.**

Transform PGSync from CLI-only tool to full-stack visual platform with:
- Zero-code schema builder (point-and-click table/relationship selection)
- Live monitoring dashboard (logs, metrics, alerting)
- Multi-storage sink support (OpenSearch, Elasticsearch, Redis, Pinecone)
- Advanced analytics (latency tracking, throughput analysis, error reporting)

---

## Release Timeline

| Version | Target | Focus | Status |
|---------|--------|-------|--------|
| **v0.5.0** | 2026-06-19 | ✅ Current baseline (PGSync CDC + Search API working) | Released |
| **v0.6.0** | 2026-07-10 | Phase 1a: Backend setup + config management | 🔄 In Progress |
| **v0.7.0** | 2026-07-24 | Phase 1b: Batch/CDC orchestration | Planned |
| **v0.8.0** | 2026-08-07 | Phase 1c: Frontend config builder | Planned |
| **v0.9.0** | 2026-08-21 | Phase 1d: Monitoring dashboard | Planned |
| **v1.0.0** | 2026-08-28 | MVP Release (Phase 1 complete) | Planned |
| **v1.5.0** | 2026-09-25 | Phase 2: Multi-storage adapters | Future |
| **v2.0.0** | 2026-10-23 | Phase 3: Advanced analytics & alerting | Future |

---

## Phase 1: MVP (v0.6.0 - v1.0.0)

### Phase 1a: Backend Setup + Config Management (v0.6.0)
**Duration:** 2 weeks
**Target:** 2026-07-10

#### Deliverables
- [x] Project structure setup (`pgsync-admin/` monorepo member)
- [ ] Robyn 0.84+ backend skeleton
- [ ] SQLite database schema (config, state, execution tracking)
- [ ] Config CRUD API endpoints
- [ ] PostgreSQL schema introspection service
- [ ] Auto-generate PGSync JSON schema from config
- [ ] Config versioning (rollback capability)
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Unit tests (pytest)

#### API Endpoints
```
POST   /api/config/new              # Create new config
GET    /api/config/:id              # Get config by ID
PUT    /api/config/:id              # Update config
DELETE /api/config/:id              # Delete config
GET    /api/config/list             # List all configs
POST   /api/config/:id/rollback     # Rollback to previous version

POST   /api/discover/test-connection  # Test PG connection
GET    /api/discover/tables          # List PG tables
GET    /api/discover/schema/:table   # Get table schema + relationships
POST   /api/generate/schema          # Generate PGSync JSON + plugin code
```

#### Database Schema (SQLite)
```sql
-- Config storage
CREATE TABLE configurations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  source_pg_host TEXT NOT NULL,
  source_pg_port INTEGER NOT NULL,
  source_pg_database TEXT NOT NULL,
  source_pg_user TEXT NOT NULL,
  source_pg_password TEXT NOT NULL, -- encrypted
  target_type TEXT NOT NULL,  -- opensearch, elasticsearch, redis
  target_config JSON NOT NULL,
  schema_config JSON NOT NULL,  -- selected tables, fields, relationships
  pgsync_schema_json TEXT,      -- generated schema
  plugin_code TEXT,              -- generated plugin
  version INTEGER DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  is_active BOOLEAN DEFAULT 1
);

-- Config history (for rollback)
CREATE TABLE configuration_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  config_id INTEGER NOT NULL,
  version INTEGER NOT NULL,
  schema_config JSON NOT NULL,
  pgsync_schema_json TEXT,
  plugin_code TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (config_id) REFERENCES configurations(id)
);

-- Execution state
CREATE TABLE executions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  config_id INTEGER NOT NULL,
  type TEXT NOT NULL,  -- batch, cdc
  status TEXT NOT NULL,  -- pending, running, completed, failed, paused
  started_at DATETIME,
  completed_at DATETIME,
  progress_pct REAL DEFAULT 0,
  total_docs INTEGER DEFAULT 0,
  synced_docs INTEGER DEFAULT 0,
  error_message TEXT,
  checkpoint JSON,  -- for resume
  FOREIGN KEY (config_id) REFERENCES configurations(id)
);
```

---

### Phase 1b: Batch/CDC Orchestration (v0.7.0)
**Duration:** 2 weeks
**Target:** 2026-07-24

#### Deliverables
- [ ] Batch migration orchestrator (Docker container spawn)
- [ ] CDC daemon manager (subprocess + health check)
- [ ] Progress tracking (checkpoint, resume)
- [ ] Process lifecycle management (start, stop, restart, pause)
- [ ] Log streaming to ClickHouse
- [ ] Metrics collection (latency, throughput)
- [ ] Error handling & retry logic
- [ ] Background task scheduler (Robyn background workers)

#### API Endpoints
```
POST   /api/execute/batch/:config_id        # Start batch migration
POST   /api/execute/cdc/:config_id          # Start CDC daemon
POST   /api/execute/stop/:execution_id      # Stop running process
POST   /api/execute/pause/:execution_id     # Pause batch (checkpoint)
POST   /api/execute/resume/:execution_id    # Resume from checkpoint
GET    /api/execute/status/:execution_id    # Get execution status
```

#### ClickHouse Schema
```sql
-- Logs table
CREATE TABLE logs (
  timestamp DateTime,
  execution_id Int32,
  config_id Int32,
  level String,         -- INFO, WARNING, ERROR, DEBUG
  process String,       -- batch, cdc, api
  table_name String,
  message String,
  context String        -- JSON string
) ENGINE = MergeTree()
ORDER BY (timestamp, execution_id)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 90 DAY;  -- Keep 90 days

-- Metrics table
CREATE TABLE metrics (
  timestamp DateTime,
  execution_id Int32,
  config_id Int32,
  table_name String,
  operation String,     -- insert, update, delete
  latency_ms Float32,
  row_count Int32,
  error_count Int32
) ENGINE = MergeTree()
ORDER BY (timestamp, config_id, table_name)
PARTITION BY toYYYYMM(timestamp)
TTL timestamp + INTERVAL 180 DAY;  -- Keep 180 days
```

---

### Phase 1c: Frontend Config Builder (v0.8.0)
**Duration:** 1.5 weeks
**Target:** 2026-08-07

#### Deliverables
- [ ] SolidJS + shadcn/ui project setup
- [ ] Database connector form (PG credentials)
- [ ] Schema discovery viewer (table list)
- [ ] Relationship picker (tree view)
- [ ] Field selector (checkbox multi-select)
- [ ] FK resolution config (which fields denormalize)
- [ ] Target storage selector (OpenSearch, Elasticsearch)
- [ ] Schema preview (generated JSON diff)
- [ ] Save/load config
- [ ] Responsive design (desktop + tablet)

#### Pages
```
/config/new             # New configuration wizard
/config/:id/edit        # Edit existing config
/config/list            # All configs (table view)
/config/:id/preview     # Preview generated schema
```

#### Key Components
```tsx
<DatabaseConnector />        // PG credentials form + test connection
<SchemaExplorer />          // Table list with search/filter
<RelationshipTree />        // Nested tree with checkboxes
<FieldSelector />           // Multi-select with preview
<StorageTargetConfig />     // OpenSearch/ES connection form
<SchemaPreview />           // JSON diff viewer (before/after)
<ConfigActions />           // Save, Test, Deploy buttons
```

---

### Phase 1d: Monitoring Dashboard (v0.9.0)
**Duration:** 1.5 weeks
**Target:** 2026-08-21

#### Deliverables
- [ ] Live log viewer (WebSocket stream)
- [ ] Execution status dashboard
- [ ] Latency charts (per table, rolling 1h/24h)
- [ ] Throughput gauge (docs/sec)
- [ ] Error list (last 100, filterable)
- [ ] Execution history table
- [ ] Start/stop/pause controls
- [ ] Export reports (CSV, JSON)

#### Pages
```
/monitor/:execution_id      # Live execution monitoring
/monitor/history            # All executions (filterable)
/monitor/metrics            # Aggregate metrics dashboard
```

#### Key Components
```tsx
<LiveLogViewer />           // WebSocket + virtualized list
<StatusBadge />             // Running, Completed, Failed
<LatencyChart />            // ApexCharts/Recharts time-series
<ThroughputGauge />         // Real-time gauge
<ErrorPanel />              // Error list with details
<ExecutionControls />       // Start/Stop/Pause buttons
<MetricsGrid />             // Cards: total docs, avg latency, errors
```

---

### Phase 1e: Testing & Deployment (v1.0.0)
**Duration:** 1 week
**Target:** 2026-08-28

#### Deliverables
- [ ] E2E testing (Playwright)
- [ ] Integration tests (backend API)
- [ ] Load testing (batch migration with 4.4M docs)
- [ ] Docker Compose setup (admin backend + frontend + ClickHouse)
- [ ] Deployment guide (bare metal + Docker)
- [ ] User documentation
- [ ] Migration guide (v0.5.0 → v1.0.0)
- [ ] Release notes

---

## Phase 2: Multi-Storage & Advanced Features (v1.5.0)

**Duration:** 4 weeks
**Target:** 2026-09-25

### Features
- [ ] Storage adapter pattern (abstract base class)
- [ ] Elasticsearch adapter
- [ ] Redis adapter (JSON storage)
- [ ] Pinecone adapter (vector embeddings)
- [ ] Custom storage plugin API
- [ ] Storage health checks
- [ ] Storage-specific schema validation
- [ ] Migration between storage types

### New API Endpoints
```
GET    /api/storage/supported       # List supported storage types
POST   /api/storage/test-connection # Test target storage
GET    /api/storage/:type/schema    # Get storage-specific schema template
```

---

## Phase 3: Advanced Analytics & Alerting (v2.0.0)

**Duration:** 4 weeks
**Target:** 2026-10-23

### Features
- [ ] Advanced reports (daily/weekly/monthly)
- [ ] Custom dashboards (user-defined metrics)
- [ ] Alerting rules (threshold-based)
- [ ] Notification channels (Telegram, email, webhook)
- [ ] Data lineage visualization
- [ ] A/B testing (shadow index)
- [ ] Performance regression detection
- [ ] Cost estimation (storage, compute)
- [ ] Role-based access control (RBAC)
- [ ] Audit logs

### New Pages
```
/reports/overview           # Executive summary
/reports/custom             # Custom report builder
/alerts/rules               # Alert rule management
/alerts/history             # Alert history
/lineage/:config_id         # Data lineage graph
```

---

## Technical Debt & Improvements

### Ongoing (Every Phase)
- [ ] Performance optimization (query caching, batch writes)
- [ ] Security hardening (encrypt at rest, audit logs)
- [ ] Documentation updates
- [ ] Dependency upgrades
- [ ] CI/CD pipeline improvements

### Future Considerations
- [ ] Multi-tenant support (separate workspaces)
- [ ] ClickHouse clustering (scale monitoring)
- [ ] Distributed tracing (OpenTelemetry)
- [ ] GraphQL API (alternative to REST)
- [ ] Real-time collaboration (multi-user config editing)

---

## Success Metrics (KPIs)

| Metric | Baseline (v0.5.0) | Target (v1.0.0) | Target (v2.0.0) |
|--------|-------------------|-----------------|-----------------|
| **Config Time** | 2 hours (manual) | 15 minutes | 5 minutes |
| **MTTR (Mean Time To Recovery)** | 30 minutes | 5 minutes | 2 minutes |
| **Visibility** | Manual log checking | Live dashboard | Predictive alerts |
| **Supported Storage** | 1 (OpenSearch) | 1 | 4+ |
| **User Satisfaction** | N/A | 8/10 | 9/10 |

---

## Dependencies & Integrations

### External Services
- PostgreSQL 15+ (source)
- OpenSearch 2.x / 3.x (target)
- ClickHouse 23+ (telemetry)
- Redis 7+ (optional cache)

### Libraries
- **Backend:** Robyn 0.84+, SQLAlchemy 2.x, psycopg2, opensearch-py, clickhouse-driver
- **Frontend:** SolidJS, shadcn/ui, TanStack Query, ApexCharts, WebSocket

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **PGSync 7.x limitations** | High | Build abstraction layer, consider forking |
| **ClickHouse ops complexity** | Medium | Provide Docker Compose default, cloud option |
| **WebSocket scale** | Medium | Redis pub/sub for multi-instance |
| **Schema generator edge cases** | High | Extensive testing, manual override option |
| **Breaking changes** | High | Versioned config, migration scripts |

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-06-19 | v0.5.0 | Initial release (PGSync CDC + Search API) |
| 2026-06-19 | Roadmap | Created product roadmap |

---

**Maintainer:** QTI Research
**Last Updated:** 2026-06-19
