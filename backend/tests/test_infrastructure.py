import time
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.rate_limiter import rate_limiter
from backend.cache import UnifiedCache, ttl_cache
from backend.metrics import metrics_registry
from backend.queue import RedisJobQueue
from backend.services.scraper_service import ScraperService
from backend.database import crud
from backend.auth.security import create_access_token

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert "service" in data

    response_v1 = client.get("/api/v1/health")
    assert response_v1.status_code == 200
    assert response_v1.json()["status"] == "ok"


def test_ready_endpoint():
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ready", "degraded"]
    assert data["database"] == "connected" or (isinstance(data["database"], dict) and data["database"].get("status") in ["ok", "connected"])
    assert "redis" in data

    response_v1 = client.get("/api/v1/ready")
    assert response_v1.status_code == 200
    assert response_v1.json()["status"] in ["ready", "degraded"]


def test_metrics_endpoint():
    # Make a request to increment counters
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    text = response.text
    assert "request_count" in text
    assert "request_duration_seconds" in text
    assert "active_jobs" in text
    assert "queue_length" in text
    assert "crawl_duration_seconds" in text
    assert "audit_duration_seconds" in text


def test_rate_limiter_unit_and_429_guard(db_session):
    # Test unit logic of rate_limiter
    test_id = "test_client_ip_123"
    assert rate_limiter.check_rate_limit(test_id, max_requests=2) is True
    assert rate_limiter.check_rate_limit(test_id, max_requests=2) is True
    # 3rd request exceeds limit
    assert rate_limiter.check_rate_limit(test_id, max_requests=2) is False

    # Test API 429 response
    user = crud.create_user(db_session, email="ratelimit_user@test.com", username="rluser")
    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    # Simulate hitting rate limit on /api/v1/keywords
    rl_id = f"Bearer {token}"
    rate_limiter._requests[rl_id] = [time.time()] * 1000

    response = client.post("/api/v1/keywords", json={"seed_keyword": "seo test limit"}, headers=headers)
    assert response.status_code == 429
    assert "Rate limit exceeded" in response.json()["error"]


def test_unified_cache_fallback():
    uc = UnifiedCache()
    uc.set("test_key", {"foo": "bar"}, ttl=300)
    assert uc.get("test_key") == {"foo": "bar"}
    assert uc.size() >= 1
    uc.delete("test_key")
    assert uc.get("test_key") is None


def test_redis_queue_fallback():
    queue = RedisJobQueue()
    res = queue.enqueue("test_type", job_id=999, user_id=1, target_func=lambda **kw: None)
    assert res.startswith("thread:") or res.startswith("redis:")


def test_scraper_service_cached_helpers(db_session):
    ttl_cache.clear()
    user = crud.create_user(db_session, email="scraper_infra_user@test.com", username="infrauser")
    website = crud.create_website(db_session, user_id=user.id, url="https://infratest.com", domain="infratest.com")
    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    # Test Robots.txt
    rob1 = ScraperService.fetch_robots_txt("infratest.com")
    assert rob1["status"] == 200
    rob2 = ScraperService.fetch_robots_txt("infratest.com")
    assert rob1 == rob2

    # Test Sitemap
    site1 = ScraperService.fetch_sitemap("infratest.com")
    assert site1["total_urls"] == 42
    site2 = ScraperService.fetch_sitemap("infratest.com")
    assert site1 == site2

    # Test WHOIS
    whois1 = ScraperService.lookup_whois("infratest.com")
    assert whois1["registrar"] == "NameCheap Inc."
    whois2 = ScraperService.lookup_whois("infratest.com")
    assert whois1 == whois2

    # Test Scraper API endpoints
    r_robots = client.get("/api/v1/scraper/robots?domain=infratest.com", headers=headers)
    assert r_robots.status_code == 200
    assert r_robots.json()["domain"] == "infratest.com"

    r_sitemap = client.get("/api/v1/scraper/sitemap?domain=infratest.com", headers=headers)
    assert r_sitemap.status_code == 200
    assert r_sitemap.json()["total_urls"] == 42

    r_whois = client.get("/api/v1/metrics/whois?domain=infratest.com", headers=headers)
    assert r_whois.status_code == 200
    assert r_whois.json()["registrar"] == "NameCheap Inc."
