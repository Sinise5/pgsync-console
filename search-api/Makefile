# Search API - Local Makefile
# =============================
# This Makefile is for search-api-specific commands.
# For workspace-wide commands, use root Makefile: cd .. && make <target>

.PHONY: run test-health test-search docker-build docker-up docker-down docker-logs

# Run locally (dev mode with auto-reload)
# Requires: uv sync from root first
run:
	@echo "=== Running Search API on http://localhost:8080 ==="
	uv run uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# Health check
test-health:
	@echo "=== Testing health (10 iterations) ==="
	@for i in $$(seq 1 10); do \
		echo -n "[$$i/10] "; \
		curl -sf http://localhost:8080/health > /dev/null && echo "OK" || echo "FAIL"; \
		sleep 1; \
	done

# Search test
test-search:
	@echo "=== Testing search API ==="
	@curl -s "http://localhost:8080/search?q=antam&size=5" | jq '.total, .page, .size'

# Build Docker image
docker-build:
	docker build -t laporan-search-api .

# Start container
docker-up:
	docker-compose --env-file ../.env up -d --build
	docker-compose --env-file ../.env ps

# Stop container
docker-down:
	docker-compose --env-file ../.env down

# View logs
docker-logs:
	docker logs laporan-search-api -f

help:
	@echo "Search API - Local Makefile"
	@echo "==========================="
	@echo ""
	@echo "LOCAL"
	@echo "  make run           Run dev server (auto-reload)"
	@echo "  make test-health   Health check test"
	@echo "  make test-search   Search endpoint test"
	@echo ""
	@echo "DOCKER"
	@echo "  make docker-build  Build image"
	@echo "  make docker-up     Start container (port 18080)"
	@echo "  make docker-down   Stop container"
	@echo "  make docker-logs   View logs"
	@echo ""
	@echo "WORKSPACE COMMANDS (from root):"
	@echo "  cd .. && make search-run"
	@echo "  cd .. && make search-build"
	@echo "  cd .. && make search-up"
	@echo ""
