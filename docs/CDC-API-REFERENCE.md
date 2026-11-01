# CDC API Reference

## Base URL
```
http://localhost:3505/api/cdc
```

---

## Endpoints

### 1. **POST /api/cdc/:config_id/start**

Start CDC sync untuk config tertentu (background thread).

**Request:**
```bash
curl -X POST http://localhost:3505/api/cdc/5/start
```

**Response (Instant, <100ms):**
```json
{
  "status": "started",
  "config_id": 5,
  "message": "Sync started in background. Poll /status for progress."
}
```

**Error Response:**
```json
{
  "error": "Configuration not found"
}
```

**Status Codes:**
- `200` — Sync started successfully
- `400` — Invalid config_id
- `404` — Configuration not found
- `409` — Sync already running for this config
- `500` — Internal error (password decrypt, DB connection, etc.)

---

### 2. **POST /api/cdc/:config_id/stop**

Stop CDC sync yang sedang running.

**Request:**
```bash
curl -X POST http://localhost:3505/api/cdc/5/stop
```

**Response:**
```json
{
  "status": "stopped",
  "config_id": 5
}
```

**Behavior:**
- Set `cdc_states.status = 'stopped'`
- Background thread tetap selesaikan batch terakhir
- Tidak force kill thread (graceful stop)

---

### 3. **GET /api/cdc/:config_id/status**

Get status CDC sync.

**Request:**
```bash
curl http://localhost:3505/api/cdc/5/status
```

**Response:**
```json
{
  "id": 1,
  "config_id": 5,
  "status": "running",
  "docs_synced": 2000,
  "throughput": 50.5,
  "lag_seconds": 0,
  "error_count": 0,
  "last_error": null,
  "last_sync_time": "2026-06-21T05:15:30",
  "created_at": "2026-06-21T05:12:00",
  "updated_at": "2026-06-21T05:15:30"
}
```

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `running`, `stopped`, `error` |
| `docs_synced` | int | Total rows synced (cumulative) |
| `throughput` | float | Docs per second (moving average) |
| `lag_seconds` | int | Seconds behind source (always 0 for on-demand) |
| `error_count` | int | Total errors encountered |
| `last_error` | string | Last error message (null if no error) |
| `last_sync_time` | datetime | Last checkpoint timestamp (WIB) |

**Status Values:**
- `running` — Sync in progress
- `stopped` — Idle (not syncing)
- `error` — Last sync failed

---

### 4. **GET /api/cdc/:config_id/logs**

Get execution logs untuk config tertentu.

**Request:**
```bash
curl http://localhost:3505/api/cdc/5/logs
```

**Response:**
```json
{
  "config_id": 5,
  "logs": [
    "[05:12:51.385] Schema mapping: PG table 'laporan' → OS index 'laporan2'",
    "[05:12:51.818] ✓ PG password decrypted",
    "[05:12:51.818] ✓ OpenSearch password decrypted",
    "[05:12:51.848] ✓ PostgreSQL connection OK",
    "[05:12:51.922] ✓ OpenSearch connection OK (localhost)",
    "[05:12:51.922] Tables to sync: laporan",
    "[05:12:51.922] Processing table: laporan",
    "[05:12:51.922]   Using schema-mapped index: laporan2",
    "[05:12:51.989]   Timestamp column: updated_date",
    "[05:12:51.989]   Querying rows since checkpoint: 2000-01-01 00:00:00",
    "[05:12:52.450]   Found 1000 rows",
    "[05:15:20.696]   ✂ Truncated field 'narasi' from 41670 bytes to 30000 bytes",
    "[05:15:26.536]   → Indexed 1000 rows to OpenSearch index 'laporan2'",
    "[05:15:26.540]   → Checkpoint updated: 2021-03-15 10:30:00"
  ]
}
```

**Log Format:**
```
[HH:MM:SS.mmm] <message>
```

**Log Symbols:**
- `✓` — Success
- `✗` — Error
- `⊘` — Warning/Skip
- `✂` — Truncation
- `→` — Action completed

**Logs Stored:**
- In-memory per config_id
- Max 500 lines per config
- Cleared on server restart
- Not persisted to disk

---

## Frontend Integration

### SolidJS API Client

```typescript
// src/lib/api-client.ts

class APIClient {
  async startCDC(config_id: number) {
    return this.client.post(`/cdc/${config_id}/start`, {});
  }

  async stopCDC(config_id: number) {
    return this.client.post(`/cdc/${config_id}/stop`, {});
  }

  async getCDCStatus(config_id: number) {
    return this.client.get(`/cdc/${config_id}/status`);
  }

  async getCDCLogs(config_id: number) {
    return this.client.get(`/cdc/${config_id}/logs`);
  }
}
```

### Polling Pattern

```typescript
const handleSyncNow = async (config_id: number) => {
  // 1. Start sync (instant return)
  const res = await apiClient.startCDC(config_id);

  // 2. Poll status every 2s
  const pollInterval = setInterval(async () => {
    const status = await apiClient.getCDCStatus(config_id);

    if (status.data.status === 'stopped' || status.data.status === 'error') {
      clearInterval(pollInterval);

      // 3. Fetch logs when done
      const logs = await apiClient.getCDCLogs(config_id);
      setCDCLogs(prev => ({ ...prev, [config_id]: logs.data.logs }));
    }
  }, 2000);

  // 4. Safety timeout (5 min max)
  setTimeout(() => clearInterval(pollInterval), 300000);
};
```

---

## Error Handling

### Backend Errors

```python
# cdc_service.py

try:
    os_client.index(index=index_name, id=str(doc_id), body=doc)
except Exception as e:
    self._log(config_id, f"✗ Error indexing doc {doc_id}: {e}")
    # Update error count
    cdc_state.error_count += 1
    cdc_state.last_error = str(e)
    cdc_state.last_error_time = datetime.now()
    session.commit()
```

### Frontend Error Display

```tsx
<Show when={state?.last_error}>
  <div class="bg-red-50 border border-red-200 rounded p-2 text-xs text-red-700">
    <strong>Error:</strong> {state.last_error}
  </div>
</Show>
```

---

## Performance Tuning

### Batch Size

Default: **1000 rows per batch**

**Increase for faster sync:**
```python
# cdc_service.py line ~260
cur.execute(f"""
    SELECT * FROM "{table}"
    WHERE "{ts_col}" > %s
    ORDER BY "{ts_col}" ASC
    LIMIT 5000  # ← Change here
""", (checkpoint,))
```

**Trade-offs:**
- Larger batch = faster sync, higher memory usage
- Smaller batch = slower sync, lower memory usage, better progress tracking

### Polling Interval

Default: **2 seconds**

**Frontend polling:**
```tsx
// src/pages/cdc.tsx
setInterval(async () => {
  await fetchStatus(config_id);
}, 2000);  // ← Change here (milliseconds)
```

**Trade-offs:**
- Faster polling = more responsive UI, higher backend load
- Slower polling = less responsive UI, lower backend load

### Connection Pooling

```python
# Not implemented — each sync creates new connection
# Future: use connection pool for high-frequency syncs

from psycopg_pool import ConnectionPool

pool = ConnectionPool(
    conninfo=pg_dsn,
    min_size=1,
    max_size=10
)
```

---

## Security

### Password Encryption

CDC uses Fernet encryption for database passwords:

```python
# CryptoService (backend/services/crypto_service.py)

class CryptoService:
    def encrypt(self, plaintext: str) -> str:
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self.cipher.decrypt(ciphertext.encode()).decode()
```

**Storage:**
- PostgreSQL password: `configurations.source_pg_password` (encrypted)
- OpenSearch password: `configurations.target_config.password` (encrypted)

**Decryption:**
- Happens at sync runtime only
- Never logged or exposed via API
- Masked in API responses as `***`

### API Authentication

**Current:** No authentication (local network only)

**Future:** Add JWT or API key auth:
```python
@app.before_request
def check_auth():
    token = request.headers.get("Authorization")
    if not verify_token(token):
        return Response({"error": "Unauthorized"}, status_code=401)
```

---

## Monitoring & Observability

### Health Check

```bash
# Backend health
curl http://localhost:3505/health

# CDC sync health
curl http://localhost:3505/api/cdc/5/status | jq '.status'
```

### Metrics Export (Future)

```python
# Prometheus metrics endpoint
from prometheus_client import Counter, Histogram

cdc_docs_synced = Counter('cdc_docs_synced_total', 'Total docs synced', ['config_id'])
cdc_sync_duration = Histogram('cdc_sync_duration_seconds', 'Sync duration', ['config_id'])

@app.get("/metrics")
def metrics():
    return generate_latest()
```

### Logging

**Backend logs:**
```bash
# Start with log level
LOG_LEVEL=DEBUG uv run python -m backend.main

# Tail logs
tail -f /tmp/cdc.log
```

**CDC-specific logs:**
```python
logger = logging.getLogger('cdc_service')
logger.setLevel(logging.INFO)
```

---

## Database Schema

### `cdc_states` Table

```sql
CREATE TABLE cdc_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'stopped',
    lag_seconds INTEGER DEFAULT 0,
    docs_synced INTEGER DEFAULT 0,
    throughput REAL DEFAULT 0.0,
    error_count INTEGER DEFAULT 0,
    last_sync_time TIMESTAMP,
    last_error TEXT,
    last_error_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (config_id) REFERENCES configurations(id) ON DELETE CASCADE
);

CREATE INDEX idx_cdc_config ON cdc_states(config_id);
CREATE INDEX idx_cdc_status ON cdc_states(status);
```

### Schema Relationships

```
configurations (1) ───┬──▶ (1) cdc_states
                      │
                      └──▶ (*) configurations_history
```

### Sample Data

```sql
-- Check CDC states
SELECT
    cs.config_id,
    c.name,
    cs.status,
    cs.docs_synced,
    cs.last_sync_time
FROM cdc_states cs
JOIN configurations c ON c.id = cs.config_id;
```

**Output:**
```
config_id | name    | status  | docs_synced | last_sync_time
----------|---------|---------|-------------|------------------
5         | example-project  | running | 2000        | 2026-06-21 05:15:30
```

---

## Testing

### Manual Testing

```bash
# 1. Start sync
curl -X POST http://localhost:3505/api/cdc/5/start

# 2. Poll status (repeat until stopped)
curl http://localhost:3505/api/cdc/5/status | jq '.status, .docs_synced'

# 3. Get logs
curl http://localhost:3505/api/cdc/5/logs | jq '.logs[-10:]'

# 4. Verify data in OpenSearch
curl -u "$OPENSEARCH_USER:$OPENSEARCH_PASSWORD" "$OPENSEARCH_SCHEME://$OPENSEARCH_HOST:$OPENSEARCH_PORT/laporan2/_count"
```

### Unit Tests (Future)

```python
# tests/test_cdc_service.py

def test_schema_mapping():
    service = CDCService()
    schema = {
        "index": "test_index",
        "nodes": {"table": "test_table"}
    }

    pg_table, os_index = service._parse_schema(schema)
    assert pg_table == "test_table"
    assert os_index == "test_index"

def test_truncate_large_field():
    doc = {"narasi": "x" * 50000}
    service = CDCService()
    truncated = service._truncate_doc(doc)

    assert len(truncated["narasi"].encode('utf-8')) <= 30000
```

---

## Future Enhancements

### 1. **Incremental Sync Scheduling**
- Cron-based auto-sync (every 5 min)
- UI: toggle "Auto Sync" switch

### 2. **Multi-Table Sync**
- Sync multiple tables in parallel
- Progress bar per table

### 3. **Conflict Resolution**
- Handle duplicate IDs
- Strategy: last-write-wins, merge, skip

### 4. **Data Transformation**
- Custom Python scripts per field
- Example: `upper(narasi)`, `hash(email)`

### 5. **Webhooks**
- POST notification on sync complete
- Payload: status, docs_synced, duration

### 6. **Metrics Dashboard**
- Historical sync trends (chart)
- Error rate over time
- Top slow tables

---

## Support

**Issues?** Check:
1. [Troubleshooting Guide](./CDC-README.md#troubleshooting)
2. Backend logs: `tail -f /tmp/cdc.log`
3. Database state: `sqlite3 pgsync_admin.db "SELECT * FROM cdc_states;"`

**Contact:**
- GitLab Issues: https://gitlab.com/QTI/QTI-Research/pgsync-production/-/issues
- Email: support@qti.co.id
