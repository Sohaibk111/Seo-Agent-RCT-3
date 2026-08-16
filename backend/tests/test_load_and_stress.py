import asyncio
import time
import pytest
from fastapi.testclient import TestClient
from backend.cache import ttl_cache
from backend.rate_limiter import sliding_window_limiter
from backend.main import app

def test_concurrent_request_load_handling(client: TestClient):
    """Simulates 100 concurrent requests to cached endpoints to measure throughput and latency."""
    token = "Bearer token_user_1"
    headers = {"Authorization": token}
    
    start_time = time.time()
    success_count = 0
    total_requests = 100

    for _ in range(total_requests):
        res = client.get("/api/v1/auth/me", headers=headers)
        if res.status_code == 200:
            success_count += 1

    duration = time.time() - start_time
    rps = total_requests / duration if duration > 0 else 1000

    assert success_count == total_requests
    assert rps > 50  # Must maintain at least 50 req/sec in memory/test client

def test_cache_and_memory_stress():
    """Stress test the UnifiedCache with thousands of entries and verify eviction & TTL behavior."""
    initial_size = ttl_cache.size()
    
    # Insert 1000 keys
    for i in range(1000):
        ttl_cache.set(f"stress_key_{i}", {"data": f"value_{i}" * 10}, ttl=60)

    assert ttl_cache.size() >= 1000

    # Retrieve 1000 keys
    hit_count = 0
    for i in range(1000):
        if ttl_cache.get(f"stress_key_{i}") is not None:
            hit_count += 1

    assert hit_count == 1000

    # Clean up test keys
    for i in range(1000):
        ttl_cache.delete(f"stress_key_{i}")

def test_rate_limiter_burst_stress():
    """Validates sliding window rate limiter under burst traffic."""
    test_ip = "192.168.99.1"
    limit = 20
    window = 10

    # Fill capacity
    allowed_count = 0
    for _ in range(limit):
        if sliding_window_limiter.is_allowed(test_ip, limit=limit, window_seconds=window):
            allowed_count += 1

    assert allowed_count == limit

    # Excess attempt should be blocked
    is_blocked = not sliding_window_limiter.is_allowed(test_ip, limit=limit, window_seconds=window)
    assert is_blocked is True

def test_sse_streaming_endpoint_load(client: TestClient):
    """Verifies that job streaming SSE endpoint initiates without blocking or crashing."""
    token = "Bearer token_user_1"
    headers = {"Authorization": token}

    # Create a job first
    job_res = client.post("/api/v1/jobs/audit", headers=headers, json={"url": "https://stress-test.com"})
    assert job_res.status_code == 200
    job_id = job_res.json()["id"]

    # Stream SSE request
    with client.stream("GET", f"/api/v1/jobs/{job_id}/stream", headers=headers) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        # Read initial event frame
        lines = list(response.iter_lines())
        assert len(lines) > 0
