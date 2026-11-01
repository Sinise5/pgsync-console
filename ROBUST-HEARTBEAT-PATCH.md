# Robust Heartbeat Patch — PGSync 7.0.5

**Date:** 2026-06-09
**Status:** Production-ready robust implementation
**Strategy:** Whitelist approach with regex pattern matching

---

## PROBLEM STATEMENT

### Error
```
pgsync.exc.LogicalSlotParseError:
No match for row: message: transactional: 1 prefix: heartbeat, sz: 29 content:2026-06-09 02:47:54.366791+00
```

### Root Cause

test_decoding plugin emits **3 types** of WAL records:

1. **Transaction boundaries** (handled)
   ```
   BEGIN 111357
   COMMIT 111357
   ```

2. **DML changes** (handled)
   ```
   table public.laporan: INSERT: id[integer]:123 title[text]:'Test'
   table public.laporan: UPDATE: old-key: id[integer]:123 new-tuple: title[text]:'Updated'
   table public.laporan: DELETE: id[integer]:123
   ```

3. **Logical messages** (NOT handled → crash)
   ```
   message: transactional: 1 prefix: heartbeat, sz: 29 content:2026-06-09 02:47:54.366791+00
   ```

**PGSync parser (`LOGICAL_SLOT_PREFIX` regex) only expects format #1 and #2.**

Format #3 → `No match for row` → LogicalSlotParseError → crash loop.

---

## SOLUTION DESIGN

### Whitelist Approach

**Before patch:** Parse everything → crash on unknown format

**After patch:** Explicit handling via ordered checks

```
WAL record received
    ↓
1. Is it BEGIN/COMMIT? → Handle as transaction boundary
    ↓ NO
2. Is it logical message? → Skip + acknowledge LSN
    ↓ NO
3. Must be DML → Parse as INSERT/UPDATE/DELETE
```

### Implementation

**File:** `scripts/patch-pgsync-robust.py`

**Changes:**

1. Add regex pattern for logical messages
   ```python
   LOGICAL_MESSAGE_RE = re.compile(r"^message:\s+", re.IGNORECASE)
   ```

2. Insert check in `consume()` method
   ```python
   if LOGICAL_MESSAGE_RE.match(raw):
       logger.debug(f"Skipping logical message: {raw[:100]}")
       if lsn is not None:
           message.cursor.send_feedback(flush_lsn=lsn, force=False)
       return
   ```

**Placement:** Between TX_BOUNDARY_RE check and parse_logical_slot() call

---

## WHY THIS IS SAFE

### 1. Regex Pattern Matching
- Not fragile string replacement
- Works across PGSync versions (as long as consume() structure is stable)
- Pattern `^message:\s+` is unambiguous

### 2. LSN Acknowledgment
- Calls `send_feedback(flush_lsn=lsn)` before return
- PostgreSQL advances replication slot
- No replication lag accumulation

### 3. Whitelist Logic
- Explicit handling: BEGIN/COMMIT → transaction boundary
- Explicit handling: message: → skip
- Everything else → falls through to DML parser
- Unknown formats caught by existing error handling

### 4. PostgreSQL 15 Compatibility
- test_decoding format is stable since PG 9.4
- Logical messages documented: https://www.postgresql.org/docs/15/logicaldecoding-output-plugin.html
- Pattern `message: transactional: N prefix: X content: Y` is standard

### 5. No Data Loss
- DML changes (INSERT/UPDATE/DELETE) still parsed normally
- Only non-DML messages skipped (heartbeat, keepalive)
- CDC pipeline unchanged for actual data

---

## FILES CHANGED

| File | Action | Lines Changed |
|------|--------|---------------|
| `scripts/patch-pgsync-robust.py` | ✅ Created | New robust patch implementation |
| `Dockerfile.base` | ✅ Updated | Use robust patch instead of baked.py |

---

## EXECUTION

```bash
cd ~/pgsync-production

# Pull latest
git pull origin main

# Rebuild base image
docker compose down
docker build --no-cache -f Dockerfile.base -t pgsync-laporan:base .
```

**Expected output:**
```
============================================================
PGSync 7.0.5 Heartbeat Patch — Robust Implementation
============================================================
[OK] Step 1: Added LOGICAL_MESSAGE_RE pattern
[OK] Step 2: Added logical message check in consume()
[OK] sync.py patched successfully

============================================================
VERIFICATION
============================================================
[✓] Logical message regex pattern
[✓] Logical message skip logic
[✓] LSN acknowledgment
============================================================
[SUCCESS] All patches applied and verified
```

```bash
# Build app image
docker build --no-cache -t pgsync-laporan:app .

# Start CDC
docker compose up -d laporan-cdc

# Monitor
docker logs pgsync-laporan-cdc -f
```

---

## EXPECTED BEHAVIOR

### Before Patch
```
Starting logical replication stream (test_decoding)...
Error parsing row: message: transactional: 1 prefix: heartbeat ...
LogicalSlotParseError: No match for row: message: ...
Container exits (code 1)
Container restarts
[infinite crash loop]
```

### After Patch
```
Starting logical replication stream (test_decoding)...
Skipping logical message: message: transactional: 1 prefix: heartbeat, sz: 29 content:2026-06-09 ...
[no error, continues processing]
```

---

## VERIFICATION CHECKLIST

```bash
# 1. Patch applied
docker exec pgsync-laporan-cdc grep -A 3 'LOGICAL_MESSAGE_RE' \
  /usr/local/lib/python3.12/site-packages/pgsync/sync.py

# Expected: LOGICAL_MESSAGE_RE = re.compile(...)

# 2. No crash loop
docker inspect pgsync-laporan-cdc --format '{{.RestartCount}}'
# Expected: 0

# 3. Container healthy
docker ps --filter name=pgsync-laporan-cdc --format '{{.Status}}'
# Expected: Up X minutes

# 4. CDC processing
docker logs pgsync-laporan-cdc --tail 50 | grep -E 'Skipping logical|INSERT|UPDATE|DELETE'
# Expected: mix of DML operations, occasional "Skipping logical message"
```

---

## ROLLBACK PROCEDURE

```bash
# If patch causes issues

# 1. Restore old Dockerfile.base
git show HEAD~1:Dockerfile.base > Dockerfile.base

# 2. Rebuild
docker build --no-cache -f Dockerfile.base -t pgsync-laporan:base .
docker build --no-cache -t pgsync-laporan:app .
docker compose up -d laporan-cdc
```

---

## COMPARISON: OLD vs NEW PATCH

| Aspect | patch-pgsync-baked.py | patch-pgsync-robust.py |
|--------|----------------------|------------------------|
| **Strategy** | String replacement | Regex pattern + whitelist |
| **Robustness** | Fragile (exact match needed) | Robust (pattern-based) |
| **Verification** | Manual | Automated checks |
| **Error handling** | Silent fail | Explicit verification |
| **Maintainability** | Hard to debug | Self-documenting |

---

## TECHNICAL DETAILS

### Logical Messages in test_decoding

**Source:** Extensions call `pg_logical_emit_message()`

**Common sources:**
- pglogical: heartbeat every 30s
- Citus: distributed coordination
- TimescaleDB: continuous aggregate signals
- pg_partman: partition maintenance
- Custom functions/triggers

**Format (from PostgreSQL docs):**
```
message: transactional: <0|1> prefix: <string> [ , sz: <bytes> ] content: <data>
```

### Why PGSync Doesn't Handle These

**PGSync design:**
- Built for DML replication (INSERT/UPDATE/DELETE)
- Parser expects table-oriented format
- Logical messages = metadata, not data changes
- Skipping them is the correct behavior

### Performance Impact

**Negligible:**
- Regex check: ~1μs per message
- Heartbeat frequency: typically 30-60s
- DML throughput: unchanged
- Replication lag: none (LSN acknowledged)

---

## TESTING RECOMMENDATIONS

### 1. Functional Test
```sql
-- In PostgreSQL
BEGIN;
INSERT INTO laporan (title) VALUES ('Test CDC');
COMMIT;
```

Verify in OpenSearch:
```bash
curl -u "$OPENSEARCH_USER:$OPENSEARCH_PASSWORD" "$OPENSEARCH_SCHEME://$OPENSEARCH_HOST:$OPENSEARCH_PORT/laporan/_search?q=title:Test%20CDC"
```

### 2. Heartbeat Test
Wait 1-2 minutes, check logs:
```bash
docker logs pgsync-laporan-cdc --since 2m | grep -i "skipping"
```

Expected: 1-2 "Skipping logical message" entries

### 3. Load Test
```bash
# Generate 1000 INSERTs
for i in {1..1000}; do
  psql -h localhost -U postgres -d example_db \
    -c "INSERT INTO laporan (title) VALUES ('Load test $i');"
done
```

Verify:
- No crashes
- All 1000 docs in OpenSearch
- RestartCount = 0

---

## REFERENCES

- PostgreSQL Logical Decoding: https://www.postgresql.org/docs/15/logicaldecoding.html
- test_decoding output format: https://www.postgresql.org/docs/15/test-decoding.html
- pg_logical_emit_message: https://www.postgresql.org/docs/15/functions-admin.html#FUNCTIONS-REPLICATION
- PGSync GitHub: https://github.com/toluaina/pgsync
