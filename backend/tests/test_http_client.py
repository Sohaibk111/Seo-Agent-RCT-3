import pytest
import httpx
from unittest.mock import patch, AsyncMock, MagicMock
from backend.http_client import (
    HTTPClientManager,
    get_http_client,
    close_http_client,
    get_async_client_dependency
)
from backend.config import settings
from backend.services.scraper_service import ScraperService

@pytest.mark.asyncio
async def test_global_http_client_singleton_and_reuse():
    """Verify that get_http_client returns the exact same httpx.AsyncClient instance across calls."""
    await close_http_client()
    
    client1 = get_http_client()
    client2 = get_http_client()
    
    assert isinstance(client1, httpx.AsyncClient)
    assert client1 is client2
    assert not client1.is_closed
    
    await close_http_client()

@pytest.mark.asyncio
async def test_http_client_pool_and_timeout_configurations():
    """Verify connection pool limits, timeouts, keep-alive, and retry transport settings."""
    await close_http_client()
    
    client = get_http_client()
    
    # Verify Timeouts
    assert client.timeout.connect == settings.HTTP_TIMEOUT_CONNECT
    assert client.timeout.read == settings.HTTP_TIMEOUT_READ
    assert client.timeout.write == settings.HTTP_TIMEOUT_WRITE
    assert client.timeout.pool == settings.HTTP_TIMEOUT_POOL
    
    # Verify Transport & Pool Limits
    transport = client._transport
    assert isinstance(transport, httpx.AsyncHTTPTransport)
    assert transport._pool._max_connections == settings.HTTP_MAX_CONNECTIONS
    
    await close_http_client()

@pytest.mark.asyncio
async def test_http_client_graceful_shutdown_and_reinit():
    """Verify that close_http_client properly closes the client and get_http_client can reinitialize it."""
    await close_http_client()
    
    client1 = get_http_client()
    assert not client1.is_closed
    
    await close_http_client()
    assert client1.is_closed
    
    client2 = get_http_client()
    assert not client2.is_closed
    assert client1 is not client2
    
    await close_http_client()

@pytest.mark.asyncio
async def test_fastapi_dependency_get_async_client_dependency():
    """Verify that get_async_client_dependency yields the global client without closing it upon generator completion."""
    await close_http_client()
    
    client_gen = get_async_client_dependency()
    client = await client_gen.__anext__()
    
    assert isinstance(client, httpx.AsyncClient)
    assert not client.is_closed
    assert client is get_http_client()
    
    # Finishing the dependency generator shouldn't close the global client
    try:
        await client_gen.__anext__()
    except StopAsyncIteration:
        pass
    
    assert not client.is_closed
    await close_http_client()

@pytest.mark.asyncio
async def test_scraper_service_fetch_with_global_http_client():
    """Verify that ScraperService uses the global HTTP client pool for async page fetches."""
    await close_http_client()
    global_client = get_http_client()
    
    mock_response = httpx.Response(
        status_code=200,
        content=b"<html><title>Pooled Test</title></html>",
        headers={"content-type": "text/html"},
        request=httpx.Request("GET", "https://example.com/test")
    )
    
    with patch.object(global_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        
        result = await ScraperService.fetch_page_content_async("https://example.com/test")
        
        mock_get.assert_called_once_with("https://example.com/test")
        assert result["status_code"] == 200
        assert "Pooled Test" in result["text"]
        assert result["url"] == "https://example.com/test"
        
    await close_http_client()
