from fastapi.testclient import TestClient
from backend.database import crud

def test_websites_pagination_and_sorting(client: TestClient, db_session):
    user = crud.create_user(db_session, email="pagiuser@test.com", username="pagiuser")
    token = "Bearer token_user_1"  # Uses mock auth override in conftest.py

    # Seed 5 websites
    for i in range(5):
        crud.create_website(db_session, user_id=1, url=f"https://site{i}.com", domain=f"site{i}.com", company_name=f"Company {i}")

    # Test limit and skip
    res = client.get("/api/v1/websites?skip=0&limit=3", headers={"Authorization": token})
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 3

    res_page2 = client.get("/api/v1/websites?skip=3&limit=3", headers={"Authorization": token})
    assert res_page2.status_code == 200
    data_page2 = res_page2.json()
    assert len(data_page2) >= 2

    # Test search filter
    res_search = client.get("/api/v1/websites?search=site2", headers={"Authorization": token})
    assert res_search.status_code == 200
    assert len(res_search.json()) == 1
    assert res_search.json()[0]["domain"] == "site2.com"

    # Test sorting
    res_sort = client.get("/api/v1/websites?sort_by=domain&order=desc", headers={"Authorization": token})
    assert res_sort.status_code == 200
    domains = [w["domain"] for w in res_sort.json()]
    assert domains == sorted(domains, reverse=True)


def test_jobs_pagination_and_filtering(client: TestClient):
    token = "Bearer token_user_1"

    # Create 3 jobs
    client.post("/api/v1/jobs/crawl", headers={"Authorization": token}, json={"url": "https://testpagi1.com"})
    client.post("/api/v1/jobs/audit", headers={"Authorization": token}, json={"url": "https://testpagi2.com"})
    client.post("/api/v1/jobs/keywords", headers={"Authorization": token}, json={"seed_keyword": "pagi kw"})

    # Filter by job_type
    res = client.get("/api/v1/jobs?job_type=crawl", headers={"Authorization": token})
    assert res.status_code == 200
    assert all(j["job_type"] == "crawl" for j in res.json())

    # Test limit & offset
    res_limit = client.get("/api/v1/jobs?limit=2&skip=0", headers={"Authorization": token})
    assert res_limit.status_code == 200
    assert len(res_limit.json()) == 2
