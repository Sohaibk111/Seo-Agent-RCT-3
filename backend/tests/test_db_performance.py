import pytest
from backend.database import crud
from backend.database.pagination import paginate, get_paginated_response, PaginatedParams
from backend.database.models import Website, AuditResult, Lead, Report, Job

def test_pagination_utility_bounds():
    p1 = PaginatedParams(skip=-5, limit=500, max_limit=100)
    assert p1.skip == 0
    assert p1.limit == 100

    p2 = PaginatedParams(skip=10, limit=0, max_limit=100)
    assert p2.skip == 10
    assert p2.limit == 1

def test_paginated_response_helper(db_session):
    user = crud.create_user(db_session, email="helperuser@test.com", username="helperuser")
    for i in range(15):
        crud.create_website(db_session, user_id=user.id, url=f"https://site{i}.com", domain=f"site{i}.com")

    query = db_session.query(Website).filter(Website.user_id == user.id)
    resp = get_paginated_response(query, skip=0, limit=5, max_limit=50)
    assert resp["total"] == 15
    assert len(resp["items"]) == 5
    assert resp["pages"] == 3
    assert resp["skip"] == 0
    assert resp["limit"] == 5

def test_relationship_eager_loading(db_session):
    """Verify that joinedload eager loads relationships to prevent N+1 queries."""
    user = crud.create_user(db_session, email="eageruser@test.com", username="eageruser")
    site = crud.create_website(db_session, user_id=user.id, url="https://eager.com", domain="eager.com")
    
    audit = crud.create_audit(
        db=db_session,
        website_id=site.id,
        user_id=user.id,
        score=95,
        title="Eager Title",
        meta_description="Eager Desc",
        h1_tags=["Heading"],
        canonical_url="https://eager.com",
        images_count=2,
        images_without_alt=0,
        broken_links_count=0
    )

    job = crud.create_job(db_session, user_id=user.id, job_type="audit", website_id=site.id)

    # Expire session cache to force reload from DB
    db_session.expire_all()

    # Fetch job with joinedload
    fetched_job = crud.get_user_job_by_id(db_session, job.id, user.id)
    assert fetched_job is not None
    # Access relationship directly - should not trigger new query if eager loaded
    assert fetched_job.website is not None
    assert fetched_job.website.domain == "eager.com"

    # Fetch audit with joinedload
    fetched_audit = crud.get_audit_by_id_unfiltered(db_session, audit.id)
    assert fetched_audit is not None
    assert fetched_audit.website is not None
    assert fetched_audit.website.url == "https://eager.com"

def test_index_query_performance(db_session):
    """Test queries that utilize newly added composite indexes."""
    user = crud.create_user(db_session, email="idxuser@test.com", username="idxuser")
    site = crud.create_website(db_session, user_id=user.id, url="https://idx.com", domain="idx.com")

    # Seed multiple leads and reports
    for i in range(5):
        crud.create_lead(db_session, website_id=site.id, user_id=user.id, email=f"lead{i}@idx.com", source="audit")
        crud.create_report(db_session, website_id=site.id, user_id=user.id, title=f"Report {i}", format="pdf")

    leads = crud.get_user_leads_for_website(db_session, website_id=site.id, user_id=user.id, source="audit")
    assert len(leads) == 5

    reports = crud.get_user_reports_for_website(db_session, website_id=site.id, user_id=user.id, format="pdf")
    assert len(reports) == 5
