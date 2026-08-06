from fastapi.testclient import TestClient

def test_register_and_login(client: TestClient):
    # Register user
    res = client.post("/api/v1/auth/register", json={"email": "newuser@test.com", "username": "newuser"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["email"] == "newuser@test.com"

    # Login user
    res = client.post("/api/v1/auth/login", json={"email": "newuser@test.com", "username": "newuser"})
    assert res.status_code == 200
    assert "access_token" in res.json()

def test_get_me_authenticated(client: TestClient):
    token = "Bearer token_user_1"
    res = client.get("/api/v1/auth/me", headers={"Authorization": token})
    assert res.status_code == 200
    assert res.json()["id"] == 1

def test_unauthenticated_returns_401(client: TestClient):
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
