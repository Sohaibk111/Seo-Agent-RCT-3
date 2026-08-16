import pytest
from fastapi.testclient import TestClient

def test_projects_full_lifecycle_and_rbac(client: TestClient):
    # 1. Register Owner (User 1)
    owner_reg = client.post("/api/v1/auth/register", json={"email": "proj_owner@corp.com", "username": "proj_owner"})
    assert owner_reg.status_code == 200, owner_reg.text
    owner_token = owner_reg.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    owner_id = owner_reg.json()["id"]

    # 2. Register Member (User 2)
    member_reg = client.post("/api/v1/auth/register", json={"email": "proj_member@corp.com", "username": "proj_member"})
    assert member_reg.status_code == 200, member_reg.text
    member_token = member_reg.json()["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}
    member_id = member_reg.json()["id"]

    # 3. Register Viewer (User 3)
    viewer_reg = client.post("/api/v1/auth/register", json={"email": "proj_viewer@corp.com", "username": "proj_viewer"})
    assert viewer_reg.status_code == 200, viewer_reg.text
    viewer_token = viewer_reg.json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    viewer_id = viewer_reg.json()["id"]

    # 4. Register Non-member outsider (User 4)
    outsider_reg = client.post("/api/v1/auth/register", json={"email": "outsider@corp.com", "username": "outsider"})
    assert outsider_reg.status_code == 200, outsider_reg.text
    outsider_token = outsider_reg.json()["access_token"]
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

    # 5. Create Organization
    org_res = client.post(
        "/api/v1/orgs",
        headers=owner_headers,
        json={"name": "Global SEO Corp", "slug": "global-seo-corp"}
    )
    assert org_res.status_code == 200, org_res.text
    org_id = org_res.json()["id"]

    # 6. Add Member and Viewer to Org
    invite_member = client.post(
        f"/api/v1/orgs/{org_id}/invitations",
        headers=owner_headers,
        json={"email": "proj_member@corp.com", "role": "Member"}
    )
    assert invite_member.status_code == 200, invite_member.text
    client.post("/api/v1/orgs/invitations/confirm", headers=member_headers, json={"token": invite_member.json()["token"]})

    invite_viewer = client.post(
        f"/api/v1/orgs/{org_id}/invitations",
        headers=owner_headers,
        json={"email": "proj_viewer@corp.com", "role": "Viewer"}
    )
    assert invite_viewer.status_code == 200, invite_viewer.text
    client.post("/api/v1/orgs/invitations/confirm", headers=viewer_headers, json={"token": invite_viewer.json()["token"]})

    # 7. Validate Slug Check
    slug_check = client.get(f"/api/v1/orgs/{org_id}/projects/validate-slug?slug=e-commerce-portal", headers=owner_headers)
    assert slug_check.status_code == 200, slug_check.text
    assert slug_check.json()["available"] is True

    # 8. Create Project by Member
    create_proj_res = client.post(
        f"/api/v1/orgs/{org_id}/projects",
        headers=member_headers,
        json={
            "name": "E-Commerce Portal",
            "slug": "e-commerce-portal",
            "description": "Primary store SEO tracking",
            "status": "active",
            "color": "#3B82F6",
            "icon": "shopping-cart",
            "timezone": "America/New_York",
            "language": "en",
            "settings": {"crawl_depth": 5, "auto_audit": True}
        }
    )
    assert create_proj_res.status_code == 201, create_proj_res.text
    project = create_proj_res.json()
    project_id = project["id"]
    assert project["name"] == "E-Commerce Portal"
    assert project["slug"] == "e-commerce-portal"
    assert project["owner_id"] == member_id
    assert project["archived"] is False

    # 9. Slug duplicate prevention
    duplicate_res = client.post(
        f"/api/v1/orgs/{org_id}/projects",
        headers=owner_headers,
        json={"name": "Duplicate E-Commerce", "slug": "e-commerce-portal"}
    )
    assert duplicate_res.status_code == 409, duplicate_res.text

    # 10. Viewer cannot create projects
    viewer_create = client.post(
        f"/api/v1/orgs/{org_id}/projects",
        headers=viewer_headers,
        json={"name": "Viewer Project"}
    )
    assert viewer_create.status_code == 403, viewer_create.text

    # 11. Outsider cannot access organization projects
    outsider_list = client.get(f"/api/v1/orgs/{org_id}/projects", headers=outsider_headers)
    assert outsider_list.status_code == 403, outsider_list.text

    # 12. List projects in Org
    list_res = client.get(f"/api/v1/orgs/{org_id}/projects?search=portal", headers=viewer_headers)
    assert list_res.status_code == 200, list_res.text
    assert list_res.json()["total"] == 1
    assert list_res.json()["items"][0]["id"] == project_id

    # 13. Get Project details
    get_res = client.get(f"/api/v1/orgs/{org_id}/projects/{project_id}", headers=viewer_headers)
    assert get_res.status_code == 200, get_res.text
    assert get_res.json()["slug"] == "e-commerce-portal"

    # 14. Update Project by owner
    patch_res = client.patch(
        f"/api/v1/orgs/{org_id}/projects/{project_id}",
        headers=member_headers,
        json={"description": "Updated primary store SEO tracking and ranking", "color": "#10B981"}
    )
    assert patch_res.status_code == 200, patch_res.text
    assert patch_res.json()["description"] == "Updated primary store SEO tracking and ranking"
    assert patch_res.json()["color"] == "#10B981"

    # 15. Update Project Settings
    settings_res = client.put(
        f"/api/v1/orgs/{org_id}/projects/{project_id}/settings",
        headers=member_headers,
        json={"settings": {"crawl_depth": 10, "alerts_enabled": True}}
    )
    assert settings_res.status_code == 200, settings_res.text
    assert settings_res.json()["settings"]["crawl_depth"] == 10

    # 16. Get Project Stats
    stats_res = client.get(f"/api/v1/orgs/{org_id}/projects/{project_id}/stats", headers=viewer_headers)
    assert stats_res.status_code == 200, stats_res.text
    assert stats_res.json()["project_id"] == project_id
    assert stats_res.json()["settings_count"] == 2

    # 17. Archive and Restore
    archive_res = client.post(f"/api/v1/orgs/{org_id}/projects/{project_id}/archive", headers=owner_headers)
    assert archive_res.status_code == 200, archive_res.text
    assert archive_res.json()["archived"] is True
    assert archive_res.json()["status"] == "archived"

    restore_res = client.post(f"/api/v1/orgs/{org_id}/projects/{project_id}/restore", headers=owner_headers)
    assert restore_res.status_code == 200, restore_res.text
    assert restore_res.json()["archived"] is False
    assert restore_res.json()["status"] == "active"

    # 18. Direct shortcut endpoint /projects/{id}
    direct_get = client.get(f"/api/v1/projects/{project_id}", headers=viewer_headers)
    assert direct_get.status_code == 200, direct_get.text
    assert direct_get.json()["id"] == project_id

    # 19. Delete project by Owner (Admin+ only)
    delete_res = client.delete(f"/api/v1/orgs/{org_id}/projects/{project_id}", headers=owner_headers)
    assert delete_res.status_code == 200, delete_res.text
    assert delete_res.json()["id"] == project_id

    # 20. Verify deletion
    verify_get = client.get(f"/api/v1/orgs/{org_id}/projects/{project_id}", headers=owner_headers)
    assert verify_get.status_code == 404, verify_get.text
