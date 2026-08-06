import time
import json
import pytest
from unittest import mock
from backend.queue import RedisJobQueue, parse_priority
from backend.worker import ReliableWorker

def test_parse_priority():
    assert parse_priority("high") == ("high", 1)
    assert parse_priority("normal") == ("normal", 5)
    assert parse_priority("low") == ("low", 10)
    assert parse_priority(1) == ("high", 1)
    assert parse_priority(5) == ("normal", 5)
    assert parse_priority(9) == ("low", 9)
    assert parse_priority("unknown") == ("normal", 5)

def test_priority_queueing_in_memory():
    q = RedisJobQueue(queue_name="test:priority:queue")
    q._redis_connected = False

    # Enqueue low, high, normal
    q.enqueue("audit", job_id=1, user_id=101, priority="low")
    q.enqueue("audit", job_id=2, user_id=101, priority="high")
    q.enqueue("audit", job_id=3, user_id=101, priority="normal")

    p1 = q.pop_next_job()
    assert p1["job_id"] == 2
    assert p1["priority"] == "high"

    p2 = q.pop_next_job()
    assert p2["job_id"] == 3
    assert p2["priority"] == "normal"

    p3 = q.pop_next_job()
    assert p3["job_id"] == 1
    assert p3["priority"] == "low"

def test_batch_enqueue_and_pop():
    q = RedisJobQueue(queue_name="test:batch:queue")
    q._redis_connected = False

    batch_jobs = [
        {"job_type": "crawl", "job_id": 10, "user_id": 1, "priority": "high", "params": {"url": "https://a.com"}},
        {"job_type": "crawl", "job_id": 11, "user_id": 1, "priority": "normal", "params": {"url": "https://b.com"}},
        {"job_type": "crawl", "job_id": 12, "user_id": 1, "priority": "low", "params": {"url": "https://c.com"}},
    ]

    res = q.enqueue_batch(batch_jobs)
    assert len(res) == 3

    popped_batch = q.pop_batch(batch_size=2)
    assert len(popped_batch) == 2
    assert popped_batch[0]["job_id"] == 10
    assert popped_batch[1]["job_id"] == 11

def test_job_grouping():
    q = RedisJobQueue(queue_name="test:group:queue")
    q._redis_connected = False

    group_id = "grp-batch-99"
    q.enqueue("rank", job_id=201, user_id=2, group_id=group_id)
    q.enqueue("rank", job_id=202, user_id=2, group_id=group_id)

    jobs = q.get_group_jobs(group_id)
    assert set(jobs) == {201, 202}

    canceled = q.cancel_group(group_id)
    assert canceled == 2
    assert q.get_group_jobs(group_id) == []

def test_queue_stats_and_scaling_hints():
    q = RedisJobQueue(queue_name="test:stats:queue")
    q._redis_connected = False

    stats = q.get_queue_stats()
    assert "total_queued" in stats
    assert "queued_by_priority" in stats
    assert "scaling_hints" in stats

    hints_high = q.get_scaling_hints(total_queued=25, current_concurrency=5, active_jobs=5)
    assert hints_high["action"] == "scale_up"
    assert hints_high["recommended_concurrency"] > 5

    hints_idle = q.get_scaling_hints(total_queued=0, current_concurrency=10, active_jobs=0)
    assert hints_idle["action"] == "scale_down"
    assert hints_idle["recommended_concurrency"] < 10

    hints_ok = q.get_scaling_hints(total_queued=2, current_concurrency=5, active_jobs=3)
    assert hints_ok["action"] == "maintain"
    assert hints_ok["recommended_concurrency"] == 5

def test_dynamic_worker_concurrency():
    worker = ReliableWorker(concurrency=3, worker_id="test-dyn-worker")
    assert worker.concurrency == 3

    new_conc = worker.adjust_concurrency(8)
    assert new_conc == 8
    assert worker.concurrency == 8

    # Test auto_tune
    with mock.patch("backend.queue.job_queue.get_scaling_hints") as mock_hints:
        mock_hints.return_value = {
            "action": "scale_up",
            "recommended_concurrency": 12,
            "reason": "Queue backlog test",
            "pressure_index": 2.5
        }
        res = worker.auto_tune_concurrency()
        assert res["action"] == "scale_up"
        assert worker.concurrency == 12

def test_worker_stats_reporting():
    worker = ReliableWorker(concurrency=4, worker_id="test-stats-worker")
    stats = worker.get_worker_stats()

    assert stats["worker_id"] == "test-stats-worker"
    assert stats["concurrency"] == 4
    assert "utilization_pct" in stats
    assert "queue_stats" in stats
    assert "scaling_hints" in stats
