# Patch Heartbeat — PGSync Crash Loop Fix

**Date:** 2026-06-09
**Error:** `LogicalSlotParseError: No match for row: message: transactional: 1 prefix: heartbeat ...`

---

## ROOT CAUSE

test_decoding plugin emit **logical messages** via `pg_logical_emit_message()`:
```
message: transactional: 1 prefix: heartbeat content: 2026-06-08 21:37:30.187581+00
```

PGSync parser regex `LOGICAL_SLOT_PREFIX` hanya handle:
```
table schema.table: INSERT/UPDATE/DELETE: ...
```

Keduanya format **tidak match** -> LogicalSlotParseError -> crash.

## FIX

Patch `sync.py:consume()` untuk skip messages starting with "message:" sebelum mencapai parser.

## FILES

| File | Action |
|------|--------|
| `scripts/patch-pgsync-baked.py` | ✅ Added Step 3: heartbeat filter |
| `scripts/patch-pgsync-heartbeat.py` | ✅ Standalone patch script (opsional) |

## EXECUTION

```bash
cd ~/pgsync-production

# Pull latest
git pull origin main

# Rebuild images
docker compose down
docker build --no-cache -f Dockerfile.base -t pgsync-laporan:base .
docker build --no-cache -t pgsync-laporan:app .

# Verify patch
docker run --rm pgsync-laporan:base python3 -c "
import pgsync.sync
src = open(pgsync.sync.__file__).read()
assert 'Skipping logical message' in src, 'Patch missing!'
print('[OK] Heartbeat patch applied')
"

# Start CDC
docker compose up -d laporan-cdc

# Monitor
docker logs pgsync-laporan-cdc -f
```

## EXPECTED OUTPUT

```
Starting logical replication stream (test_decoding)...
Skipping logical message: message: transactional: 1 prefix: heartbeat ...
```

**NO ERROR** — heartbeat messages silently skipped.
