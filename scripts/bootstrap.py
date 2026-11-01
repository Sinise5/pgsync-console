#!/usr/bin/env python3
"""Bootstrap OpenSearch index from schema.json."""
import json
import os
import sys

from opensearchpy import OpenSearch

HOST = os.environ.get("ELASTICSEARCH_HOST", "localhost")
PORT = int(os.environ.get("ELASTICSEARCH_PORT", "9200"))
USER = os.environ.get("ELASTICSEARCH_USER", "admin")
PASSWORD = os.environ.get("ELASTICSEARCH_PASSWORD", "")
USE_SSL = os.environ.get("ELASTICSEARCH_USE_SSL", "true").lower() == "true"
VERIFY_CERTS = os.environ.get("ELASTICSEARCH_VERIFY_CERTS", "true").lower() == "true"
SCHEMA_PATH = os.environ.get("SCHEMA", "config/schema.json")

if not PASSWORD:
    raise SystemExit("Set ELASTICSEARCH_PASSWORD before bootstrapping the index")

os_client = OpenSearch(
    hosts=[{"host": HOST, "port": PORT}],
    http_auth=(USER, PASSWORD),
    use_ssl=USE_SSL,
    verify_certs=VERIFY_CERTS,
)

with open(SCHEMA_PATH) as f:
    schemas = json.load(f)

for schema in schemas:
    index = schema["index"]
    body = {
        "settings": schema.get("settings", {}),
        "mappings": {"properties": schema["mapping"]["properties"]},
    }
    if os_client.indices.exists(index=index):
        os_client.indices.delete(index=index)
        print(f"  Deleted existing index: {index}")
    os_client.indices.create(index=index, body=body)
    print(f"  Created index:  {index}")

print("Bootstrap complete.")
