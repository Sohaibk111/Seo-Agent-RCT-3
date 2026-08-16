from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_async_db
from backend.database import crud, schemas
from backend.auth.dependencies import get_current_user
from backend.database.models import User, Membership, Project, Website
from backend.exceptions import (
    ForbiddenException,
    ResourceNotFoundException,
    ConflictException,
    ValidationErrorException,
    SEOAgentException
)
from backend.services.audit_service import log_audit_event_async

router = APIRouter(tags=["Website Management"])


async def get_project_with_auth(
    project_id: int,
    current_user: User,
    db: AsyncSession,
    min_role: Optional[str] = None
) -> tuple[Project, Membership]:
    """Retrieve project and verify current user is a member of its organization."""
    project = await crud.get_project_async(db, project_id=project_id)
    if not project:
        raise ResourceNotFoundException("Project not found")

    membership = await crud.get_membership_async(db, org_id=project.organization_id, user_id=current_user.id)
    if not membership:
        raise ForbiddenException("You do not have access to this project's organization")

    if min_role and not crud.check_role_permission(membership.role, min_role):
        raise ForbiddenException(f"Action requires at least '{min_role}' role in this organization")

    return project, membership


async def get_website_with_auth(
    website_id: int,
    current_user: User,
    db: AsyncSession,
    action: str = "read"
) -> tuple[Website, Optional[Membership]]:
    """
    Retrieve website and check organization/owner permissions:
    - read: Viewer+ or legacy owner
    - update: Manager+ or website owner
    - delete: Admin+ or org owner
    """
    website = await crud.get_project_website_by_id_async(db, website_id=website_id)
    if not website:
        raise ResourceNotFoundException("Website not found")

    if website.organization_id:
        membership = await crud.get_membership_async(db, org_id=website.organization_id, user_id=current_user.id)
        if not membership:
            raise ForbiddenException("You do not have access to this website")

        if action == "delete":
            if not crud.check_role_permission(membership.role, "Admin"):
                raise ForbiddenException("Action requires at least 'Admin' role in this organization")
        elif action == "update":
            is_owner = (website.owner_id == current_user.id or website.user_id == current_user.id)
            is_manager = crud.check_role_permission(membership.role, "Manager")
            if not is_owner and not is_manager:
                raise ForbiddenException("You must be the website owner or have at least 'Manager' role to update")
        else:
            # action == "read"
            if not crud.check_role_permission(membership.role, "Viewer"):
                raise ForbiddenException("Access denied")

        return website, membership
    else:
        # Legacy fallback if no organization_id
        if website.user_id != current_user.id and website.owner_id != current_user.id:
            raise ForbiddenException("You do not own this website")
        return website, None


# --- PROJECT-SCOPED WEBSITE ENDPOINTS ---

@router.post("/projects/{project_id}/websites", response_model=schemas.WebsiteOut, status_code=201)
async def create_website(
    project_id: int,
    payload: schemas.WebsiteCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Create a new website in a project. Requires Member role or above."""
    project, membership = await get_project_with_auth(project_id, current_user, db, min_role="Member")

    # Domain normalization and validation
    try:
        canonical_domain = crud.normalize_domain_name(payload.domain)
    except ValueError as e:
        raise ValidationErrorException(str(e))

    # Check domain uniqueness within project
    is_unique = await crud.validate_website_domain_unique_in_project_async(
        db=db,
        project_id=project_id,
        domain=canonical_domain
    )
    if not is_unique:
        raise ConflictException(f"Website domain '{canonical_domain}' is already registered in this project")

    owner_id = payload.owner_id if payload.owner_id is not None else current_user.id
    if owner_id:
        is_member = await crud.validate_project_owner_async(db, organization_id=project.organization_id, owner_id=owner_id)
        if not is_member:
            raise ValidationErrorException("Website owner must be an active member of this organization")

    name = payload.name.strip() if payload.name else canonical_domain

    website = await crud.create_website_in_project_async(
        db=db,
        project_id=project_id,
        organization_id=project.organization_id,
        domain=canonical_domain,
        name=name,
        description=payload.description,
        status=payload.status or "active",
        settings=payload.settings or {},
        metadata=payload.metadata or {},
        owner_id=owner_id
    )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_audit_event_async(
        db=db,
        user_id=current_user.id,
        organization_id=project.organization_id,
        action="website.created",
        target_resource=f"website:{website.id}",
        ip_address=client_ip,
        user_agent=user_agent,
        details={"domain": website.domain, "name": website.name, "project_id": project_id}
    )

    return website


@router.get("/projects/{project_id}/websites", response_model=schemas.WebsitePaginated)
async def list_project_websites(
    project_id: int,
    search: Optional[str] = Query(None, description="Search query across domain, name, description"),
    status: Optional[str] = Query(None, description="Filter by status (active, paused, archived, draft)"),
    archived: Optional[bool] = Query(False, description="Filter archived websites"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field (created_at, domain, name, status)"),
    order: str = Query("desc", description="Sort order (asc or desc)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """List and search websites within a project with pagination and filters."""
    await get_project_with_auth(project_id, current_user, db, min_role="Viewer")

    skip = (page - 1) * size
    items = await crud.get_websites_by_project_async(
        db=db,
        project_id=project_id,
        skip=skip,
        limit=size,
        status=status,
        archived=archived,
        search=search,
        sort_by=sort_by,
        order=order
    )

    total = await crud.count_websites_by_project_async(
        db=db,
        project_id=project_id,
        status=status,
        archived=archived,
        search=search
    )

    total_pages = (total + size - 1) // size if total > 0 else 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "total_pages": total_pages
    }


@router.get("/projects/{project_id}/websites/validate-domain")
async def validate_domain_endpoint(
    project_id: int,
    domain: str = Query(..., description="Domain name to check for availability in this project"),
    exclude_website_id: Optional[int] = Query(None, description="Exclude website ID for update checks"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Validate whether a domain is valid and available within the given project."""
    await get_project_with_auth(project_id, current_user, db, min_role="Viewer")

    try:
        canonical_domain = crud.normalize_domain_name(domain)
    except ValueError as e:
        return {
            "domain": domain,
            "canonical_domain": None,
            "available": False,
            "valid": False,
            "reason": str(e)
        }

    is_unique = await crud.validate_website_domain_unique_in_project_async(
        db=db,
        project_id=project_id,
        domain=canonical_domain,
        exclude_website_id=exclude_website_id
    )

    return {
        "domain": domain,
        "canonical_domain": canonical_domain,
        "available": is_unique,
        "valid": True,
        "reason": None if is_unique else "Domain already exists in this project"
    }


# --- DIRECT WEBSITE ENDPOINTS (/websites/{website_id}) ---

@router.get("/websites/{website_id}", response_model=schemas.WebsiteOut)
async def get_website(
    website_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Retrieve website details. Requires Viewer role or above in the website's organization."""
    website, _ = await get_website_with_auth(website_id, current_user, db, action="read")
    return website


@router.patch("/websites/{website_id}", response_model=schemas.WebsiteOut)
async def update_website(
    website_id: int,
    payload: schemas.WebsiteUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Update website properties. Requires Manager role or website owner."""
    website, membership = await get_website_with_auth(website_id, current_user, db, action="update")

    # If domain is changing, check uniqueness within project
    if payload.domain is not None:
        try:
            new_domain = crud.normalize_domain_name(payload.domain)
        except ValueError as e:
            raise ValidationErrorException(str(e))

        if website.project_id:
            is_unique = await crud.validate_website_domain_unique_in_project_async(
                db=db,
                project_id=website.project_id,
                domain=new_domain,
                exclude_website_id=website.id
            )
            if not is_unique:
                raise ConflictException(f"Domain '{new_domain}' already exists in this project")

    if payload.owner_id is not None and website.organization_id:
        is_member = await crud.validate_project_owner_async(
            db, organization_id=website.organization_id, owner_id=payload.owner_id
        )
        if not is_member:
            raise ValidationErrorException("Website owner must be an active member of this organization")

    updated_site = await crud.update_website_async(
        db=db,
        website=website,
        name=payload.name,
        domain=payload.domain,
        description=payload.description,
        status=payload.status,
        settings=payload.settings,
        metadata=payload.metadata,
        owner_id=payload.owner_id
    )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_audit_event_async(
        db=db,
        user_id=current_user.id,
        organization_id=website.organization_id,
        action="website.updated",
        target_resource=f"website:{website.id}",
        ip_address=client_ip,
        user_agent=user_agent,
        details={"name": updated_site.name, "domain": updated_site.domain, "status": updated_site.status}
    )

    return updated_site


@router.delete("/websites/{website_id}")
async def delete_website(
    website_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Delete a website. Requires Admin role or above."""
    website, _ = await get_website_with_auth(website_id, current_user, db, action="delete")

    org_id = website.organization_id
    domain = website.domain

    await crud.delete_website_async(db, website)

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_audit_event_async(
        db=db,
        user_id=current_user.id,
        organization_id=org_id,
        action="website.deleted",
        target_resource=f"website:{website_id}",
        ip_address=client_ip,
        user_agent=user_agent,
        details={"website_id": website_id, "domain": domain}
    )

    return {"message": "Website deleted successfully", "id": website_id}


@router.post("/websites/{website_id}/archive", response_model=schemas.WebsiteOut)
async def archive_website(
    website_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Archive a website. Requires Manager role or website owner."""
    website, _ = await get_website_with_auth(website_id, current_user, db, action="update")

    archived_site = await crud.archive_website_async(db, website)

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_audit_event_async(
        db=db,
        user_id=current_user.id,
        organization_id=website.organization_id,
        action="website.archived",
        target_resource=f"website:{website.id}",
        ip_address=client_ip,
        user_agent=user_agent,
        details={"domain": archived_site.domain}
    )

    return archived_site


@router.post("/websites/{website_id}/restore", response_model=schemas.WebsiteOut)
async def restore_website(
    website_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Restore an archived website. Requires Manager role or website owner."""
    website, _ = await get_website_with_auth(website_id, current_user, db, action="update")

    restored_site = await crud.restore_website_async(db, website)

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_audit_event_async(
        db=db,
        user_id=current_user.id,
        organization_id=website.organization_id,
        action="website.restored",
        target_resource=f"website:{website.id}",
        ip_address=client_ip,
        user_agent=user_agent,
        details={"domain": restored_site.domain}
    )

    return restored_site


@router.get("/websites/{website_id}/settings")
async def get_website_settings(
    website_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Retrieve website settings JSON payload."""
    website, _ = await get_website_with_auth(website_id, current_user, db, action="read")
    return {"website_id": website.id, "domain": website.domain, "settings": website.settings or {}}


@router.put("/websites/{website_id}/settings")
async def update_website_settings(
    website_id: int,
    payload: schemas.WebsiteSettingsUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Update website settings JSON. Requires Manager role or website owner."""
    website, _ = await get_website_with_auth(website_id, current_user, db, action="update")

    updated_site = await crud.update_website_async(
        db=db,
        website=website,
        settings=payload.settings
    )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_audit_event_async(
        db=db,
        user_id=current_user.id,
        organization_id=website.organization_id,
        action="website.settings_updated",
        target_resource=f"website:{website.id}",
        ip_address=client_ip,
        user_agent=user_agent,
        details={"settings_keys": list(payload.settings.keys())}
    )

    return {"website_id": updated_site.id, "domain": updated_site.domain, "settings": updated_site.settings}


@router.get("/websites/{website_id}/metadata", response_model=schemas.WebsiteMetadataOut)
async def get_website_metadata(
    website_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Retrieve website metadata."""
    website, _ = await get_website_with_auth(website_id, current_user, db, action="read")
    return {
        "website_id": website.id,
        "project_id": website.project_id,
        "organization_id": website.organization_id,
        "domain": website.domain,
        "name": website.name,
        "status": website.status,
        "archived": website.archived,
        "created_at": website.created_at,
        "updated_at": website.updated_at,
        "metadata": website.metadata_json or {}
    }


@router.get("/websites/{website_id}/stats", response_model=schemas.WebsiteStatsOut)
async def get_website_stats(
    website_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Retrieve foundational website statistics."""
    website, _ = await get_website_with_auth(website_id, current_user, db, action="read")
    stats = await crud.get_website_stats_async(db, website)
    return stats
