import datetime
from typing import Dict, Any, List, Optional

class CrawlLifecycleService:
    """
    Manages crawl lifecycle and page records:
    - start crawl job
    - pause crawl job
    - resume crawl job
    - stop crawl job
    - status query
    - pages listing & query
    - single page detail
    """
    crawls: Dict[int, Dict[str, Any]] = {}
    pages: Dict[int, Dict[str, Any]] = {}
    _next_page_id: int = 1

    @classmethod
    def register_crawl(cls, crawl_id: int, website_id: int, status: str = "queued") -> Dict[str, Any]:
        now = datetime.datetime.utcnow().isoformat() + "Z"
        crawl = {
            "id": crawl_id,
            "website_id": website_id,
            "status": status,
            "progress": 0,
            "pages_found": 0,
            "issues_found": 0,
            "duration_seconds": None,
            "started_at": None,
            "finished_at": None,
            "error_message": None,
            "created_at": now,
            "updated_at": now
        }
        cls.crawls[crawl_id] = crawl
        return crawl

    @classmethod
    def start_crawl(cls, crawl_id: int) -> Optional[Dict[str, Any]]:
        crawl = cls.crawls.get(crawl_id)
        if not crawl:
            return None
        now = datetime.datetime.utcnow().isoformat() + "Z"
        crawl["status"] = "running"
        if not crawl.get("started_at"):
            crawl["started_at"] = now
        crawl["updated_at"] = now
        return crawl

    @classmethod
    def pause_crawl(cls, crawl_id: int) -> Optional[Dict[str, Any]]:
        crawl = cls.crawls.get(crawl_id)
        if not crawl:
            return None
        now = datetime.datetime.utcnow().isoformat() + "Z"
        crawl["status"] = "paused"
        crawl["updated_at"] = now
        return crawl

    @classmethod
    def resume_crawl(cls, crawl_id: int) -> Optional[Dict[str, Any]]:
        crawl = cls.crawls.get(crawl_id)
        if not crawl:
            return None
        now = datetime.datetime.utcnow().isoformat() + "Z"
        crawl["status"] = "running"
        crawl["updated_at"] = now
        return crawl

    @classmethod
    def stop_crawl(cls, crawl_id: int) -> Optional[Dict[str, Any]]:
        crawl = cls.crawls.get(crawl_id)
        if not crawl:
            return None
        now = datetime.datetime.utcnow().isoformat() + "Z"
        crawl["status"] = "stopped"
        crawl["finished_at"] = now
        if crawl.get("started_at"):
            try:
                start_dt = datetime.datetime.fromisoformat(crawl["started_at"].replace("Z", "+00:00"))
                end_dt = datetime.datetime.fromisoformat(now.replace("Z", "+00:00"))
                crawl["duration_seconds"] = int((end_dt - start_dt).total_seconds())
            except Exception:
                pass
        crawl["updated_at"] = now
        return crawl

    @classmethod
    def get_status(cls, crawl_id: int) -> Optional[Dict[str, Any]]:
        crawl = cls.crawls.get(crawl_id)
        if not crawl:
            return None
        job_pages = [p for p in cls.pages.values() if p["crawl_job_id"] == crawl_id]
        stats = {
            "total_pages": len(job_pages),
            "html_pages": len([p for p in job_pages if "html" in (p.get("content_type") or "").lower()]),
            "redirects": len([p for p in job_pages if 300 <= (p.get("status_code") or 0) < 400]),
            "broken_pages": len([p for p in job_pages if (p.get("status_code") or 0) >= 400 or (p.get("status_code") or 0) == 0])
        }
        res = dict(crawl)
        res["stats"] = stats
        return res

    @classmethod
    def add_page(cls, crawl_id: int, page_data: Dict[str, Any]) -> Dict[str, Any]:
        page_id = cls._next_page_id
        cls._next_page_id += 1
        page = {
            "id": page_id,
            "crawl_job_id": crawl_id,
            "url": page_data.get("url", ""),
            "depth": page_data.get("depth", 0),
            "status_code": page_data.get("status_code", 200),
            "content_type": page_data.get("content_type", "text/html"),
            "title": page_data.get("title"),
            "meta_description": page_data.get("meta_description"),
            "canonical": page_data.get("canonical"),
            "h1": page_data.get("h1"),
            "word_count": page_data.get("word_count", 0),
            "internal_links": page_data.get("internal_links", 0),
            "external_links": page_data.get("external_links", 0),
            "noindex": bool(page_data.get("noindex")),
            "nofollow": bool(page_data.get("nofollow")),
            "redirect_target": page_data.get("redirect_target"),
            "response_time": page_data.get("response_time"),
            "created_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
        cls.pages[page_id] = page
        if crawl_id in cls.crawls:
            cls.crawls[crawl_id]["pages_found"] += 1
        return page

    @classmethod
    def list_pages(cls, crawl_id: int) -> List[Dict[str, Any]]:
        return [p for p in cls.pages.values() if p["crawl_job_id"] == crawl_id]

    @classmethod
    def get_page(cls, crawl_id: int, page_id: int) -> Optional[Dict[str, Any]]:
        page = cls.pages.get(page_id)
        if not page or page["crawl_job_id"] != crawl_id:
            return None
        return page
