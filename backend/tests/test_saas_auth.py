import pytest
from fastapi.testclient import TestClient

def test_saas_auth_full_flow(client: TestClient):
    # 1. Registration
    reg_payload = {
        "email": "saasuser@example.com",
        "username": "saasuser",
        "password": "SecurePassword123!",
        "remember_me": True
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 200, reg_res.text
    reg_data = reg_res.json()
    assert "access_token" in reg_data
    assert "refresh_token" in reg_data
    assert reg_data["email"] == "saasuser@example.com"
    assert reg_data["is_verified"] is False
    assert "verification_token" in reg_data
    ver_token = reg_data["verification_token"]
    access_token = reg_data["access_token"]
    refresh_token = reg_data["refresh_token"]

    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Email Verification Confirm
    ver_res = client.post("/api/v1/auth/verify-email/confirm", json={"token": ver_token})
    assert ver_res.status_code == 200, ver_res.text
    assert ver_res.json()["is_verified"] is True

    # 3. Get Profile
    profile_res = client.get("/api/v1/auth/profile", headers=headers)
    assert profile_res.status_code == 200, profile_res.text
    prof_data = profile_res.json()
    assert prof_data["is_verified"] is True
    assert prof_data["timezone"] == "UTC"

    # 4. Update Profile
    update_res = client.put(
        "/api/v1/auth/profile",
        headers=headers,
        json={
            "username": "updated_saasuser",
            "timezone": "America/New_York",
            "language": "es",
            "notification_settings": {"email_alerts": True}
        }
    )
    assert update_res.status_code == 200, update_res.text
    updated_data = update_res.json()
    assert updated_data["username"] == "updated_saasuser"
    assert updated_data["timezone"] == "America/New_York"
    assert updated_data["language"] == "es"

    # 5. Avatar Update
    avatar_res = client.post(
        "/api/v1/auth/profile/avatar",
        headers=headers,
        json={"avatar_url": "https://example.com/avatar.png"}
    )
    assert avatar_res.status_code == 200, avatar_res.text
    assert avatar_res.json()["avatar_url"] == "https://example.com/avatar.png"

    # 6. List Sessions
    sessions_res = client.get("/api/v1/auth/sessions", headers=headers)
    assert sessions_res.status_code == 200, sessions_res.text
    sessions = sessions_res.json()
    assert len(sessions) >= 1

    # 7. Token Refresh
    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 200, refresh_res.text
    new_tokens = refresh_res.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens

    # 8. Password Reset Request & Confirm
    pw_req_res = client.post("/api/v1/auth/password-reset/request", json={"email": "saasuser@example.com"})
    assert pw_req_res.status_code == 200, pw_req_res.text
    reset_data = pw_req_res.json()
    assert "reset_token" in reset_data
    reset_token = reset_data["reset_token"]

    pw_conf_res = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "NewSecretPassword456!"}
    )
    assert pw_conf_res.status_code == 200, pw_conf_res.text

    # 9. Login with New Password
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "saasuser@example.com", "password": "NewSecretPassword456!"}
    )
    assert login_res.status_code == 200, login_res.text
    new_login_access_token = login_res.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_login_access_token}"}

    # 10. Logout
    logout_res = client.post("/api/v1/auth/logout", headers=new_headers)
    assert logout_res.status_code == 200, logout_res.text
