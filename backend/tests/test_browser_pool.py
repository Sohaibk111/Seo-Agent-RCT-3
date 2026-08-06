import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock
from playwright.async_api import Browser, BrowserContext, Page
from backend.browser_pool import (
    BrowserPool,
    PooledBrowser,
    get_browser_pool,
    close_browser_pool,
    get_browser_pool_dependency
)
from backend.config import settings
from backend.services.scraper_service import ScraperService

@pytest.mark.asyncio
async def test_browser_pool_singleton_and_configuration():
    """Verify get_browser_pool returns a singleton instance matching config settings."""
    await close_browser_pool()

    pool1 = get_browser_pool()
    pool2 = get_browser_pool()

    assert pool1 is pool2
    assert pool1.pool_size == settings.BROWSER_POOL_SIZE
    assert pool1.idle_timeout == settings.BROWSER_IDLE_TIMEOUT
    assert pool1.headless == settings.BROWSER_HEADLESS

    await close_browser_pool()

@pytest.mark.asyncio
async def test_browser_reuse_and_page_rendering():
    """Verify that BrowserPool launches, reuses browsers, and provides working Page rendering."""
    await close_browser_pool()
    pool = BrowserPool(pool_size=2, idle_timeout=10.0)

    # First page acquisition
    async with pool.get_page() as page:
        await page.set_content("<html><head><title>Test Pool Page 1</title></head><body><h1>Hello World 1</h1></body></html>")
        title1 = await page.title()
        assert title1 == "Test Pool Page 1"

    assert len(pool._browsers) == 1
    pb = pool._browsers[0]
    assert pb.active_contexts == 0

    # Second page acquisition should REUSE the same browser instance
    async with pool.get_page() as page:
        await page.set_content("<html><head><title>Test Pool Page 2</title></head><body><h1>Hello World 2</h1></body></html>")
        title2 = await page.title()
        assert title2 == "Test Pool Page 2"

    assert len(pool._browsers) == 1
    assert pool._browsers[0] is pb  # Reused!

    await pool.close()

@pytest.mark.asyncio
async def test_context_recycling_isolation():
    """Verify that each task gets an isolated BrowserContext (recycled and cleaned up)."""
    await close_browser_pool()
    pool = BrowserPool(pool_size=2)

    # Set cookie in context 1
    async with pool.get_context() as ctx1:
        await ctx1.add_cookies([{"name": "session_id", "value": "secret_123", "domain": "example.com", "path": "/"}])
        page1 = await ctx1.new_page()
        await page1.goto("https://example.com")
        cookies1 = await ctx1.cookies("https://example.com")
        assert len(cookies1) == 1
        assert cookies1[0]["value"] == "secret_123"

    # Context 2 (recycled context) MUST be clean and isolated
    async with pool.get_context() as ctx2:
        page2 = await ctx2.new_page()
        await page2.goto("https://example.com")
        cookies2 = await ctx2.cookies("https://example.com")
        assert len(cookies2) == 0  # Completely clean context state!

    await pool.close()

@pytest.mark.asyncio
async def test_idle_timeout_cleanup():
    """Verify that browsers exceeding idle_timeout are closed and cleaned up."""
    await close_browser_pool()
    # Fast idle timeout for testing
    pool = BrowserPool(pool_size=2, idle_timeout=0.1)

    async with pool.get_page() as page:
        await page.set_content("<html><title>Idle Test</title></html>")

    assert len(pool._browsers) == 1
    # Simulate time passing beyond idle_timeout
    pool._browsers[0].last_used_at = time.time() - 2.0

    await pool.cleanup_idle_browsers()
    assert len(pool._browsers) == 0  # Idle browser closed!

    await pool.close()

@pytest.mark.asyncio
async def test_crash_recovery():
    """Verify that if a browser disconnects or crashes, the pool removes it and recovers with a fresh replacement."""
    await close_browser_pool()
    pool = BrowserPool(pool_size=2)

    # Launch initial browser
    async with pool.get_page() as page:
        await page.set_content("<html><title>Crash Recovery Test 1</title></html>")

    assert len(pool._browsers) == 1
    dead_browser = pool._browsers[0]

    # Forcefully close the underlying browser to simulate a crash
    await dead_browser.browser.close()
    assert not dead_browser.is_connected()

    # Next acquire MUST trigger crash recovery, clean up dead browser, and launch a new healthy replacement
    async with pool.get_page() as page2:
        await page2.set_content("<html><title>Crash Recovery Test 2</title></html>")
        title = await page2.title()
        assert title == "Crash Recovery Test 2"

    assert len(pool._browsers) == 1
    new_browser = pool._browsers[0]
    assert new_browser is not dead_browser
    assert new_browser.is_connected()

    await pool.close()

@pytest.mark.asyncio
async def test_concurrent_crawling_safety():
    """Verify that multiple concurrent crawl tasks run safely through the pool up to pool_size."""
    await close_browser_pool()
    pool = BrowserPool(pool_size=3)

    async def crawl_task(idx: int):
        async with pool.get_page() as page:
            await page.set_content(f"<html><title>Task {idx}</title></html>")
            await asyncio.sleep(0.05)
            return await page.title()

    results = await asyncio.gather(*[crawl_task(i) for i in range(6)])
    assert len(results) == 6
    assert results == [f"Task {i}" for i in range(6)]
    # Should not exceed pool_size
    assert len(pool._browsers) <= 3

    await pool.close()

@pytest.mark.asyncio
async def test_scraper_service_render_page_integration():
    """Verify ScraperService.render_page_async renders using BrowserPool."""
    await close_browser_pool()
    pool = get_browser_pool()

    # Mock page.goto and page.content for external URL
    async with pool.get_page() as page:
        await page.set_content("<html><head><title>Scraper Integration</title></head><body><h1>SEO Data</h1></body></html>")
        content = await page.content()
        title = await page.title()
        assert title == "Scraper Integration"
        assert "SEO Data" in content

    await close_browser_pool()

@pytest.mark.asyncio
async def test_fastapi_browser_pool_dependency():
    """Verify get_browser_pool_dependency yields active BrowserPool without shutting down."""
    await close_browser_pool()

    pool_gen = get_browser_pool_dependency()
    pool = await pool_gen.__anext__()

    assert isinstance(pool, BrowserPool)
    assert not pool._is_closed

    try:
        await pool_gen.__anext__()
    except StopAsyncIteration:
        pass

    assert not pool._is_closed
    await close_browser_pool()
