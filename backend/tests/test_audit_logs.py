import pytest
from fastapi.testclient import TestClient


def test_audit_logging_full_lifecycle(client: TestClient):
    # 1. Register User
    reg_res = client.post("/api/v1/auth/register", json={"email": "audit_user@acme.com", "username": "audit_user"})
    assert reg_res.status_code == 200, reg_res.text
    user_token = reg_res.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}
    user_id = reg_res.json()["id"]

    # 2. Login -> user.login
    login_res = client.post("/api/v1/auth/login", json={"email": "audit_user@acme.com", "password": "password123"})
    assert login_res.status_code == 200, login_res.text

    # 3. Profile Update -> user.profile_update
    profile_res = client.put(
        "/api/v1/auth/profile",
        headers=user_headers,
        json={"timezone": "UTC", "language": "en"}
    )
    assert profile_res.status_code == 200, profile_res.text

    # 4. API Key Creation -> api_key.created
    key_res = client.post(
        "/api/v1/auth/api-keys",
        headers=user_headers,
        json={"name": "Production Key"}
    )
    assert key_res.status_code == 200, key_res.text

    # 5. Create Project -> project.created
    project_res = client.post(
        "/api/v1/websites",
        headers=user_headers,
        json={"url": "https://audit-test.com", "company_name": "Audit Test Inc"}
    )
    assert project_res.status_code == 200, project_res.text
    project_id = project_res.json()["id"]

    # 6. Delete Project -> project.deleted
    del_project_res = client.delete(
        f"/api/v1/websites/{project_id}",
        headers=user_headers
    )
    assert del_project_res.status_code == 200, del_project_res.text

    # 7. Create Organization -> org.created
    org_res = client.post(
        "/api/v1/orgs",
        headers=user_headers,
        json={"name": "Audit Org", "slug": "audit-org"}
    )
    assert org_res.status_code == 200, org_res.text
    org_id = org_res.json()["id"]

    # 8. Update Organization Settings -> settings.changed
    update_org_res = client.put(
        f"/api/v1/orgs/{org_id}",
        headers=user_headers,
        json={"name": "Audit Org Updated", "primary_color": "#123456"}
    )
    assert update_org_res.status_code == 200, update_org_res.text

    # 9. Register second user & invite -> invitation.sent
    member_reg = client.post("/api/v1/auth/register", json={"email": "invitee@acme.com", "username": "invitee_user"})
    assert member_reg.status_code == 200
    invitee_token = member_reg.json()["access_token"]
    invitee_headers = {"Authorization": f"Bearer {invitee_token}"}
    invitee_id = member_reg.json()["id"]

    invite_res = client.post(
        f"/api/v1/orgs/{org_id}/invitations",
        headers=user_headers,
        json={"email": "invitee@acme.com", "role": "Member"}
    )
    assert invite_res.status_code == 200
    inv_token = invite_res.json()["token"]

    # 10. Accept Invitation -> invitation.accepted
    accept_res = client.post(
        "/api/v1/orgs/invitations/accept",
        headers=invitee_headers,
        json={"token": inv_token}
    )
    assert accept_res.status_code == 200

    # 11. Role Changed -> role.changed
    role_res = client.put(
        f"/api/v1/orgs/{org_id}/members/{invitee_id}/role",
        headers=user_headers,
        json={"role": "Manager"}
    )
    assert role_res.status_code == 200

    # 12. Remove Member -> member.removed
    remove_res = client.delete(
        f"/api/v1/orgs/{org_id}/members/{invitee_id}",
        headers=user_headers
    )
    assert remove_res.status_code == 200

    # 13. Query Audit Logs (List, Filter, Pagination, Search)
    audit_list_res = client.get("/api/v1/audit-logs", headers=user_headers)
    assert audit_list_res.status_code == 200, audit_list_res.text
    audit_data = audit_list_res.json()
    assert audit_data["total"] >= 10
    actions = [item["action"] for item in audit_data["items"]]
    assert "user.login" in actions
    assert "user.profile_update" in actions
    assert "api_key.created" in actions
    assert "project.created" in actions
    assert "project.deleted" in actions
    assert "org.created" in actions
    assert "settings.changed" in actions
    assert "invitation.sent" in actions
    assert "role.changed" in actions
    assert "member.removed" in actions

    # Test Action Filtering
    filtered_res = client.get("/api/v1/audit-logs?action=project.created", headers=user_headers)
    assert filtered_res.status_code == 200
    filtered_items = filtered_res.json()["items"]
    assert all(i["action"] == "project.created" for i in filtered_items)

    # Test Search Filtering
    search_res = client.get("/api/v1/audit-logs?search=Audit%20Org", headers=user_headers)
    assert search_res.status_code == 200
    assert len(search_res.json()["items"]) >= 1

    # Test Pagination
    page_res = client.get("/api/v1/audit-logs?page=1&size=2", headers=user_headers)
    assert page_res.status_code == 200
    assert len(page_res.json()["items"]) == 2
    assert page_res.json()["total_pages"] >= 5

    # 14. Export CSV & JSON
    export_csv_res = client.get("/api/v1/audit-logs/export?format=csv", headers=user_headers)
    assert export_csv_res.status_code == 200
    assert "text/csv" in export_csv_res.headers["content-type"]
    assert "Action,User ID" in export_csv_res.text or "ID,Timestamp" in export_csv_res.text

    export_json_res = client.get("/api/v1/audit-logs/export?format=json", headers=user_headers)
    assert export_json_res.status_code == 200
    assert "application/json" in export_json_res.headers["content-type"]
    assert len(export_json_res.json()) >= 10

    # 15. Delete Organization -> org.deleted
    del_org_res = client.delete(
        f"/api/v1/orgs/{org_id}",
        headers=user_headers
    )
    assert del_org_res.status_code == 200
