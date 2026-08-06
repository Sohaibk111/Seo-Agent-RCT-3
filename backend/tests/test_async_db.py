import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text
from backend.database.database import (
    get_async_database_url,
    get_async_db,
    async_session_scope,
    Base
)
from backend.database import crud
from backend.database.models import User, Website, AuditResult, Lead, Report, Job
from backend.database.pagination import async_paginate, get_async_paginated_response

@pytest.fixture
def async_test_url():
    return get_async_database_url("sqlite:///:memory:")

@pytest_asyncio.fixture
async def async_test_engine(async_test_url):
    engine = create_async_engine(async_test_url, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def async_db_session(async_test_engine):
    session_factory = async_sessionmaker(
        bind=async_test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    async with session_factory() as session:
        yield session

def test_async_database_url_translation():
    assert get_async_database_url("sqlite:///./seo_agent.db") == "sqlite+aiosqlite:///./seo_agent.db"
    assert get_async_database_url("postgresql://user:pass@localhost:5432/dbname") == "postgresql+asyncpg://user:pass@localhost:5432/dbname"
    assert get_async_database_url("postgres://user:pass@localhost:5432/dbname") == "postgresql+asyncpg://user:pass@localhost:5432/dbname"
    assert get_async_database_url("") == "sqlite+aiosqlite:///:memory:"

@pytest.mark.asyncio
async def test_async_session_connectivity(async_db_session: AsyncSession):
    result = await async_db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1

@pytest.mark.asyncio
async def test_async_user_crud(async_db_session: AsyncSession):
    # 1. Create User
    user = await crud.create_user_async(
        async_db_session,
        email="async_user@example.com",
        username="asyncuser",
        hashed_password="secret_hash"
    )
    assert user.id is not None
    assert user.email == "async_user@example.com"

    # 2. Get User by Email
    fetched_email = await crud.get_user_by_email_async(async_db_session, "async_user@example.com")
    assert fetched_email is not None
    assert fetched_email.id == user.id

    # 3. Get User by ID
    fetched_id = await crud.get_user_async(async_db_session, user.id)
    assert fetched_id is not None
    assert fetched_id.email == "async_user@example.com"

@pytest.mark.asyncio
async def test_async_website_and_tenant_isolation(async_db_session: AsyncSession):
    u1 = await crud.create_user_async(async_db_session, email="u1@example.com", username="u1")
    u2 = await crud.create_user_async(async_db_session, email="u2@example.com", username="u2")

    w1 = await crud.create_website_async(
        async_db_session,
        user_id=u1.id,
        url="https://site1.com",
        domain="site1.com",
        company_name="Company One"
    )
    assert w1.id is not None

    # u1 can access w1
    found_u1 = await crud.get_website_by_id_async(async_db_session, website_id=w1.id, user_id=u1.id)
    assert found_u1 is not None

    # u2 CANNOT access w1 (strict tenant isolation)
    found_u2 = await crud.get_website_by_id_async(async_db_session, website_id=w1.id, user_id=u2.id)
    assert found_u2 is None

    # List websites for u1
    websites_u1 = await crud.get_user_websites_async(async_db_session, user_id=u1.id)
    assert len(websites_u1) == 1

    # List websites for u2
    websites_u2 = await crud.get_user_websites_async(async_db_session, user_id=u2.id)
    assert len(websites_u2) == 0

@pytest.mark.asyncio
async def test_async_job_lifecycle(async_db_session: AsyncSession):
    u = await crud.create_user_async(async_db_session, email="job_user@example.com", username="jobuser")
    job = await crud.create_job_async(
        async_db_session,
        user_id=u.id,
        job_type="crawl",
        result_reference={"url": "https://example.com"}
    )
    assert job.id is not None
    assert job.status == "pending"

    # Update job
    updated_job = await crud.update_job_async(
        async_db_session,
        job=job,
        status="running",
        progress=50
    )
    assert updated_job.status == "running"
    assert updated_job.progress == 50

    # Fetch job by user
    fetched_job = await crud.get_user_job_by_id_async(async_db_session, job_id=job.id, user_id=u.id)
    assert fetched_job is not None
    assert fetched_job.status == "running"

@pytest.mark.asyncio
async def test_async_pagination_helper(async_db_session: AsyncSession):
    u = await crud.create_user_async(async_db_session, email="page_user@example.com", username="pageuser")
    for i in range(15):
        await crud.create_website_async(
            async_db_session,
            user_id=u.id,
            url=f"https://page{i}.com",
            domain=f"page{i}.com"
        )

    stmt = select(Website).where(Website.user_id == u.id)
    paged_res = await get_async_paginated_response(async_db_session, stmt, skip=0, limit=5)
    assert paged_res["total"] == 15
    assert len(paged_res["items"]) == 5
    assert paged_res["pages"] == 3
