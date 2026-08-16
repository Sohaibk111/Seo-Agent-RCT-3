import pytest
from fastapi.testclient import TestClient

def test_organization_full_lifecycle(client: TestClient):
    # 1. Register Owner (User 1)
    owner_reg = client.post("/api/v1/auth/register", json={"email": "owner@acme.com", "username": "owner_user"})
    assert owner_reg.status_code == 200, owner_reg.text
    owner_token = owner_reg.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    owner_id = owner_reg.json()["id"]

    # 2. Register Member candidate (User 2)
    member_reg = client.post("/api/v1/auth/register", json={"email": "member@acme.com", "username": "member_user"})
    assert member_reg.status_code == 200, member_reg.text
    member_token = member_reg.json()["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}
    member_id = member_reg.json()["id"]

    # 3. Create Organization
    create_res = client.post(
        "/api/v1/orgs",
        headers=owner_headers,
        json={
            "name": "Acme Corp",
            "slug": "acme-corp",
            "logo_url": "https://acme.com/logo.png",
            "primary_color": "#FF0000",
            "settings": {"enforce_mfa": True}
        }
    )
    assert create_res.status_code == 200, create_res.text
    org = create_res.json()
    org_id = org["id"]
    assert org["name"] == "Acme Corp"
    assert org["slug"] == "acme-corp"
    assert org["logo_url"] == "https://acme.com/logo.png"

    # 4. Get My Organizations
    my_orgs_res = client.get("/api/v1/orgs", headers=owner_headers)
    assert my_orgs_res.status_code == 200, my_orgs_res.text
    assert len(my_orgs_res.json()) >= 1
    assert any(o["id"] == org_id for o in my_orgs_res.json())

    # 5. Get Organization Details
    org_res = client.get(f"/api/v1/orgs/{org_id}", headers=owner_headers)
    assert org_res.status_code == 200, org_res.text
    assert org_res.json()["id"] == org_id

    # 6. Update Organization Settings & Branding
    update_res = client.put(
        f"/api/v1/orgs/{org_id}",
        headers=owner_headers,
        json={
            "name": "Acme Corporation",
            "primary_color": "#00FF00",
            "settings": {"enforce_mfa": True, "sso_enabled": True}
        }
    )
    assert update_res.status_code == 200, update_res.text
    assert update_res.json()["name"] == "Acme Corporation"
    assert update_res.json()["primary_color"] == "#00FF00"

    # 7. Invite Member by Email
    invite_res = client.post(
        f"/api/v1/orgs/{org_id}/invitations",
        headers=owner_headers,
        json={"email": "member@acme.com", "role": "Member"}
    )
    assert invite_res.status_code == 200, invite_res.text
    invitation = invite_res.json()
    assert invitation["email"] == "member@acme.com"
    assert invitation["role"] == "Member"
    inv_token = invitation["token"]

    # 8. List Pending Invitations
    invs_res = client.get(f"/api/v1/orgs/{org_id}/invitations", headers=owner_headers)
    assert invs_res.status_code == 200, invs_res.text
    assert len(invs_res.json()) >= 1

    # 9. Accept Invitation as Member (User 2)
    accept_res = client.post(
        "/api/v1/orgs/invitations/accept",
        headers=member_headers,
        json={"token": inv_token}
    )
    assert accept_res.status_code == 200, accept_res.text
    assert accept_res.json()["role"] == "Member"

    # 10. List Members
    members_res = client.get(f"/api/v1/orgs/{org_id}/members", headers=owner_headers)
    assert members_res.status_code == 200, members_res.text
    members = members_res.json()
    assert len(members) == 2

    # 11. Change Role: Owner promotes Member to Manager
    role_change_res = client.put(
        f"/api/v1/orgs/{org_id}/members/{member_id}/role",
        headers=owner_headers,
        json={"role": "Manager"}
    )
    assert role_change_res.status_code == 200, role_change_res.text
    assert role_change_res.json()["role"] == "Manager"

    # 12. RBAC Enforcement Test: Member/Manager cannot delete org or transfer ownership
    forbidden_del = client.delete(f"/api/v1/orgs/{org_id}", headers=member_headers)
    assert forbidden_del.status_code == 403

    forbidden_transfer = client.post(
        f"/api/v1/orgs/{org_id}/transfer-ownership",
        headers=member_headers,
        json={"new_owner_user_id": owner_id}
    )
    assert forbidden_transfer.status_code == 403

    # 13. Transfer Ownership from Owner to User 2
    transfer_res = client.post(
        f"/api/v1/orgs/{org_id}/transfer-ownership",
        headers=owner_headers,
        json={"new_owner_user_id": member_id}
    )
    assert transfer_res.status_code == 200, transfer_res.text

    # Verify User 2 is now Owner and User 1 is now Admin
    members_after_res = client.get(f"/api/v1/orgs/{org_id}/members", headers=member_headers)
    assert members_after_res.status_code == 200, members_after_res.text
    mem_map = {m["user_id"]: m["role"] for m in members_after_res.json()}
    assert mem_map[member_id] == "Owner"
    assert mem_map[owner_id] == "Admin"

    # 14. Audit Events
    audit_res = client.get(f"/api/v1/orgs/{org_id}/audit-logs", headers=member_headers)
    assert audit_res.status_code == 200, audit_res.text
    events = audit_res.json()
    assert len(events) >= 4
    actions = [e["action"] for e in events]
    assert "organization.created" in actions
    assert "ownership.transferred" in actions

    # 15. Delete Organization as New Owner (User 2)
    del_res = client.delete(f"/api/v1/orgs/{org_id}", headers=member_headers)
    assert del_res.status_code == 200, del_res.text
