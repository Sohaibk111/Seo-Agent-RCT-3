from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from backend.services.ai_service import AIService
from backend.services.metrics_service import MetricsService
from backend.services.export_service import ExportService
from backend.services.scraper_service import ScraperService
from backend.services.keyword_service import KeywordService
from backend.services.rank_service import RankService
from backend.exceptions import ResourceNotFoundException, ValidationErrorException
from backend.database import crud

def test_keyword_service(client: TestClient):
    token = "Bearer token_user_1"
    res = client.post(
        "/api/v1/keywords",
        headers={"Authorization": token},
        json={"seed_keyword": "seo automation", "limit": 5}
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 5
    assert data[0]["kw"] == "seo automation"


def test_rank_service(client: TestClient):
    token = "Bearer token_user_1"
    res = client.post(
        "/api/v1/rank/check",
        headers={"Authorization": token},
        json={"keyword": "best seo tool", "domain": "techflow-seo.com"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["keyword"] == "best seo tool"
    assert "position" in data


def test_ai_service(db_session):
    user = crud.create_user(db_session, email="aiuser@test.com", username="aiuser")
    website = crud.create_website(db_session, user_id=user.id, url="https://aitest.com", domain="aitest.com")
    audit = crud.create_audit(
        db=db_session, website_id=website.id, user_id=user.id, score=85,
        title="AI Test", meta_description="Desc", h1_tags=["H1"], canonical_url="https://aitest.com",
        images_count=2, images_without_alt=0, broken_links_count=0
    )

    res = AIService.analyze_audit(audit_id=audit.id, user_id=user.id, db=db_session)
    assert res["provider"] == "gemini-3.6-flash"
    assert "scores 85/100" in res["summary"]
    assert len(res["recommendations"]) == 3

    # Error handling for non-existent audit
    with pytest.raises(ResourceNotFoundException):
        AIService.analyze_audit(audit_id=99999, user_id=user.id, db=db_session)


def test_metrics_service(db_session):
    user = crud.create_user(db_session, email="metricsuser@test.com", username="metricsuser")
    website = crud.create_website(db_session, user_id=user.id, url="https://metricstest.com", domain="metricstest.com")

    res = MetricsService.get_domain_metrics(domain="metricstest.com", user_id=user.id, db=db_session)
    assert res["domain"] == "metricstest.com"
    assert res["provider"] == "whois_free"
    assert res["domain_authority"] == 54

    # Test error handling when neither domain nor website_id provided
    with pytest.raises(ValidationErrorException):
        MetricsService.get_domain_metrics(domain=None, website_id=None, user_id=user.id, db=db_session)


def test_export_service(db_session):
    import os
    user = crud.create_user(db_session, email="exportuser@test.com", username="exportuser")
    website = crud.create_website(db_session, user_id=user.id, url="https://exporttest.com", domain="exporttest.com")
    crud.create_audit(db_session, website_id=website.id, user_id=user.id, score=90, title="Export Test Audit")

    for fmt in ["pdf", "csv", "json", "html"]:
        export_res = ExportService.export_report(website_id=website.id, user_id=user.id, format=fmt, db=db_session)
        assert export_res["format"] == fmt
        assert export_res["status"] == "exported"
        assert export_res["website_id"] == website.id

    # Test CSV streaming generator
    chunks = list(ExportService.stream_csv_audits(website_id=website.id, user_id=user.id, db=db_session))
    csv_text = "".join(chunks)
    assert "Audit ID,Website ID,Domain,Score" in csv_text
    assert "exporttest.com" in csv_text

    # Test Google Sheets payload generator
    sheets_payload = ExportService.generate_sheets_payload(website_id=website.id, user_id=user.id, db=db_session)
    assert sheets_payload["domain"] == "exporttest.com"
    assert sheets_payload["totalRows"] >= 2
    assert sheets_payload["values"][0] == ["Audit ID", "Score", "Title Length", "Images Without Alt", "Created At"]

    # Test temporary file creation and cleanup
    temp_path = ExportService.create_temp_report_file(website_id=website.id, user_id=user.id, format="pdf", db=db_session)
    assert os.path.exists(temp_path)
    ExportService.cleanup_temp_file(temp_path)
    assert not os.path.exists(temp_path)

    # Error handling for invalid website_id
    with pytest.raises(ResourceNotFoundException):
        ExportService.export_report(website_id=99999, user_id=user.id, format="pdf", db=db_session)


def test_mocked_network_and_browser_scraping(db_session):
    user = crud.create_user(db_session, email="scrapeuser@test.com", username="scrapeuser")
    
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><head><title>Mocked Page</title></head><body><h1>Hello</h1><a href='mailto:info@scrape.com'>Email Us</a></body></html>"
        mock_get.return_value = mock_response

        res = ScraperService.audit_website(url="https://mockedtarget.com", user_id=user.id, db=db_session)
        assert res["website"].domain == "mockedtarget.com"
        assert res["audit"].score >= 70
        assert res["leads_found"] >= 0

    # Test ScraperService error when neither url nor website_id provided
    with pytest.raises(ValidationErrorException):
        ScraperService.audit_website(url=None, website_id=None, user_id=user.id, db=db_session)
