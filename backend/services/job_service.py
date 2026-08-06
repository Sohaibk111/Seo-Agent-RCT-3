import time
import json
from datetime import datetime
from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database.database import SessionLocal, AsyncSessionLocal
from backend.database import crud
from backend.database.models import Job
from backend.services.scraper_service import ScraperService
from backend.services.keyword_service import KeywordService
from backend.services.rank_service import RankService
from backend.logging_config import logger
from backend.metrics import metrics_registry
from backend.queue import job_queue

class JobService:
    @staticmethod
    def _publish_job_update(job_id: int, status: str, progress: int, error_message: Optional[str] = None):
        try:
            from backend.cache import get_redis_client
            client = get_redis_client()
            if client:
                channel = f"job:{job_id}:updates"
                payload = json.dumps({
                    "id": job_id,
                    "status": status,
                    "progress": progress,
                    "error_message": error_message,
                    "timestamp": datetime.utcnow().isoformat()
                })
                client.publish(channel, payload)
        except Exception as e:
            logger.debug(f"PubSub status update exception for job #{job_id}: {e}")

    @staticmethod
    def create_job(
        db: Session,
        user_id: int,
        job_type: str,
        website_id: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> Job:
        initial_ref = {"payload": payload} if payload else None
        job = crud.create_job(
            db=db,
            user_id=user_id,
            job_type=job_type,
            website_id=website_id,
            result_reference=initial_ref
        )
        logger.info(f"Job created: {job.id} ({job_type})", extra={"job_id": job.id, "user_id": user_id})
        return job

    @staticmethod
    async def create_job_async(
        db: AsyncSession,
        user_id: int,
        job_type: str,
        website_id: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> Job:
        initial_ref = {"payload": payload} if payload else None
        job = await crud.create_job_async(
            db=db,
            user_id=user_id,
            job_type=job_type,
            website_id=website_id,
            result_reference=initial_ref
        )
        logger.info(f"Job created (async): {job.id} ({job_type})", extra={"job_id": job.id, "user_id": user_id})
        return job

    @staticmethod
    def _resolve_job(db: Session, job: Any, user_id: int) -> Optional[Job]:
        if isinstance(job, Job):
            return job
        return crud.get_user_job_by_id(db, job_id=job, user_id=user_id)

    @staticmethod
    async def _resolve_job_async(db: AsyncSession, job: Any, user_id: int) -> Optional[Job]:
        if isinstance(job, Job):
            return job
        return await crud.get_user_job_by_id_async(db, job_id=job, user_id=user_id)

    @staticmethod
    def start_job(db: Session, job: Any, user_id: int) -> Optional[Job]:
        job_obj = JobService._resolve_job(db, job, user_id)
        if not job_obj or job_obj.status in ["running", "completed", "cancelled", "failed"]:
            return job_obj
        updated = crud.update_job(
            db=db,
            job=job_obj,
            status="running",
            progress=10,
            started_at=datetime.utcnow()
        )
        logger.info(f"Job started: {job_obj.id}", extra={"job_id": job_obj.id, "user_id": user_id})
        if updated:
            JobService._publish_job_update(updated.id, updated.status, updated.progress)
        return updated

    @staticmethod
    async def start_job_async(db: AsyncSession, job: Any, user_id: int) -> Optional[Job]:
        job_obj = await JobService._resolve_job_async(db, job, user_id)
        if not job_obj or job_obj.status in ["running", "completed", "cancelled", "failed"]:
            return job_obj
        updated = await crud.update_job_async(
            db=db,
            job=job_obj,
            status="running",
            progress=10,
            started_at=datetime.utcnow()
        )
        logger.info(f"Job started (async): {job_obj.id}", extra={"job_id": job_obj.id, "user_id": user_id})
        if updated:
            JobService._publish_job_update(updated.id, updated.status, updated.progress)
        return updated

    @staticmethod
    def is_cancelled(db: Session, job_id: int) -> bool:
        """Check if job status has been set to cancelled in DB using lightweight scalar query."""
        status = db.query(Job.status).filter(Job.id == job_id).scalar()
        cancelled = (status == "cancelled") if status is not None else True
        if cancelled:
            logger.info(f"Job cancellation detected: {job_id}", extra={"job_id": job_id})
        return cancelled

    @staticmethod
    async def is_cancelled_async(db: AsyncSession, job_id: int) -> bool:
        stmt = select(Job.status).where(Job.id == job_id)
        result = await db.execute(stmt)
        status = result.scalar_one_or_none()
        cancelled = (status == "cancelled") if status is not None else True
        if cancelled:
            logger.info(f"Job cancellation detected (async): {job_id}", extra={"job_id": job_id})
        return cancelled

    @staticmethod
    def update_progress(
        db: Session,
        job: Any,
        user_id: int,
        progress: int,
        status: Optional[str] = None
    ) -> Optional[Job]:
        job_obj = JobService._resolve_job(db, job, user_id)
        if not job_obj or job_obj.status in ["cancelled", "completed", "failed"]:
            return job_obj
        clamped_progress = max(0, min(100, progress))
        updated = crud.update_job(
            db=db,
            job=job_obj,
            status=status or job_obj.status,
            progress=clamped_progress
        )
        if updated:
            JobService._publish_job_update(updated.id, updated.status, updated.progress)
        return updated

    @staticmethod
    async def update_progress_async(
        db: AsyncSession,
        job: Any,
        user_id: int,
        progress: int,
        status: Optional[str] = None
    ) -> Optional[Job]:
        job_obj = await JobService._resolve_job_async(db, job, user_id)
        if not job_obj or job_obj.status in ["cancelled", "completed", "failed"]:
            return job_obj
        clamped_progress = max(0, min(100, progress))
        updated = await crud.update_job_async(
            db=db,
            job=job_obj,
            status=status or job_obj.status,
            progress=clamped_progress
        )
        if updated:
            JobService._publish_job_update(updated.id, updated.status, updated.progress)
        return updated

    @staticmethod
    def complete_job(
        db: Session,
        job: Any,
        user_id: int,
        result_reference: Optional[Any] = None
    ) -> Optional[Job]:
        job_obj = JobService._resolve_job(db, job, user_id)
        if not job_obj or job_obj.status in ["cancelled", "failed"]:
            return job_obj
        completed = crud.update_job(
            db=db,
            job=job_obj,
            status="completed",
            progress=100,
            finished_at=datetime.utcnow(),
            result_reference=result_reference
        )
        logger.info(f"Job completed: {job_obj.id}", extra={"job_id": job_obj.id, "user_id": user_id})
        if completed:
            JobService._publish_job_update(completed.id, completed.status, completed.progress)
        return completed

    @staticmethod
    async def complete_job_async(
        db: AsyncSession,
        job: Any,
        user_id: int,
        result_reference: Optional[Any] = None
    ) -> Optional[Job]:
        job_obj = await JobService._resolve_job_async(db, job, user_id)
        if not job_obj or job_obj.status in ["cancelled", "failed"]:
            return job_obj
        completed = await crud.update_job_async(
            db=db,
            job=job_obj,
            status="completed",
            progress=100,
            finished_at=datetime.utcnow(),
            result_reference=result_reference
        )
        logger.info(f"Job completed (async): {job_obj.id}", extra={"job_id": job_obj.id, "user_id": user_id})
        if completed:
            JobService._publish_job_update(completed.id, completed.status, completed.progress)
        return completed

    @staticmethod
    def fail_job(db: Session, job: Any, user_id: int, error_message: str) -> Optional[Job]:
        job_obj = JobService._resolve_job(db, job, user_id)
        if not job_obj or job_obj.status in ["cancelled", "completed"]:
            return job_obj
        failed = crud.update_job(
            db=db,
            job=job_obj,
            status="failed",
            finished_at=datetime.utcnow(),
            error_message=error_message
        )
        logger.error(f"Job failed: {job_obj.id} error={error_message}", extra={"job_id": job_obj.id, "user_id": user_id})
        if failed:
            JobService._publish_job_update(failed.id, failed.status, failed.progress, error_message=error_message)
        return failed

    @staticmethod
    async def fail_job_async(db: AsyncSession, job: Any, user_id: int, error_message: str) -> Optional[Job]:
        job_obj = await JobService._resolve_job_async(db, job, user_id)
        if not job_obj or job_obj.status in ["cancelled", "completed"]:
            return job_obj
        failed = await crud.update_job_async(
            db=db,
            job=job_obj,
            status="failed",
            finished_at=datetime.utcnow(),
            error_message=error_message
        )
        logger.error(f"Job failed (async): {job_obj.id} error={error_message}", extra={"job_id": job_obj.id, "user_id": user_id})
        if failed:
            JobService._publish_job_update(failed.id, failed.status, failed.progress, error_message=error_message)
        return failed

    @staticmethod
    def cancel_job(db: Session, job: Any, user_id: int) -> Optional[Job]:
        job_obj = JobService._resolve_job(db, job, user_id)
        if not job_obj:
            return None
        cancelled = crud.update_job(
            db=db,
            job=job_obj,
            status="cancelled",
            finished_at=datetime.utcnow()
        )
        logger.info(f"Job cancelled: {job_obj.id}", extra={"job_id": job_obj.id, "user_id": user_id})
        return cancelled

    @staticmethod
    async def cancel_job_async(db: AsyncSession, job: Any, user_id: int) -> Optional[Job]:
        job_obj = await JobService._resolve_job_async(db, job, user_id)
        if not job_obj:
            return None
        cancelled = await crud.update_job_async(
            db=db,
            job=job_obj,
            status="cancelled",
            finished_at=datetime.utcnow()
        )
        logger.info(f"Job cancelled (async): {job_obj.id}", extra={"job_id": job_obj.id, "user_id": user_id})
        return cancelled

    @staticmethod
    def cleanup_stale_jobs(db: Session, max_age_seconds: int = 300) -> int:
        """Clean up jobs stuck in pending or running state for longer than max_age_seconds."""
        stale_jobs = crud.get_stale_jobs(db, max_age_seconds=max_age_seconds)
        count = 0
        for job in stale_jobs:
            crud.update_job(
                db=db,
                job=job,
                status="failed",
                finished_at=datetime.utcnow(),
                error_message="Job timed out (stale execution cleanup)"
            )
            logger.warning(f"Stale job cleaned up: {job.id}", extra={"job_id": job.id, "user_id": job.user_id})
            count += 1
        return count

    @staticmethod
    async def cleanup_stale_jobs_async(db: AsyncSession, max_age_seconds: int = 300) -> int:
        stale_jobs = await crud.get_stale_jobs_async(db, max_age_seconds=max_age_seconds)
        count = 0
        for job in stale_jobs:
            await crud.update_job_async(
                db=db,
                job=job,
                status="failed",
                finished_at=datetime.utcnow(),
                error_message="Job timed out (stale execution cleanup)"
            )
            logger.warning(f"Stale job cleaned up (async): {job.id}", extra={"job_id": job.id, "user_id": job.user_id})
            count += 1
        return count

    @staticmethod
    def get_job(db: Session, job_id: int, user_id: int) -> Optional[Job]:
        return crud.get_user_job_by_id(db, job_id=job_id, user_id=user_id)

    @staticmethod
    async def get_job_async(db: AsyncSession, job_id: int, user_id: int) -> Optional[Job]:
        return await crud.get_user_job_by_id_async(db, job_id=job_id, user_id=user_id)

    @staticmethod
    def list_jobs(
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
        return crud.get_user_jobs(
            db=db,
            user_id=user_id,
            job_type=job_type,
            status=status,
            website_id=website_id,
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            order=order
        )

    @staticmethod
    async def list_jobs_async(
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
        return await crud.get_user_jobs_async(
            db=db,
            user_id=user_id,
            job_type=job_type,
            status=status,
            website_id=website_id,
            skip=skip,
            limit=limit,
            sort_by=sort_by,
            order=order
        )

    @staticmethod
    def delete_job(db: Session, job_id: int, user_id: int) -> bool:
        res = crud.delete_user_job(db, job_id=job_id, user_id=user_id)
        if res:
            logger.info(f"Job deleted: {job_id}", extra={"job_id": job_id, "user_id": user_id})
        return res

    @staticmethod
    async def delete_job_async(db: AsyncSession, job_id: int, user_id: int) -> bool:
        res = await crud.delete_user_job_async(db, job_id=job_id, user_id=user_id)
        if res:
            logger.info(f"Job deleted (async): {job_id}", extra={"job_id": job_id, "user_id": user_id})
        return res

    @staticmethod
    def delete_job_instance(db: Session, job: Job) -> None:
        crud.delete_job_instance(db, job)

    @staticmethod
    async def delete_job_instance_async(db: AsyncSession, job: Job) -> None:
        await crud.delete_job_instance_async(db, job)

    @staticmethod
    def _execute_with_retry(func, retries: int = 2, db: Optional[Session] = None, job_id: Optional[int] = None, *args, **kwargs):
        if db and job_id and JobService.is_cancelled(db, job_id):
            logger.info(f"Execution cancelled before starting: job_id={job_id}")
            return None
        from backend.retry import RetryEngine
        engine = RetryEngine(max_retries=retries)
        return engine.execute(func, *args, **kwargs)

    # --- BACKGROUND JOB RUNNERS ---
    @staticmethod
    def run_crawl_job(job_id: int, user_id: int, url: Optional[str], website_id: Optional[int]):
        db = SessionLocal()
        metrics_registry.inc_active_jobs(1)
        start_t = time.time()
        try:
            job = crud.get_user_job_by_id(db, job_id=job_id, user_id=user_id)
            if not job or job.status in ["cancelled", "completed", "failed"]:
                return
            JobService.start_job(db, job, user_id)
            JobService.update_progress(db, job, user_id, 30)

            if JobService.is_cancelled(db, job_id):
                return

            res = JobService._execute_with_retry(
                ScraperService.audit_website, retries=2, db=db, job_id=job_id, url=url, website_id=website_id, user_id=user_id
            )

            if JobService.is_cancelled(db, job_id) or res is None:
                return

            JobService.update_progress(db, job, user_id, 80)
            output = {
                "website_id": res["website"].id if hasattr(res.get("website"), "id") else None,
                "audit_id": res["audit"].id if hasattr(res.get("audit"), "id") else None,
                "leads_found": res.get("leads_found", 0)
            }
            JobService.complete_job(db, job, user_id, result_reference=output)
            metrics_registry.observe_crawl_duration(time.time() - start_t)
        except Exception as e:
            db.rollback()
            try:
                JobService.fail_job(db, job_id, user_id, str(e))
            except Exception as fail_err:
                logger.error(f"Failed to record job failure: {fail_err}")
        finally:
            metrics_registry.inc_active_jobs(-1)
            metrics_registry.set_queue_length(job_queue.get_queue_length())
            db.close()

    @staticmethod
    def run_audit_job(job_id: int, user_id: int, url: Optional[str], website_id: Optional[int]):
        db = SessionLocal()
        metrics_registry.inc_active_jobs(1)
        start_t = time.time()
        try:
            job = crud.get_user_job_by_id(db, job_id=job_id, user_id=user_id)
            if not job or job.status in ["cancelled", "completed", "failed"]:
                return
            JobService.start_job(db, job, user_id)
            JobService.update_progress(db, job, user_id, 30)

            if JobService.is_cancelled(db, job_id):
                return

            res = JobService._execute_with_retry(
                ScraperService.audit_website, retries=2, db=db, job_id=job_id, url=url, website_id=website_id, user_id=user_id
            )

            if JobService.is_cancelled(db, job_id) or res is None:
                return

            JobService.update_progress(db, job, user_id, 80)
            output = {
                "website_id": res["website"].id if hasattr(res.get("website"), "id") else None,
                "audit_id": res["audit"].id if hasattr(res.get("audit"), "id") else None,
                "score": getattr(res.get("audit"), "score", 0)
            }
            JobService.complete_job(db, job, user_id, result_reference=output)
            metrics_registry.observe_audit_duration(time.time() - start_t)
        except Exception as e:
            db.rollback()
            try:
                JobService.fail_job(db, job_id, user_id, str(e))
            except Exception as fail_err:
                logger.error(f"Failed to record job failure: {fail_err}")
        finally:
            metrics_registry.inc_active_jobs(-1)
            metrics_registry.set_queue_length(job_queue.get_queue_length())
            db.close()

    @staticmethod
    def run_keywords_job(job_id: int, user_id: int, seed_keyword: str, limit: int):
        db = SessionLocal()
        try:
            job = crud.get_user_job_by_id(db, job_id=job_id, user_id=user_id)
            if not job or job.status in ["cancelled", "completed", "failed"]:
                return
            JobService.start_job(db, job, user_id)
            JobService.update_progress(db, job, user_id, 30)

            if JobService.is_cancelled(db, job_id):
                return

            keywords = JobService._execute_with_retry(
                KeywordService.get_keyword_ideas, retries=2, db=db, job_id=job_id, seed_keyword=seed_keyword, limit=limit
            )

            if JobService.is_cancelled(db, job_id) or keywords is None:
                return

            JobService.update_progress(db, job, user_id, 80)
            output = {"seed_keyword": seed_keyword, "total": len(keywords), "keywords": keywords}
            JobService.complete_job(db, job, user_id, result_reference=output)
        except Exception as e:
            db.rollback()
            try:
                JobService.fail_job(db, job_id, user_id, str(e))
            except Exception as fail_err:
                logger.error(f"Failed to record job failure: {fail_err}")
        finally:
            db.close()

    @staticmethod
    def run_rank_job(job_id: int, user_id: int, keyword: str, domain: Optional[str], website_id: Optional[int]):
        db = SessionLocal()
        try:
            job = crud.get_user_job_by_id(db, job_id=job_id, user_id=user_id)
            if not job or job.status in ["cancelled", "completed", "failed"]:
                return
            JobService.start_job(db, job, user_id)
            JobService.update_progress(db, job, user_id, 30)

            if JobService.is_cancelled(db, job_id):
                return

            rank = JobService._execute_with_retry(
                RankService.check_rank, retries=2, db=db, job_id=job_id, keyword=keyword, domain=domain, website_id=website_id, user_id=user_id
            )

            if JobService.is_cancelled(db, job_id) or rank is None:
                return

            JobService.update_progress(db, job, user_id, 80)
            JobService.complete_job(db, job, user_id, result_reference=rank)
        except Exception as e:
            db.rollback()
            try:
                JobService.fail_job(db, job_id, user_id, str(e))
            except Exception as fail_err:
                logger.error(f"Failed to record job failure: {fail_err}")
        finally:
            db.close()
