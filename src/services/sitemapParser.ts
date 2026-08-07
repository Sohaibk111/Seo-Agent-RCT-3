import * as cheerio from 'cheerio';

export interface SitemapImage {
  loc: string;
  title?: string;
  caption?: string;
}

export interface SitemapUrl {
  loc: string;
  lastmod?: string;
  changefreq?: string;
  priority?: number;
  images: SitemapImage[];
}

export interface SitemapChildIndex {
  loc: string;
  lastmod?: string;
}

export interface ParsedSitemapResult {
  isIndex: boolean;
  urls: SitemapUrl[];
  childSitemaps: SitemapChildIndex[];
  totalUrls: number;
  totalImages: number;
}

/**
 * Discovers standard candidate sitemap URLs for a given website URL,
 * plus any explicit sitemap URLs found in robots.txt.
 */
export function discoverSitemapCandidateUrls(baseUrl: string, robotsSitemaps: string[] = []): string[] {
  const candidates: string[] = [];
  
  // 1. Add sitemaps from robots.txt
  for (const sitemap of robotsSitemaps) {
    if (sitemap && !candidates.includes(sitemap)) {
      candidates.push(sitemap);
    }
  }

  // 2. Derive base origin and add standard sitemap locations
  try {
    const origin = new URL(baseUrl).origin;
    const defaultXml = `${origin}/sitemap.xml`;
    const defaultIndex = `${origin}/sitemap_index.xml`;

    if (!candidates.includes(defaultXml)) {
      candidates.push(defaultXml);
    }
    if (!candidates.includes(defaultIndex)) {
      candidates.push(defaultIndex);
    }
  } catch {
    // If baseUrl is invalid, return candidate list as is
  }

  return candidates;
}

/**
 * Parses XML sitemap string (handles both sitemap index and urlset with image sitemaps).
 */
export function parseSitemapXml(xmlContent: string): ParsedSitemapResult {
  const $ = cheerio.load(xmlContent || '', { xmlMode: true });

  const childSitemaps: SitemapChildIndex[] = [];
  const urls: SitemapUrl[] = [];

  // Check if it's a Sitemap Index (<sitemapindex>)
  const sitemapElements = $('sitemapindex > sitemap, sitemap');
  const urlElements = $('urlset > url, url');

  const isIndex = sitemapElements.length > 0 && $('sitemapindex').length > 0;

  if (isIndex || ($('sitemapindex').length > 0 && urlElements.length === 0)) {
    $('sitemapindex > sitemap, sitemap').each((_, el) => {
      const loc = $(el).find('loc').first().text().trim();
      const lastmod = $(el).find('lastmod').first().text().trim();
      if (loc) {
        childSitemaps.push({
          loc,
          lastmod: lastmod || undefined
        });
      }
    });

    return {
      isIndex: true,
      urls: [],
      childSitemaps,
      totalUrls: 0,
      totalImages: 0
    };
  }

  // Parse URL set (<urlset>)
  let totalImagesCount = 0;

  $('urlset > url, url').each((_, el) => {
    const loc = $(el).find('loc').first().text().trim();
    if (!loc) return;

    const lastmod = $(el).find('lastmod').first().text().trim() || undefined;
    const changefreq = $(el).find('changefreq').first().text().trim() || undefined;
    const priorityRaw = $(el).find('priority').first().text().trim();
    let priority: number | undefined = undefined;
    if (priorityRaw) {
      const parsed = parseFloat(priorityRaw);
      if (!isNaN(parsed)) {
        priority = parsed;
      }
    }

    // Extract image sitemaps (<image:image>)
    const images: SitemapImage[] = [];
    
    // Cheerio with xmlMode allows selecting image\\:image or image
    $(el).find('image\\:image, image').each((_, imgEl) => {
      const imgLoc = $(imgEl).find('image\\:loc, loc').first().text().trim();
      const imgTitle = $(imgEl).find('image\\:title, title').first().text().trim() || undefined;
      const imgCaption = $(imgEl).find('image\\:caption, caption').first().text().trim() || undefined;

      if (imgLoc) {
        images.push({
          loc: imgLoc,
          title: imgTitle,
          caption: imgCaption
        });
      }
    });

    totalImagesCount += images.length;

    urls.push({
      loc,
      lastmod,
      changefreq,
      priority,
      images
    });
  });

  return {
    isIndex: false,
    urls,
    childSitemaps,
    totalUrls: urls.length,
    totalImages: totalImagesCount
  };
}
