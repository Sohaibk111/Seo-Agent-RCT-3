import pytest
from fastapi.testclient import TestClient
from backend.auth.security import create_access_token, decode_access_token
from backend.ssrf_protection import validate_url_ssrf, is_ip_blocked
from backend.exceptions import ValidationErrorException, ForbiddenException
from backend.rate_limiter import DistributedRateLimiter
from backend.logging_config import sanitize_data

def test_jwt_token_creation_and_decoding():
    """Verify production JWT token generation, signature validation, and claims parsing."""
    token = create_access_token(user_id=42, email="sec_test@example.com")
    assert isinstance(token, str)
    assert len(token.split(".")) == 3

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["user_id"] == 42
    assert payload["sub"] == "42"
    assert payload["email"] == "sec_test@example.com"

def test_jwt_token_invalid_signature_rejected():
    """Verify that tampered JWT signatures are rejected."""
    token = create_access_token(user_id=10, email="user10@example.com")
    parts = token.split(".")
    tampered_token = f"{parts[0]}.{parts[1]}.invalid_signature_hash"
    
    assert decode_access_token(tampered_token) is None

def test_ssrf_protection_blocks_internal_and_private_ips():
    """Verify SSRF protection blocks localhost, AWS/GCP metadata endpoints, and private subnets."""
    blocked_urls = [
        "http://localhost:8000/admin",
        "http://127.0.0.1/status",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/internal",
        "http://192.168.1.1/router",
        "http://172.16.0.5/api",
        "http://metadata.google.internal/computeMetadata/v1/",
        "file:///etc/passwd",
        "ftp://example.com/file"
    ]

    for url in blocked_urls:
        with pytest.raises(ValidationErrorException):
            validate_url_ssrf(url)

def test_ssrf_protection_allows_valid_public_urls():
    """Verify SSRF protection allows safe, public internet domains."""
    valid_urls = [
        "https://example.com",
        "https://google.com/search?q=test",
        "http://wikipedia.org"
    ]
    for url in valid_urls:
        res = validate_url_ssrf(url)
        assert res == url

def test_tenant_isolation_boundary_check(client: TestClient):
    """Verify strict cross-tenant isolation enforcement on protected resources."""
    # User A creates a website
    token_a = create_access_token(user_id=101, email="usera@test.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    create_res = client.post("/api/v1/websites", headers=headers_a, json={
        "url": "https://usera-domain.com",
        "domain": "usera-domain.com"
    })
    assert create_res.status_code == 200
    site_id = create_res.json()["id"]

    # User B attempts to access User A's website -> MUST RETURN 403 FORBIDDEN
    token_b = create_access_token(user_id=102, email="userb@test.com")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    get_res = client.get(f"/api/v1/websites/{site_id}", headers=headers_b)
    assert get_res.status_code == 403, f"Expected 403 Forbidden for cross-tenant access, got {get_res.status_code}"

    # User B attempts to delete User A's website -> MUST RETURN 403 FORBIDDEN
    del_res = client.delete(f"/api/v1/websites/{site_id}", headers=headers_b)
    assert del_res.status_code == 403, f"Expected 403 Forbidden for cross-tenant delete, got {del_res.status_code}"

def test_admin_authorization_guard(client: TestClient):
    """Verify non-admin users are blocked from administrative endpoints."""
    token_user = create_access_token(user_id=55, email="normaluser@test.com")
    headers_user = {"Authorization": f"Bearer {token_user}"}

    # Attempt to access admin DLQ endpoint
    dlq_res = client.get("/api/v1/dlq", headers=headers_user)
    assert dlq_res.status_code == 403

    # Attempt to adjust worker concurrency
    adj_res = client.post("/api/v1/worker/concurrency?concurrency=10", headers=headers_user)
    assert adj_res.status_code == 403

def test_sensitive_data_logging_scrub():
    """Verify log sanitizer scrubs passwords, secrets, JWTs, and API keys."""
    raw_data = {
        "user_id": 1,
        "password": "SuperSecretPassword123!",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.sig",
        "api_key": "secret_api_key_value",
        "headers": {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiInR5cCI6IkpXVCJ9"
        }
    }
    scrubbed = sanitize_data(raw_data)
    assert scrubbed["password"] == "[REDACTED]"
    assert scrubbed["access_token"] == "[REDACTED]"
    assert scrubbed["api_key"] == "[REDACTED]"
    assert scrubbed["headers"]["Authorization"] == "[REDACTED]"
