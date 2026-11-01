# Laporan Search API - Installation Guide

⚠️ **This service is part of a uv workspace monorepo.**
All dependencies are managed from the root `pgsync-production/` directory.

Complete installation and deployment guide untuk production environment.

---

## Prerequisites

### Server Requirements
- Docker Engine 20.10+
- Docker Compose v2.0+
- **uv** (Rust-based Python package manager)
- Min 512MB RAM available
- Port 18080 available

### Install uv (if not installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### OpenSearch Requirements
- OpenSearch 2.x running dan accessible
- Index `laporan` sudah ada (dari PGSync CDC)
- Credentials: username + password dengan read access

---

## Installation Steps

### 1. Prepare Workspace

```bash
# Login ke server
ssh deploy@your-server

# Navigate ke project root (NOT search-api/)
cd ~/pgsync-production

# Verify workspace structure
ls -la
```

**Expected output:**
```
drwxr-xr-x 10 isep isep 4096 Jun  9 13:00 .
drwxr-xr-x  5 isep isep 4096 Jun  9 12:00 ..
-rw-r--r--  1 isep isep  327 Jun  9 13:30 pyproject.toml
-rw-r--r--  1 isep isep 6370 Jun  9 13:31 Makefile
-rw-r--r--  1 isep isep 5930 Jun  9 13:32 README.md
drwxr-xr-x  2 isep isep 4096 Jun  9 13:00 search-api/
drwxr-xr-x  2 isep isep 4096 Jun  9 13:00 config/
drwxr-xr-x  2 isep isep 4096 Jun  9 13:00 scripts/
...
```

---

### 2. Install Workspace Dependencies

```bash
# Install ALL dependencies (PGSync + Search API) with single command
make install

# This creates .venv/ at root and installs:
# - PGSync deps: pgsync, opensearch-py, psycopg2-binary
# - Search API deps: fastapi, uvicorn, pydantic
# - Generates single uv.lock for entire workspace
```

**Expected output:**
```
=== Installing workspace dependencies (uv sync) ===
Resolved 45 packages in 1.2s
Installed 45 packages in 850ms
=== ✅ Done - all dependencies installed ===
```

---

### 3. Configure Environment

```bash
# Copy env template
cp .env.example .env

# Edit configuration
nano .env
```

**Set these values:**
```bash
# PostgreSQL
PG_PASSWORD=***

# OpenSearch
OPENSEARCH_PASSWORD=***

# Redis (leave default if local)
REDIS_HOST=localhost
```

**Save and exit:** `Ctrl+X`, `Y`, `Enter`

---

### 4. Build Docker Images

```bash
# Build ALL images (PGSync + Search API)
make build

# This runs:
# - docker build PGSync base image (with patch)
# - docker build PGSync app image
# - docker build Search API image (uv-native)
```

**Expected output:**
```
=== Building PGSync images ===
[OK] PLUGIN = test_decoding
...
=== Building Search API image ===
Successfully tagged laporan-search-api:latest
=== ✅ All images built ===
```

---

### 5. Start Services

```bash
# Start ALL services (PGSync CDC + Search API)
make up

# Or start individually:
# make pgsync-up
# make search-up
```

**Expected output:**
```
=== Starting Search API ===
{
  "status": "healthy",
  "opensearch": {
    "cluster_name": "opensearch-cluster",
    "version": "2.11.1"
  }
}
=== ✅ All services running ===
```

---

### 6. Verify Services

```bash
# Check status
make dev-status

# Search API health
curl http://localhost:18080/health

# PGSync CDC logs
make pgsync-logs

# Search API logs
make search-logs
```

---

## Post-Installation

### Enable External Access (Optional)

Jika perlu akses dari luar server (dari mesin lain di network):

```bash
# Check firewall (jika ada)
sudo ufw status

# Allow port 18080 (jika firewall enabled)
sudo ufw allow 18080/tcp

# Test dari mesin lain
curl "http://localhost:18080/health"
```

### Auto-Start on Boot

Service sudah configured dengan `restart: unless-stopped` di docker-compose.yml.

Container akan auto-restart:
- Setelah server reboot
- Jika container crash
- Kecuali di-stop manual dengan `docker compose down`

---

## Maintenance

### View Logs

```bash
# All services combined
make logs

# PGSync CDC only
make pgsync-logs

# Search API only
make search-logs

# With timestamps
docker logs laporan-search-api -f --timestamps
```

### Restart Services

```bash
# Restart all services
make restart

# Restart individually
make pgsync-up
make search-up

# Or using docker compose directly
docker compose restart
```

### Update Code

```bash
cd ~/pgsync-production

# Pull latest code
git pull origin main

# Re-sync dependencies (if pyproject.toml changed)
make sync

# Rebuild and restart
make rebuild
```

### Check Resource Usage

```bash
# All containers stats
docker stats

# Service status
make dev-status

# Detailed inspect
docker inspect laporan-search-api
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs for error
docker logs laporan-search-api

# Common issues:
# 1. Port 18080 already in use
sudo netstat -tulpn | grep 18080

# 2. OpenSearch connection failed
docker exec laporan-search-api python3 -c "import os; print('OpenSearch host:', os.getenv('OPENSEARCH_HOST'))"

# 3. Container crash loop
docker ps -a | grep laporan-search-api  # check restart count
```

### Can't Connect to OpenSearch

```bash
# Test from container
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

# If fails, check:
# - OPENSEARCH_HOST reachable: ping localhost
# - OPENSEARCH_PORT correct: telnet localhost 9200
# - Credentials correct: check .env file
```

### No Search Results

```bash
# Check index exists
curl -u "$ELASTICSEARCH_USER:$ELASTICSEARCH_PASSWORD" "$ELASTICSEARCH_SCHEME://$ELASTICSEARCH_HOST:$ELASTICSEARCH_PORT/_cat/indices/laporan?v"

# Check document count
curl -u "$ELASTICSEARCH_USER:$ELASTICSEARCH_PASSWORD" "$ELASTICSEARCH_SCHEME://$ELASTICSEARCH_HOST:$ELASTICSEARCH_PORT/laporan/_count"

# If 0 docs, PGSync bootstrap belum jalan atau CDC belum sync
```

### High Memory Usage

```bash
# Check memory
docker stats laporan-search-api --no-stream

# If >500MB, restart service
docker compose restart

# For production, set memory limit di docker-compose.yml:
# deploy:
#   resources:
#     limits:
#       memory: 512M
```

---

## Uninstall

```bash
cd ~/pgsync-production/search-api

# Stop and remove container
docker compose down

# Remove image (optional)
docker rmi laporan-search-api:latest

# Remove data (optional, if needed)
rm -rf search-api/
```

---

## Security Notes

### Production Checklist

- [ ] Change default OpenSearch password
- [ ] Use strong `.env` file permissions: `chmod 600 .env`
- [ ] Restrict port 18080 to internal network only (firewall rules)
- [ ] Enable HTTPS reverse proxy (nginx/traefik) jika expose ke internet
- [ ] Review logs regularly: `docker logs laporan-search-api`

### Reverse Proxy (Optional - untuk HTTPS)

```nginx
# /etc/nginx/sites-available/search-api
server {
    listen 443 ssl http2;
    server_name search.your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:18080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Next Steps

1. ✅ Installation complete
2. 📖 Read [README.md](README.md) untuk API usage examples
3. 🔍 Test search queries: `curl "http://localhost:18080/search?q=test"`
4. 📊 Integrate dengan frontend/dashboard
5. 🔐 Setup monitoring & alerts (optional)

---

## Support

**Logs:** `docker logs laporan-search-api -f`
**Health:** `curl http://localhost:18080/health`
**Docs:** [README.md](README.md)

**Server:** your-search-server (your-server)
**Maintainer:** QTI Research
