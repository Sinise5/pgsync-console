#!/usr/bin/env python3
"""
Search Laporan — OpenSearch Query Builder.

Fitur:
- Full-text search di judul/narasi/catatan/isi_list
- Multi filter: object FK, scalar, date range, exists
- Nested query untuk isi_list, tembusan, aspek, lampiran, tokoh
- Highlighting, aggregasi, pagination
- Siap import dari FastAPI atau jalan standalone

Usage:
    # Standalone
    python scripts/search_laporan.py --q "keamanan" --jenis-id 8

    # Import
    from scripts.search_laporan import LaporanSearch
    ls = LaporanSearch()
    result = ls.search(q="patroli", jenis_id=8, satuan_kerja_id=286)
"""

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional
from urllib.parse import urljoin

import requests

# ─── Config ──────────────────────────────────────────────────────────────────

OPENSEARCH_HOST = os.environ.get("ELASTICSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.environ.get("ELASTICSEARCH_PORT", "9200"))
OPENSEARCH_USER = os.environ.get("ELASTICSEARCH_USER", "admin")
OPENSEARCH_PASS = os.environ.get("ELASTICSEARCH_PASSWORD", "")
OPENSEARCH_INDEX = os.environ.get("ELASTICSEARCH_INDEX", "laporan")
OPENSEARCH_SCHEME = os.environ.get("ELASTICSEARCH_SCHEME", "https")

BASE_URL = f"{OPENSEARCH_SCHEME}://{OPENSEARCH_HOST}:{OPENSEARCH_PORT}"
SEARCH_URL = urljoin(BASE_URL, f"/{OPENSEARCH_INDEX}/_search")
VERIFY_CERTS = os.environ.get("ELASTICSEARCH_VERIFY_CERTS", "true").lower() == "true"


# ─── Query Builder ───────────────────────────────────────────────────────────


class BoolQuery:
    """Helper untuk membangun OpenSearch bool query secara programatik."""

    def __init__(self):
        self.must = []
        self.filter = []
        self.must_not = []
        self.should = []

    def add_match(self, field: str, query: str, target: str = "must"):
        """Text match sederhana."""
        clause = {"match": {field: query}}
        getattr(self, target).append(clause)

    def add_multi_match(self, query: str, fields: list, target: str = "must",
                        boost_field: Optional[str] = None):
        """Multi-field match dengan optional boost field."""
        if boost_field:
            boosted = [f"{boost_field}^3"] + [f for f in fields if f != boost_field]
            fields = boosted[:5]  # max 5 fields untuk performance
        fields_list = list(dict.fromkeys(fields))  # unique, preserve order

        # Kalau cuma 1 field, fallback ke match biasa
        if len(fields_list) == 1:
            self.add_match(fields_list[0], query, target)
            return

        clause = {"multi_match": {"query": query, "fields": fields_list, "type": "best_fields"}}
        getattr(self, target).append(clause)

    def add_term(self, field: str, value, target: str = "filter"):
        """Exact term match."""
        clause = {"term": {field: value}}
        getattr(self, target).append(clause)

    def add_terms(self, field: str, values: list, target: str = "filter"):
        """Multi-value term match."""
        clause = {"terms": {field: values}}
        getattr(self, target).append(clause)

    def add_range(self, field: str, gte=None, lte=None, target: str = "filter"):
        """Range query."""
        r = {}
        if gte is not None:
            r["gte"] = gte
        if lte is not None:
            r["lte"] = lte
        if r:
            clause = {"range": {field: r}}
            getattr(self, target).append(clause)

    def add_exists(self, field: str, target: str = "filter"):
        """Exists check."""
        clause = {"exists": {"field": field}}
        getattr(self, target).append(clause)

    def add_must_not(self, clause_or_fn):
        """Add to must_not."""
        if callable(clause_or_fn):
            self.must_not.append(clause_or_fn(self))
        else:
            self.must_not.append(clause_or_fn)

    def add_nested(self, path: str, inner_clauses: list,
                   target: str = "filter", inner_target: str = "must",
                   score_mode: str = "none"):
        """Nested query builder."""
        inner = {"bool": {inner_target: inner_clauses}}
        clause = {"nested": {"path": path, "query": inner, "score_mode": score_mode}}
        getattr(self, target).append(clause)

    def add_nested_term(self, path: str, field: str, value,
                        target: str = "filter", score_mode: str = "none"):
        """Shortcut: nested + term."""
        inner = {"bool": {"filter": [{"term": {field: value}}]}}
        clause = {"nested": {"path": path, "query": inner, "score_mode": score_mode}}
        getattr(self, target).append(clause)

    def add_nested_match(self, path: str, field: str, query: str,
                         target: str = "must", score_mode: str = "max"):
        """Shortcut: nested + match."""
        inner = {"bool": {"must": [{"match": {field: query}}]}}
        clause = {"nested": {"path": path, "query": inner, "score_mode": score_mode}}
        getattr(self, target).append(clause)

    def add_deep_nested_term(self, outer_path: str, inner_path: str,
                             field: str, value,
                             target: str = "filter", score_mode: str = "none"):
        """Nested-in-nested: isi_list.tokoh.nama."""
        inner_nested = {
            "nested": {
                "path": f"{outer_path}.{inner_path}",
                "query": {"bool": {"filter": [{"term": {f"{outer_path}.{inner_path}.{field}": value}}]}}
            }
        }
        outer = {
            "nested": {
                "path": outer_path,
                "query": {"bool": {"filter": [inner_nested]}},
                "score_mode": score_mode
            }
        }
        getattr(self, target).append(outer)

    def build(self) -> dict:
        """Hasilkan dict query final."""
        result = {}
        if self.must:
            result["must"] = self.must
        if self.filter:
            result["filter"] = self.filter
        if self.must_not:
            result["must_not"] = self.must_not
        if self.should:
            result["should"] = self.should
            result.setdefault("minimum_should_match", 1)
        return {"bool": result}


@dataclass
class SearchResult:
    hits: list[dict] = field(default_factory=list)
    total: int = 0
    took_ms: int = 0
    aggregations: dict[str, dict] = field(default_factory=dict)
    error: Optional[str] = None


# ─── Search Class ────────────────────────────────────────────────────────────


class LaporanSearch:
    """
    Pencarian laporan dengan multi-filter.

    Semua parameter opsional — hanya yang di-set yang jadi filter.

    Args:
        q: Full-text search keyword
        q_isi: Search di isi_list (nested)
        jenis_id / klasifikasi_id / urgensi_id: FK object filter
        satuan_kerja_id / tujuan_id / pelapor_id: FK object filter
        created_by_id / neraca_kebenaran_id / neraca_kepercayaan_id
        status: integer (0=draft, 1=active, etc)
        approve: boolean
        nomor: exact keyword
        unique_id: exact keyword
        status_pengajuan_penghapusan: keyword

        tanggal_from / tanggal_to: date range (YYYY-MM-DD)
        created_from / created_to: date range
        updated_from / updated_to: date range

        tembusan_nama: filter by tembusan satuan_kerja name
        aspek_nama: filter by aspek name
        aspek_id: filter by aspek id
        has_lampiran: bool — ada lampiran atau tidak
        lampiran_jenis: filter by file jenis

        laporan_masuk_sk_nama: filter by laporan_masuk satuan_kerja.nama
        lokasi_id: filter nested isi_list by lokasi id
        tokoh_nama: filter nested isi_list.tokoh by nama
        tanggal_kapan_from / tanggal_kapan_to: range di isi_list.kapan

        size / from_p: pagination
        sort_by: field name (default: _score)
        sort_order: asc/desc
        highlight: bool — enable highlighting
        aggs: dict — custom aggregations
    """

    def __init__(self, base_url: str = BASE_URL, **kwargs):
        password = kwargs.get("password", OPENSEARCH_PASS)
        if not password:
            raise ValueError("Set ELASTICSEARCH_PASSWORD before using LaporanSearch")
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (kwargs.get("user", OPENSEARCH_USER),
                             password)
        self.session.verify = kwargs.get("verify", VERIFY_CERTS)
        self.session.headers.update({"Content-Type": "application/json"})
        self.index = kwargs.get("index", OPENSEARCH_INDEX)

    def _search_url(self):
        return f"{self.base_url}/{self.index}/_search"

    def _build_query(self, **params) -> dict:
        bq = BoolQuery()

        # ── Full-text search ──
        q = params.get("q")
        if q:
            bq.add_multi_match(
                query=q,
                fields=["judul", "narasi", "catatan", "komentar"],
                boost_field="judul",
                target="must"
            )

        # ── Search di isi_list (nested) ──
        q_isi = params.get("q_isi")
        if q_isi:
            bq.add_nested_match(
                path="isi_list",
                field="isi_list.isi",
                query=q_isi,
                target="should",
                score_mode="max"
            )

        # ── FK Object filters ──
        fk_int_filters = {
            "jenis.id": "jenis_id",
            "klasifikasi.id": "klasifikasi_id",
            "urgensi.id": "urgensi_id",
            "satuan_kerja.id": "satuan_kerja_id",
            "tujuan.id": "tujuan_id",
            "pelapor.id": "pelapor_id",
            "created_by.id": "created_by_id",
            "updated_by.id": "updated_by_id",
            "neraca_kebenaran.id": "neraca_kebenaran_id",
            "neraca_kepercayaan.id": "neraca_kepercayaan_id",
        }
        for es_field, param_key in fk_int_filters.items():
            val = params.get(param_key)
            if val is not None:
                bq.add_term(es_field, int(val))

        # ── Scalar filters ──
        if params.get("status") is not None:
            bq.add_term("status", int(params["status"]))

        if params.get("approve") is not None:
            bq.add_term("approve", bool(params["approve"]))

        if params.get("nomor"):
            bq.add_term("nomor", params["nomor"])

        if params.get("unique_id"):
            bq.add_term("unique_id", params["unique_id"])

        if params.get("status_pengajuan_penghapusan"):
            bq.add_term("status_pengajuan_penghapusan", params["status_pengajuan_penghapusan"])

        # ── Date ranges ──
        date_range_config = [
            ("tanggal_laporan", "tanggal_from", "tanggal_to"),
            ("created_date", "created_from", "created_to"),
            ("updated_date", "updated_from", "updated_to"),
        ]
        for field, param_from, param_to in date_range_config:
            gte = params.get(param_from)
            lte = params.get(param_to)
            if gte or lte:
                bq.add_range(field, gte=gte, lte=lte)

        # ── Array object filters ──
        if params.get("tembusan_nama"):
            bq.add_term("tembusan.nama", params["tembusan_nama"])

        if params.get("aspek_nama"):
            bq.add_term("aspek.nama", params["aspek_nama"])

        if params.get("aspek_id") is not None:
            bq.add_term("aspek.id", int(params["aspek_id"]))

        if params.get("has_lampiran") is True:
            bq.add_exists("lampiran")
        elif params.get("has_lampiran") is False:
            bq.must_not.append({"exists": {"field": "lampiran"}})

        if params.get("lampiran_jenis"):
            bq.add_term("lampiran.jenis", params["lampiran_jenis"])

        if params.get("laporan_masuk_sk_nama"):
            bq.add_term("laporan_masuk.satuan_kerja.nama", params["laporan_masuk_sk_nama"])

        # ── Nested filters (isi_list) ──
        if params.get("lokasi_id") is not None:
            bq.add_nested_term(
                path="isi_list",
                field="isi_list.lokasi.id",
                value=int(params["lokasi_id"])
            )

        if params.get("tokoh_nama"):
            bq.add_deep_nested_term(
                outer_path="isi_list",
                inner_path="tokoh",
                field="nama",
                value=params["tokoh_nama"]
            )

        # ── Range di isi_list.kapan ──
        kapan_from = params.get("tanggal_kapan_from")
        kapan_to = params.get("tanggal_kapan_to")
        if kapan_from or kapan_to:
            inner_r = {}
            if kapan_from:
                inner_r["gte"] = kapan_from
            if kapan_to:
                inner_r["lte"] = kapan_to
            inner = {"bool": {"filter": [{"range": {"isi_list.kapan": inner_r}}]}}
            bq.filter.append({"nested": {"path": "isi_list", "query": inner}})

        return bq.build()

    def _build_body(self, query: dict, **params) -> dict:
        body = {"query": query}

        # Pagination
        size = params.get("size", 20)
        from_p = params.get("from_p", 0)
        body["size"] = min(int(size), 10000)
        body["from"] = int(from_p)

        # Sorting
        sort_by = params.get("sort_by", "_score")
        sort_order = params.get("sort_order", "desc")
        body["sort"] = [{sort_by: {"order": sort_order}}]

        # Highlighting
        if params.get("highlight", True):
            body["highlight"] = {
                "fields": {
                    "judul": {"number_of_fragments": 1},
                    "narasi": {"fragment_size": 200, "number_of_fragments": 2},
                    "catatan": {"fragment_size": 150, "number_of_fragments": 1},
                    "komentar": {"fragment_size": 150, "number_of_fragments": 1},
                }
            }

        # Aggregations (from caller)
        if params.get("aggs"):
            body["aggs"] = params["aggs"]

        return body

    def search(self, verbose: bool = False, **params) -> SearchResult:
        """
        Lakukan pencarian.

        Args:
            verbose: Print raw query + response JSON ke stderr
            **params: Semua parameter filter (lihat docstring class)

        Returns:
            SearchResult dengan hits, total, aggregations
        """
        try:
            query = self._build_query(**params)
            body = self._build_body(query, **params)

            # Raw request body
            if verbose:
                print("=== REQUEST BODY ===", file=sys.stderr)
                print(json.dumps(body, indent=2), file=sys.stderr)

            resp = self.session.post(self._search_url(), json=body, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if verbose:
                print("=== RESPONSE (truncated) ===", file=sys.stderr)
                print(json.dumps(data, indent=2)[:3000], file=sys.stderr)

            # Parse hits
            hits_raw = data.get("hits", {}).get("hits", [])
            total = data.get("hits", {}).get("total", {}).get("value", 0)
            took = data.get("took", 0)

            hits = []
            for h in hits_raw:
                src = h.get("_source", {})
                hit = {
                    "id": src.get("id"),
                    "score": h.get("_score"),
                    "nomor": src.get("nomor"),
                    "judul": src.get("judul"),
                    "narasi": src.get("narasi"),
                    "catatan": src.get("catatan"),
                    "status": src.get("status"),
                    "approve": src.get("approve"),
                    "tanggal_laporan": src.get("tanggal_laporan"),
                    "jenis": src.get("jenis"),
                    "klasifikasi": src.get("klasifikasi"),
                    "urgensi": src.get("urgensi"),
                    "satuan_kerja": src.get("satuan_kerja"),
                    "pelapor": src.get("pelapor"),
                    "highlight": h.get("highlight"),
                }
                hits.append(hit)

            return SearchResult(
                hits=hits,
                total=total,
                took_ms=took,
                aggregations=data.get("aggregations", {}),
            )

        except requests.exceptions.RequestException as e:
            return SearchResult(error=f"HTTP Error: {e}")
        except json.JSONDecodeError as e:
            return SearchResult(error=f"JSON Parse Error: {e}")
        except Exception as e:
            return SearchResult(error=f"Error: {e}")


# ─── Preset Aggregations ────────────────────────────────────────────────────


AGGS_SIDEBAR = {
    "per_jenis": {"terms": {"field": "jenis.nama", "size": 30}},
    "per_klasifikasi": {"terms": {"field": "klasifikasi.nama", "size": 20}},
    "per_urgensi": {"terms": {"field": "urgensi.nama", "size": 10}},
    "per_status": {"terms": {"field": "status"}},
    "per_tahun": {
        "date_histogram": {
            "field": "tanggal_laporan",
            "calendar_interval": "year",
            "format": "yyyy",
            "min_doc_count": 1,
        }
    },
}

AGGS_TREND_BULANAN = {
    "trend_bulanan": {
        "date_histogram": {
            "field": "tanggal_laporan",
            "calendar_interval": "month",
            "format": "yyyy-MM",
            "min_doc_count": 1,
        }
    }
}


# ─── CLI ─────────────────────────────────────────────────────────────────────


def _parse_cli():
    import argparse

    p = argparse.ArgumentParser(description="Search laporan di OpenSearch")

    # Search
    p.add_argument("--q", help="Full-text search keyword")
    p.add_argument("--q-isi", help="Search di isi_list (nested)")

    # FK filters
    for fk in ["jenis_id", "klasifikasi_id", "urgensi_id", "satuan_kerja_id",
               "tujuan_id", "pelapor_id", "created_by_id", "neraca_kebenaran_id",
               "neraca_kepercayaan_id"]:
        p.add_argument(f"--{fk.replace('_', '-')}", type=int)

    # Scalar
    p.add_argument("--status", type=int)
    p.add_argument("--approve", type=str, choices=["true", "false"])
    p.add_argument("--nomor")
    p.add_argument("--unique-id")

    # Dates
    p.add_argument("--tanggal-from")
    p.add_argument("--tanggal-to")
    p.add_argument("--created-from")
    p.add_argument("--created-to")

    # Array objects
    p.add_argument("--tembusan-nama")
    p.add_argument("--aspek-nama")
    p.add_argument("--has-lampiran", type=str, choices=["true", "false"])
    p.add_argument("--lampiran-jenis")
    p.add_argument("--laporan-masuk-sk-nama")

    # Nested
    p.add_argument("--lokasi-id", type=int)
    p.add_argument("--tokoh-nama")

    # Pagination
    p.add_argument("--size", type=int, default=10)
    p.add_argument("--from", dest="from_p", type=int, default=0)
    p.add_argument("--sort-by", default="_score")
    p.add_argument("--sort-order", default="desc", choices=["asc", "desc"])

    # Aggregations
    p.add_argument("--aggs-sidebar", action="store_true", help="Tampilkan aggregasi sidebar")
    p.add_argument("--aggs-trend", action="store_true", help="Tampilkan trend bulanan")

    # Debug
    p.add_argument("-v", "--verbose", action="store_true")

    return p.parse_args()


def _fmt_hit(h: dict, i: int) -> str:
    lines = []
    lines.append(f"  [{i}] ID={h['id']} | score={h['score']:.4f}" if h.get('score') else f"  [{i}] ID={h['id']}")
    lines.append(f"       No.   : {h.get('nomor', '-')}")
    lines.append(f"       Judul : {h.get('judul', '-')}")

    narasi = h.get("narasi", "")
    if narasi and len(narasi) > 150:
        narasi = narasi[:150] + "..."
    if narasi:
        lines.append(f"       Narasi: {narasi}")

    if h.get("jenis"):
        lines.append(f"       Jenis : {h['jenis'].get('nama', '-')}")
    if h.get("klasifikasi"):
        lines.append(f"       Klasif: {h['klasifikasi'].get('nama', '-')}")
    if h.get("satuan_kerja"):
        lines.append(f"       SK    : {h['satuan_kerja'].get('nama', '-')}")
    if h.get("tanggal_laporan"):
        lines.append(f"       Tgl   : {h['tanggal_laporan']}")

    hl = h.get("highlight")
    if hl:
        for field, snippets in hl.items():
            for s in snippets:
                lines.append(f"       [HL] {field}: {s[:120]}")

    return "\n".join(lines)


def main():
    args = _parse_cli()

    # Convert argparse → params dict
    params = {k: v for k, v in vars(args).items()
              if v is not None and not k.startswith("aggs_") and k != "verbose"}

    # Boolean handling
    if params.get("approve") is not None:
        params["approve"] = params["approve"] == "true"
    if params.get("has_lampiran") is not None:
        params["has_lampiran"] = params["has_lampiran"] == "true"

    # Aggregations
    if args.aggs_sidebar:
        params["aggs"] = AGGS_SIDEBAR
    elif args.aggs_trend:
        params["aggs"] = AGGS_TREND_BULANAN

    # Search
    ls = LaporanSearch()
    result = ls.search(verbose=args.verbose, **params)

    # Output
    if result.error:
        print(f"ERROR: {result.error}")
        sys.exit(1)

    print(f"Found {result.total:,} docs in {result.took_ms}ms\n")

    for i, hit in enumerate(result.hits, 1):
        print(_fmt_hit(hit, i))
        print()

    if result.aggregations:
        print("── Aggregations ──")
        for name, buckets in result.aggregations.items():
            if "buckets" in buckets:
                items = [f"  {b['key']}: {b['doc_count']}" for b in buckets["buckets"]]
                print(f"{name}:")
                print("\n".join(items[:15]))
                print()


if __name__ == "__main__":
    main()
