import os
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.config import Settings
from backend.metrics import metrics_registry
from backend.database.database import engine_kwargs
from backend.logging_config import JSONFormatter, logger

client = TestClient(app)

def test_production_settings_validation():
    # Test development mode validation
    dev_settings = Settings(ENVIRONMENT="development", SECRET_KEY="super-secret-jwt-key-for-dev")
    warnings = dev_settings.validate_startup()
    assert isinstance(warnings, list)

    # Test production mode secret key security validation
    prod_insecure = Settings(ENVIRONMENT="production", SECRET_KEY="super-secret-jwt-key-for-dev")
    with pytest.raises(ValueError, match="CRITICAL SECURITY ERROR"):
        prod_insecure.validate_startup()

    # Test valid production settings
    prod_valid = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a_very_secure_production_secret_key_that_is_long_enough_32chars",
        DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"
    )
    prod_warnings = prod_valid.validate_startup()
    assert len(prod_warnings) == 1  # Notice about GEMINI_API_KEY


def test_database_connection_pooling_config():
    # Verify pool_pre_ping is enabled for PostgreSQL engine kwargs
    from backend.config import settings
    if "sqlite" not in settings.DATABASE_URL:
        assert engine_kwargs.get("pool_pre_ping") is True
        assert engine_kwargs.get("pool_size") == settings.DB_POOL_SIZE
        assert engine_kwargs.get("max_overflow") == settings.DB_MAX_OVERFLOW
    else:
        assert engine_kwargs.get("connect_args") == {"check_same_thread": False}


def test_extended_prometheus_metrics():
    metrics_registry.inc_cache_hit()
    metrics_registry.inc_cache_miss()
    metrics_registry.observe_db_query_duration(0.015)
    metrics_registry.set_worker_utilization(75.5)

    prom_text = metrics_registry.generate_prometheus_text()
    assert "cache_hits_total" in prom_text
    assert "cache_misses_total" in prom_text
    assert "db_query_duration_seconds" in prom_text
    assert "worker_utilization_percent" in prom_text


def test_docker_and_nginx_files_exist():
    assert os.path.exists("Dockerfile.backend")
    assert os.path.exists("Dockerfile.frontend")
    assert os.path.exists("docker-compose.yml")
    assert os.path.exists("docker-compose.prod.yml")
    assert os.path.exists("nginx/nginx.conf")
    assert os.path.exists("nginx/conf.d/default.conf")
    assert os.path.exists("scripts/backup_db.sh")
    assert os.path.exists("scripts/restore_db.sh")
    assert os.path.exists(".github/workflows/ci.yml")


def test_trace_id_and_span_id_logging_formatter():
    import logging
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test trace logging message",
        args=(),
        exc_info=None
    )
    setattr(record, "trace_id", "trace-1234567890abcdef")
    setattr(record, "span_id", "span-12345678")

    formatter = JSONFormatter()
    formatted_json = formatter.format(record)
    assert "trace-1234567890abcdef" in formatted_json
    assert "span-12345678" in formatted_json
