import re
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

class SitemapService:
    """
    Parses XML sitemaps and discovers sitemap locations.
    Supports nested sitemaps (sitemapindex), urlsets, and image sitemaps (image:image).
    """

    @staticmethod
    def discover_candidate_urls(base_url: str, robots_sitemaps: Optional[List[str]] = None) -> List[str]:
        candidates: List[str] = []

        if robots_sitemaps:
            for sm in robots_sitemaps:
                if sm and sm not in candidates:
                    candidates.append(sm)

        try:
            parsed = urlparse(base_url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            default_xml = f"{origin}/sitemap.xml"
            default_index = f"{origin}/sitemap_index.xml"

            if default_xml not in candidates:
                candidates.append(default_xml)
            if default_index not in candidates:
                candidates.append(default_index)
        except Exception:
            pass

        return candidates

    @staticmethod
    def parse_sitemap_xml(xml_content: str) -> Dict[str, Any]:
        if not xml_content or not xml_content.strip():
            return {
                "isIndex": False,
                "urls": [],
                "childSitemaps": [],
                "totalUrls": 0,
                "totalImages": 0
            }

        # Clean namespace prefixes for simpler parsing or use regex/namespaces
        # Remove default XML namespaces to simplify tag comparisons
        clean_xml = re.sub(r'\sxmlns(?::\w+)?="[^"]+"', '', xml_content)

        child_sitemaps: List[Dict[str, Any]] = []
        urls: List[Dict[str, Any]] = []

        try:
            root = ET.fromstring(clean_xml)
            tag_name = root.tag.split('}')[-1].lower()

            if tag_name == 'sitemapindex':
                for sitemap in root.findall('.//sitemap'):
                    loc_elem = sitemap.find('loc')
                    loc = loc_elem.text.strip() if loc_elem is not None and loc_elem.text else ""
                    lastmod_elem = sitemap.find('lastmod')
                    lastmod = lastmod_elem.text.strip() if lastmod_elem is not None and lastmod_elem.text else None

                    if loc:
                        child_sitemaps.append({
                            "loc": loc,
                            "lastmod": lastmod
                        })

                return {
                    "isIndex": True,
                    "urls": [],
                    "childSitemaps": child_sitemaps,
                    "totalUrls": 0,
                    "totalImages": 0
                }

            total_images = 0
            for url_elem in root.findall('.//url'):
                loc_elem = url_elem.find('loc')
                loc = loc_elem.text.strip() if loc_elem is not None and loc_elem.text else ""
                if not loc:
                    continue

                lastmod_elem = url_elem.find('lastmod')
                lastmod = lastmod_elem.text.strip() if lastmod_elem is not None and lastmod_elem.text else None

                changefreq_elem = url_elem.find('changefreq')
                changefreq = changefreq_elem.text.strip() if changefreq_elem is not None and changefreq_elem.text else None

                priority_elem = url_elem.find('priority')
                priority: Optional[float] = None
                if priority_elem is not None and priority_elem.text:
                    try:
                        priority = float(priority_elem.text.strip())
                    except ValueError:
                        priority = None

                images: List[Dict[str, Any]] = []
                for img_elem in url_elem.findall('.//image') + url_elem.findall('.//{*}image'):
                    img_loc_elem = img_elem.find('loc') or img_elem.find('{*}loc')
                    img_loc = img_loc_elem.text.strip() if img_loc_elem is not None and img_loc_elem.text else ""

                    img_title_elem = img_elem.find('title') or img_elem.find('{*}title')
                    img_title = img_title_elem.text.strip() if img_title_elem is not None and img_title_elem.text else None

                    img_caption_elem = img_elem.find('caption') or img_elem.find('{*}caption')
                    img_caption = img_caption_elem.text.strip() if img_caption_elem is not None and img_caption_elem.text else None

                    if img_loc:
                        images.append({
                            "loc": img_loc,
                            "title": img_title,
                            "caption": img_caption
                        })

                total_images += len(images)

                urls.append({
                    "loc": loc,
                    "lastmod": lastmod,
                    "changefreq": changefreq,
                    "priority": priority,
                    "images": images
                })

            return {
                "isIndex": False,
                "urls": urls,
                "childSitemaps": child_sitemaps,
                "totalUrls": len(urls),
                "totalImages": total_images
            }

        except Exception:
            return {
                "isIndex": False,
                "urls": [],
                "childSitemaps": [],
                "totalUrls": 0,
                "totalImages": 0
            }
