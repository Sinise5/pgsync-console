#!/usr/bin/env python3
"""Get FK constraints (deduped) + row counts + sample data."""
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

# FK constraints deduped
cur.execute("""
    SELECT DISTINCT
        tc.table_name,
        kcu.column_name,
        ccu.table_name AS ref_table,
        ccu.column_name AS ref_column
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public'
      AND tc.table_name IN ('laporan','laporan_isi')
    ORDER BY tc.table_name, kcu.column_name
""")
print("=== FK Constraints ===")
for r in cur.fetchall():
    print(f"  {r[0]}.{r[1]} -> {r[2]}.{r[3]}")

# Row counts
for tbl in ['laporan', 'laporan_isi', 'laporan_isi_tokoh', 'laporan_isi_lampiran']:
    cur.execute(f"SELECT count(*) FROM {tbl}")
    print(f"\n  {tbl}: {cur.fetchone()[0]} rows")

# Sample laporan (1 row)
cur.execute("SELECT * FROM laporan LIMIT 1")
cols = [d[0] for d in cur.description]
row = cur.fetchone()
print(f"\n=== Sample laporan ({len(cols)} cols) ===")
for c, v in zip(cols, row):
    val = str(v)[:80] if v else "NULL"
    print(f"  {c:30s} = {val}")

# Sample laporan_isi (3 rows for that laporan)
if row:
    lid = row[0]
    cur.execute("SELECT * FROM laporan_isi WHERE laporan_id=%s LIMIT 3", (lid,))
    ic = [d[0] for d in cur.description]
    rows = cur.fetchall()
    print(f"\n=== Sample laporan_isi (for laporan_id={lid}) ===")
    for r in rows:
        for c, v in zip(ic, r):
            val = str(v)[:60] if v else "NULL"
            print(f"  {c:25s} = {val}")
        print("  ---")

conn.close()
