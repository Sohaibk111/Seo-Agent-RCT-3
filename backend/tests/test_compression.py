import pytest
import gzip
from fastapi import FastAPI
from fastapi.responses import Response, JSONResponse
from fastapi.testclient import TestClient
from backend.compression import setup_compression_middleware, HAS_BROTLI, AdvancedCompressionMiddleware
from backend.config import settings

try:
    import brotli
except ImportError:
    brotli = None


@pytest.fixture
def compression_app():
    """Creates a test FastAPI application with compression setup."""
    app = FastAPI()

    @app.get("/api/v1/large-json")
    def large_json():
        return {"data": "x" * 1500, "status": "ok", "items": list(range(100))}

    @app.get("/api/v1/small-json")
    def small_json():
        return {"status": "ok"}

    @app.get("/api/v1/reports/export")
    def report_export():
        csv_content = "header1,header2,header3\n" + "\n".join([f"val_{i},val_{i*2},val_{i*3}" for i in range(150)])
        return Response(content=csv_content, media_type="text/csv")

    setup_compression_middleware(app)
    return app


def test_gzip_compression_large_json(compression_app):
    """Verify GZip compression is applied when client sends Accept-Encoding: gzip."""
    client = TestClient(compression_app)
    response = client.get("/api/v1/large-json", headers={"Accept-Encoding": "gzip"})

    assert response.status_code == 200
    assert response.headers.get("Content-Encoding") == "gzip"
    # TestClient automatically decompresses body content when reading json()
    assert response.json()["status"] == "ok"
    assert len(response.json()["data"]) == 1500


def test_brotli_compression_large_json(compression_app):
    """Verify Brotli compression is applied when client sends Accept-Encoding: br (if Brotli available)."""
    client = TestClient(compression_app)
    response = client.get("/api/v1/large-json", headers={"Accept-Encoding": "gzip, br"})

    assert response.status_code == 200
    if HAS_BROTLI:
        assert response.headers.get("Content-Encoding") == "br"
    else:
        assert response.headers.get("Content-Encoding") == "gzip"

    assert response.json()["status"] == "ok"


def test_compression_threshold_ignores_small_payloads(compression_app):
    """Verify responses smaller than 500 bytes threshold are not compressed."""
    client = TestClient(compression_app)
    response = client.get("/api/v1/small-json", headers={"Accept-Encoding": "gzip, br"})

    assert response.status_code == 200
    assert "Content-Encoding" not in response.headers
    assert response.json() == {"status": "ok"}


def test_reports_and_exports_compression(compression_app):
    """Verify reports and export responses get compressed."""
    client = TestClient(compression_app)
    response = client.get("/api/v1/reports/export", headers={"Accept-Encoding": "br, gzip"})

    assert response.status_code == 200
    expected_encoding = "br" if HAS_BROTLI else "gzip"
    assert response.headers.get("Content-Encoding") == expected_encoding
    assert "header1,header2,header3" in response.text


def test_compression_disabled_setting(monkeypatch):
    """Verify compression is bypassed when COMPRESSION_ENABLED is False."""
    monkeypatch.setattr(settings, "COMPRESSION_ENABLED", False)

    app = FastAPI()
    @app.get("/large")
    def large():
        return {"data": "y" * 2000}

    setup_compression_middleware(app)
    client = TestClient(app)

    response = client.get("/large", headers={"Accept-Encoding": "gzip, br"})
    assert response.status_code == 200
    assert "Content-Encoding" not in response.headers


def test_brotli_fallback_to_gzip_when_brotli_not_installed(monkeypatch):
    """Verify fallback to gzip when HAS_BROTLI is False."""
    import backend.compression as comp_module
    monkeypatch.setattr(comp_module, "HAS_BROTLI", False)

    app = FastAPI()
    @app.get("/large")
    def large():
        return {"data": "z" * 2000}

    setup_compression_middleware(app)
    client = TestClient(app)

    response = client.get("/large", headers={"Accept-Encoding": "br, gzip"})
    assert response.status_code == 200
    assert response.headers.get("Content-Encoding") == "gzip"
