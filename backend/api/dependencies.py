from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from backend.database.models import Website, AuditResult, Job
from backend.database import crud
from backend.exceptions import ResourceNotFoundException, ForbiddenException

def verify_website_ownership(website_id: int, user_id: int, db: Session) -> Website:
    """Verifies that website exists (404) and belongs to user_id (403) synchronously."""
    website = crud.get_website_by_id_unfiltered(db, website_id)
    if not website:
        raise ResourceNotFoundException(message="Website not found")
    if website.user_id != user_id:
        raise ForbiddenException(message="Forbidden: You do not own this website")
    return website

async def verify_website_ownership_async(website_id: int, user_id: int, db: AsyncSession) -> Website:
    """Verifies that website exists (404) and belongs to user_id (403) asynchronously."""
    website = await crud.get_website_by_id_unfiltered_async(db, website_id)
    if not website:
        raise ResourceNotFoundException(message="Website not found")
    if website.user_id != user_id:
        raise ForbiddenException(message="Forbidden: You do not own this website")
    return website


def verify_audit_ownership(audit_id: int, user_id: int, db: Session) -> AuditResult:
    """Verifies that audit result exists (404) and belongs to user_id (403) synchronously."""
    audit = crud.get_audit_by_id_unfiltered(db, audit_id)
    if not audit:
        raise ResourceNotFoundException(message="Audit result not found")
    if audit.user_id != user_id:
        raise ForbiddenException(message="Forbidden: You do not own this audit")
    return audit

async def verify_audit_ownership_async(audit_id: int, user_id: int, db: AsyncSession) -> AuditResult:
    """Verifies that audit result exists (404) and belongs to user_id (403) asynchronously."""
    audit = await crud.get_audit_by_id_unfiltered_async(db, audit_id)
    if not audit:
        raise ResourceNotFoundException(message="Audit result not found")
    if audit.user_id != user_id:
        raise ForbiddenException(message="Forbidden: You do not own this audit")
    return audit


def verify_domain_ownership(domain: str, user_id: int, db: Session) -> Optional[Website]:
    """Checks if domain is registered under another user's account (403) synchronously."""
    existing = crud.get_website_by_domain_unfiltered(db, domain)
    if existing and existing.user_id != user_id:
        raise ForbiddenException(message="Forbidden: Domain belongs to another user")
    return existing

async def verify_domain_ownership_async(domain: str, user_id: int, db: AsyncSession) -> Optional[Website]:
    """Checks if domain is registered under another user's account (403) asynchronously."""
    existing = await crud.get_website_by_domain_unfiltered_async(db, domain)
    if existing and existing.user_id != user_id:
        raise ForbiddenException(message="Forbidden: Domain belongs to another user")
    return existing


def verify_job_ownership(job_id: int, user_id: int, db: Session) -> Job:
    """Verifies that job exists (404) and belongs to user_id (403) synchronously."""
    job = crud.get_job_by_id_unfiltered(db, job_id)
    if not job:
        raise ResourceNotFoundException(message="Job not found")
    if job.user_id != user_id:
        raise ForbiddenException(message="Forbidden: You do not own this job")
    return job

async def verify_job_ownership_async(job_id: int, user_id: int, db: AsyncSession) -> Job:
    """Verifies that job exists (404) and belongs to user_id (403) asynchronously."""
    job = await crud.get_job_by_id_unfiltered_async(db, job_id)
    if not job:
        raise ResourceNotFoundException(message="Job not found")
    if job.user_id != user_id:
        raise ForbiddenException(message="Forbidden: You do not own this job")
    return job
