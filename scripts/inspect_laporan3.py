#!/usr/bin/env python3
"""Get referensi + referensi type filter + laporan_isi columns + date range."""
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
    dbname=os.environ.get("PG_DATABASE", "example_db"),
    connect_timeout=10,
)
cur = conn.cursor()

# referensi columns
print("=== referensi columns ===")
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='referensi'
    ORDER BY ordinal_position
""")
for r in cur.fetchall():
    print(f"  {r[0]:25s} {r[1]:20s} nullable={r[2]}")

# Check if referensi has category/type field to filter jenis vs klasifikasi vs urgensi
print("\n=== referensi sample (10 rows) ===")
cur.execute("SELECT * FROM referensi LIMIT 10")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    for c, v in zip(cols, r):
        val = str(v)[:50] if v else "NULL"
        print(f"  {c:20s} = {val}")
    print("  ---")

# satuan_kerja columns
print("\n=== satuan_kerja columns ===")
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='satuan_kerja'
    ORDER BY ordinal_position
""")
for r in cur.fetchall():
    print(f"  {r[0]:25s} {r[1]:20s} nullable={r[2]}")

# neraca tables
print("\n=== neraca_penilaian_kebenaran columns ===")
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='neraca_penilaian_kebenaran'
    ORDER BY ordinal_position
""")
for r in cur.fetchall():
    print(f"  {r[0]:25s} {r[1]:20s} nullable={r[2]}")

# laporan_isi full columns
print("\n=== laporan_isi full columns ===")
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='laporan_isi'
    ORDER BY ordinal_position
""")
for r in cur.fetchall():
    print(f"  {r[0]:25s} {r[1]:20s} nullable={r[2]}")

# Date range of laporan
print("\n=== laporan date range ===")
cur.execute("SELECT min(tanggal_laporan), max(tanggal_laporan), count(*) FROM laporan")
r = cur.fetchone()
print(f"  min: {r[0]}, max: {r[1]}, count: {r[2]}")

# pelapor columns
print("\n=== pelapor columns ===")
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='pelapor'
    ORDER BY ordinal_position
""")
for r in cur.fetchall():
    print(f"  {r[0]:25s} {r[1]:20s} nullable={r[2]}")

# Check if laporan has any other text-rich child tables besides laporan_isi
print("\n=== Tables referencing laporan.id ===")
cur.execute("""
    SELECT tc.table_name, kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND ccu.table_name = 'laporan'
      AND ccu.column_name = 'id'
    ORDER BY tc.table_name
""")
for r in cur.fetchall():
    print(f"  {r[0]}.{r[1]}")

conn.close()
