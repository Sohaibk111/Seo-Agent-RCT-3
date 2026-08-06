import pytest
from datetime import datetime, timedelta
from backend.database import crud

def test_user_crud(db_session):
    user = crud.create_user(db_session, email="cruduser@test.com", username="cruduser", hashed_password="hashed_pass")
    assert user.id is not None
    assert user.email == "cruduser@test.com"

    fetched = crud.get_user(db_session, user.id)
    assert fetched is not None
    assert fetched.username == "cruduser"

    fetched_by_email = crud.get_user_by_email(db_session, "cruduser@test.com")
    assert fetched_by_email is not None
    assert fetched_by_email.id == user.id

    assert crud.get_user(db_session, 999999) is None
    assert crud.get_user_by_email(db_session, "nonexistent@test.com") is None


def test_website_crud(db_session):
    user = crud.create_user(db_session, email="webuser@test.com", username="webuser")
    other_user = crud.create_user(db_session, email="webother@test.com", username="webother")

    site1 = crud.create_website(db_session, user_id=user.id, url="https://site1.com", domain="site1.com", company_name="Corp One")
    site2 = crud.create_website(db_session, user_id=user.id, url="https://site2.com", domain="site2.com", company_name="Corp Two")

    # get_user_websites with search, sort, pagination
    user_sites = crud.get_user_websites(db_session, user_id=user.id, search="site1")
    assert len(user_sites) == 1
    assert user_sites[0].id == site1.id

    # get_website_by_id (filtered by owner)
    assert crud.get_website_by_id(db_session, site1.id, user.id) is not None
    assert crud.get_website_by_id(db_session, site1.id, other_user.id) is None

    # get_website_by_id_unfiltered
    assert crud.get_website_by_id_unfiltered(db_session, site1.id) is not None

    # get_website_by_domain_unfiltered
    assert crud.get_website_by_domain_unfiltered(db_session, "https://site2.com/path") is not None

    # delete_user_website
    assert crud.delete_user_website(db_session, site1.id, other_user.id) is False
    assert crud.delete_user_website(db_session, site1.id, user.id) is True
    assert crud.get_website_by_id(db_session, site1.id, user.id) is None


def test_audit_crud(db_session):
    user = crud.create_user(db_session, email="auditcrud@test.com", username="auditcrud")
    site = crud.create_website(db_session, user_id=user.id, url="https://auditsite.com", domain="auditsite.com")

    audit1 = crud.create_audit(
        db=db_session,
        website_id=site.id,
        user_id=user.id,
        score=88,
        title="Audit Title",
        meta_description="Meta Desc",
        h1_tags=["Main Heading"],
        canonical_url="https://auditsite.com",
        images_count=5,
        images_without_alt=1,
        broken_links_count=0
    )

    assert audit1.id is not None
    assert audit1.score == 88

    # get_audit_by_id_unfiltered
    assert crud.get_audit_by_id_unfiltered(db_session, audit1.id) is not None
    assert crud.get_audit_by_id_unfiltered(db_session, 999999) is None

    # get_user_audits_for_website
    audits = crud.get_user_audits_for_website(db_session, website_id=site.id, user_id=user.id, sort_by="score", order="asc")
    assert len(audits) == 1
    assert audits[0].id == audit1.id


def test_lead_and_report_crud(db_session):
    user = crud.create_user(db_session, email="leadrep@test.com", username="leadrep")
    site = crud.create_website(db_session, user_id=user.id, url="https://leadrep.com", domain="leadrep.com")

    # Lead CRUD
    lead = crud.create_lead(db_session, website_id=site.id, user_id=user.id, email="lead@client.com", source="popup")
    assert lead.id is not None

    leads = crud.get_user_leads_for_website(db_session, website_id=site.id, user_id=user.id, source="popup")
    assert len(leads) == 1
    assert leads[0].email == "lead@client.com"

    # Report CRUD
    report = crud.create_report(db_session, website_id=site.id, user_id=user.id, title="SEO Monthly Report", format="pdf")
    assert report.id is not None

    reports = crud.get_user_reports_for_website(db_session, website_id=site.id, user_id=user.id, format="pdf")
    assert len(reports) == 1
    assert reports[0].title == "SEO Monthly Report"


def test_job_crud_advanced(db_session):
    user = crud.create_user(db_session, email="jobcrud@test.com", username="jobcrud")

    job = crud.create_job(db_session, user_id=user.id, job_type="crawl")
    assert job.id is not None

    # get_job_by_id_unfiltered
    assert crud.get_job_by_id_unfiltered(db_session, job.id) is not None

    # get_user_job_by_id
    assert crud.get_user_job_by_id(db_session, job.id, user.id) is not None

    # get_user_jobs with status filter
    running_job = crud.create_job(db_session, user_id=user.id, job_type="audit")
    crud.update_job(db_session, running_job, status="running", progress=25)

    running_jobs = crud.get_user_jobs(db_session, user_id=user.id, status="running")
    assert len(running_jobs) == 1
    assert running_jobs[0].id == running_job.id

    # get_stale_jobs
    stale_job = crud.create_job(db_session, user_id=user.id, job_type="rank")
    stale_job.status = "running"
    stale_job.updated_at = datetime.utcnow() - timedelta(seconds=600)
    db_session.commit()

    stale_list = crud.get_stale_jobs(db_session, max_age_seconds=300)
    assert any(j.id == stale_job.id for j in stale_list)

    # delete_user_job
    assert crud.delete_user_job(db_session, job.id, user.id) is True
    assert crud.delete_user_job(db_session, job.id, user.id) is False
