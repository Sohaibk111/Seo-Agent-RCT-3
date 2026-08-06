from datetime import datetime, timedelta
from typing import List, Optional, Union, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, update, insert

from backend.database.models import User, Website, AuditResult, Lead, Report, KeywordResult, RankCheck, Job
from backend.database.pagination import (
    paginate,
    async_paginate,
    cursor_paginate,
    async_cursor_paginate,
    encode_cursor,
    decode_cursor
)

# --- USER CRUD ---
def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

async def get_user_async(db: AsyncSession, user_id: int) -> Optional[User]:
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

async def get_user_by_email_async(db: AsyncSession, email: str) -> Optional[User]:
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    return result.scalars().first()

def create_user(db: Session, email: str, username: str, hashed_password: Optional[str] = None) -> User:
    db_user = User(email=email, username=username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

async def create_user_async(db: AsyncSession, email: str, username: str, hashed_password: Optional[str] = None) -> User:
    db_user = User(email=email, username=username, hashed_password=hashed_password)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


# --- WEBSITE CRUD (STRICTLY TENANT ISOLATED) ---
def get_user_websites(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    sort_by: str = "id",
    order: str = "asc"
) -> List[Website]:
    """Retrieve ONLY websites owned by the specified user_id with pagination, sorting, and search."""
    query = db.query(Website).options(joinedload(Website.owner)).filter(Website.user_id == user_id)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (Website.domain.ilike(pattern)) |
            (Website.url.ilike(pattern)) |
            (Website.company_name.ilike(pattern))
        )

    sort_attr = getattr(Website, sort_by, Website.id) if hasattr(Website, sort_by) else Website.id
    if order.lower() == "desc":
        query = query.order_by(sort_attr.desc())
    else:
        query = query.order_by(sort_attr.asc())

    return paginate(query, skip=skip, limit=limit)

async def get_user_websites_async(
    db: AsyncSession,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    sort_by: str = "id",
    order: str = "asc"
) -> List[Website]:
    stmt = select(Website).options(selectinload(Website.owner)).where(Website.user_id == user_id)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Website.domain.ilike(pattern),
                Website.url.ilike(pattern),
                Website.company_name.ilike(pattern)
            )
        )

    sort_attr = getattr(Website, sort_by, Website.id) if hasattr(Website, sort_by) else Website.id
    if order.lower() == "desc":
        stmt = stmt.order_by(sort_attr.desc())
    else:
        stmt = stmt.order_by(sort_attr.asc())

    return await async_paginate(db, stmt, skip=skip, limit=limit)

def get_website_by_id(db: Session, website_id: int, user_id: int) -> Optional[Website]:
    """Retrieve a website if and ONLY if it belongs to user_id."""
    return db.query(Website).options(joinedload(Website.owner)).filter(
        Website.id == website_id, Website.user_id == user_id
    ).first()

async def get_website_by_id_async(db: AsyncSession, website_id: int, user_id: int) -> Optional[Website]:
    stmt = select(Website).options(selectinload(Website.owner)).where(
        Website.id == website_id, Website.user_id == user_id
    )
    result = await db.execute(stmt)
    return result.scalars().first()

def get_website_by_id_unfiltered(db: Session, website_id: int) -> Optional[Website]:
    """Retrieve website strictly for ownership checking (returns record regardless of owner)."""
    return db.query(Website).options(joinedload(Website.owner)).filter(Website.id == website_id).first()

async def get_website_by_id_unfiltered_async(db: AsyncSession, website_id: int) -> Optional[Website]:
    stmt = select(Website).options(selectinload(Website.owner)).where(Website.id == website_id)
    result = await db.execute(stmt)
    return result.scalars().first()

def get_website_by_domain_unfiltered(db: Session, domain: str) -> Optional[Website]:
    """Retrieve website by domain regardless of owner for domain-level collision/ownership checking."""
    clean_domain = domain.replace("https://", "").replace("http://", "").split("/")[0].lower()
    return db.query(Website).options(joinedload(Website.owner)).filter(Website.domain == clean_domain).first()

async def get_website_by_domain_unfiltered_async(db: AsyncSession, domain: str) -> Optional[Website]:
    clean_domain = domain.replace("https://", "").replace("http://", "").split("/")[0].lower()
    stmt = select(Website).options(selectinload(Website.owner)).where(Website.domain == clean_domain)
    result = await db.execute(stmt)
    return result.scalars().first()

def create_website(db: Session, user_id: int, url: str, domain: str, company_name: Optional[str] = None) -> Website:
    website = Website(user_id=user_id, url=url, domain=domain, company_name=company_name)
    db.add(website)
    db.commit()
    db.refresh(website)
    return website

async def create_website_async(db: AsyncSession, user_id: int, url: str, domain: str, company_name: Optional[str] = None) -> Website:
    website = Website(user_id=user_id, url=url, domain=domain, company_name=company_name)
    db.add(website)
    await db.commit()
    await db.refresh(website)
    return website

def delete_website_instance(db: Session, website: Website) -> None:
    """Delete website instance directly without extra DB lookup."""
    db.delete(website)
    db.commit()

async def delete_website_instance_async(db: AsyncSession, website: Website) -> None:
    await db.delete(website)
    await db.commit()

def delete_user_website(db: Session, website_id: int, user_id: int) -> bool:
    """Delete website ONLY if owned by user_id."""
    website = get_website_by_id(db, website_id, user_id)
    if not website:
        return False
    delete_website_instance(db, website)
    return True

async def delete_user_website_async(db: AsyncSession, website_id: int, user_id: int) -> bool:
    website = await get_website_by_id_async(db, website_id, user_id)
    if not website:
        return False
    await delete_website_instance_async(db, website)
    return True


# --- AUDIT CRUD (STRICTLY TENANT ISOLATED) ---
def get_audit_by_id_unfiltered(db: Session, audit_id: int) -> Optional[AuditResult]:
    """Retrieve audit strictly for ownership validation with relationship eager loading."""
    return db.query(AuditResult).options(joinedload(AuditResult.website)).filter(AuditResult.id == audit_id).first()

async def get_audit_by_id_unfiltered_async(db: AsyncSession, audit_id: int) -> Optional[AuditResult]:
    stmt = select(AuditResult).options(selectinload(AuditResult.website)).where(AuditResult.id == audit_id)
    result = await db.execute(stmt)
    return result.scalars().first()

def get_user_audits_for_website(
    db: Session,
    website_id: int,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "id",
    order: str = "desc"
) -> List[AuditResult]:
    """Retrieve audits for a website if and ONLY if owned by user_id with pagination and sorting."""
    query = db.query(AuditResult).options(joinedload(AuditResult.website)).filter(
        AuditResult.website_id == website_id,
        AuditResult.user_id == user_id
    )

    sort_attr = getattr(AuditResult, sort_by, AuditResult.id) if hasattr(AuditResult, sort_by) else AuditResult.id
    if order.lower() == "asc":
        query = query.order_by(sort_attr.asc())
    else:
        query = query.order_by(sort_attr.desc())

    return paginate(query, skip=skip, limit=limit)

async def get_user_audits_for_website_async(
    db: AsyncSession,
    website_id: int,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "id",
    order: str = "desc"
) -> List[AuditResult]:
    stmt = select(AuditResult).options(selectinload(AuditResult.website)).where(
        AuditResult.website_id == website_id,
        AuditResult.user_id == user_id
    )

    sort_attr = getattr(AuditResult, sort_by, AuditResult.id) if hasattr(AuditResult, sort_by) else AuditResult.id
    if order.lower() == "asc":
        stmt = stmt.order_by(sort_attr.asc())
    else:
        stmt = stmt.order_by(sort_attr.desc())

    return await async_paginate(db, stmt, skip=skip, limit=limit)

def create_audit(db: Session, website_id: int, user_id: int, score: int, title: str, meta_description: str,
                 h1_tags: List[str], canonical_url: str, images_count: int, images_without_alt: int,
                 broken_links_count: int) -> AuditResult:
    audit = AuditResult(
        website_id=website_id,
        user_id=user_id,
        score=score,
        title=title,
        title_length=len(title) if title else 0,
        meta_description=meta_description,
        meta_description_length=len(meta_description) if meta_description else 0,
        h1_tags=h1_tags,
        canonical_url=canonical_url,
        viewport="width=device-width, initial-scale=1.0",
        images_count=images_count,
        images_without_alt=images_without_alt,
        has_structured_data=True,
        has_sitemap=True,
        has_robots_txt=True,
        broken_links_count=broken_links_count
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit

async def create_audit_async(db: AsyncSession, website_id: int, user_id: int, score: int, title: str, meta_description: str,
                       h1_tags: List[str], canonical_url: str, images_count: int, images_without_alt: int,
                       broken_links_count: int) -> AuditResult:
    audit = AuditResult(
        website_id=website_id,
        user_id=user_id,
        score=score,
        title=title,
        title_length=len(title) if title else 0,
        meta_description=meta_description,
        meta_description_length=len(meta_description) if meta_description else 0,
        h1_tags=h1_tags,
        canonical_url=canonical_url,
        viewport="width=device-width, initial-scale=1.0",
        images_count=images_count,
        images_without_alt=images_without_alt,
        has_structured_data=True,
        has_sitemap=True,
        has_robots_txt=True,
        broken_links_count=broken_links_count
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)
    return audit


# --- LEADS CRUD (STRICTLY TENANT ISOLATED) ---
def get_user_leads_for_website(
    db: Session,
    website_id: int,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    source: Optional[str] = None,
    sort_by: str = "id",
    order: str = "desc"
) -> List[Lead]:
    query = db.query(Lead).options(joinedload(Lead.website)).filter(
        Lead.website_id == website_id,
        Lead.user_id == user_id
    )
    if source:
        query = query.filter(Lead.source == source)

    sort_attr = getattr(Lead, sort_by, Lead.id) if hasattr(Lead, sort_by) else Lead.id
    if order.lower() == "asc":
        query = query.order_by(sort_attr.asc())
    else:
        query = query.order_by(sort_attr.desc())

    return paginate(query, skip=skip, limit=limit)

async def get_user_leads_for_website_async(
    db: AsyncSession,
    website_id: int,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    source: Optional[str] = None,
    sort_by: str = "id",
    order: str = "desc"
) -> List[Lead]:
    stmt = select(Lead).options(selectinload(Lead.website)).where(
        Lead.website_id == website_id,
        Lead.user_id == user_id
    )
    if source:
        stmt = stmt.where(Lead.source == source)

    sort_attr = getattr(Lead, sort_by, Lead.id) if hasattr(Lead, sort_by) else Lead.id
    if order.lower() == "asc":
        stmt = stmt.order_by(sort_attr.asc())
    else:
        stmt = stmt.order_by(sort_attr.desc())

    return await async_paginate(db, stmt, skip=skip, limit=limit)

def create_lead(db: Session, website_id: int, user_id: int, email: str, source: str = "audit") -> Lead:
    lead = Lead(website_id=website_id, user_id=user_id, email=email, source=source)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead

async def create_lead_async(db: AsyncSession, website_id: int, user_id: int, email: str, source: str = "audit") -> Lead:
    lead = Lead(website_id=website_id, user_id=user_id, email=email, source=source)
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


# --- REPORTS CRUD (STRICTLY TENANT ISOLATED) ---
def get_user_reports_for_website(
    db: Session,
    website_id: int,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    format: Optional[str] = None,
    sort_by: str = "id",
    order: str = "desc"
) -> List[Report]:
    query = db.query(Report).options(joinedload(Report.website)).filter(
        Report.website_id == website_id,
        Report.user_id == user_id
    )
    if format:
        query = query.filter(Report.format == format)

    sort_attr = getattr(Report, sort_by, Report.id) if hasattr(Report, sort_by) else Report.id
    if order.lower() == "asc":
        query = query.order_by(sort_attr.asc())
    else:
        query = query.order_by(sort_attr.desc())

    return paginate(query, skip=skip, limit=limit)

async def get_user_reports_for_website_async(
    db: AsyncSession,
    website_id: int,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    format: Optional[str] = None,
    sort_by: str = "id",
    order: str = "desc"
) -> List[Report]:
    stmt = select(Report).options(selectinload(Report.website)).where(
        Report.website_id == website_id,
        Report.user_id == user_id
    )
    if format:
        stmt = stmt.where(Report.format == format)

    sort_attr = getattr(Report, sort_by, Report.id) if hasattr(Report, sort_by) else Report.id
    if order.lower() == "asc":
        stmt = stmt.order_by(sort_attr.asc())
    else:
        stmt = stmt.order_by(sort_attr.desc())

    return await async_paginate(db, stmt, skip=skip, limit=limit)

def create_report(db: Session, website_id: int, user_id: int, title: str, format: str = "pdf") -> Report:
    report = Report(website_id=website_id, user_id=user_id, title=title, format=format)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report

async def create_report_async(db: AsyncSession, website_id: int, user_id: int, title: str, format: str = "pdf") -> Report:
    report = Report(website_id=website_id, user_id=user_id, title=title, format=format)
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


# --- JOBS CRUD (STRICTLY TENANT ISOLATED) ---
def get_job_by_id_unfiltered(db: Session, job_id: int) -> Optional[Job]:
    """Retrieve job strictly for ownership verification with relationship eager loading."""
    return db.query(Job).options(joinedload(Job.website)).filter(Job.id == job_id).first()

async def get_job_by_id_unfiltered_async(db: AsyncSession, job_id: int) -> Optional[Job]:
    stmt = select(Job).options(selectinload(Job.website)).where(Job.id == job_id)
    result = await db.execute(stmt)
    return result.scalars().first()

def get_user_job_by_id(db: Session, job_id: int, user_id: int) -> Optional[Job]:
    """Retrieve job if and ONLY if it belongs to user_id with eager relationship loading."""
    return db.query(Job).options(joinedload(Job.website)).filter(Job.id == job_id, Job.user_id == user_id).first()

async def get_user_job_by_id_async(db: AsyncSession, job_id: int, user_id: int) -> Optional[Job]:
    stmt = select(Job).options(selectinload(Job.website)).where(Job.id == job_id, Job.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()

def get_user_jobs(
    db: Session,
    user_id: int,
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    website_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "created_at",
    order: str = "desc"
) -> List[Job]:
    """Retrieve jobs owned exclusively by user_id with optional filtering, sorting, eager loading, and pagination."""
    query = db.query(Job).options(joinedload(Job.website)).filter(Job.user_id == user_id)
    if job_type:
        query = query.filter(Job.job_type == job_type)
    if status:
        query = query.filter(Job.status == status)
    if website_id is not None:
        query = query.filter(Job.website_id == website_id)

    sort_attr = getattr(Job, sort_by, Job.created_at) if hasattr(Job, sort_by) else Job.created_at
    if order.lower() == "asc":
        query = query.order_by(sort_attr.asc())
    else:
        query = query.order_by(sort_attr.desc())

    return paginate(query, skip=skip, limit=limit)

async def get_user_jobs_async(
    db: AsyncSession,
    user_id: int,
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    website_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "created_at",
    order: str = "desc"
) -> List[Job]:
    stmt = select(Job).options(selectinload(Job.website)).where(Job.user_id == user_id)
    if job_type:
        stmt = stmt.where(Job.job_type == job_type)
    if status:
        stmt = stmt.where(Job.status == status)
    if website_id is not None:
        stmt = stmt.where(Job.website_id == website_id)

    sort_attr = getattr(Job, sort_by, Job.created_at) if hasattr(Job, sort_by) else Job.created_at
    if order.lower() == "asc":
        stmt = stmt.order_by(sort_attr.asc())
    else:
        stmt = stmt.order_by(sort_attr.desc())

    return await async_paginate(db, stmt, skip=skip, limit=limit)

def create_job(db: Session, user_id: int, job_type: str, website_id: Optional[int] = None, result_reference: Optional[dict] = None) -> Job:
    """Create a new job record for user_id."""
    job = Job(
        user_id=user_id,
        website_id=website_id,
        job_type=job_type,
        status="pending",
        progress=0,
        result_reference=result_reference,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

async def create_job_async(db: AsyncSession, user_id: int, job_type: str, website_id: Optional[int] = None, result_reference: Optional[dict] = None) -> Job:
    job = Job(
        user_id=user_id,
        website_id=website_id,
        job_type=job_type,
        status="pending",
        progress=0,
        result_reference=result_reference,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job

def update_job(db: Session, job: Job, status: Optional[str] = None, progress: Optional[int] = None,
               error_message: Optional[str] = None, result_reference: Optional[dict] = None,
               started_at: Optional[datetime] = None, finished_at: Optional[datetime] = None) -> Job:
    """Update job fields safely in place without redundant refresh SELECT queries."""
    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = progress
    if error_message is not None:
        job.error_message = error_message
    if result_reference is not None:
        job.result_reference = result_reference
    if started_at is not None:
        job.started_at = started_at
    if finished_at is not None:
        job.finished_at = finished_at
    job.updated_at = datetime.utcnow()
    db.commit()
    return job

async def update_job_async(db: AsyncSession, job: Job, status: Optional[str] = None, progress: Optional[int] = None,
                     error_message: Optional[str] = None, result_reference: Optional[dict] = None,
                     started_at: Optional[datetime] = None, finished_at: Optional[datetime] = None) -> Job:
    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = progress
    if error_message is not None:
        job.error_message = error_message
    if result_reference is not None:
        job.result_reference = result_reference
    if started_at is not None:
        job.started_at = started_at
    if finished_at is not None:
        job.finished_at = finished_at
    job.updated_at = datetime.utcnow()
    await db.commit()
    return job

def delete_job_instance(db: Session, job: Job) -> None:
    """Delete job instance directly without extra DB lookup."""
    db.delete(job)
    db.commit()

async def delete_job_instance_async(db: AsyncSession, job: Job) -> None:
    await db.delete(job)
    await db.commit()

def delete_user_job(db: Session, job_id: int, user_id: int) -> bool:
    """Delete job ONLY if owned by user_id."""
    job = get_user_job_by_id(db, job_id, user_id)
    if not job:
        return False
    delete_job_instance(db, job)
    return True

async def delete_user_job_async(db: AsyncSession, job_id: int, user_id: int) -> bool:
    job = await get_user_job_by_id_async(db, job_id, user_id)
    if not job:
        return False
    await delete_job_instance_async(db, job)
    return True

def get_stale_jobs(db: Session, max_age_seconds: int = 300) -> List[Job]:
    """Retrieve running or pending jobs that haven't been updated within max_age_seconds using composite index."""
    cutoff = datetime.utcnow() - timedelta(seconds=max_age_seconds)
    return db.query(Job).options(joinedload(Job.website)).filter(
        Job.status.in_(["running", "pending"]),
        Job.updated_at < cutoff
    ).all()

async def get_stale_jobs_async(db: AsyncSession, max_age_seconds: int = 300) -> List[Job]:
    cutoff = datetime.utcnow() - timedelta(seconds=max_age_seconds)
    stmt = select(Job).options(selectinload(Job.website)).where(
        Job.status.in_(["running", "pending"]),
        Job.updated_at < cutoff
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# --- RELATIONSHIP EAGER LOADING (SELECTINLOAD / JOINEDLOAD TO ELIMINATE N+1 QUERIES) ---
def get_user_with_relations(db: Session, user_id: int) -> Optional[User]:
    """Retrieve user with selectinload on collection relationships (websites, audits, jobs)."""
    return db.query(User).options(
        selectinload(User.websites),
        selectinload(User.audits),
        selectinload(User.jobs)
    ).filter(User.id == user_id).first()

async def get_user_with_relations_async(db: AsyncSession, user_id: int) -> Optional[User]:
    stmt = select(User).options(
        selectinload(User.websites),
        selectinload(User.audits),
        selectinload(User.jobs)
    ).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()

def get_website_with_details(db: Session, website_id: int, user_id: int) -> Optional[Website]:
    """Retrieve website with selectinload on collections and joinedload on owner to prevent N+1 queries."""
    return db.query(Website).options(
        joinedload(Website.owner),
        selectinload(Website.audits),
        selectinload(Website.leads),
        selectinload(Website.reports),
        selectinload(Website.jobs)
    ).filter(Website.id == website_id, Website.user_id == user_id).first()

async def get_website_with_details_async(db: AsyncSession, website_id: int, user_id: int) -> Optional[Website]:
    stmt = select(Website).options(
        joinedload(Website.owner),
        selectinload(Website.audits),
        selectinload(Website.leads),
        selectinload(Website.reports),
        selectinload(Website.jobs)
    ).where(Website.id == website_id, Website.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()


# --- BULK INSERTS AND BULK UPDATES ---
def bulk_create_keywords(db: Session, user_id: int, items: List[Dict[str, Any]]) -> List[KeywordResult]:
    """Perform bulk insert of keyword results to optimize write throughput."""
    if not items:
        return []
    records = []
    for item in items:
        record = KeywordResult(
            user_id=user_id,
            seed_keyword=item.get("seed_keyword", ""),
            keyword=item.get("keyword", ""),
            intent=item.get("intent", "Informational"),
            volume=item.get("volume", 0),
            kd=item.get("kd", 0),
            cpc=str(item.get("cpc", "0.00")),
            cluster=item.get("cluster", "General")
        )
        records.append(record)
    db.add_all(records)
    db.commit()
    return records

async def bulk_create_keywords_async(db: AsyncSession, user_id: int, items: List[Dict[str, Any]]) -> List[KeywordResult]:
    """Perform bulk insert of keyword results asynchronously."""
    if not items:
        return []
    records = []
    for item in items:
        record = KeywordResult(
            user_id=user_id,
            seed_keyword=item.get("seed_keyword", ""),
            keyword=item.get("keyword", ""),
            intent=item.get("intent", "Informational"),
            volume=item.get("volume", 0),
            kd=item.get("kd", 0),
            cpc=str(item.get("cpc", "0.00")),
            cluster=item.get("cluster", "General")
        )
        records.append(record)
    db.add_all(records)
    await db.commit()
    return records

def bulk_create_leads(db: Session, user_id: int, website_id: Optional[int], items: List[Dict[str, Any]]) -> List[Lead]:
    """Perform bulk insert of lead records."""
    if not items:
        return []
    records = []
    for item in items:
        record = Lead(
            user_id=user_id,
            website_id=website_id,
            email=item.get("email"),
            phone=item.get("phone"),
            source=item.get("source", "audit")
        )
        records.append(record)
    db.add_all(records)
    db.commit()
    return records

async def bulk_create_leads_async(db: AsyncSession, user_id: int, website_id: Optional[int], items: List[Dict[str, Any]]) -> List[Lead]:
    if not items:
        return []
    records = []
    for item in items:
        record = Lead(
            user_id=user_id,
            website_id=website_id,
            email=item.get("email"),
            phone=item.get("phone"),
            source=item.get("source", "audit")
        )
        records.append(record)
    db.add_all(records)
    await db.commit()
    return records

def bulk_create_rank_checks(db: Session, user_id: int, items: List[Dict[str, Any]]) -> List[RankCheck]:
    """Perform bulk insert of rank check results."""
    if not items:
        return []
    records = []
    for item in items:
        record = RankCheck(
            user_id=user_id,
            website_id=item.get("website_id"),
            keyword=item.get("keyword"),
            domain=item.get("domain"),
            position=item.get("position", 100),
            checked_results=item.get("checked_results", 30),
            source=item.get("source", "free_tracker")
        )
        records.append(record)
    db.add_all(records)
    db.commit()
    return records

async def bulk_create_rank_checks_async(db: AsyncSession, user_id: int, items: List[Dict[str, Any]]) -> List[RankCheck]:
    if not items:
        return []
    records = []
    for item in items:
        record = RankCheck(
            user_id=user_id,
            website_id=item.get("website_id"),
            keyword=item.get("keyword"),
            domain=item.get("domain"),
            position=item.get("position", 100),
            checked_results=item.get("checked_results", 30),
            source=item.get("source", "free_tracker")
        )
        records.append(record)
    db.add_all(records)
    await db.commit()
    return records

def bulk_update_jobs_status(
    db: Session,
    job_ids: List[int],
    status: str,
    progress: Optional[int] = None,
    error_message: Optional[str] = None
) -> int:
    """Perform bulk update of job statuses in a single SQL UPDATE query."""
    if not job_ids:
        return 0
    values: Dict[str, Any] = {"status": status, "updated_at": datetime.utcnow()}
    if progress is not None:
        values["progress"] = progress
    if error_message is not None:
        values["error_message"] = error_message

    stmt = update(Job).where(Job.id.in_(job_ids)).values(**values)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount

async def bulk_update_jobs_status_async(
    db: AsyncSession,
    job_ids: List[int],
    status: str,
    progress: Optional[int] = None,
    error_message: Optional[str] = None
) -> int:
    """Perform bulk update of job statuses asynchronously in a single SQL UPDATE query."""
    if not job_ids:
        return 0
    values: Dict[str, Any] = {"status": status, "updated_at": datetime.utcnow()}
    if progress is not None:
        values["progress"] = progress
    if error_message is not None:
        values["error_message"] = error_message

    stmt = update(Job).where(Job.id.in_(job_ids)).values(**values)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


# --- CURSOR-BASED PAGINATION CRUD FUNCTIONS ---
def get_user_websites_cursor(
    db: Session,
    user_id: int,
    cursor: Optional[str] = None,
    limit: int = 50,
    order: str = "desc"
) -> Tuple[List[Website], Optional[str], bool]:
    """Retrieve user websites using cursor pagination."""
    query = db.query(Website).options(joinedload(Website.owner)).filter(Website.user_id == user_id)
    return cursor_paginate(query, column=Website.id, cursor=cursor, limit=limit, order=order)

async def get_user_websites_cursor_async(
    db: AsyncSession,
    user_id: int,
    cursor: Optional[str] = None,
    limit: int = 50,
    order: str = "desc"
) -> Tuple[List[Website], Optional[str], bool]:
    stmt = select(Website).options(selectinload(Website.owner)).where(Website.user_id == user_id)
    return await async_cursor_paginate(db, stmt, column=Website.id, cursor=cursor, limit=limit, order=order)

async def get_user_audits_cursor_async(
    db: AsyncSession,
    website_id: int,
    user_id: int,
    cursor: Optional[str] = None,
    limit: int = 50,
    order: str = "desc"
) -> Tuple[List[AuditResult], Optional[str], bool]:
    """Retrieve audit results using cursor pagination."""
    stmt = select(AuditResult).options(selectinload(AuditResult.website)).where(
        AuditResult.website_id == website_id,
        AuditResult.user_id == user_id
    )
    return await async_cursor_paginate(db, stmt, column=AuditResult.id, cursor=cursor, limit=limit, order=order)

async def get_user_jobs_cursor_async(
    db: AsyncSession,
    user_id: int,
    cursor: Optional[str] = None,
    limit: int = 50,
    order: str = "desc"
) -> Tuple[List[Job], Optional[str], bool]:
    """Retrieve jobs using cursor pagination."""
    stmt = select(Job).options(selectinload(Job.website)).where(Job.user_id == user_id)
    return await async_cursor_paginate(db, stmt, column=Job.id, cursor=cursor, limit=limit, order=order)

async def get_user_leads_cursor_async(
    db: AsyncSession,
    website_id: int,
    user_id: int,
    cursor: Optional[str] = None,
    limit: int = 50,
    order: str = "desc"
) -> Tuple[List[Lead], Optional[str], bool]:
    """Retrieve leads using cursor pagination."""
    stmt = select(Lead).options(selectinload(Lead.website)).where(
        Lead.website_id == website_id,
        Lead.user_id == user_id
    )
    return await async_cursor_paginate(db, stmt, column=Lead.id, cursor=cursor, limit=limit, order=order)

