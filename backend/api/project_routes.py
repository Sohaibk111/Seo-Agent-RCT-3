from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_async_db
from backend.database import crud, schemas
from backend.auth.dependencies import get_current_user
from backend.database.models import User, Membership, Project
from backend.exceptions import (
    ForbiddenException,
    ResourceNotFoundException,
    ConflictException,
    ValidationErrorException
)
from backend.api.org_routes import require_membership, check_role_min

router = APIRouter(prefix="/orgs", tags=["Project Management"])


async def get_project_with_auth_check(
    org_id: int,
    project_id_or_slug: str,
    current_user: User,
    db: AsyncSession,
    required_role: str = "Viewer"
) -> tuple[Project, Membership]:
    membership = await require_membership(org_id, current_user, db)
    check_role_min(membership, required_role)

    project = await crud.get_project_by_id_or_slug_async(db, org_id, project_id_or_slug)
    if not project:
        raise ResourceNotFoundException("Project not found in this organization")

    return project, membership


# --- PROJECT ENDPOINTS ---

@router.post("/{org_id}/projects", response_model=schemas.ProjectOut, status_code=201)
async def create_project(
    org_id: int,
    project_in: schemas.ProjectCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    membership = await require_membership(org_id, current_user, db)
    check_role_min(membership, "Member")

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    project = await crud.create_project_async(
        db,
        organization_id=org_id,
        owner_id=current_user.id,
        name=project_in.name,
        slug=project_in.slug,
        description=project_in.description,
        status=project_in.status or "active",
        color=project_in.color,
        icon=project_in.icon,
        timezone=project_in.timezone or "UTC",
        language=project_in.language or "en",
        settings=project_in.settings or {},
        ip_address=ip_address,
        user_agent=user_agent
    )
    return project


@router.get("/{org_id}/projects", response_model=List[schemas.ProjectOut])
async def list_organization_projects(
    org_id: int,
    search: Optional[str] = Query(None, description="Search by name, slug, or description"),
    status: Optional[str] = Query(None, description="Filter by status (active, draft, paused, archived, completed)"),
    archived: Optional[bool] = Query(None, description="Filter by archived flag"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    membership = await require_membership(org_id, current_user, db)
    check_role_min(membership, "Viewer")

    projects, _ = await crud.get_org_projects_async(
        db,
        organization_id=org_id,
        search=search,
        status=status,
        archived=archived,
        skip=skip,
        limit=limit
    )
    return projects


@router.get("/{org_id}/projects/{project_id_or_slug}", response_model=schemas.ProjectOut)
async def get_project(
    org_id: int,
    project_id_or_slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    project, _ = await get_project_with_auth_check(org_id, project_id_or_slug, current_user, db, "Viewer")
    return project


@router.put("/{org_id}/projects/{project_id_or_slug}", response_model=schemas.ProjectOut)
async def update_project(
    org_id: int,
    project_id_or_slug: str,
    project_in: schemas.ProjectUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    project, _ = await get_project_with_auth_check(org_id, project_id_or_slug, current_user, db, "Member")

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    updated_project = await crud.update_project_async(
        db,
        project=project,
        name=project_in.name,
        slug=project_in.slug,
        description=project_in.description,
        status=project_in.status,
        color=project_in.color,
        icon=project_in.icon,
        timezone=project_in.timezone,
        language=project_in.language,
        settings=project_in.settings,
        actor_id=current_user.id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    return updated_project


@router.delete("/{org_id}/projects/{project_id_or_slug}")
async def delete_project(
    org_id: int,
    project_id_or_slug: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    project, _ = await get_project_with_auth_check(org_id, project_id_or_slug, current_user, db, "Admin")

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    project_id = project.id
    await crud.delete_project_async(
        db,
        project=project,
        actor_id=current_user.id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    return {"message": "Project deleted successfully", "id": project_id}


@router.post("/{org_id}/projects/{project_id_or_slug}/archive", response_model=schemas.ProjectOut)
async def archive_project(
    org_id: int,
    project_id_or_slug: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    project, _ = await get_project_with_auth_check(org_id, project_id_or_slug, current_user, db, "Member")

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    archived_project = await crud.archive_project_async(
        db,
        project=project,
        actor_id=current_user.id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    return archived_project


@router.post("/{org_id}/projects/{project_id_or_slug}/restore", response_model=schemas.ProjectOut)
async def restore_project(
    org_id: int,
    project_id_or_slug: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    project, _ = await get_project_with_auth_check(org_id, project_id_or_slug, current_user, db, "Member")

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    restored_project = await crud.restore_project_async(
        db,
        project=project,
        actor_id=current_user.id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    return restored_project


@router.get("/{org_id}/projects/{project_id_or_slug}/settings")
async def get_project_settings(
    org_id: int,
    project_id_or_slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    project, _ = await get_project_with_auth_check(org_id, project_id_or_slug, current_user, db, "Viewer")
    return {"project_id": project.id, "settings": project.settings or {}}


@router.put("/{org_id}/projects/{project_id_or_slug}/settings", response_model=schemas.ProjectOut)
async def update_project_settings(
    org_id: int,
    project_id_or_slug: str,
    settings_in: schemas.ProjectSettingsUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    project, _ = await get_project_with_auth_check(org_id, project_id_or_slug, current_user, db, "Member")

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    updated_project = await crud.update_project_async(
        db,
        project=project,
        settings=settings_in.settings,
        actor_id=current_user.id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    return updated_project


@router.get("/{org_id}/projects/{project_id_or_slug}/metadata", response_model=schemas.ProjectMetadataOut)
async def get_project_metadata(
    org_id: int,
    project_id_or_slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    project, _ = await get_project_with_auth_check(org_id, project_id_or_slug, current_user, db, "Viewer")
    settings_dict = project.settings or {}
    return schemas.ProjectMetadataOut(
        project_id=project.id,
        organization_id=project.organization_id,
        owner_id=project.owner_id,
        name=project.name,
        slug=project.slug,
        status=project.status,
        timezone=project.timezone,
        language=project.language,
        archived=project.archived,
        color=project.color,
        icon=project.icon,
        settings_count=len(settings_dict),
        created_at=project.created_at,
        updated_at=project.updated_at
    )


@router.get("/{org_id}/projects/{project_id_or_slug}/stats", response_model=schemas.ProjectStatsOut)
async def get_project_stats(
    org_id: int,
    project_id_or_slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    project, _ = await get_project_with_auth_check(org_id, project_id_or_slug, current_user, db, "Viewer")
    activities = await crud.get_project_activity_async(db, project.id, limit=500)
    settings_dict = project.settings or {}
    created_dt = project.created_at or datetime.utcnow()
    days_old = (datetime.utcnow() - created_dt).days
    return schemas.ProjectStatsOut(
        project_id=project.id,
        organization_id=project.organization_id,
        name=project.name,
        slug=project.slug,
        status=project.status,
        archived=project.archived,
        created_days_ago=max(0, days_old),
        settings_keys_count=len(settings_dict),
        total_activities=len(activities)
    )


@router.get("/{org_id}/projects/{project_id_or_slug}/activity", response_model=List[schemas.ProjectActivityOut])
async def get_project_activity(
    org_id: int,
    project_id_or_slug: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    project, _ = await get_project_with_auth_check(org_id, project_id_or_slug, current_user, db, "Viewer")
    logs = await crud.get_project_activity_async(db, project.id, limit=limit)
    out = []
    for log in logs:
        out.append(
            schemas.ProjectActivityOut(
                id=log.id,
                action=log.action,
                actor_id=log.user_id,
                details=log.details,
                created_at=log.created_at
            )
        )
    return out
