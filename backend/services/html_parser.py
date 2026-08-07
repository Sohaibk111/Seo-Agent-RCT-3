import re
import json
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional

class HTMLParserService:
    """
    Parses HTML documents using BeautifulSoup to extract SEO elements.
    Extracts title, meta description, canonical, meta robots, headings (h1-h6),
    images, links, Open Graph tags, Twitter Cards, JSON-LD, language, and charset.
    """
    @staticmethod
    def parse_html(html: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        soup = BeautifulSoup(html or "", "html.parser")

        # 1. Title
        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        # 2. Meta description
        meta_desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        meta_description = meta_desc_tag.get("content", "").strip() if meta_desc_tag and meta_desc_tag.get("content") else ""

        # 3. Canonical
        canonical_tag = soup.find("link", attrs={"rel": re.compile(r"^canonical$", re.I)})
        canonical = canonical_tag.get("href", "").strip() if canonical_tag and canonical_tag.get("href") else ""
        if canonical and base_url:
            try:
                canonical = urljoin(base_url, canonical)
            except Exception:
                pass

        # 4. Meta Robots
        meta_robots_tag = soup.find("meta", attrs={"name": re.compile(r"^(robots|googlebot)$", re.I)})
        meta_robots = meta_robots_tag.get("content", "").strip() if meta_robots_tag and meta_robots_tag.get("content") else ""

        # 5. Language
        html_tag = soup.find("html")
        language = html_tag.get("lang", "").strip() if html_tag and html_tag.get("lang") else ""

        # 6. Charset
        meta_charset = soup.find("meta", attrs={"charset": True})
        charset = meta_charset.get("charset", "").strip() if meta_charset and meta_charset.get("charset") else ""
        if not charset:
            meta_ct = soup.find("meta", attrs={"http-equiv": re.compile(r"^content-type$", re.I)})
            if meta_ct and meta_ct.get("content"):
                match = re.search(r"charset=([^\s;]+)", meta_ct.get("content"), re.I)
                if match:
                    charset = match.group(1)

        # 7. Headings H1-H6
        headings: List[Dict[str, str]] = []
        for tag in soup.find_all(re.compile(r"^h[1-6]$", re.I)):
            text = " ".join(tag.get_text().split())
            if text:
                headings.append({"level": tag.name.lower(), "text": text})

        # 8. Images
        images: List[Dict[str, Any]] = []
        for img in soup.find_all("img"):
            src = img.get("src", "").strip()
            if src and base_url:
                try:
                    src = urljoin(base_url, src)
                except Exception:
                    pass
            alt = img.get("alt", "").strip()
            images.append({
                "src": src,
                "alt": alt,
                "width": img.get("width"),
                "height": img.get("height"),
                "loading": img.get("loading")
            })

        # 9. Links
        links: List[Dict[str, Any]] = []
        base_origin = ""
        if base_url:
            parsed_base = urlparse(base_url)
            base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"

        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            is_internal = False
            if href and base_url:
                try:
                    resolved = urljoin(base_url, href)
                    parsed_resolved = urlparse(resolved)
                    resolved_origin = f"{parsed_resolved.scheme}://{parsed_resolved.netloc}"
                    is_internal = (resolved_origin == base_origin) if base_origin else False
                    href = resolved
                except Exception:
                    is_internal = False
            elif href.startswith("/") or href.startswith("#") or href.startswith("."):
                is_internal = True

            text = " ".join(a.get_text().split())
            links.append({
                "href": href,
                "text": text,
                "rel": a.get("rel"),
                "target": a.get("target"),
                "isInternal": is_internal
            })

        # 10. Open Graph
        open_graph: Dict[str, str] = {}
        for og_meta in soup.find_all("meta", property=re.compile(r"^og:", re.I)):
            prop = og_meta.get("property", "").lower()
            content = og_meta.get("content", "").strip()
            if prop and content:
                open_graph[prop] = content

        # 11. Twitter Cards
        twitter_cards: Dict[str, str] = {}
        for tw_meta in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:", re.I)}):
            key = tw_meta.get("name", "").lower()
            content = tw_meta.get("content", "").strip()
            if key and content:
                twitter_cards[key] = content

        # 12. JSON-LD
        json_ld: List[Any] = []
        for script in soup.find_all("script", type=re.compile(r"application/ld\+json", re.I)):
            raw_content = script.string
            if raw_content:
                try:
                    parsed = json.loads(raw_content)
                    json_ld.append(parsed)
                except Exception:
                    json_ld.append({"raw": raw_content, "parseError": True})

        return {
            "title": title,
            "metaDescription": meta_description,
            "canonical": canonical,
            "metaRobots": meta_robots,
            "language": language,
            "charset": charset,
            "headings": headings,
            "images": images,
            "links": links,
            "openGraph": open_graph,
            "twitterCards": twitter_cards,
            "jsonLd": json_ld
        }
