import os
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.config import Settings, settings
from backend.metrics import metrics_registry

client = TestClient(app)

def test_production_environment_config_checklist():
    """Validates that production environment configuration checks enforce strict security criteria."""
    # Check that development setting warns correctly
    dev_settings = Settings(ENVIRONMENT="development", SECRET_KEY="dev_secret_key_long_enough_for_dev")
    dev_warnings = dev_settings.validate_startup()
    assert isinstance(dev_warnings, list)

    # Insecure secret key in production must fail validation
    insecure_prod = Settings(ENVIRONMENT="production", SECRET_KEY="short_key")
    with pytest.raises(ValueError, match="CRITICAL SECURITY ERROR"):
        insecure_prod.validate_startup()

    # Valid production settings
    valid_prod = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="super_secure_production_secret_key_32_characters_minimum_length!",
        DATABASE_URL="postgresql://user:pass@localhost:5432/seo_agent"
    )
    prod_warnings = valid_prod.validate_startup()
    assert isinstance(prod_warnings, list)

def test_health_and_metrics_endpoints():
    """Validates production observability endpoints."""
    # Health check
    health_res = client.get("/api/v1/health")
    assert health_res.status_code == 200
    health_data = health_res.json()
    assert health_data["status"] == "ok"
    assert "timestamp" in health_data

    # Prometheus metrics
    metrics_res = client.get("/metrics")
    assert metrics_res.status_code == 200
    prom_text = metrics_res.text
    assert "seo_agent_requests_total" in prom_text or "http_requests_total" in prom_text or "cache_hits_total" in prom_text

def test_security_authorization_boundaries():
    """Validates that protected endpoints reject unauthorized requests."""
    protected_paths = [
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/websites"),
        ("POST", "/api/v1/websites"),
        ("GET", "/api/v1/websites/cursor"),
        ("POST", "/api/v1/jobs/audit"),
        ("POST", "/api/v1/keywords/ideas"),
        ("POST", "/api/v1/domain-metrics"),
        ("POST", "/api/v1/reports/export"),
    ]

    for method, path in protected_paths:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json={})
        assert res.status_code == 401, f"Path {path} did not reject unauthenticated access! Status: {res.status_code}"

def test_required_production_release_files():
    """Ensures all necessary containerization, configuration, and script assets exist."""
    required_files = [
        "Dockerfile.backend",
        "Dockerfile.frontend",
        "docker-compose.yml",
        "docker-compose.prod.yml",
        "nginx/nginx.conf",
        "nginx/conf.d/default.conf",
        "scripts/backup_db.sh",
        "scripts/restore_db.sh",
        ".github/workflows/ci.yml"
    ]
    for rel_path in required_files:
        assert os.path.exists(rel_path), f"Missing required production file: {rel_path}"
