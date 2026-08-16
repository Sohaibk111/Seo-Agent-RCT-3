import time
import json
import asyncio
import threading
import logging
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from typing import Any, Dict, List, Optional, Tuple, Callable
from backend.config import settings
from backend.metrics import metrics_registry

logger = logging.getLogger("seo_agent.cache")

def custom_json_serializer(obj: Any) -> Any:
    """Encoder handler for complex Python types during JSON caching serialization."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, set):
        return list(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

def safe_json_dumps(value: Any) -> str:
    """Safely serialize data to JSON string for Redis storage with custom type handlers."""
    return json.dumps(value, default=custom_json_serializer)


# Global Redis Connection Pool Singleton
_redis_connection_pool = None
_redis_pool_lock = threading.Lock()

def get_redis_connection_pool():
    """
    Returns a thread-safe singleton Redis ConnectionPool configured with settings.
    """
    global _redis_connection_pool
    if not settings.REDIS_URL:
        return None
        
    if _redis_connection_pool is None:
        with _redis_pool_lock:
            if _redis_connection_pool is None:
                try:
                    import redis
                    _redis_connection_pool = redis.ConnectionPool.from_url(
                        settings.REDIS_URL,
                        max_connections=getattr(settings, "REDIS_MAX_CONNECTIONS", 50),
                        socket_timeout=getattr(settings, "REDIS_SOCKET_TIMEOUT", 2.0),
                        socket_connect_timeout=getattr(settings, "REDIS_CONNECT_TIMEOUT", 1.0),
                        decode_responses=True
                    )
                    logger.info("Initialized Redis ConnectionPool successfully.")
                except Exception as e:
                    logger.warning(f"Failed to initialize Redis ConnectionPool: {e}")
                    _redis_connection_pool = None
    return _redis_connection_pool

def get_redis_client():
    """
    Returns a Redis client instance backed by the shared connection pool.
    """
    pool = get_redis_connection_pool()
    if pool is not None:
        try:
            import redis
            return redis.Redis(connection_pool=pool)
        except Exception as e:
            logger.warning(f"Failed to create Redis client from pool: {e}")
    return None


class InMemoryTTLCache:
    """Lightweight, thread-safe in-memory TTL cache for expensive backend operations."""

    def __init__(self, default_ttl: int = settings.CACHE_TTL_DEFAULT, max_size: int = settings.CACHE_MAX_ITEMS):
        self._cache: Dict[str, Tuple[Any, float]] = {}  # key -> (value, expire_at)
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        now = time.time()
        with self._lock:
            if key in self._cache:
                val, expire_at = self._cache[key]
                if now < expire_at:
                    return val
                del self._cache[key]
        return None

    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        result = {}
        now = time.time()
        with self._lock:
            for key in keys:
                if key in self._cache:
                    val, expire_at = self._cache[key]
                    if now < expire_at:
                        result[key] = val
                    else:
                        del self._cache[key]
        return result

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl_seconds = ttl if ttl is not None else self._default_ttl
        expire_at = time.time() + ttl_seconds
        with self._lock:
            if len(self._cache) >= self._max_size:
                self._prune_expired_unlocked()
                if len(self._cache) >= self._max_size:
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
            self._cache[key] = (value, expire_at)

    def set_many(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> None:
        for k, v in mapping.items():
            self.set(k, v, ttl=ttl)

    def delete(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def delete_many(self, keys: List[str]) -> int:
        count = 0
        with self._lock:
            for key in keys:
                if key in self._cache:
                    del self._cache[key]
                    count += 1
        return count

    def delete_pattern(self, pattern: str) -> int:
        import fnmatch
        count = 0
        with self._lock:
            keys_to_del = [k for k in self._cache if fnmatch.fnmatch(k, pattern)]
            for k in keys_to_del:
                del self._cache[k]
                count += 1
        return count

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def _prune_expired_unlocked(self) -> None:
        now = time.time()
        expired_keys = [k for k, (_, exp) in self._cache.items() if now >= exp]
        for k in expired_keys:
            del self._cache[k]

    def size(self) -> int:
        now = time.time()
        with self._lock:
            return sum(1 for _, exp in self._cache.values() if now < exp)


# Lua Scripts for Redis
LUA_INVALIDATE_PATTERN = """
local keys = redis.call('KEYS', ARGV[1])
if #keys > 0 then
    return redis.call('DEL', unpack(keys))
else
    return 0
end
"""

LUA_ATOMIC_GET_DEL = """
local val = redis.call('GET', KEYS[1])
if val then
    redis.call('DEL', KEYS[1])
end
return val
"""


class UnifiedCache:
    """Production cache supporting Redis Connection Pooling, Pipelines, Lua Scripts, Batch operations, and Warming."""

    def __init__(self):
        self._local_cache = InMemoryTTLCache()
        self._redis_client = None
        self._redis_connected = False
        self._lua_invalidate_pattern = None
        self._lua_atomic_get_del = None
        self._init_redis()

    def _init_redis(self):
        client = get_redis_client()
        if client is not None:
            try:
                client.ping()
                self._redis_client = client
                self._redis_connected = True
                self._register_lua_scripts()
                logger.info("UnifiedCache connected to Redis with ConnectionPool.")
            except Exception as e:
                logger.warning(f"Redis cache ping failed ({e}). Falling back to InMemoryTTLCache.")
                self._redis_client = None
                self._redis_connected = False
        else:
            self._redis_client = None
            self._redis_connected = False

    def _register_lua_scripts(self):
        if self._redis_client:
            try:
                self._lua_invalidate_pattern = self._redis_client.register_script(LUA_INVALIDATE_PATTERN)
                self._lua_atomic_get_del = self._redis_client.register_script(LUA_ATOMIC_GET_DEL)
            except Exception as e:
                logger.warning(f"Failed to register Lua scripts in Redis: {e}")

    def is_redis_active(self) -> bool:
        return self._redis_connected and self._redis_client is not None

    @property
    def redis_client(self):
        return self._redis_client if self.is_redis_active() else None

    def get(self, key: str) -> Optional[Any]:
        val = None
        if self.is_redis_active():
            try:
                raw_val = self._redis_client.get(key)
                if raw_val is not None:
                    val = json.loads(raw_val)
            except Exception as e:
                logger.warning(f"Redis get failed ({e}), falling back to local cache.")
                val = self._local_cache.get(key)
        else:
            val = self._local_cache.get(key)

        if val is not None:
            metrics_registry.inc_cache_hit()
        else:
            metrics_registry.inc_cache_miss()

        return val

    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Batch fetch multiple keys from cache using Redis MGET or local cache."""
        if not keys:
            return {}

        result: Dict[str, Any] = {}
        if self.is_redis_active():
            try:
                raw_vals = self._redis_client.mget(keys)
                for key, raw_val in zip(keys, raw_vals):
                    if raw_val is not None:
                        try:
                            result[key] = json.loads(raw_val)
                            metrics_registry.inc_cache_hit()
                        except Exception:
                            metrics_registry.inc_cache_miss()
                    else:
                        metrics_registry.inc_cache_miss()
                return result
            except Exception as e:
                logger.warning(f"Redis get_many failed ({e}), falling back to local cache.")

        local_results = self._local_cache.get_many(keys)
        for key in keys:
            if key in local_results:
                metrics_registry.inc_cache_hit()
            else:
                metrics_registry.inc_cache_miss()
        return local_results

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl_seconds = ttl if ttl is not None else settings.CACHE_TTL_DEFAULT
        if self.is_redis_active():
            try:
                serialized = safe_json_dumps(value)
                self._redis_client.setex(key, ttl_seconds, serialized)
                return
            except Exception as e:
                logger.warning(f"Redis set failed ({e}), using local cache.")
        self._local_cache.set(key, value, ttl=ttl_seconds)

    def set_many(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """Batch set multiple key-value pairs using Redis pipeline."""
        if not mapping:
            return
        ttl_seconds = ttl if ttl is not None else settings.CACHE_TTL_DEFAULT
        if self.is_redis_active():
            try:
                pipe = self._redis_client.pipeline(transaction=False)
                for key, val in mapping.items():
                    serialized = safe_json_dumps(val)
                    pipe.setex(key, ttl_seconds, serialized)
                pipe.execute()
                return
            except Exception as e:
                logger.warning(f"Redis set_many pipeline failed ({e}), using local cache.")
        self._local_cache.set_many(mapping, ttl=ttl_seconds)

    def delete(self, key: str) -> None:
        if self.is_redis_active():
            try:
                self._redis_client.delete(key)
            except Exception as e:
                logger.warning(f"Redis delete failed ({e}).")
        self._local_cache.delete(key)

    def delete_many(self, keys: List[str]) -> int:
        """Batch delete multiple keys."""
        if not keys:
            return 0
        deleted_count = 0
        if self.is_redis_active():
            try:
                deleted_count = self._redis_client.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis delete_many failed ({e}).")
        local_count = self._local_cache.delete_many(keys)
        return max(deleted_count, local_count)

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate keys matching pattern (e.g. 'website:101:*') using Lua script or local search."""
        count = 0
        if self.is_redis_active():
            try:
                if self._lua_invalidate_pattern:
                    count = self._lua_invalidate_pattern(args=[pattern])
                else:
                    keys = self._redis_client.keys(pattern)
                    if keys:
                        count = self._redis_client.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis pattern invalidation failed for {pattern}: {e}")

        local_count = self._local_cache.delete_pattern(pattern)
        return max(count, local_count)

    def invalidate_tag(self, tag: str) -> int:
        """Helper to invalidate all cache entries for a given entity tag (e.g., 'user_12')."""
        pattern = f"*{tag}*"
        return self.invalidate_pattern(pattern)

    def invalidate_keys(self, keys: List[str]) -> int:
        """Alias for delete_many for clean domain invalidation."""
        return self.delete_many(keys)

    def atomic_get_delete(self, key: str) -> Optional[Any]:
        """Atomically get and delete a key using Lua script."""
        if self.is_redis_active() and self._lua_atomic_get_del:
            try:
                raw_val = self._lua_atomic_get_del(keys=[key])
                if raw_val:
                    return json.loads(raw_val)
            except Exception as e:
                logger.warning(f"Lua atomic_get_delete failed ({e}), using fallback.")
        val = self.get(key)
        if val is not None:
            self.delete(key)
        return val

    def warm_cache(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> int:
        """Pre-populates the cache with a dictionary of key-value pairs."""
        if not mapping:
            return 0
        self.set_many(mapping, ttl=ttl)
        logger.info(f"Warmed cache with {len(mapping)} keys.")
        return len(mapping)

    def warm_common_keys(self, data_loader_func: Callable[[], Dict[str, Any]], ttl: Optional[int] = None) -> int:
        """Executes a data loader function and populates the cache with the returned map."""
        try:
            data = data_loader_func()
            return self.warm_cache(data, ttl=ttl)
        except Exception as e:
            logger.error(f"Error warming cache via data loader: {e}")
            return 0

    def clear(self) -> None:
        if self.is_redis_active():
            try:
                self._redis_client.flushdb()
            except Exception as e:
                logger.warning(f"Redis clear failed ({e}).")
        self._local_cache.clear()

    async def get_async(self, key: str) -> Optional[Any]:
        return self.get(key)

    async def set_async(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self.set(key, value, ttl=ttl)

    async def delete_async(self, key: str) -> None:
        self.delete(key)

    async def get_many_async(self, keys: List[str]) -> Dict[str, Any]:
        return self.get_many(keys)

    async def set_many_async(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> None:
        self.set_many(mapping, ttl=ttl)

    def size(self) -> int:
        if self.is_redis_active():
            try:
                return self._redis_client.dbsize()
            except Exception:
                pass
        return self._local_cache.size()


def cache_response(ttl: int = settings.CACHE_TTL_DEFAULT, prefix: str = "resp"):
    """
    Decorator for caching endpoint responses based on function arguments and current user.
    """
    from functools import wraps
    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                user_id = 0
                current_user = kwargs.get("current_user")
                if current_user and hasattr(current_user, "id"):
                    user_id = current_user.id
                
                # Build cache key from function name, user_id, args, and kwargs
                arg_str = ":".join(str(a) for a in args if not hasattr(a, "execute"))
                kwarg_str = ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()) if k not in ("db", "current_user", "request"))
                cache_key = f"{prefix}:{func.__name__}:u{user_id}:{arg_str}:{kwarg_str}"
                
                cached = ttl_cache.get(cache_key)
                if cached is not None:
                    return cached
                
                res = await func(*args, **kwargs)
                ttl_cache.set(cache_key, res, ttl=ttl)
                return res
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                user_id = 0
                current_user = kwargs.get("current_user")
                if current_user and hasattr(current_user, "id"):
                    user_id = current_user.id
                
                arg_str = ":".join(str(a) for a in args if not hasattr(a, "execute"))
                kwarg_str = ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()) if k not in ("db", "current_user", "request"))
                cache_key = f"{prefix}:{func.__name__}:u{user_id}:{arg_str}:{kwarg_str}"
                
                cached = ttl_cache.get(cache_key)
                if cached is not None:
                    return cached
                
                res = func(*args, **kwargs)
                ttl_cache.set(cache_key, res, ttl=ttl)
                return res
            return sync_wrapper
    return decorator



# Global singleton cache instance for backend services
ttl_cache = UnifiedCache()
