#!/usr/bin/env python3

"""Create laporan index in OpenSearch with full mapping."""

import os, json, sys
from pathlib import Path
from opensearchpy import OpenSearch

# Load env — coba .env dulu (default compose), fallback legacy
env_candidates = [".env", ".env.laporan-dev", "laporan/.env"]
for env_candidate in env_candidates:
    env_path = Path(__file__).resolve().parent.parent / env_candidate
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            # Jangan timpa env yang udah di-set (prioritas dari compose --env-file)
            if key.strip() not in os.environ:
                os.environ[key.strip()] = val.strip()
        break  # pake file pertama yg ketemu

host = os.environ.get("ELASTICSEARCH_HOST", "localhost")
port = int(os.environ.get("ELASTICSEARCH_PORT", "9200"))
user = os.environ.get("ELASTICSEARCH_USER", "admin")
password = os.environ.get("ELASTICSEARCH_PASSWORD", "")

c = OpenSearch(
    hosts=[{"host": host, "port": port, "scheme": "https"}],
    http_auth=(user, password),
    use_ssl=True,
    verify_certs=os.environ.get("ELASTICSEARCH_VERIFY_CERTS", "true").lower() == "true",
)

index = os.environ.get("ELASTICSEARCH_INDEX", "laporan")
label = os.environ.get("OS_LABEL", "")

# ── Cek: index udah ada & berisi data? skip ──
exists = c.indices.exists(index=index)
if exists:
    count = c.count(index=index)["count"]
    if count > 0:
        print(f"Index '{index}' sudah ada dengan {count:,} docs — skip create")
        sys.exit(0)
    print(f"Index '{index}' ada tapi kosong — recreate")

# Delete if exists (empty or explicit recreate mode)
c.indices.delete(index=index, ignore=[400, 404])

body = {
    "settings": {"number_of_shards": 3, "number_of_replicas": 1},
    "mappings": {
        "properties": {
            "id": {"type": "integer"},
            "nomor": {"type": "keyword"},
            "judul": {"type": "text", "analyzer": "standard"},
            "narasi": {"type": "text", "analyzer": "standard"},
            "catatan": {"type": "text"},
            "komentar": {"type": "text"},
            "status": {"type": "integer"},
            "approve": {"type": "boolean"},
            "unique_id": {"type": "keyword"},
            "status_pengajuan_penghapusan": {"type": "keyword"},
            "tanggal_laporan": {"type": "date"},
            "created_date": {"type": "date"},
            "updated_date": {"type": "date"},
            "jenis": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "nama": {"type": "keyword"}},
            },
            "klasifikasi": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "nama": {"type": "keyword"}},
            },
            "urgensi": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "nama": {"type": "keyword"}},
            },
            "created_by": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "nama": {"type": "keyword"}},
            },
            "updated_by": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "nama": {"type": "keyword"}},
            },
            "pelapor": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "nama": {"type": "keyword"}},
            },
            "tujuan": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "nama": {"type": "keyword"}},
            },
            "satuan_kerja": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "nama": {"type": "keyword"}},
            },
            "neraca_kebenaran": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "nama": {"type": "keyword"}},
            },
            "neraca_kepercayaan": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "nama": {"type": "keyword"}},
            },
            # New multi-value relasi
            "tembusan": {
                "type": "nested",
                "properties": {
                    "id": {"type": "integer"},
                    "nama": {"type": "keyword"},
                },
            },
            "aspek": {
                "type": "nested",
                "properties": {
                    "id": {"type": "integer"},
                    "nama": {"type": "keyword"},
                },
            },
            "lampiran": {
                "type": "nested",
                "properties": {
                    "id": {"type": "integer"},
                    "jenis": {"type": "keyword"},
                    "file": {"type": "keyword"},
                    "catatan": {"type": "text"},
                    "realfile": {"type": "keyword"},
                    "created_date": {"type": "date"},
                },
            },
            "laporan_masuk": {
                "type": "nested",
                "properties": {
                    "id": {"type": "integer"},
                    "satuan_kerja": {
                        "type": "object",
                        "properties": {"id": {"type": "integer"}, "nama": {"type": "keyword"}},
                    },
                },
            },
            "isi_list": {
                "type": "nested",
                "properties": {
                    "isi": {"type": "text"},
                    "apa": {"type": "text"},
                    "mengapa": {"type": "text"},
                    "bagaimana": {"type": "text"},
                    "kapan": {"type": "date"},
                    "lokasi": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "nama": {"type": "keyword"},
                        },
                    },
                    "tokoh": {
                        "type": "nested",
                        "properties": {
                            "id": {"type": "integer"},
                            "nama": {"type": "keyword"},
                        },
                    },
                },
            },
        }
    },
}

c.indices.create(index=index, body=body)
tag = f" ({label})" if label else ""
print(f"Index '{index}' created{tag}")
