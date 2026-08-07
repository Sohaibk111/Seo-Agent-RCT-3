import time
import httpx
from typing import Dict, Any, List, Optional

class HTTPFetcher:
    """
    HTTP Fetcher utility for crawling pages.
    Collects status code, redirects, response headers, response time, and HTML content.
    """
    @staticmethod
    async def fetch_url_async(url: str, timeout: float = 10.0) -> Dict[str, Any]:
        start_time = time.time()
        redirects: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "SEO-Agent-Bot/1.0 (Compatible; HTTP Fetcher)"}
        ) as client:
            try:
                response = await client.get(url)
                end_time = time.time()
                response_time = round((end_time - start_time) * 1000, 2)

                for hist in response.history:
                    redirects.append({
                        "url": str(hist.url),
                        "status_code": hist.status_code,
                        "location": hist.headers.get("location")
                    })

                headers = dict(response.headers)
                return {
                    "url": str(response.url),
                    "status_code": response.status_code,
                    "redirects": redirects,
                    "headers": headers,
                    "response_time": response_time,
                    "html": response.text,
                    "content_type": headers.get("content-type", "text/html")
                }
            except Exception as e:
                end_time = time.time()
                response_time = round((end_time - start_time) * 1000, 2)
                return {
                    "url": url,
                    "status_code": 500,
                    "redirects": redirects,
                    "headers": {},
                    "response_time": response_time,
                    "html": "",
                    "error": str(e)
                }
