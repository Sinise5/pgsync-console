#!/bin/sh
# Patch PGSync 7.0.5 untuk kompatibilitas PostgreSQL 15 + wal2json
#
# Root Cause (solved):
#   - PGSync 7.0.5 hardcode PLUGIN="test_decoding" di constants.py
#   - sync.py hardcode options={"include-xids":"1","skip-empty-xacts":"1"}
#   - Opsi-opsi itu hanya valid untuk test_decoding
#   - pgoutput tidak support options itu DAN outputnya binary (UnicodeDecodeError)
#   - wal2json: text-based JSON output, kompatibel dengan parser PGSync
#
# Solution:
#   1. constants.py: PLUGIN = "test_decoding" -> PLUGIN = "wal2json"
#   2. sync.py: hapus options dict (wal2json tidak butuh include-xids/skip-empty-xacts)
#   3. sync.py: update log message
#
# Requirements:
#   - PostgreSQL 15 dengan extension wal2json installed
#   - Replication slot dibuat dengan plugin 'wal2json'
#
set -e

PGSYNC_DIR=$(python3 -c "import pgsync.constants; import os; print(os.path.dirname(pgsync.constants.__file__))" 2>/dev/null)
if [ -z "$PGSYNC_DIR" ]; then
    PGSYNC_DIR="/usr/local/lib/python3.12/site-packages/pgsync"
fi

echo "=========================================="
echo "Patching PGSync 7.0.5 for wal2json"
echo "PGSYNC_DIR=$PGSYNC_DIR"
echo "=========================================="

CONSTANTS="$PGSYNC_DIR/constants.py"
SYNC_PY="$PGSYNC_DIR/sync.py"

#
# Step 1: Change PLUGIN constant to wal2json
#
if grep -q 'PLUGIN = "test_decoding"' "$CONSTANTS"; then
    sed -i 's/PLUGIN = "test_decoding"/PLUGIN = "wal2json"/' "$CONSTANTS"
    echo "[OK] constants.py: PLUGIN -> wal2json"
elif grep -q 'PLUGIN = "pgoutput"' "$CONSTANTS"; then
    sed -i 's/PLUGIN = "pgoutput"/PLUGIN = "wal2json"/' "$CONSTANTS"
    echo "[OK] constants.py: PLUGIN -> wal2json (from pgoutput)"
elif grep -q 'PLUGIN = "wal2json"' "$CONSTANTS"; then
    echo "[SKIP] constants.py: already wal2json"
else
    echo "[WARN] constants.py: PLUGIN pattern not found"
fi

#
# Step 2: Remove test_decoding/pgoutput-specific options from sync.py
#
# wal2json tidak butuh options apapun — output JSON sudah self-describing
# Hapus baris yang punya options={...} untuk menghindari error
#
if grep -q 'include-xids' "$SYNC_PY" || grep -q 'proto_version' "$SYNC_PY"; then
    # Hapus baris options={...} apapun bentuknya
    sed -i '/options={/,/}/d' "$SYNC_PY"
    echo "[OK] sync.py: removed plugin-specific options"
else
    echo "[SKIP] sync.py: options already removed"
fi

#
# Step 3: Update log message
#
if grep -q 'test_decoding' "$SYNC_PY"; then
    sed -i 's/Starting logical replication stream (test_decoding).../Starting logical replication stream (wal2json).../' "$SYNC_PY"
    echo "[OK] sync.py: updated log message"
elif grep -q 'pgoutput' "$SYNC_PY"; then
    sed -i 's/Starting logical replication stream (pgoutput).../Starting logical replication stream (wal2json).../' "$SYNC_PY"
    echo "[OK] sync.py: updated log message (from pgoutput)"
else
    echo "[SKIP] sync.py: log message already updated"
fi

#
# Step 4: Verification
#
echo ""
echo "========== VERIFICATION =========="
echo "--- constants.py ---"
grep -n "PLUGIN" "$CONSTANTS" | head -3

echo ""
echo "--- sync.py (start_replication call) ---"
grep -A 4 "def wal_consumer" "$SYNC_PY" | tail -5 || grep -B 2 -A 2 "start_replication" "$SYNC_PY" | head -6

echo ""
echo "==================================="
echo "Patch complete - wal2json ready"
echo "==================================="
