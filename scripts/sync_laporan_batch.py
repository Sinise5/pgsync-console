#!/usr/bin/env python3
"""
Sync laporan batch per bulan — PostgreSQL → OpenSearch.
Denormalize semua FK, {id, nama} format, plus relasi:
  - tembusan (through laporan_tembusan → satuan_kerja)
  - aspek (through laporan_aspek → referensi)
  - lampiran (direct child laporan_lampiran)
  - laporan_masuk (direct child)
  - isi_list + tokoh (through laporan_isi_tokoh → tokoh)

Usage:
  # Sync 1 month
  ./scripts/sync_laporan_batch.py --month 2025-01

  # Sync range
  ./scripts/sync_laporan_batch.py --from 2024-01 --to 2025-01

  # Sync all months (default)
  ./scripts/sync_laporan_batch.py --all

  # Sync N rows test
  ./scripts/sync_laporan_batch.py --limit 100

  # Resume from checkpoint
  ./scripts/sync_laporan_batch.py --resume
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2
import psycopg2.extras
from opensearchpy import OpenSearch, helpers

# === Auto-load .env (priority: .env.laporan-dev > laporan/.env > .env) ===
for candidate in [".env.laporan-dev", "laporan/.env", ".env"]:
    env_path = Path(__file__).resolve().parent.parent / candidate
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            # Only set if not already in environment (allow bash exports)
            os.environ.setdefault(key.strip(), val.strip())
        break  # Use first found

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
OS_INDEX = os.environ.get("ELASTICSEARCH_INDEX", "laporan")

PAGE_SIZE = 5000

# === Checkpoint ===
CHECKPOINT_FILE = "/tmp/laporan-sync-checkpoint.txt"

def save_checkpoint(month_str):
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(month_str.strip() + "\n")

def load_checkpoint():
    try:
        return Path(CHECKPOINT_FILE).read_text().strip()
    except (FileNotFoundError, OSError):
        return None

def clear_checkpoint():
    try:
        os.remove(CHECKPOINT_FILE)
    except OSError:
        pass

# === Date helpers ===
def parse_month(s):
    if not s:
        return None
    parts = s.strip().split("-")
    if len(parts) == 2:
        return datetime(int(parts[0]), int(parts[1]), 1)
    return datetime.fromisoformat(s.strip())

def month_start(d):
    return d.replace(day=1)

def next_month(d):
    if d.month == 12:
        return datetime(d.year + 1, 1, 1)
    return datetime(d.year, d.month + 1, 1)

def iter_months(from_d, to_d):
    cur = month_start(from_d)
    end = month_start(to_d) if to_d else month_start(from_d) + timedelta(days=32)
    while cur < end:
        nxt = next_month(cur)
        yield cur, nxt
        cur = nxt

# === Connect PG ===
def pg_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, user=PG_USER,
        password=PG_PASSWORD, dbname=PG_DB, connect_timeout=10
    )

# === Connect OS ===
def os_client():
    return OpenSearch(
        hosts=[{"host": OS_HOST, "port": OS_PORT, "scheme": "https"}],
        http_auth=(OS_USER, OS_PASSWORD),
        use_ssl=True,
        verify_certs=os.environ.get("ELASTICSEARCH_VERIFY_CERTS", "true").lower() == "true",
        timeout=120,
        max_retries=5,
        retry_on_timeout=True,
    )

# === Lookup caches ===
def build_lookup_cache(cur, table, id_col="id", name_col="nama"):
    cur.execute(f"SELECT {id_col}, {name_col} FROM {table}")
    return {row[0]: row[1] for row in cur.fetchall()}

def build_lokasi_cache(cur):
    cur.execute("SELECT id, nama FROM lokasi")
    return {row[0]: row[1] for row in cur.fetchall()}

# === Date serialization ===
def serialize_pg_date(val):
    if val is None:
        return None
    s = str(val).strip()
    s = s.replace(" ", "T", 1)
    return s

# === Query columns ===
SEL_COLS = """
    l.id, l.nomor, l.judul, l.narasi, l.catatan, l.komentar,
    l.status, l.approve, l.tanggal_laporan,
    l.created_date, l.updated_date,
    l.unique_id, l.status_pengajuan_penghapusan,
    l.created_by_id, l.updated_by_id,
    l.jenis_id, l.klasifikasi_id, l.urgensi_id,
    l.pelapor_id, l.tujuan_id, l.satuan_kerja_id,
    l.neraca_kebenaran_id, l.neraca_kepercayaan_id
"""

def sync_month(client, cur, ref_cache, user_cache, pelapor_cache,
                satker_cache, kebenaran_cache, kepercayaan_cache,
                lokasi_cache, month_start_d, month_end_d,
                total_limit=None, silent=False):
    total_synced = 0
    total_errors = 0
    offset = 0

    while True:
        page_limit = PAGE_SIZE
        if total_limit is not None:
            remaining = total_limit - total_synced
            if remaining <= 0:
                break
            page_limit = min(PAGE_SIZE, remaining)

        cur.execute(f"""
            SELECT {SEL_COLS}
            FROM laporan l
            WHERE l.tanggal_laporan >= %s AND l.tanggal_laporan < %s
            ORDER BY l.id
            LIMIT %s OFFSET %s
        """, (month_start_d, month_end_d, page_limit, offset))
        rows = cur.fetchall()
        if not rows:
            break

        laporan_ids = [r["id"] for r in rows]

        # === Batch fetch child/bridge data ===
        # laporan_isi (include li.id for tokoh linking)
        isi_rows = {}
        isi_id_map = {}  # isi_id -> laporan_id
        cur.execute("""
            SELECT li.id, li.laporan_id, li.isi, li.apa, li.mengapa,
                   li.bagaimana, li.kapan, li.lokasi_id
            FROM laporan_isi li
            WHERE li.laporan_id = ANY(%s)
            ORDER BY li.id
        """, (laporan_ids,))
        for r in cur.fetchall():
            lid = r["laporan_id"]
            iid = r["id"]
            if lid not in isi_rows:
                isi_rows[lid] = []
            isi_rows[lid].append({
                "id": iid,
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
            isi_id_map[iid] = lid

        # tokoh per isi
        tokoh_by_isi = {}
        if isi_id_map:
            isi_ids_list = list(isi_id_map.keys())
            cur.execute("""
                SELECT lit.isi_id, t.id AS tokoh_id, t.nama AS tokoh_nama
                FROM laporan_isi_tokoh lit
                JOIN tokoh t ON t.id = lit.tokoh_id
                WHERE lit.isi_id = ANY(%s)
            """, (isi_ids_list,))
            for r in cur.fetchall():
                iid = r["isi_id"]
                if iid not in tokoh_by_isi:
                    tokoh_by_isi[iid] = []
                tokoh_by_isi[iid].append({
                    "id": r["tokoh_id"],
                    "nama": r["tokoh_nama"],
                })

        # Attach tokoh to isi entries
        isi_by_laporan = {}
        for lid, entries in isi_rows.items():
            for e in entries:
                e["tokoh"] = tokoh_by_isi.get(e["id"], [])
                del e["id"]  # Remove internal id from final doc
            isi_by_laporan[lid] = entries

        # tembusan (through laporan_tembusan -> satuan_kerja)
        tembusan_by_laporan = {}
        cur.execute("""
            SELECT lt.laporan_id, sk.group_ptr_id AS id, sk.deskripsi AS nama
            FROM laporan_tembusan lt
            JOIN satuan_kerja sk ON sk.group_ptr_id = lt.satuankerja_id
            WHERE lt.laporan_id = ANY(%s)
        """, (laporan_ids,))
        for r in cur.fetchall():
            lid = r["laporan_id"]
            if lid not in tembusan_by_laporan:
                tembusan_by_laporan[lid] = []
            tembusan_by_laporan[lid].append({
                "id": r["id"],
                "nama": r["nama"],
            })

        # aspek (through laporan_aspek -> referensi)
        aspek_by_laporan = {}
        cur.execute("""
            SELECT la.laporan_id, r.id, r.nama
            FROM laporan_aspek la
            JOIN referensi r ON r.id = la.referensi_id
            WHERE la.laporan_id = ANY(%s)
        """, (laporan_ids,))
        for r in cur.fetchall():
            lid = r["laporan_id"]
            if lid not in aspek_by_laporan:
                aspek_by_laporan[lid] = []
            aspek_by_laporan[lid].append({
                "id": r["id"],
                "nama": r["nama"],
            })

        # lampiran (direct child laporan_lampiran)
        lampiran_by_laporan = {}
        cur.execute("""
            SELECT id, laporan_id, jenis, file, catatan, realfile, created_date
            FROM laporan_lampiran
            WHERE laporan_id = ANY(%s)
        """, (laporan_ids,))
        for r in cur.fetchall():
            lid = r["laporan_id"]
            if lid not in lampiran_by_laporan:
                lampiran_by_laporan[lid] = []
            lampiran_by_laporan[lid].append({
                "id": r["id"],
                "jenis": r.get("jenis"),
                "file": r.get("file"),
                "catatan": r.get("catatan"),
                "realfile": r.get("realfile"),
                "created_date": serialize_pg_date(r.get("created_date")),
            })

        # laporan_masuk (direct child)
        laporan_masuk_by_laporan = {}
        cur.execute("""
            SELECT lm.id, lm.laporan_id,
                   sk.group_ptr_id AS satuan_kerja_id,
                   sk.deskripsi AS satuan_kerja_nama
            FROM laporan_masuk lm
            JOIN satuan_kerja sk ON sk.group_ptr_id = lm.satuan_kerja_id
            WHERE lm.laporan_id = ANY(%s)
        """, (laporan_ids,))
        for r in cur.fetchall():
            lid = r["laporan_id"]
            if lid not in laporan_masuk_by_laporan:
                laporan_masuk_by_laporan[lid] = []
            laporan_masuk_by_laporan[lid].append({
                "id": r["id"],
                "satuan_kerja": {
                    "id": r["satuan_kerja_id"],
                    "nama": r["satuan_kerja_nama"],
                } if r.get("satuan_kerja_id") else None,
            })

        # Build docs
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
                    "jenis": {"id": r["jenis_id"], "nama": ref_cache.get(r["jenis_id"])} if r.get("jenis_id") else None,
                    "klasifikasi": {"id": r["klasifikasi_id"], "nama": ref_cache.get(r["klasifikasi_id"])} if r.get("klasifikasi_id") else None,
                    "urgensi": {"id": r["urgensi_id"], "nama": ref_cache.get(r["urgensi_id"])} if r.get("urgensi_id") else None,
                    "created_by": {"id": r["created_by_id"], "nama": user_cache.get(r["created_by_id"])} if r.get("created_by_id") else None,
                    "updated_by": {"id": r["updated_by_id"], "nama": user_cache.get(r["updated_by_id"])} if r.get("updated_by_id") else None,
                    "pelapor": {"id": r["pelapor_id"], "nama": pelapor_cache.get(r["pelapor_id"])} if r.get("pelapor_id") else None,
                    "tujuan": {"id": r["tujuan_id"], "nama": satker_cache.get(r["tujuan_id"])} if r.get("tujuan_id") else None,
                    "satuan_kerja": {"id": r["satuan_kerja_id"], "nama": satker_cache.get(r["satuan_kerja_id"])} if r.get("satuan_kerja_id") else None,
                    "neraca_kebenaran": {"id": r["neraca_kebenaran_id"], "nama": kebenaran_cache.get(r["neraca_kebenaran_id"])} if r.get("neraca_kebenaran_id") else None,
                    "neraca_kepercayaan": {"id": r["neraca_kepercayaan_id"], "nama": kepercayaan_cache.get(r["neraca_kepercayaan_id"])} if r.get("neraca_kepercayaan_id") else None,

                    # New relasi
                    "tembusan": tembusan_by_laporan.get(doc_id, []),
                    "aspek": aspek_by_laporan.get(doc_id, []),
                    "lampiran": lampiran_by_laporan.get(doc_id, []),
                    "laporan_masuk": laporan_masuk_by_laporan.get(doc_id, []),

                    # isi_list with tokoh
                    "isi_list": isi_by_laporan.get(doc_id, []),
                }
            }
            docs.append(doc)

        # Bulk
        success, errors = helpers.bulk(client, docs, raise_on_error=False)
        total_synced += success
        total_errors += len(errors) if errors else 0
        offset += len(rows)

        if not silent:
            print(f"  offset={offset} synced={total_synced} errors={total_errors}", file=sys.stderr, flush=True)

        if total_limit is not None and total_synced >= total_limit:
            break

    return total_synced, total_errors


# === Main ===
def main():
    parser = argparse.ArgumentParser(description="Sync laporan batch")
    parser.add_argument("--month", help="Single month YYYY-MM")
    parser.add_argument("--from", dest="from_d", help="Start month YYYY-MM")
    parser.add_argument("--to", dest="to_d", help="End month YYYY-MM (exclusive)")
    parser.add_argument("--all", action="store_true", help="Sync all months")
    parser.add_argument("--limit", type=int, help="Max docs to sync (for testing)")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--resume-from", help="Resume from specific month")
    parser.add_argument("--silent", action="store_true", help="Minimal output")
    args = parser.parse_args()

    silent = args.silent

    # Determine date range
    from_dt = to_dt = None

    if args.month:
        from_dt = parse_month(args.month)
        to_dt = next_month(from_dt)
    elif args.from_d:
        from_dt = parse_month(args.from_d)
        to_dt = parse_month(args.to_d) if args.to_d else None
    elif args.resume:
        checkpoint = load_checkpoint()
        if checkpoint:
            from_dt = next_month(parse_month(checkpoint))
        else:
            print("No checkpoint found. Use --resume-from or --from.", file=sys.stderr)
            sys.exit(1)
    elif args.resume_from:
        from_dt = parse_month(args.resume_from)
    else:
        # Default: all months
        from_dt = datetime(2001, 1, 1)
        to_dt = datetime(2026, 6, 1)

    if not silent:
        print(f"Range: {from_dt.strftime('%Y-%m-%d')} → {to_dt.strftime('%Y-%m-%d') if to_dt else 'now'}")

    # PG connection for caches
    conn = pg_conn()
    cur_plain = conn.cursor()

    # Build lookup caches
    if not silent:
        print("Building lookup caches...", file=sys.stderr, flush=True)
    ref_cache = build_lookup_cache(cur_plain, "referensi")
    user_cache = build_lookup_cache(cur_plain, '"user"')
    pelapor_cache = build_lookup_cache(cur_plain, "pelapor")
    satker_cache = build_lookup_cache(cur_plain, "satuan_kerja", id_col="group_ptr_id", name_col="deskripsi")
    kebenaran_cache = build_lookup_cache(cur_plain, "neraca_penilaian_kebenaran")
    kepercayaan_cache = build_lookup_cache(cur_plain, "neraca_penilaian_kepercayaan")
    lokasi_cache = build_lokasi_cache(cur_plain)
    cur_plain.close()

    if not silent:
        print(f"  caches: ref={len(ref_cache)} user={len(user_cache)} "
              f"pelapor={len(pelapor_cache)} satker={len(satker_cache)} "
              f"lokasi={len(lokasi_cache)}", file=sys.stderr, flush=True)

    # OpenSearch client
    client = os_client()

    # Iterate months
    total_all = 0
    error_all = 0
    month_count = 0

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    for m_start, m_end in iter_months(from_dt, to_dt):
        if args.limit and total_all >= args.limit:
            break

        # Count rows in this month
        cur.execute("SELECT count(*) FROM laporan WHERE tanggal_laporan >= %s AND tanggal_laporan < %s",
                     (m_start, m_end))
        month_total = cur.fetchone()["count"]

        if month_total == 0:
            continue

        if not silent:
            print(f"\n[{m_start.strftime('%Y-%m')}] rows={month_total}", file=sys.stderr, flush=True)

        synced, errors = sync_month(
            client, cur,
            ref_cache, user_cache, pelapor_cache,
            satker_cache, kebenaran_cache, kepercayaan_cache,
            lokasi_cache,
            m_start, m_end,
            total_limit=args.limit,
            silent=silent,
        )
        total_all += synced
        error_all += errors
        month_count += 1

        if not silent:
            elapsed = 0  # rough
            rate = synced / (time.time() - (time.time() - 1)) if synced > 0 else 0
            print(f"  [{m_start.strftime('%Y-%m')}] done: {synced} docs "
                  f"in {elapsed:.1f}s ({rate:.0f} docs/s)",
                  file=sys.stderr, flush=True)

        # Save checkpoint after each month
        save_checkpoint(m_start.strftime("%Y-%m"))

        if args.limit and total_all >= args.limit:
            break

    conn.close()
    total_os = client.count(index=OS_INDEX)["count"]

    # Clear checkpoint on successful completion
    clear_checkpoint()

    print(f"\nSTATUS: {month_count} months, {total_all} docs synced, "
          f"{error_all} errors. OS index: {total_os} total docs")


if __name__ == "__main__":
    main()
