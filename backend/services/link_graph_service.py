import uuid
from typing import Dict, Any, List, Optional, Set
from urllib.parse import urlparse

class PageNode:
    def __init__(self, url: str, status_code: int = 200, redirect_target: Optional[str] = None, is_external: bool = False):
        self.url = url
        self.status_code = status_code
        self.redirect_target = redirect_target
        self.is_external = is_external
        self.inbound_count = 0
        self.outbound_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "statusCode": self.status_code,
            "redirectTarget": self.redirect_target,
            "isExternal": self.is_external,
            "inboundCount": self.inbound_count,
            "outboundCount": self.outbound_count
        }

class LinkEdge:
    def __init__(self, source_url: str, target_url: str, anchor_text: str = "", rel: str = "", is_internal: bool = True, is_broken: bool = False):
        self.id = f"edge_{str(uuid.uuid4())[:8]}"
        self.source_url = source_url
        self.target_url = target_url
        self.anchor_text = anchor_text.strip()
        self.rel = rel.strip()
        self.is_internal = is_internal
        self.is_broken = is_broken

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sourceUrl": self.source_url,
            "targetUrl": self.target_url,
            "anchorText": self.anchor_text,
            "rel": self.rel,
            "isInternal": self.is_internal,
            "isBroken": self.is_broken
        }

class LinkGraphService:
    """
    Stores directional link edges (Page A -> Page B) and generates analysis:
    - Internal links
    - External links
    - Broken links
    - Orphan pages
    - Redirect chains
    """
    def __init__(self, session_id: str, base_url: str):
        self.session_id = session_id
        self.base_url = self.normalize_url(base_url)
        self.pages: Dict[str, PageNode] = {}
        self.edges: List[LinkEdge] = []

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

    def is_internal_url(self, url: str) -> bool:
        try:
            target_host = urlparse(url).netloc.lower()
            base_host = urlparse(self.base_url).netloc.lower()
            return target_host == base_host or target_host.endswith(f".{base_host}")
        except Exception:
            return False

    def add_page(self, url: str, status_code: int = 200, redirect_target: Optional[str] = None, is_external: Optional[bool] = None) -> PageNode:
        normalized = self.normalize_url(url)
        external = is_external if is_external is not None else not self.is_internal_url(normalized)
        norm_redirect = self.normalize_url(redirect_target) if redirect_target else None

        node = self.pages.get(normalized)
        if not node:
            node = PageNode(normalized, status_code, norm_redirect, external)
            self.pages[normalized] = node
        else:
            node.status_code = status_code
            node.redirect_target = norm_redirect
            node.is_external = external

        return node

    def add_link(self, source_url: str, target_url: str, anchor_text: str = "", rel: str = "") -> LinkEdge:
        norm_source = self.normalize_url(source_url)
        norm_target = self.normalize_url(target_url)

        self.add_page(norm_source)
        target_node = self.pages.get(norm_target) or self.add_page(norm_target, 200)

        is_internal = self.is_internal_url(norm_target)
        is_broken = target_node.status_code >= 400

        edge = LinkEdge(norm_source, norm_target, anchor_text, rel, is_internal, is_broken)
        self.edges.append(edge)

        source_node = self.pages.get(norm_source)
        if source_node:
            source_node.outbound_count += 1
        if target_node:
            target_node.inbound_count += 1

        return edge

    def get_internal_links(self, source_url: Optional[str] = None) -> List[Dict[str, Any]]:
        internal = [e for e in self.edges if e.is_internal]
        if source_url:
            norm_source = self.normalize_url(source_url)
            internal = [e for e in internal if e.source_url == norm_source]
        return [e.to_dict() for e in internal]

    def get_external_links(self, source_url: Optional[str] = None) -> List[Dict[str, Any]]:
        external = [e for e in self.edges if not e.is_internal]
        if source_url:
            norm_source = self.normalize_url(source_url)
            external = [e for e in external if e.source_url == norm_source]
        return [e.to_dict() for e in external]

    def get_broken_links(self) -> List[Dict[str, Any]]:
        broken = []
        for e in self.edges:
            target_node = self.pages.get(e.target_url)
            if e.is_broken or (target_node and target_node.status_code >= 400):
                broken.append(e.to_dict())
        return broken

    def get_orphan_pages(self) -> List[Dict[str, Any]]:
        orphans = []
        seed_norm = self.normalize_url(self.base_url)

        for url, node in self.pages.items():
            if not node.is_external and url != seed_norm:
                inbound_internal = [e for e in self.edges if e.target_url == url and e.is_internal]
                if len(inbound_internal) == 0:
                    orphans.append(node.to_dict())

        return orphans

    def get_redirect_chains(self) -> List[Dict[str, Any]]:
        chains = []

        for url, node in self.pages.items():
            if node.redirect_target:
                visited = {url}
                hop_list = [url]

                curr_url = node.redirect_target
                is_loop = False
                final_status = None

                while curr_url:
                    hop_list.append(curr_url)
                    if curr_url in visited:
                        is_loop = True
                        break
                    visited.add(curr_url)

                    next_node = self.pages.get(curr_url)
                    if next_node and next_node.redirect_target:
                        curr_url = next_node.redirect_target
                    else:
                        if next_node:
                            final_status = next_node.status_code
                        break

                if len(hop_list) >= 2:
                    chains.append({
                        "startUrl": url,
                        "chain": hop_list,
                        "finalUrl": hop_list[-1],
                        "finalStatusCode": final_status,
                        "hopCount": len(hop_list) - 1,
                        "isLoop": is_loop
                    })

        return chains

    def get_summary(self) -> Dict[str, Any]:
        internal_nodes = [p for p in self.pages.values() if not p.is_external]
        external_nodes = [p for p in self.pages.values() if p.is_external]

        return {
            "totalNodes": len(self.pages),
            "internalNodesCount": len(internal_nodes),
            "externalNodesCount": len(external_nodes),
            "totalEdges": len(self.edges),
            "internalEdgesCount": len(self.get_internal_links()),
            "externalEdgesCount": len(self.get_external_links()),
            "brokenEdgesCount": len(self.get_broken_links()),
            "orphanPagesCount": len(self.get_orphan_pages()),
            "redirectChainsCount": len(self.get_redirect_chains())
        }
