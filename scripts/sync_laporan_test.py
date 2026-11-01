#!/usr/bin/env python3
"""
PGSync Laporan — Test sync (LIMIT N rows).
Query laporan + JOIN semua FK → denormalized doc → bulk to OpenSearch.

Env: PG_PASSWORD, ELASTICSEARCH_PASSWORD (or auto-read from laporan/.env)
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
from opensearchpy import OpenSearch, helpers

# === Auto-load .env ===
env_path = Path(__file__).resolve().parent.parent / "laporan" / ".env"
if not env_path.exists():
    env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())

# === Config ===
PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_USER = os.environ.get("PG_USER", "postgres")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "")
PG_DB = os.environ.get("PG_DATABASE", "example_db")

OS_HOST = os.environ.get("ELASTICSEARCH_HOST", "localhost")
OS_PORT = int(os.environ.get("ELASTICSEARCH_PORT", "9200"))
OS_USER = os.environ.get("ELASTICSEARCH_USER", "admin")
OS_PASSWORD = os.environ.get("ELASTICSEARCH_PASSWORD", "")
VERIFY_CERTS = os.environ.get("ELASTICSEARCH_VERIFY_CERTS", "true").lower() == "true"
OS_INDEX = os.environ.get("ELASTICSEARCH_INDEX", "laporan")

LIMIT = int(os.environ.get("LIMIT", "100"))
OFFSET = int(os.environ.get("OFFSET", "0"))
SILENT = os.environ.get("SILENT", "")

# === Connect PG ===
def pg_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, user=PG_USER,
        password=PG_PASSWORD, dbname=PG_DB, connect_timeout=10
    )

# === Connect OS ===
os_client = OpenSearch(
    hosts=[{"host": OS_HOST, "port": OS_PORT}],
    http_auth=(OS_USER, OS_PASSWORD),
    use_ssl=True,
    verify_certs=VERIFY_CERTS,
)

# === Lookup caches ===
def build_lookup_cache(cur, table, id_col="id", name_col="nama"):
    cur.execute(f"SELECT {id_col}, {name_col} FROM {table}")
    return {row[0]: row[1] for row in cur.fetchall()}

def build_lokasi_cache(cur):
    cur.execute("SELECT id, nama FROM lokasi")
    return {row[0]: row[1] for row in cur.fetchall()}


# === Date format fix ===
def serialize_pg_date(val):
    """Convert PG timestamp to ISO8601 for OpenSearch."""
    if val is None:
        return None
    s = str(val).strip()
    # PG format: '2018-03-18 00:00:00+07:00' → ISO8601
    s = s.replace(" ", "T", 1)
    # Fix timezone offset: +07:00 → +07:00 (already good), but ensure proper
    return s


# === Main ===
def main():
    conn = pg_conn()

    # Build lookup caches (regular cursor, tuple results)
    if not SILENT:
        print("Loading lookup caches...", file=sys.stderr, flush=True)
    cur_plain = conn.cursor()
    ref_cache = build_lookup_cache(cur_plain, "referensi")
    user_cache = build_lookup_cache(cur_plain, '"user"')
    pelapor_cache = build_lookup_cache(cur_plain, "pelapor")
    satker_cache = build_lookup_cache(cur_plain, "satuan_kerja", id_col="group_ptr_id", name_col="deskripsi")
    kebenaran_cache = build_lookup_cache(cur_plain, "neraca_penilaian_kebenaran")
    kepercayaan_cache = build_lookup_cache(cur_plain, "neraca_penilaian_kepercayaan")
    lokasi_cache = build_lokasi_cache(cur_plain)
    cur_plain.close()

    # Query laporan with RealDictCursor
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if not SILENT:
        print(f"  referenci: {len(ref_cache)}, user: {len(user_cache)}, "
              f"pelapor: {len(pelapor_cache)}, satker: {len(satker_cache)}",
              file=sys.stderr, flush=True)
        print(f"  lokasi: {len(lokasi_cache)}, kebenaran: {len(kebenaran_cache)}, "
              f"kepercayaan: {len(kepercayaan_cache)}",
              file=sys.stderr, flush=True)

    # Query laporan with LIMIT
    if not SILENT:
        print(f"Querying laporan LIMIT {LIMIT} OFFSET {OFFSET}...",
              file=sys.stderr, flush=True)

    cur.execute("""
        SELECT id, nomor, judul, narasi, catatan, komentar,
               status, approve, tanggal_laporan,
               created_date, updated_date,
               unique_id, status_pengajuan_penghapusan,
               created_by_id, updated_by_id,
               jenis_id, klasifikasi_id, urgensi_id,
               pelapor_id, tujuan_id, satuan_kerja_id,
               neraca_kebenaran_id, neraca_kepercayaan_id
        FROM laporan
        ORDER BY id
        LIMIT %s OFFSET %s
    """, (LIMIT, OFFSET))
    rows = cur.fetchall()

    if not SILENT:
        print(f"Got {len(rows)} rows. Fetching laporan_isi...",
              file=sys.stderr, flush=True)

    # Get all laporan IDs
    laporan_ids = [r["id"] for r in rows]

    # Fetch laporan_isi for these IDs
    isi_by_laporan = {}
    if laporan_ids:
        cur.execute("""
            SELECT li.id, li.laporan_id, li.isi, li.apa, li.mengapa,
                   li.bagaimana, li.kapan, li.lokasi_id
            FROM laporan_isi li
            WHERE li.laporan_id = ANY(%s)
        """, (laporan_ids,))
        for r in cur.fetchall():
            lid = r["laporan_id"]
            if lid not in isi_by_laporan:
                isi_by_laporan[lid] = []
            isi_by_laporan[lid].append({
                "isi": r.get("isi"),
                "apa": r.get("apa"),
                "mengapa": r.get("mengapa"),
                "bagaimana": r.get("bagaimana"),
                "kapan": serialize_pg_date(r.get("kapan")),
                "lokasi": {
                    "id": r["lokasi_id"],
                    "nama": lokasi_cache.get(r["lokasi_id"])
                } if r.get("lokasi_id") else None,
            })

    conn.close()

    # Build OpenSearch documents
    docs = []
    for r in rows:
        doc_id = r["id"]
        doc = {
            "_id": str(doc_id),
            "_index": OS_INDEX,
            "_source": {
                "id": doc_id,
                "nomor": r.get("nomor"),
                "judul": r.get("judul"),
                "narasi": r.get("narasi"),
                "catatan": r.get("catatan"),
                "komentar": r.get("komentar"),
                "status": r.get("status"),
                "approve": r.get("approve"),
                "tanggal_laporan": serialize_pg_date(r.get("tanggal_laporan")),
                "created_date": serialize_pg_date(r.get("created_date")),
                "updated_date": serialize_pg_date(r.get("updated_date")),
                "unique_id": r.get("unique_id"),
                "status_pengajuan_penghapusan": r.get("status_pengajuan_penghapusan"),

                # Denormalized FK → {id, nama}
                "jenis": {
                    "id": r["jenis_id"],
                    "nama": ref_cache.get(r["jenis_id"])
                } if r.get("jenis_id") else None,
                "klasifikasi": {
                    "id": r["klasifikasi_id"],
                    "nama": ref_cache.get(r["klasifikasi_id"])
                } if r.get("klasifikasi_id") else None,
                "urgensi": {
                    "id": r["urgensi_id"],
                    "nama": ref_cache.get(r["urgensi_id"])
                } if r.get("urgensi_id") else None,
                "created_by": {
                    "id": r["created_by_id"],
                    "nama": user_cache.get(r["created_by_id"])
                } if r.get("created_by_id") else None,
                "updated_by": {
                    "id": r["updated_by_id"],
                    "nama": user_cache.get(r["updated_by_id"])
                } if r.get("updated_by_id") else None,
                "pelapor": {
                    "id": r["pelapor_id"],
                    "nama": pelapor_cache.get(r["pelapor_id"])
                } if r.get("pelapor_id") else None,
                "tujuan": {
                    "id": r["tujuan_id"],
                    "nama": satker_cache.get(r["tujuan_id"])
                } if r.get("tujuan_id") else None,
                "satuan_kerja": {
                    "id": r["satuan_kerja_id"],
                    "nama": satker_cache.get(r["satuan_kerja_id"])
                } if r.get("satuan_kerja_id") else None,
                "neraca_kebenaran": {
                    "id": r["neraca_kebenaran_id"],
                    "nama": kebenaran_cache.get(r["neraca_kebenaran_id"])
                } if r.get("neraca_kebenaran_id") else None,
                "neraca_kepercayaan": {
                    "id": r["neraca_kepercayaan_id"],
                    "nama": kepercayaan_cache.get(r["neraca_kepercayaan_id"])
                } if r.get("neraca_kepercayaan_id") else None,

                # Nested child
                "isi_list": isi_by_laporan.get(doc_id, []),
            }
        }
        docs.append(doc)

    if not SILENT:
        print(f"Built {len(docs)} documents. Pushing to OpenSearch...",
              file=sys.stderr, flush=True)

    # Delete existing docs if reindexing same IDs
    # (first-run: no cleanup needed)

    # Bulk insert
    success, errors = helpers.bulk(os_client, docs, raise_on_error=False)
    if not SILENT:
        print(f"  Success: {success}, Errors: {len(errors)}",
              file=sys.stderr, flush=True)
    if errors:
        for e in errors[:3]:
            print(f"  Error: {e}", file=sys.stderr, flush=True)

    # Verify count
    count = os_client.count(index=OS_INDEX)
    if not SILENT:
        print(f"Index '{OS_INDEX}' total docs: {count['count']}",
              file=sys.stderr, flush=True)

    # Print sample for verification
    if not SILENT and docs:
        sample = docs[0]["_source"]
        print(f"\n=== Sample doc (id={sample['id']}) ===", file=sys.stderr, flush=True)
        for k in ["id", "nomor", "judul", "narasi", "tanggal_laporan"]:
            v = sample.get(k)
            print(f"  {k}: {str(v)[:80]}", file=sys.stderr, flush=True)
        print(f"  jenis: {sample.get('jenis')}", file=sys.stderr, flush=True)
        print(f"  klasifikasi: {sample.get('klasifikasi')}", file=sys.stderr, flush=True)
        print(f"  isi_list count: {len(sample.get('isi_list', []))}",
              file=sys.stderr, flush=True)

    # Machine-readable summary
    print(f"STATUS:synced {len(docs)} docs, errors: {len(errors)}")

if __name__ == "__main__":
    main()
