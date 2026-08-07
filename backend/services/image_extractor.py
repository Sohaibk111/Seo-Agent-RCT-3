import re
import urllib.parse
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

class ImageExtractor:
    """
    Extracts image attributes from HTML:
    - src
    - alt
    - width & height
    - lazy loading (loading="lazy", data-src, lazy classes)
    - srcset
    - file size (if available)
    """

    @staticmethod
    def extract_images_from_html(html: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        soup = BeautifulSoup(html or "", "html.parser")
        images: List[Dict[str, Any]] = []

        missing_alt_count = 0
        missing_dim_count = 0
        lazy_count = 0

        for img in soup.find_all("img"):
            src = (img.get("src") or img.get("data-src") or "").strip()
            data_src = (img.get("data-src") or "").strip() or None
            srcset = (img.get("srcset") or "").strip() or None

            if src and base_url:
                try:
                    src = urllib.parse.urljoin(base_url, src)
                except Exception:
                    pass

            alt = (img.get("alt") or "").strip()
            width = img.get("width")
            height = img.get("height")
            loading = (img.get("loading") or "").strip().lower() or None

            classes = img.get("class") or []
            if isinstance(classes, str):
                classes = classes.split()

            is_missing_alt = len(alt) == 0
            is_missing_dim = not width or not height
            is_lazy = (
                loading == "lazy" or
                data_src is not None or
                "lazyload" in classes or
                "lazy" in classes
            )

            if is_missing_alt:
                missing_alt_count += 1
            if is_missing_dim:
                missing_dim_count += 1
            if is_lazy:
                lazy_count += 1

            images.append({
                "src": src,
                "alt": alt,
                "width": str(width) if width else None,
                "height": str(height) if height else None,
                "loading": loading,
                "dataSrc": data_src,
                "srcset": srcset,
                "isMissingAlt": is_missing_alt,
                "isMissingDimensions": is_missing_dim,
                "isLazy": is_lazy,
                "fileSize": None
            })

        return {
            "totalImages": len(images),
            "missingAltCount": missing_alt_count,
            "missingDimensionsCount": missing_dim_count,
            "lazyLoadedCount": lazy_count,
            "images": images
        }
