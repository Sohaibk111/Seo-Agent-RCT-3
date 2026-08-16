import pytest
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import crud, models
from backend.database.pagination import (
    encode_cursor,
    decode_cursor,
    cursor_paginate,
    async_cursor_paginate
)

def test_cursor_encoding_decoding():
    """Test cursor encoder and decoder functions."""
    val = 12345
    encoded = encode_cursor(val)
    decoded = decode_cursor(encoded)
    assert decoded == "12345"

    with pytest.raises(ValueError):
        decode_cursor("invalid_base64_string!!!")


def test_selectinload_and_joinedload_eager_loading(db_session: Session):
    """Verify that get_user_with_relations and get_website_with_details eager load relationships."""
    user = crud.create_user(db_session, email="eager_test@example.com", username="eageruser")
    website = crud.create_website(db_session, user_id=user.id, url="https://eagertest.com", domain="eagertest.com")
    audit = crud.create_audit(
        db_session, website_id=website.id, user_id=user.id, score=90,
        title="Eager Test", meta_description="Eager desc", h1_tags=["H1"],
        canonical_url="https://eagertest.com", images_count=2, images_without_alt=0, broken_links_count=0
    )
    job = crud.create_job(db_session, user_id=user.id, job_type="audit", website_id=website.id)

    # Test get_user_with_relations
    fetched_user = crud.get_user_with_relations(db_session, user.id)
    assert fetched_user is not None
    assert len(fetched_user.websites) == 1
    assert len(fetched_user.jobs) == 1

    # Test get_website_with_details
    fetched_website = crud.get_website_with_details(db_session, website.id, user.id)
    assert fetched_website is not None
    assert fetched_website.owner.id == user.id
    assert len(fetched_website.audits) == 1
    assert len(fetched_website.jobs) == 1


def test_bulk_inserts_and_updates(db_session: Session):
    """Verify bulk insert and bulk update functions for high performance."""
    user = crud.create_user(db_session, email="bulk_test@example.com", username="bulkuser")
    website = crud.create_website(db_session, user_id=user.id, url="https://bulktest.com", domain="bulktest.com")

    # Bulk create keywords
    kw_items = [
        {"seed_keyword": "seo", "keyword": f"seo tool {i}", "volume": 100 * i, "kd": 10 + i, "cpc": "1.50"}
        for i in range(1, 6)
    ]
    created_kws = crud.bulk_create_keywords(db_session, user_id=user.id, items=kw_items)
    assert len(created_kws) == 5

    # Bulk create leads
    lead_items = [{"email": f"lead{i}@test.com", "source": "bulk"} for i in range(1, 4)]
    created_leads = crud.bulk_create_leads(db_session, user_id=user.id, website_id=website.id, items=lead_items)
    assert len(created_leads) == 3

    # Bulk create rank checks
    rank_items = [{"keyword": f"kw{i}", "domain": "bulktest.com", "position": i * 2} for i in range(1, 4)]
    created_ranks = crud.bulk_create_rank_checks(db_session, user_id=user.id, items=rank_items)
    assert len(created_ranks) == 3

    # Bulk update job status
    j1 = crud.create_job(db_session, user_id=user.id, job_type="audit", website_id=website.id)
    j2 = crud.create_job(db_session, user_id=user.id, job_type="crawl", website_id=website.id)
    updated_rows = crud.bulk_update_jobs_status(db_session, [j1.id, j2.id], status="completed", progress=100)
    assert updated_rows == 2

    db_session.refresh(j1)
    db_session.refresh(j2)
    assert j1.status == "completed"
    assert j1.progress == 100
    assert j2.status == "completed"


def test_cursor_based_pagination(db_session: Session):
    """Verify keyset/cursor-based pagination fetches items in ordered chunks with next_cursor."""
    user = crud.create_user(db_session, email="cursor_test@example.com", username="cursoruser")
    
    # Create 10 websites
    for i in range(1, 11):
        crud.create_website(db_session, user_id=user.id, url=f"https://site{i}.com", domain=f"site{i}.com")

    # First page with limit 4
    page1, next_cursor1, has_more1 = crud.get_user_websites_cursor(db_session, user_id=user.id, limit=4, order="desc")
    assert len(page1) == 4
    assert has_more1 is True
    assert next_cursor1 is not None

    # Second page using next_cursor1
    page2, next_cursor2, has_more2 = crud.get_user_websites_cursor(db_session, user_id=user.id, cursor=next_cursor1, limit=4, order="desc")
    assert len(page2) == 4
    assert has_more2 is True
    # Ensure no overlap between page 1 and page 2
    page1_ids = {w.id for w in page1}
    page2_ids = {w.id for w in page2}
    assert page1_ids.isdisjoint(page2_ids)

    # Third page (remaining 2 items)
    page3, next_cursor3, has_more3 = crud.get_user_websites_cursor(db_session, user_id=user.id, cursor=next_cursor2, limit=4, order="desc")
    assert len(page3) == 2
    assert has_more3 is False
    assert next_cursor3 is None


@pytest.mark.asyncio
async def test_async_bulk_and_cursor_pagination(async_db_session: AsyncSession):
    """Verify async implementations for bulk inserts and cursor pagination."""
    user = await crud.create_user_async(async_db_session, email="async_opt@example.com", username="asyncoptuser")
    
    # Async bulk create keywords
    kw_items = [
        {"seed_keyword": "async_seo", "keyword": f"async kw {i}", "volume": 50 * i, "kd": 5 + i, "cpc": "2.00"}
        for i in range(1, 6)
    ]
    created_kws = await crud.bulk_create_keywords_async(async_db_session, user_id=user.id, items=kw_items)
    assert len(created_kws) == 5

    # Async cursor pagination on websites
    for i in range(1, 6):
        await crud.create_website_async(async_db_session, user_id=user.id, url=f"https://asyncsite{i}.com", domain=f"asyncsite{i}.com")

    page1, cursor1, has_more1 = await crud.get_user_websites_cursor_async(async_db_session, user_id=user.id, limit=3, order="desc")
    assert len(page1) == 3
    assert has_more1 is True
    assert cursor1 is not None

    page2, cursor2, has_more2 = await crud.get_user_websites_cursor_async(async_db_session, user_id=user.id, cursor=cursor1, limit=3, order="desc")
    assert len(page2) == 2
    assert has_more2 is False
    assert cursor2 is None
