#!/bin/bash
# Create/Recreate laporan index in OpenSearch with full mapping
# Usage: source .env.laporan-dev && bash scripts/create-index.sh

set -euo pipefail

: "${ELASTICSEARCH_HOST:=localhost}"
: "${ELASTICSEARCH_PORT:=9200}"
: "${ELASTICSEARCH_USER:=admin}"
: "${ELASTICSEARCH_PASSWORD:?Set ELASTICSEARCH_PASSWORD before running this script}"
: "${ELASTICSEARCH_VERIFY_CERTS:=true}"

URL="https://${ELASTICSEARCH_HOST}:${ELASTICSEARCH_PORT}"
CURL_TLS=(-sS)
if [[ "${ELASTICSEARCH_VERIFY_CERTS,,}" != "true" ]]; then
  CURL_TLS+=(-k)
fi
SCHEMA_FILE="${SCHEMA_FILE:-config/schema-laporan.json}"

echo "=== Delete index laporan (if exists) ==="
curl "${CURL_TLS[@]}" -u "${ELASTICSEARCH_USER}:${ELASTICSEARCH_PASSWORD}" -X DELETE "$URL/laporan" -H 'Content-Type: application/json' || true

echo ""
echo "=== Create index laporan from ${SCHEMA_FILE} ==="
curl "${CURL_TLS[@]}" -u "${ELASTICSEARCH_USER}:${ELASTICSEARCH_PASSWORD}" -X PUT "$URL/laporan" -H 'Content-Type: application/json' -d "$(cat "$SCHEMA_FILE")"

echo ""
echo "=== Verify ==="
curl "${CURL_TLS[@]}" -u "${ELASTICSEARCH_USER}:${ELASTICSEARCH_PASSWORD}" "$URL/laporan" -H 'Content-Type: application/json' | python3 -m json.tool
