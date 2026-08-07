import re
import uuid
import datetime
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

class TechnicalMetadata:
    """
    Extracts and stores technical metadata for web pages:
    - Response time
    - Content length
    - HTML size
    - Word count
    - Language
    - Encoding
    - Content-Type
    - Compression
    - Cache headers
    """
    store: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def extract_metadata(
        cls,
        url: str,
        html: str,
        headers: Optional[Dict[str, str]] = None,
        response_time: int = 0
    ) -> Dict[str, Any]:
        headers = {k.lower(): v for k, v in (headers or {}).items()}
        soup = BeautifulSoup(html or "", "html.parser")

        # 1. HTML size
        html_bytes = (html or "").encode("utf-8")
        html_size = len(html_bytes)

        # 2. Content Length
        content_length = html_size
        if "content-length" in headers:
            try:
                parsed_len = int(headers["content-length"])
                if parsed_len > 0:
                    content_length = parsed_len
            except ValueError:
                pass

        # 3. Word count
        for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
            tag.decompose()
        body_text = soup.get_text() or ""
        words = [w for w in re.split(r"\s+", body_text.strip()) if w]
        word_count = len(words)

        # 4. Language
        html_tag = soup.find("html")
        language = html_tag.get("lang").strip() if html_tag and html_tag.get("lang") else ""
        if not language and "content-language" in headers:
            language = headers["content-language"].strip()
        if not language:
            language = "unknown"

        # 5. Encoding
        encoding = ""
        meta_charset = soup.find("meta", attrs={"charset": True})
        if meta_charset and meta_charset.get("charset"):
            encoding = meta_charset["charset"].strip()

        if not encoding:
            meta_http = soup.find("meta", attrs={"http-equiv": re.compile(r"content-type", re.I)})
            if meta_http and meta_http.get("content"):
                match = re.search(r"charset=([^\s;]+)", meta_http["content"], re.I)
                if match:
                    encoding = match.group(1)

        if not encoding and "content-type" in headers:
            match = re.search(r"charset=([^\s;]+)", headers["content-type"], re.I)
            if match:
                encoding = match.group(1)

        if not encoding:
            encoding = "utf-8"

        # 6. Content-Type
        content_type = headers.get("content-type", "text/html")

        # 7. Compression
        compression = headers.get("content-encoding", "none")

        # 8. Cache headers
        cache_headers = {
            "cacheControl": headers.get("cache-control"),
            "expires": headers.get("expires"),
            "etag": headers.get("etag"),
            "lastModified": headers.get("last-modified"),
            "pragma": headers.get("pragma"),
            "age": headers.get("age"),
            "vary": headers.get("vary")
        }

        item_id = f"tech_{str(uuid.uuid4())[:8]}"
        metadata = {
            "id": item_id,
            "url": url,
            "responseTime": response_time,
            "contentLength": content_length,
            "htmlSize": html_size,
            "wordCount": word_count,
            "language": language,
            "encoding": encoding,
            "contentType": content_type,
            "compression": compression,
            "cacheHeaders": cache_headers,
            "rawHeaders": headers,
            "createdAt": datetime.datetime.utcnow().isoformat() + "Z"
        }

        return metadata

    @classmethod
    def store_metadata(cls, metadata: Dict[str, Any]) -> Dict[str, Any]:
        cls.store[metadata["id"]] = metadata
        return metadata

    @classmethod
    def get_metadata(cls, item_id: str) -> Optional[Dict[str, Any]]:
        return cls.store.get(item_id)

    @classmethod
    def list_metadata(cls) -> List[Dict[str, Any]]:
        return list(cls.store.values())
