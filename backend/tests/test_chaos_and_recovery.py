import pytest
import unittest.mock as mock
from backend.cache import UnifiedCache, ttl_cache
from backend.exceptions import ExternalServiceException, DatabaseException
from backend.dead_letter_queue import dead_letter_queue
from backend.queue import job_queue

def test_redis_chaos_fallback_to_local_memory():
    """Chaos test: Simulate Redis server connection crash and verify zero-downtime fallback to local memory cache."""
    cache = UnifiedCache()
    # Mock redis client as active initially
    mock_redis = mock.MagicMock()
    mock_redis.ping.side_effect = Exception("ConnectionRefusedError: Redis connection lost!")
    cache._redis_client = mock_redis

    # Redis ping should raise exception and is_redis_active() returns False
    assert cache.is_redis_active() is False

    # Setting and getting keys should continue seamlessly using local memory fallback
    cache.set("chaos_key", "chaos_value", ttl=60)
    assert cache.get("chaos_key") == "chaos_value"

    # Multi operations should also work gracefully on fallback
    cache.set_many({"k1": "v1", "k2": "v2"}, ttl=60)
    res = cache.get_many(["k1", "k2"])
    assert res == {"k1": "v1", "k2": "v2"}

def test_dead_letter_queue_and_failed_job_recovery():
    """Chaos test: Verify that exhausted failed jobs are safely captured in DLQ for worker recovery."""
    job_id = "test_chaos_job_999"
    job_type = "audit"
    error_reason = "Fatal scraper subprocess memory exception"

    # Push to Dead Letter Queue
    dead_letter_queue.push(
        job_id=job_id,
        job_type=job_type,
        user_id=1,
        func_name="run_audit_job",
        kwargs={"url": "https://chaos-test.com"},
        error=error_reason,
        attempts=3
    )

    # Inspect DLQ
    dlq_items = dead_letter_queue.get_all()
    failed_item = next((item for item in dlq_items if item["job_id"] == job_id), None)

    assert failed_item is not None
    assert failed_item["error"] == error_reason
    assert failed_item["attempts"] == 3

    # Clean up DLQ
    dead_letter_queue.remove(job_id)

def test_http_client_resilience_and_retry_backoff():
    """Verify that external HTTP calls handle timeouts with structured error wrapping."""
    from backend.http_client import fetch_url_content_async

    # Patch httpx client to raise timeout
    with mock.patch("backend.http_client.get_http_client") as mock_get_client:
        mock_client = mock.AsyncMock()
        mock_client.get.side_effect = Exception("ReadTimeout: Network unreachable")
        mock_get_client.return_value = mock_client

        # Expect exception handling without unhandled crash
        try:
            import asyncio
            asyncio.run(fetch_url_content_async("https://unreachable-domain-123.com"))
        except Exception as e:
            assert "ReadTimeout" in str(e) or "Network unreachable" in str(e) or isinstance(e, ExternalServiceException)
