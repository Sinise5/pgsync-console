"""
PGSync Plugin: Laporan Denormalizer.

Run via PGSync:
    pgsync --config schema-laporan-plugin.json --verbose

Schema must include:
    "plugins": ["LaporanDenormalize"]

The plugin intercepts WAL changes to `laporan` table and enriches
the document with FK lookup values + child data from laporan_isi,
plus multi-value relations: tembusan, aspek, lampiran, laporan_masuk.
"""

import logging
import os
from pathlib import Path

import psycopg2
import psycopg2.extras

from pgsync.plugin import Plugin

logger = logging.getLogger(__name__)


class LaporanDenormalize(Plugin):
    """Denormalize laporan FK references and child data for PGSync CDC."""

    name = "LaporanDenormalize"

    LOOKUP_TABLES = [
        ("referensi", "id", "nama"),
        ('"user"', "id", "nama"),
        ("pelapor", "id", "nama"),
        ("satuan_kerja", "group_ptr_id", "deskripsi"),
        ("neraca_penilaian_kebenaran", "id", "nama"),
        ("neraca_penilaian_kepercayaan", "id", "nama"),
        ("lokasi", "id", "nama"),
    ]

    FK_MAP = {
        "jenis_id":         ("referensi", "jenis"),
        "klasifikasi_id":   ("referensi", "klasifikasi"),
        "urgensi_id":       ("referensi", "urgensi"),
        "created_by_id":    ('"user"', "created_by"),
        "updated_by_id":    ('"user"', "updated_by"),
        "pelapor_id":       ("pelapor", "pelapor"),
        "tujuan_id":        ("satuan_kerja", "tujuan"),
        "satuan_kerja_id":  ("satuan_kerja", "satuan_kerja"),
        "neraca_kebenaran_id":  ("neraca_penilaian_kebenaran", "neraca_kebenaran"),
        "neraca_kepercayaan_id": ("neraca_penilaian_kepercayaan", "neraca_kepercayaan"),
    }

    def __init__(self):
        super().__init__()
        self._caches = {}
        self._pg_conn = None

    def _get_pg_conn(self):
        if self._pg_conn is None or self._pg_conn.closed:
            pg_host = os.environ.get("PG_HOST", "localhost")
            pg_port = int(os.environ.get("PG_PORT", "5432"))
            pg_user = os.environ.get("PG_USER", "postgres")
            pg_pass = os.environ.get("PG_PASSWORD", "")
            pg_db = os.environ.get("PG_DATABASE", "example_db")
            if not pg_pass:
                raise RuntimeError("Set PG_PASSWORD before using LaporanDenormalize")
            self._pg_conn = psycopg2.connect(
                host=pg_host, port=pg_port, user=pg_user,
                password=pg_pass, dbname=pg_db, connect_timeout=5
            )
        return self._pg_conn

    def _ensure_cache(self, table, id_col, name_col):
        if table in self._caches:
            return
        conn = self._get_pg_conn()
        cur = conn.cursor()
        cur.execute(f"SELECT {id_col}, {name_col} FROM {table}")
        self._caches[table] = {row[0]: row[1] for row in cur.fetchall()}
        cur.close()
        logger.debug(f"Loaded {table}: {len(self._caches[table])} rows")

    def _resolve_fk(self, fk_val, table_key):
        if fk_val is None:
            return None
        cache = self._caches.get(table_key)
        return {"id": fk_val, "nama": cache.get(fk_val)} if cache else None

    def _fetch_isi(self, laporan_id):
        """Fetch laporan_isi + attached tokoh."""
        try:
            conn = self._get_pg_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Fetch isi entries
            cur.execute(
                "SELECT id, isi, apa, mengapa, bagaimana, kapan, lokasi_id "
                "FROM laporan_isi WHERE laporan_id = %s",
                (laporan_id,)
            )
            rows = cur.fetchall()

            # Fetch tokoh per isi
            isi_ids = [r["id"] for r in rows]
            tokoh_by_isi = {}
            if isi_ids:
                cur.execute(
                    "SELECT lit.isi_id, t.id, t.nama "
                    "FROM laporan_isi_tokoh lit "
                    "JOIN tokoh t ON t.id = lit.tokoh_id "
                    "WHERE lit.isi_id = ANY(%s)",
                    (isi_ids,)
                )
                for row in cur.fetchall():
                    isi_id = row[0]
                    tokoh_by_isi.setdefault(isi_id, []).append(
                        {"id": row[1], "nama": row[2]}
                    )

            cur.close()

            result = []
            for r in rows:
                item = {
                    "isi": r.get("isi"),
                    "apa": r.get("apa"),
                    "mengapa": r.get("mengapa"),
                    "bagaimana": r.get("bagaimana"),
                    "kapan": str(r["kapan"]).replace(" ", "T", 1) if r.get("kapan") else None,
                }
                if r.get("lokasi_id"):
                    item["lokasi"] = self._resolve_fk(r["lokasi_id"], "lokasi")
                tokoh = tokoh_by_isi.get(r["id"], [])
                if tokoh:
                    item["tokoh"] = tokoh
                result.append(item)
            return result
        except Exception as e:
            logger.warning(f"Failed to fetch laporan_isi for id={laporan_id}: {e}")
            return []

    def _fetch_tembusan(self, laporan_id):
        """Fetch tembusan through laporan_tembusan → satuan_kerja."""
        try:
            conn = self._get_pg_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT sk.group_ptr_id AS id, sk.deskripsi AS nama "
                "FROM laporan_tembusan lt "
                "JOIN satuan_kerja sk ON sk.group_ptr_id = lt.satuankerja_id "
                "WHERE lt.laporan_id = %s",
                (laporan_id,)
            )
            rows = [{"id": r["id"], "nama": r["nama"]} for r in cur.fetchall()]
            cur.close()
            return rows if rows else None
        except Exception as e:
            logger.warning(f"Failed to fetch tembusan for id={laporan_id}: {e}")
            return None

    def _fetch_aspek(self, laporan_id):
        """Fetch aspek through laporan_aspek → referensi."""
        try:
            conn = self._get_pg_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT r.id, r.nama "
                "FROM laporan_aspek la "
                "JOIN referensi r ON r.id = la.referensi_id "
                "WHERE la.laporan_id = %s",
                (laporan_id,)
            )
            rows = [{"id": r["id"], "nama": r["nama"]} for r in cur.fetchall()]
            cur.close()
            return rows if rows else None
        except Exception as e:
            logger.warning(f"Failed to fetch aspek for id={laporan_id}: {e}")
            return None

    def _fetch_lampiran(self, laporan_id):
        """Fetch lampiran files."""
        try:
            conn = self._get_pg_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT id, jenis, file, catatan, realfile, created_date "
                "FROM laporan_lampiran WHERE laporan_id = %s",
                (laporan_id,)
            )
            rows = []
            for r in cur.fetchall():
                item = {"id": r["id"], "jenis": r.get("jenis"), "file": r.get("file")}
                if r.get("catatan"):
                    item["catatan"] = r["catatan"]
                if r.get("realfile"):
                    item["realfile"] = r["realfile"]
                if r.get("created_date"):
                    item["created_date"] = str(r["created_date"])
                rows.append(item)
            cur.close()
            return rows if rows else None
        except Exception as e:
            logger.warning(f"Failed to fetch lampiran for id={laporan_id}: {e}")
            return None

    def _fetch_laporan_masuk(self, laporan_id):
        """Fetch laporan_masuk with satuan_kerja denormalized."""
        try:
            conn = self._get_pg_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT lm.id, sk.group_ptr_id AS sk_id, sk.deskripsi AS sk_nama "
                "FROM laporan_masuk lm "
                "JOIN satuan_kerja sk ON sk.group_ptr_id = lm.satuan_kerja_id "
                "WHERE lm.laporan_id = %s",
                (laporan_id,)
            )
            rows = []
            for r in cur.fetchall():
                rows.append({
                    "id": r["id"],
                    "satuan_kerja": {"id": r["sk_id"], "nama": r["sk_nama"]}
                })
            cur.close()
            return rows if rows else None
        except Exception as e:
            logger.warning(f"Failed to fetch laporan_masuk for id={laporan_id}: {e}")
            return None

    def transform(self, doc, **kwargs):
        """Enrich laporan doc with FK values + child data."""
        if not doc or "id" not in doc:
            return doc

        # Ensure all lookup caches are loaded
        for table, id_col, name_col in self.LOOKUP_TABLES:
            self._ensure_cache(table, id_col, name_col)

        # Resolve FK fields → {id, nama}
        for fk_col, (table_key, output_key) in self.FK_MAP.items():
            if fk_col in doc:
                doc[output_key] = self._resolve_fk(doc[fk_col], table_key)
            else:
                doc[output_key] = None

        laporan_id = doc.get("id")
        if not laporan_id:
            doc["isi_list"] = []
            return doc

        # Fetch all child relations
        doc["isi_list"] = self._fetch_isi(laporan_id)
        doc["tembusan"] = self._fetch_tembusan(laporan_id)
        doc["aspek"] = self._fetch_aspek(laporan_id)
        doc["lampiran"] = self._fetch_lampiran(laporan_id)
        doc["laporan_masuk"] = self._fetch_laporan_masuk(laporan_id)

        return doc
