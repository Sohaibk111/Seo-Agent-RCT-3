import { fetchUrl, FetchResult } from './httpFetcher';
import { RobotsParser, parseRobotsTxt } from './robotsParser';
import { discoverSitemapCandidateUrls, parseSitemapXml } from './sitemapParser';
import { URLDiscoveryManager, DiscoveryConfig } from './urlDiscoveryManager';
import { parseHtml, ParsedSEOData } from './htmlParser';
import { extractHeadingsFromHtml, HeadingExtractionResult } from './headingExtractor';
import { extractImagesFromHtml, ImageExtractionResult } from './imageExtractor';
import { TechnicalMetadataManager, TechnicalMetadata } from './technicalMetadata';
import { LinkGraphManager, GraphSummary } from './linkGraphManager';

export interface CrawlPipelinePageResult {
  url: string;
  depth: number;
  statusCode: number;
  contentType: string;
  title: string;
  metaDescription: string;
  canonical: string;
  h1: string;
  wordCount: number;
  internalLinksCount: number;
  externalLinksCount: number;
  noindex: boolean;
  nofollow: boolean;
  responseTime: number;
  headings: HeadingExtractionResult;
  images: ImageExtractionResult;
  technicalMetadata: TechnicalMetadata;
}

export interface CrawlPipelineIssue {
  pageUrl: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  category: 'status_code' | 'metadata' | 'content' | 'links' | 'security' | 'indexability';
  message: string;
  recommendation: string;
}

export interface CrawlPipelineResult {
  seedUrl: string;
  status: 'completed' | 'failed' | 'stopped';
  pages: CrawlPipelinePageResult[];
  issues: CrawlPipelineIssue[];
  linkGraphSummary: GraphSummary;
  robotsTxtFound: boolean;
  sitemapsFound: string[];
  totalDiscovered: number;
  totalCrawled: number;
  totalFailed: number;
  durationMs: number;
}

export interface CrawlPipelineOptions {
  maxDepth?: number;
  maxPages?: number;
  timeoutMs?: number;
  userAgent?: string;
  respectRobotsTxt?: boolean;
  allowLocalIp?: boolean;
}

/**
 * Executes a full end-to-end crawl pipeline across robots, sitemaps, URL discovery,
 * HTTP fetching, HTML/Headings/Images/Metadata extraction, Link Graph, and Issue detection.
 */
export async function executeCrawlPipeline(
  seedUrl: string,
  options: CrawlPipelineOptions = {}
): Promise<CrawlPipelineResult> {
  const startTime = Date.now();
  const maxDepth = options.maxDepth ?? 3;
  const maxPages = options.maxPages ?? 20;
  const timeoutMs = options.timeoutMs ?? 10000;
  const userAgent = options.userAgent ?? '*';
  const respectRobots = options.respectRobotsTxt !== false;
  const allowLocalIp = options.allowLocalIp ?? (process.env.NODE_ENV === 'test');

  const origin = new URL(seedUrl).origin;
  const pages: CrawlPipelinePageResult[] = [];
  const issues: CrawlPipelineIssue[] = [];

  // 1. Initialize Link Graph
  const graphManager = new LinkGraphManager(`crawl_graph_${Date.now()}`, origin);

  // 2. Fetch and evaluate robots.txt
  let robotsParser: RobotsParser | undefined;
  let robotsTxtFound = false;
  let robotsSitemaps: string[] = [];

  try {
    const robotsRes = await fetchUrl(`${origin}/robots.txt`, { timeoutMs, allowLocalIp });
    if (robotsRes.status_code === 200 && robotsRes.html) {
      robotsParser = new RobotsParser(robotsRes.html);
      robotsTxtFound = true;
      robotsSitemaps = robotsParser.sitemaps;
    }
  } catch {
    // robots.txt unavailable or fetch error; proceed with default permissions
  }

  const robotsChecker = (url: string): boolean => {
    if (!respectRobots || !robotsParser) return true;
    try {
      const pathname = new URL(url).pathname;
      return robotsParser.isAllowed(pathname, userAgent);
    } catch {
      return true;
    }
  };

  // 3. Initialize URL Discovery Manager
  const discoveryConfig: Partial<DiscoveryConfig> = {
    maxDepth,
    maxPages,
    timeout: timeoutMs,
    allowedDomains: [new URL(seedUrl).hostname],
    robotsChecker
  };

  const discoveryManager = new URLDiscoveryManager(
    `disc_${Date.now()}`,
    seedUrl,
    discoveryConfig
  );

  // 4. Sitemap discovery and seeding
  const discoveredSitemapUrls: string[] = [];
  const candidateSitemaps = discoverSitemapCandidateUrls(seedUrl, robotsSitemaps);

  for (const sitemapUrl of candidateSitemaps) {
    try {
      const sitemapRes = await fetchUrl(sitemapUrl, { timeoutMs, allowLocalIp });
      if (sitemapRes.status_code === 200 && sitemapRes.html) {
        const parsedSitemap = parseSitemapXml(sitemapRes.html);
        discoveredSitemapUrls.push(sitemapUrl);

        if (parsedSitemap.urls.length > 0) {
          const locs = parsedSitemap.urls.map(u => u.loc);
          discoveryManager.addSitemapUrls(locs, sitemapUrl);
        }
      }
    } catch {
      // Non-fatal if candidate sitemap does not exist
    }
  }

  // 5. Main Crawl Loop
  let currentItem = discoveryManager.next();
  while (currentItem && pages.length < maxPages) {
    const url = currentItem.url;
    const depth = currentItem.depth;

    let fetchRes: FetchResult;
    try {
      fetchRes = await fetchUrl(url, { timeoutMs, allowLocalIp });
    } catch (err: any) {
      fetchRes = {
        url,
        status_code: 500,
        redirects: [],
        headers: {},
        response_time: 0,
        html: '',
        error: err.message
      };
    }

    if (fetchRes.status_code >= 400 || fetchRes.error) {
      discoveryManager.markFailed(url, fetchRes.error || `HTTP ${fetchRes.status_code}`, fetchRes.status_code);
      graphManager.addPage(url, fetchRes.status_code);

      // Record HTTP Error Issue
      issues.push({
        pageUrl: url,
        severity: fetchRes.status_code >= 500 ? 'critical' : 'high',
        category: 'status_code',
        message: `HTTP request failed with status ${fetchRes.status_code}`,
        recommendation: 'Fix broken links or server configuration causing HTTP error response.'
      });

      currentItem = discoveryManager.next();
      continue;
    }

    discoveryManager.markVisited(url, fetchRes.status_code, fetchRes.redirects.length);
    graphManager.addPage(url, fetchRes.status_code);

    // Parse HTML and SEO elements
    const parsedSeo: ParsedSEOData = parseHtml(fetchRes.html, url);
    const headings: HeadingExtractionResult = extractHeadingsFromHtml(fetchRes.html);
    const images: ImageExtractionResult = extractImagesFromHtml(fetchRes.html, url);
    const technical: TechnicalMetadata = TechnicalMetadataManager.extractMetadata(
      url,
      fetchRes.html,
      fetchRes.headers,
      fetchRes.response_time
    );

    // Robots directives detection
    const isNoindex = parsedSeo.metaRobots.toLowerCase().includes('noindex');
    const isNofollow = parsedSeo.metaRobots.toLowerCase().includes('nofollow');

    // Add extracted links to Link Graph and URL Discovery
    const internalLinks = parsedSeo.links.filter(l => l.isInternal);
    const externalLinks = parsedSeo.links.filter(l => !l.isInternal);

    for (const link of parsedSeo.links) {
      if (link.href) {
        graphManager.addLink(url, link.href, link.text, link.rel);
      }
    }

    if (!isNofollow) {
      const discoveredInternalUrls = internalLinks.map(l => l.href);
      discoveryManager.addDiscoveredUrls(discoveredInternalUrls, depth, url);
    }

    // Inspect Issues for this page
    if (!parsedSeo.title) {
      issues.push({
        pageUrl: url,
        severity: 'high',
        category: 'metadata',
        message: 'Page is missing a <title> tag',
        recommendation: 'Add a descriptive <title> tag between 30 and 60 characters.'
      });
    }

    if (!parsedSeo.metaDescription) {
      issues.push({
        pageUrl: url,
        severity: 'medium',
        category: 'metadata',
        message: 'Page is missing a meta description',
        recommendation: 'Add a compelling meta description between 120 and 160 characters.'
      });
    }

    if (headings.issues.missingH1) {
      issues.push({
        pageUrl: url,
        severity: 'high',
        category: 'content',
        message: 'Page has no <h1> heading',
        recommendation: 'Include exactly one primary <h1> heading summarizing the page topic.'
      });
    } else if (headings.issues.multipleH1) {
      issues.push({
        pageUrl: url,
        severity: 'low',
        category: 'content',
        message: 'Page contains multiple <h1> headings',
        recommendation: 'Structure the document with a single primary <h1> heading.'
      });
    }

    if (images.missingAltCount > 0) {
      issues.push({
        pageUrl: url,
        severity: 'medium',
        category: 'content',
        message: `Found ${images.missingAltCount} image(s) missing alt attributes`,
        recommendation: 'Provide meaningful alt text for all informative images.'
      });
    }

    const firstH1 = headings.flatHeadings.find(h => h.tag === 'h1')?.text || '';

    pages.push({
      url,
      depth,
      statusCode: fetchRes.status_code,
      contentType: technical.contentType,
      title: parsedSeo.title,
      metaDescription: parsedSeo.metaDescription,
      canonical: parsedSeo.canonical,
      h1: firstH1,
      wordCount: technical.wordCount,
      internalLinksCount: internalLinks.length,
      externalLinksCount: externalLinks.length,
      noindex: isNoindex,
      nofollow: isNofollow,
      responseTime: fetchRes.response_time,
      headings,
      images,
      technicalMetadata: technical
    });

    currentItem = discoveryManager.next();
  }

  const durationMs = Date.now() - startTime;
  const linkGraphSummary = graphManager.getSummary();

  return {
    seedUrl,
    status: 'completed',
    pages,
    issues,
    linkGraphSummary,
    robotsTxtFound,
    sitemapsFound: discoveredSitemapUrls,
    totalDiscovered: discoveryManager.getStats().totalDiscovered,
    totalCrawled: pages.length,
    totalFailed: discoveryManager.getStats().failedCount,
    durationMs
  };
}
