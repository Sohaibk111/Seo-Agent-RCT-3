export interface PageNode {
  url: string;
  statusCode: number;
  redirectTarget?: string;
  isExternal: boolean;
  inboundCount: number;
  outboundCount: number;
}

export interface LinkEdge {
  id: string;
  sourceUrl: string;
  targetUrl: string;
  anchorText: string;
  rel?: string;
  isInternal: boolean;
  isBroken: boolean;
}

export interface RedirectChain {
  startUrl: string;
  chain: string[];
  finalUrl?: string;
  finalStatusCode?: number;
  hopCount: number;
  isLoop: boolean;
}

export interface GraphSummary {
  totalNodes: number;
  internalNodesCount: number;
  externalNodesCount: number;
  totalEdges: number;
  internalEdgesCount: number;
  externalEdgesCount: number;
  brokenEdgesCount: number;
  orphanPagesCount: number;
  redirectChainsCount: number;
}

export class LinkGraphManager {
  public id: string;
  public baseUrl: string;

  public pages: Map<string, PageNode> = new Map();
  public edges: LinkEdge[] = [];

  constructor(id: string, baseUrl: string) {
    this.id = id;
    this.baseUrl = this.normalizeUrl(baseUrl);
  }

  public normalizeUrl(rawUrl: string): string {
    try {
      const parsed = new URL(rawUrl);
      parsed.hash = '';
      if (parsed.pathname === '/' && !parsed.search) {
        return `${parsed.protocol}//${parsed.host}`;
      } else if (parsed.pathname.length > 1 && parsed.pathname.endsWith('/')) {
        parsed.pathname = parsed.pathname.slice(0, -1);
        return parsed.href;
      }
      return parsed.href;
    } catch {
      return rawUrl.trim();
    }
  }

  public isInternalUrl(url: string): boolean {
    try {
      const targetHost = new URL(url).hostname.toLowerCase();
      const baseHost = new URL(this.baseUrl).hostname.toLowerCase();
      return targetHost === baseHost || targetHost.endsWith(`.${baseHost}`);
    } catch {
      return false;
    }
  }

  public addPage(url: string, statusCode: number = 200, redirectTarget?: string, isExternal?: boolean): PageNode {
    const normalized = this.normalizeUrl(url);
    const external = isExternal !== undefined ? isExternal : !this.isInternalUrl(normalized);
    const normRedirect = redirectTarget ? this.normalizeUrl(redirectTarget) : undefined;

    let node = this.pages.get(normalized);
    if (!node) {
      node = {
        url: normalized,
        statusCode,
        redirectTarget: normRedirect,
        isExternal: external,
        inboundCount: 0,
        outboundCount: 0
      };
      this.pages.set(normalized, node);
    } else {
      node.statusCode = statusCode;
      node.redirectTarget = normRedirect;
      node.isExternal = external;
    }

    return node;
  }

  public addLink(sourceUrl: string, targetUrl: string, anchorText: string = '', rel: string = ''): LinkEdge {
    const normSource = this.normalizeUrl(sourceUrl);
    const normTarget = this.normalizeUrl(targetUrl);

    // Ensure source and target page nodes exist
    this.addPage(normSource);
    const targetNode = this.pages.get(normTarget) || this.addPage(normTarget, 200);

    const isInternal = this.isInternalUrl(normTarget);
    const isBroken = targetNode.statusCode >= 400;

    const edge: LinkEdge = {
      id: `edge_${Math.random().toString(36).substring(2, 11)}`,
      sourceUrl: normSource,
      targetUrl: normTarget,
      anchorText: anchorText.trim(),
      rel: rel.trim(),
      isInternal,
      isBroken
    };

    this.edges.push(edge);

    // Update node metrics
    const sourceNode = this.pages.get(normSource);
    if (sourceNode) sourceNode.outboundCount += 1;
    if (targetNode) targetNode.inboundCount += 1;

    return edge;
  }

  public getInternalLinks(sourceUrl?: string): LinkEdge[] {
    let internal = this.edges.filter(e => e.isInternal);
    if (sourceUrl) {
      const normSource = this.normalizeUrl(sourceUrl);
      internal = internal.filter(e => e.sourceUrl === normSource);
    }
    return internal;
  }

  public getExternalLinks(sourceUrl?: string): LinkEdge[] {
    let external = this.edges.filter(e => !e.isInternal);
    if (sourceUrl) {
      const normSource = this.normalizeUrl(sourceUrl);
      external = external.filter(e => e.sourceUrl === normSource);
    }
    return external;
  }

  public getBrokenLinks(): LinkEdge[] {
    return this.edges.filter(e => {
      const targetNode = this.pages.get(e.targetUrl);
      return e.isBroken || (targetNode && targetNode.statusCode >= 400);
    });
  }

  public getOrphanPages(): PageNode[] {
    const orphans: PageNode[] = [];
    const seedNorm = this.normalizeUrl(this.baseUrl);

    for (const [url, node] of this.pages.entries()) {
      // Internal pages with 0 internal inbound links (excluding root baseUrl)
      if (!node.isExternal && url !== seedNorm) {
        const inboundInternal = this.edges.filter(e => e.targetUrl === url && e.isInternal);
        if (inboundInternal.length === 0) {
          orphans.push(node);
        }
      }
    }

    return orphans;
  }

  public getRedirectChains(): RedirectChain[] {
    const chains: RedirectChain[] = [];

    for (const [url, node] of this.pages.entries()) {
      // Check if page initiates a redirect (301, 302, 307, 308) or has a redirectTarget
      if (node.redirectTarget) {
        const visitedUrls = new Set<string>([url]);
        const hopList: string[] = [url];

        let currUrl: string | undefined = node.redirectTarget;
        let isLoop = false;
        let finalStatus: number | undefined;

        while (currUrl) {
          hopList.push(currUrl);

          if (visitedUrls.has(currUrl)) {
            isLoop = true;
            break;
          }

          visitedUrls.add(currUrl);
          const nextNode = this.pages.get(currUrl);

          if (nextNode && nextNode.redirectTarget) {
            currUrl = nextNode.redirectTarget;
          } else {
            if (nextNode) {
              finalStatus = nextNode.statusCode;
            }
            break;
          }
        }

        // Only include chains with >= 2 hops (e.g. A -> B -> C) or redirect loops
        if (hopList.length >= 2) {
          chains.push({
            startUrl: url,
            chain: hopList,
            finalUrl: hopList[hopList.length - 1],
            finalStatusCode: finalStatus,
            hopCount: hopList.length - 1,
            isLoop
          });
        }
      }
    }

    return chains;
  }

  public getSummary(): GraphSummary {
    const internalNodes = Array.from(this.pages.values()).filter(p => !p.isExternal);
    const externalNodes = Array.from(this.pages.values()).filter(p => p.isExternal);

    return {
      totalNodes: this.pages.size,
      internalNodesCount: internalNodes.length,
      externalNodesCount: externalNodes.length,
      totalEdges: this.edges.length,
      internalEdgesCount: this.getInternalLinks().length,
      externalEdgesCount: this.getExternalLinks().length,
      brokenEdgesCount: this.getBrokenLinks().length,
      orphanPagesCount: this.getOrphanPages().length,
      redirectChainsCount: this.getRedirectChains().length
    };
  }
}

export const linkGraphSessions: Map<string, LinkGraphManager> = new Map();
