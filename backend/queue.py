import time
import json
import logging
import threading
import queue as pyqueue
from typing import Dict, Any, Callable, Optional, List, Union, Tuple
from backend.config import settings
from backend.cache import get_redis_client

logger = logging.getLogger("seo_agent.queue")

PRIORITY_MAP = {
    "high": 1,
    "normal": 5,
    "low": 10,
}

def parse_priority(priority: Union[str, int]) -> Tuple[str, int]:
    """Parse priority into string ('high', 'normal', 'low') and integer score (1..10)."""
    if isinstance(priority, int):
        if priority <= 3:
            return "high", priority
        elif priority >= 8:
            return "low", priority
        else:
            return "normal", priority
    elif isinstance(priority, str):
        p_lower = priority.lower()
        if p_lower in PRIORITY_MAP:
            return p_lower, PRIORITY_MAP[p_lower]
    return "normal", 5


class RedisJobQueue:
    """Production Redis Queue manager supporting Priority Queueing, Anti-Starvation Scheduling,
    Batch Processing, Job Grouping, Trace Propagation, and Thread Fallback."""

    def __init__(self, queue_name: str = "seo_agent:jobs"):
        self.queue_name = queue_name
        self._redis_client = None
        self._redis_connected = False
        self._in_memory_queue: pyqueue.PriorityQueue = pyqueue.PriorityQueue()
        self._in_memory_groups: Dict[str, set] = {}
        self._in_memory_lock = threading.Lock()
        self._pop_counter = 0
        self._counter_lock = threading.Lock()
        self._init_redis()

    def _init_redis(self):
        client = get_redis_client()
        if client is not None:
            try:
                client.ping()
                self._redis_client = client
                self._redis_connected = True
                logger.info(f"Redis Queue connected via connection pool.")
            except Exception as e:
                logger.warning(f"Redis Queue connection failed ({e}). Operating in thread fallback mode.")
                self._redis_client = None
                self._redis_connected = False

    def is_redis_active(self) -> bool:
        if settings.USE_REDIS_QUEUE and self._redis_connected and self._redis_client is not None:
            return True
        if settings.USE_REDIS_QUEUE and not self._redis_connected:
            self._init_redis()
            return self._redis_connected
        return False

    def enqueue(
        self,
        job_type: str,
        job_id: int,
        user_id: int,
        target_func: Optional[Callable] = None,
        priority: Union[str, int] = "normal",
        group_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """Enqueues a job with priority level, group_id, and trace_id for cross-worker propagation."""
        if "priority" in kwargs and priority == "normal":
            priority = kwargs.pop("priority")
        if "group_id" in kwargs and group_id is None:
            group_id = kwargs.pop("group_id")
        if "trace_id" in kwargs and trace_id is None:
            trace_id = kwargs.pop("trace_id")

        pri_str, pri_val = parse_priority(priority)
        params = kwargs.get("params", kwargs) if "params" in kwargs and len(kwargs) == 1 else kwargs
        effective_trace_id = trace_id or f"trace-job-{job_id}"

        payload = {
            "job_type": job_type,
            "job_id": job_id,
            "user_id": user_id,
            "priority": pri_str,
            "priority_val": pri_val,
            "group_id": group_id,
            "trace_id": effective_trace_id,
            "params": params,
            "enqueued_at": time.time()
        }

        if self.is_redis_active():
            try:
                task_data = json.dumps(payload)
                target_key = f"{self.queue_name}:{pri_str}"
                self._redis_client.rpush(target_key, task_data)

                if group_id:
                    self._redis_client.sadd(f"{self.queue_name}:group:{group_id}", job_id)
                    self._redis_client.sadd(f"{self.queue_name}:groups", group_id)

                logger.info(f"Enqueued job #{job_id} ({job_type}, priority={pri_str}, trace_id={effective_trace_id}) to Redis '{target_key}'")
                return f"redis:{job_id}"
            except Exception as e:
                logger.warning(f"Failed to push job #{job_id} to Redis queue ({e}). Running via thread fallback.")
                self._redis_connected = False

        # In-memory fallback
        with self._in_memory_lock:
            self._in_memory_queue.put((pri_val, job_id, payload, target_func))
            if group_id:
                if group_id not in self._in_memory_groups:
                    self._in_memory_groups[group_id] = set()
                self._in_memory_groups[group_id].add(job_id)

        if target_func:
            thread = threading.Thread(
                target=target_func,
                kwargs={"job_id": job_id, "user_id": user_id, "trace_id": effective_trace_id, **params},
                daemon=True
            )
            thread.start()

        logger.info(f"Dispatched job #{job_id} ({job_type}) via background thread worker.")
        return f"thread:{job_id}"

    def enqueue_batch(self, jobs: List[Dict[str, Any]]) -> List[str]:
        """Atomic pipeline batch enqueue for multiple jobs with trace propagation."""
        if not jobs:
            return []

        results = []
        if self.is_redis_active():
            try:
                pipe = self._redis_client.pipeline(transaction=False)
                for j in jobs:
                    j_type = j["job_type"]
                    j_id = j["job_id"]
                    u_id = j["user_id"]
                    pri = j.get("priority", "normal")
                    grp = j.get("group_id", None)
                    t_id = j.get("trace_id") or f"trace-job-{j_id}"
                    params = j.get("params", j.get("kwargs", {}))

                    pri_str, pri_val = parse_priority(pri)
                    payload = {
                        "job_type": j_type,
                        "job_id": j_id,
                        "user_id": u_id,
                        "priority": pri_str,
                        "priority_val": pri_val,
                        "group_id": grp,
                        "trace_id": t_id,
                        "params": params,
                        "enqueued_at": time.time()
                    }
                    task_data = json.dumps(payload)
                    target_key = f"{self.queue_name}:{pri_str}"
                    pipe.rpush(target_key, task_data)

                    if grp:
                        pipe.sadd(f"{self.queue_name}:group:{grp}", j_id)
                        pipe.sadd(f"{self.queue_name}:groups", grp)

                    results.append(f"redis:{j_id}")

                pipe.execute()
                logger.info(f"Batch enqueued {len(jobs)} jobs to Redis queue.")
                return results
            except Exception as e:
                logger.warning(f"Batch enqueue pipeline failed ({e}). Falling back to individual enqueue.")
                self._redis_connected = False

        results = []
        for j in jobs:
            res = self.enqueue(
                job_type=j["job_type"],
                job_id=j["job_id"],
                user_id=j["user_id"],
                target_func=j.get("target_func"),
                priority=j.get("priority", "normal"),
                group_id=j.get("group_id"),
                trace_id=j.get("trace_id"),
                **j.get("params", j.get("kwargs", {}))
            )
            results.append(res)
        return results

    def pop_next_job(self, timeout: int = 2) -> Optional[Dict[str, Any]]:
        """Pops the next job respecting priority order ('high' -> 'normal' -> 'low')
        with anti-starvation fair round-robin scheduling."""
        if self.is_redis_active():
            try:
                with self._counter_lock:
                    self._pop_counter += 1
                    pop_count = self._pop_counter

                # Anti-starvation check: Every 5th pop attempt checks normal/low/default first via non-blocking LPOP
                if pop_count % 5 == 0:
                    for fallback_key in [
                        f"{self.queue_name}:normal",
                        f"{self.queue_name}:low",
                        self.queue_name,
                        f"{self.queue_name}:high"
                    ]:
                        raw_item = self._redis_client.lpop(fallback_key)
                        if raw_item:
                            return json.loads(raw_item)

                # Standard priority order
                keys = [
                    f"{self.queue_name}:high",
                    f"{self.queue_name}:normal",
                    f"{self.queue_name}:low",
                    self.queue_name
                ]
                raw = self._redis_client.blpop(keys, timeout=timeout)
                if raw:
                    _, task_data = raw
                    return json.loads(task_data)
            except Exception as e:
                logger.warning(f"Redis pop_next_job failed: {e}")
                self._redis_connected = False
                return None

        with self._in_memory_lock:
            if not self._in_memory_queue.empty():
                _, _, payload, _ = self._in_memory_queue.get()
                return payload
        return None

    def pop_batch(self, batch_size: int = 5) -> List[Dict[str, Any]]:
        """Pops a batch of up to `batch_size` jobs ordered by priority."""
        batch = []
        for _ in range(batch_size):
            job = self.pop_next_job(timeout=0)
            if not job:
                break
            batch.append(job)
        return batch

    def get_group_jobs(self, group_id: str) -> List[int]:
        """Returns list of job_ids belonging to a group."""
        if self.is_redis_active():
            try:
                members = self._redis_client.smembers(f"{self.queue_name}:group:{group_id}")
                return [int(m) for m in members] if members else []
            except Exception:
                self._redis_connected = False
        with self._in_memory_lock:
            return list(self._in_memory_groups.get(group_id, set()))

    def cancel_group(self, group_id: str) -> int:
        """Purges group metadata from queue."""
        job_ids = self.get_group_jobs(group_id)
        if self.is_redis_active():
            try:
                self._redis_client.delete(f"{self.queue_name}:group:{group_id}")
                self._redis_client.srem(f"{self.queue_name}:groups", group_id)
            except Exception:
                self._redis_connected = False
        with self._in_memory_lock:
            self._in_memory_groups.pop(group_id, None)
        return len(job_ids)

    def get_queue_length(self) -> int:
        if self.is_redis_active():
            try:
                total = 0
                for suffix in ["high", "normal", "low"]:
                    total += self._redis_client.llen(f"{self.queue_name}:{suffix}")
                total += self._redis_client.llen(self.queue_name)
                return total
            except Exception:
                self._redis_connected = False
        with self._in_memory_lock:
            return self._in_memory_queue.qsize()

    def get_queue_stats(self) -> Dict[str, Any]:
        """Provides comprehensive queue metrics per priority level, groups, and scaling hints."""
        stats = {
            "queue_name": self.queue_name,
            "is_redis_active": self.is_redis_active(),
            "total_queued": 0,
            "queued_by_priority": {"high": 0, "normal": 0, "low": 0, "default": 0},
            "active_groups": [],
            "group_count": 0
        }

        if self.is_redis_active():
            try:
                high_len = self._redis_client.llen(f"{self.queue_name}:high")
                norm_len = self._redis_client.llen(f"{self.queue_name}:normal")
                low_len = self._redis_client.llen(f"{self.queue_name}:low")
                def_len = self._redis_client.llen(self.queue_name)

                stats["queued_by_priority"] = {
                    "high": high_len,
                    "normal": norm_len,
                    "low": low_len,
                    "default": def_len
                }
                stats["total_queued"] = high_len + norm_len + low_len + def_len

                groups = list(self._redis_client.smembers(f"{self.queue_name}:groups") or [])
                stats["active_groups"] = groups
                stats["group_count"] = len(groups)
            except Exception as e:
                logger.warning(f"Error fetching Redis queue stats: {e}")
                self._redis_connected = False
        else:
            with self._in_memory_lock:
                stats["total_queued"] = self._in_memory_queue.qsize()
                stats["queued_by_priority"]["normal"] = stats["total_queued"]
                stats["active_groups"] = list(self._in_memory_groups.keys())
                stats["group_count"] = len(self._in_memory_groups)

        stats["scaling_hints"] = self.get_scaling_hints(total_queued=stats["total_queued"])
        return stats

    def get_scaling_hints(self, total_queued: Optional[int] = None, current_concurrency: int = 5, active_jobs: int = 0) -> Dict[str, Any]:
        """Computes automatic scaling hints for workers based on queue pressure."""
        if total_queued is None:
            total_queued = self.get_queue_length()

        if total_queued > current_concurrency * 2:
            recommended_concurrency = min(20, current_concurrency + 5)
            return {
                "action": "scale_up",
                "recommended_concurrency": recommended_concurrency,
                "reason": f"High queue backlog ({total_queued} jobs pending vs concurrency {current_concurrency}).",
                "pressure_index": round(total_queued / max(1, current_concurrency), 2)
            }
        elif total_queued > 0 and active_jobs >= current_concurrency:
            recommended_concurrency = min(20, current_concurrency + 2)
            return {
                "action": "scale_up",
                "recommended_concurrency": recommended_concurrency,
                "reason": f"Worker capacity fully saturated ({active_jobs} running, {total_queued} queued).",
                "pressure_index": round((total_queued + active_jobs) / max(1, current_concurrency), 2)
            }
        elif total_queued == 0 and active_jobs < (current_concurrency // 2) and current_concurrency > 2:
            recommended_concurrency = max(2, current_concurrency - 2)
            return {
                "action": "scale_down",
                "recommended_concurrency": recommended_concurrency,
                "reason": f"Worker underutilized ({active_jobs} active threads out of {current_concurrency}).",
                "pressure_index": round(active_jobs / max(1, current_concurrency), 2)
            }
        else:
            return {
                "action": "maintain",
                "recommended_concurrency": current_concurrency,
                "reason": f"Queue workload balanced ({total_queued} queued, {active_jobs} active).",
                "pressure_index": round((total_queued + active_jobs) / max(1, current_concurrency), 2)
            }


# Global singleton job queue
job_queue = RedisJobQueue()
