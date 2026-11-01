#!/bin/bash
# Migration Script: pgoutput -> wal2json
# Target: PostgreSQL 15.14 @ localhost:5432/example_db
# PGSync: 7.0.5

set -e
source .env

echo "=== MIGRASI PGSync: pgoutput -> wal2json ==="

# Step 1: Audit
echo ""
echo "[1/8] Audit PostgreSQL"
docker run --rm --network host postgres:16 psql \
  "host=localhost dbname=example_db user=postgres password=$PG_PASSWORD" \
  -c "SELECT version(); SELECT name,default_version,installed_version
      FROM pg_available_extensions
      WHERE name IN ('wal2json','test_decoding') ORDER BY name;
      SELECT slot_name,plugin,slot_type,database,active
      FROM pg_replication_slots;
      SELECT pubname FROM pg_publication;
      SHOW wal_level;"

# Step 2: Drop old slot
echo ""
echo "[2/8] Drop replication slot lama"
read -p "Drop slot 'pgsync_laporan'? (y/n): " DROP
if [ "$DROP" = "y" ]; then
  docker run --rm --network host postgres:16 psql \
    "host=localhost dbname=example_db user=postgres password=$PG_PASSWORD" \
    -c "SELECT pg_drop_replication_slot('pgsync_laporan');"
  echo "[OK] Slot dropped"
else
  echo "[SKIP]"
fi

# Step 3: Create slot with wal2json
echo ""
echo "[3/8] Create replication slot dengan wal2json"
docker run --rm --network host postgres:16 psql \
  "host=localhost dbname=example_db user=postgres password=$PG_PASSWORD" \
  -c "SELECT * FROM pg_create_logical_replication_slot('pgsync_laporan','wal2json');"

# Step 4: Verify
echo ""
echo "[4/8] Verifikasi slot baru"
docker run --rm --network host postgres:16 psql \
  "host=localhost dbname=example_db user=postgres password=$PG_PASSWORD" \
  -c "SELECT slot_name,plugin,slot_type,active
      FROM pg_replication_slots
      WHERE slot_name='pgsync_laporan';"

# Step 5: Rebuild Docker image
echo ""
echo "[5/8] Rebuild Docker image"
docker compose down
docker build --no-cache -f Dockerfile.base -t pgsync-laporan:base .
docker build --no-cache -t pgsync-laporan:app .

# Step 6: Bootstrap data
echo ""
echo "[6/8] Bootstrap (opsional)"
read -p "Jalankan bootstrap? (y/n): " BS
if [ "$BS" = "y" ]; then
  docker compose --profile bootstrap run laporan-bootstrap
fi

# Step 7: Start CDC
echo ""
echo "[7/8] Start CDC"
docker compose up -d laporan-cdc

# Step 8: Monitor
echo ""
echo "[8/8] Monitor log"
sleep 5
docker logs pgsync-laporan-cdc --tail 50

echo ""
echo "=== MIGRASI SELESAI ==="
echo "Verifikasi:"
echo "  1. docker logs pgsync-laporan-cdc -f"
echo "  2. Insert/Update/Delete test record di PG"
echo "  3. Cek OpenSearch index 'laporan'"
