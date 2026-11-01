# PGSync Admin - CDC (Change Data Capture) Dashboard

## 📋 Daftar Isi

- [Overview](#overview)
- [Fitur Utama](#fitur-utama)
- [Arsitektur](#arsitektur)
- [Cara Penggunaan](#cara-penggunaan)
- [Troubleshooting](#troubleshooting)

---

## Overview

**CDC Dashboard** adalah fitur Change Data Capture untuk sinkronisasi real-time data dari PostgreSQL ke OpenSearch. Dibangun dengan:

- **Backend:** Python (Robyn + SQLAlchemy + psycopg + opensearchpy)
- **Frontend:** SolidJS + TypeScript
- **Database:** SQLite (metadata CDC state)

### Apa itu CDC?

CDC (Change Data Capture) mendeteksi perubahan data di PostgreSQL berdasarkan timestamp column (`updated_date`, `created_date`, dll) dan otomatis mensinkronkan ke OpenSearch index.

### Kapan Digunakan?

- ✅ Sinkronisasi data PostgreSQL → OpenSearch untuk full-text search
- ✅ Monitoring perubahan data real-time
- ✅ ETL pipeline dengan low-latency
- ✅ Data warehouse integration

---

## Fitur Utama

### 1. **On-Demand Sync**
- Trigger manual via UI (button "Sync Now")
- Background threading — no timeout 30s
- Auto-polling status tiap 2 detik
- Return instant response (<100ms)

### 2. **Schema Mapping**
- Map PostgreSQL table → OpenSearch index via `schema_config`
- Contoh: `laporan` (PG table) → `laporan2` (OS index)
- Auto-detect timestamp columns (`updated_date`, `created_date`)

### 3. **Auto-Truncate Large Fields**
- Deteksi field text >30KB
- Otomatis potong ke 30KB (OpenSearch limit: 32766 bytes)
- Log truncation untuk monitoring

### 4. **Real-Time Logs**
- Terminal-style log display (bg-gray-900, text-green-400)
- Streaming logs via API: `GET /api/cdc/:config_id/logs`
- Toggle View/Hide Logs button

### 5. **CDC Pipeline Details**
- Display source PostgreSQL (host, port, database)
- Display target OpenSearch (host, port, index)
- Visual connection arrow (source → target)

### 6. **Monitoring Metrics**
- Status: running / stopped / error
- Docs synced: total rows
- Throughput: docs/sec
- Lag: seconds behind source
- Error count + last error message
- Last sync time (WIB timezone)

---

## Arsitektur

### Backend Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     CDC Service                          │
│  (backend/services/cdc_service.py)                      │
└─────────────────────────────────────────────────────────┘
                          │
      ┌───────────────────┼───────────────────┐
      ▼                   ▼                   ▼
┌──────────┐      ┌──────────────┐    ┌─────────────┐
│ PostgreSQL│      │ OpenSearch   │    │  SQLite     │
│  Source   │      │   Target     │    │  (State)    │
└──────────┘      └──────────────┘    └─────────────┘
```

### Threading Model

```
HTTP Request (POST /api/cdc/5/start)
    │
    ▼
┌─────────────────────────────────┐
│  start_sync()                   │  ← Return instant response
│  - Create background thread     │     (status: "started")
│  - Set status = RUNNING         │
│  - Return immediately           │
└─────────────────────────────────┘
                │
                ▼
        ┌────────────────────┐
        │  Background Thread │
        │  _run_sync_thread()│
        └────────────────────┘
                │
                ▼
        ┌────────────────────┐
        │  _poll_and_sync()  │  ← Sync 1000 rows/batch
        │  - Query PG        │
        │  - Index to OS     │
        │  - Update checkpoint│
        │  - Log progress    │
        └────────────────────┘
```

### Schema Mapping Flow

```
Configuration.schema_config (JSON):
{
  "database": "example_db",
  "index": "laporan2",           ← OpenSearch index name
  "nodes": {
    "table": "laporan",          ← PostgreSQL table name
    "schema": "public",
    "columns": ["id", "narasi", ...]
  }
}

CDC Service:
1. Load schema_config from DB
2. Extract: pg_table = "laporan", os_index = "laporan2"
3. Query PG: SELECT * FROM "laporan" WHERE updated_date > checkpoint
4. Index to OS: os_client.index(index="laporan2", body=doc)
```

### Data Flow

```
1. User clicks "Sync Now"
   ↓
2. POST /api/cdc/5/start
   ↓
3. Backend: start_sync() → background thread
   ↓
4. Thread: _poll_and_sync()
   ↓
5. Query PG: SELECT * FROM laporan WHERE updated_date > '2000-01-01'
   ↓
6. Process 1000 rows/batch:
   - Convert Decimal → float
   - Truncate text >30KB
   - Log each step
   ↓
7. Index to OpenSearch: laporan2 (index name dari schema)
   ↓
8. Update checkpoint: last_sync_time = latest row timestamp
   ↓
9. Frontend polls /api/cdc/5/status every 2s
   ↓
10. Display: docs_synced, throughput, logs
```

---

## Cara Penggunaan

### Setup (Backend + Frontend)

1. **Install Dependencies**
   ```bash
   cd pgsync-admin/backend
   uv sync

   cd ../frontend
   npm install
   ```

2. **Konfigurasi Database**
   - Backend otomatis create SQLite DB: `pgsync_admin.db`
   - Tables: `configurations`, `cdc_states`

3. **Start Backend**
   ```bash
   cd pgsync-admin/backend
   uv run python -m backend.main
   # Listening on http://localhost:3505
   ```

4. **Start Frontend**
   ```bash
   cd pgsync-admin/frontend
   npm run dev -- --port 3506
   # Open http://localhost:3506
   ```

### Membuat CDC Config

1. **Buka Schema Builder**
   - Navigate: http://localhost:3506/schema-builder
   - Pilih PostgreSQL source + OpenSearch target
   - Drag table dari PG → mapping → generate schema
   - **PENTING:** Set **Index Name** di schema (misal: `laporan2`)
   - Save configuration

2. **Verifikasi Config**
   - Navigate: http://localhost:3506/
   - Lihat config list
   - Pastikan `schema.index` terisi (bukan null)

### Menjalankan CDC Sync

1. **Navigate ke CDC Dashboard**
   ```
   http://localhost:3506/cdc
   ```

2. **Lihat Config List**
   - Semua config dengan schema valid muncul di list
   - Info: name, source PG, target OS

3. **Klik "Sync Now"**
   - Button berubah jadi "Syncing..." (disabled)
   - Backend mulai sync di background thread
   - Frontend auto-poll status tiap 2s

4. **Monitor Progress**
   - **CDC Pipeline box (biru):**
     - Source: PostgreSQL localhost:5432 → DB: example_db
     - Target: OpenSearch localhost:9200 → Index: laporan2

   - **Monitoring cards:**
     - Status: running
     - Docs Synced: 1000 (increment tiap batch)
     - Throughput: 50 docs/sec
     - Lag: 0s
     - Errors: 0

5. **View Logs** (opsional)
   - Klik button **"View Logs"** (abu-abu, sebelah kanan "Stop")
   - Terminal-style logs muncul
   - Scroll untuk lihat detail:
     ```
     [05:12:51] Schema mapping: PG table 'laporan' → OS index 'laporan2'
     [05:12:51]   Using schema-mapped index: laporan2
     [05:12:51]   Timestamp column: updated_date
     [05:12:51]   Found 1000 rows
     [05:12:52]   ✂ Truncated field 'narasi' from 44201 bytes to 30000 bytes
     [05:12:53]   → Indexed 1000 rows to OpenSearch index 'laporan2'
     ```

6. **Stop Sync** (jika perlu)
   - Klik button **"Stop"** (merah)
   - Status berubah jadi "stopped"
   - Button kembali jadi "Sync Now"

### Verifikasi Data di OpenSearch

```bash
# Check index exists
curl -u "$OPENSEARCH_USER:$OPENSEARCH_PASSWORD" "$OPENSEARCH_SCHEME://$OPENSEARCH_HOST:$OPENSEARCH_PORT/_cat/indices/laporan2?v"

# Count docs
curl -u "$OPENSEARCH_USER:$OPENSEARCH_PASSWORD" "$OPENSEARCH_SCHEME://$OPENSEARCH_HOST:$OPENSEARCH_PORT/laporan2/_count"

# Sample data
curl -u "$OPENSEARCH_USER:$OPENSEARCH_PASSWORD" "$OPENSEARCH_SCHEME://$OPENSEARCH_HOST:$OPENSEARCH_PORT/laporan2/_search?size=1"
```

---

## Troubleshooting

### 1. **Timeout 30s pada Sync**

**Gejala:**
```
Error: timeout of 30000ms exceeded
```

**Penyebab:**
- Sync process lama (>30s)
- Frontend timeout menunggu response

**Solusi:**
✅ Sudah fixed — sync jalan di background thread, return instant (<100ms)

---

### 2. **Index Name Berbeda (Schema Builder vs CDC)**

**Gejala:**
- Schema Builder tampil: `laporan2`
- CDC logs tampil: `laporan`
- Data masuk ke index salah

**Penyebab:**
- CDC service pakai table name sebagai index (salah)
- Harusnya pakai `schema.index` dari config

**Solusi:**
✅ Sudah fixed — CDC sekarang baca `schema_config.index`

**Cek di logs:**
```
[05:12:51] Schema mapping: PG table 'laporan' → OS index 'laporan2'
[05:12:51]   Using schema-mapped index: laporan2
```

---

### 3. **Error: immense_term (field terlalu panjang)**

**Gejala:**
```
illegal_argument_exception: Document contains at least one immense term
in field="narasi" (whose UTF8 encoding is longer than the max length 32766)
```

**Penyebab:**
- Field `narasi` ada row dengan text >32KB
- OpenSearch limit: 32766 bytes per field

**Solusi:**
✅ Sudah fixed — auto-truncate ke 30KB

**Cek di logs:**
```
[05:15:20]   ✂ Truncated field 'narasi' from 44201 bytes to 30000 bytes
```

---

### 4. **Logs Tidak Muncul**

**Gejala:**
- Sync selesai
- Button "View Logs" tidak muncul

**Penyebab:**
- Logs belum di-fetch dari backend
- `cdcLogs[config_id]` masih kosong

**Solusi:**
1. Tunggu sync selesai (status = "stopped")
2. Refresh page atau klik "Sync Now" lagi
3. Logs auto-fetch setelah sync

**Manual fetch:**
```bash
curl http://localhost:3505/api/cdc/5/logs
```

---

### 5. **Sync Return 0 Rows**

**Gejala:**
```
Total rows synced: 0
```

**Penyebab:**
- Checkpoint sudah di latest timestamp
- Data PG tidak ada perubahan sejak last sync
- Timestamp column tidak ditemukan

**Cek:**
1. **Timestamp column:**
   ```sql
   SELECT column_name, data_type
   FROM information_schema.columns
   WHERE table_name = 'laporan'
   AND data_type LIKE '%timestamp%';
   ```

2. **Data PG:**
   ```sql
   SELECT COUNT(*), MAX(updated_date)
   FROM laporan
   WHERE updated_date > '2000-01-01';
   ```

3. **Checkpoint:**
   ```bash
   sqlite3 pgsync_admin.db "SELECT config_id, last_sync_time FROM cdc_states;"
   ```

**Reset checkpoint (force re-sync semua):**
```bash
sqlite3 pgsync_admin.db "UPDATE cdc_states SET last_sync_time = '2000-01-01' WHERE config_id = 5;"
```

---
