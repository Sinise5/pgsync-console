# Heartbeat Message Analysis — PGSync Crash Loop

**Date:** 2026-06-09
**Status:** ROOT CAUSE IDENTIFIED
**Plugin:** test_decoding
**Error:** `LogicalSlotParseError: No match for row: message: transactional: 1 prefix: heartbeat ...`

---

## 1. ROOT CAUSE

### Error Message
```
LogicalSlotParseError: 'No match for row: message: transactional: 1 prefix: heartbeat content: 2026-06-08 21:37:30.187581+00'
```

### PGSync Parser Expectation
**File:** `pgsync/constants.py:208`

```python
LOGICAL_SLOT_PREFIX = re.compile(
    r"^table\s+"
    r'"?(?P<schema>[^"]+?)"?\.'
    r'"?(?P<table>[^"]+?)"?'
    r"\s*:\s*(?P<tg_op>[A-Z]+):"
)
```

**Expected format:**
```
table public.laporan: INSERT: id[integer]:12345 title[text]:'Test'
table public.laporan: UPDATE: old-key: id[integer]:12345 new-tuple: title[text]:'Updated'
table public.laporan: DELETE: id[integer]:12345
```

### Actual Heartbeat Format
```
message: transactional: 1 prefix: heartbeat content: 2026-06-08 21:37:30.187581+00
```

**Mismatch:** `message:` ≠ `table ...:`

---

## 2. SOURCE OF HEARTBEAT

### PostgreSQL Logical Messages
test_decoding plugin dapat output **2 tipe pesan:**

1. **DML changes** (INSERT/UPDATE/DELETE)
   ```
   table schema.table: OPERATION: col[type]:val ...
   ```

2. **Logical messages** (via `pg_logical_emit_message()`)
   ```
   message: transactional: 0/1 prefix: <prefix> content: <data>
   ```

### Kemungkinan Source Heartbeat

#### A. PostgreSQL Extension (HIGH PROBABILITY)
Extensions yang dapat emit heartbeat:

1. **pglogical** — logical replication framework
   - Emits heartbeat via `pg_logical_emit_message('heartbeat', ...)`
   - Interval: default 30 detik

2. **Citus** — distributed PostgreSQL
   - Background worker emits heartbeat untuk coordination

3. **TimescaleDB** — time-series database
   - Continuous aggregates emit heartbeat messages

4. **pg_cron** — job scheduler
   - Dapat schedule heartbeat emission

#### B. Custom Application (MEDIUM PROBABILITY)
- Trigger atau function yang call `pg_logical_emit_message()`
- Background worker yang emit keepalive

#### C. Replication Tool (LOW PROBABILITY)
- Debezium, Materialize, atau tool lain yang consume slot
- Tapi log tidak menunjukkan multiple consumers

---

## 3. VERIFICATION QUERIES

### Query 1: Cek installed extensions
```sql
SELECT
    extname,
    extversion
FROM pg_extension
WHERE extname IN ('pglogical', 'citus', 'timescaledb', 'pg_cron', 'pg_partman');
```

### Query 2: Cari function yang emit heartbeat
```sql
SELECT
    n.nspname,
    p.proname,
    pg_get_functiondef(p.oid) as definition
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE pg_get_functiondef(p.oid) ILIKE '%pg_logical_emit_message%'
   OR pg_get_functiondef(p.oid) ILIKE '%heartbeat%'
LIMIT 10;
```

### Query 3: Cek pg_cron jobs
```sql
-- Jika pg_cron installed
SELECT
    jobid,
    schedule,
    command,
    nodename,
    active
FROM cron.job
WHERE command ILIKE '%heartbeat%'
   OR command ILIKE '%emit_message%';
```

### Query 4: Peek WAL untuk lihat pattern
```sql
SELECT
    lsn,
    xid,
    data
FROM pg_logical_slot_peek_changes('pgsync_laporan', NULL, NULL)
LIMIT 50;
```

---

## 4. SOLUTIONS

### Solution A: Filter Heartbeat di PGSync (RECOMMENDED)

**Patch `sync.py:consume()` untuk skip logical messages:**

```python
def consume(self, message: t.Any) -> None:
    raw: str = message.payload.decode("utf-8")

    # PATCH: Skip logical messages (heartbeat, etc)
    if raw.startswith("message:"):
        logger.debug(f"Skipping logical message: {raw[:100]}")
        message.cursor.send_feedback(flush_lsn=message.data_start)
        return

    match = TX_BOUNDARY_RE.match(raw)
    # ... rest of consume logic
```

**File:** `scripts/patch-pgsync-heartbeat.py`

---

## 5. NEXT STEPS

1. **Jalankan verification queries** di PostgreSQL server
2. **Identifikasi extension** yang emit heartbeat
3. **Apply patch** untuk skip logical messages
4. **Test** dengan INSERT/UPDATE/DELETE real data

---

## 6. REFERENCES

- PostgreSQL Logical Decoding: https://www.postgresql.org/docs/15/logicaldecoding-output-plugin.html
- pg_logical_emit_message: https://www.postgresql.org/docs/15/functions-admin.html#FUNCTIONS-REPLICATION
- PGSync issue tracker: https://github.com/toluaina/pgsync/issues
