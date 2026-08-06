import pytest
from fastapi.testclient import TestClient

def test_project_full_lifecycle_and_rbac(client: TestClient):
    # 1. Register Owner User
    owner_reg = client.post("/api/v1/auth/register", json={"email": "proj_owner@acme.com", "username": "proj_owner"})
    assert owner_reg.status_code == 200, owner_reg.text
    owner_token = owner_reg.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # 2. Register Member User
    member_reg = client.post("/api/v1/auth/register", json={"email": "proj_member@acme.com", "username": "proj_member"})
    assert member_reg.status_code == 200, member_reg.text
    member_token = member_reg.json()["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}
    member_id = member_reg.json()["id"]

    # 3. Register Outsider User
    outsider_reg = client.post("/api/v1/auth/register", json={"email": "outsider@other.com", "username": "outsider_user"})
    assert outsider_reg.status_code == 200, outsider_reg.text
    outsider_token = outsider_reg.json()["access_token"]
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

    # 4. Create Organization as Owner
    org_res = client.post(
        "/api/v1/orgs",
        headers=owner_headers,
        json={"name": "Project Workspace Org", "slug": "project-workspace-org"}
    )
    assert org_res.status_code == 200, org_res.text
    org_id = org_res.json()["id"]

    # 5. Invite Member User & Accept Invitation
    inv_res = client.post(
        f"/api/v1/orgs/{org_id}/invitations",
        headers=owner_headers,
        json={"email": "proj_member@acme.com", "role": "Member"}
    )
    assert inv_res.status_code == 200, inv_res.text
    token = inv_res.json()["token"]

    accept_res = client.post(
        "/api/v1/orgs/invitations/accept",
        headers=member_headers,
        json={"token": token}
    )
    assert accept_res.status_code == 200, accept_res.text

    # 6. Unauthenticated requests should fail (401)
    unauth_res = client.post(f"/api/v1/orgs/{org_id}/projects", json={"name": "Fail Proj"})
    assert unauth_res.status_code == 401

    # 7. Outsider requests should fail (403)
    outsider_create = client.post(
        f"/api/v1/orgs/{org_id}/projects",
        headers=outsider_headers,
        json={"name": "Outsider Proj"}
    )
    assert outsider_create.status_code == 403

    # 8. Create Project as Owner
    create_res = client.post(
        f"/api/v1/orgs/{org_id}/projects",
        headers=owner_headers,
        json={
            "name": "E-Commerce SEO Campaign",
            "slug": "ecommerce-seo",
            "description": "Primary organic growth initiative for e-commerce division",
            "status": "active",
            "color": "#3B82F6",
            "icon": "shopping-bag",
            "timezone": "America/New_York",
            "language": "en",
            "settings": {"crawl_frequency": "daily", "target_keywords": 250}
        }
    )
    assert create_res.status_code == 201, create_res.text
    proj = create_res.json()
    proj_id = proj["id"]
    assert proj["name"] == "E-Commerce SEO Campaign"
    assert proj["slug"] == "ecommerce-seo"
    assert proj["organization_id"] == org_id
    assert proj["archived"] is False
    assert proj["settings"]["crawl_frequency"] == "daily"

    # 9. Duplicate slug in same org returns 409 Conflict
    dup_res = client.post(
        f"/api/v1/orgs/{org_id}/projects",
        headers=owner_headers,
        json={"name": "Another E-Commerce", "slug": "ecommerce-seo"}
    )
    assert dup_res.status_code == 409

    # 10. Auto-generated slug when omitted
    auto_res = client.post(
        f"/api/v1/orgs/{org_id}/projects",
        headers=owner_headers,
        json={"name": "Brand Reputation & PR 2026"}
    )
    assert auto_res.status_code == 201, auto_res.text
    auto_proj = auto_res.json()
    assert auto_proj["slug"] == "brand-reputation-pr-2026"

    # 11. Get Project by ID and by Slug
    get_by_id = client.get(f"/api/v1/orgs/{org_id}/projects/{proj_id}", headers=member_headers)
    assert get_by_id.status_code == 200, get_by_id.text
    assert get_by_id.json()["id"] == proj_id

    get_by_slug = client.get(f"/api/v1/orgs/{org_id}/projects/ecommerce-seo", headers=member_headers)
    assert get_by_slug.status_code == 200, get_by_slug.text
    assert get_by_slug.json()["id"] == proj_id

    # 12. Update Project Details as Member
    update_res = client.put(
        f"/api/v1/orgs/{org_id}/projects/{proj_id}",
        headers=member_headers,
        json={
            "name": "Global E-Commerce SEO Campaign",
            "description": "Updated global campaign strategy"
        }
    )
    assert update_res.status_code == 200, update_res.text
    assert update_res.json()["name"] == "Global E-Commerce SEO Campaign"

    # 13. Get and Update Settings
    get_settings = client.get(f"/api/v1/orgs/{org_id}/projects/{proj_id}/settings", headers=member_headers)
    assert get_settings.status_code == 200, get_settings.text

    update_settings = client.put(
        f"/api/v1/orgs/{org_id}/projects/{proj_id}/settings",
        headers=member_headers,
        json={"settings": {"crawl_frequency": "weekly", "auto_audit": True}}
    )
    assert update_settings.status_code == 200, update_settings.text
    assert update_settings.json()["settings"]["auto_audit"] is True

    # 14. Get Metadata, Stats, and Activity
    meta_res = client.get(f"/api/v1/orgs/{org_id}/projects/{proj_id}/metadata", headers=member_headers)
    assert meta_res.status_code == 200, meta_res.text
    meta = meta_res.json()
    assert meta["project_id"] == proj_id
    assert meta["settings_count"] == 2

    stats_res = client.get(f"/api/v1/orgs/{org_id}/projects/{proj_id}/stats", headers=member_headers)
    assert stats_res.status_code == 200, stats_res.text
    stats = stats_res.json()
    assert stats["project_id"] == proj_id
    assert stats["settings_keys_count"] == 2

    activity_res = client.get(f"/api/v1/orgs/{org_id}/projects/{proj_id}/activity", headers=member_headers)
    assert activity_res.status_code == 200, activity_res.text
    activity = activity_res.json()
    assert isinstance(activity, list)

    # 15. Search and Filter Projects
    list_res = client.get(f"/api/v1/orgs/{org_id}/projects?search=Global", headers=member_headers)
    assert list_res.status_code == 200, list_res.text
    items = list_res.json()
    assert len(items) >= 1
    assert any(p["id"] == proj_id for p in items)

    # 16. Archive and Restore Project
    archive_res = client.post(f"/api/v1/orgs/{org_id}/projects/{proj_id}/archive", headers=member_headers)
    assert archive_res.status_code == 200, archive_res.text
    assert archive_res.json()["archived"] is True
    assert archive_res.json()["status"] == "archived"

    restore_res = client.post(f"/api/v1/orgs/{org_id}/projects/{proj_id}/restore", headers=member_headers)
    assert restore_res.status_code == 200, restore_res.text
    assert restore_res.json()["archived"] is False
    assert restore_res.json()["status"] == "active"

    # 17. Delete Project: Member role cannot delete (requires Admin/Owner)
    # Demote member user to Viewer or test Member delete permission
    # Member role should fail deletion if Admin is required
    member_delete = client.delete(f"/api/v1/orgs/{org_id}/projects/{proj_id}", headers=member_headers)
    assert member_delete.status_code == 403

    owner_delete = client.delete(f"/api/v1/orgs/{org_id}/projects/{proj_id}", headers=owner_headers)
    assert owner_delete.status_code == 200, owner_delete.text

    # 18. Verify Deleted Project returns 404
    get_deleted = client.get(f"/api/v1/orgs/{org_id}/projects/{proj_id}", headers=owner_headers)
    assert get_deleted.status_code == 404
