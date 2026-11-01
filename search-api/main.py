#!/usr/bin/env python3
"""
Laporan Search API
==================

FastAPI service untuk full-text search + dynamic filtering OpenSearch index 'laporan'

Features:
- Full-text search (nomor, judul, narasi, catatan, komentar)
- Dynamic filters (any field dari schema)
- Pagination (page, size)
- Highlighting
- Aggregations (counts by field)

Usage:
  curl "http://localhost:18080/search?q=korupsi&page=1&size=20"
  curl "http://localhost:18080/search?status=approve&urgensi_id=1"
  curl -X POST http://localhost:18080/search -H "Content-Type: application/json" \
    -d '{"query":"korupsi","filters":{"status":"approve"},"page":1,"size":20}'
"""

import os
from typing import Any, Optional
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from opensearchpy import OpenSearch
import logging

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load the monorepo environment file, with a service-local fallback for development.
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info("Loaded Search API environment file")
except ImportError:
    pass  # dotenv not installed, use system env only

# OpenSearch connection
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "laporan")
OPENSEARCH_VERIFY_CERTS = os.getenv("OPENSEARCH_VERIFY_CERTS", "true").lower() in {"1", "true", "yes"}

if not OPENSEARCH_PASSWORD:
    raise RuntimeError("OPENSEARCH_PASSWORD must be set in the environment")

client = OpenSearch(
    hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=True,
    verify_certs=OPENSEARCH_VERIFY_CERTS,
    ssl_show_warn=OPENSEARCH_VERIFY_CERTS,
)

app = FastAPI(
    title="Laporan Search API",
    description="Full-text search + dynamic filtering untuk OpenSearch index 'laporan'",
    version="1.0.0",
)


# ============================================================================
# Schema mapping — field types untuk dynamic filter
# ============================================================================

SEARCHABLE_FIELDS = [
    "nomor",
    "judul",
    "narasi",
    "catatan",
    "komentar",
    # nested fields (text only, no date/numeric)
    "laporan_isi.isi",
    "laporan_isi.apa",
    "laporan_isi.mengapa",
    "laporan_isi.bagaimana",
    # NOTE: laporan_isi.kapan excluded — date field tidak support fuzzy search
]

FILTERABLE_FIELDS = {
    # root table fields
    "id": "integer",
    "status": "keyword",
    "approve": "keyword",
    "tanggal_laporan": "date",
    "created_date": "date",
    "updated_date": "date",
    "unique_id": "keyword",
    "status_pengajuan_penghapusan": "keyword",
    "jenis_id": "integer",
    "klasifikasi_id": "integer",
    "urgensi_id": "integer",
    "created_by_id": "integer",
    "updated_by_id": "integer",
    "pelapor_id": "integer",
    "tujuan_id": "integer",
    "satuan_kerja_id": "integer",
    "neraca_kebenaran_id": "integer",
    "neraca_kepercayaan_id": "integer",
}


# ============================================================================
# Request/Response models
# ============================================================================

class SearchRequest(BaseModel):
    query: Optional[str] = Field(None, description="Full-text search query")
    filters: Optional[dict[str, Any]] = Field(default_factory=dict, description="Dynamic filters")
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    size: int = Field(20, ge=1, le=100, description="Results per page")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: Optional[str] = Field("desc", description="asc or desc")
    highlight: bool = Field(True, description="Enable highlighting")


class SearchResponse(BaseModel):
    total: int
    page: int
    size: int
    total_pages: int
    results: list[dict[str, Any]]
    aggregations: Optional[dict[str, Any]] = None
    took: int  # milliseconds


# ============================================================================
# Search builder
# ============================================================================

def build_query(request: SearchRequest) -> dict:
    """
    Build OpenSearch query DSL from SearchRequest
    """
    query_body: dict[str, Any] = {
        "from": (request.page - 1) * request.size,
        "size": request.size,
    }

    # Bool query container
    bool_query: dict[str, Any] = {
        "must": [],
        "filter": [],
    }

    # Full-text search
    if request.query:
        bool_query["must"].append({
            "multi_match": {
                "query": request.query,
                "fields": SEARCHABLE_FIELDS,
                "type": "best_fields",
                "operator": "or",
                "fuzziness": "AUTO",
            }
        })

    # Dynamic filters
    if request.filters:
        for field, value in request.filters.items():
            if field not in FILTERABLE_FIELDS:
                logger.warning(f"Unknown filter field: {field}")
                continue

            field_type = FILTERABLE_FIELDS[field]

            if field_type == "keyword":
                bool_query["filter"].append({"term": {field: value}})
            elif field_type == "integer":
                bool_query["filter"].append({"term": {field: int(value)}})
            elif field_type == "date":
                # Support range queries: {"tanggal_laporan": {"gte": "2024-01-01"}}
                if isinstance(value, dict):
                    bool_query["filter"].append({"range": {field: value}})
                else:
                    bool_query["filter"].append({"term": {field: value}})
            else:
                bool_query["filter"].append({"term": {field: value}})

    # If no must clauses, use match_all
    if not bool_query["must"]:
        query_body["query"] = {
            "bool": {
                "filter": bool_query["filter"]
            }
        } if bool_query["filter"] else {"match_all": {}}
    else:
        query_body["query"] = {"bool": bool_query}

    # Sort
    if request.sort_by:
        query_body["sort"] = [{request.sort_by: {"order": request.sort_order}}]
    else:
        # Default sort: relevance (_score) descending
        query_body["sort"] = ["_score"]

    # Highlighting
    if request.highlight:
        query_body["highlight"] = {
            "fields": {field: {} for field in SEARCHABLE_FIELDS},
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
        }

    return query_body


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/")
def root():
    return {
        "service": "Laporan Search API",
        "version": "1.0.0",
        "index": OPENSEARCH_INDEX,
        "endpoints": {
            "search_get": "GET /search?q=query&page=1&size=20",
            "search_post": "POST /search",
            "health": "GET /health",
        }
    }


@app.get("/health")
def health():
    """Health check — verify OpenSearch connectivity"""
    try:
        info = client.info()
        return {
            "status": "healthy",
            "opensearch": {
                "cluster_name": info.get("cluster_name"),
                "version": info.get("version", {}).get("number"),
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"OpenSearch unhealthy: {str(e)}")


@app.get("/search", response_model=SearchResponse)
def search_get(
    q: Optional[str] = Query(None, description="Full-text search query"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Results per page"),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    sort_order: str = Query("desc", description="asc or desc"),
    highlight: bool = Query(True, description="Enable highlighting"),
    # Dynamic filters via query params
    status: Optional[str] = None,
    approve: Optional[str] = None,
    jenis_id: Optional[int] = None,
    klasifikasi_id: Optional[int] = None,
    urgensi_id: Optional[int] = None,
    satuan_kerja_id: Optional[int] = None,
):
    """
    GET search with query params

    Examples:
      /search?q=korupsi&page=1&size=20
      /search?status=approve&urgensi_id=1
      /search?q=politik&jenis_id=2&sort_by=created_date&sort_order=desc
    """
    # Build filters from query params
    filters = {}
    if status:
        filters["status"] = status
    if approve:
        filters["approve"] = approve
    if jenis_id:
        filters["jenis_id"] = jenis_id
    if klasifikasi_id:
        filters["klasifikasi_id"] = klasifikasi_id
    if urgensi_id:
        filters["urgensi_id"] = urgensi_id
    if satuan_kerja_id:
        filters["satuan_kerja_id"] = satuan_kerja_id

    request = SearchRequest(
        query=q,
        filters=filters,
        page=page,
        size=size,
        sort_by=sort_by,
        sort_order=sort_order,
        highlight=highlight,
    )

    return execute_search(request)


@app.post("/search", response_model=SearchResponse)
def search_post(request: SearchRequest):
    """
    POST search with JSON body

    Example:
      {
        "query": "korupsi",
        "filters": {"status": "approve", "urgensi_id": 1},
        "page": 1,
        "size": 20,
        "sort_by": "created_date",
        "sort_order": "desc"
      }
    """
    return execute_search(request)


def execute_search(request: SearchRequest) -> SearchResponse:
    """Execute OpenSearch query"""
    try:
        query_body = build_query(request)

        logger.info(f"Executing search: page={request.page} size={request.size}")

        response = client.search(
            index=OPENSEARCH_INDEX,
            body=query_body,
        )

        total = response["hits"]["total"]["value"]
        total_pages = (total + request.size - 1) // request.size

        results = []
        for hit in response["hits"]["hits"]:
            result = {
                "id": hit["_id"],
                "score": hit["_score"],
                **hit["_source"],
            }

            # Add highlights if present
            if "highlight" in hit:
                result["_highlight"] = hit["highlight"]

            results.append(result)

        return SearchResponse(
            total=total,
            page=request.page,
            size=request.size,
            total_pages=total_pages,
            results=results,
            took=response["took"],
        )

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
