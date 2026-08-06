import json
import logging
import threading
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.config import settings
from backend.metrics import metrics_registry

logger = logging.getLogger("seo_agent.dlq")

class DeadLetterQueue:
    """Redis-backed Dead Letter Queue with thread-safe in-memory fallback and persistent synchronization."""

    def __init__(self, queue_name: str = "dead_letter_queue"):
        self.queue_name = queue_name
        self._local_dlq: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._redis_client = None
        self._redis_connected = False
        self._init_redis()

    def _init_redis(self):
        if settings.REDIS_URL:
            try:
                import redis
                client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1.0)
                client.ping()
                self._redis_client = client
                self._redis_connected = True
            except Exception as e:
                logger.warning(f"DLQ Redis connection failed ({e}). Using in-memory DLQ store.")
                self._redis_client = None
                self._redis_connected = False

    def is_redis_active(self) -> bool:
        if settings.ENABLE_DEAD_LETTER_QUEUE and self._redis_connected and self._redis_client is not None:
            return True
        # Attempt reconnection if Redis URL is configured but not connected
        if settings.ENABLE_DEAD_LETTER_QUEUE and settings.REDIS_URL and not self._redis_connected:
            self._init_redis()
            return self._redis_connected
        return False

    def push_to_dlq(
        self,
        job_id: int,
        job_type: str,
        user_id: int,
        failure_reason: str,
        stack_trace: Optional[str] = None,
        retry_count: int = 0,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "job_id": job_id,
            "job_type": job_type,
            "user_id": user_id,
            "failure_reason": failure_reason,
            "stack_trace": stack_trace or traceback.format_exc(),
            "retry_count": retry_count,
            "timestamp": datetime.utcnow().isoformat(),
            "extra_data": extra_data or {},
        }

        if self.is_redis_active():
            try:
                data_str = json.dumps(payload)
                self._redis_client.rpush(self.queue_name, data_str)
                count = self._redis_client.llen(self.queue_name)
                metrics_registry.set_dead_letter_jobs(count)
                logger.error(
                    f"Job #{job_id} ({job_type}) moved to Redis DLQ '{self.queue_name}'. Reason: {failure_reason}",
                    extra={"job_id": job_id, "user_id": user_id}
                )
                return payload
            except Exception as e:
                logger.warning(f"Failed to push to Redis DLQ ({e}), saving to local DLQ.")
                self._redis_connected = False

        with self._lock:
            self._local_dlq.append(payload)
            local_count = len(self._local_dlq)
            
        metrics_registry.set_dead_letter_jobs(local_count)
        logger.error(
            f"Job #{job_id} ({job_type}) moved to Local DLQ. Reason: {failure_reason}",
            extra={"job_id": job_id, "user_id": user_id}
        )
        return payload

    def get_dlq_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        if self.is_redis_active():
            try:
                raw_items = self._redis_client.lrange(self.queue_name, 0, limit - 1)
                return [json.loads(item) for item in raw_items]
            except Exception as e:
                logger.warning(f"Failed to fetch DLQ jobs from Redis ({e}).")
                self._redis_connected = False

        with self._lock:
            return list(self._local_dlq[:limit])

    def get_dlq_count(self) -> int:
        if self.is_redis_active():
            try:
                return self._redis_client.llen(self.queue_name)
            except Exception:
                self._redis_connected = False

        with self._lock:
            return len(self._local_dlq)

    def clear_dlq(self) -> int:
        count = 0
        if self.is_redis_active():
            try:
                count = self._redis_client.llen(self.queue_name)
                self._redis_client.delete(self.queue_name)
                metrics_registry.set_dead_letter_jobs(0)
                with self._lock:
                    self._local_dlq.clear()
                return count
            except Exception as e:
                logger.warning(f"Failed to clear Redis DLQ ({e}).")
                self._redis_connected = False

        with self._lock:
            count = len(self._local_dlq)
            self._local_dlq.clear()
        metrics_registry.set_dead_letter_jobs(0)
        return count


# Global singleton DLQ instance
dead_letter_queue = DeadLetterQueue()
