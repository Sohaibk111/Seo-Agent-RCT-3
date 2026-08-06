import time
import threading
from backend.cache import InMemoryTTLCache, ttl_cache
from backend.services.keyword_service import KeywordService
from backend.services.metrics_service import MetricsService
from backend.services.rank_service import RankService
from backend.services.ai_service import AIService
from backend.database import crud

def test_in_memory_ttl_cache_basic_ops():
    cache = InMemoryTTLCache(default_ttl=10, max_size=5)
    
    # Set and Get
    cache.set("key1", "val1")
    assert cache.get("key1") == "val1"

    # Non-existent key
    assert cache.get("missing_key") is None

    # Delete
    cache.delete("key1")
    assert cache.get("key1") is None

    # Clear
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.size() == 2
    cache.clear()
    assert cache.size() == 0


def test_in_memory_ttl_cache_expiration():
    cache = InMemoryTTLCache(default_ttl=1, max_size=5)
    cache.set("expiring", "data", ttl=1)
    assert cache.get("expiring") == "data"
    
    time.sleep(1.1)
    assert cache.get("expiring") is None


def test_in_memory_ttl_cache_max_size_eviction():
    cache = InMemoryTTLCache(default_ttl=100, max_size=3)
    cache.set("k1", 1)
    cache.set("k2", 2)
    cache.set("k3", 3)
    assert cache.size() == 3

    # Adding 4th item forces eviction of oldest item
    cache.set("k4", 4)
    assert cache.size() == 3
    assert cache.get("k1") is None
    assert cache.get("k4") == 4


def test_in_memory_ttl_cache_thread_safety():
    cache = InMemoryTTLCache(default_ttl=100, max_size=500)
    errors = []

    def worker(worker_id):
        try:
            for i in range(50):
                key = f"thread_{worker_id}_key_{i}"
                cache.set(key, i)
                val = cache.get(key)
                if val != i:
                    errors.append(f"Mismatch in thread {worker_id}: expected {i}, got {val}")
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0


def test_keyword_service_caching():
    ttl_cache.clear()
    res1 = KeywordService.get_keyword_ideas("seo tools", limit=5)
    assert len(res1) == 5
    
    # Second call uses cache
    res2 = KeywordService.get_keyword_ideas("seo tools", limit=5)
    assert res1 == res2


def test_metrics_service_caching(db_session):
    ttl_cache.clear()
    user = crud.create_user(db_session, email="metrics_cache_user@test.com", username="mcacheuser")
    website = crud.create_website(db_session, user_id=user.id, url="https://cachemetrics.com", domain="cachemetrics.com")

    m1 = MetricsService.get_domain_metrics("cachemetrics.com", user_id=user.id, db=db_session)
    assert m1["domain"] == "cachemetrics.com"

    m2 = MetricsService.get_domain_metrics("cachemetrics.com", user_id=user.id, db=db_session)
    assert m1 == m2


def test_rank_service_caching(db_session):
    ttl_cache.clear()
    user = crud.create_user(db_session, email="rank_cache_user@test.com", username="rcacheuser")
    website = crud.create_website(db_session, user_id=user.id, url="https://cacherank.com", domain="cacherank.com")

    r1 = RankService.check_rank(keyword="seo tool", domain=None, website_id=website.id, user_id=user.id, db=db_session)
    assert r1["position"] == 4

    r2 = RankService.check_rank(keyword="seo tool", domain=None, website_id=website.id, user_id=user.id, db=db_session)
    assert r1 == r2


def test_ai_service_caching(db_session):
    ttl_cache.clear()
    user = crud.create_user(db_session, email="ai_cache_user@test.com", username="aicacheuser")
    website = crud.create_website(db_session, user_id=user.id, url="https://cacheai.com", domain="cacheai.com")
    audit = crud.create_audit(
        db_session,
        website_id=website.id,
        user_id=user.id,
        score=85,
        title="Test Site",
        meta_description="A test site for caching.",
        h1_tags=["Welcome"],
        canonical_url="https://cacheai.com",
        images_count=5,
        images_without_alt=0,
        broken_links_count=0
    )

    a1 = AIService.analyze_audit(audit_id=audit.id, user_id=user.id, db=db_session)
    assert "recommendations" in a1

    a2 = AIService.analyze_audit(audit_id=audit.id, user_id=user.id, db=db_session)
    assert a1 == a2
