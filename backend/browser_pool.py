import asyncio
import time
from typing import Optional, List, Dict, Any, AsyncGenerator
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page
from backend.config import settings
from backend.logging_config import logger

class PooledBrowser:
    """Wrapper around Playwright Browser tracking metadata for reuse, idle timeout, and health checks."""
    def __init__(self, browser: Browser, browser_id: int):
        self.browser: Browser = browser
        self.id: int = browser_id
        self.created_at: float = time.time()
        self.last_used_at: float = time.time()
        self.active_contexts: int = 0
        self.is_healthy: bool = True

    def mark_used(self) -> None:
        """Updates the last used timestamp."""
        self.last_used_at = time.time()

    def is_idle(self, timeout_seconds: float) -> bool:
        """Returns True if the browser has no active contexts and has exceeded the idle timeout."""
        return self.active_contexts == 0 and (time.time() - self.last_used_at) > timeout_seconds

    def is_connected(self) -> bool:
        """Checks if the browser is healthy and still connected to Playwright."""
        try:
            return self.is_healthy and self.browser.is_connected()
        except Exception:
            return False

    async def close(self) -> None:
        """Closes the underlying Playwright Browser instance safely."""
        self.is_healthy = False
        try:
            if self.browser.is_connected():
                await self.browser.close()
        except Exception as e:
            logger.warning(f"Error closing pooled browser #{self.id}: {e}")

class BrowserPool:
    """
    Manages a pool of Playwright Browser instances to support concurrent crawling safely.
    Features:
    - Configurable pool size
    - Idle timeout browser cleanup
    - Browser reuse across tasks
    - Context recycling for clean isolated sessions
    - Automatic cleanup on shutdown
    - Crash recovery for disconnected/crashed browsers
    """
    def __init__(
        self,
        pool_size: Optional[int] = None,
        idle_timeout: Optional[float] = None,
        headless: Optional[bool] = None,
        page_timeout_ms: Optional[int] = None
    ):
        self.pool_size = pool_size if pool_size is not None else getattr(settings, "BROWSER_POOL_SIZE", 5)
        self.idle_timeout = idle_timeout if idle_timeout is not None else getattr(settings, "BROWSER_IDLE_TIMEOUT", 60.0)
        self.headless = headless if headless is not None else getattr(settings, "BROWSER_HEADLESS", True)
        self.page_timeout_ms = page_timeout_ms if page_timeout_ms is not None else getattr(settings, "BROWSER_PAGE_TIMEOUT_MS", 30000)

        self._playwright: Optional[Playwright] = None
        self._browsers: List[PooledBrowser] = []
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._lock = asyncio.Lock()
        self._counter = 0
        self._is_closed = False
        self._cleanup_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initializes the Playwright driver, concurrency semaphore, and periodic cleanup task."""
        async with self._lock:
            if self._playwright is None and not self._is_closed:
                self._playwright = await async_playwright().start()
                self._semaphore = asyncio.Semaphore(self.pool_size)
                self._is_closed = False
                self._cleanup_task = asyncio.create_task(self._periodic_idle_cleanup())
                logger.info(f"Initialized BrowserPool (pool_size={self.pool_size}, idle_timeout={self.idle_timeout}s)")

    async def _launch_pooled_browser(self) -> PooledBrowser:
        """Launches a new underlying Playwright Browser instance."""
        if not self._playwright:
            raise RuntimeError("BrowserPool is not initialized or has been closed.")

        self._counter += 1
        browser_id = self._counter
        browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        pooled = PooledBrowser(browser, browser_id)
        self._browsers.append(pooled)
        logger.info(f"Launched new pooled browser #{browser_id}. Total active browsers: {len(self._browsers)}")
        return pooled

    async def acquire_browser(self) -> PooledBrowser:
        """
        Retrieves an available healthy PooledBrowser or launches a new instance.
        Includes crash recovery to replace disconnected/crashed browser instances.
        """
        if self._is_closed:
            raise RuntimeError("BrowserPool is closed.")

        if self._playwright is None:
            await self.initialize()

        async with self._lock:
            # 1. Clean up dead or disconnected browsers (Crash Recovery)
            healthy_browsers: List[PooledBrowser] = []
            for pb in self._browsers:
                if pb.is_connected():
                    healthy_browsers.append(pb)
                else:
                    logger.warning(f"Browser #{pb.id} disconnected or crashed. Performing crash recovery cleanup.")
                    await pb.close()
            self._browsers = healthy_browsers

            # 2. Pick an existing browser with the lowest number of active contexts
            best_browser: Optional[PooledBrowser] = None
            if self._browsers:
                self._browsers.sort(key=lambda b: b.active_contexts)
                best_browser = self._browsers[0]

            # 3. If no browser exists or if existing browser has active load and pool isn't full, launch a new browser
            if best_browser is None or (len(self._browsers) < self.pool_size and best_browser.active_contexts > 0):
                best_browser = await self._launch_pooled_browser()

            best_browser.active_contexts += 1
            best_browser.mark_used()
            return best_browser

    async def release_browser(self, pooled: PooledBrowser) -> None:
        """Decrements context load and updates last used timestamp."""
        async with self._lock:
            pooled.active_contexts = max(0, pooled.active_contexts - 1)
            pooled.mark_used()

    @asynccontextmanager
    async def get_context(
        self,
        viewport: Optional[Dict[str, int]] = None,
        user_agent: Optional[str] = None,
        block_resources: bool = False
    ) -> AsyncGenerator[BrowserContext, None]:
        """
        Context manager yielding an isolated BrowserContext.
        Enforces concurrency limit via semaphore, performs context recycling on exit.
        If block_resources=True, blocks images, stylesheets, fonts, and media for memory optimization.
        """
        if self._semaphore is None:
            await self.initialize()

        assert self._semaphore is not None
        async with self._semaphore:
            pooled = await self.acquire_browser()
            context: Optional[BrowserContext] = None
            try:
                viewport_opts = viewport or {"width": 1280, "height": 800}
                ua_opts = user_agent or "SEO-Agent-Bot/1.0 (Playwright Pool)"

                context = await pooled.browser.new_context(
                    viewport=viewport_opts,
                    user_agent=ua_opts,
                    ignore_https_errors=True
                )
                context.set_default_timeout(self.page_timeout_ms)
                
                if block_resources:
                    async def route_handler(route):
                        req = route.request
                        if req.resource_type in ["image", "media", "font", "stylesheet"]:
                            await route.abort()
                        else:
                            await route.continue_()
                    await context.route("**/*", route_handler)

                yield context
            except Exception as exc:
                logger.error(f"Error during browser context execution: {exc}")
                pooled.is_healthy = False  # Mark for crash recovery cleanup
                raise
            finally:
                if context:
                    try:
                        await context.close()  # Recycles context (clears cookies, storage, cache)
                    except Exception as c_err:
                        logger.warning(f"Error closing recycled browser context: {c_err}")
                await self.release_browser(pooled)

    @asynccontextmanager
    async def get_page(
        self,
        viewport: Optional[Dict[str, int]] = None,
        user_agent: Optional[str] = None,
        block_resources: bool = False
    ) -> AsyncGenerator[Page, None]:
        """
        Convenience context manager yielding a fresh Page within a recycled BrowserContext.
        """
        async with self.get_context(viewport=viewport, user_agent=user_agent, block_resources=block_resources) as context:
            page = await context.new_page()
            try:
                yield page
            finally:
                try:
                    await page.close()
                except Exception as p_err:
                    logger.warning(f"Error closing browser page: {p_err}")


    async def cleanup_idle_browsers(self) -> None:
        """Closes browsers that have been idle longer than idle_timeout."""
        async with self._lock:
            remaining: List[PooledBrowser] = []
            for pb in self._browsers:
                if pb.is_idle(self.idle_timeout):
                    logger.info(f"Closing idle browser #{pb.id} (idle > {self.idle_timeout}s)")
                    await pb.close()
                elif not pb.is_connected():
                    logger.info(f"Removing disconnected browser #{pb.id}")
                    await pb.close()
                else:
                    remaining.append(pb)
            self._browsers = remaining

    async def _periodic_idle_cleanup(self) -> None:
        """Background task running idle browser cleanup periodically."""
        while not self._is_closed:
            try:
                await asyncio.sleep(15.0)
                if not self._is_closed:
                    await self.cleanup_idle_browsers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Error in browser pool idle cleanup loop: {e}")

    async def close(self) -> None:
        """Gracefully closes all browsers, background tasks, and Playwright driver."""
        async with self._lock:
            self._is_closed = True
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
                self._cleanup_task = None

            for pb in list(self._browsers):
                await pb.close()
            self._browsers.clear()

            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception as p_err:
                    logger.warning(f"Error stopping Playwright driver: {p_err}")
                self._playwright = None

            logger.info("BrowserPool shut down gracefully.")


# Global Manager Instance
_global_browser_pool: Optional[BrowserPool] = None

def get_browser_pool() -> BrowserPool:
    """Returns the global BrowserPool singleton instance."""
    global _global_browser_pool
    if _global_browser_pool is None or _global_browser_pool._is_closed:
        _global_browser_pool = BrowserPool()
    return _global_browser_pool

async def close_browser_pool() -> None:
    """Closes the global BrowserPool singleton instance."""
    global _global_browser_pool
    if _global_browser_pool is not None and not _global_browser_pool._is_closed:
        await _global_browser_pool.close()
        _global_browser_pool = None

async def get_browser_pool_dependency() -> AsyncGenerator[BrowserPool, None]:
    """FastAPI dependency injecting the global BrowserPool without closing it per request."""
    pool = get_browser_pool()
    yield pool
