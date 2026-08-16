import pytest
from fastapi.testclient import TestClient

def test_full_e2e_user_workflow(client: TestClient):
    """
    End-to-End Integration Test:
    1. User Registration & Authentication
    2. Website Creation & Listing (with cursor pagination)
    3. Site-Level Audit Job Dispatch & Progress Check
    4. Keyword Ideas Generation & Caching
    5. Domain Metrics Retrieval
    6. Exporting Reports
    """
    # 1. Registration & Authentication
    user_email = "e2e_user@example.com"
    user_name = "e2e_user"
    reg_res = client.post("/api/v1/auth/register", json={"email": user_email, "username": user_name})
    assert reg_res.status_code == 200, f"Registration failed: {reg_res.text}"
    auth_data = reg_res.json()
    token = f"Bearer {auth_data['access_token']}"
    headers = {"Authorization": token}

    # Verify /me endpoint
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == user_email

    # 2. Website Creation
    site_payload = {
        "url": "https://e2e-demo-site.com",
        "domain": "e2e-demo-site.com",
        "company_name": "E2E Demo Corp"
    }
    create_site_res = client.post("/api/v1/websites", headers=headers, json=site_payload)
    assert create_site_res.status_code == 200, f"Website creation failed: {create_site_res.text}"
    site_data = create_site_res.json()
    website_id = site_data["id"]

    # List websites with cursor
    cursor_res = client.get("/api/v1/websites/cursor?limit=10", headers=headers)
    assert cursor_res.status_code == 200
    cursor_data = cursor_res.json()
    assert "items" in cursor_data
    assert len(cursor_data["items"]) >= 1

    # 3. Create Audit Job
    audit_job_payload = {
        "website_id": website_id,
        "url": "https://e2e-demo-site.com"
    }
    job_res = client.post("/api/v1/jobs/audit", headers=headers, json=audit_job_payload)
    assert job_res.status_code == 200, f"Audit job dispatch failed: {job_res.text}"
    job_data = job_res.json()
    job_id = job_data["id"]

    # Verify job status via GET /jobs/{id}
    job_check = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert job_check.status_code == 200
    assert job_check.json()["id"] == job_id

    # 4. Keyword Research & Ideas
    kw_res = client.post("/api/v1/keywords/ideas", headers=headers, json={"seed_keyword": "e2e seo test", "limit": 5})
    assert kw_res.status_code == 200
    kw_ideas = kw_res.json()
    assert isinstance(kw_ideas, list)
    assert len(kw_ideas) > 0

    # 5. Domain Metrics
    metrics_res = client.post("/api/v1/domain-metrics", headers=headers, json={"domain": "e2e-demo-site.com"})
    assert metrics_res.status_code == 200
    metrics_data = metrics_res.json()
    assert metrics_data["domain"] == "e2e-demo-site.com"
    assert "domain_authority" in metrics_data

    # 6. Export Reports
    export_payload = {
        "format": "csv",
        "website_id": website_id
    }
    export_res = client.post("/api/v1/reports/export", headers=headers, json=export_payload)
    assert export_res.status_code == 200
    assert export_res.headers["content-type"].startswith("text/csv") or "csv" in export_res.headers.get("content-type", "")
