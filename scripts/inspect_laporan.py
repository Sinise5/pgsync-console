#!/usr/bin/env python3
"""Inspect laporan-related table structures."""
import os
import psycopg2

password = os.environ.get("PG_PASSWORD")
if not password:
    raise SystemExit("Set PG_PASSWORD before inspecting the database")
conn = psycopg2.connect(
    host=os.environ.get("PG_HOST", "localhost"),
    port=int(os.environ.get("PG_PORT", "5432")),
    user=os.environ.get("PG_USER", "postgres"),
    password=password,
    dbname=os.environ.get("PG_DATABASE", "siitpartisi"),
    connect_timeout=10,
)
cur = conn.cursor()

tables = [
    'laporan', 'laporan_isi', 'laporan_isi_tokoh', 'laporan_isi_lampiran',
    'referensi', 'user', 'pelapor', 'satuan_kerja', 'lokasi', 'tokoh',
    'lampiran', 'neraca_penilaian_kebenaran', 'neraca_penilaian_kepercayaan'
]

for tbl in tables:
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
    """, (tbl,))
    rows = cur.fetchall()
    print(f"\n=== {tbl} ===")
    for col in rows:
        print(f"  {col[0]:30s} {col[1]:20s} nullable={col[2]}")

# Also check FK constraints
cur.execute("""
    SELECT
        tc.table_name,
        kcu.column_name,
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public'
      AND tc.table_name IN ('laporan','laporan_isi','laporan_isi_tokoh','laporan_isi_lampiran')
    ORDER BY tc.table_name, kcu.column_name
""")
print("\n\n=== FK Constraints ===")
for row in cur.fetchall():
    print(f"  {row[0]}.{row[1]} -> {row[2]}.{row[3]}")

# Count rows
for tbl in ['laporan', 'laporan_isi', 'laporan_isi_tokoh', 'laporan_isi_lampiran']:
    cur.execute(f"SELECT count(*) FROM {tbl}")
    cnt = cur.fetchone()[0]
    print(f"  {tbl}: {cnt} rows")

cur.close()
conn.close()
