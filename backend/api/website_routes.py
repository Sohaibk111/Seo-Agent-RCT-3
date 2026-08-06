from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Request, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.database.database import get_async_db
from backend.database import crud, schemas
from backend.auth.dependencies import get_current_user
from backend.database.models import User, Membership, Project, Website, AuditResult, Lead
from backend.exceptions import (
    ForbiddenException,
    ResourceNotFoundException,
    ConflictException,
    ValidationErrorException
)
from backend.api.org_routes import require_membership, check_role_min
from backend.api.project_routes import get_project_with_auth_check

router = APIRouter(prefix="/orgs", tags=["Website Management"])


async def get_website_with_auth_check(
    org_id: int,
    project_id_or_slug: str,
    website_id_or_domain: str,
    current_user: User,
    db: AsyncSession,
    required_role: str = "Viewer"
) -> tuple[Website, Project, Membership]:
    project, membership = await get_project_with_auth_check(
        org_id, project_id_or_slug, current_user, db, required_role
    )
    website = await crud.get_project_website_by_id_or_domain_async(
        db, project.id, website_id_or_domain
    )
    if not website or website.organization_id != org_id:
        raise ResourceNotFoundException("Website not found in this project")

    return website, project, membership


# --- WEBSITE ENDPOINTS ---

@router.post("/{org_id}/projects/{project_id_or_slug}/websites", response_model=schemas.WebsiteOut, status_code=status.HTTP_201_CREATED)
async def create_website(
    org_id: int,
    project_id_or_slug: str,
    website_in: schemas.WebsiteCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    project, membership = await get_project_with_auth_check(
        org_id, project_id_or_slug, current_user, db, "Member"
    )

    if not crud.is_valid_domain(website_in.domain):
        raise ValidationErrorException("Invalid domain format")

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    website = await crud.create_project_website_async(
        db=db,
        project_id=project.id,
        organization_id=org_id,
        owner_id=current_user.id,
        domain=website_in.domain,
        protocol=website_in.protocol or "https",
        status=website_in.status or "active",
        verification_status=website_in.verification_status or "unverified",
        favicon=website_in.favicon,
        country=website_in.country,
        language=website_in.language or "en",
        timezone=website_in.timezone or "UTC",
        settings=website_in.settings or {},
        ip_address=ip_address,
        user_agent=user_agent
    )
    return website


@router.get("/{org_id}/projects/{project_id_or_slug}/websites", response_model=List[schemas.WebsiteOut])
async def list_websites(
    org_id: int,
    project_id_or_slug: str,
    search: Optional[str] = Query(None, description="Search domain or company name"),
    status: Optional[str] = Query(None, description="Filter by status"),
    archived: Optional[bool] = Query(None, description="Filter by archived state"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    project, _ = await get_project_with_auth_check(
        org_id, project_id_or_slug, current_user, db, "Viewer"
    )

    websites, _ = await crud.get_project_websites_async(
        db=db,
        project_id=project.id,
        search=search,
        status=status,
        archived=archived,
        skip=skip,
        limit=limit
    )
    return websites


@router.get("/{org_id}/projects/{project_id_or_slug}/websites/{website_id_or_domain}", response_model=schemas.WebsiteOut)
async def get_website(
    org_id: int,
    project_id_or_slug: str,
    website_id_or_domain: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    website, _, _ = await get_website_with_auth_check(
        org_id, project_id_or_slug, website_id_or_domain, current_user, db, "Viewer"
    )
    return website


@router.put("/{org_id}/projects/{project_id_or_slug}/websites/{website_id_or_domain}", response_model=schemas.WebsiteOut)
async def update_website(
    org_id: int,
    project_id_or_slug: str,
    website_id_or_domain: str,
    website_in: schemas.WebsiteUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    website, _, _ = await get_website_with_auth_check(
        org_id, project_id_or_slug, website_id_or_domain, current_user, db, "Member"
    )

    if website_in.domain is not None and not crud.is_valid_domain(website_in.domain):
        raise ValidationErrorException("Invalid domain format")

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    updated_website = await crud.update_project_website_async(
        db=db,
        website=website,
        domain=website_in.domain,
        protocol=website_in.protocol,
        status=website_in.status,
        verification_status=website_in.verification_status,
        favicon=website_in.favicon,
        country=website_in.country,
        language=website_in.language,
        timezone=website_in.timezone,
        settings=website_in.settings,
        actor_id=current_user.id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    return updated_website


@router.delete("/{org_id}/projects/{project_id_or_slug}/websites/{website_id_or_domain}")
async def delete_website(
    org_id: int,
    project_id_or_slug: str,
    website_id_or_domain: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    website, _, _ = await get_website_with_auth_check(
        org_id, project_id_or_slug, website_id_or_domain, current_user, db, "Admin"
    )

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    website_id = website.id
    await crud.delete_project_website_async(
        db=db,
        website=website,
        actor_id=current_user.id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    return {"message": "Website deleted successfully", "id": website_id}


@router.post("/{org_id}/projects/{project_id_or_slug}/websites/{website_id_or_domain}/archive", response_model=schemas.WebsiteOut)
async def archive_website(
    org_id: int,
    project_id_or_slug: str,
    website_id_or_domain: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    website, _, _ = await get_website_with_auth_check(
        org_id, project_id_or_slug, website_id_or_domain, current_user, db, "Member"
    )

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    archived_website = await crud.archive_project_website_async(
        db=db,
        website=website,
        actor_id=current_user.id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    return archived_website


@router.post("/{org_id}/projects/{project_id_or_slug}/websites/{website_id_or_domain}/restore", response_model=schemas.WebsiteOut)
async def restore_website(
    org_id: int,
    project_id_or_slug: str,
    website_id_or_domain: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    website, _, _ = await get_website_with_auth_check(
        org_id, project_id_or_slug, website_id_or_domain, current_user, db, "Member"
    )

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    restored_website = await crud.restore_project_website_async(
        db=db,
        website=website,
        actor_id=current_user.id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    return restored_website


@router.get("/{org_id}/projects/{project_id_or_slug}/websites/{website_id_or_domain}/settings")
async def get_website_settings(
    org_id: int,
    project_id_or_slug: str,
    website_id_or_domain: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    website, _, _ = await get_website_with_auth_check(
        org_id, project_id_or_slug, website_id_or_domain, current_user, db, "Viewer"
    )
    return {"website_id": website.id, "settings": website.settings or {}}


@router.put("/{org_id}/projects/{project_id_or_slug}/websites/{website_id_or_domain}/settings", response_model=schemas.WebsiteOut)
async def update_website_settings(
    org_id: int,
    project_id_or_slug: str,
    website_id_or_domain: str,
    settings_in: schemas.WebsiteSettingsUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    website, _, _ = await get_website_with_auth_check(
        org_id, project_id_or_slug, website_id_or_domain, current_user, db, "Member"
    )

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    updated_website = await crud.update_project_website_async(
        db=db,
        website=website,
        settings=settings_in.settings,
        actor_id=current_user.id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    return updated_website


@router.get("/{org_id}/projects/{project_id_or_slug}/websites/{website_id_or_domain}/metadata", response_model=schemas.WebsiteMetadataOut)
async def get_website_metadata(
    org_id: int,
    project_id_or_slug: str,
    website_id_or_domain: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    website, _, _ = await get_website_with_auth_check(
        org_id, project_id_or_slug, website_id_or_domain, current_user, db, "Viewer"
    )

    norm_domain = website.normalized_domain or crud.normalize_domain(website.domain)
    settings_dict = website.settings or {}

    return schemas.WebsiteMetadataOut(
        website_id=website.id,
        project_id=website.project_id,
        organization_id=website.organization_id,
        owner_id=website.owner_id,
        domain=website.domain,
        normalized_domain=norm_domain,
        protocol=website.protocol or "https",
        status=website.status or "active",
        verification_status=website.verification_status or "unverified",
        favicon=website.favicon,
        country=website.country,
        language=website.language or "en",
        timezone=website.timezone or "UTC",
        archived=website.archived,
        settings_count=len(settings_dict),
        last_scan_at=website.last_scan_at,
        created_at=website.created_at,
        updated_at=website.updated_at
    )


@router.get("/{org_id}/projects/{project_id_or_slug}/websites/{website_id_or_domain}/stats", response_model=schemas.WebsiteStatsOut)
async def get_website_stats(
    org_id: int,
    project_id_or_slug: str,
    website_id_or_domain: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    website, _, _ = await get_website_with_auth_check(
        org_id, project_id_or_slug, website_id_or_domain, current_user, db, "Viewer"
    )

    created_days_ago = (datetime.utcnow() - website.created_at).days if website.created_at else 0
    settings_dict = website.settings or {}

    # Query counts for audits and leads
    audits_res = await db.execute(
        select(func.count(AuditResult.id)).where(AuditResult.website_id == website.id)
    )
    audits_count = audits_res.scalar_one()

    leads_res = await db.execute(
        select(func.count(Lead.id)).where(Lead.website_id == website.id)
    )
    leads_count = leads_res.scalar_one()

    return schemas.WebsiteStatsOut(
        website_id=website.id,
        project_id=website.project_id,
        organization_id=website.organization_id,
        domain=website.domain,
        status=website.status or "active",
        archived=website.archived,
        created_days_ago=created_days_ago,
        settings_keys_count=len(settings_dict),
        total_audits=audits_count,
        total_leads=leads_count
    )
