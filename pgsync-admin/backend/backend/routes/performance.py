"""Performance monitoring and optimization routes."""

import json
import logging
from robyn import Request, Response

from backend.services.cache_service import config_cache, sql_cache, discovery_cache, clickhouse_cache

logger = logging.getLogger(__name__)


def performance_routes(app):
    """Register performance monitoring routes."""

    @app.get("/api/performance/cache-stats")
    async def cache_stats(request: Request) -> Response:
        """Get cache statistics."""
        try:
            stats = {
                "config_cache": config_cache.stats,
                "sql_cache": sql_cache.stats,
                "discovery_cache": discovery_cache.stats,
                "clickhouse_cache": clickhouse_cache.stats,
                "total_cached": (
                    config_cache.size
                    + sql_cache.size
                    + discovery_cache.size
                    + clickhouse_cache.size
                ),
            }
            return Response(
                status_code=200,
                body=json.dumps({"stats": stats}),
            )
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/performance/cache/clear")
    async def clear_caches(request: Request) -> Response:
        """Clear all caches."""
        try:
            body = json.loads(request.body or "{}")
            cache_type = body.get("cache_type", "all")

            if cache_type == "config" or cache_type == "all":
                config_cache.clear()
            if cache_type == "sql" or cache_type == "all":
                sql_cache.clear()
            if cache_type == "discovery" or cache_type == "all":
                discovery_cache.clear()
            if cache_type == "clickhouse" or cache_type == "all":
                clickhouse_cache.clear()

            return Response(
                status_code=200,
                body=json.dumps({"message": f"Cleared {cache_type} cache"}),
            )
        except Exception as e:
            logger.error(f"Failed to clear caches: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )

    @app.post("/api/performance/cache/invalidate")
    async def invalidate_cache_prefix(request: Request) -> Response:
        """Invalidate cache by prefix."""
        try:
            body = json.loads(request.body)
            prefix = body.get("prefix")
            cache_type = body.get("cache_type", "config")

            if not prefix:
                return Response(
                    status_code=400,
                    body=json.dumps({"error": "Prefix is required"}),
                )

            if cache_type == "config":
                config_cache.invalidate_by_prefix(prefix)
            elif cache_type == "sql":
                sql_cache.invalidate_by_prefix(prefix)
            elif cache_type == "discovery":
                discovery_cache.invalidate_by_prefix(prefix)
            elif cache_type == "clickhouse":
                clickhouse_cache.invalidate_by_prefix(prefix)

            return Response(
                status_code=200,
                body=json.dumps({"message": f"Invalidated cache entries with prefix: {prefix}"}),
            )
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
            return Response(
                status_code=500,
                body=json.dumps({"error": str(e)}),
            )
