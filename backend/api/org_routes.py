from datetime import datetime, timedelta
import secrets
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_async_db
from backend.database import crud, schemas
from backend.auth.dependencies import get_current_user
from backend.database.models import User, Membership
from backend.exceptions import (
    ForbiddenException,
    ResourceNotFoundException,
    ConflictException,
    ValidationErrorException,
    SEOAgentException
)
from backend.services.audit_service import log_audit_event_async

router = APIRouter(prefix="/orgs", tags=["Organizations & Teams"])


def slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    return slug.strip('-')


async def require_membership(
    org_id: int,
    current_user: User,
    db: AsyncSession
) -> Membership:
    membership = await crud.get_membership_async(db, org_id=org_id, user_id=current_user.id)
    if not membership:
        raise ForbiddenException("You are not a member of this organization")
    return membership


def check_role_min(membership: Membership, required_role: str):
    if not crud.check_role_permission(membership.role, required_role):
        raise ForbiddenException(f"Action requires at least '{required_role}' role in this organization")


# --- ORGANIZATION ENDPOINTS ---

@router.post("", response_model=schemas.OrganizationOut)
async def create_organization(
    org_in: schemas.OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    slug = org_in.slug or slugify(org_in.name)
    if not slug:
        slug = f"org-{secrets.token_hex(4)}"

    # Ensure unique slug
    existing = await crud.get_organization_by_slug_async(db, slug=slug)
    if existing:
        slug = f"{slug}-{secrets.token_hex(3)}"

    org = await crud.create_organization_async(
        db,
        name=org_in.name,
        slug=slug,
        creator_user_id=current_user.id,
        logo_url=org_in.logo_url,
        primary_color=org_in.primary_color,
        settings=org_in.settings
    )
    await log_audit_event_async(
        db=db,
        action="org.created",
        user_id=current_user.id,
        organization_id=org.id,
        target_resource=f"org:{org.id}",
        details={"name": org.name, "slug": org.slug}
    )
    return org


@router.get("", response_model=List[schemas.OrganizationOut])
async def list_my_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    orgs = await crud.get_user_organizations_async(db, user_id=current_user.id)
    return orgs


@router.get("/{org_id}", response_model=schemas.OrganizationOut)
async def get_organization_details(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    await require_membership(org_id, current_user, db)
    org = await crud.get_organization_async(db, org_id=org_id)
    if not org:
        raise ResourceNotFoundException("Organization not found")
    return org


@router.put("/{org_id}", response_model=schemas.OrganizationOut)
async def update_organization(
    org_id: int,
    org_in: schemas.OrganizationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    membership = await require_membership(org_id, current_user, db)
    check_role_min(membership, "Admin")

    org = await crud.get_organization_async(db, org_id=org_id)
    if not org:
        raise ResourceNotFoundException("Organization not found")

    new_slug = org_in.slug
    if new_slug and new_slug != org.slug:
        existing = await crud.get_organization_by_slug_async(db, slug=new_slug)
        if existing:
            raise ConflictException("Organization slug already taken")

    updated_org = await crud.update_organization_async(
        db,
        org=org,
        name=org_in.name,
        slug=new_slug,
        logo_url=org_in.logo_url,
        primary_color=org_in.primary_color,
        settings=org_in.settings,
        actor_id=current_user.id
    )
    await log_audit_event_async(
        db=db,
        action="settings.changed",
        user_id=current_user.id,
        organization_id=org_id,
        target_resource=f"org:{org_id}",
        details=org_in.model_dump(exclude_unset=True)
    )
    return updated_org


@router.delete("/{org_id}", response_model=dict)
async def delete_organization(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    membership = await require_membership(org_id, current_user, db)
    check_role_min(membership, "Owner")

    org = await crud.get_organization_async(db, org_id=org_id)
    if not org:
        raise ResourceNotFoundException("Organization not found")

    await log_audit_event_async(
        db=db,
        action="org.deleted",
        user_id=current_user.id,
        organization_id=org_id,
        target_resource=f"org:{org_id}",
        details={"name": org.name}
    )
    await crud.delete_organization_async(db, org=org, actor_id=current_user.id)
    return {"message": "Organization deleted successfully"}


@router.post("/{org_id}/transfer-ownership", response_model=dict)
async def transfer_ownership(
    org_id: int,
    transfer_in: schemas.OwnershipTransfer,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    membership = await require_membership(org_id, current_user, db)
    check_role_min(membership, "Owner")

    if transfer_in.new_owner_user_id == current_user.id:
        raise ValidationErrorException("You are already the owner of this organization")

    success = await crud.transfer_org_ownership_async(
        db,
        org_id=org_id,
        current_owner_id=current_user.id,
        new_owner_id=transfer_in.new_owner_user_id
    )
    if not success:
        raise ResourceNotFoundException("Target user is not a member of this organization")

    return {"message": f"Ownership transferred to user {transfer_in.new_owner_user_id}"}


# --- MEMBERSHIP & ROLES ENDPOINTS ---

@router.get("/{org_id}/members", response_model=List[schemas.MembershipOut])
async def list_members(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    await require_membership(org_id, current_user, db)
    members = await crud.get_org_members_async(db, org_id=org_id)
    return members


@router.put("/{org_id}/members/{user_id}/role", response_model=schemas.MembershipOut)
async def change_member_role(
    org_id: int,
    user_id: int,
    role_in: schemas.MemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    actor_mem = await require_membership(org_id, current_user, db)
    check_role_min(actor_mem, "Manager")

    if role_in.role not in crud.ROLE_HIERARCHY:
        raise ValidationErrorException("Invalid role specified")

    if role_in.role == "Owner":
        raise ValidationErrorException("Use the transfer-ownership endpoint to set a new Owner")

    target_mem = await crud.get_membership_async(db, org_id=org_id, user_id=user_id)
    if not target_mem:
        raise ResourceNotFoundException("Member not found in organization")

    if target_mem.role == "Owner":
        raise ForbiddenException("Cannot change the role of the organization Owner")

    # Ensure actor has strictly higher rank than target user's current role and target role
    actor_rank = crud.ROLE_HIERARCHY.get(actor_mem.role, 0)
    target_current_rank = crud.ROLE_HIERARCHY.get(target_mem.role, 0)
    target_new_rank = crud.ROLE_HIERARCHY.get(role_in.role, 0)

    if actor_rank <= target_current_rank:
        raise ForbiddenException("You cannot modify the role of a member with equal or higher rank")
    if actor_rank <= target_new_rank:
        raise ForbiddenException("You cannot promote a member to a role equal to or higher than your own")

    updated_mem = await crud.update_member_role_async(
        db,
        org_id=org_id,
        user_id=user_id,
        new_role=role_in.role,
        actor_id=current_user.id
    )
    await log_audit_event_async(
        db=db,
        action="role.changed",
        user_id=current_user.id,
        organization_id=org_id,
        target_resource=f"user:{user_id}",
        details={"new_role": role_in.role}
    )
    return updated_mem


@router.delete("/{org_id}/members/{user_id}", response_model=dict)
async def remove_member(
    org_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    actor_mem = await require_membership(org_id, current_user, db)

    target_mem = await crud.get_membership_async(db, org_id=org_id, user_id=user_id)
    if not target_mem:
        raise ResourceNotFoundException("Member not found in organization")

    # Leaving organization case (removing self)
    if user_id == current_user.id:
        if actor_mem.role == "Owner":
            raise ValidationErrorException("Organization Owner cannot leave without transferring ownership first")
        await crud.remove_org_member_async(db, org_id=org_id, user_id=user_id, actor_id=current_user.id)
        return {"message": "You have left the organization"}

    # Removing another member
    check_role_min(actor_mem, "Manager")

    if target_mem.role == "Owner":
        raise ForbiddenException("Cannot remove the organization Owner")

    actor_rank = crud.ROLE_HIERARCHY.get(actor_mem.role, 0)
    target_rank = crud.ROLE_HIERARCHY.get(target_mem.role, 0)

    if actor_rank <= target_rank:
        raise ForbiddenException("You cannot remove a member with equal or higher rank")

    await crud.remove_org_member_async(db, org_id=org_id, user_id=user_id, actor_id=current_user.id)
    await log_audit_event_async(
        db=db,
        action="member.removed",
        user_id=current_user.id,
        organization_id=org_id,
        target_resource=f"user:{user_id}"
    )
    return {"message": "Member removed from organization"}


# --- INVITATIONS ENDPOINTS ---

@router.post("/{org_id}/invitations", response_model=schemas.InvitationOut)
async def invite_member(
    org_id: int,
    inv_in: schemas.InvitationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    actor_mem = await require_membership(org_id, current_user, db)
    check_role_min(actor_mem, "Manager")

    if inv_in.role not in crud.ROLE_HIERARCHY:
        raise ValidationErrorException("Invalid role specified")

    if inv_in.role == "Owner":
        raise ValidationErrorException("Cannot invite someone directly as Owner")

    actor_rank = crud.ROLE_HIERARCHY.get(actor_mem.role, 0)
    invited_rank = crud.ROLE_HIERARCHY.get(inv_in.role, 0)
    if actor_rank <= invited_rank:
        raise ForbiddenException("You cannot invite a member with a role equal to or higher than your own")

    # Check if user with email is already a member
    user = await crud.get_user_by_email_async(db, email=inv_in.email)
    if user:
        existing_mem = await crud.get_membership_async(db, org_id=org_id, user_id=user.id)
        if existing_mem:
            raise ConflictException("User is already a member of this organization")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=7)

    invitation = await crud.create_invitation_async(
        db,
        org_id=org_id,
        email=inv_in.email,
        role=inv_in.role,
        token=token,
        invited_by_id=current_user.id,
        expires_at=expires_at
    )
    await log_audit_event_async(
        db=db,
        action="invitation.sent",
        user_id=current_user.id,
        organization_id=org_id,
        target_resource=f"invitation:{invitation.id}",
        details={"email": inv_in.email, "role": inv_in.role}
    )
    return invitation


@router.get("/{org_id}/invitations", response_model=List[schemas.InvitationOut])
async def list_invitations(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    actor_mem = await require_membership(org_id, current_user, db)
    check_role_min(actor_mem, "Manager")

    invitations = await crud.get_org_invitations_async(db, org_id=org_id)
    return invitations


@router.post("/invitations/accept", response_model=schemas.MembershipOut)
async def accept_invitation(
    confirm: schemas.InvitationConfirm,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    invitation = await crud.get_invitation_by_token_async(db, token=confirm.token)
    if not invitation:
        raise ResourceNotFoundException("Invalid, expired, or used invitation token")

    if invitation.email.lower() != current_user.email.lower():
        raise ForbiddenException("This invitation was issued to a different email address")

    membership = await crud.accept_invitation_async(db, invitation=invitation, user=current_user)
    await log_audit_event_async(
        db=db,
        action="invitation.accepted",
        user_id=current_user.id,
        organization_id=membership.organization_id,
        target_resource=f"membership:{membership.id}",
        details={"role": membership.role}
    )
    return membership


@router.post("/invitations/reject", response_model=dict)
async def reject_invitation(
    confirm: schemas.InvitationConfirm,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    invitation = await crud.get_invitation_by_token_async(db, token=confirm.token)
    if not invitation:
        raise ResourceNotFoundException("Invalid, expired, or used invitation token")

    if invitation.email.lower() != current_user.email.lower():
        raise ForbiddenException("This invitation was issued to a different email address")

    await crud.reject_invitation_async(db, invitation=invitation, user=current_user)
    return {"message": "Invitation rejected"}


@router.delete("/{org_id}/invitations/{invitation_id}", response_model=dict)
async def cancel_invitation(
    org_id: int,
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    actor_mem = await require_membership(org_id, current_user, db)
    check_role_min(actor_mem, "Manager")

    invitations = await crud.get_org_invitations_async(db, org_id=org_id)
    target_inv = next((inv for inv in invitations if inv.id == invitation_id), None)
    if not target_inv:
        raise ResourceNotFoundException("Invitation not found")

    await crud.cancel_invitation_async(db, invitation=target_inv, actor_id=current_user.id)
    return {"message": "Invitation cancelled"}


# --- AUDIT LOGS ENDPOINT ---

@router.get("/{org_id}/audit-logs", response_model=List[schemas.OrganizationAuditEventOut])
async def list_audit_logs(
    org_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    actor_mem = await require_membership(org_id, current_user, db)
    check_role_min(actor_mem, "Admin")

    logs = await crud.get_org_audit_events_async(db, org_id=org_id, limit=limit)
    return logs
