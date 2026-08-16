import os
import json
import socket
import time
import uuid
import logging
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.config import settings
from backend.metrics import metrics_registry

logger = logging.getLogger("seo_agent.worker_heartbeat")

class WorkerHeartbeatManager:
    """Manages worker identification, system metrics collection, and periodic Redis heartbeat persistence."""

    def __init__(
        self,
        worker_id: Optional[str] = None,
        heartbeat_interval: Optional[int] = None,
        redis_client: Optional[Any] = None,
    ):
        self.hostname = socket.gethostname()
        self.pid = os.getpid()
        self.worker_id = worker_id or f"worker-{self.hostname}-{self.pid}-{uuid.uuid4().hex[:6]}"
        self.heartbeat_interval = heartbeat_interval or settings.WORKER_HEARTBEAT_INTERVAL
        self.ttl = self.heartbeat_interval * 3

        self.status = "starting"
        self.running_jobs_count = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._redis_client = redis_client
        self._init_redis()

    def _init_redis(self):
        if self._redis_client is None and settings.REDIS_URL:
            try:
                import redis
                client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1.0)
                client.ping()
                self._redis_client = client
            except Exception as e:
                logger.warning(f"Heartbeat Redis connection warning ({e}). Operating in memory mode.")
                self._redis_client = None

    def get_redis_key(self) -> str:
        return f"seo_agent:worker:{self.worker_id}"

    def collect_system_metrics(self) -> Dict[str, float]:
        cpu_usage = 0.0
        memory_usage = 0.0
        try:
            import psutil
            process = psutil.Process(self.pid)
            cpu_usage = round(process.cpu_percent(interval=None), 2)
            memory_usage = round(process.memory_info().rss / (1024 * 1024), 2)  # MB
        except Exception:
            try:
                import resource
                memory_usage = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)
            except Exception:
                pass
        return {"cpu_usage": cpu_usage, "memory_usage": memory_usage}

    def set_status(self, status: str, running_jobs: Optional[int] = None):
        with self._lock:
            self.status = status
            if running_jobs is not None:
                self.running_jobs_count = running_jobs
        self.publish_heartbeat()

    def generate_heartbeat_payload(self) -> Dict[str, Any]:
        with self._lock:
            current_status = self.status
            current_jobs = self.running_jobs_count

        sys_metrics = self.collect_system_metrics()
        return {
            "worker_id": self.worker_id,
            "hostname": self.hostname,
            "pid": self.pid,
            "status": current_status,
            "last_seen": datetime.utcnow().isoformat(),
            "running_jobs": current_jobs,
            "cpu_usage": sys_metrics["cpu_usage"],
            "memory_usage": sys_metrics["memory_usage"],
        }

    def publish_heartbeat(self):
        payload = self.generate_heartbeat_payload()
        if self._redis_client:
            try:
                key = self.get_redis_key()
                self._redis_client.set(key, json.dumps(payload), ex=self.ttl)
            except Exception as e:
                logger.warning(f"Failed to publish Redis worker heartbeat ({e}).")

    def start_heartbeat_loop(self):
        if self._running:
            return
        self._running = True
        self.set_status("idle")
        metrics_registry.set_worker_active(1)

        def _heartbeat_task():
            while self._running:
                try:
                    self.publish_heartbeat()
                except Exception as e:
                    logger.error(f"Error in heartbeat thread: {e}")
                time.sleep(self.heartbeat_interval)

        self._thread = threading.Thread(target=_heartbeat_task, daemon=True)
        self._thread.start()
        logger.info(f"Worker heartbeat loop started for {self.worker_id}")

    def stop_heartbeat_loop(self):
        self._running = False
        self.set_status("stopped")
        metrics_registry.set_worker_active(0)
        if self._redis_client:
            try:
                self._redis_client.delete(self.get_redis_key())
            except Exception:
                pass
        logger.info(f"Worker heartbeat stopped for {self.worker_id}")

    @classmethod
    def get_active_workers(cls, redis_client: Optional[Any] = None) -> List[Dict[str, Any]]:
        client = redis_client
        if client is None and settings.REDIS_URL:
            try:
                import redis
                client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1.0)
            except Exception:
                return []

        if not client:
            return []

        active_workers = []
        try:
            keys = client.keys("seo_agent:worker:*")
            for k in keys:
                raw = client.get(k)
                if raw:
                    active_workers.append(json.loads(raw))
        except Exception as e:
            logger.warning(f"Failed to fetch active workers from Redis: {e}")
        return active_workers
