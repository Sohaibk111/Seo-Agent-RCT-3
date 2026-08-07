from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

class HeadingExtractor:
    """
    Extracts headings (H1-H6) from HTML and analyzes hierarchical structure,
    detecting skipped heading levels, missing/multiple H1s, and building a tree.
    """

    @staticmethod
    def extract_headings_from_html(html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html or "", "html.parser")
        headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

        flat_headings: List[Dict[str, Any]] = []
        counts = {"h1": 0, "h2": 0, "h3": 0, "h4": 0, "h5": 0, "h6": 0}

        empty_headings_count = 0
        has_skipped_levels = False
        previous_level = 0

        for idx, el in enumerate(headings):
            tag_name = el.name.lower()
            level = int(tag_name.replace("h", ""))
            text = el.get_text().strip()
            element_id = el.get("id")
            class_name = " ".join(el.get("class")) if isinstance(el.get("class"), list) else el.get("class")

            if not text:
                empty_headings_count += 1

            counts[tag_name] += 1

            is_skipped = False
            if previous_level > 0 and level > previous_level + 1:
                is_skipped = True
                has_skipped_levels = True

            item = {
                "id": f"h_{idx + 1}",
                "tag": tag_name,
                "level": level,
                "text": text,
                "elementId": element_id,
                "className": class_name,
                "isSkippedLevel": is_skipped,
                "parentTag": None
            }
            flat_headings.append(item)
            previous_level = level

        # Build Hierarchical Tree
        tree: List[Dict[str, Any]] = []
        stack: List[Dict[str, Any]] = []

        for item in flat_headings:
            node = {"heading": item, "children": []}

            while stack and stack[-1]["level"] >= item["level"]:
                stack.pop()

            if not stack:
                tree.append(node)
            else:
                parent = stack[-1]["node"]
                parent["children"].append(node)
                item["parentTag"] = parent["heading"]["tag"]

            stack.append({"level": item["level"], "node": node})

        return {
            "totalHeadings": len(flat_headings),
            "counts": counts,
            "issues": {
                "missingH1": counts["h1"] == 0,
                "multipleH1": counts["h1"] > 1,
                "hasSkippedLevels": has_skipped_levels,
                "emptyHeadingsCount": empty_headings_count
            },
            "flatHeadings": flat_headings,
            "tree": tree
        }
