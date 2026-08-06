import pytest
from unittest import mock
from backend.cache import (
    UnifiedCache,
    InMemoryTTLCache,
    get_redis_connection_pool,
    get_redis_client,
    ttl_cache
)
from backend.config import settings

def test_redis_connection_pool_initialization():
    mock_redis_mod = mock.MagicMock()
    with mock.patch.dict("sys.modules", {"redis": mock_redis_mod}):
        with mock.patch("backend.cache.settings.REDIS_URL", "redis://localhost:6379/0"):
            # Reset cache singleton
            import backend.cache
            backend.cache._redis_connection_pool = None
            pool = get_redis_connection_pool()
            assert pool is not None
            mock_redis_mod.ConnectionPool.from_url.assert_called_once()

def test_redis_client_from_pool():
    mock_redis_mod = mock.MagicMock()
    with mock.patch.dict("sys.modules", {"redis": mock_redis_mod}):
        with mock.patch("backend.cache.get_redis_connection_pool") as mock_get_pool:
            mock_pool = mock.MagicMock()
            mock_get_pool.return_value = mock_pool
            client = get_redis_client()
            assert client is not None
            mock_redis_mod.Redis.assert_called_once_with(connection_pool=mock_pool)

def test_cache_batch_operations_in_memory():
    cache = UnifiedCache()
    # Ensure operating in local cache mode for this test
    cache._redis_connected = False
    
    mapping = {
        "batch_k1": {"data": 1},
        "batch_k2": {"data": 2},
        "batch_k3": {"data": 3}
    }
    cache.set_many(mapping, ttl=60)
    
    fetched = cache.get_many(["batch_k1", "batch_k2", "batch_k3", "missing_k"])
    assert fetched["batch_k1"] == {"data": 1}
    assert fetched["batch_k2"] == {"data": 2}
    assert fetched["batch_k3"] == {"data": 3}
    assert "missing_k" not in fetched

    deleted_count = cache.delete_many(["batch_k1", "batch_k2"])
    assert deleted_count == 2
    assert cache.get("batch_k1") is None
    assert cache.get("batch_k3") == {"data": 3}

def test_cache_batch_operations_redis_mocked():
    mock_redis = mock.MagicMock()
    mock_pipeline = mock.MagicMock()
    mock_redis.pipeline.return_value = mock_pipeline
    mock_redis.mget.return_value = ['{"a": 1}', '{"b": 2}']
    
    cache = UnifiedCache()
    cache._redis_client = mock_redis
    cache._redis_connected = True

    # Test get_many via MGET
    res = cache.get_many(["k1", "k2"])
    assert res == {"k1": {"a": 1}, "k2": {"b": 2}}
    mock_redis.mget.assert_called_once_with(["k1", "k2"])

    # Test set_many via Pipeline
    cache.set_many({"k1": {"a": 1}, "k2": {"b": 2}}, ttl=120)
    mock_redis.pipeline.assert_called_once_with(transaction=False)
    assert mock_pipeline.setex.call_count == 2
    mock_pipeline.execute.assert_called_once()

def test_cache_warming():
    cache = UnifiedCache()
    cache._redis_connected = False
    cache.clear()

    warm_data = {"warm_1": "val1", "warm_2": "val2"}
    count = cache.warm_cache(warm_data)
    assert count == 2
    assert cache.get("warm_1") == "val1"
    assert cache.get("warm_2") == "val2"

    def data_loader():
        return {"loaded_1": "lval1", "loaded_2": "lval2"}

    loaded_count = cache.warm_common_keys(data_loader)
    assert loaded_count == 2
    assert cache.get("loaded_1") == "lval1"

def test_cache_invalidation_helpers():
    cache = UnifiedCache()
    cache._redis_connected = False
    cache.clear()

    cache.set("website:101:metrics", "m1")
    cache.set("website:101:audit", "a1")
    cache.set("website:202:metrics", "m2")

    # Invalidate by tag
    count = cache.invalidate_tag("website:101")
    assert count == 2
    assert cache.get("website:101:metrics") is None
    assert cache.get("website:101:audit") is None
    assert cache.get("website:202:metrics") == "m2"

    # Invalidate by pattern
    cache.set("user:50:profile", "u50")
    cache.set("user:50:settings", "s50")
    count_pat = cache.invalidate_pattern("user:50:*")
    assert count_pat == 2
    assert cache.get("user:50:profile") is None

def test_lua_scripts_invoked():
    mock_redis = mock.MagicMock()
    mock_script = mock.MagicMock()
    mock_script.return_value = 2
    mock_redis.register_script.return_value = mock_script

    cache = UnifiedCache()
    cache._redis_client = mock_redis
    cache._redis_connected = True
    cache._register_lua_scripts()

    invalidated = cache.invalidate_pattern("tag:*")
    assert invalidated == 2
    mock_script.assert_called_with(args=["tag:*"])
