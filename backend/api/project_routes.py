from datetime import datetime
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_async_db
from backend.database import crud, schemas
from backend.auth.dependencies import get_current_user
from backend.database.models import User, Membership, Project
from backend.exceptions import (
    ForbiddenException,
    ResourceNotFoundException,
    ConflictException,
    ValidationErrorException,
    SEOAgentException
)
from backend.services.audit_service import log_audit_event_async

router = APIRouter(tags=["Project Management"])


def slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    return slug.strip('-')


async def require_org_membership(
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


async def get_project_by_id_or_slug(
    db: AsyncSession,
    org_id: int,
    project_identifier: str
) -> Project:
    if project_identifier.isdigit():
        project = await crud.get_project_async(db, project_id=int(project_identifier))
        if project and project.organization_id == org_id:
            return project

    project = await crud.get_project_by_slug_async(db, organization_id=org_id, slug=project_identifier)
    if not project:
        raise ResourceNotFoundException("Project not found in this organization")
    return project


# --- ORGANIZATION-SCOPED PROJECT ROUTES ---

@router.post("/orgs/{org_id}/projects", response_model=schemas.ProjectOut, status_code=201)
async def create_project(
    org_id: int,
    payload: schemas.ProjectCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Create a new project within an organization. Requires Member role or above."""
    membership = await require_org_membership(org_id, current_user, db)
    check_role_min(membership, "Member")

    org = await crud.get_organization_async(db, org_id=org_id)
    if not org:
        raise ResourceNotFoundException("Organization not found")

    # Generate slug if omitted
    slug = payload.slug or slugify(payload.name)
    if not slug:
        slug = f"project-{secrets_token()[:6]}"

    # Validate slug uniqueness
    is_available = await crud.validate_project_slug_async(db, organization_id=org_id, slug=slug)
    if not is_available:
        raise ConflictException(f"Project slug '{slug}' is already in use within this organization")

    # Determine project owner: default to current user if not specified
    owner_id = payload.owner_id if payload.owner_id is not None else current_user.id
    if owner_id:
        is_member = await crud.validate_project_owner_async(db, organization_id=org_id, owner_id=owner_id)
        if not is_member:
            raise ValidationErrorException("Project owner must be an active member of this organization")

    project = await crud.create_project_async(
        db=db,
        organization_id=org_id,
        owner_id=owner_id,
        name=payload.name,
        slug=slug,
        description=payload.description,
        status=payload.status or "active",
        color=payload.color or "#3B82F6",
        icon=payload.icon or "folder",
        timezone=payload.timezone or "UTC",
        language=payload.language or "en",
        settings=payload.settings or {},
        actor_id=current_user.id
    )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_audit_event_async(
        db=db,
        user_id=current_user.id,
        organization_id=org_id,
        action="project.created",
        target_resource=f"project:{project.id}",
        ip_address=client_ip,
        user_agent=user_agent,
        details={"name": project.name, "slug": project.slug, "status": project.status}
    )

    return project


@router.get("/orgs/{org_id}/projects", response_model=schemas.ProjectPaginated)
async def list_org_projects(
    org_id: int,
    search: Optional[str] = Query(None, description="Search query across project name, slug, and description"),
    status: Optional[str] = Query(None, description="Filter by status (active, paused, archived, draft)"),
    archived: Optional[bool] = Query(False, description="Filter archived projects (default false)"),
    owner_id: Optional[int] = Query(None, description="Filter by owner user ID"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field (created_at, name, updated_at, status)"),
    order: str = Query("desc", description="Sort order (asc or desc)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """List and search projects in an organization. Requires Viewer role or above."""
    await require_org_membership(org_id, current_user, db)

    skip = (page - 1) * size
    projects = await crud.get_org_projects_async(
        db=db,
        organization_id=org_id,
        skip=skip,
        limit=size,
        search=search,
        status=status,
        archived=archived,
        owner_id=owner_id,
        sort_by=sort_by,
        order=order
    )

    total = await crud.count_org_projects_async(
        db=db,
        organization_id=org_id,
        search=search,
        status=status,
        archived=archived,
        owner_id=owner_id
    )

    total_pages = (total + size - 1) // size if total > 0 else 1

    return schemas.ProjectPaginated(
        items=projects,
        total=total,
        page=page,
        size=size,
        total_pages=total_pages
    )


@router.get("/orgs/{org_id}/projects/validate-slug", response_model=schemas.ProjectSlugValidationOut)
async def validate_project_slug(
    org_id: int,
    slug: str = Query(..., min_length=1, max_length=255, description="Slug to check for availability"),
    project_id: Optional[int] = Query(None, description="Optional project ID to exclude when updating"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Validate slug availability within an organization."""
    await require_org_membership(org_id, current_user, db)

    clean_slug = slugify(slug)
    if not clean_slug:
        return schemas.ProjectSlugValidationOut(
            slug=slug,
            available=False,
            message="Slug cannot be empty"
        )

    is_available = await crud.validate_project_slug_async(
        db=db,
        organization_id=org_id,
        slug=clean_slug,
        exclude_project_id=project_id
    )

    return schemas.ProjectSlugValidationOut(
        slug=clean_slug,
        available=is_available,
        message="Slug is available" if is_available else f"Slug '{clean_slug}' is already in use"
    )


@router.get("/orgs/{org_id}/projects/{project_id_or_slug}", response_model=schemas.ProjectOut)
async def get_project(
    org_id: int,
    project_id_or_slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Retrieve details of a single project by ID or slug."""
    await require_org_membership(org_id, current_user, db)
    project = await get_project_by_id_or_slug(db, org_id=org_id, project_identifier=project_id_or_slug)
    return project


@router.patch("/orgs/{org_id}/projects/{project_id_or_slug}", response_model=schemas.ProjectOut)
async def update_project(
    org_id: int,
    project_id_or_slug: str,
    payload: schemas.ProjectUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Update project metadata. Requires Member role if project owner, or Manager role otherwise."""
    membership = await require_org_membership(org_id, current_user, db)
    project = await get_project_by_id_or_slug(db, org_id=org_id, project_identifier=project_id_or_slug)

    # Permission check: project owner with Member role, or Manager+
    is_owner = (project.owner_id == current_user.id)
    is_manager_or_higher = crud.check_role_permission(membership.role, "Manager")

    if not (is_owner or is_manager_or_higher):
        raise ForbiddenException("You must be the project owner or have at least Manager role to update this project")

    # Validate slug uniqueness if updated
    if payload.slug is not None and payload.slug != project.slug:
        is_available = await crud.validate_project_slug_async(
            db=db,
            organization_id=org_id,
            slug=payload.slug,
            exclude_project_id=project.id
        )
        if not is_available:
            raise ConflictException(f"Project slug '{payload.slug}' is already in use")

    # Validate new owner if updated
    if payload.owner_id is not None and payload.owner_id != project.owner_id:
        if not is_manager_or_higher:
            raise ForbiddenException("Only Managers, Admins, or Owners can reassign project ownership")
        is_member = await crud.validate_project_owner_async(db, organization_id=org_id, owner_id=payload.owner_id)
        if not is_member:
            raise ValidationErrorException("Assigned owner must be an active member of this organization")

    updated_project = await crud.update_project_async(
        db=db,
        project=project,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        status=payload.status,
        color=payload.color,
        icon=payload.icon,
        timezone=payload.timezone,
        language=payload.language,
        settings=payload.settings,
        owner_id=payload.owner_id,
        actor_id=current_user.id
    )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_audit_event_async(
        db=db,
        user_id=current_user.id,
        organization_id=org_id,
        action="project.updated",
        target_resource=f"project:{project.id}",
        ip_address=client_ip,
        user_agent=user_agent,
        details={"name": project.name, "slug": project.slug}
    )

    return updated_project


@router.delete("/orgs/{org_id}/projects/{project_id_or_slug}")
async def delete_project(
    org_id: int,
    project_id_or_slug: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Delete a project permanently. Requires Admin role or above."""
    membership = await require_org_membership(org_id, current_user, db)
    check_role_min(membership, "Admin")

    project = await get_project_by_id_or_slug(db, org_id=org_id, project_identifier=project_id_or_slug)
    project_id = project.id
    project_name = project.name
    project_slug = project.slug

    await crud.delete_project_async(db=db, project=project, actor_id=current_user.id)

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_audit_event_async(
        db=db,
        user_id=current_user.id,
        organization_id=org_id,
        action="project.deleted",
        target_resource=f"project:{project_id}",
        ip_address=client_ip,
        user_agent=user_agent,
        details={"name": project_name, "slug": project_slug}
    )

    return {"message": "Project deleted successfully", "id": project_id}


@router.post("/orgs/{org_id}/projects/{project_id_or_slug}/archive", response_model=schemas.ProjectOut)
async def archive_project(
    org_id: int,
    project_id_or_slug: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Archive a project. Requires Manager role or above."""
    membership = await require_org_membership(org_id, current_user, db)
    check_role_min(membership, "Manager")

    project = await get_project_by_id_or_slug(db, org_id=org_id, project_identifier=project_id_or_slug)
    archived_project = await crud.archive_project_async(db=db, project=project, actor_id=current_user.id)

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_audit_event_async(
        db=db,
        user_id=current_user.id,
        organization_id=org_id,
        action="project.archived",
        target_resource=f"project:{project.id}",
        ip_address=client_ip,
        user_agent=user_agent,
        details={"name": project.name, "slug": project.slug}
    )

    return archived_project


@router.post("/orgs/{org_id}/projects/{project_id_or_slug}/restore", response_model=schemas.ProjectOut)
async def restore_project(
    org_id: int,
    project_id_or_slug: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Restore an archived project to active status. Requires Manager role or above."""
    membership = await require_org_membership(org_id, current_user, db)
    check_role_min(membership, "Manager")

    project = await get_project_by_id_or_slug(db, org_id=org_id, project_identifier=project_id_or_slug)
    restored_project = await crud.restore_project_async(db=db, project=project, actor_id=current_user.id)

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_audit_event_async(
        db=db,
        user_id=current_user.id,
        organization_id=org_id,
        action="project.restored",
        target_resource=f"project:{project.id}",
        ip_address=client_ip,
        user_agent=user_agent,
        details={"name": project.name, "slug": project.slug}
    )

    return restored_project


@router.get("/orgs/{org_id}/projects/{project_id_or_slug}/settings")
async def get_project_settings(
    org_id: int,
    project_id_or_slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get project configuration settings dictionary."""
    await require_org_membership(org_id, current_user, db)
    project = await get_project_by_id_or_slug(db, org_id=org_id, project_identifier=project_id_or_slug)
    return {"project_id": project.id, "settings": project.settings or {}}


@router.put("/orgs/{org_id}/projects/{project_id_or_slug}/settings", response_model=schemas.ProjectOut)
async def update_project_settings(
    org_id: int,
    project_id_or_slug: str,
    payload: schemas.ProjectSettingsUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Update custom JSON settings for a project. Requires Project Owner or Manager role."""
    membership = await require_org_membership(org_id, current_user, db)
    project = await get_project_by_id_or_slug(db, org_id=org_id, project_identifier=project_id_or_slug)

    is_owner = (project.owner_id == current_user.id)
    is_manager = crud.check_role_permission(membership.role, "Manager")
    if not (is_owner or is_manager):
        raise ForbiddenException("Requires Project Owner or Manager role to update settings")

    updated_project = await crud.update_project_settings_async(
        db=db,
        project=project,
        settings=payload.settings,
        actor_id=current_user.id
    )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_audit_event_async(
        db=db,
        user_id=current_user.id,
        organization_id=org_id,
        action="project.settings_updated",
        target_resource=f"project:{project.id}",
        ip_address=client_ip,
        user_agent=user_agent,
        details={"keys": list(payload.settings.keys())}
    )

    return updated_project


@router.get("/orgs/{org_id}/projects/{project_id_or_slug}/stats", response_model=schemas.ProjectStatsOut)
async def get_project_stats(
    org_id: int,
    project_id_or_slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Retrieve operational statistics and health indicators for a project."""
    await require_org_membership(org_id, current_user, db)
    project = await get_project_by_id_or_slug(db, org_id=org_id, project_identifier=project_id_or_slug)
    stats = await crud.get_project_stats_async(db=db, project=project)
    return schemas.ProjectStatsOut(**stats)


@router.get("/orgs/{org_id}/projects/{project_id_or_slug}/activity")
async def get_project_activity(
    org_id: int,
    project_id_or_slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Retrieve audit activity history for a project."""
    await require_org_membership(org_id, current_user, db)
    project = await get_project_by_id_or_slug(db, org_id=org_id, project_identifier=project_id_or_slug)
    events = await crud.get_org_audit_events_async(db=db, org_id=org_id, limit=50)

    # Filter events relevant to this project
    project_events = [
        e for e in events
        if e.details and (
            e.details.get("project_id") == project.id or
            e.action.startswith("project.")
        )
    ]
    return project_events


# --- DIRECT SHORTCUT PROJECT ROUTES (GLOBAL /projects/{id}) ---

@router.get("/projects/{project_id}", response_model=schemas.ProjectOut)
async def get_project_direct(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Direct lookup for a project by ID with tenant security check."""
    project = await crud.get_project_async(db, project_id=project_id)
    if not project:
        raise ResourceNotFoundException("Project not found")

    await require_org_membership(project.organization_id, current_user, db)
    return project


@router.patch("/projects/{project_id}", response_model=schemas.ProjectOut)
async def update_project_direct(
    project_id: int,
    payload: schemas.ProjectUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Direct update for a project by ID."""
    project = await crud.get_project_async(db, project_id=project_id)
    if not project:
        raise ResourceNotFoundException("Project not found")

    membership = await require_org_membership(project.organization_id, current_user, db)
    is_owner = (project.owner_id == current_user.id)
    is_manager_or_higher = crud.check_role_permission(membership.role, "Manager")

    if not (is_owner or is_manager_or_higher):
        raise ForbiddenException("You must be the project owner or have at least Manager role to update this project")

    if payload.slug is not None and payload.slug != project.slug:
        is_available = await crud.validate_project_slug_async(
            db=db,
            organization_id=project.organization_id,
            slug=payload.slug,
            exclude_project_id=project.id
        )
        if not is_available:
            raise ConflictException(f"Project slug '{payload.slug}' is already in use")

    updated = await crud.update_project_async(
        db=db,
        project=project,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        status=payload.status,
        color=payload.color,
        icon=payload.icon,
        timezone=payload.timezone,
        language=payload.language,
        settings=payload.settings,
        owner_id=payload.owner_id,
        actor_id=current_user.id
    )
    return updated


@router.delete("/projects/{project_id}")
async def delete_project_direct(
    project_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Direct delete for a project by ID."""
    project = await crud.get_project_async(db, project_id=project_id)
    if not project:
        raise ResourceNotFoundException("Project not found")

    membership = await require_org_membership(project.organization_id, current_user, db)
    check_role_min(membership, "Admin")

    await crud.delete_project_async(db=db, project=project, actor_id=current_user.id)
    return {"message": "Project deleted successfully", "id": project_id}


def secrets_token() -> str:
    import secrets
    return secrets.token_hex(4)
