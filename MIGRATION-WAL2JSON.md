# Migrasi PGSync: pgoutput → wal2json

**Tanggal:** 2026-06-08
**Target:** PostgreSQL 15.14 @ localhost:5432/example_db
**PGSync:** 7.0.5
**Status:** READY FOR EXECUTION

---

## 1. ROOT CAUSE

### Error yang terjadi:
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xf0
```

### Analisis:
1. PGSync 7.0.5 dibuat untuk **text-based logical decoding output** (test_decoding, wal2json)
2. Plugin `pgoutput` menghasilkan **binary protocol output** — tidak kompatibel dengan parser PGSync
3. Parser `consume()` dan `parse_logical_slot()` di `sync.py` expect string format `"table: col: val"` dan `"BEGIN/COMMIT N"`
4. Binary pgoutput protocol tidak bisa di-decode sebagai UTF-8 text → crash

### Timeline masalah:
- Awal: PGSync pakai `test_decoding` (text output) → berjalan OK
- Upgrade: Patch ke `pgoutput` untuk compatibility PG15 → **UnicodeDecodeError**
- Root cause: pgoutput binary protocol vs text parser

---

## 2. SOLUTION: MIGRASI KE WAL2JSON

### Kenapa wal2json?
1. **Text-based JSON output** — kompatibel dengan parser PGSync yang expect string
2. **Format konsisten** — self-describing JSON, tidak butuh options tambahan
3. **Mature & stable** — production-ready, widely used untuk CDC pipelines
4. **PostgreSQL 15 support** — tersedia sebagai extension official

### Arsitektur baru:
```
PostgreSQL 15.14 (wal2json plugin)
  ↓ logical replication slot
PGSync 7.0.5 (text parser)
  ↓ bulk index
OpenSearch (index: laporan)
```

---

## 3. FILES YANG DIUBAH

### 3.1 `scripts/patch-pgsync-plugin.sh`
**Before:**
```bash
# Patch untuk pgoutput
sed -i 's/PLUGIN = "test_decoding"/PLUGIN = "pgoutput"/' constants.py
# Tambah options pgoutput-specific
```

**After:**
```bash
# Patch untuk wal2json
sed -i 's/PLUGIN = "test_decoding"/PLUGIN = "wal2json"/' constants.py
sed -i 's/PLUGIN = "pgoutput"/PLUGIN = "wal2json"/' constants.py
# Hapus semua options dict — wal2json tidak butuh
sed -i '/options={/,/}/d' sync.py
```

**Reason:** wal2json tidak butuh options apapun, output JSON sudah self-contained.

### 3.2 Runtime patch target: `constants.py`
**Location (di container):** `/usr/local/lib/python3.12/site-packages/pgsync/constants.py`

**Change:**
```python
# Before
PLUGIN = "test_decoding"  # atau "pgoutput"

# After
PLUGIN = "wal2json"
```

### 3.3 Runtime patch target: `sync.py`
**Location (di container):** `/usr/local/lib/python3.12/site-packages/pgsync/sync.py`

**Change (line ~1990):**
```python
# Before
cursor.start_replication(
    slot_name=self.__name,
    options={"include-xids": "1", "skip-empty-xacts": "1"},  # ← test_decoding only
    decode=True,
)

# After
cursor.start_replication(
    slot_name=self.__name,
    decode=True,
)
```

**Reason:**
- `include-xids` & `skip-empty-xacts` hanya valid untuk test_decoding
- wal2json output JSON dengan XID embedded, tidak perlu parameter
- Biarkan `decode=True` — wal2json output text JSON, bukan binary

---

## 4. POSTGRESQL CHANGES

### 4.1 Install wal2json extension (jika belum ada)

**Debian/Ubuntu:**
```bash
sudo apt-get update
sudo apt-get install postgresql-15-wal2json
sudo systemctl restart postgresql
```

**RHEL/CentOS:**
```bash
sudo yum install wal2json15
sudo systemctl restart postgresql
```

**Verifikasi:**
```sql
SELECT name, default_version, installed_version
FROM pg_available_extensions
WHERE name = 'wal2json';
```

Expected output:
```
   name    | default_version | installed_version
-----------+-----------------+-------------------
 wal2json  | 2.5             | 2.5
```

### 4.2 Drop replication slot lama (pgoutput)

```sql
-- Cek slot saat ini
SELECT slot_name, plugin, slot_type, active
FROM pg_replication_slots;

-- Drop slot lama
SELECT pg_drop_replication_slot('pgsync_laporan');
```

### 4.3 Create replication slot dengan wal2json

```sql
SELECT *
FROM pg_create_logical_replication_slot(
    'pgsync_laporan',
    'wal2json'
);
```

Expected output:
```
     slot_name       |    lsn
---------------------+-----------
 pgsync_laporan | 0/XXXXXX
```

### 4.4 Drop publication (opsional — tidak dipakai wal2json)

```sql
-- Publication hanya untuk pgoutput
DROP PUBLICATION IF EXISTS pgsync_laporan;
```

**Note:** wal2json tidak butuh publication — langsung decode dari WAL.

---

## 5. EXECUTION STEPS

### 5.1 Manual execution
```bash
cd /Volumes/Sinise/work/qti/pgsync-production

# 1. Audit PostgreSQL
source .env
docker run --rm --network host postgres:16 psql \
  "host=localhost dbname=example_db user=postgres password=$PG_PASSWORD" \
  -c "SELECT name FROM pg_available_extensions WHERE name='wal2json';"

# 2. Drop slot lama
docker run --rm --network host postgres:16 psql \
  "host=localhost dbname=example_db user=postgres password=$PG_PASSWORD" \
  -c "SELECT pg_drop_replication_slot('pgsync_laporan');"

# 3. Create slot baru
docker run --rm --network host postgres:16 psql \
  "host=localhost dbname=example_db user=postgres password=$PG_PASSWORD" \
  -c "SELECT * FROM pg_create_logical_replication_slot('pgsync_laporan','wal2json');"

# 4. Rebuild image
docker compose down
docker build --no-cache -f Dockerfile.base -t pgsync-laporan:base .
docker build --no-cache -t pgsync-laporan:app .

# 5. Start CDC
docker compose up -d laporan-cdc

# 6. Monitor
docker logs pgsync-laporan-cdc -f
```

### 5.2 Automated execution
```bash
bash migration-to-wal2json.sh
```

---

## 6. VALIDATION

### 6.1 Container health
```bash
docker ps --filter name=pgsync-laporan-cdc
docker logs pgsync-laporan-cdc --tail 100
```

**Expected log:**
```
[OK] constants.py: PLUGIN -> wal2json
[OK] sync.py: removed plugin-specific options
[OK] sync.py: updated log message
Starting logical replication stream (wal2json)...
```

**NO ERROR:**
- ❌ `UnicodeDecodeError`
- ❌ `unrecognized pgoutput option`
- ❌ `replication slot does not exist`

### 6.2 Replication slot active
```bash
docker run --rm --network host postgres:16 psql \
  "host=localhost dbname=example_db user=postgres password=$PG_PASSWORD" \
  -c "SELECT slot_name, plugin, active, restart_lsn
      FROM pg_replication_slots
      WHERE slot_name='pgsync_laporan';"
```

**Expected:**
```
     slot_name       |  plugin  | active | restart_lsn
---------------------+----------+--------+-------------
 pgsync_laporan | wal2json | t      | 0/XXXXXX
```

### 6.3 End-to-end CDC test

**Insert:**
```sql
INSERT INTO laporan (nomor, judul, narasi, tanggal_laporan)
VALUES ('TEST-001', 'Test CDC', 'Validasi wal2json', NOW());
```

**Update:**
```sql
UPDATE laporan SET narasi = 'CDC working' WHERE nomor = 'TEST-001';
```

**Delete:**
```sql
DELETE FROM laporan WHERE nomor = 'TEST-001';
```

**Check OpenSearch:**
```bash
curl -u admin:*** -k \
  https://localhost:9200/laporan/_search?q=nomor:TEST-001
```

Expected: record ada (untuk INSERT/UPDATE), hilang (untuk DELETE).

---

## 7. ROLLBACK PROCEDURE

### 7.1 Jika migrasi gagal sebelum drop slot

```bash
# Stop container
docker compose stop laporan-cdc

# Restore patch script via git
git checkout HEAD -- scripts/patch-pgsync-plugin.sh

# Rebuild
docker build --no-cache -t pgsync-laporan:app .
docker compose up -d laporan-cdc
```

Slot tetap pgoutput — rollback tanpa data loss.

### 7.2 Jika migrasi gagal setelah drop slot

```bash
# Stop container
docker compose stop laporan-cdc

# Recreate slot dengan plugin lama
docker run --rm --network host postgres:16 psql \
  "host=localhost dbname=example_db user=postgres password=$PG_PASSWORD" \
  -c "SELECT * FROM pg_create_logical_replication_slot('pgsync_laporan','pgoutput');"

# Restore patch script
git checkout HEAD~1 -- scripts/patch-pgsync-plugin.sh

# Rebuild
docker build --no-cache -t pgsync-laporan:app .

# Bootstrap ulang (data loss — resync from PG)
docker compose --profile bootstrap run laporan-bootstrap

# Start CDC
docker compose up -d laporan-cdc
```

**WARNING:** Bootstrap ulang = full resync historical data, bisa lama untuk tabel besar.

### 7.3 Emergency rollback (pakai test_decoding)

```bash
# Drop slot apapun yang ada
docker run --rm --network host postgres:16 psql \
  "host=localhost dbname=example_db user=postgres password=$PG_PASSWORD" \
  -c "SELECT pg_drop_replication_slot(slot_name)
      FROM pg_replication_slots
      WHERE slot_name='pgsync_laporan';"

# Create slot dengan test_decoding
docker run --rm --network host postgres:16 psql \
  "host=localhost dbname=example_db user=postgres password=$PG_PASSWORD" \
  -c "SELECT * FROM pg_create_logical_replication_slot('pgsync_laporan','test_decoding');"

# Restore original PGSync (no patch)
git checkout HEAD~2 -- scripts/patch-pgsync-plugin.sh

# Rebuild & bootstrap
docker build --no-cache -t pgsync-laporan:app .
docker compose --profile bootstrap run laporan-bootstrap
docker compose up -d laporan-cdc
```

---

## 8. RISK ANALYSIS

| Risk | Severity | Likelihood | Mitigation |
|------|----------|-----------|------------|
| wal2json belum installed di PG server | HIGH | Medium | Pre-check dengan `pg_available_extensions` sebelum drop slot |
| Data loss during migration | MEDIUM | Low | WAL tetap di PG, CDC resumable via LSN checkpoint |
| wal2json format berbeda dari test_decoding | MEDIUM | Low | Parser PGSync dibuat untuk text format — wal2json JSON bisa di-parse as string |
| Slot corrupt / tidak bisa dibuat | LOW | Low | Drop via `pg_drop_replication_slot` dan recreate |
| OpenSearch index mapping mismatch | LOW | Very Low | Schema tetap sama, hanya transport layer berubah |

---

## 9. MONITORING POST-MIGRATION

### 9.1 Metrics to watch (first 24h)
- Container restart count: `docker inspect pgsync-laporan-cdc --format '{{.RestartCount}}'`
- Log errors: `docker logs pgsync-laporan-cdc | grep -i error`
- Replication lag: cek `restart_lsn` vs `confirmed_flush_lsn` di `pg_replication_slots`
- OpenSearch index size: `GET /laporan/_stats`

### 9.2 Health indicators
✅ **HEALTHY:**
- Container `Up` tanpa restart
- Log: `Starting logical replication stream (wal2json)...`
- Slot `active=true`
- Insert/Update/Delete masuk OpenSearch dalam < 5 detik

❌ **UNHEALTHY:**
- Container crash loop
- Log: `UnicodeDecodeError`, `RuntimeError`, `replication slot does not exist`
- Slot `active=false` > 5 menit
- Data tidak masuk OpenSearch

---

## 10. REFERENCES

- **wal2json GitHub:** https://github.com/eulerto/wal2json
- **PGSync docs:** https://pgsync.com
- **PostgreSQL logical decoding:** https://www.postgresql.org/docs/15/logicaldecoding.html
- **Internal docs:** `docs/01-arsitektur.md`, `docs/03-operasi.md`

---

## 11. CHANGELOG

| Date | Change | Author |
|------|--------|--------|
| 2026-06-08 | Initial migration: pgoutput → wal2json | Kiro (AI Agent) |
| 2026-06-08 | Updated `patch-pgsync-plugin.sh` untuk wal2json | Kiro |
| 2026-06-08 | Created `migration-to-wal2json.sh` automation script | Kiro |

---

**NEXT STEPS:**
1. Jalankan `migration-to-wal2json.sh` di server yang ada Docker
2. Monitor log selama 1 jam pertama
3. Validasi end-to-end CDC test
4. Update README & docs jika migrasi sukses
