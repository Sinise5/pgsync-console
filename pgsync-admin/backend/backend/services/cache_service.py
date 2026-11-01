"""In-memory cache service for performance optimization."""

import logging
import time
from typing import Any, Optional, Dict, Tuple
from collections import OrderedDict
from threading import Lock

logger = logging.getLogger(__name__)


class LRUCache:
    """Thread-safe LRU cache with TTL."""

    def __init__(self, max_size: int = 100, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get cached value. Returns None if missing or expired."""
        with self._lock:
            if key not in self._cache:
                return None

            value, expiry = self._cache[key]
            if time.time() > expiry:
                del self._cache[key]
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set cached value with TTL."""
        with self._lock:
            expiry = time.time() + (ttl or self.default_ttl)
            self._cache[key] = (value, expiry)
            self._cache.move_to_end(key)

            # Evict oldest if over max_size
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def delete(self, key: str):
        """Delete cached value."""
        with self._lock:
            self._cache.pop(key, None)

    def clear(self):
        """Clear all cached values."""
        with self._lock:
            self._cache.clear()

    def invalidate_by_prefix(self, prefix: str):
        """Invalidate all keys starting with prefix."""
        with self._lock:
            keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_delete:
                del self._cache[k]

    @property
    def size(self) -> int:
        """Current cache size."""
        with self._lock:
            return len(self._cache)

    @property
    def stats(self) -> Dict[str, Any]:
        """Cache statistics."""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "default_ttl": self.default_ttl,
            }


# Global cache instances
config_cache = LRUCache(max_size=200, default_ttl=60)  # Config lookup cache (1 min TTL)
sql_cache = LRUCache(max_size=50, default_ttl=300)      # SQL query result cache (5 min TTL)
discovery_cache = LRUCache(max_size=20, default_ttl=600) # Schema discovery cache (10 min TTL)
clickhouse_cache = LRUCache(max_size=30, default_ttl=120) # ClickHouse query cache (2 min TTL)
