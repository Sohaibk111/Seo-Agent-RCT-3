from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Request, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from backend.database.database import get_async_db
from backend.database import crud, schemas
from backend.auth.dependencies import get_current_user
from backend.database.models import User, Membership, Project, Website, CrawlJob, CrawlPage, CrawlIssue
from backend.exceptions import (
    ForbiddenException,
    ResourceNotFoundException,
    ConflictException,
    ValidationErrorException
)
from backend.api.org_routes import require_membership, check_role_min

router = APIRouter(tags=["Crawl Jobs"])


async def get_website_and_project_auth(
    project_id: int,
    website_id: int,
    current_user: User,
    db: AsyncSession,
    required_role: str = "Viewer"
) -> tuple[Website, Project, Membership]:
    stmt = select(Website).where(Website.id == website_id)
    res = await db.execute(stmt)
    website = res.scalars().first()
    if not website or website.project_id != project_id:
        raise ResourceNotFoundException("Website not found in specified project")

    membership = await require_membership(website.organization_id, current_user, db)
    check_role_min(membership, required_role)

    stmt_p = select(Project).where(Project.id == project_id)
    res_p = await db.execute(stmt_p)
    project = res_p.scalars().first()
    if not project:
        raise ResourceNotFoundException("Project not found")

    return website, project, membership


async def get_crawl_auth(
    crawl_id: int,
    current_user: User,
    db: AsyncSession,
    required_role: str = "Viewer"
) -> tuple[CrawlJob, Website, Membership]:
    crawl_job = await crud.get_crawl_job_async(db, crawl_id)
    if not crawl_job:
        raise ResourceNotFoundException("Crawl job not found")

    website = crawl_job.website
    if not website:
        stmt = select(Website).where(Website.id == crawl_job.website_id)
        res = await db.execute(stmt)
        website = res.scalars().first()
        if not website:
            raise ResourceNotFoundException("Associated website not found")

    membership = await require_membership(website.organization_id, current_user, db)
    check_role_min(membership, required_role)

    return crawl_job, website, membership


# --- CRAWL JOB ENDPOINTS ---

@router.post("/projects/{project_id}/websites/{website_id}/crawls", response_model=schemas.CrawlJobOut, status_code=status.HTTP_201_CREATED)
async def create_crawl_job(
    project_id: int,
    website_id: int,
    crawl_in: Optional[schemas.CrawlJobCreate] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    website, project, membership = await get_website_and_project_auth(
        project_id, website_id, current_user, db, required_role="Member"
    )

    # Check if active crawl exists
    active_crawl = await crud.get_active_crawl_job_for_website_async(db, website.id)
    if active_crawl:
        raise ConflictException(f"An active crawl job (id={active_crawl.id}, status='{active_crawl.status}') already exists for this website")

    triggered_by = crawl_in.triggered_by if crawl_in and crawl_in.triggered_by else "manual"
    crawler_version = crawl_in.crawler_version if crawl_in and crawl_in.crawler_version else "1.0.0"

    crawl_job = await crud.create_crawl_job_async(
        db=db,
        website_id=website.id,
        triggered_by=triggered_by,
        crawler_version=crawler_version
    )
    return crawl_job


@router.get("/projects/{project_id}/websites/{website_id}/crawls")
async def list_crawl_jobs(
    project_id: int,
    website_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    website, project, membership = await get_website_and_project_auth(
        project_id, website_id, current_user, db, required_role="Viewer"
    )

    jobs, total = await crud.list_crawl_jobs_async(db, website.id, skip=skip, limit=limit)
    out_items = []
    for j in jobs:
        out = schemas.CrawlJobOut.model_validate(j)
        stats = await crud.calculate_crawl_stats_async(db, j.id)
        out.stats = schemas.CrawlStatsOut(**stats)
        out_items.append(out)

    return {"items": out_items, "total": total}


@router.get("/crawls/{crawl_id}", response_model=schemas.CrawlJobOut)
async def get_crawl_job(
    crawl_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    crawl_job, website, membership = await get_crawl_auth(
        crawl_id, current_user, db, required_role="Viewer"
    )
    out = schemas.CrawlJobOut.model_validate(crawl_job)
    stats = await crud.calculate_crawl_stats_async(db, crawl_job.id)
    out.stats = schemas.CrawlStatsOut(**stats)
    return out


@router.post("/crawls/{crawl_id}/cancel", response_model=schemas.CrawlJobOut)
async def cancel_crawl_job(
    crawl_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    crawl_job, website, membership = await get_crawl_auth(
        crawl_id, current_user, db, required_role="Member"
    )
    updated_job = await crud.cancel_crawl_async(db, crawl_job)
    out = schemas.CrawlJobOut.model_validate(updated_job)
    stats = await crud.calculate_crawl_stats_async(db, updated_job.id)
    out.stats = schemas.CrawlStatsOut(**stats)
    return out


@router.post("/crawls/{crawl_id}/retry", response_model=schemas.CrawlJobOut)
async def retry_crawl_job(
    crawl_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    crawl_job, website, membership = await get_crawl_auth(
        crawl_id, current_user, db, required_role="Member"
    )
    updated_job = await crud.retry_crawl_async(db, crawl_job)
    out = schemas.CrawlJobOut.model_validate(updated_job)
    stats = await crud.calculate_crawl_stats_async(db, updated_job.id)
    out.stats = schemas.CrawlStatsOut(**stats)
    return out


@router.get("/crawls/{crawl_id}/pages")
async def list_crawl_pages(
    crawl_id: int,
    status_code: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    crawl_job, website, membership = await get_crawl_auth(
        crawl_id, current_user, db, required_role="Viewer"
    )
    stmt = select(CrawlPage).where(CrawlPage.crawl_job_id == crawl_id)
    count_stmt = select(func.count(CrawlPage.id)).where(CrawlPage.crawl_job_id == crawl_id)

    if status_code is not None:
        stmt = stmt.where(CrawlPage.status_code == status_code)
        count_stmt = count_stmt.where(CrawlPage.status_code == status_code)

    if search:
        pat = f"%{search}%"
        cond = or_(CrawlPage.url.ilike(pat), CrawlPage.title.ilike(pat))
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    stmt = stmt.order_by(CrawlPage.id.asc()).offset(skip).limit(limit)

    tot_res = await db.execute(count_stmt)
    total = tot_res.scalar_one()

    res = await db.execute(stmt)
    pages = list(res.scalars().all())

    items = [schemas.CrawlPageOut.model_validate(p) for p in pages]
    return {"items": items, "total": total}


@router.post("/crawls/{crawl_id}/pages", response_model=schemas.CrawlPageOut, status_code=status.HTTP_201_CREATED)
async def add_crawl_page(
    crawl_id: int,
    page_in: schemas.CrawlPageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    crawl_job, website, membership = await get_crawl_auth(
        crawl_id, current_user, db, required_role="Member"
    )
    page = await crud.create_crawl_page_async(
        db, crawl_id, page_in.model_dump()
    )
    return schemas.CrawlPageOut.model_validate(page)


@router.get("/crawls/{crawl_id}/issues")
async def list_crawl_issues(
    crawl_id: int,
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    crawl_job, website, membership = await get_crawl_auth(
        crawl_id, current_user, db, required_role="Viewer"
    )
    stmt = select(CrawlIssue).where(CrawlIssue.crawl_job_id == crawl_id)
    count_stmt = select(func.count(CrawlIssue.id)).where(CrawlIssue.crawl_job_id == crawl_id)

    if severity:
        stmt = stmt.where(CrawlIssue.severity == severity)
        count_stmt = count_stmt.where(CrawlIssue.severity == severity)

    if category:
        stmt = stmt.where(CrawlIssue.category == category)
        count_stmt = count_stmt.where(CrawlIssue.category == category)

    stmt = stmt.order_by(CrawlIssue.id.asc()).offset(skip).limit(limit)

    tot_res = await db.execute(count_stmt)
    total = tot_res.scalar_one()

    res = await db.execute(stmt)
    issues = list(res.scalars().all())

    items = [schemas.CrawlIssueOut.model_validate(i) for i in issues]
    return {"items": items, "total": total}


@router.post("/crawls/{crawl_id}/issues", response_model=schemas.CrawlIssueOut, status_code=status.HTTP_201_CREATED)
async def add_crawl_issue(
    crawl_id: int,
    issue_in: schemas.CrawlIssueCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    crawl_job, website, membership = await get_crawl_auth(
        crawl_id, current_user, db, required_role="Member"
    )
    issue = await crud.create_crawl_issue_async(
        db, crawl_id, issue_in.model_dump()
    )
    return schemas.CrawlIssueOut.model_validate(issue)


@router.patch("/crawls/{crawl_id}/progress", response_model=schemas.CrawlJobOut)
async def update_crawl_progress(
    crawl_id: int,
    progress_in: schemas.CrawlProgressUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    crawl_job, website, membership = await get_crawl_auth(
        crawl_id, current_user, db, required_role="Member"
    )
    updated_job = await crud.update_crawl_job_progress_async(
        db,
        crawl_job,
        progress=progress_in.progress,
        status=progress_in.status,
        pages_found=progress_in.pages_found,
        issues_found=progress_in.issues_found,
        duration_seconds=progress_in.duration_seconds,
        error_message=progress_in.error_message
    )
    out = schemas.CrawlJobOut.model_validate(updated_job)
    stats = await crud.calculate_crawl_stats_async(db, updated_job.id)
    out.stats = schemas.CrawlStatsOut(**stats)
    return out
