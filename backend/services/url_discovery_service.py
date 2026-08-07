import re
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from urllib.parse import urlparse, urljoin

class DiscoveryConfig:
    def __init__(
        self,
        max_depth: int = 3,
        max_pages: int = 100,
        max_redirects: int = 5,
        timeout: float = 10.0,
        retry: int = 3,
        allowed_domains: Optional[List[str]] = None
    ):
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.max_redirects = max_redirects
        self.timeout = timeout
        self.retry = retry
        self.allowed_domains = allowed_domains or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "maxDepth": self.max_depth,
            "maxPages": self.max_pages,
            "maxRedirects": self.max_redirects,
            "timeout": self.timeout,
            "retry": self.retry,
            "allowedDomains": self.allowed_domains
        }

class URLItem:
    def __init__(self, url: str, depth: int, discovered_from: Optional[str] = None):
        self.id = str(uuid.uuid4())[:8]
        self.url = url
        self.depth = depth
        self.discovered_from = discovered_from
        self.status = "queue"  # queue, pending, visited, failed
        self.attempts = 0
        self.redirect_count = 0
        self.error: Optional[str] = None
        self.status_code: Optional[int] = None
        self.added_at = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "depth": self.depth,
            "discoveredFrom": self.discovered_from,
            "status": self.status,
            "attempts": self.attempts,
            "redirectCount": self.redirect_count,
            "error": self.error,
            "statusCode": self.status_code,
            "addedAt": self.added_at,
            "updatedAt": self.updated_at
        }

class URLDiscoveryService:
    """
    Manages URL discovery queues (Queue, Visited, Pending, Failed) with configurable limits:
    max_depth, max_pages, max_redirects, timeout, retry.
    """
    def __init__(self, session_id: str, seed_url: str, config: Optional[Dict[str, Any]] = None):
        self.session_id = session_id
        self.seed_url = self.normalize_url(seed_url)

        cfg = config or {}
        self.config = DiscoveryConfig(
            max_depth=cfg.get("maxDepth", 3),
            max_pages=cfg.get("maxPages", 100),
            max_redirects=cfg.get("maxRedirects", 5),
            timeout=cfg.get("timeout", 10.0),
            retry=cfg.get("retry", 3),
            allowed_domains=cfg.get("allowedDomains")
        )

        self.queue: Dict[str, URLItem] = {}
        self.pending: Dict[str, URLItem] = {}
        self.visited: Dict[str, URLItem] = {}
        self.failed: Dict[str, URLItem] = {}

        if self.seed_url:
            self.enqueue(self.seed_url, depth=0)

    @staticmethod
    def normalize_url(raw_url: str) -> str:
        if not raw_url:
            return ""
        try:
            parsed = urlparse(raw_url)
            scheme = parsed.scheme.lower() or "http"
            netloc = parsed.netloc.lower()
            path = parsed.path
            if path == "/":
                path = ""
            elif len(path) > 1 and path.endswith("/"):
                path = path[:-1]
            return f"{scheme}://{netloc}{path}" + (f"?{parsed.query}" if parsed.query else "")
        except Exception:
            return raw_url.strip()

    def is_url_tracked(self, normalized_url: str) -> bool:
        return (
            normalized_url in self.queue or
            normalized_url in self.pending or
            normalized_url in self.visited or
            normalized_url in self.failed
        )

    def enqueue(self, url: str, depth: int, discovered_from: Optional[str] = None) -> bool:
        normalized = self.normalize_url(url)
        if not normalized:
            return False

        if depth > self.config.max_depth:
            return False

        if self.is_url_tracked(normalized):
            return False

        total_tracked = len(self.queue) + len(self.pending) + len(self.visited) + len(self.failed)
        if total_tracked >= self.config.max_pages:
            return False

        if self.config.allowed_domains:
            try:
                hostname = urlparse(normalized).netloc.lower()
                is_allowed = any(hostname == d or hostname.endswith(f".{d}") for d in self.config.allowed_domains)
                if not is_allowed:
                    return False
            except Exception:
                return False

        item = URLItem(normalized, depth, discovered_from)
        self.queue[normalized] = item
        return True

    def add_discovered_urls(self, urls: List[str], current_depth: int, source_url: str) -> int:
        added_count = 0
        next_depth = current_depth + 1

        for raw in urls:
            try:
                resolved = urljoin(source_url, raw)
            except Exception:
                resolved = raw

            if self.enqueue(resolved, next_depth, source_url):
                added_count += 1

        return added_count

    def next(self) -> Optional[URLItem]:
        if not self.queue:
            return None

        url_key = next(iter(self.queue))
        item = self.queue.pop(url_key)

        item.status = "pending"
        item.attempts += 1
        item.updated_at = datetime.utcnow().isoformat()

        self.pending[url_key] = item
        return item

    def mark_visited(self, url: str, status_code: int = 200, redirect_count: int = 0) -> bool:
        normalized = self.normalize_url(url)
        item = self.pending.pop(normalized, None) or self.queue.pop(normalized, None)

        if not item:
            return False

        item.status = "visited"
        item.status_code = status_code
        item.redirect_count = redirect_count
        item.updated_at = datetime.utcnow().isoformat()

        self.visited[normalized] = item
        return True

    def mark_failed(self, url: str, error: str, status_code: Optional[int] = None) -> bool:
        normalized = self.normalize_url(url)
        item = self.pending.pop(normalized, None) or self.queue.pop(normalized, None)

        if not item:
            return False

        item.error = error
        if status_code:
            item.status_code = status_code
        item.updated_at = datetime.utcnow().isoformat()

        if item.attempts < self.config.retry:
            item.status = "queue"
            self.queue[normalized] = item
        else:
            item.status = "failed"
            self.failed[normalized] = item

        return True

    def get_stats(self) -> Dict[str, Any]:
        return {
            "totalDiscovered": len(self.queue) + len(self.pending) + len(self.visited) + len(self.failed),
            "queueCount": len(self.queue),
            "pendingCount": len(self.pending),
            "visitedCount": len(self.visited),
            "failedCount": len(self.failed),
            "config": self.config.to_dict()
        }

    def get_urls_by_status(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        if status == "queue":
            return [i.to_dict() for i in self.queue.values()]
        if status == "pending":
            return [i.to_dict() for i in self.pending.values()]
        if status == "visited":
            return [i.to_dict() for i in self.visited.values()]
        if status == "failed":
            return [i.to_dict() for i in self.failed.values()]

        all_items = (
            list(self.visited.values()) +
            list(self.pending.values()) +
            list(self.queue.values()) +
            list(self.failed.values())
        )
        return [i.to_dict() for i in all_items]
