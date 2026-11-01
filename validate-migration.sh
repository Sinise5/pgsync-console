#!/bin/bash
# Validation Script: wal2json migration verification
# Run setelah migrasi selesai untuk verify semua komponen

set -e
source .env

PASS=0
FAIL=0

echo "============================================="
echo "WAL2JSON MIGRATION VALIDATION"
echo "============================================="
echo ""

# Test 1: Container running
echo "[1/7] Container status"
if docker ps --filter name=pgsync-laporan-cdc --format '{{.Status}}' | grep -q "Up"; then
    echo "✅ Container running"
    ((PASS++))
else
    echo "❌ Container not running or restarting"
    ((FAIL++))
fi
echo ""

# Test 2: Patch applied
echo "[2/7] Patch verification"
if docker exec pgsync-laporan-cdc python3 -c "
import pgsync.constants
if pgsync.constants.PLUGIN == 'wal2json':
    print('✅ PLUGIN = wal2json')
    exit(0)
else:
    print('❌ PLUGIN = ' + pgsync.constants.PLUGIN)
    exit(1)
" 2>/dev/null; then
    ((PASS++))
else
    echo "❌ Patch not applied"
    ((FAIL++))
fi
echo ""

# Test 3: No UnicodeDecodeError in logs
echo "[3/7] Check logs for errors"
if docker logs pgsync-laporan-cdc 2>&1 | grep -q "UnicodeDecodeError"; then
    echo "❌ UnicodeDecodeError found in logs"
    ((FAIL++))
else
    echo "✅ No UnicodeDecodeError"
    ((PASS++))
fi
echo ""

# Test 4: Replication slot exists and active
echo "[4/7] Replication slot"
SLOT_CHECK=$(docker run --rm --network host postgres:16 psql \
  "host=localhost dbname=example_db user=postgres password=$PG_PASSWORD" \
  -t -c "SELECT plugin, active FROM pg_replication_slots WHERE slot_name='pgsync_laporan';" 2>&1)

if echo "$SLOT_CHECK" | grep -q "wal2json"; then
    echo "✅ Slot plugin = wal2json"
    ((PASS++))
else
    echo "❌ Slot plugin bukan wal2json"
    echo "$SLOT_CHECK"
    ((FAIL++))
fi

if echo "$SLOT_CHECK" | grep -q " t$"; then
    echo "✅ Slot active"
else
    echo "⚠️  Slot not active (mungkin baru start)"
fi
echo ""

# Test 5: Container restart count
echo "[5/7] Container stability"
RESTART_COUNT=$(docker inspect pgsync-laporan-cdc --format '{{.RestartCount}}' 2>/dev/null || echo "999")
if [ "$RESTART_COUNT" -lt 3 ]; then
    echo "✅ Restart count: $RESTART_COUNT (healthy)"
    ((PASS++))
else
    echo "❌ Restart count: $RESTART_COUNT (crash loop)"
    ((FAIL++))
fi
echo ""

# Test 6: Log streaming message
echo "[6/7] CDC streaming"
if docker logs pgsync-laporan-cdc 2>&1 | grep -q "Starting logical replication stream"; then
    echo "✅ CDC streaming started"
    ((PASS++))
else
    echo "❌ CDC stream not started"
    ((FAIL++))
fi
echo ""

# Test 7: OpenSearch connectivity
echo "[7/7] OpenSearch connection"
if docker logs pgsync-laporan-cdc 2>&1 | grep -q "Connected to OpenSearch\|Elasticsearch"; then
    echo "✅ OpenSearch connected"
    ((PASS++))
else
    echo "⚠️  OpenSearch connection not confirmed in logs"
fi
echo ""

# Summary
echo "============================================="
echo "VALIDATION SUMMARY"
echo "============================================="
echo "Passed: $PASS"
echo "Failed: $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "✅ MIGRATION SUCCESSFUL"
    echo ""
    echo "Next steps:"
    echo "  1. Monitor logs: docker logs pgsync-laporan-cdc -f"
    echo "  2. Test CDC: INSERT/UPDATE/DELETE record di PostgreSQL"
    echo "  3. Verify OpenSearch: curl -u admin:*** -k https://localhost:9200/laporan/_search"
    exit 0
else
    echo "❌ MIGRATION INCOMPLETE - $FAIL tests failed"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check logs: docker logs pgsync-laporan-cdc --tail 100"
    echo "  2. Check slot: SELECT * FROM pg_replication_slots;"
    echo "  3. Review: cat MIGRATION-WAL2JSON.md"
    exit 1
fi
