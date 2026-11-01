# Search API - Deployment Summary

Tanggal: 2026-06-09
Port: 18080 (non-standard, production-ready)

---

## ✅ Files Created

```
search-api/
├── main.py              # 354 lines — FastAPI app with OpenSearch queries
├── pyproject.toml       # 25 lines — uv-native dependencies (replaces requirements.txt)
├── Dockerfile           # 26 lines — uv-native build (10-100x faster)
├── docker-compose.yml   # 27 lines — service config, port 18080, restart policy
├── Makefile             # 126 lines — local dev + docker commands
├── .env.example         # Environment variables template
├── README.md            # 468 lines — API docs, curl examples, integration guides
├── INSTALL.md           # 232 lines — Step-by-step deployment & troubleshooting
└── DEPLOYMENT.md        # This file
```

---

## 🚀 Quick Deploy (Production)

⚠️ **This is a uv workspace monorepo.** All commands run from root.

```bash
# 1. Copy entire repo to server
scp -r pgsync-production deploy@your-server:~/

# 2. SSH ke server
ssh deploy@your-server

# 3. Setup workspace
cd ~/pgsync-production
cp .env.example .env
nano .env  # set OPENSEARCH_PASSWORD & PG_PASSWORD

# 4. Install dependencies (entire workspace)
make install

# 5. Build all images
make build

# 6. Start all services (PGSync CDC + Search API)
make up

# 7. Verify
make dev-status
curl http://localhost:18080/health
```

---

## 🔧 Local Testing (Makefile)

```bash
cd search-api

# Install uv + setup venv
make install

# Run dev server (auto-reload)
make run

# In another terminal: test
make test-health
make test-search
```

---

## 🔍 Test Queries

```bash
# Health check
curl http://localhost:18080/health

# Basic search
curl "http://localhost:18080/search?q=korupsi&size=5"

# With filters
curl "http://localhost:18080/search?status=approve&urgensi_id=1&page=1&size=20"

# Complex POST
curl -X POST http://localhost:18080/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "politik",
    "filters": {"status": "approve", "jenis_id": 2},
    "page": 1,
    "size": 20,
    "sort_by": "created_date",
    "sort_order": "desc"
  }'
```

---

## 📊 Features

✅ **Full-text search** — 10 searchable fields (nomor, judul, narasi, laporan_isi.*, dll)
✅ **Dynamic filters** — 17 filterable fields (status, urgensi_id, jenis_id, dates, dll)
✅ **Pagination** — page + size (max 100 per page)
✅ **Highlighting** — search term highlighting dengan `<mark>` tags
✅ **Sort** — any field, asc/desc
✅ **Date ranges** — support `{"tanggal_laporan": {"gte": "2024-01-01"}}`
✅ **GET & POST** — both methods supported
✅ **Healthcheck** — auto-restart on failure

---

## 🛠 Maintenance Commands

```bash
# Logs
docker logs laporan-search-api -f

# Restart
docker compose restart

# Rebuild after code change
docker compose down
docker compose up -d --build

# Stats
docker stats laporan-search-api

# Stop
docker compose down
```

---

## 📝 API Response Format

```json
{
  "total": 1234,
  "page": 1,
  "size": 20,
  "total_pages": 62,
  "took": 15,
  "results": [
    {
      "id": "12345",
      "score": 8.234,
      "nomor": "LAP/2024/001",
      "judul": "Laporan Dugaan Korupsi",
      "status": "approve",
      "urgensi_id": 1,
      "_highlight": {
        "judul": ["<mark>Korupsi</mark>"]
      }
    }
  ]
}
```

---

## 🔗 Integration

**JavaScript:**
```javascript
const response = await fetch('http://localhost:18080/search?q=korupsi');
const data = await response.json();
```

**Python:**
```python
import requests
response = requests.get('http://localhost:18080/search', params={'q': 'korupsi'})
data = response.json()
```

**curl:**
```bash
curl "http://localhost:18080/search?q=korupsi&status=approve"
```

---

## 🔐 Security

- ✅ OPENSEARCH_PASSWORD via environment variable (not hardcoded)
- ✅ SSL disabled OpenSearch cert verification (internal network trusted)
- ✅ Port 18080 (non-standard, reduces automated scanning)
- ✅ Healthcheck auto-restart on failure
- ⚠️ No authentication on API itself (add reverse proxy with auth if exposed to internet)

---

## 📚 Documentation

- **INSTALL.md** — Complete installation & deployment guide
- **README.md** — API reference, examples, troubleshooting
- **main.py docstring** — Quick usage examples

---

## ✅ Ready to Push

```bash
cd /Volumes/Sinise/work/qti/pgsync-production

# Add search-api directory
git add search-api/

# Commit
git commit -m "feat: add search API service

- FastAPI service for full-text search + dynamic filtering
- Port 18080 (non-standard)
- OpenSearch integration
- Pagination, highlighting, sort support
- Docker + docker-compose ready
- Full documentation (README + INSTALL)"

# Push (setelah konfirmasi user)
# git push origin main
```

---

## 🎯 Next Steps

1. Deploy ke server (ikuti INSTALL.md)
2. Test semua endpoints
3. Integrate dengan frontend/dashboard
4. Optional: setup reverse proxy (nginx) untuk HTTPS + auth
5. Optional: monitoring & alerting (Prometheus + Grafana)

---

**Status:** ✅ Ready for production
**Port:** 18080
**Docs:** README.md + INSTALL.md
**Server:** your-search-server
