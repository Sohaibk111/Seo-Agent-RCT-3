from fastapi.testclient import TestClient

def test_unauthenticated_requests_return_401(client: TestClient):
    assert client.get("/api/v1/websites").status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/audit", json={"url": "https://test.com"}).status_code == 401
    assert client.get("/api/v1/ai/analyze/101").status_code == 401

def test_tenant_isolation_and_authorization(client: TestClient):
    user_a_token = "Bearer token_user_1"
    user_b_token = "Bearer token_user_2"

    # User A creates a site audit
    audit_res = client.post(
        "/api/v1/audit",
        headers={"Authorization": user_a_token},
        json={"url": "https://usera-exclusive-fastapi.com"}
    )
    assert audit_res.status_code == 200
    data = audit_res.json()
    user_a_website_id = data["website"]["id"]
    user_a_audit_id = data["audit"]["id"]

    # User A can list their website
    websites_res = client.get("/api/v1/websites", headers={"Authorization": user_a_token})
    assert websites_res.status_code == 200
    assert any(w["id"] == user_a_website_id for w in websites_res.json())

    # User B CANNOT read User A's website -> 403 Forbidden
    b_site = client.get(f"/api/v1/websites/{user_a_website_id}", headers={"Authorization": user_b_token})
    assert b_site.status_code == 403

    # User B CANNOT audit User A's website_id -> 403 Forbidden
    b_audit_id = client.post(
        "/api/v1/audit",
        headers={"Authorization": user_b_token},
        json={"website_id": user_a_website_id}
    )
    assert b_audit_id.status_code == 403

    # User B CANNOT audit User A's domain directly -> 403 Forbidden
    b_domain_audit = client.post(
        "/api/v1/audit",
        headers={"Authorization": user_b_token},
        json={"url": "https://usera-exclusive-fastapi.com"}
    )
    assert b_domain_audit.status_code == 403

    # User B CANNOT get AI analysis for User A's audit -> 403 Forbidden
    b_ai = client.get(f"/api/v1/ai/analyze/{user_a_audit_id}", headers={"Authorization": user_b_token})
    assert b_ai.status_code == 403

    # User B CANNOT access User A's leads -> 403 Forbidden
    b_leads = client.get(f"/api/v1/leads/{user_a_website_id}", headers={"Authorization": user_b_token})
    assert b_leads.status_code == 403

    # User B CANNOT export User A's report -> 403 Forbidden
    b_export = client.post(
        "/api/v1/reports/export",
        headers={"Authorization": user_b_token},
        json={"website_id": user_a_website_id, "format": "pdf"}
    )
    assert b_export.status_code == 403

    # User B CANNOT stream User A's CSV report -> 403 Forbidden
    b_stream = client.get(
        f"/api/v1/reports/export/{user_a_website_id}/csv/stream",
        headers={"Authorization": user_b_token}
    )
    assert b_stream.status_code == 403

    # User B CANNOT access User A's Sheets export payload -> 403 Forbidden
    b_sheets = client.get(
        f"/api/v1/reports/export/{user_a_website_id}/sheets",
        headers={"Authorization": user_b_token}
    )
    assert b_sheets.status_code == 403

    # User A CAN stream their CSV report and access Sheets export payload
    a_stream = client.get(
        f"/api/v1/reports/export/{user_a_website_id}/csv/stream",
        headers={"Authorization": user_a_token}
    )
    assert a_stream.status_code == 200
    assert "Audit ID,Website ID,Domain" in a_stream.text

    a_sheets = client.get(
        f"/api/v1/reports/export/{user_a_website_id}/sheets",
        headers={"Authorization": user_a_token}
    )
    assert a_sheets.status_code == 200
    assert a_sheets.json()["domain"] == "usera-exclusive-fastapi.com"

    # User B CANNOT delete User A's website -> 403 Forbidden
    b_delete = client.delete(f"/api/v1/websites/{user_a_website_id}", headers={"Authorization": user_b_token})
    assert b_delete.status_code == 403

    # User B listing websites returns ONLY User B resources (User A site is excluded)
    b_list = client.get("/api/v1/websites", headers={"Authorization": user_b_token})
    assert b_list.status_code == 200
    assert not any(w["id"] == user_a_website_id for w in b_list.json())

def test_non_existent_resources_return_404(client: TestClient):
    user_a_token = "Bearer token_user_1"
    assert client.get("/api/v1/websites/99999", headers={"Authorization": user_a_token}).status_code == 404
    assert client.delete("/api/v1/websites/99999", headers={"Authorization": user_a_token}).status_code == 404
    assert client.get("/api/v1/ai/analyze/99999", headers={"Authorization": user_a_token}).status_code == 404
    assert client.get("/api/v1/leads/99999", headers={"Authorization": user_a_token}).status_code == 404
