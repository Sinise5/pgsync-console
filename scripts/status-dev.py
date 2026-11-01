#!/usr/bin/env python3
"""Print laporan index status on dev OS cluster."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env.laporan-dev
from pathlib import Path
env_path = Path(__file__).resolve().parent.parent / ".env.laporan-dev"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())

from opensearchpy import OpenSearch

host = os.environ.get("ELASTICSEARCH_HOST", "localhost")
port = int(os.environ.get("ELASTICSEARCH_PORT", 9200))
user = os.environ.get("ELASTICSEARCH_USER", "admin")
password = os.environ.get("ELASTICSEARCH_PASSWORD", "")
scheme = os.environ.get("ELASTICSEARCH_SCHEME", "https")

client = OpenSearch(
    hosts=[{"host": host, "port": port, "scheme": scheme}],
    http_auth=(user, password),
    use_ssl=(scheme == "https"),
    verify_certs=os.environ.get("ELASTICSEARCH_VERIFY_CERTS", "true").lower() == "true",
)

r = client.count(index="laporan")
print(f"  laporan index: {r['count']} docs")

s = client.search(index="laporan", body={
    "size": 3, "query": {"match_all": {}}, "sort": [{"id": "desc"}]
})
for h in s["hits"]["hits"]:
    src = h["_source"]
    j = src.get("judul", "")[:60]
    jn = src.get("jenis", {}).get("nama", "")
    sk = src.get("satuan_kerja", {}).get("nama", "")
    dt = src.get("tanggal_laporan", "")
    print(f'  id={h["_id"]} judul="{j}" jenis={jn} satker={sk} date={dt}')
