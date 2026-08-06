import os
import sys
import time
import json
import signal
import logging
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Any, Callable, Optional, List

from backend.config import settings
from backend.database.database import SessionLocal, engine
from backend.database import crud
from backend.database.models import Job
from backend.services.job_service import JobService
from backend.retry import RetryEngine, DEFAULT_NON_RETRYABLE
from backend.dead_letter_queue import dead_letter_queue
from backend.worker_heartbeat import WorkerHeartbeatManager
from backend.metrics import metrics_registry
from backend.queue import job_queue
from backend.logging_config import logger as root_logger

logger = logging.getLogger("seo_agent.worker")

class ReliableWorker:
    """Enterprise Reliable Worker with Dynamic Concurrency, Priority Queueing,
    Thread Cleanup, Memory Safety, Trace Propagation, and Graceful Shutdown."""

    def __init__(
        self,
        concurrency: Optional[int] = None,
        queue_name: str = "seo_agent:jobs",
        worker_id: Optional[str] = None,
    ):
        self.concurrency = concurrency if concurrency is not None else settings.WORKER_CONCURRENCY
        self.queue_name = queue_name

        self.heartbeat_manager = WorkerHeartbeatManager(worker_id=worker_id)
        self.worker_id = self.heartbeat_manager.worker_id

        self.retry_engine = RetryEngine(
            max_retries=settings.MAX_JOB_RETRIES,
            initial_delay=settings.RETRY_BASE_DELAY,
            max_delay=settings.RETRY_MAX_DELAY,
            non_retryable_exceptions=DEFAULT_NON_RETRYABLE,
        )

        self.executor = ThreadPoolExecutor(max_workers=self.concurrency, thread_name_prefix="SEO-Worker")
        self._executors_to_clean: List[ThreadPoolExecutor] = []
        self._running_jobs_lock = threading.Lock()
        self._running_jobs: Dict[int, Dict[str, Any]] = {}

        self.accepting_jobs = True
        self.is_stopping = False

        self._redis_client = None
        self._init_redis()
        self._register_signal_handlers()

    def _init_redis(self):
        if settings.REDIS_URL:
            try:
                import redis
                client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1.0)
                client.ping()
                self._redis_client = client
            except Exception as e:
                logger.warning(f"Worker Redis connection warning ({e}). Operating in thread fallback mode.")
                self._redis_client = None

    def _register_signal_handlers(self):
        try:
            signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
            signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        except (ValueError, AttributeError):
            pass

    def _handle_shutdown_signal(self, signum, frame):
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        logger.info(f"Received shutdown signal {sig_name}. Initiating graceful worker shutdown...")
        self.shutdown()

    def adjust_concurrency(self, new_concurrency: int) -> int:
        """Dynamically scales worker thread concurrency up or down at runtime with thread cleanup."""
        target = max(1, min(100, new_concurrency))
        if target == self.concurrency:
            return self.concurrency

        logger.info(f"Adjusting worker {self.worker_id} concurrency from {self.concurrency} to {target}.")
        self.concurrency = target

        # Replace executor smoothly with thread cleanup
        old_executor = self.executor
        self.executor = ThreadPoolExecutor(max_workers=self.concurrency, thread_name_prefix=f"SEO-Worker-{target}")
        
        try:
            old_executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            old_executor.shutdown(wait=False)

        metrics_registry.set_worker_concurrency(self.concurrency)
        return self.concurrency

    def auto_tune_concurrency(self) -> Dict[str, Any]:
        """Automatically tunes concurrency based on queue backlog pressure and worker utilization."""
        with self._running_jobs_lock:
            active_count = len(self._running_jobs)

        scaling_hints = job_queue.get_scaling_hints(
            current_concurrency=self.concurrency,
            active_jobs=active_count
        )

        if scaling_hints["action"] != "maintain":
            new_target = scaling_hints["recommended_concurrency"]
            self.adjust_concurrency(new_target)

        return scaling_hints

    def start(self, run_loop: bool = True):
        logger.info(
            f"Starting ReliableWorker {self.worker_id} with concurrency={self.concurrency}...",
            extra={"worker_id": self.worker_id}
        )
        self.heartbeat_manager.start_heartbeat_loop()

        if settings.JOB_RECOVERY_ENABLED:
            self.recover_interrupted_jobs()

        if run_loop:
            self.run_worker_loop()

    def run_worker_loop(self):
        logger.info(f"Worker {self.worker_id} main event loop started.")
        while self.accepting_jobs and not self.is_stopping:
            try:
                # Metrics update
                with self._running_jobs_lock:
                    active_count = len(self._running_jobs)

                utilization = (active_count / self.concurrency) * 100.0 if self.concurrency > 0 else 0.0
                metrics_registry.set_worker_utilization(utilization)
                metrics_registry.set_worker_jobs_running(active_count)
                self.heartbeat_manager.set_status("busy" if active_count > 0 else "idle", running_jobs=active_count)

                # Fetch priority job payload from queue if under concurrency threshold
                available_slots = self.concurrency - active_count
                if available_slots > 0:
                    batch = job_queue.pop_batch(batch_size=min(available_slots, 5))
                    if batch:
                        for job_payload in batch:
                            self._dispatch_job_payload(job_payload)
                    else:
                        time.sleep(0.2)
                else:
                    time.sleep(0.2)

            except Exception as e:
                if not self.is_stopping:
                    logger.error(f"Error in worker main loop: {e}", exc_info=True)
                time.sleep(0.5)

    def _dispatch_job_payload(self, payload: Dict[str, Any]):
        try:
            job_id = payload.get("job_id")
            job_type = payload.get("job_type")
            user_id = payload.get("user_id")
            group_id = payload.get("group_id")
            trace_id = payload.get("trace_id")
            kwargs = payload.get("params", {})

            if not job_id or not job_type or not user_id:
                logger.error(f"Invalid job payload received: {payload}")
                return

            self.submit_job(
                job_id=job_id,
                job_type=job_type,
                user_id=user_id,
                group_id=group_id,
                trace_id=trace_id,
                kwargs=kwargs
            )
        except Exception as e:
            logger.error(f"Failed to parse or dispatch job payload: {e}")

    def submit_job(
        self,
        job_id: int,
        job_type: str,
        user_id: int,
        kwargs: Dict[str, Any],
        group_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ):
        if not self.accepting_jobs:
            logger.warning(f"Worker is stopping. Rejecting job submission for #{job_id}.")
            return

        with self._running_jobs_lock:
            self._running_jobs[job_id] = {
                "job_type": job_type,
                "user_id": user_id,
                "group_id": group_id,
                "trace_id": trace_id,
                "start_time": time.time(),
            }

        try:
            self.executor.submit(self._execute_job_wrapper, job_id, job_type, user_id, kwargs, trace_id)
        except Exception as exc:
            logger.error(f"Failed to submit job #{job_id} to executor: {exc}")
            with self._running_jobs_lock:
                self._running_jobs.pop(job_id, None)

    def _execute_job_wrapper(
        self,
        job_id: int,
        job_type: str,
        user_id: int,
        kwargs: Dict[str, Any],
        trace_id: Optional[str] = None,
    ):
        start_time = time.time()
        effective_trace_id = trace_id or kwargs.get("trace_id") or f"trace-job-{job_id}"
        logger_extra = {
            "worker_id": self.worker_id,
            "job_id": job_id,
            "user_id": user_id,
            "trace_id": effective_trace_id,
            "retry_number": 0,
        }

        try:
            # Map job_type to target function
            target_func = None
            if job_type == "crawl":
                target_func = JobService.run_crawl_job
            elif job_type == "audit":
                target_func = JobService.run_audit_job
            elif job_type == "keywords":
                target_func = JobService.run_keywords_job
            elif job_type == "rank":
                target_func = JobService.run_rank_job
            else:
                logger.error(f"Unknown job type: {job_type}", extra=logger_extra)
                db_init = SessionLocal()
                try:
                    JobService.fail_job(db_init, job_id, user_id, f"Unknown job type '{job_type}'")
                finally:
                    db_init.close()
                return

            # Initial cancellation check
            db_chk = SessionLocal()
            try:
                if JobService.is_cancelled(db_chk, job_id):
                    logger.info(f"Job #{job_id} was cancelled prior to worker execution.", extra=logger_extra)
                    return
            finally:
                db_chk.close()

            # Execute with Retry Engine and DB connection safety (no open connection during sleep)
            for attempt in range(self.retry_engine.max_retries + 1):
                logger_extra["retry_number"] = attempt
                
                # Check cancellation before attempt
                db = SessionLocal()
                try:
                    if JobService.is_cancelled(db, job_id):
                        logger.info(f"Job #{job_id} cancelled before retry attempt {attempt}.", extra=logger_extra)
                        return

                    target_func(job_id=job_id, user_id=user_id, **kwargs)
                    duration = round(time.time() - start_time, 3)
                    logger_extra["duration"] = duration
                    logger.info(f"Job #{job_id} ({job_type}) completed successfully in {duration}s.", extra=logger_extra)
                    metrics_registry.inc_worker_jobs_completed()
                    return
                except Exception as exc:
                    if isinstance(exc, self.retry_engine.non_retryable_exceptions):
                        logger.warning(f"Non-retryable error in job #{job_id}: {exc}", extra=logger_extra)
                        JobService.fail_job(db, job_id, user_id, str(exc))
                        dead_letter_queue.push_to_dlq(
                            job_id=job_id,
                            job_type=job_type,
                            user_id=user_id,
                            failure_reason=str(exc),
                            stack_trace=traceback.format_exc(),
                            retry_count=attempt,
                            extra_data={"trace_id": effective_trace_id}
                        )
                        metrics_registry.inc_worker_jobs_failed()
                        return

                    if attempt < self.retry_engine.max_retries:
                        metrics_registry.inc_retry_attempts()
                        delay = self.retry_engine.compute_delay(attempt)
                        logger.warning(
                            f"Job #{job_id} attempt {attempt + 1} failed ({exc}). Retrying in {delay:.2f}s...",
                            extra=logger_extra
                        )
                        # Close DB connection before sleeping to prevent connection pool exhaustion!
                        db.close()
                        time.sleep(delay)
                    else:
                        metrics_registry.inc_retry_failures()
                        metrics_registry.inc_worker_jobs_failed()
                        logger.error(
                            f"Job #{job_id} failed permanently after {self.retry_engine.max_retries} retries.",
                            extra=logger_extra
                        )
                        JobService.fail_job(db, job_id, user_id, f"Failed after max retries: {str(exc)}")
                        dead_letter_queue.push_to_dlq(
                            job_id=job_id,
                            job_type=job_type,
                            user_id=user_id,
                            failure_reason=f"Exhausted retries: {str(exc)}",
                            stack_trace=traceback.format_exc(),
                            retry_count=attempt,
                            extra_data={"trace_id": effective_trace_id}
                        )
                finally:
                    db.close()

        except Exception as fatal_e:
            logger.error(f"Fatal unhandled exception in job #{job_id}: {fatal_e}", extra=logger_extra)
            db_err = SessionLocal()
            try:
                JobService.fail_job(db_err, job_id, user_id, str(fatal_e))
            finally:
                db_err.close()
        finally:
            with self._running_jobs_lock:
                self._running_jobs.pop(job_id, None)

    def recover_interrupted_jobs(self):
        """Recover jobs left in running or pending state from crashed or restarted workers."""
        logger.info("Scanning for interrupted or orphan jobs needing recovery...")
        db = SessionLocal()
        try:
            running_jobs = db.query(Job).filter(Job.status == "running").all()
            recovered_count = 0
            for job in running_jobs:
                if job.updated_at:
                    elapsed = (datetime.utcnow() - job.updated_at).total_seconds()
                else:
                    elapsed = 300

                if elapsed > settings.JOB_TIMEOUT_SECONDS:
                    logger.warning(
                        f"Recovering orphan job #{job.id} ({job.job_type}) stuck in running state for {elapsed:.0f}s."
                    )
                    dead_letter_queue.push_to_dlq(
                        job_id=job.id,
                        job_type=job.job_type,
                        user_id=job.user_id,
                        failure_reason=f"Orphan job recovered on worker startup (elapsed: {elapsed:.0f}s)",
                        stack_trace="Worker crash or ungraceful termination recovery",
                        retry_count=settings.MAX_JOB_RETRIES
                    )
                    JobService.fail_job(db, job.id, job.user_id, "Job recovered after worker crash/timeout")
                    recovered_count += 1

            logger.info(f"Job recovery complete. Recovered {recovered_count} orphan jobs.")
        except Exception as e:
            logger.error(f"Job recovery failed: {e}")
        finally:
            db.close()

    def get_worker_stats(self) -> Dict[str, Any]:
        """Returns active worker status, concurrency, utilization, queue stats, and scaling hints."""
        with self._running_jobs_lock:
            running_info = list(self._running_jobs.values())
            active_count = len(self._running_jobs)

        q_stats = job_queue.get_queue_stats()
        utilization = (active_count / self.concurrency * 100.0) if self.concurrency > 0 else 0.0

        return {
            "worker_id": self.worker_id,
            "concurrency": self.concurrency,
            "active_jobs_count": active_count,
            "running_jobs": running_info,
            "utilization_pct": round(utilization, 2),
            "accepting_jobs": self.accepting_jobs,
            "is_stopping": self.is_stopping,
            "queue_stats": q_stats,
            "scaling_hints": job_queue.get_scaling_hints(
                total_queued=q_stats["total_queued"],
                current_concurrency=self.concurrency,
                active_jobs=active_count
            )
        }

    def shutdown(self):
        """Gracefully shuts down worker, waiting for active jobs, stopping heartbeats, and releasing resources."""
        if self.is_stopping:
            return
        self.is_stopping = True
        self.accepting_jobs = False
        logger.info(f"Shutting down worker {self.worker_id} gracefully...")

        # 1. Stop heartbeat
        self.heartbeat_manager.stop_heartbeat_loop()

        # 2. Drain active jobs (wait up to 10 seconds for running jobs to finish)
        drain_deadline = time.time() + 10.0
        while time.time() < drain_deadline:
            with self._running_jobs_lock:
                active = len(self._running_jobs)
            if active == 0:
                break
            time.sleep(0.2)

        # 3. Shutdown ThreadPoolExecutor
        try:
            self.executor.shutdown(wait=True, cancel_futures=False)
        except TypeError:
            self.executor.shutdown(wait=True)

        for handler in root_logger.handlers:
            handler.flush()

        if self._redis_client:
            try:
                self._redis_client.close()
            except Exception:
                pass

        try:
            engine.dispose()
        except Exception:
            pass

        logger.info(f"Worker {self.worker_id} shutdown completed cleanly.")


# Global singleton worker instance
worker_instance = ReliableWorker()

if __name__ == "__main__":
    logger.info("Initializing standalone SEO Agent background worker service...")
    worker_instance.start(run_loop=True)

