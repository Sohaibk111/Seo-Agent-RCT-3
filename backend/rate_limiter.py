import time
import threading
from typing import Dict, List, Optional
from fastapi import Request
from backend.config import settings
from backend.exceptions import SEOAgentException
from backend.logging_config import logger

class DistributedRateLimiter:
    """
    Production-grade distributed rate limiter using Redis sorted sets (ZADD/ZREMRANGEBYSCORE/ZCARD)
    with thread-safe local in-memory sliding window fallback.
    """

    def __init__(self):
        self._local_requests: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
        self._redis_client = None

    def is_redis_active(self) -> bool:
        """Returns True if Redis connection is established and healthy for rate limiting."""
        client = self._get_redis()
        return client is not None

    def _get_redis(self):
        if self._redis_client is not None:
            return self._redis_client
        if settings.REDIS_URL:
            try:
                import redis
                client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                    socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT
                )
                if client.ping():
                    self._redis_client = client
                    logger.info("Initialized Redis-backed distributed rate limiter.")
                    return self._redis_client
            except Exception as e:
                logger.warning(f"Failed to connect to Redis for distributed rate limiter: {e}")
                self._redis_client = None
        return None

    def check_rate_limit(self, client_identifier: str, max_requests: Optional[int] = None, window_seconds: int = 60) -> bool:
        if not settings.RATE_LIMIT_ENABLED:
            return True

        limit = max_requests if max_requests is not None else settings.RATE_LIMIT_PER_MINUTE
        now = time.time()
        cutoff = now - window_seconds

        # 1. Redis-backed distributed rate limiting
        redis_client = self._get_redis()
        if redis_client is not None:
            try:
                key = f"ratelimit:{client_identifier}"
                pipe = redis_client.pipeline()
                pipe.zremrangebyscore(key, 0, cutoff)
                pipe.zadd(key, {f"{now}": now})
                pipe.zcard(key)
                pipe.expire(key, window_seconds + 5)
                results = pipe.execute()
                
                request_count = results[2]
                if request_count > limit:
                    return False
                return True
            except Exception as e:
                logger.warning(f"Redis rate limiting failed, falling back to local memory: {e}")
                self._redis_client = None

        # 2. Local in-memory sliding window fallback
        with self._lock:
            timestamps = self._local_requests.get(client_identifier, [])
            valid_timestamps = [ts for ts in timestamps if ts > cutoff]

            if len(valid_timestamps) >= limit:
                self._local_requests[client_identifier] = valid_timestamps
                return False

            valid_timestamps.append(now)
            self._local_requests[client_identifier] = valid_timestamps
            return True

rate_limiter = DistributedRateLimiter()

# Backward compatibility alias
sliding_window_limiter = rate_limiter

def rate_limit_guard(request: Request, max_requests: Optional[int] = None):
    """FastAPI dependency to enforce rate limiting on specific endpoints."""
    client_ip = request.client.host if request.client else "unknown"
    auth_header = request.headers.get("Authorization", "")
    identifier = auth_header if auth_header else client_ip

    if not rate_limiter.check_rate_limit(identifier, max_requests=max_requests):
        raise SEOAgentException(
            message="Rate limit exceeded. Please try again later.",
            status_code=429,
            details={"retry_after_seconds": 60}
        )
