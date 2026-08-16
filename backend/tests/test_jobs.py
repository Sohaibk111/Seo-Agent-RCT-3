import pytest
from fastapi.testclient import TestClient
from backend.services.job_service import JobService
from backend.database import crud

def test_job_service_lifecycle(db_session):
    user = crud.create_user(db_session, email="jobuser@test.com", username="jobuser")
    website = crud.create_website(db_session, user_id=user.id, url="https://jobtest.com", domain="jobtest.com")

    # 1. Create job
    job = JobService.create_job(db_session, user_id=user.id, job_type="audit", website_id=website.id, payload={"test": True})
    assert job.id is not None
    assert job.status == "pending"
    assert job.progress == 0
    assert job.user_id == user.id
    assert job.website_id == website.id

    # 2. Start job
    started = JobService.start_job(db_session, job_id=job.id, user_id=user.id)
    assert started.status == "running"
    assert started.progress == 10
    assert started.started_at is not None

    # 3. Update progress
    updated = JobService.update_progress(db_session, job_id=job.id, user_id=user.id, progress=50)
    assert updated.progress == 50

    # Clamped progress test
    over_clamped = JobService.update_progress(db_session, job_id=job.id, user_id=user.id, progress=150)
    assert over_clamped.progress == 100

    # 4. Complete job
    completed = JobService.complete_job(db_session, job_id=job.id, user_id=user.id, result_reference={"score": 90})
    assert completed.status == "completed"
    assert completed.progress == 100
    assert completed.finished_at is not None
    assert completed.result_reference == {"score": 90}

    # 5. Fail job
    failed_job = JobService.create_job(db_session, user_id=user.id, job_type="crawl")
    failed = JobService.fail_job(db_session, job_id=failed_job.id, user_id=user.id, error_message="Network Timeout")
    assert failed.status == "failed"
    assert failed.error_message == "Network Timeout"

    # 6. Cancel job
    cancel_target = JobService.create_job(db_session, user_id=user.id, job_type="keywords")
    cancelled = JobService.cancel_job(db_session, job_id=cancel_target.id, user_id=user.id)
    assert cancelled.status == "cancelled"

    # 7. Get job & List jobs
    fetched = JobService.get_job(db_session, job_id=job.id, user_id=user.id)
    assert fetched.id == job.id

    user_jobs = JobService.list_jobs(db_session, user_id=user.id)
    assert len(user_jobs) == 3

    # Filtering
    audit_jobs = JobService.list_jobs(db_session, user_id=user.id, job_type="audit")
    assert len(audit_jobs) == 1
    assert audit_jobs[0].job_type == "audit"

    # 8. Delete job
    deleted = JobService.delete_job(db_session, job_id=job.id, user_id=user.id)
    assert deleted is True
    assert JobService.get_job(db_session, job_id=job.id, user_id=user.id) is None


def test_job_endpoints_create_and_query(client: TestClient):
    user_a_token = "Bearer token_user_1"

    # Create crawl job
    res = client.post("/api/v1/jobs/crawl", headers={"Authorization": user_a_token}, json={"url": "https://crawltarget.com"})
    assert res.status_code == 200
    crawl_data = res.json()
    assert crawl_data["job_type"] == "crawl"
    assert crawl_data["status"] == "pending"
    crawl_id = crawl_data["id"]

    # Create audit job
    res = client.post("/api/v1/jobs/audit", headers={"Authorization": user_a_token}, json={"url": "https://audittarget.com"})
    assert res.status_code == 200
    audit_data = res.json()
    assert audit_data["job_type"] == "audit"
    audit_id = audit_data["id"]

    # Create keywords job
    res = client.post("/api/v1/jobs/keywords", headers={"Authorization": user_a_token}, json={"seed_keyword": "ai seo", "limit": 5})
    assert res.status_code == 200
    kw_data = res.json()
    assert kw_data["job_type"] == "keywords"

    # Create rank job
    res = client.post("/api/v1/jobs/rank", headers={"Authorization": user_a_token}, json={"keyword": "best seo app", "domain": "audittarget.com"})
    assert res.status_code == 200
    rank_data = res.json()
    assert rank_data["job_type"] == "rank"

    # Get single job by ID
    res = client.get(f"/api/v1/jobs/{crawl_id}", headers={"Authorization": user_a_token})
    assert res.status_code == 200
    assert res.json()["id"] == crawl_id

    # List jobs
    res = client.get("/api/v1/jobs", headers={"Authorization": user_a_token})
    assert res.status_code == 200
    all_jobs = res.json()
    assert len(all_jobs) >= 4

    # Delete job
    res = client.delete(f"/api/v1/jobs/{audit_id}", headers={"Authorization": user_a_token})
    assert res.status_code == 200
    assert res.json()["id"] == audit_id


def test_job_security_and_tenant_isolation(client: TestClient):
    user_a_token = "Bearer token_user_1"
    user_b_token = "Bearer token_user_2"

    # User A creates a job
    res = client.post("/api/v1/jobs/audit", headers={"Authorization": user_a_token}, json={"url": "https://usera-exclusive-job.com"})
    assert res.status_code == 200
    user_a_job_id = res.json()["id"]

    # 401 Unauthenticated
    assert client.get("/api/v1/jobs").status_code == 401
    assert client.get(f"/api/v1/jobs/{user_a_job_id}").status_code == 401
    assert client.delete(f"/api/v1/jobs/{user_a_job_id}").status_code == 401

    # 403 Forbidden: User B cannot get User A's job
    res_b_get = client.get(f"/api/v1/jobs/{user_a_job_id}", headers={"Authorization": user_b_token})
    assert res_b_get.status_code == 403

    # 403 Forbidden: User B cannot delete User A's job
    res_b_del = client.delete(f"/api/v1/jobs/{user_a_job_id}", headers={"Authorization": user_b_token})
    assert res_b_del.status_code == 403

    # User B list jobs excludes User A's job
    res_b_list = client.get("/api/v1/jobs", headers={"Authorization": user_b_token})
    assert res_b_list.status_code == 200
    assert not any(j["id"] == user_a_job_id for j in res_b_list.json())

    # 404 Not Found for non-existent job
    assert client.get("/api/v1/jobs/999999", headers={"Authorization": user_a_token}).status_code == 404
    assert client.delete("/api/v1/jobs/999999", headers={"Authorization": user_a_token}).status_code == 404


def test_stale_jobs_cleanup(client: TestClient):
    user_a_token = "Bearer token_user_1"
    res = client.post("/api/v1/jobs/cleanup/stale?max_age_seconds=60", headers={"Authorization": user_a_token})
    assert res.status_code == 200
    assert "cleaned_count" in res.json()


def test_background_job_runners_and_duplicate_prevention(db_session):
    user = crud.create_user(db_session, email="runneruser@test.com", username="runneruser")
    website = crud.create_website(db_session, user_id=user.id, url="https://runnertest.com", domain="runnertest.com")

    # Create job
    job = JobService.create_job(db_session, user_id=user.id, job_type="keywords", website_id=website.id)
    assert job.status == "pending"

    # Run background job runner
    JobService.run_keywords_job(job_id=job.id, user_id=user.id, seed_keyword="python fast api", limit=5)

    completed_job = JobService.get_job(db_session, job_id=job.id, user_id=user.id)
    assert completed_job.status == "completed"
    assert completed_job.progress == 100
    assert completed_job.result_reference["total"] == 5

    # Duplicate start_job attempt on completed job should be ignored
    dup_start = JobService.start_job(db_session, job_id=job.id, user_id=user.id)
    assert dup_start.status == "completed"
    assert dup_start.progress == 100


def test_job_cancellation_prevents_completion(db_session):
    user = crud.create_user(db_session, email="canceluser@test.com", username="canceluser")
    job = JobService.create_job(db_session, user_id=user.id, job_type="rank")

    # Cancel job before execution
    JobService.cancel_job(db_session, job_id=job.id, user_id=user.id)
    assert JobService.is_cancelled(db_session, job.id) is True

    # Attempt running background job on cancelled job
    JobService.run_rank_job(job_id=job.id, user_id=user.id, keyword="test kw", domain="example.com", website_id=None)

    post_run_job = JobService.get_job(db_session, job_id=job.id, user_id=user.id)
    assert post_run_job.status == "cancelled"
    assert post_run_job.result_reference is None or "position" not in (post_run_job.result_reference or {})

