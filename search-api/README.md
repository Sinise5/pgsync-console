# Laporan Search API

FastAPI service untuk full-text search + dynamic filtering OpenSearch index `laporan`.

## Konfigurasi dan port

- Siapkan environment di root repo: `cp .env.example .env`, lalu isi koneksi.
- `make search-run` menjalankan service lokal di `http://localhost:8080`.
- Docker memetakan `SEARCH_API_PORT` (default `18080`) ke port container `8080`.
- Jalankan Docker dari root dengan `make search-up`, atau dari folder ini dengan `docker compose --env-file ../.env up -d`.
- `OPENSEARCH_PASSWORD` wajib diisi; aplikasi tidak memakai password fallback.
- Verifikasi sertifikat TLS aktif secara default. Untuk sertifikat self-signed di development, set `OPENSEARCH_VERIFY_CERTS=false` hanya di environment lokal.

## Features

✅ **Full-text search** — nomor, judul, narasi, catatan, komentar, laporan_isi
✅ **Dynamic filters** — filter by any field (status, urgensi_id, jenis_id, dll)
✅ **Pagination** — page + size parameters
## Quick Start

⚠️ **This is a workspace member.** Install dependencies from root first.

### 1. Setup (from root)

```bash
# Navigate to root
cd ..

# Install ALL workspace dependencies (PGSync + Search API)
make install

# Configure environment in repository root
cp .env.example .env
nano .env  # set OPENSEARCH_HOST, OPENSEARCH_PASSWORD, and other connection values
```

### 2. Run Locally

```bash
# From root
make search-run

# Or from search-api/ (the service loads ../.env)
cd search-api
make run
```

### 3. Verify

```bash
curl http://localhost:8080/health
```

Expected:
```json
{
  "status": "healthy",
  "opensearch": {
    "cluster_name": "<cluster name>",
    "version": "<OpenSearch version>"
  }
}
```

---

## API Endpoints

### GET /

Service info + available endpoints

```bash
curl http://localhost:8080/  # local
curl http://localhost:18080/ # Docker
```

### GET /health

Health check — verify OpenSearch connectivity

```bash
curl http://localhost:8080/health  # local
curl http://localhost:18080/health # Docker
```

### GET /search

Search dengan query parameters

**Parameters:**
- `q` — full-text search query
- `page` — page number (default: 1)
- `size` — results per page (default: 20, max: 100)
- `sort_by` — field to sort by
- `sort_order` — `asc` or `desc` (default: `desc`)
- `highlight` — enable highlighting (default: `true`)
- **Dynamic filters:**
  - `status`
  - `approve`
  - `jenis_id`
  - `klasifikasi_id`
  - `urgensi_id`
  - `satuan_kerja_id`
  - `created_by_id`
  - `pelapor_id`
  - `tujuan_id`

### POST /search

Search dengan JSON body (recommended untuk complex queries)

**Body:**
```json
{
  "query": "korupsi",
  "filters": {
    "status": "approve",
    "urgensi_id": 1
  },
  "page": 1,
  "size": 20,
  "sort_by": "created_date",
  "sort_order": "desc",
  "highlight": true
}
```

---

## Usage Examples

### 1. Basic Full-Text Search

```bash
# Search "korupsi" dalam semua text fields
curl "http://localhost:18080/search?q=korupsi"

# Search dengan pagination
curl "http://localhost:18080/search?q=korupsi&page=2&size=50"
```

### 2. Filter by Status

```bash
# Filter laporan yang sudah di-approve
curl "http://localhost:18080/search?status=approve"

# Combine search + filter
curl "http://localhost:18080/search?q=politik&status=approve"
```

### 3. Filter by IDs

```bash
# Filter by urgensi_id
curl "http://localhost:18080/search?urgensi_id=1"

# Multiple filters
curl "http://localhost:18080/search?jenis_id=2&klasifikasi_id=3&urgensi_id=1"

# Search + multiple filters
curl "http://localhost:18080/search?q=ekonomi&jenis_id=2&status=approve"
```

### 4. Sort Results

```bash
# Sort by created_date descending (newest first)
curl "http://localhost:18080/search?q=korupsi&sort_by=created_date&sort_order=desc"

# Sort by tanggal_laporan ascending (oldest first)
curl "http://localhost:18080/search?sort_by=tanggal_laporan&sort_order=asc"
```

### 5. POST Request (Complex Query)

```bash
curl -X POST http://localhost:18080/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "korupsi OR suap",
    "filters": {
      "status": "approve",
      "urgensi_id": 1,
      "jenis_id": 2
    },
    "page": 1,
    "size": 20,
    "sort_by": "created_date",
    "sort_order": "desc",
    "highlight": true
  }'
```

### 6. Date Range Filter (POST only)

```bash
curl -X POST http://localhost:18080/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "politik",
    "filters": {
      "tanggal_laporan": {
        "gte": "2024-01-01",
        "lte": "2024-12-31"
      }
    },
    "page": 1,
    "size": 20
  }'
```

### 7. No Highlighting

```bash
# Disable highlighting (faster response)
curl "http://localhost:18080/search?q=korupsi&highlight=false"
```

---

## Response Format

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
      "narasi": "...",
      "status": "approve",
      "urgensi_id": 1,
      "created_date": "2024-06-01T10:00:00",
      "_highlight": {
        "judul": ["Laporan Dugaan <mark>Korupsi</mark>"],
        "narasi": ["... terkait <mark>korupsi</mark> ..."]
      }
    }
  ]
}
```

**Fields:**
- `total` — total matching documents
- `page` — current page number
- `size` — results per page
- `total_pages` — total pages available
- `took` — query execution time (milliseconds)
- `results` — array of documents
  - `id` — document ID
  - `score` — relevance score
  - `_highlight` — highlighted snippets (jika enabled)
  - ... all other fields from schema

---

## Schema Reference

### Searchable Fields (Full-Text)

- `nomor`
- `judul`
- `narasi`
- `catatan`
- `komentar`
- `laporan_isi.isi`
- `laporan_isi.apa`
- `laporan_isi.mengapa`
- `laporan_isi.bagaimana`
- `laporan_isi.kapan`

### Filterable Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Laporan ID |
| `status` | keyword | Status laporan |
| `approve` | keyword | Approval status |
| `tanggal_laporan` | date | Tanggal laporan (supports range) |
| `created_date` | date | Created timestamp |
| `updated_date` | date | Updated timestamp |
| `unique_id` | keyword | Unique identifier |
| `status_pengajuan_penghapusan` | keyword | Deletion request status |
| `jenis_id` | integer | Jenis ID |
| `klasifikasi_id` | integer | Klasifikasi ID |
| `urgensi_id` | integer | Urgensi ID |
| `created_by_id` | integer | Creator user ID |
| `updated_by_id` | integer | Updater user ID |
| `pelapor_id` | integer | Pelapor ID |
| `tujuan_id` | integer | Tujuan ID |
| `satuan_kerja_id` | integer | Satuan kerja ID |
| `neraca_kebenaran_id` | integer | Neraca kebenaran ID |
| `neraca_kepercayaan_id` | integer | Neraca kepercayaan ID |

---

## Deployment

### Local Testing (uv + Make)

```bash
cd search-api

# Install uv (https://astral.sh/uv/install.sh)
# Setup venv + deps
make install

# Set env vars
export OPENSEARCH_HOST=localhost
export OPENSEARCH_PORT=9200
export OPENSEARCH_USER=admin
export OPENSEARCH_PASSWORD=your_p...n

# Run dev server (auto-reload on code change)
make run
```

Access: http://localhost:8080

### Docker Production

```bash
cd search-api

# Build
docker compose build

# Run detached
docker compose up -d

# Check logs
docker logs laporan-search-api -f

# Restart
docker compose restart

# Stop
docker compose down
```

### Remote Server

```bash
# Copy to server
scp -r search-api deploy@your-server:~/pgsync-production/

# SSH to server
ssh deploy@your-server

# Navigate
cd ~/pgsync-production/search-api

# Setup env
cp .env.example .env
nano .env

# Deploy
docker compose up -d --build

# Verify
curl http://localhost:18080/health
```

---

## Integration Examples

### JavaScript/TypeScript

```javascript
// GET request
const response = await fetch(
  'http://localhost:18080/search?q=korupsi&status=approve&page=1&size=20'
);
const data = await response.json();
console.log(`Found ${data.total} results`);

// POST request
const response = await fetch('http://localhost:18080/search', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'politik',
    filters: { urgensi_id: 1 },
    page: 1,
    size: 20
  })
});
const data = await response.json();
```

### Python

```python
import requests

# GET request
response = requests.get(
    'http://localhost:18080/search',
    params={
        'q': 'korupsi',
        'status': 'approve',
        'page': 1,
        'size': 20
    }
)
data = response.json()
print(f"Found {data['total']} results")

# POST request
response = requests.post(
    'http://localhost:18080/search',
    json={
        'query': 'politik',
        'filters': {'urgensi_id': 1},
        'page': 1,
        'size': 20
    }
)
data = response.json()
```

---

## Troubleshooting

### Service not starting

```bash
# Check logs
docker logs laporan-search-api

# Common issues:
# 1. OPENSEARCH_PASSWORD not set
# 2. OpenSearch not reachable from container
# 3. Port 8080 already in use
```

### OpenSearch connection failed

```bash
# Test connectivity from container
docker exec laporan-search-api python3 -c "
from opensearchpy import OpenSearch
import os
client = OpenSearch(
    hosts=[{'host': os.getenv('OPENSEARCH_HOST'), 'port': int(os.getenv('OPENSEARCH_PORT'))}],
    http_auth=(os.getenv('OPENSEARCH_USER'), os.getenv('OPENSEARCH_PASSWORD')),
    use_ssl=True,
    verify_certs=os.getenv("OPENSEARCH_VERIFY_CERTS", "true").lower() == "true"
)
print(client.info())
"
```

### No results returned

```bash
# Check index exists
curl -u "$OPENSEARCH_USER:$OPENSEARCH_PASSWORD" "$OPENSEARCH_SCHEME://$OPENSEARCH_HOST:$OPENSEARCH_PORT/_cat/indices/laporan?v"

# Check document count
curl -u "$OPENSEARCH_USER:$OPENSEARCH_PASSWORD" "$OPENSEARCH_SCHEME://$OPENSEARCH_HOST:$OPENSEARCH_PORT/laporan/_count"

# Test basic match_all query
curl "http://localhost:18080/search?size=10"
```

---

## Performance Tips

1. **Use POST for complex queries** — GET has URL length limits
2. **Disable highlighting for large result sets** — `highlight=false`
3. **Use specific filters** — filters are faster than full-text search
4. **Limit page size** — max 100, recommend 20-50 for UI
5. **Use date range filters** — more efficient than full scan

---

## License

This service is covered by the repository MIT License.
