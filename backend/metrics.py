import time
import threading
from typing import Dict, Any, List

class MetricsRegistry:
    """Prometheus Metrics Manager suitable for Kubernetes and Cloud deployment."""

    def __init__(self):
        self._lock = threading.Lock()

        # Counter: request_count & seo_requests_total{method, endpoint, status_code}
        self.request_counts: Dict[str, int] = {}
        # Summary/Total: request_duration_seconds & seo_request_duration_seconds
        self.request_duration_sum: float = 0.0
        self.request_duration_count: int = 0

        # Gauges
        self._active_jobs: int = 0
        self._queue_length: int = 0
        self._active_users: int = 0
        self._redis_latency: float = 0.0
        self._database_latency: float = 0.0
        self._worker_memory_usage: float = 0.0
        self._worker_cpu_usage: float = 0.0
        self._worker_utilization: float = 0.0
        self._worker_concurrency: int = 5
        self._worker_active: int = 0
        self._worker_jobs_running: int = 0

        # Job Durations (Summaries)
        self.crawl_duration_sum: float = 0.0
        self.crawl_duration_count: int = 0
        self.audit_duration_sum: float = 0.0
        self.audit_duration_count: int = 0
        self.keyword_duration_sum: float = 0.0
        self.keyword_duration_count: int = 0
        self.rank_duration_sum: float = 0.0
        self.rank_duration_count: int = 0
        self.ai_duration_sum: float = 0.0
        self.ai_duration_count: int = 0
        self.queue_processing_time_sum: float = 0.0
        self.queue_processing_time_count: int = 0

        # Cache & DB Counters
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.db_query_duration_sum: float = 0.0
        self.db_query_duration_count: int = 0

        # Worker Reliability Counters
        self.worker_jobs_completed: int = 0
        self.worker_jobs_failed: int = 0
        self.worker_restarts: int = 0
        self.dead_letter_jobs: int = 0
        self.retry_attempts: int = 0
        self.retry_failures: int = 0
        self._worker_start_time: float = time.time()

    def set_worker_active(self, active: int):
        with self._lock:
            self._worker_active = active

    def set_worker_jobs_running(self, count: int):
        with self._lock:
            self._worker_jobs_running = max(0, count)

    def inc_worker_jobs_completed(self, delta: int = 1):
        with self._lock:
            self.worker_jobs_completed += delta

    def inc_worker_jobs_failed(self, delta: int = 1):
        with self._lock:
            self.worker_jobs_failed += delta

    def inc_worker_restarts(self, delta: int = 1):
        with self._lock:
            self.worker_restarts += delta

    def inc_dead_letter_jobs(self, delta: int = 1):
        with self._lock:
            self.dead_letter_jobs += delta

    def set_dead_letter_jobs(self, count: int):
        with self._lock:
            self.dead_letter_jobs = max(0, count)

    def inc_retry_attempts(self, delta: int = 1):
        with self._lock:
            self.retry_attempts += delta

    def inc_retry_failures(self, delta: int = 1):
        with self._lock:
            self.retry_failures += delta

    def inc_cache_hit(self):
        with self._lock:
            self.cache_hits += 1

    def inc_cache_miss(self):
        with self._lock:
            self.cache_misses += 1

    def set_active_users(self, count: int):
        with self._lock:
            self._active_users = max(0, count)

    def set_redis_latency(self, latency_seconds: float):
        with self._lock:
            self._redis_latency = max(0.0, latency_seconds)

    def set_database_latency(self, latency_seconds: float):
        with self._lock:
            self._database_latency = max(0.0, latency_seconds)

    def set_worker_memory_usage(self, mb: float):
        with self._lock:
            self._worker_memory_usage = max(0.0, mb)

    def set_worker_cpu_usage(self, percent: float):
        with self._lock:
            self._worker_cpu_usage = max(0.0, percent)

    def observe_db_query_duration(self, duration_seconds: float):
        with self._lock:
            self.db_query_duration_sum += duration_seconds
            self.db_query_duration_count += 1
            self._database_latency = duration_seconds

    def set_worker_utilization(self, percent: float):
        with self._lock:
            self._worker_utilization = max(0.0, min(100.0, percent))

    def set_worker_concurrency(self, concurrency: int):
        with self._lock:
            self._worker_concurrency = max(1, concurrency)

    def inc_request_count(self, method: str, endpoint: str, status_code: int):
        key = f'{method}:{endpoint}:{status_code}'
        with self._lock:
            self.request_counts[key] = self.request_counts.get(key, 0) + 1

    def observe_request_duration(self, duration_seconds: float):
        with self._lock:
            self.request_duration_sum += duration_seconds
            self.request_duration_count += 1

    def set_active_jobs(self, count: int):
        with self._lock:
            self._active_jobs = count

    def inc_active_jobs(self, delta: int = 1):
        with self._lock:
            self._active_jobs = max(0, self._active_jobs + delta)

    def set_queue_length(self, count: int):
        with self._lock:
            self._queue_length = count

    def observe_crawl_duration(self, duration_seconds: float):
        with self._lock:
            self.crawl_duration_sum += duration_seconds
            self.crawl_duration_count += 1

    def observe_audit_duration(self, duration_seconds: float):
        with self._lock:
            self.audit_duration_sum += duration_seconds
            self.audit_duration_count += 1

    def observe_keyword_duration(self, duration_seconds: float):
        with self._lock:
            self.keyword_duration_sum += duration_seconds
            self.keyword_duration_count += 1

    def observe_rank_duration(self, duration_seconds: float):
        with self._lock:
            self.rank_duration_sum += duration_seconds
            self.rank_duration_count += 1

    def observe_ai_duration(self, duration_seconds: float):
        with self._lock:
            self.ai_duration_sum += duration_seconds
            self.ai_duration_count += 1

    def observe_queue_processing_time(self, duration_seconds: float):
        with self._lock:
            self.queue_processing_time_sum += duration_seconds
            self.queue_processing_time_count += 1

    def generate_prometheus_text(self) -> str:
        with self._lock:
            lines = []

            # Total requests counters
            lines.append("# HELP seo_requests_total Total number of HTTP API requests.")
            lines.append("# TYPE seo_requests_total counter")
            total_reqs = sum(self.request_counts.values())
            lines.append(f"seo_requests_total {total_reqs}")

            lines.append("# HELP request_count Total number of HTTP requests by method, endpoint, status.")
            lines.append("# TYPE request_count counter")
            if not self.request_counts:
                lines.append('request_count{method="GET",endpoint="/",status_code="200"} 0')
            else:
                for k, v in self.request_counts.items():
                    method, endpoint, status_code = k.split(":", 2)
                    lines.append(f'request_count{{method="{method}",endpoint="{endpoint}",status_code="{status_code}"}} {v}')

            # Request duration summary
            lines.append("# HELP seo_request_duration_seconds Request duration in seconds.")
            lines.append("# TYPE seo_request_duration_seconds summary")
            lines.append(f'seo_request_duration_seconds_sum {self.request_duration_sum:.6f}')
            lines.append(f'seo_request_duration_seconds_count {self.request_duration_count}')

            lines.append("# HELP request_duration_seconds Request duration summary.")
            lines.append("# TYPE request_duration_seconds summary")
            lines.append(f'request_duration_seconds_sum {self.request_duration_sum:.6f}')
            lines.append(f'request_duration_seconds_count {self.request_duration_count}')

            # Active users & queue length / queue size
            lines.append("# HELP active_users Current count of active authenticated users.")
            lines.append("# TYPE active_users gauge")
            lines.append(f'active_users {self._active_users}')

            lines.append("# HELP worker_queue_size Pending background jobs in queue.")
            lines.append("# TYPE worker_queue_size gauge")
            lines.append(f'worker_queue_size {self._queue_length}')

            lines.append("# HELP queue_length Number of pending jobs in queue.")
            lines.append("# TYPE queue_length gauge")
            lines.append(f'queue_length {self._queue_length}')

            lines.append("# HELP active_jobs Number of executing background jobs.")
            lines.append("# TYPE active_jobs gauge")
            lines.append(f'active_jobs {self._active_jobs}')

            # Processing & Task Durations
            lines.append("# HELP queue_processing_time Queue processing duration in seconds.")
            lines.append("# TYPE queue_processing_time summary")
            lines.append(f'queue_processing_time_sum {self.queue_processing_time_sum:.6f}')
            lines.append(f'queue_processing_time_count {self.queue_processing_time_count}')

            lines.append("# HELP crawl_duration Website crawler execution duration in seconds.")
            lines.append("# TYPE crawl_duration summary")
            lines.append(f'crawl_duration_sum {self.crawl_duration_sum:.6f}')
            lines.append(f'crawl_duration_count {self.crawl_duration_count}')
            lines.append(f'crawl_duration_seconds_sum {self.crawl_duration_sum:.6f}')

            lines.append("# HELP audit_duration Technical audit execution duration in seconds.")
            lines.append("# TYPE audit_duration summary")
            lines.append(f'audit_duration_sum {self.audit_duration_sum:.6f}')
            lines.append(f'audit_duration_count {self.audit_duration_count}')
            lines.append(f'audit_duration_seconds_sum {self.audit_duration_sum:.6f}')

            lines.append("# HELP keyword_duration Keyword research job duration in seconds.")
            lines.append("# TYPE keyword_duration summary")
            lines.append(f'keyword_duration_sum {self.keyword_duration_sum:.6f}')
            lines.append(f'keyword_duration_count {self.keyword_duration_count}')

            lines.append("# HELP rank_duration Rank tracking job duration in seconds.")
            lines.append("# TYPE rank_duration summary")
            lines.append(f'rank_duration_sum {self.rank_duration_sum:.6f}')
            lines.append(f'rank_duration_count {self.rank_duration_count}')

            lines.append("# HELP ai_duration Gemini AI recommendation duration in seconds.")
            lines.append("# TYPE ai_duration summary")
            lines.append(f'ai_duration_sum {self.ai_duration_sum:.6f}')
            lines.append(f'ai_duration_count {self.ai_duration_count}')

            # Latencies
            lines.append("# HELP redis_latency Redis ping and operation latency in seconds.")
            lines.append("# TYPE redis_latency gauge")
            lines.append(f'redis_latency {self._redis_latency:.6f}')

            lines.append("# HELP database_latency Database query execution latency in seconds.")
            lines.append("# TYPE database_latency gauge")
            lines.append(f'database_latency {self._database_latency:.6f}')

            # Cache Ratios & Counts
            total_cache_ops = self.cache_hits + self.cache_misses
            hit_ratio = (self.cache_hits / total_cache_ops) if total_cache_ops > 0 else 0.0
            miss_ratio = (self.cache_misses / total_cache_ops) if total_cache_ops > 0 else 0.0

            lines.append("# HELP cache_hit_ratio Ratio of cache hits over total cache queries.")
            lines.append("# TYPE cache_hit_ratio gauge")
            lines.append(f'cache_hit_ratio {hit_ratio:.4f}')

            lines.append("# HELP cache_miss_ratio Ratio of cache misses over total cache queries.")
            lines.append("# TYPE cache_miss_ratio gauge")
            lines.append(f'cache_miss_ratio {miss_ratio:.4f}')

            lines.append("# HELP cache_hits_total Total number of cache hits.")
            lines.append("# TYPE cache_hits_total counter")
            lines.append(f'cache_hits_total {self.cache_hits}')

            lines.append("# HELP cache_misses_total Total number of cache misses.")
            lines.append("# TYPE cache_misses_total counter")
            lines.append(f'cache_misses_total {self.cache_misses}')

            # Jobs Success / Failure counters
            lines.append("# HELP successful_jobs Total successfully processed background jobs.")
            lines.append("# TYPE successful_jobs counter")
            lines.append(f'successful_jobs {self.worker_jobs_completed}')
            lines.append(f'worker_jobs_completed {self.worker_jobs_completed}')

            lines.append("# HELP failed_jobs Total failed background jobs.")
            lines.append("# TYPE failed_jobs counter")
            lines.append(f'failed_jobs {self.worker_jobs_failed}')
            lines.append(f'worker_jobs_failed {self.worker_jobs_failed}')

            # Worker Resource Metrics
            lines.append("# HELP worker_memory_usage Worker process memory usage in MB.")
            lines.append("# TYPE worker_memory_usage gauge")
            lines.append(f'worker_memory_usage {self._worker_memory_usage:.2f}')

            lines.append("# HELP worker_cpu_usage Worker process CPU utilization percentage.")
            lines.append("# TYPE worker_cpu_usage gauge")
            lines.append(f'worker_cpu_usage {self._worker_cpu_usage:.2f}')

            lines.append("# HELP worker_restarts Total worker process restarts.")
            lines.append("# TYPE worker_restarts counter")
            lines.append(f'worker_restarts {self.worker_restarts}')

            lines.append("# HELP worker_active Whether worker is active (1/0).")
            lines.append("# TYPE worker_active gauge")
            lines.append(f'worker_active {self._worker_active}')

            lines.append("# HELP worker_jobs_running Number of worker jobs running.")
            lines.append("# TYPE worker_jobs_running gauge")
            lines.append(f'worker_jobs_running {self._worker_jobs_running}')

            lines.append("# HELP dead_letter_jobs Total dead letter queue jobs.")
            lines.append("# TYPE dead_letter_jobs gauge")
            lines.append(f'dead_letter_jobs {self.dead_letter_jobs}')

            lines.append("# HELP retry_attempts Total job retry attempts.")
            lines.append("# TYPE retry_attempts counter")
            lines.append(f'retry_attempts {self.retry_attempts}')

            lines.append("# HELP retry_failures Total job execution retry failures.")
            lines.append("# TYPE retry_failures counter")
            lines.append(f'retry_failures {self.retry_failures}')

            uptime = time.time() - self._worker_start_time
            lines.append("# HELP worker_uptime_seconds Worker process uptime in seconds.")
            lines.append("# TYPE worker_uptime_seconds gauge")
            lines.append(f'worker_uptime_seconds {uptime:.2f}')

            return "\n".join(lines) + "\n"


metrics_registry = MetricsRegistry()
