from fastapi.testclient import TestClient
import pytest

def test_user_registration_email_and_username_validation(client: TestClient):
    # Invalid email
    res = client.post("/api/v1/auth/register", json={"email": "not-an-email", "username": "validuser"})
    assert res.status_code == 422

    # Empty username
    res = client.post("/api/v1/auth/register", json={"email": "valid@test.com", "username": "   "})
    assert res.status_code == 422


def test_website_creation_url_and_domain_validation(client: TestClient):
    token = "Bearer token_user_1"

    # Valid website creation
    res = client.post("/api/v1/websites", headers={"Authorization": token}, json={
        "url": "example.com",
        "company_name": "Example Corp"
    })
    assert res.status_code == 200
    assert res.json()["url"] == "https://example.com"
    assert res.json()["domain"] == "example.com"

    # Invalid domain format in Website creation
    res_inv = client.post("/api/v1/websites", headers={"Authorization": token}, json={
        "url": "https://valid.com",
        "domain": "invalid_domain!!$$"
    })
    assert res_inv.status_code == 422


def test_keyword_request_validation(client: TestClient):
    token = "Bearer token_user_1"

    # Empty keyword
    res = client.post("/api/v1/keywords/ideas", headers={"Authorization": token}, json={
        "seed_keyword": "   "
    })
    assert res.status_code == 422

    # Out of bounds limit
    res_limit = client.post("/api/v1/keywords/ideas", headers={"Authorization": token}, json={
        "seed_keyword": "seo tools",
        "limit": 500
    })
    assert res_limit.status_code == 422


def test_domain_metrics_validation(client: TestClient):
    token = "Bearer token_user_1"

    # Invalid domain format
    res = client.post("/api/v1/domain-metrics", headers={"Authorization": token}, json={
        "domain": "not a domain"
    })
    assert res.status_code == 422

    # Valid domain format cleans prefix
    res_valid = client.post("/api/v1/domain-metrics", headers={"Authorization": token}, json={
        "domain": "https://sub.domain.com/path"
    })
    assert res_valid.status_code == 200
    assert res_valid.json()["domain"] == "sub.domain.com"
