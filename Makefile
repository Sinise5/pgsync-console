# PGSync Production - Central Makefile
# =====================================
# Monorepo dengan uv workspace: PGSync CDC + Search API
DOCKER_COMPOSE ?= docker-compose

.PHONY: help install sync clean

## =============================================================================
# WORKSPACE SETUP
## =============================================================================

# Install all workspace dependencies (1 uv.lock for entire repo)
install:
	@echo "=== Installing workspace dependencies (uv sync) ==="
	uv sync
	@echo "=== ✅ Done - all dependencies installed ==="

# Sync dependencies (after adding new deps)
sync:
	uv sync

# Lock dependencies
lock:
	uv lock

# Clean venv + cache
clean:
	rm -rf .venv
	rm -rf .uv_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

## =============================================================================
# PGSYNC CDC
## =============================================================================

.PHONY: pgsync-build pgsync-up pgsync-down pgsync-logs pgsync-bootstrap

# Build PGSync images (base + app)
pgsync-build:
	@echo "=== Building PGSync images ==="
	docker build --no-cache -f Dockerfile.base -t pgsync-laporan:base .
	docker build --no-cache -t pgsync-laporan:app .

# Start PGSync CDC
pgsync-up:
	@echo "PGSync CDC is not defined as a service in docker-compose.yml; use the PGSync-specific deployment configuration."
	@exit 1

# Stop PGSync CDC
pgsync-down:
	@echo "PGSync CDC is not defined as a service in docker-compose.yml."
	@exit 1

# View PGSync CDC logs
pgsync-logs:
	@echo "PGSync CDC container is not defined in this Compose project."
	@exit 1

# Run bootstrap (full index rebuild)
pgsync-bootstrap:
	@echo "PGSync bootstrap service is not defined in docker-compose.yml."
	@exit 1

# Setup replication slot (PostgreSQL)
pgsync-slot-create:
	@echo "=== Create replication slot ==="
	@echo "Run this SQL on PostgreSQL server (localhost):"
	@echo ""
	@echo "SELECT pg_create_logical_replication_slot('siitpartisi_laporan', 'test_decoding');"
	@echo ""

pgsync-slot-drop:
	@echo "=== Drop replication slot ==="
	@echo "Run this SQL on PostgreSQL server (localhost):"
	@echo ""
	@echo "SELECT pg_drop_replication_slot('siitpartisi_laporan');"
	@echo ""

## =============================================================================
# SEARCH API
## =============================================================================

.PHONY: search-run search-build search-up search-down search-logs search-test

# Run search-api locally (dev mode with auto-reload)
search-run:
	@echo "=== Running Search API on http://localhost:8080 ==="
	cd search-api && uv run uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# Build search-api Docker image
search-build:
	@echo "=== Building Search API image ==="
	cd search-api && docker build -t laporan-search-api .

# Start search-api container
search-up:
	@echo "=== Starting Search API ==="
	cd search-api && $(DOCKER_COMPOSE) --env-file ../.env up -d --build
	cd search-api && $(DOCKER_COMPOSE) --env-file ../.env ps

# Stop search-api container
search-down:
	cd search-api && $(DOCKER_COMPOSE) --env-file ../.env down

# View search-api logs
search-logs:
	docker logs laporan-search-api -f

# Test search-api (health + search)
search-test:
	@echo "=== Testing Search API ==="
	@SEARCH_PORT=$$($(DOCKER_COMPOSE) --env-file .env -f search-api/docker-compose.yml port search-api 8080 | sed 's/.*://'); \
	 curl -s "http://127.0.0.1:$$SEARCH_PORT/health" | jq '.'; \
	 curl -s "http://127.0.0.1:$$SEARCH_PORT/search?q=test&size=5" | jq '.total, .page, .size'

## =============================================================================
# PGSYNC ADMIN (Visual CDC Platform)
## =============================================================================

.PHONY: admin-db-init admin-backend-run admin-frontend-dev admin-frontend-build
.PHONY: admin-build admin-up admin-down admin-logs admin-test-quick admin-full-test

# Initialize SQLite database with all tables
admin-db-init:
	@echo "=== Initializing PGSync Admin Database ==="
	cd pgsync-admin/backend && uv run python -c "from backend.db import db; db.init_db(); print('✅ Database initialized')"

# Run backend locally (dev mode with auto-reload)
admin-backend-run:
	@echo "=== Running PGSync Admin Backend on http://localhost:3505 ==="
	@lsof -ti:3505 | xargs kill -9 2>/dev/null || true
	@sleep 1
	cd pgsync-admin/backend && uv run python -m backend.main

# Run frontend dev server (auto-reload)
admin-frontend-dev:
	@echo "=== Running PGSync Admin Frontend (dev) on http://localhost:3506 ==="
	@lsof -ti:3506 | xargs kill -9 2>/dev/null || true
	@sleep 1
	cd pgsync-admin/frontend && npm run dev -- --port 3506

# Build frontend for production
admin-frontend-build:
	@echo "=== Building PGSync Admin Frontend ==="
	cd pgsync-admin/frontend && npm run build
	@echo "✅ Build complete: pgsync-admin/frontend/dist/"

# Build Docker images (backend + frontend)
admin-build:
	@echo "=== Building PGSync Admin Docker Images ==="
	$(DOCKER_COMPOSE) -f docker-compose.yml build
	@echo "✅ PGSync Admin images built"

# Start PGSync Admin (Docker)
admin-up:
	@echo "=== Starting PGSync Admin ==="
	$(DOCKER_COMPOSE) -f docker-compose.yml up -d --build
	@echo "✅ PGSync Admin running:"
	@echo "   Frontend: http://localhost:3507"
	@echo "   Backend:  http://localhost:3505"

# Stop PGSync Admin
admin-down:
	@echo "=== Stopping PGSync Admin ==="
	$(DOCKER_COMPOSE) -f docker-compose.yml down
	@echo "✅ PGSync Admin stopped"

# View PGSync Admin logs
admin-logs:
	@echo "=== PGSync Admin Logs (Ctrl+C to exit) ==="
	$(DOCKER_COMPOSE) -f docker-compose.yml logs -f

# Quick test (start backend, test health, kill)
admin-test-quick:
	@echo "=== Quick Test: Starting Backend ==="
	@lsof -ti:3505 | xargs kill -9 2>/dev/null || true
	@cd pgsync-admin/backend && uv run python -m backend.main &
	@sleep 5
	@echo "=== Testing Health Endpoint ==="
	@curl -s http://localhost:3505/health || echo "❌ Health check failed"
	@echo ""
	@echo "=== Killing Backend ==="
	@lsof -ti:3505 | xargs kill -9 2>/dev/null || true
	@echo "✅ Quick test complete"

# Full test (backend + frontend build + health checks)
admin-full-test: admin-db-init admin-frontend-build
	@echo "=== Full Test: Starting Backend ==="
	@lsof -ti:3505 | xargs kill -9 2>/dev/null || true
	@cd pgsync-admin/backend && uv run python -m backend.main &
	@sleep 5
	@echo "=== Testing All Endpoints ==="
	@curl -s http://localhost:3505/health | jq '.' || echo "❌ Health failed"
	@curl -s http://localhost:3505/api/configs | jq '.configs | length' || echo "❌ Configs API failed"
	@echo ""
	@echo "=== Frontend Build Check ==="
	@test -d pgsync-admin/frontend/dist && echo "✅ Frontend dist exists" || echo "❌ No frontend dist"
	@echo ""
	@echo "=== Killing Backend ==="
	@lsof -ti:3505 | xargs kill -9 2>/dev/null || true
	@echo "✅ Full test complete"

# ClickHouse migration targets
.PHONY: admin-clickhouse-init admin-clickhouse-migrate-status admin-clickhouse-migrate-history admin-clickhouse-migrate-up admin-clickhouse-migrate-down admin-migrations-setup

# Initialize ClickHouse database + create tables
admin-clickhouse-init:
	@echo "=== Initializing ClickHouse Database ==="
	@echo "Creating database: pgsync_admin"
	@curl -s -X POST "http://localhost:8123/" -d "CREATE DATABASE IF NOT EXISTS pgsync_admin" || echo "❌ ClickHouse not running at localhost:8123"
	@echo ""
	@echo "Creating executions table..."
	@cat pgsync-admin/backend/schema/clickhouse/01_executions.sql | curl -s -X POST "http://localhost:8123/" --data-binary @- || echo "❌ Failed to create executions table"
	@echo ""
	@echo "Creating execution_metrics table..."
	@cat pgsync-admin/backend/schema/clickhouse/02_execution_metrics.sql | curl -s -X POST "http://localhost:8123/" --data-binary @- || echo "❌ Failed to create execution_metrics table"
	@echo ""
	@echo "✅ ClickHouse database initialized"
	@echo ""
	@echo "Tables created: pgsync_admin.executions, pgsync_admin.execution_metrics"
	@echo "Verify: curl -s 'http://localhost:8123/?query=SHOW+TABLES+FROM+pgsync_admin+FORMAT+TabSeparated'"

admin-clickhouse-migrate-status:
	@echo "=== ClickHouse Migration Status ==="
	@curl -s http://localhost:3505/api/clickhouse/migrations/current 2>/dev/null | jq '.' || echo "❌ Backend not running at localhost:3505"

admin-clickhouse-migrate-history:
	@echo "=== ClickHouse Migration History ==="
	@curl -s http://localhost:3505/api/clickhouse/migrations/history 2>/dev/null | jq '.' || echo "❌ Backend not running at localhost:3505"

admin-clickhouse-migrate-up:
	@echo "=== Applying ClickHouse Migrations ==="
	@curl -s -X POST http://localhost:3505/api/clickhouse/migrations/upgrade 2>/dev/null | jq '.' || echo "❌ Backend not running at localhost:3505"

admin-clickhouse-migrate-down:
	@echo "=== Rollback ClickHouse Migration ==="
	@test -n "$(VERSION)" || { echo "Usage: make admin-clickhouse-migrate-down VERSION=20260619"; exit 1; }
	@curl -s -X POST http://localhost:3505/api/clickhouse/migrations/rollback \
		-H "Content-Type: application/json" \
		-d "{\"version\":\"$(VERSION)\"}" 2>/dev/null | jq '.' || echo "❌ Backend not running"

# Combined: Initialize both SQLite + ClickHouse databases
admin-migrations-setup: admin-db-init admin-clickhouse-init
	@echo ""
	@echo "=== ✅ All Databases Initialized ==="
	@echo ""
	@echo "SQLite Tables (pgsync_admin.db):"
	@cd pgsync-admin/backend && uv run python -c "from backend.db import db; db.connect(); from sqlalchemy import inspect; insp = inspect(db.engine); tables = insp.get_table_names(); print('  ' + '\n  '.join(tables))" 2>/dev/null || echo "  ❌ Could not verify SQLite tables"
	@echo ""
	@echo "ClickHouse Tables (pgsync_admin):"
	@curl -s "http://localhost:8123/?query=SHOW+TABLES+FROM+pgsync_admin+FORMAT+TabSeparated" 2>/dev/null | awk '{print "  " $$0}' || echo "  ❌ Could not verify ClickHouse tables"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Start backend: make admin-backend-run"
	@echo "  2. Check migrations: make admin-clickhouse-migrate-status"
	@echo "  3. Apply migrations: make admin-clickhouse-migrate-up"

## =============================================================================
# COMBINED OPERATIONS
## =============================================================================

.PHONY: up down logs build restart

# Start all services currently defined for local Compose (Search API + PGSync Admin)
up: search-up admin-up
	@echo "=== ✅ All services running ==="

# Stop all services currently defined for local Compose
down: search-down admin-down
	@echo "=== ✅ All services stopped ==="

# View all logs (combined)
logs:
	$(DOCKER_COMPOSE) -f docker-compose.yml logs -f

# Build all images
# Build all currently configured Compose services and the PGSync image pair
build: pgsync-build search-build admin-build
	@echo "=== ✅ All images built ==="

# Restart all services
restart: down up
	@echo "=== ✅ All services restarted ==="

# Full rebuild + restart
rebuild: build down up
	@echo "=== ✅ Full rebuild complete ==="

## =============================================================================
# DEVELOPMENT
## =============================================================================

.PHONY: dev-setup dev-status

# One-time dev setup
dev-setup: install admin-db-init admin-frontend-build
	@echo "=== Dev Setup Complete ==="
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy .env.example -> .env and configure"
	@echo "  2. Run 'make pgsync-build' to build PGSync images"
	@echo "  3. Run 'make search-build' to build Search API image"
	@echo "  4. Run 'make admin-build' to build PGSync Admin images"
	@echo "  5. Run 'make up' to start all services"
	@echo ""
	@echo "For PGSync Admin development:"
	@echo "  make admin-backend-run    Start backend (port 3505)"
	@echo "  make admin-frontend-dev   Start frontend (port 3506)"
	@echo "  make admin-test-quick     Quick health test"
	@echo ""

# Show status of all services
dev-status:
	@echo "=== Service Status ==="
	@docker ps --filter "name=pgsync" --filter "name=laporan-search" --filter "name=pgsync-admin" --format "table {{.Names}}	{{.Status}}	{{.Ports}}"
	@echo ""
	@echo "=== Port Status ==="
	@echo -n "Port 3505 (Admin Backend): "; lsof -ti:3505 2>/dev/null && echo "IN USE" || echo "FREE"
	@echo -n "Port 3506 (Admin Frontend): "; lsof -ti:3506 2>/dev/null && echo "IN USE" || echo "FREE"
	@echo -n "Port 8080 (Search API): "; lsof -ti:8080 2>/dev/null && echo "IN USE" || echo "FREE"

## =============================================================================
# HELP
## =============================================================================

help:
	@echo "PGSync Production - Central Makefile"
	@echo "===================================="
	@echo ""
	@echo "WORKSPACE"
	@echo "  make install         Install all workspace dependencies (uv sync)"
	@echo "  make sync            Sync dependencies after pyproject.toml changes"
	@echo "  make clean           Remove venv + cache"
	@echo ""
	@echo "PGSYNC CDC"
	@echo "  make pgsync-build    Build PGSync images (base + app)"
	@echo "  make pgsync-up       Start PGSync CDC container"
	@echo "  make pgsync-down     Stop PGSync CDC"
	@echo "  make pgsync-logs     View CDC logs"
	@echo "  make pgsync-bootstrap Run bootstrap (full index rebuild)"
	@echo ""
	@echo "SEARCH API"
	@echo "  make search-run      Run locally (dev mode, auto-reload)"
	@echo "  make search-build    Build Docker image"
	@echo "  make search-up       Start container (port 18080)"
	@echo "  make search-down     Stop container"
	@echo "  make search-logs     View logs"
	@echo "  make search-test     Test health + search endpoints"
	@echo ""
	@echo "PGSYNC ADMIN"
	@echo "  Development:"
	@echo "    make admin-db-init            Initialize SQLite database + tables"
	@echo "    make admin-clickhouse-init    Initialize ClickHouse database + tables"
	@echo "    make admin-migrations-setup   Initialize both SQLite + ClickHouse (combined)"
	@echo "    make admin-backend-run        Run backend locally (port 3505)"
	@echo "    make admin-frontend-dev       Run frontend dev server (port 3506)"
	@echo "    make admin-frontend-build     Build frontend for production"
	@echo ""
	@echo "  Docker:"
	@echo "    make admin-build              Build Docker images (backend + frontend)"
	@echo "    make admin-up                 Start via Docker Compose"
	@echo "    make admin-down               Stop containers"
	@echo "    make admin-logs               View logs"
	@echo ""
	@echo "  Testing:"
	@echo "    make admin-test-quick         Quick health check"
	@echo "    make admin-full-test          Full test (DB init + build + health checks)"
	@echo "    make admin-test-unit          Run unit tests"
	@echo "    make admin-test-integration   Run integration tests"
	@echo "    make admin-test-e2e           Run end-to-end tests"
	@echo "    make admin-test-all           Run all tests with coverage"
	@echo ""
	@echo "  ClickHouse Migrations:"
	@echo "    make admin-clickhouse-migrate-status   Check current migration version"
	@echo "    make admin-clickhouse-migrate-history  Show migration history"
	@echo "    make admin-clickhouse-migrate-up       Apply pending migrations"
	@echo "    make admin-clickhouse-migrate-down     Rollback (VERSION=xxx required)"
	@echo ""
	@echo "COMBINED (All Services)"
	@echo "  make up              Start all services (PGSync CDC + Search API + Admin)"
	@echo "  make down            Stop all services"
	@echo "  make logs            View all logs (combined)"
	@echo "  make build           Build all images"
	@echo "  make restart         Restart all services"
	@echo "  make rebuild         Full rebuild + restart"
	@echo ""
	@echo "DEVELOPMENT"
	@echo "  make dev-setup       One-time dev setup (install + admin DB + build)"
	@echo "  make dev-status      Show all services status + port availability"
	@echo ""
	@echo "EXAMPLES:"
	@echo ""
	@echo "  First Time Setup:"
	@echo "    1. make dev-setup              # Install deps + init admin DB"
	@echo "    2. make admin-frontend-dev    # Start frontend dev server"
	@echo "    3. make admin-backend-run     # Start backend (different terminal)"
	@echo "    4. Visit http://localhost:3506"
	@echo ""
	@echo "  Docker Deployment:"
	@echo "    1. make admin-build            # Build images"
	@echo "    2. make admin-up               # Start containers"
	@echo "    3. make admin-logs             # View logs"
	@echo "    4. Visit http://localhost"
	@echo ""
	@echo "  Full Stack (All Services):"
	@echo "    1. make dev-setup              # One-time setup"
	@echo "    2. make build                  # Build all images"
	@echo "    3. make up                     # Start everything"
	@echo "    4. make dev-status             # Check status"
	@echo ""
