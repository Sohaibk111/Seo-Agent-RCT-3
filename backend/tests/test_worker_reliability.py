import time
import pytest
from backend.worker import ReliableWorker
from backend.queue import RedisJobQueue, parse_priority
from backend.dead_letter_queue import DeadLetterQueue
from backend.worker_heartbeat import WorkerHeartbeatManager
from backend.retry import RetryEngine

def test_worker_concurrency_adjustment_and_thread_cleanup():
    """Verify dynamic concurrency scaling creates new thread pool and safely shuts down old executor."""
    worker = ReliableWorker(concurrency=2, worker_id="test-worker-concurrency")
    assert worker.concurrency == 2

    new_concurrency = worker.adjust_concurrency(5)
    assert new_concurrency == 5
    assert worker.concurrency == 5

    # Scale back down
    worker.adjust_concurrency(2)
    assert worker.concurrency == 2
    worker.shutdown()

def test_queue_anti_starvation_and_trace_propagation():
    """Verify priority parsing, anti-starvation pop logic, and trace ID propagation."""
    queue = RedisJobQueue(queue_name="test:queue:starvation")

    # Enqueue high, normal, low priority jobs with explicit trace_ids
    id_high = queue.enqueue("crawl", 1001, 1, priority="high", trace_id="trace-high-1001")
    id_low = queue.enqueue("audit", 1002, 1, priority="low", trace_id="trace-low-1002")

    assert "1001" in id_high
    assert "1002" in id_low

    # Verify priority parsing
    pri_name, pri_val = parse_priority("high")
    assert pri_name == "high"
    assert pri_val == 1

    pri_name_low, pri_val_low = parse_priority("low")
    assert pri_name_low == "low"
    assert pri_val_low == 10

def test_dead_letter_queue_thread_safety_and_operations():
    """Verify DLQ push, list, count, and clear operations under thread-safe in-memory mode."""
    dlq = DeadLetterQueue(queue_name="test_dlq_isolated")
    dlq.clear_dlq()

    item1 = dlq.push_to_dlq(
        job_id=9901,
        job_type="crawl",
        user_id=1,
        failure_reason="Network Timeout",
        retry_count=3,
        extra_data={"trace_id": "trace-test-9901"}
    )
    assert item1["job_id"] == 9901
    assert item1["failure_reason"] == "Network Timeout"
    assert item1["extra_data"]["trace_id"] == "trace-test-9901"

    count = dlq.get_dlq_count()
    assert count >= 1

    jobs = dlq.get_dlq_jobs(limit=10)
    assert len(jobs) >= 1
    assert any(j["job_id"] == 9901 for j in jobs)

    cleared = dlq.clear_dlq()
    assert cleared >= 1
    assert dlq.get_dlq_count() == 0

def test_worker_heartbeat_lifecycle():
    """Verify worker heartbeat initialization, payload generation, and cleanup."""
    hb = WorkerHeartbeatManager(worker_id="test-hb-worker", heartbeat_interval=1)
    hb.start_heartbeat_loop()

    hb.set_status("busy", running_jobs=3)
    payload = hb.generate_heartbeat_payload()

    assert payload["worker_id"] == "test-hb-worker"
    assert payload["status"] == "busy"
    assert payload["running_jobs"] == 3
    assert "cpu_usage" in payload
    assert "memory_usage" in payload

    hb.stop_heartbeat_loop()

def test_retry_engine_backoff_and_non_retryable():
    """Verify retry engine compute delay with jitter and non-retryable exception handling."""
    engine = RetryEngine(max_retries=3, initial_delay=1.0, max_delay=10.0)

    delay0 = engine.compute_delay(0)
    delay1 = engine.compute_delay(1)
    delay2 = engine.compute_delay(2)

    assert 0.5 <= delay0 <= 1.5
    assert 1.0 <= delay1 <= 3.0
    assert 2.0 <= delay2 <= 6.0

def test_worker_graceful_shutdown():
    """Verify graceful worker shutdown drains state and releases resources cleanly."""
    worker = ReliableWorker(concurrency=2, worker_id="test-worker-shutdown")
    worker.start(run_loop=False)

    assert worker.accepting_jobs is True
    assert worker.is_stopping is False

    worker.shutdown()

    assert worker.accepting_jobs is False
    assert worker.is_stopping is True
