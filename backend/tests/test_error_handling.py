from fastapi.testclient import TestClient
import pytest

def test_unauthorized_error_format(client: TestClient):
    res = client.get("/api/v1/websites")
    assert res.status_code == 401
    json_data = res.json()
    assert "error" in json_data
    assert "detail" in json_data
    assert json_data["status_code"] == 401

def test_not_found_error_format(client: TestClient):
    token = "Bearer token_user_1"
    res = client.get("/api/v1/websites/999999", headers={"Authorization": token})
    assert res.status_code == 404
    json_data = res.json()
    assert "error" in json_data
    assert "detail" in json_data
    assert json_data["status_code"] == 404

def test_forbidden_error_format(client: TestClient):
    user_a_token = "Bearer token_user_1"
    user_b_token = "Bearer token_user_2"

    # Create website under User A
    create_res = client.post("/api/v1/websites", headers={"Authorization": user_a_token}, json={
        "url": "https://user-a-site.com"
    })
    site_id = create_res.json()["id"]

    # Try accessing with User B token
    res = client.get(f"/api/v1/websites/{site_id}", headers={"Authorization": user_b_token})
    assert res.status_code == 403
    json_data = res.json()
    assert "error" in json_data
    assert "detail" in json_data
    assert json_data["status_code"] == 403

def test_validation_error_format(client: TestClient):
    token = "Bearer token_user_1"
    res = client.post("/api/v1/keywords/ideas", headers={"Authorization": token}, json={
        "seed_keyword": "  "
    })
    assert res.status_code == 422
    json_data = res.json()
    assert "error" in json_data
    assert "detail" in json_data
    assert json_data["status_code"] == 422
    assert "details" in json_data
    assert "errors" in json_data["details"]
