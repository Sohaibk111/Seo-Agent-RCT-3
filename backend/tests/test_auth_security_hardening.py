import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from backend.auth.security import (
    validate_password_strength,
    calculate_progressive_delay,
    hash_token,
    parse_device_info
)

def test_password_strength_validator_unit():
    # Weak passwords
    assert validate_password_strength("short")[0] is False
    assert validate_password_strength("alllowercase1!")[0] is False
    assert validate_password_strength("ALLUPPERCASE1!")[0] is False
    assert validate_password_strength("NoSpecialChar123")[0] is False
    assert validate_password_strength("NoNumbersHere!")[0] is False
    assert validate_password_strength("password123")[0] is False
    assert validate_password_strength("qwerty123")[0] is False

    # Strong password
    valid, errors = validate_password_strength("ComplexPass123!#$")
    assert valid is True
    assert len(errors) == 0

def test_progressive_delay_calculation():
    assert calculate_progressive_delay(0) == 0.0
    assert calculate_progressive_delay(1) == 0.0
    assert calculate_progressive_delay(2) == 0.2
    assert calculate_progressive_delay(3) == 0.5
    assert calculate_progressive_delay(4) == 1.0
    assert calculate_progressive_delay(5) == 2.0
    assert calculate_progressive_delay(10) == 2.0  # Max delay capped at 2.0s

def test_device_info_parser():
    info_mobile = parse_device_info("Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1")
    assert info_mobile["device_type"] == "mobile"
    assert "Safari" in info_mobile["device_name"]

    info_desktop = parse_device_info("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    assert info_desktop["device_type"] == "desktop"
    assert "Chrome" in info_desktop["device_name"]

    info_bot = parse_device_info("curl/7.68.0")
    assert info_bot["device_type"] == "api"

def test_auth_security_hardening_integration_flow(client: TestClient):
    # 1. Registration with Weak Password Fails
    weak_res = client.post("/api/v1/auth/register", json={
        "email": "secuser@example.com",
        "username": "secuser",
        "password": "weak"
    })
    assert weak_res.status_code == 400
    assert "at least 8 characters" in weak_res.text

    # 2. Registration with Strong Password
    strong_pwd = "SuperSecurePass123!"
    reg_res = client.post("/api/v1/auth/register", json={
        "email": "secuser@example.com",
        "username": "secuser",
        "password": strong_pwd,
        "remember_me": True
    }, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert reg_data["is_verified"] is False
    ver_token = reg_data["verification_token"]
    user_id = reg_data["id"]
    access_token = reg_data["access_token"]
    refresh_token = reg_data["refresh_token"]

    auth_headers = {"Authorization": f"Bearer {access_token}"}

    # 3. Email Verification Enforcement: Unverified user cannot create API Key (403 Forbidden)
    api_key_unverified_res = client.post("/api/v1/auth/api-keys", headers=auth_headers, json={"name": "Test Key"})
    assert api_key_unverified_res.status_code == 403
    assert "Email verification is required" in api_key_unverified_res.text

    # Verify email
    ver_res = client.post("/api/v1/auth/verify-email/confirm", json={"token": ver_token})
    assert ver_res.status_code == 200
    assert ver_res.json()["is_verified"] is True

    # Now API key creation succeeds
    api_key_res = client.post("/api/v1/auth/api-keys", headers=auth_headers, json={"name": "Test Key"})
    assert api_key_res.status_code == 200
    assert "api_key" in api_key_res.json()

    # 4. Device Tracking & Session Verification
    sessions_res = client.get("/api/v1/auth/sessions", headers=auth_headers)
    assert sessions_res.status_code == 200
    sessions = sessions_res.json()
    assert len(sessions) >= 1
    current_sess = sessions[0]
    assert current_sess["device_type"] in ["desktop", "api", "mobile"]
    assert "device_name" in current_sess
    assert current_sess["is_active"] is True

    # 5. Refresh Token Rotation
    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 200
    new_token_data = refresh_res.json()
    new_access_token = new_token_data["access_token"]
    new_refresh_token = new_token_data["refresh_token"]
    assert new_refresh_token != refresh_token

    # 6. Refresh Token Reuse Detection (Replaying the old rotated refresh token)
    reuse_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse_res.status_code == 401
    assert "Suspicious token activity detected" in reuse_res.text or "revoked" in reuse_res.text

    # Verify that all sessions were revoked due to breach detection
    after_reuse_sessions = client.get("/api/v1/auth/sessions", headers={"Authorization": f"Bearer {new_access_token}"})
    # Since sessions are invalidated, authentication will fail with 401 or return empty active sessions
    assert after_reuse_sessions.status_code in [200, 401]
    if after_reuse_sessions.status_code == 200:
        active = [s for s in after_reuse_sessions.json() if s.get("is_active")]
        assert len(active) == 0

    # 7. Login and Password History Enforcement
    login_res = client.post("/api/v1/auth/login", json={
        "email": "secuser@example.com",
        "password": strong_pwd
    })
    assert login_res.status_code == 200
    login_access_token = login_res.json()["access_token"]
    login_headers = {"Authorization": f"Bearer {login_access_token}"}

    # Attempt to change password to the same password (history rejection)
    history_reject_res = client.post("/api/v1/auth/change-password", headers=login_headers, json={
        "current_password": strong_pwd,
        "new_password": strong_pwd
    })
    assert history_reject_res.status_code == 400
    assert "Cannot reuse any of your last" in history_reject_res.text

    # Change password to new valid password
    newer_pwd = "BrandNewStrongPass2026!#"
    change_pw_res = client.post("/api/v1/auth/change-password", headers=login_headers, json={
        "current_password": strong_pwd,
        "new_password": newer_pwd
    })
    assert change_pw_res.status_code == 200

    # 8. Account Lockout & Brute-force Protection
    # 5 consecutive failed logins triggers lockout (HTTP 423 Locked)
    for i in range(4):
        fail_res = client.post("/api/v1/auth/login", json={
            "email": "secuser@example.com",
            "password": "WrongPassword123!"
        })
        assert fail_res.status_code == 401
        assert "remaining before lockout" in fail_res.text

    # 5th failed attempt locks the account
    lock_res = client.post("/api/v1/auth/login", json={
        "email": "secuser@example.com",
        "password": "WrongPassword123!"
    })
    assert lock_res.status_code == 423
    assert "locked" in lock_res.text.lower()

    # Even with correct password, locked account is rejected
    locked_attempt = client.post("/api/v1/auth/login", json={
        "email": "secuser@example.com",
        "password": newer_pwd
    })
    assert locked_attempt.status_code == 423
    assert "temporarily locked" in locked_attempt.text.lower()

    # 9. CSRF Token Endpoint
    csrf_res = client.get("/api/v1/auth/csrf-token")
    assert csrf_res.status_code == 200
    assert "csrf_token" in csrf_res.json()
