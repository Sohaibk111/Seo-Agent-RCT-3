import httpx
from typing import Optional, AsyncGenerator
from backend.config import settings
from backend.logging_config import logger

class HTTPClientManager:
    """Global manager for reusable httpx.AsyncClient connection pooling."""
    _client: Optional[httpx.AsyncClient] = None

    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        """Returns the global reusable httpx.AsyncClient instance.
        Creates and configures the client lazily if it is not initialized or closed.
        """
        if cls._client is None or cls._client.is_closed:
            limits = httpx.Limits(
                max_connections=settings.HTTP_MAX_CONNECTIONS,
                max_keepalive_connections=settings.HTTP_MAX_KEEPALIVE_CONNECTIONS,
                keepalive_expiry=settings.HTTP_KEEPALIVE_EXPIRY
            )
            timeout = httpx.Timeout(
                connect=settings.HTTP_TIMEOUT_CONNECT,
                read=settings.HTTP_TIMEOUT_READ,
                write=settings.HTTP_TIMEOUT_WRITE,
                pool=settings.HTTP_TIMEOUT_POOL
            )
            transport = httpx.AsyncHTTPTransport(
                retries=settings.HTTP_MAX_RETRIES,
                limits=limits
            )
            cls._client = httpx.AsyncClient(
                transport=transport,
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": "SEO-Agent-Bot/1.0"}
            )
            logger.info("Initialized global httpx.AsyncClient connection pool.")
        return cls._client

    @classmethod
    async def close_client(cls) -> None:
        """Closes the global httpx.AsyncClient instance gracefully on application shutdown."""
        if cls._client is not None and not cls._client.is_closed:
            await cls._client.aclose()
            logger.info("Closed global httpx.AsyncClient connection pool.")
            cls._client = None

def get_http_client() -> httpx.AsyncClient:
    """Returns the globally managed httpx.AsyncClient instance."""
    return HTTPClientManager.get_client()

async def close_http_client() -> None:
    """Closes the globally managed httpx.AsyncClient instance."""
    await HTTPClientManager.close_client()

async def get_async_client_dependency() -> AsyncGenerator[httpx.AsyncClient, None]:
    """FastAPI dependency for injecting the reusable global httpx.AsyncClient without closing it per request."""
    client = get_http_client()
    yield client
