from fastapi.testclient import TestClient
import json

def test_request_logging_header(client: TestClient):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert "X-Request-ID" in res.headers
    assert len(res.headers["X-Request-ID"]) > 0

def test_sanitization_helper():
    from backend.logging_config import sanitize_data
    sample_data = {
        "user_id": 12,
        "password": "secret_password_123",
        "nested": {
            "access_token": "bearer xyz.abc.123",
            "normal_field": "hello"
        }
    }
    cleaned = sanitize_data(sample_data)
    assert cleaned["password"] == "[REDACTED]"
    assert cleaned["nested"]["access_token"] == "[REDACTED]"
    assert cleaned["nested"]["normal_field"] == "hello"
