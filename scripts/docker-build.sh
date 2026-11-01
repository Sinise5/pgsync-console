#!/usr/bin/env bash
set -euo pipefail

# Docker build helper — PGSync Laporan
# Usage: ./scripts/docker-build.sh [--no-cache]

NO_CACHE=""
if [ "${1:-}" = "--no-cache" ]; then
    NO_CACHE="--no-cache"
fi

echo "=== Step 1/2: Build BASE image (deps) ==="
podman build $NO_CACHE -t pgsync-laporan:base -f Dockerfile.base .

echo ""
echo "=== Step 2/2: Build APP image (code) ==="
podman build $NO_CACHE -t pgsync-laporan:app -f Dockerfile .

echo ""
echo "=== Done ==="
echo "  base: pgsync-laporan:base"
echo "  app:  pgsync-laporan:app"
