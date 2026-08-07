export interface DiscoveryConfig {
  maxDepth: number;
  maxPages: number;
  maxRedirects: number;
  timeout: number;
  retry: number;
  allowedDomains?: string[];
}

export type URLItemStatus = 'queue' | 'pending' | 'visited' | 'failed';

export interface URLItem {
  id: string;
  url: string;
  depth: number;
  discoveredFrom?: string;
  status: URLItemStatus;
  attempts: number;
  redirectCount: number;
  error?: string;
  statusCode?: number;
  addedAt: string;
  updatedAt: string;
}

export interface URLDiscoveryStats {
  totalDiscovered: number;
  queueCount: number;
  pendingCount: number;
  visitedCount: number;
  failedCount: number;
  config: DiscoveryConfig;
}

export class URLDiscoveryManager {
  public id: string;
  public seedUrl: string;
  public config: DiscoveryConfig;

  public queue: Map<string, URLItem> = new Map();
  public pending: Map<string, URLItem> = new Map();
  public visited: Map<string, URLItem> = new Map();
  public failed: Map<string, URLItem> = new Map();

  constructor(
    id: string,
    seedUrl: string,
    config?: Partial<DiscoveryConfig>
  ) {
    this.id = id;
    this.seedUrl = this.normalizeUrl(seedUrl);
    this.config = {
      maxDepth: config?.maxDepth ?? 3,
      maxPages: config?.maxPages ?? 100,
      maxRedirects: config?.maxRedirects ?? 5,
      timeout: config?.timeout ?? 10000,
      retry: config?.retry ?? 3,
      allowedDomains: config?.allowedDomains
    };

    // Auto-enqueue seed URL at depth 0
    if (this.seedUrl) {
      this.enqueue(this.seedUrl, 0);
    }
  }

  public normalizeUrl(rawUrl: string): string {
    try {
      const parsed = new URL(rawUrl);
      parsed.hash = ''; // strip fragments
      let href = parsed.href;
      if (parsed.pathname === '/' && !parsed.search) {
        return `${parsed.protocol}//${parsed.host}`;
      } else if (parsed.pathname.length > 1 && parsed.pathname.endsWith('/')) {
        parsed.pathname = parsed.pathname.slice(0, -1);
        return parsed.href;
      }
      return href;
    } catch {
      return rawUrl.trim();
    }
  }

  public isUrlTracked(normalizedUrl: string): boolean {
    return (
      this.queue.has(normalizedUrl) ||
      this.pending.has(normalizedUrl) ||
      this.visited.has(normalizedUrl) ||
      this.failed.has(normalizedUrl)
    );
  }

  public enqueue(url: string, depth: number, discoveredFrom?: string): boolean {
    const normalized = this.normalizeUrl(url);
    if (!normalized) return false;

    // Check depth constraint
    if (depth > this.config.maxDepth) {
      return false;
    }

    // Check if already tracked
    if (this.isUrlTracked(normalized)) {
      return false;
    }

    // Check max pages limit
    const totalTracked = this.queue.size + this.pending.size + this.visited.size + this.failed.size;
    if (totalTracked >= this.config.maxPages) {
      return false;
    }

    // Domain filter check if configured
    if (this.config.allowedDomains && this.config.allowedDomains.length > 0) {
      try {
        const hostname = new URL(normalized).hostname;
        const isAllowed = this.config.allowedDomains.some(domain => 
          hostname === domain || hostname.endsWith(`.${domain}`)
        );
        if (!isAllowed) return false;
      } catch {
        return false;
      }
    }

    const item: URLItem = {
      id: Math.random().toString(36).substring(2, 11),
      url: normalized,
      depth,
      discoveredFrom,
      status: 'queue',
      attempts: 0,
      redirectCount: 0,
      addedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    this.queue.set(normalized, item);
    return true;
  }

  public addDiscoveredUrls(urls: string[], currentDepth: number, sourceUrl: string): number {
    let addedCount = 0;
    const nextDepth = currentDepth + 1;

    for (const rawUrl of urls) {
      let resolvedUrl = rawUrl;
      try {
        resolvedUrl = new URL(rawUrl, sourceUrl).href;
      } catch {
        // Keep raw string if resolution fails
      }

      if (this.enqueue(resolvedUrl, nextDepth, sourceUrl)) {
        addedCount++;
      }
    }

    return addedCount;
  }

  public next(): URLItem | null {
    if (this.queue.size === 0) return null;

    // Get first item from queue (FIFO)
    const firstEntry = this.queue.entries().next().value;
    if (!firstEntry) return null;

    const [urlKey, item] = firstEntry;
    this.queue.delete(urlKey);

    item.status = 'pending';
    item.attempts += 1;
    item.updatedAt = new Date().toISOString();

    this.pending.set(urlKey, item);
    return item;
  }

  public markVisited(url: string, statusCode: number = 200, redirectCount: number = 0): boolean {
    const normalized = this.normalizeUrl(url);
    const item = this.pending.get(normalized) || this.queue.get(normalized);

    if (!item) return false;

    this.pending.delete(normalized);
    this.queue.delete(normalized);

    item.status = 'visited';
    item.statusCode = statusCode;
    item.redirectCount = redirectCount;
    item.updatedAt = new Date().toISOString();

    this.visited.set(normalized, item);
    return true;
  }

  public markFailed(url: string, error: string, statusCode?: number): boolean {
    const normalized = this.normalizeUrl(url);
    const item = this.pending.get(normalized) || this.queue.get(normalized);

    if (!item) return false;

    this.pending.delete(normalized);
    this.queue.delete(normalized);

    item.error = error;
    if (statusCode) item.statusCode = statusCode;
    item.updatedAt = new Date().toISOString();

    // Retry logic
    if (item.attempts < this.config.retry) {
      item.status = 'queue';
      this.queue.set(normalized, item);
    } else {
      item.status = 'failed';
      this.failed.set(normalized, item);
    }

    return true;
  }

  public getStats(): URLDiscoveryStats {
    return {
      totalDiscovered: this.queue.size + this.pending.size + this.visited.size + this.failed.size,
      queueCount: this.queue.size,
      pendingCount: this.pending.size,
      visitedCount: this.visited.size,
      failedCount: this.failed.size,
      config: { ...this.config }
    };
  }

  public getUrlsByStatus(status?: URLItemStatus): URLItem[] {
    if (status === 'queue') return Array.from(this.queue.values());
    if (status === 'pending') return Array.from(this.pending.values());
    if (status === 'visited') return Array.from(this.visited.values());
    if (status === 'failed') return Array.from(this.failed.values());

    return [
      ...Array.from(this.visited.values()),
      ...Array.from(this.pending.values()),
      ...Array.from(this.queue.values()),
      ...Array.from(this.failed.values())
    ];
  }
}

// In-memory sessions store
export const discoverySessions: Map<string, URLDiscoveryManager> = new Map();
