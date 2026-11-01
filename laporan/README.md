# laporan/ — Config & Data Directory

## File

| File | Fungsi |
|------|--------|
| `.env` | Kredensial PostgreSQL + OpenSearch (fallback legacy) |

**Prioritas load script batch:**
1. `.env.laporan-dev` (root project) — kalau ada
2. `.env.laporan` (root project) — produksi
3. `laporan/.env` — legacy fallback

## `.env` Format

```bash
export PG_HOST=localhost
export PG_PORT=5432
export PG_USER=postgres
export PG_PASSWORD=your_postgres_password_here
export PG_DATABASE=siitpartisi

export ELASTICSEARCH_SCHEME=https
export ELASTICSEARCH_HOST=localhost
export ELASTICSEARCH_PORT=9200
export ELASTICSEARCH_USER=admin
export ELASTICSEARCH_PASSWORD=your_opensearch_password_here
export ELASTICSEARCH_USE_SSL=true
export ELASTICSEARCH_VERIFY_CERTS=false

export OPENSEARCH=true
export SCHEMA=config/schema-laporan.json
```

> **Catatan:** Project utama sekarang pakai `.env.laporan` di root.
> `laporan/.env` cuma fallback — tidak perlu diubah untuk operasi normal.
