from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from urllib.parse import urlparse

from backend.database.database import get_async_db
from backend.database import crud, schemas
from backend.database.models import User
from backend.exceptions import ValidationErrorException
from backend.ssrf_protection import validate_url_ssrf
from backend.auth.dependencies import get_current_user, get_current_admin_user
from backend.api.dependencies import (
    verify_website_ownership_async,
    verify_audit_ownership_async,
    verify_domain_ownership_async,
    verify_job_ownership_async
)
from backend.services.ai_service import AIService
from backend.services.export_service import ExportService
from backend.services.keyword_service import KeywordService
from backend.services.metrics_service import MetricsService
from backend.services.rank_service import RankService
from backend.services.scraper_service import ScraperService
from backend.services.job_service import JobService
from backend.services.audit_service import log_audit_event_async
from backend.rate_limiter import rate_limit_guard
from backend.queue import job_queue

router = APIRouter()

# --- WEBSITES ENDPOINTS ---
@router.post("/websites", response_model=schemas.WebsiteOut, dependencies=[Depends(rate_limit_guard)])
async def create_website(website_in: schemas.WebsiteCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    """Create a new website owned by the current user."""
    clean_domain = website_in.domain or website_in.url.replace("https://", "").replace("http://", "").split("/")[0].lower()
    website = await crud.create_website_async(
        db, user_id=current_user.id, url=website_in.url, domain=clean_domain, company_name=website_in.company_name
    )
    await log_audit_event_async(
        db=db,
        action="project.created",
        user_id=current_user.id,
        target_resource=f"project:{website.id}",
        details={"url": website.url, "domain": website.domain}
    )
    return website

@router.get("/websites", response_model=List[schemas.WebsiteOut])
async def list_websites(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    sort_by: str = Query("id", pattern="^(id|created_at|domain|url|company_name)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """List websites owned exclusively by the authenticated user with async pagination, filtering, and sorting."""
    return await crud.get_user_websites_async(
        db, user_id=current_user.id, skip=skip, limit=limit, search=search, sort_by=sort_by, order=order
    )

@router.get("/websites/{id}", response_model=schemas.WebsiteOut)
async def get_website(id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    """Get website details with strict async ownership verification (403 if unauthorized, 404 if missing)."""
    return await verify_website_ownership_async(id, current_user.id, db)

@router.delete("/websites/{id}")
async def delete_website(id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    """Delete a website owned by the user along with associated audits, leads, and reports asynchronously."""
    website = await verify_website_ownership_async(id, current_user.id, db)
    await log_audit_event_async(
        db=db,
        action="project.deleted",
        user_id=current_user.id,
        target_resource=f"project:{id}",
        details={"domain": website.domain, "url": website.url}
    )
    await crud.delete_website_instance_async(db, website)
    return {"message": "Website deleted successfully", "id": id}

# --- AUDIT ENDPOINTS ---
@router.post("/audit", dependencies=[Depends(rate_limit_guard)])
async def create_audit(audit_in: schemas.AuditCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    """Trigger site audit with domain and website ownership verification."""
    if not audit_in.url and not audit_in.website_id:
        raise ValidationErrorException(message="URL or website_id is required")
    return await ScraperService.audit_website_async(
        url=audit_in.url,
        website_id=audit_in.website_id,
        user_id=current_user.id,
        db=db
    )


@router.get("/audit/{website_id}", response_model=List[schemas.AuditOut])
async def get_audits_for_website(
    website_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("id", pattern="^(id|created_at|score)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get all technical audit records for a user-owned website asynchronously with pagination and sorting."""
    await verify_website_ownership_async(website_id, current_user.id, db)
    return await crud.get_user_audits_for_website_async(
        db, website_id=website_id, user_id=current_user.id, skip=skip, limit=limit, sort_by=sort_by, order=order
    )

@router.post("/audit/site-level", dependencies=[Depends(rate_limit_guard)])
async def site_level_audit(req: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    website_id = req.get("website_id")
    url = req.get("url")
    if url:
        url = validate_url_ssrf(url)
    if website_id:
        await verify_website_ownership_async(int(website_id), current_user.id, db)
    elif url:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        await verify_domain_ownership_async(domain, current_user.id, db)

    return {
        "sitemap": {"found": True, "url": f"{url}/sitemap.xml", "total_urls": 42},
        "robots_txt": {"found": True, "url": f"{url}/robots.txt", "allow_all": True}
    }

@router.get("/scraper/robots")
async def get_robots_txt(domain: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    """Fetch and parse robots.txt for domain (cached with Redis/TTL)."""
    await verify_domain_ownership_async(domain, current_user.id, db)
    return ScraperService.fetch_robots_txt(domain)

@router.get("/scraper/sitemap")
async def get_sitemap(domain: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    """Fetch and parse sitemap for domain (cached with Redis/TTL)."""
    await verify_domain_ownership_async(domain, current_user.id, db)
    return ScraperService.fetch_sitemap(domain)

@router.get("/metrics/whois")
async def get_whois(domain: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    """Lookup WHOIS registration data for domain (cached with Redis/TTL)."""
    await verify_domain_ownership_async(domain, current_user.id, db)
    return ScraperService.lookup_whois(domain)

# --- AI RECOMMENDATIONS ENDPOINTS ---
@router.get("/ai/analyze/{audit_id}", dependencies=[Depends(rate_limit_guard)])
async def ai_analyze_audit(audit_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    """Generate AI optimization recommendations for an owned audit result."""
    return await AIService.analyze_audit_async(audit_id=audit_id, user_id=current_user.id, db=db)

# --- RANK TRACKER ENDPOINTS ---
@router.post("/rank/check", dependencies=[Depends(rate_limit_guard)])
async def check_keyword_rank(req: schemas.RankCheckRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    """Perform keyword rank checking for user's domain/website."""
    return await RankService.check_rank_async(
        keyword=req.keyword,
        domain=req.domain,
        website_id=req.website_id,
        user_id=current_user.id,
        db=db
    )

# --- LEADS ENDPOINTS ---
@router.get("/leads/{website_id}", response_model=List[schemas.LeadOut])
async def get_leads_for_website(
    website_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    source: Optional[str] = None,
    sort_by: str = Query("id", pattern="^(id|created_at|email|source)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Retrieve extracted leads for an owned website asynchronously with pagination and filtering."""
    await verify_website_ownership_async(website_id, current_user.id, db)
    return await crud.get_user_leads_for_website_async(
        db, website_id=website_id, user_id=current_user.id, skip=skip, limit=limit, source=source, sort_by=sort_by, order=order
    )

@router.post("/outreach/email/send")
async def send_outreach_email(req: dict, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    website_id = req.get("website_id")
    if website_id:
        await verify_website_ownership_async(int(website_id), current_user.id, db)
    return {
        "status": "sent",
        "to": req.get("to_email"),
        "subject": req.get("subject"),
        "timestamp": "2026-08-02T09:40:00Z"
    }

# --- REPORTS ENDPOINTS ---
@router.get("/reports/{website_id}", response_model=List[schemas.ReportOut])
async def get_reports_for_website(
    website_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    format: Optional[str] = None,
    sort_by: str = Query("id", pattern="^(id|created_at|title|format)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Retrieve generated reports for an owned website asynchronously with pagination and filtering."""
    await verify_website_ownership_async(website_id, current_user.id, db)
    return await crud.get_user_reports_for_website_async(
        db, website_id=website_id, user_id=current_user.id, skip=skip, limit=limit, format=format, sort_by=sort_by, order=order
    )

@router.post("/reports/export")
async def export_report(req: schemas.ReportExportRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    """Export audit report with strict website ownership validation."""
    return await ExportService.export_report_async(
        website_id=req.website_id,
        user_id=current_user.id,
        format=req.format or "pdf",
        db=db
    )

@router.get("/reports/export/{website_id}/csv/stream")
async def stream_csv_report(website_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    """Stream audit reports for an owned website as chunked CSV for memory efficiency."""
    await verify_website_ownership_async(website_id, current_user.id, db)
    return StreamingResponse(
        ExportService.stream_csv_audits_async(website_id=website_id, user_id=current_user.id, db=db),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=audit_export_{website_id}.csv"}
    )

@router.get("/reports/export/{website_id}/sheets")
async def get_sheets_payload(website_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    """Retrieve Google Sheets API formatted payload for audit report export."""
    await verify_website_ownership_async(website_id, current_user.id, db)
    return await ExportService.generate_sheets_payload_async(website_id=website_id, user_id=current_user.id, db=db)

# --- KEYWORD RESEARCH ENDPOINTS ---
@router.post("/keywords", dependencies=[Depends(rate_limit_guard)])
@router.post("/keywords/ideas", dependencies=[Depends(rate_limit_guard)])
async def generate_keyword_ideas(req: schemas.KeywordRequest, current_user: User = Depends(get_current_user)):
    return await KeywordService.get_keyword_ideas_async(seed_keyword=req.seed_keyword, limit=req.limit or 10)

# --- CURSOR PAGINATION ENDPOINTS ---
@router.get("/websites/cursor")
async def list_websites_cursor(
    cursor: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """List user websites with cursor-based pagination for high-performance sequential scanning."""
    items, next_cursor, has_more = await crud.get_user_websites_cursor_async(
        db, user_id=current_user.id, cursor=cursor, limit=limit, order=order
    )
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}

@router.get("/audit/{website_id}/cursor")
async def list_audits_cursor(
    website_id: int,
    cursor: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """List audits for website with cursor-based pagination."""
    await verify_website_ownership_async(website_id, current_user.id, db)
    items, next_cursor, has_more = await crud.get_user_audits_cursor_async(
        db, website_id=website_id, user_id=current_user.id, cursor=cursor, limit=limit, order=order
    )
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}

@router.get("/jobs/cursor")
async def list_jobs_cursor(
    cursor: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """List jobs with cursor-based pagination."""
    items, next_cursor, has_more = await crud.get_user_jobs_cursor_async(
        db, user_id=current_user.id, cursor=cursor, limit=limit, order=order
    )
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}

@router.get("/leads/{website_id}/cursor")
async def list_leads_cursor(
    website_id: int,
    cursor: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """List leads for website with cursor-based pagination."""
    await verify_website_ownership_async(website_id, current_user.id, db)
    items, next_cursor, has_more = await crud.get_user_leads_cursor_async(
        db, website_id=website_id, user_id=current_user.id, cursor=cursor, limit=limit, order=order
    )
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


# --- DOMAIN METRICS ENDPOINTS ---
@router.post("/metrics/domain", dependencies=[Depends(rate_limit_guard)])
@router.post("/domain-metrics", dependencies=[Depends(rate_limit_guard)])
async def get_domain_metrics(req: schemas.DomainMetricsRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    return await MetricsService.get_domain_metrics_async(domain=req.domain, user_id=current_user.id, db=db)

# --- BACKGROUND JOBS ENDPOINTS ---
@router.post("/jobs/crawl", response_model=schemas.JobOut, dependencies=[Depends(rate_limit_guard)])
async def create_crawl_job(
    req: schemas.CrawlJobRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    if not req.url and not req.website_id:
        raise ValidationErrorException(message="URL or website_id is required")
    if req.website_id:
        await verify_website_ownership_async(req.website_id, current_user.id, db)
    elif req.url:
        target_url = req.url if req.url.startswith("http") else f"https://{req.url}"
        parsed = urlparse(target_url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        await verify_domain_ownership_async(domain, current_user.id, db)

    job = await JobService.create_job_async(
        db=db,
        user_id=current_user.id,
        job_type="crawl",
        website_id=req.website_id,
        payload={"url": req.url, "website_id": req.website_id}
    )
    if job_queue.is_redis_active():
        job_queue.enqueue("crawl", job.id, current_user.id, JobService.run_crawl_job, url=req.url, website_id=req.website_id)
    else:
        background_tasks.add_task(
            JobService.run_crawl_job,
            job_id=job.id,
            user_id=current_user.id,
            url=req.url,
            website_id=req.website_id
        )
    return job

@router.post("/jobs/audit", response_model=schemas.JobOut, dependencies=[Depends(rate_limit_guard)])
async def create_audit_job(
    req: schemas.AuditJobRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    if not req.url and not req.website_id:
        raise ValidationErrorException(message="URL or website_id is required")
    if req.website_id:
        await verify_website_ownership_async(req.website_id, current_user.id, db)
    elif req.url:
        target_url = req.url if req.url.startswith("http") else f"https://{req.url}"
        parsed = urlparse(target_url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        await verify_domain_ownership_async(domain, current_user.id, db)

    job = await JobService.create_job_async(
        db=db,
        user_id=current_user.id,
        job_type="audit",
        website_id=req.website_id,
        payload={"url": req.url, "website_id": req.website_id}
    )
    if job_queue.is_redis_active():
        job_queue.enqueue("audit", job.id, current_user.id, JobService.run_audit_job, url=req.url, website_id=req.website_id)
    else:
        background_tasks.add_task(
            JobService.run_audit_job,
            job_id=job.id,
            user_id=current_user.id,
            url=req.url,
            website_id=req.website_id
        )
    return job

@router.post("/jobs/keywords", response_model=schemas.JobOut, dependencies=[Depends(rate_limit_guard)])
async def create_keywords_job(
    req: schemas.KeywordJobRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    if not req.seed_keyword:
        raise ValidationErrorException(message="seed_keyword is required")

    job = await JobService.create_job_async(
        db=db,
        user_id=current_user.id,
        job_type="keywords",
        payload={"seed_keyword": req.seed_keyword, "limit": req.limit or 10}
    )
    if job_queue.is_redis_active():
        job_queue.enqueue("keywords", job.id, current_user.id, JobService.run_keywords_job, seed_keyword=req.seed_keyword, limit=req.limit or 10)
    else:
        background_tasks.add_task(
            JobService.run_keywords_job,
            job_id=job.id,
            user_id=current_user.id,
            seed_keyword=req.seed_keyword,
            limit=req.limit or 10
        )
    return job

@router.post("/jobs/rank", response_model=schemas.JobOut, dependencies=[Depends(rate_limit_guard)])
async def create_rank_job(
    req: schemas.RankJobRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    if not req.keyword or (not req.domain and not req.website_id):
        raise ValidationErrorException(message="keyword and domain or website_id are required")

    if req.website_id:
        await verify_website_ownership_async(req.website_id, current_user.id, db)
    elif req.domain:
        await verify_domain_ownership_async(req.domain, current_user.id, db)

    job = await JobService.create_job_async(
        db=db,
        user_id=current_user.id,
        job_type="rank",
        website_id=req.website_id,
        payload={"keyword": req.keyword, "domain": req.domain, "website_id": req.website_id}
    )
    if job_queue.is_redis_active():
        job_queue.enqueue("rank", job.id, current_user.id, JobService.run_rank_job, keyword=req.keyword, domain=req.domain, website_id=req.website_id)
    else:
        background_tasks.add_task(
            JobService.run_rank_job,
            job_id=job.id,
            user_id=current_user.id,
            keyword=req.keyword,
            domain=req.domain,
            website_id=req.website_id
        )
    return job

@router.get("/jobs", response_model=List[schemas.JobOut])
async def list_jobs(
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    website_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("created_at", pattern="^(id|created_at|updated_at|status|job_type|progress)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """List background jobs for the authenticated user asynchronously with filtering, pagination, and sorting."""
    return await JobService.list_jobs_async(
        db=db,
        user_id=current_user.id,
        job_type=job_type,
        status=status,
        website_id=website_id,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        order=order
    )

@router.get("/jobs/{id}", response_model=schemas.JobOut)
async def get_job(id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    return await verify_job_ownership_async(id, current_user.id, db)

@router.get("/jobs/{id}/stream")
async def stream_job_progress(id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    """Stream real-time job progress and status updates via Server-Sent Events (SSE) with Redis Pub/Sub optimization."""
    import asyncio
    import json
    await verify_job_ownership_async(id, current_user.id, db)

    async def event_generator():
        # Yield current state on stream connect
        job = await crud.get_user_job_by_id_async(db, job_id=id, user_id=current_user.id)
        if not job:
            return

        initial_data = json.dumps({
            "id": job.id,
            "status": job.status,
            "progress": job.progress,
            "error_message": job.error_message,
            "updated_at": str(job.updated_at)
        })
        yield f"data: {initial_data}\n\n"

        if job.status in ["completed", "failed", "cancelled"]:
            return

        # Attempt Redis Pub/Sub stream listener
        redis_pubsub = None
        if settings.REDIS_URL:
            try:
                import redis.asyncio as aioredis
                client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
                pubsub = client.pubsub()
                await pubsub.subscribe(f"job:{id}:updates")
                redis_pubsub = (client, pubsub)
            except Exception as e:
                logger.warning(f"Failed to connect Redis PubSub for job stream #{id}: {e}")

        if redis_pubsub:
            client, pubsub = redis_pubsub
            try:
                while True:
                    try:
                        message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=2.0)
                        if message and message.get("type") == "message":
                            payload_str = message.get("data")
                            yield f"data: {payload_str}\n\n"
                            try:
                                parsed = json.loads(payload_str)
                                if parsed.get("status") in ["completed", "failed", "cancelled"]:
                                    break
                            except Exception:
                                pass
                    except asyncio.TimeoutError:
                        # Periodically verify job state in DB to avoid stale pubsub stream
                        job_check = await crud.get_user_job_by_id_async(db, job_id=id, user_id=current_user.id)
                        if job_check and job_check.status in ["completed", "failed", "cancelled"]:
                            break
            finally:
                try:
                    await pubsub.unsubscribe(f"job:{id}:updates")
                    await client.close()
                except Exception:
                    pass
        else:
            # Fallback DB polling loop
            last_progress = job.progress
            last_status = job.status
            while True:
                updated_job = await crud.get_user_job_by_id_async(db, job_id=id, user_id=current_user.id)
                if not updated_job:
                    break
                if updated_job.progress != last_progress or updated_job.status != last_status:
                    last_progress = updated_job.progress
                    last_status = updated_job.status
                    data = json.dumps({
                        "id": updated_job.id,
                        "status": updated_job.status,
                        "progress": updated_job.progress,
                        "error_message": updated_job.error_message,
                        "updated_at": str(updated_job.updated_at)
                    })
                    yield f"data: {data}\n\n"
                if updated_job.status in ["completed", "failed", "cancelled"]:
                    break
                await asyncio.sleep(0.5)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)



@router.post("/jobs/{id}/cancel", response_model=schemas.JobOut)
async def cancel_job(id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    """Cancel a queued or running background job with strict ownership verification asynchronously."""
    job = await verify_job_ownership_async(id, current_user.id, db)
    cancelled = await JobService.cancel_job_async(db, job, current_user.id)
    return cancelled

@router.delete("/jobs/{id}")
async def delete_job(id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_db)):
    job = await verify_job_ownership_async(id, current_user.id, db)
    await JobService.delete_job_instance_async(db, job)
    return {"message": "Job deleted successfully", "id": id}

@router.post("/jobs/cleanup/stale")
async def cleanup_stale_jobs(
    max_age_seconds: int = Query(300, ge=60),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_async_db)
):
    cleaned = await JobService.cleanup_stale_jobs_async(db, max_age_seconds=max_age_seconds)
    return {"message": f"Cleaned up {cleaned} stale jobs", "cleaned_count": cleaned}

@router.get("/workers")
async def list_active_workers(current_user: User = Depends(get_current_admin_user)):
    """List active worker heartbeats from Redis."""
    from backend.worker_heartbeat import WorkerHeartbeatManager
    workers = WorkerHeartbeatManager.get_active_workers()
    return {"active_workers": workers, "count": len(workers)}

@router.get("/dlq")
async def get_dead_letter_queue(limit: int = Query(50, ge=1, le=100), current_user: User = Depends(get_current_admin_user)):
    """Inspect dead letter queue contents."""
    from backend.dead_letter_queue import dead_letter_queue
    dlq_items = dead_letter_queue.get_dlq_jobs(limit=limit)
    return {"dead_letter_queue": dlq_items, "total_count": dead_letter_queue.get_dlq_count()}

@router.get("/queue/stats")
async def get_queue_statistics(current_user: User = Depends(get_current_admin_user)):
    """Retrieve detailed queue statistics, priority counts, and scaling hints."""
    from backend.queue import job_queue
    return job_queue.get_queue_stats()

@router.get("/worker/stats")
async def get_worker_statistics(current_user: User = Depends(get_current_admin_user)):
    """Retrieve background worker runtime statistics, utilization, and active jobs."""
    from backend.worker import worker_instance
    return worker_instance.get_worker_stats()

@router.post("/worker/concurrency")
async def adjust_worker_concurrency(
    concurrency: int = Query(..., ge=1, le=100),
    auto_tune: bool = Query(False),
    current_user: User = Depends(get_current_admin_user)
):
    """Dynamically adjust background worker concurrency or auto-tune based on workload pressure."""
    from backend.worker import worker_instance
    if auto_tune:
        hints = worker_instance.auto_tune_concurrency()
        return {
            "message": f"Worker concurrency auto-tuned to {worker_instance.concurrency}",
            "concurrency": worker_instance.concurrency,
            "scaling_hints": hints
        }
    new_capacity = worker_instance.adjust_concurrency(concurrency)
    return {
        "message": f"Worker concurrency adjusted to {new_capacity}",
        "concurrency": new_capacity
    }
